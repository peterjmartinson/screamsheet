"""show_prompt — print the fully-rendered LLM prompt for any screamsheet source.

Fetches real data, builds the same data dict that gets passed to the LLM,
and prints it without ever calling the LLM.  Useful for reviewing prompt
quality and debugging unexpected outputs.

Usage
-----
    uv run show_prompt                        # interactive menu
    uv run show_prompt --source sky           # non-interactive
    uv run show_prompt --source nhl --date 2026-04-18
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Per-source data builders
# Each returns (data_dict, summarizer_instance) where data_dict is exactly
# what would be passed to summarizer.generate_summary(..., data=data_dict).
# ---------------------------------------------------------------------------

def _build_sky(date: datetime) -> Tuple[Dict[str, Any], Any]:
    from screamsheet.config import load_config
    from screamsheet.providers.sky_provider import SkyDataProvider
    from screamsheet.llm.summarizers import SkyNightSummarizer

    cfg = load_config()
    provider = SkyDataProvider(
        lat=cfg.sky.lat,
        lon=cfg.sky.lon,
        location_name=cfg.sky.location_name,
    )
    sky = provider.get_sky_data(date)
    planets_str = ", ".join(
        f"{p['name']} in {p['zodiac']}"
        for p in sky.get("planets", [])
        if p.get("name") not in {"Uranus", "Neptune"}
    )
    data: Dict[str, Any] = {
        "planets":    planets_str,
        "moon_phase": sky.get("moon_phase", ""),
        "highlights": "\n".join(sky.get("highlights", [])),
        "location":   cfg.sky.location_name,
        "date":       date.strftime("%B %d, %Y"),
    }
    return data, SkyNightSummarizer()


def _build_nhl(date: datetime) -> Tuple[Dict[str, Any], Any]:
    from screamsheet.config import load_config
    from screamsheet.providers.nhl_provider import NHLProvider
    from screamsheet.providers.extractors import NHLGameExtractor
    from screamsheet.llm.summarizers import NHLGameSummarizer

    cfg = load_config()
    teams = cfg.nhl.favorite_teams
    if not teams:
        raise ValueError("No NHL favorite_teams configured in config.yaml")
    team = teams[0]

    provider = NHLProvider()
    extractor = NHLGameExtractor()

    for delta in range(4):  # today, yesterday, 2 days ago, 3 days ago
        d = date - timedelta(days=delta)
        game_pk = provider._get_game_pk(team.id, d)
        if game_pk:
            raw = extractor.fetch_raw_data(game_pk)
            data = extractor.extract_key_info(raw)
            if isinstance(data, dict):
                return data, NHLGameSummarizer()

    raise ValueError(
        f"No completed NHL game found for {team.name} in the last 4 days"
    )


def _build_mlb(date: datetime) -> Tuple[Dict[str, Any], Any]:
    from screamsheet.config import load_config
    from screamsheet.providers.extractors import MLBGameExtractor
    from screamsheet.llm.summarizers import MLBGameSummarizer

    cfg = load_config()
    teams = cfg.mlb.favorite_teams
    if not teams:
        raise ValueError("No MLB favorite_teams configured in config.yaml")
    team = teams[0]

    extractor = MLBGameExtractor()

    for delta in range(4):
        d = date - timedelta(days=delta)
        raw = extractor.fetch_raw_data(team.id, d.strftime("%Y-%m-%d"))
        if raw:
            data = extractor.extract_key_info(raw)
            if isinstance(data, dict):
                return data, MLBGameSummarizer()

    raise ValueError(
        f"No completed MLB game found for {team.name} in the last 4 days"
    )


def _build_mlb_news(date: datetime) -> Tuple[Dict[str, Any], Any]:
    from screamsheet.config import load_config
    from screamsheet.providers.mlb_news_rss_provider import MLBNewsRssProvider
    from screamsheet.llm.summarizers import NewsSummarizer

    cfg = load_config()
    names = cfg.mlb.news_names or [t.name for t in cfg.mlb.favorite_teams]
    provider = MLBNewsRssProvider(favorite_teams=names, max_articles=4)
    articles = provider.get_articles()
    articles = provider.sanitize_articles(articles)
    if not articles:
        raise ValueError("No MLB news articles available from RSS")

    entry = articles[0]["entry"]
    data = {
        "id":      entry.get("id", entry.get("link", "")),
        "title":   entry.get("title", "Untitled"),
        "summary": entry.get("summary", ""),
        "link":    entry.get("link", ""),
    }
    return data, NewsSummarizer()


def _build_political_news(date: datetime) -> Tuple[Dict[str, Any], Any]:
    from screamsheet.providers.political_news_provider import PoliticalNewsProvider
    from screamsheet.llm.summarizers import PoliticalNewsSummarizer

    provider = PoliticalNewsProvider(max_articles=4)
    articles = provider.get_articles()
    articles = provider.sanitize_articles(articles)
    if not articles:
        raise ValueError("No political news articles available")

    entry = articles[0]["entry"]
    data = {
        "id":      entry.get("id", entry.get("link", "")),
        "title":   entry.get("title", "Untitled"),
        "summary": entry.get("summary", ""),
        "link":    entry.get("link", ""),
    }
    return data, PoliticalNewsSummarizer()


# ---------------------------------------------------------------------------
# Registry: (key, display_label, builder_fn)
# ---------------------------------------------------------------------------

_SOURCES: list[tuple[str, str, Callable[[datetime], Tuple[Dict[str, Any], Any]]]] = [
    ("sky",      "Sky Tonight",           _build_sky),
    ("nhl",      "NHL Game Summary",      _build_nhl),
    ("mlb",      "MLB Game Summary",      _build_mlb),
    ("mlb_news", "MLB News Article",      _build_mlb_news),
    ("political","Political News Article",_build_political_news),
]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

_SEP = "=" * 72


def _print_prompt(label: str, data: Dict[str, Any], summarizer: Any) -> None:
    """Print input variables, the filled template, and the full final prompt."""
    filled: str = summarizer._build_llm_prompt(data)

    # Reconstruct the full string that LangChain assembles before sending to the LLM.
    # See BaseGameSummaryGenerator._setup_prompt_chain in llm/base.py.
    full_prompt = (
        "Here is the input data:\n\n"
        + json.dumps(data, indent=2)
        + "\n\nInstruction: "
        + filled
    )

    print(f"\n{_SEP}")
    print(f"  SOURCE : {label}")
    print(_SEP)

    print("\n── INPUT VARIABLES ──────────────────────────────────────────────")
    for key, value in data.items():
        v_str = str(value)
        # Show first 300 chars; replace newlines with a visible marker
        preview = v_str[:300].replace("\n", "\n              ")
        suffix = "  [truncated]" if len(v_str) > 300 else ""
        print(f"  {key!r:16s}  {preview}{suffix}")

    print("\n── FILLED PROMPT TEMPLATE ───────────────────────────────────────")
    print(filled)

    print("\n── FULL FINAL PROMPT (as sent to LLM) ───────────────────────────")
    print(full_prompt)

    print(f"\n{_SEP}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="show_prompt",
        description=(
            "Print the fully-rendered LLM prompt for a screamsheet source "
            "without calling the LLM."
        ),
    )
    parser.add_argument(
        "--source",
        choices=[s[0] for s in _SOURCES],
        metavar="SOURCE",
        help=(
            "Which source to show: "
            + ", ".join(s[0] for s in _SOURCES)
            + ".  Omit for interactive menu."
        ),
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        metavar="YYYY-MM-DD",
        help="Target date (default: today).",
    )
    args = parser.parse_args()

    try:
        date = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"ERROR: --date must be YYYY-MM-DD, got: {args.date!r}")
        sys.exit(1)

    # Resolve source key -------------------------------------------------
    if args.source:
        key: Optional[str] = args.source
    else:
        print("\nScreamsheet sources that send prompts to the LLM:\n")
        for i, (k, label, _) in enumerate(_SOURCES, 1):
            print(f"  {i}.  {label}  [{k}]")
        print()
        raw = input("Pick a number or key: ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            key = _SOURCES[idx][0] if 0 <= idx < len(_SOURCES) else None
        else:
            key = raw if any(s[0] == raw for s in _SOURCES) else None

        if key is None:
            print("Invalid selection.")
            sys.exit(1)

    match = next((s for s in _SOURCES if s[0] == key), None)
    if match is None:
        print(f"Unknown source: {key!r}")
        sys.exit(1)

    _, label, builder = match
    print(f"\nFetching data for '{label}' on {date.strftime('%Y-%m-%d')} …")

    try:
        data, summarizer = builder(date)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)

    _print_prompt(label, data, summarizer)
