"""Gmail IMAP provider for retrieving news emails under a specific label."""
from __future__ import annotations

import email
import email.header
import email.utils
import imaplib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from email.message import Message
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _decode_header_value(raw: Optional[str]) -> str:
    """Return a decoded plain string from an RFC 2047 encoded email header."""
    if not raw:
        return ""
    try:
        parts = email.header.decode_header(raw)
        decoded_parts: List[str] = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded_parts.append(str(part))
        return "".join(decoded_parts).strip()
    except Exception as exc:
        logger.debug("Error decoding header %r: %s", raw, exc)
        return str(raw).strip()


def _parse_sender(from_header: str) -> Tuple[str, str]:
    """
    Parse a 'From' header into (display_name, email_address).

    Handles formats like:
      - 'Not Even Wrong <donotreply@wordpress.com>' -> ('Not Even Wrong', 'donotreply@wordpress.com')
      - 'newsletters@punchbowl.news' -> ('Punchbowl News', 'newsletters@punchbowl.news')
      - 'Politico <politico@politico.com>' -> ('Politico', 'politico@politico.com')
    """
    if not from_header:
        return ("", "")

    raw_name, raw_addr = email.utils.parseaddr(from_header)
    name = _decode_header_value(raw_name).strip()
    addr = raw_addr.strip().lower()

    if name:
        return (name, addr)

    # Derive a clean display name from the domain if the name is absent
    if "@" in addr:
        domain = addr.split("@")[-1]
        domain_parts = domain.split(".")
        if len(domain_parts) >= 2:
            base_name = domain_parts[0].capitalize()
            return (base_name, addr)

    return (addr, addr)


def _extract_body_text(msg: Message, max_chars: int = 80000) -> str:
    """Extract and sanitize plain text from an email message.

    Prefers HTML rendered text via BeautifulSoup because newsletters include
    massive tracking links and ugly formatting in their text/plain fallback.
    """
    plain_text = ""
    html_text = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition.lower():
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                decoded = payload.decode("utf-8", errors="replace")

            if content_type == "text/html" and not html_text:
                html_text = decoded.strip()
            elif content_type == "text/plain" and not plain_text:
                plain_text = decoded.strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                decoded = payload.decode("utf-8", errors="replace")
            if msg.get_content_type() == "text/html":
                html_text = decoded.strip()
            else:
                plain_text = decoded.strip()

    body = ""
    if html_text:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            for tag in soup(["script", "style", "head", "title", "meta", "noscript"]):
                tag.decompose()
            body = soup.get_text(separator="\n", strip=True)
        except Exception:
            body = html_text
    elif plain_text:
        # Strip long URL tracking links in brackets <https://...>
        cleaned_plain = re.sub(r"<https?://[^>]+>", "", plain_text)
        body = cleaned_plain

    # Collapse excessive blank lines
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if max_chars and len(body) > max_chars:
        body = body[:max_chars] + "\n... [truncated]"
    return body


class GmailNewsProvider:
    """
    Fetches news emails received in the past 24 hours under a specified Gmail label.
    """

    def __init__(
        self,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        label: str = "Morning Briefing",
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        timeout: int = 25,
    ) -> None:
        self.username = username or os.getenv("GMAIL_USERNAME") or ""
        self.app_password = app_password or os.getenv("GMAIL_APP_PASSWORD") or ""

        # Fallback to local and user config .env files if not in os.environ
        if not self.username or not self.app_password:
            from pathlib import Path
            import dotenv
            candidates = [
                Path.home() / ".config" / "screamsheet" / ".env",
                Path(__file__).resolve().parent.parent.parent.parent / ".env",
                Path.home() / "Code" / "dispatch" / ".env",
            ]
            for candidate in candidates:
                if candidate.is_file():
                    vals = dotenv.dotenv_values(candidate)
                    if not self.username and "GMAIL_USERNAME" in vals:
                        self.username = vals["GMAIL_USERNAME"]
                    if not self.app_password and "GMAIL_APP_PASSWORD" in vals:
                        self.app_password = vals["GMAIL_APP_PASSWORD"]
                if self.username and self.app_password:
                    break

        self.label = label
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.timeout = timeout

    def fetch_emails(
        self,
        since: Optional[datetime] = None,
        lookback_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails received within the lookback window under self.label.

        Args:
            since: Reference datetime (defaults to current UTC time).
            lookback_hours: Number of hours to look back (defaults to 24).

        Returns:
            List of dictionaries containing:
                - id: Message UID
                - subject: Email subject line
                - sender: Display sender name (e.g. "Not Even Wrong", "Punchbowl News")
                - sender_email: Email address
                - date: Message datetime (timezone-aware)
                - body: Cleaned body text
        """
        if not self.username or not self.app_password:
            logger.info("Gmail credentials not configured (GMAIL_USERNAME / GMAIL_APP_PASSWORD). Skipping email news.")
            return []

        ref_dt = since if since is not None else datetime.now(timezone.utc)
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=timezone.utc)

        cutoff_dt = ref_dt - timedelta(hours=lookback_hours)

        emails: List[Dict[str, Any]] = []
        try:
            logger.info("Connecting to %s:%d to fetch label %r", self.imap_host, self.imap_port, self.label)
            imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            imap.sock.settimeout(self.timeout)

            try:
                imap.login(self.username, self.app_password)

                # Select mailbox (try quoted and unquoted if needed)
                status, data = imap.select(f'"{self.label}"', readonly=True)
                if status != "OK":
                    status, data = imap.select(self.label, readonly=True)

                if status != "OK":
                    logger.info("Could not select mailbox/label %r in Gmail: %s", self.label, data)
                    return []

                # Search messages
                search_status, search_data = imap.uid("SEARCH", None, "ALL")
                if search_status != "OK" or not search_data or not search_data[0]:
                    logger.info("No messages found under label %r", self.label)
                    return []

                uids = search_data[0].decode().split()
                # Process most recent first
                for uid in reversed(uids):
                    try:
                        fetch_status, msg_data = imap.uid("FETCH", uid, "(RFC822)")
                        if fetch_status != "OK" or not msg_data:
                            continue

                        raw_bytes = None
                        for item in msg_data:
                            if isinstance(item, tuple) and len(item) >= 2:
                                raw_bytes = item[1]
                                break

                        if not raw_bytes:
                            continue

                        msg = email.message_from_bytes(raw_bytes)

                        # Parse message date
                        date_header = msg.get("Date", "")
                        try:
                            msg_dt = email.utils.parsedate_to_datetime(date_header)
                            if msg_dt.tzinfo is None:
                                msg_dt = msg_dt.replace(tzinfo=timezone.utc)
                        except Exception:
                            # If date cannot be parsed, accept it
                            msg_dt = ref_dt

                        # Filter by cutoff time
                        if msg_dt < cutoff_dt:
                            continue

                        subject = _decode_header_value(msg.get("Subject", "(No Subject)"))
                        sender_name, sender_email = _parse_sender(msg.get("From", ""))
                        body = _extract_body_text(msg)

                        emails.append(
                            {
                                "id": uid,
                                "subject": subject,
                                "sender": sender_name,
                                "sender_email": sender_email,
                                "date": msg_dt,
                                "body": body,
                            }
                        )
                    except Exception as e:
                        logger.warning("Failed to parse message UID %s: %s", uid, e)

            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        except Exception as e:
            logger.error("Failed to connect or fetch emails from Gmail: %s", e)
            return []

        logger.info("Fetched %d email(s) from label %r within past %d hours", len(emails), self.label, lookback_hours)
        return emails

    def fetch_important_emails(
        self,
        important_senders: List[str],
        since: Optional[datetime] = None,
        lookback_hours: int = 24,
        mailbox: str = "INBOX",
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from priority senders (matching specific addresses or domains)
        received in the past lookback_hours.

        Args:
            important_senders: List of email addresses or domains (e.g. ['annashavin@gmail.com', 'mainlineclassical.org'])
            since: Reference datetime (defaults to current UTC time).
            lookback_hours: Hours to look back (default 24).
            mailbox: Mailbox to search (default 'INBOX').

        Returns:
            List of matched email dicts.
        """
        if not self.username or not self.app_password:
            logger.info("Gmail credentials not configured. Skipping important emails.")
            return []

        if not important_senders:
            return []

        ref_dt = since if since is not None else datetime.now(timezone.utc)
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=timezone.utc)

        cutoff_dt = ref_dt - timedelta(hours=lookback_hours)
        since_date_str = (ref_dt - timedelta(days=2)).strftime("%d-%b-%Y")

        emails: List[Dict[str, Any]] = []
        try:
            logger.info("Connecting to %s:%d to search %r for %d priority sender(s)", self.imap_host, self.imap_port, mailbox, len(important_senders))
            imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            imap.sock.settimeout(self.timeout)

            try:
                imap.login(self.username, self.app_password)
                status, data = imap.select(f'"{mailbox}"', readonly=True)
                if status != "OK":
                    status, data = imap.select(mailbox, readonly=True)

                if status != "OK":
                    logger.info("Could not select mailbox %r in Gmail: %s", mailbox, data)
                    return []

                # Search by SINCE date to limit scope
                search_status, search_data = imap.uid("SEARCH", None, f'SINCE "{since_date_str}"')
                if search_status != "OK" or not search_data or not search_data[0]:
                    search_status, search_data = imap.uid("SEARCH", None, "ALL")

                if search_status != "OK" or not search_data or not search_data[0]:
                    return []

                uids = search_data[0].decode().split()
                # Process most recent first
                for uid in reversed(uids):
                    try:
                        fetch_status, msg_data = imap.uid("FETCH", uid, "(RFC822)")
                        if fetch_status != "OK" or not msg_data:
                            continue

                        raw_bytes = None
                        for item in msg_data:
                            if isinstance(item, tuple) and len(item) >= 2:
                                raw_bytes = item[1]
                                break

                        if not raw_bytes:
                            continue

                        msg = email.message_from_bytes(raw_bytes)

                        # Check sender first to avoid parsing body of non-matching emails
                        from_header = msg.get("From", "")
                        sender_name, sender_email = _parse_sender(from_header)

                        if not _matches_important_sender(sender_email, important_senders):
                            continue

                        # Parse message date
                        date_header = msg.get("Date", "")
                        try:
                            msg_dt = email.utils.parsedate_to_datetime(date_header)
                            if msg_dt.tzinfo is None:
                                msg_dt = msg_dt.replace(tzinfo=timezone.utc)
                        except Exception:
                            msg_dt = ref_dt

                        if msg_dt < cutoff_dt:
                            continue

                        subject = _decode_header_value(msg.get("Subject", "(No Subject)"))
                        body = _extract_body_text(msg)

                        emails.append(
                            {
                                "id": uid,
                                "subject": subject,
                                "sender": sender_name,
                                "sender_email": sender_email,
                                "date": msg_dt,
                                "body": body,
                            }
                        )
                    except Exception as e:
                        logger.warning("Failed to parse message UID %s: %s", uid, e)

            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        except Exception as e:
            logger.error("Failed to connect or fetch priority emails from Gmail: %s", e)
            return []

        logger.info("Found %d priority email(s) from %d sender patterns within past %d hours", len(emails), len(important_senders), lookback_hours)
        return emails


def _matches_important_sender(sender_email: str, important_senders: List[str]) -> bool:
    """Check whether sender_email matches any address or domain pattern."""
    if not sender_email or not important_senders:
        return False
    _, extracted_addr = email.utils.parseaddr(sender_email)
    if extracted_addr:
        email_clean = extracted_addr.strip().lower()
    else:
        email_clean = sender_email.strip().lower()

    for item in important_senders:
        pattern = item.strip().lower()
        if not pattern:
            continue
        if email_clean == pattern:
            return True
        domain = pattern.lstrip("@")
        if email_clean.endswith(f"@{domain}") or email_clean.endswith(f".{domain}"):
            return True
    return False
