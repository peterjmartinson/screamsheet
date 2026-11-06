"""Weather Patterns & Teleconnections Screamsheet implementation.

Combines objective large-scale atmospheric/climate indices (AO, NAO, PNA, MJO,
ENSO, Stratospheric Polar Vortex), deterministic signal-change calculations,
local NWS observations/forecasts and NCEI 1991–2020 climatological anomalies,
optional snow-stake/snowfall tracking, B&W print-friendly vector charts, and
a strictly grounded LLM meteorological briefing.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepInFrame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from ..base import BaseScreamsheet
from ..config import (
    WeatherPatternsConfig,
    WeatherPatternsLocationConfig,
)
from ..llm.config import LLMConfig
from ..llm.summarizers import WeatherPatternsSummarizer
from .charts import (
    MJO_PHASE_REGIONS,
    build_enso_sparkline,
    build_forecast_evolution_chart,
    build_local_pressure_chart,
    build_local_temperature_chart,
    build_mjo_phase_diagram,
    build_polar_vortex_chart,
    build_snow_watch_chart,
    build_teleconnections_chart,
)
from .models import (
    LocalLocationBundle,
    SourceProvenance,
    WeatherPatternsDataBundle,
)
from .signals import compute_derived_signals

logger = logging.getLogger(__name__)


def _pressure_tendency_label(change_24h: Optional[float]) -> str:
    if change_24h is None:
        return "Steady"
    if change_24h >= 2.0:
        return "Rising"
    if change_24h <= -2.0:
        return "Falling"
    return "Steady"


def _format_afd_paragraphs(raw_afd: str, max_chars: int = 900) -> List[str]:
    """Clean and format NWS AFD synopsis/key-messages text into HTML-safe paragraphs."""
    if not raw_afd or not raw_afd.strip():
        return []
    text = re.sub(r"\s+", " ", raw_afd).strip()

    # Parse [SECTION] blocks if present
    tag_matches = list(
        re.finditer(
            r"\[([A-Z0-9 /&-]+)\]\s*(.*?)(?=\s*\[[A-Z0-9 /&-]+\]|\Z)",
            text,
        )
    )
    if not tag_matches:
        cut = text[:max_chars]
        if len(text) > max_chars and "." in cut:
            cut = cut[: cut.rfind(".") + 1]
        return [escape(cut)]

    key_msg_sentences: List[str] = []
    paragraphs: List[str] = []
    total_len = 0

    label_map = {
        "SYNOPSIS": "Synopsis",
        "KEY MESSAGES": "Key Message",
        "WHAT HAS CHANGED": "Forecast Update",
        "DISCUSSION": "Synoptic Discussion",
        "NEAR TERM": "Near Term",
        "SHORT TERM": "Short Term",
    }

    for m in tag_matches:
        sec_key = m.group(1).strip().upper()
        body = m.group(2).strip()
        if not body:
            continue
        body_low = body.lower()
        if sec_key == "WHAT HAS CHANGED":
            if (
                "no major change" in body_low
                or "no significant change" in body_low
                or body_low in ("none.", "none", "n/a")
                or (len(body) < 60 and "taf" in body_low)
            ):
                continue

        if sec_key == "KEY MESSAGES":
            body = re.sub(r"(?:^|\s)-\s*\d+\)\s*", " ", body).strip()
            for s in re.split(r"(?<=[.!?])\s+", body):
                if len(s.strip()) > 15:
                    key_msg_sentences.append(s.strip())
        elif sec_key == "DISCUSSION":
            body = re.sub(
                r"KEY MESSAGE\s*\d+\.{2,}\s*", "", body, flags=re.IGNORECASE
            ).strip()
            for km_s in key_msg_sentences:
                if body.lower().startswith(km_s.lower()):
                    body = body[len(km_s) :].strip()
            body = re.sub(
                r"KEY MESSAGE\s*\d+\.{2,}\s*", " ", body, flags=re.IGNORECASE
            ).strip()

        if not body:
            continue

        remaining = max_chars - total_len
        if remaining < 80:
            break
        if len(body) > remaining:
            cut = body[:remaining]
            if "." in cut:
                body = cut[: cut.rfind(".") + 1].strip()
            else:
                body = cut.rsplit(" ", 1)[0].strip() + "..."
        elif body.endswith("..."):
            trimmed = body[:-3].rstrip()
            if "." in trimmed:
                body = trimmed[: trimmed.rfind(".") + 1].strip()

        display_lbl = label_map.get(sec_key, sec_key.title())
        paragraphs.append(f"<b>{escape(display_lbl)}:</b> {escape(body)}")
        total_len += len(body)

    return paragraphs


class WeatherPatternsScreamsheet(BaseScreamsheet):
    """Multi-page morning weather-pattern and teleconnections screamsheet."""

    def __init__(
        self,
        output_filename: Optional[str] = None,
        target_date: Optional[datetime] = None,
        weather_patterns_config: Optional[WeatherPatternsConfig] = None,
        gemini_api_key: Optional[str] = None,
        grok_api_key: Optional[str] = None,
        data_bundle: Optional[WeatherPatternsDataBundle] = None,
        use_cache: bool = True,
        refresh_cache: bool = False,
    ) -> None:
        super().__init__(
            output_filename=output_filename or "WEATHER_PATTERNS.pdf",
            date=target_date,
        )
        self.title = "Climate Screamsheet"
        self.wp_config = weather_patterns_config or WeatherPatternsConfig(
            locations=[
                WeatherPatternsLocationConfig(
                    name="Bryn Mawr, PA",
                    lat=40.02,
                    lon=-75.34,
                ),
            ]
        )
        self.gemini_api_key = gemini_api_key
        self.grok_api_key = grok_api_key
        self._bundle: Optional[WeatherPatternsDataBundle] = data_bundle
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache
        self._wp_styles = self._create_wp_styles()

    def get_title(self) -> str:
        return "Climate Screamsheet"

    def _create_wp_styles(self) -> Dict[str, ParagraphStyle]:
        base_style = self.styles["Normal"]
        return {
            "section_hdr": ParagraphStyle(
                "WP_SectionHdr",
                parent=base_style,
                fontName="Helvetica-Bold",
                fontSize=13.0,
                leading=15.5,
                textColor=colors.black,
                spaceBefore=2,
                spaceAfter=2,
            ),
            "back_section_hdr": ParagraphStyle(
                "WP_BackSectionHdr",
                parent=base_style,
                fontName="Helvetica-Bold",
                fontSize=13.5,
                leading=16.5,
                textColor=colors.black,
                spaceBefore=4,
                spaceAfter=2,
            ),
            "sub_hdr": ParagraphStyle(
                "WP_SubHdr",
                parent=base_style,
                fontName="Helvetica-Bold",
                fontSize=10.5,
                leading=13.0,
                textColor=colors.black,
                spaceBefore=2,
                spaceAfter=2,
            ),
            "narrative_p": ParagraphStyle(
                "WP_NarrativeP",
                parent=base_style,
                fontName="Helvetica",
                fontSize=11.0,
                leading=13.8,
                spaceAfter=4.0,
            ),
            "back_body": ParagraphStyle(
                "WP_BackBody",
                parent=base_style,
                fontName="Helvetica",
                fontSize=10.8,
                leading=14.8,
                spaceAfter=5.5,
            ),
            "back_list_item": ParagraphStyle(
                "WP_BackListItem",
                parent=base_style,
                fontName="Helvetica",
                fontSize=11.0,
                leading=15.0,
                leftIndent=8,
                spaceAfter=2.5,
            ),
            "table_cell": ParagraphStyle(
                "WP_TableCell",
                parent=base_style,
                fontName="Helvetica",
                fontSize=8.8,
                leading=10.8,
            ),
            "table_hdr": ParagraphStyle(
                "WP_TableHdr",
                parent=base_style,
                fontName="Helvetica-Bold",
                fontSize=9.0,
                leading=11.0,
                textColor=colors.black,
            ),
            "back_table_cell": ParagraphStyle(
                "WP_BackTableCell",
                parent=base_style,
                fontName="Helvetica",
                fontSize=10.0,
                leading=12.5,
            ),
            "back_table_hdr": ParagraphStyle(
                "WP_BackTableHdr",
                parent=base_style,
                fontName="Helvetica-Bold",
                fontSize=10.0,
                leading=12.5,
                textColor=colors.black,
            ),
        }

    def get_subtitle(self) -> Optional[str]:
        if self._bundle and self._bundle.locations:
            return self._bundle.locations[0].name
        if self.wp_config.locations:
            return self.wp_config.locations[0].name
        return self.wp_config.weather.location_name

    def _section_header_flowables(
        self, title_text: str, back_page: bool = False
    ) -> List[Any]:
        style_key = "back_section_hdr" if back_page else "section_hdr"
        return [
            Paragraph(escape(title_text), self._wp_styles[style_key]),
            HRFlowable(
                width="100%",
                thickness=1.0,
                color=colors.black,
                spaceBefore=1,
                spaceAfter=6 if back_page else 4,
            ),
        ]

    # ------------------------------------------------------------------
    # Data orchestration & normalization
    # ------------------------------------------------------------------
    def collect_data_bundle(self) -> WeatherPatternsDataBundle:
        """Fetch, normalize, and compute derived signals across all providers."""
        if self._bundle is not None:
            if not self._bundle.derived or not self._bundle.derived.flags:
                self._bundle.derived = compute_derived_signals(
                    teleconnections=self._bundle.teleconnections,
                    stratosphere=self._bundle.stratosphere,
                    mjo=self._bundle.mjo,
                    enso=self._bundle.enso,
                    locations=self._bundle.locations,
                    forecast_vintages=self._bundle.forecast_vintages,
                )
            elif not self._bundle.derived.forecast_evolution:
                self._bundle.derived = compute_derived_signals(
                    teleconnections=self._bundle.teleconnections,
                    stratosphere=self._bundle.stratosphere,
                    mjo=self._bundle.mjo,
                    enso=self._bundle.enso,
                    locations=self._bundle.locations,
                    forecast_vintages=self._bundle.forecast_vintages,
                )
            if not self._bundle.narrative_text:
                if self.wp_config.narrative.enabled:
                    self._bundle.narrative_text = self._generate_narrative(self._bundle)
                else:
                    self._bundle.narrative_text = self._build_deterministic_fallback_narrative(self._bundle)
            return self._bundle

        cfg = self.wp_config
        provenance_list: List[SourceProvenance] = []

        from ..providers.climate_history_provider import ClimateHistoryProvider
        from ..providers.enso_provider import ENSOProvider
        from ..providers.mjo_provider import MJOProvider
        from ..providers.nws_patterns_provider import NWSWeatherPatternsProvider
        from ..providers.snow_provider import SnowProvider
        from ..providers.stratosphere_provider import StratosphereProvider
        from ..providers.teleconnection_provider import TeleconnectionProvider

        # 1. Teleconnections (AO, NAO, PNA)
        tele_prov = TeleconnectionProvider(
            history_days=cfg.history_days,
            forecast_days=cfg.forecast_days,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )
        teleconnections = tele_prov.get_all_teleconnections(target_date=self.date)
        for tb in teleconnections.values():
            if tb.obs_provenance:
                provenance_list.append(tb.obs_provenance)
            if tb.fcst_provenance:
                provenance_list.append(tb.fcst_provenance)

        # 2. MJO (NOAA PSL ROMI)
        mjo_prov = MJOProvider(
            history_days=cfg.history_days,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )
        mjo_bundle = mjo_prov.get_mjo_bundle(target_date=self.date)
        if mjo_bundle.provenance:
            provenance_list.append(mjo_bundle.provenance)

        # 3. ENSO (NOAA CPC Niño 3.4, ONI, RONI + PSL MEI.v2)
        enso_prov = ENSOProvider(
            months_to_keep=24,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )
        enso_bundle = enso_prov.get_enso_bundle(target_date=self.date)
        if enso_bundle.provenance:
            provenance_list.append(enso_bundle.provenance)

        # 4. Stratospheric Polar Vortex (10 hPa 60°N U-wind & 60–90°N Cap Temp)
        strat_prov = StratosphereProvider(
            history_days=cfg.history_days,
            forecast_days=cfg.forecast_days,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )
        strat_bundle = strat_prov.get_stratosphere_bundle(target_date=self.date)
        if strat_bundle.provenance:
            provenance_list.append(strat_bundle.provenance)

        # 5, 6, 7. Local NWS + NCEI Climate Normals + Snow for each configured location
        nws_prov = NWSWeatherPatternsProvider(
            include_afd=cfg.narrative.include_afd,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )
        clim_prov = ClimateHistoryProvider(
            history_days=max(35, cfg.history_days),
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )
        snow_prov = SnowProvider(
            history_days=max(35, cfg.history_days),
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )

        locations: List[LocalLocationBundle] = []
        for loc_cfg in cfg.locations:
            loc_bundle = nws_prov.get_location_nws_bundle(
                name=loc_cfg.name,
                lat=loc_cfg.lat,
                lon=loc_cfg.lon,
                station_override=loc_cfg.station,
                target_date=self.date,
            )
            clim_prov.enrich_location_climate(loc_bundle, target_date=self.date)
            snow_prov.enrich_location_snow(
                loc_bundle,
                explicit_snow_station=loc_cfg.snow_station,
                target_date=self.date,
            )
            if loc_bundle.nws_provenance:
                provenance_list.append(loc_bundle.nws_provenance)
            if loc_bundle.climate_provenance:
                provenance_list.append(loc_bundle.climate_provenance)
            if loc_bundle.snow and loc_bundle.snow.provenance:
                provenance_list.append(loc_bundle.snow.provenance)
            locations.append(loc_bundle)

        report_date_str = self.date.strftime("%Y-%m-%d")

        # V2 Workflow: Persist observations & current forecast vintages, then query historical DB
        forecast_vintages: Dict[str, List[Dict[str, Any]]] = {}
        verification_summary: Dict[str, Any] = {}
        try:
            from ..db.weather_patterns_db import (
                compute_teleconnection_verification_stats,
                get_forecast_vintages_for_metric,
                get_local_pressure_history,
                get_stratosphere_obs_history,
                get_teleconnection_obs_history,
                persist_weather_patterns_bundle,
            )

            prelim_bundle = WeatherPatternsDataBundle(
                report_date=report_date_str,
                teleconnections=teleconnections,
                stratosphere=strat_bundle,
                mjo=mjo_bundle,
                enso=enso_bundle,
                locations=locations,
                provenance_list=provenance_list,
            )
            persist_weather_patterns_bundle(prelim_bundle)

            # Query historical observations from DB where helpful (e.g., if today's fetch had gaps or for pressure retention)
            for code, tb in teleconnections.items():
                if not tb.observations:
                    db_obs = get_teleconnection_obs_history(
                        code, limit_days=cfg.history_days, up_to_date=report_date_str
                    )
                    if db_obs:
                        tb.observations = db_obs
                forecast_vintages[code] = get_forecast_vintages_for_metric(
                    metric=code,
                    model="GEFS",
                    up_to_run_time=report_date_str,
                    max_runs=8,
                )
                ver_stats = compute_teleconnection_verification_stats(code)
                if ver_stats.get("has_sufficient_data_for_display"):
                    verification_summary[code] = ver_stats

            if strat_bundle and not strat_bundle.observations:
                db_strat = get_stratosphere_obs_history(
                    limit_days=cfg.history_days, up_to_date=report_date_str
                )
                if db_strat:
                    strat_bundle.observations = db_strat

            forecast_vintages["U60N_10HPA"] = get_forecast_vintages_for_metric(
                metric="U60N_10HPA",
                model="GEOS5_FP",
                up_to_run_time=report_date_str,
                max_runs=8,
            )

            for loc_b in locations:
                if not loc_b.pressure_series:
                    db_press = get_local_pressure_history(
                        location_name=loc_b.name,
                        station_id=loc_b.station_id,
                        limit_hours=168,
                    )
                    if db_press:
                        loc_b.pressure_series = db_press
        except Exception as db_exc:
            logger.error(
                "Weather Patterns V2 database persistence/query failed (rendering from live data): %s",
                db_exc,
            )

        derived = compute_derived_signals(
            teleconnections=teleconnections,
            stratosphere=strat_bundle,
            mjo=mjo_bundle,
            enso=enso_bundle,
            locations=locations,
            forecast_vintages=forecast_vintages,
            verification_summary=verification_summary,
        )

        bundle = WeatherPatternsDataBundle(
            report_date=report_date_str,
            teleconnections=teleconnections,
            stratosphere=strat_bundle,
            mjo=mjo_bundle,
            enso=enso_bundle,
            locations=locations,
            derived=derived,
            forecast_vintages=forecast_vintages,
            provenance_list=provenance_list,
        )

        if cfg.narrative.enabled:
            bundle.narrative_text = self._generate_narrative(bundle)
        else:
            bundle.narrative_text = self._build_deterministic_fallback_narrative(bundle)

        self._bundle = bundle
        return bundle

    # ------------------------------------------------------------------
    # LLM Narrative Generation & Deterministic Fallback
    # ------------------------------------------------------------------
    def _generate_narrative(self, bundle: WeatherPatternsDataBundle) -> str:
        import os

        packet = bundle.to_llm_packet(include_afd=self.wp_config.narrative.include_afd)
        packet_json = json.dumps(packet, indent=2, sort_keys=True)

        llm_cfg = LLMConfig(
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )
        gem_key = self.gemini_api_key if self.gemini_api_key is not None else os.getenv("GEMINI_API_KEY")
        grok_key = self.grok_api_key if self.grok_api_key is not None else os.getenv("GROK_API_KEY")
        summarizer = WeatherPatternsSummarizer(
            gemini_api_key=gem_key,
            grok_api_key=grok_key,
            config=llm_cfg,
        )
        if not (summarizer.llm_gemini or summarizer.llm_grok):
            return self._build_deterministic_fallback_narrative(bundle)

        try:
            choice = "gemini" if summarizer.llm_gemini else "grok"
            text = summarizer.generate_summary(
                llm_choice=choice,
                data={
                    "weather_packet_json": packet_json,
                    "max_words": self.wp_config.narrative.max_words,
                },
            )
            if (
                text
                and text.strip()
                and text != summarizer.config.default_text
                and not text.startswith("Summary generation failed")
            ):
                return text.strip()
        except Exception as exc:
            logger.warning("WeatherPatternsSummarizer failed, using deterministic summary: %s", exc)

        return self._build_deterministic_fallback_narrative(bundle)

    @staticmethod
    def _build_deterministic_fallback_narrative(
        bundle: WeatherPatternsDataBundle,
    ) -> str:
        """Build a strictly factual 4-paragraph summary directly from the normalized bundle."""
        sig = bundle.derived

        ao_str = f"AO at {sig.ao['current']:+.2f} SD" if sig.ao.get("available") else "AO unavailable"
        nao_str = f"NAO at {sig.nao['current']:+.2f} SD" if sig.nao.get("available") else "NAO unavailable"
        pna_str = f"PNA at {sig.pna['current']:+.2f} SD" if sig.pna.get("available") else "PNA unavailable"

        mjo_str = "MJO unavailable"
        if sig.mjo.get("available"):
            state_w = "active" if sig.mjo.get("active") else "inactive/weak"
            ph = sig.mjo.get("phase")
            reg = MJO_PHASE_REGIONS.get(ph, "")
            mjo_str = f"MJO in Phase {ph} ({reg}, amplitude {sig.mjo['amplitude']:.2f}, {state_w})"

        enso_str = "ENSO unavailable"
        if sig.enso.get("available"):
            enso_str = f"ENSO in {sig.enso['state']} (Niño 3.4 {sig.enso['nino34']:+.2f}°C)"

        strat_str = "Stratospheric 10-hPa data unavailable"
        if sig.polar_vortex.get("available"):
            strat_str = (
                f"10-hPa 60°N zonal wind at {sig.polar_vortex['current_wind']:.1f} m/s "
                f"(forecast min {sig.polar_vortex.get('forecast_min') or 0.0:.1f} m/s)"
            )

        p1 = (
            f"PATTERN: Large-scale indices show {ao_str}, {nao_str}, and {pna_str}. "
            f"Tropical and seasonal background forcing features {mjo_str} and {enso_str}, "
            f"while the stratospheric polar vortex shows {strat_str}."
        )

        changes: List[str] = []
        for code, info in (("AO", sig.ao), ("NAO", sig.nao), ("PNA", sig.pna)):
            if info.get("available") and info.get("change_7d") is not None:
                fc_s = (
                    f", 7d GEFS Δ {info['forecast_change_7d']:+.2f} SD"
                    if info.get("forecast_change_7d") is not None
                    else ""
                )
                changes.append(f"{code} 7-day change of {info['change_7d']:+.2f} SD{fc_s}")
        if sig.polar_vortex.get("available") and sig.polar_vortex.get("change_7d") is not None:
            changes.append(f"10-hPa 60°N wind 7-day change of {sig.polar_vortex['change_7d']:+.1f} m/s")

        # Include V2 model trend / forecast evolution highlights if multiple runs exist
        wc = sig.what_changed or {}
        for mt_bullet in (wc.get("MODEL_TREND") or [])[:2]:
            changes.append(mt_bullet.rstrip("."))
        for st_bullet in (wc.get("STRATOSPHERE") or []):
            if "consecutive" in st_bullet or "disappeared" in st_bullet:
                changes.append(st_bullet.rstrip("."))

        p2 = (
            "WHAT CHANGED: "
            + ("; ".join(changes) if changes else "Recent 7-day index deltas are minimal.")
            + "."
        )

        notes = sig.notable_changes if sig.notable_changes else ["Large-scale indices remain near neutral regimes."]
        p3 = "WHAT IT MAY MEAN: " + " | ".join(notes[:3])

        loc_parts: List[str] = []
        for loc in bundle.locations:
            t_s = f"{loc.current_temp_f:.0f}°F" if loc.current_temp_f is not None else "N/A"
            tend = _pressure_tendency_label(loc.pressure_change_24h_hpa)
            p_s = f"{loc.current_pressure_hpa:.1f} hPa ({tend})" if loc.current_pressure_hpa else "pressure N/A"
            anom_s = f"7d temp anomaly {loc.temp_anomaly_7d_f:+.1f}°F" if loc.temp_anomaly_7d_f is not None else ""
            snow_s = ""
            if loc.snow and loc.snow.has_useful_snow_data:
                snow_s = f", snow depth {loc.snow.current_depth_in or 0.0:.1f}\" (7d fcst snow {loc.snow.forecast_snow_7d_in or 0.0:.1f}\")"
            loc_parts.append(f"{loc.name}: {t_s}, {p_s}{', ' + anom_s if anom_s else ''}{snow_s}")
        p4 = "LOCAL WATCH: " + (" | ".join(loc_parts) if loc_parts else "No local stations configured.")

        return "\n\n".join([p1, p2, p3, p4])

    # ------------------------------------------------------------------
    # Page 1 Builders: Narrative, Scorecard Table, & Large-Scale Charts
    # ------------------------------------------------------------------
    def _build_left_column_flowables(
        self, bundle: WeatherPatternsDataBundle
    ) -> List[Any]:
        st = self._wp_styles
        narrative_raw = bundle.narrative_text or self._build_deterministic_fallback_narrative(bundle)

        left_flowables: List[Any] = []
        left_flowables.extend(self._section_header_flowables("Morning Pattern Briefing"))

        for para in [p.strip() for p in narrative_raw.split("\n\n") if p.strip()]:
            safe_p = escape(para)
            for label in ("PATTERN:", "WHAT CHANGED:", "WHAT IT MAY MEAN:", "LOCAL WATCH:"):
                if safe_p.startswith(label):
                    safe_p = f"<b>{label}</b>{safe_p[len(label):]}"
                    break
            left_flowables.append(Paragraph(safe_p, st["narrative_p"]))

        left_flowables.append(Spacer(1, 5))
        left_flowables.extend(
            self._section_header_flowables("Teleconnection & Index Scorecard")
        )
        left_flowables.append(self._build_scorecard_table(bundle))

        left_flowables.append(Spacer(1, 5))
        left_flowables.extend(
            self._section_header_flowables("Forecast Evolution (Multi-Run Trend)")
        )
        left_flowables.append(self._build_forecast_evolution_table(bundle))
        return left_flowables

    def _build_right_column_charts(
        self, bundle: WeatherPatternsDataBundle
    ) -> List[Any]:
        charts_cfg = self.wp_config.charts
        right_flowables: List[Any] = []

        if charts_cfg.polar_vortex:
            right_flowables.append(
                build_polar_vortex_chart(
                    bundle.stratosphere,
                    width=252.0,
                    height=130.0,
                    history_days=min(self.wp_config.history_days, 45),
                )
            )
            right_flowables.append(Spacer(1, 4))

        if charts_cfg.mjo:
            right_flowables.append(
                build_mjo_phase_diagram(
                    bundle.mjo,
                    width=252.0,
                    height=130.0,
                )
            )
            right_flowables.append(Spacer(1, 4))

        if charts_cfg.enso:
            right_flowables.append(
                build_enso_sparkline(
                    bundle.enso,
                    width=252.0,
                    height=118.0,
                )
            )

        return right_flowables

    def _build_scorecard_table(self, bundle: WeatherPatternsDataBundle) -> Table:
        st = self._wp_styles
        sig = bundle.derived

        rows: List[List[Any]] = [
            [
                Paragraph("Index", st["table_hdr"]),
                Paragraph("Latest Obs", st["table_hdr"]),
                Paragraph("7d Δ", st["table_hdr"]),
                Paragraph("Status / Forecast", st["table_hdr"]),
            ]
        ]

        def _fmt_delta(val: Optional[float], unit: str = "") -> str:
            return f"{val:+.2f}{unit}" if val is not None else "—"

        for code, info in (("AO", sig.ao), ("NAO", sig.nao), ("PNA", sig.pna)):
            if info.get("available"):
                v = float(info["current"])
                dt_short = str(info.get("latest_date") or "")[5:]
                fc_d = info.get("forecast_change_7d")
                regime = (
                    "Strongly Neg"
                    if v <= -1.0
                    else "Strongly Pos"
                    if v >= 1.0
                    else "Negative"
                    if v <= -0.4
                    else "Positive"
                    if v >= 0.4
                    else "Neutral"
                )
                fc_txt = f" (Fcst Δ {fc_d:+.2f})" if fc_d is not None else ""
                rows.append(
                    [
                        Paragraph(f"<b>{code}</b>", st["table_cell"]),
                        Paragraph(f"{v:+.2f} SD ({dt_short})", st["table_cell"]),
                        Paragraph(_fmt_delta(info.get("change_7d")), st["table_cell"]),
                        Paragraph(f"{regime}{fc_txt}", st["table_cell"]),
                    ]
                )
            else:
                rows.append(
                    [
                        Paragraph(f"<b>{code}</b>", st["table_cell"]),
                        Paragraph("Unavailable", st["table_cell"]),
                        Paragraph("—", st["table_cell"]),
                        Paragraph("Unavailable", st["table_cell"]),
                    ]
                )

        if sig.mjo.get("available"):
            ph = sig.mjo["phase"]
            amp = sig.mjo["amplitude"]
            act_txt = "Active" if sig.mjo.get("active") else "Weak"
            reg = MJO_PHASE_REGIONS.get(ph, "")
            rows.append(
                [
                    Paragraph("<b>MJO</b>", st["table_cell"]),
                    Paragraph(f"Ph {ph}, Amp {amp:.2f}", st["table_cell"]),
                    Paragraph(f"{sig.mjo.get('amplitude_change_7d', 0.0):+.2f}", st["table_cell"]),
                    Paragraph(f"{act_txt} ({reg})", st["table_cell"]),
                ]
            )

        if bundle.enso and bundle.enso.latest_nino34 is not None:
            el = bundle.enso
            oni_txt = f"ONI {el.latest_oni:+.2f}" if el.latest_oni is not None else ""
            rows.append(
                [
                    Paragraph("<b>ENSO</b>", st["table_cell"]),
                    Paragraph(f"{el.latest_nino34:+.2f}°C ({el.latest_period[5:] if el.latest_period and len(el.latest_period) >= 7 else el.latest_period})", st["table_cell"]),
                    Paragraph("Bkgd", st["table_cell"]),
                    Paragraph(
                        f"{el.enso_state_label}" + (f" ({oni_txt})" if oni_txt else ""),
                        st["table_cell"],
                    ),
                ]
            )

        if sig.polar_vortex.get("available"):
            pv = sig.polar_vortex
            u_str = f"{pv['current_wind']:.1f} m/s"
            d7_u = f"{pv['change_7d']:+.1f}" if pv.get("change_7d") is not None else "—"
            min_f = f"Min {pv['forecast_min']:.1f}" if pv.get("forecast_min") is not None else ""
            ssw_status = (
                "MAJOR SSW (WMO Met)"
                if pv.get("major_ssw_criteria_met")
                else f"Reversal Fcst ({min_f} m/s)"
                if pv.get("forecast_reversal")
                else f"Westerly ({min_f} m/s)" if min_f else "Westerly Vortex"
            )
            rows.append(
                [
                    Paragraph("<b>10hPa 60°N U</b>", st["table_cell"]),
                    Paragraph(u_str, st["table_cell"]),
                    Paragraph(d7_u, st["table_cell"]),
                    Paragraph(ssw_status, st["table_cell"]),
                ]
            )
            if pv.get("current_polar_cap_temp_k") is not None:
                tk = float(pv["current_polar_cap_temp_k"])
                tc = tk - 273.15
                d7_t = (
                    f"{pv['polar_cap_temp_change_7d_k']:+.1f} K"
                    if pv.get("polar_cap_temp_change_7d_k") is not None
                    else "—"
                )
                rows.append(
                    [
                        Paragraph("<b>10hPa Cap T</b>", st["table_cell"]),
                        Paragraph(f"{tk:.1f} K ({tc:.0f}°C)", st["table_cell"]),
                        Paragraph(d7_t, st["table_cell"]),
                        Paragraph("60–90°N Polar Cap Mean", st["table_cell"]),
                    ]
                )

        tbl = Table(
            rows,
            colWidths=[66.0, 78.0, 40.0, 126.0],
        )
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
                    ("LINEBELOW", (0, 0), (-1, 0), 1.0, colors.black),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#777777")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F8F8")]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return tbl

    def _build_forecast_evolution_table(self, bundle: WeatherPatternsDataBundle) -> Table:
        """Build compact V2 FORECAST EVOLUTION table showing multi-run convergence & consistency."""
        st = self._wp_styles
        evol_map = bundle.derived.forecast_evolution or {}

        rows: List[List[Any]] = [
            [
                Paragraph("Metric", st["table_hdr"]),
                Paragraph("Model Trend / Signal Evolution", st["table_hdr"]),
                Paragraph("Consistency", st["table_hdr"]),
            ]
        ]

        for code in ("NAO", "AO", "PNA"):
            ev = evol_map.get(code.lower()) or evol_map.get(code) or {}
            if ev.get("available"):
                lbl = str(ev.get("display_label") or "→ little change")
                tgt = str(ev.get("target_date") or "")
                tgt_short = f" ({tgt[5:]})" if len(tgt) >= 10 else ""
                c_val = ev.get("current_run")
                val_txt = f" [{c_val:+.2f} SD]" if c_val is not None else ""
                n_runs = int(ev.get("display_runs") or ev.get("run_count") or 1)
                runs_lbl = f"{n_runs} run{'s' if n_runs != 1 else ''}"
                rows.append(
                    [
                        Paragraph(f"<b>{code}</b>", st["table_cell"]),
                        Paragraph(f"{escape(lbl)}{escape(tgt_short)}{escape(val_txt)}", st["table_cell"]),
                        Paragraph(escape(runs_lbl), st["table_cell"]),
                    ]
                )
            else:
                rows.append(
                    [
                        Paragraph(f"<b>{code}</b>", st["table_cell"]),
                        Paragraph("→ accumulating forecast runs", st["table_cell"]),
                        Paragraph("—", st["table_cell"]),
                    ]
                )

        pv_ev = evol_map.get("stratosphere") or {}
        if pv_ev.get("available"):
            lbl = str(pv_ev.get("display_label") or "→ steady westerly vortex")
            c_min = pv_ev.get("current_run_minimum")
            min_txt = f" [min {c_min:+.1f} m/s]" if c_min is not None else ""
            n_runs = int(pv_ev.get("display_runs") or pv_ev.get("run_count") or 1)
            runs_lbl = f"{n_runs} run{'s' if n_runs != 1 else ''}"
            rows.append(
                [
                    Paragraph("<b>PV WIND</b>", st["table_cell"]),
                    Paragraph(f"{escape(lbl)}{escape(min_txt)}", st["table_cell"]),
                    Paragraph(escape(runs_lbl), st["table_cell"]),
                ]
            )
        else:
            rows.append(
                [
                    Paragraph("<b>PV WIND</b>", st["table_cell"]),
                    Paragraph("→ accumulating forecast runs", st["table_cell"]),
                    Paragraph("—", st["table_cell"]),
                ]
            )

        tbl = Table(rows, colWidths=[54.0, 200.0, 56.0])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
                    ("LINEBELOW", (0, 0), (-1, 0), 1.0, colors.black),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#777777")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F8F8")]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return tbl

    def _build_header(self) -> List[Any]:
        """Build standard screamsheet title, date, and location header for Page 1."""
        title_st = ParagraphStyle(
            "WP_MainTitle",
            parent=self.title_style,
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=29,
            spaceAfter=3,
            alignment=1,
        )
        date_st = ParagraphStyle(
            "WP_DateSub",
            parent=self.subtitle_style,
            fontName="Helvetica",
            fontSize=15.5,
            leading=18,
            spaceAfter=2,
            alignment=1,
        )
        loc_st = ParagraphStyle(
            "WP_LocationSub",
            parent=self.subtitle_style,
            fontName="Helvetica",
            fontSize=13.5,
            leading=16,
            spaceAfter=6,
            alignment=1,
            textColor=colors.HexColor("#222222"),
        )
        flow: List[Any] = [
            Paragraph(escape(self.get_title()), title_st),
            Paragraph(escape(self.get_date_string()), date_st),
        ]
        loc_sub = self.get_subtitle()
        if loc_sub:
            flow.append(Paragraph(escape(loc_sub), loc_st))
        return flow

    def _build_page1(self, bundle: WeatherPatternsDataBundle) -> List[Any]:
        story: List[Any] = []
        story.extend(self._build_header())

        left_col = self._build_left_column_flowables(bundle)
        right_col = self._build_right_column_charts(bundle)

        top_two_col = Table(
            [[left_col, right_col]],
            colWidths=[316.0, 252.0],
        )
        top_two_col.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, -1), 0),
                    ("RIGHTPADDING", (0, 0), (0, -1), 6),
                    ("LEFTPADDING", (1, 0), (1, -1), 0),
                    ("RIGHTPADDING", (1, 0), (1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(top_two_col)
        story.append(Spacer(1, 4))

        charts_cfg = self.wp_config.charts
        if charts_cfg.teleconnections:
            c4 = build_teleconnections_chart(
                bundle.teleconnections,
                width=568.0,
                height=144.0,
                history_days=min(self.wp_config.history_days, 55),
                forecast_days=self.wp_config.forecast_days,
            )
            c4.hAlign = "CENTER"
            story.append(c4)

        if getattr(charts_cfg, "forecast_evolution", True):
            story.append(Spacer(1, 3))
            c5 = build_forecast_evolution_chart(
                forecast_vintages=bundle.forecast_vintages,
                teleconnections=bundle.teleconnections,
                stratosphere=bundle.stratosphere,
                width=568.0,
                height=108.0,
            )
            c5.hAlign = "CENTER"
            story.append(c5)

        return story

    # ------------------------------------------------------------------
    # Page 2 Builder: Single Location Observations, Normals, AFD & Forecasts
    # ------------------------------------------------------------------
    def _build_location_section(self, loc: LocalLocationBundle) -> List[Any]:
        st = self._wp_styles
        charts_cfg = self.wp_config.charts
        blocks: List[Any] = []

        stn_str = f" — Station {loc.station_id}" if loc.station_id else ""
        wfo_str = f" (NWS {loc.grid_id})" if loc.grid_id else ""
        blocks.extend(
            self._section_header_flowables(
                f"Local Weather & Climatological Context: {loc.name}{stn_str}{wfo_str}",
                back_page=True,
            )
        )

        t_cur = f"{loc.current_temp_f:.1f}°F" if loc.current_temp_f is not None else "N/A"
        td_cur = f" (Dewpoint {loc.current_dewpoint_f:.1f}°F)" if loc.current_dewpoint_f is not None else ""
        tend = _pressure_tendency_label(loc.pressure_change_24h_hpa)
        p_cur = (
            f"{loc.current_pressure_hpa:.1f} hPa ({tend}, "
            f"24h Δ {loc.pressure_change_24h_hpa or 0.0:+.1f} hPa)"
            if loc.current_pressure_hpa is not None
            else "N/A"
        )
        w_cur = (
            f"{loc.current_wind_mph:.0f} mph"
            + (f" ({loc.current_wind_dir_deg}°)" if loc.current_wind_dir_deg is not None else "")
            if loc.current_wind_mph is not None
            else "Calm / N/A"
        )
        t_anom = (
            f"7-Day: {loc.temp_anomaly_7d_f:+.1f}°F  |  14-Day: {loc.temp_anomaly_14d_f or 0.0:+.1f}°F (vs. 1991–2020 NCEI Normal)"
            if loc.temp_anomaly_7d_f is not None
            else "Unavailable"
        )
        p_anom = (
            f"{loc.precip_30d_in or 0.0:.2f}\" ({loc.precip_30d_pct_normal:.0f}% of 1991–2020 Normal {loc.precip_30d_normal_in or 0.0:.2f}\")"
            if loc.precip_30d_pct_normal is not None
            else "Unavailable"
        )

        list_items = [
            f"&bull; <b>Latest Observation:</b> {escape(t_cur)}{escape(td_cur)}, {escape(loc.current_conditions or 'Reported')}",
            f"&bull; <b>Wind:</b> {escape(w_cur)}",
            f"&bull; <b>Sea-Level Pressure:</b> {escape(p_cur)}",
            f"&bull; <b>Temperature Anomalies:</b> {escape(t_anom)}",
            f"&bull; <b>30-Day Precipitation:</b> {escape(p_anom)}",
        ]
        for item_html in list_items:
            blocks.append(Paragraph(item_html, st["back_list_item"]))
        blocks.append(Spacer(1, 6))

        if loc.afd_synopsis:
            afd_paras = _format_afd_paragraphs(loc.afd_synopsis, max_chars=900)
            if afd_paras:
                blocks.extend(
                    self._section_header_flowables(
                        f"NWS Area Forecast Discussion Synopsis ({loc.grid_id or 'WFO'})",
                        back_page=True,
                    )
                )
                for p_html in afd_paras:
                    blocks.append(Paragraph(p_html, st["back_body"]))
                blocks.append(Spacer(1, 6))

        loc_charts: List[Any] = []
        if charts_cfg.local_pressure:
            loc_charts.append(build_local_pressure_chart(loc, width=278.0, height=160.0))
        if charts_cfg.local_temperature:
            loc_charts.append(build_local_temperature_chart(loc, width=278.0, height=160.0))
        if loc_charts:
            blocks.extend(
                self._section_header_flowables(
                    "Local Barometric Pressure & Temperature Anomaly Diagnostics",
                    back_page=True,
                )
            )
            if len(loc_charts) == 1:
                blocks.append(loc_charts[0])
            else:
                ct = Table([loc_charts], colWidths=[282.0, 282.0])
                ct.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                blocks.append(ct)
            blocks.append(Spacer(1, 8))

        if loc.daily_forecasts:
            blocks.extend(
                self._section_header_flowables(
                    f"7-Day NWS Local Forecast — {loc.name}",
                    back_page=True,
                )
            )
            fcst_days = loc.daily_forecasts[:7]
            hdr_row = [Paragraph("<b>Metric</b>", st["back_table_hdr"])] + [
                Paragraph(
                    f"<b>{escape(f.day_name[:3])} {escape(f.date[5:])}</b>",
                    st["back_table_hdr"],
                )
                for f in fcst_days
            ]
            hi_lo_row = [Paragraph("<b>High / Low (°F)</b>", st["back_table_cell"])] + [
                Paragraph(
                    f"{f.high_f:.0f}° / {f.low_f:.0f}°"
                    if (f.high_f is not None and f.low_f is not None)
                    else f"{f.high_f or f.low_f or 0.0:.0f}°",
                    st["back_table_cell"],
                )
                for f in fcst_days
            ]
            pop_qpf_row = [Paragraph("<b>PoP / QPF</b>", st["back_table_cell"])] + [
                Paragraph(
                    f"{f.pop_pct or 0}% / {f.qpf_in or 0.0:.2f}\"",
                    st["back_table_cell"],
                )
                for f in fcst_days
            ]
            cond_row = [Paragraph("<b>Conditions</b>", st["back_table_cell"])] + [
                Paragraph(escape((f.short_forecast or "—")[:26]), st["back_table_cell"])
                for f in fcst_days
            ]
            f_rows = [hdr_row, hi_lo_row, pop_qpf_row, cond_row]
            if any((f.snow_in or 0.0) > 0 for f in fcst_days):
                snow_row = [Paragraph("<b>Grid Snow</b>", st["back_table_cell"])] + [
                    Paragraph(f"{f.snow_in or 0.0:.1f}\"", st["back_table_cell"])
                    for f in fcst_days
                ]
                f_rows.insert(3, snow_row)

            col_w = [84.0] + [(480.0 / max(1, len(fcst_days)))] * len(fcst_days)
            ft = Table(f_rows, colWidths=col_w)
            ft.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
                        ("LINEBELOW", (0, 0), (-1, 0), 1.0, colors.black),
                        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#777777")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F8F8")]),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5.0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5.0),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4.0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4.0),
                    ]
                )
            )
            blocks.append(ft)
            blocks.append(Spacer(1, 8))

        if charts_cfg.snow and loc.snow and loc.snow.has_useful_snow_data:
            sn = loc.snow
            blocks.extend(
                self._section_header_flowables(
                    f"Snow Depth & Snowfall Watch — {sn.station_name or sn.station_id or loc.name}",
                    back_page=True,
                )
            )
            elev_txt = f" (Elev {sn.elevation_ft:.0f} ft)" if sn.elevation_ft is not None else ""
            sn_html = (
                f"<b>Reporting Station:</b> {escape(sn.station_name or sn.station_id or 'Local')}{escape(elev_txt)}  &bull;  "
                f"<b>Current Depth:</b> {sn.current_depth_in or 0.0:.1f}\" (7d Δ {sn.change_7d_in or 0.0:+.1f}\")  &bull;  "
                f"<b>Snowfall:</b> 24h {sn.snowfall_24h_in or 0.0:.1f}\", 7d {sn.snowfall_7d_in or 0.0:.1f}\"  &bull;  "
                f"<b>7d NWS Fcst Snow:</b> {sn.forecast_snow_7d_in or 0.0:.1f}\""
            )
            blocks.append(Paragraph(sn_html, st["back_body"]))
            blocks.append(Spacer(1, 4))
            blocks.append(build_snow_watch_chart(sn, width=564.0, height=130.0))

        return blocks

    # ------------------------------------------------------------------
    # BaseScreamsheet interface: build_sections, generate, render_markdown
    # ------------------------------------------------------------------
    def _build_multi_page_pdf(
        self,
        pages: List[List[Any]],
    ) -> str:
        """Build an N-page PDF with narrower horizontal margins (24pt = 1/3 inch)."""
        non_empty_pages = [p for p in pages if p]
        if not non_empty_pages:
            non_empty_pages = [[]]

        margin_x = 22.0
        margin_top = 24.0
        margin_bottom = 28.0
        page_width, page_height = letter
        frame_w = page_width - 2 * margin_x
        frame_h = page_height - margin_top - margin_bottom

        Path(self.output_filename).parent.mkdir(parents=True, exist_ok=True)
        doc = BaseDocTemplate(
            self.output_filename,
            pagesize=letter,
            leftMargin=margin_x,
            rightMargin=margin_x,
            topMargin=margin_top,
            bottomMargin=margin_bottom,
        )

        templates = []
        story: List[Any] = []
        for idx, page_flowables in enumerate(non_empty_pages):
            tpl_id = f"Page_{idx + 1}"
            frame = Frame(
                margin_x,
                margin_bottom,
                frame_w,
                frame_h,
                leftPadding=0,
                rightPadding=0,
                topPadding=0,
                bottomPadding=0,
                id=f"frame_{idx + 1}",
            )
            templates.append(
                PageTemplate(id=tpl_id, frames=[frame], onPage=self._draw_branding_footer)
            )
            if idx > 0:
                story.append(NextPageTemplate(tpl_id))
                story.append(PageBreak())
            story.append(
                KeepInFrame(
                    maxWidth=0,
                    maxHeight=frame_h,
                    content=page_flowables,
                    mode="shrink",
                )
            )

        doc.addPageTemplates(templates)
        doc.build(story)
        logger.info(
            "Multi-page PDF (%d pages) written to %s",
            len(non_empty_pages),
            self.output_filename,
        )
        return self.output_filename

    def build_sections(self) -> List[Any]:
        return []

    def generate(self) -> str:
        """Generate two-page Climate Screamsheet PDF and return path string."""
        bundle = self.collect_data_bundle()
        pages: List[List[Any]] = [self._build_page1(bundle)]

        if bundle.locations:
            pages.append(self._build_location_section(bundle.locations[0]))

        return self._build_multi_page_pdf(pages)

    def generate_pdf(self, output_path: Optional[Path] = None) -> Path:
        """Convenience wrapper returning a Path object."""
        if output_path is not None:
            self.output_filename = str(output_path)
        return Path(self.generate())

    def render_markdown(self) -> str:
        """Render a rich plain-text / Markdown edition of the Weather Patterns screamsheet."""
        bundle = self.collect_data_bundle()
        lines: List[str] = [
            f"# {self.get_title()}",
            f"*{self.get_subtitle()}*",
            "",
            "## Morning Meteorological Pattern Briefing",
            "",
            bundle.narrative_text or self._build_deterministic_fallback_narrative(bundle),
            "",
            "## Large-Scale Index Scorecard",
            "",
            "| Index | Latest Observed | 7d Change | 7d Forecast Change | Status / Notes |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        sig = bundle.derived
        for code, info in (("AO", sig.ao), ("NAO", sig.nao), ("PNA", sig.pna)):
            if info.get("available"):
                d7 = info.get("change_7d")
                f7 = info.get("forecast_change_7d")
                lines.append(
                    f"| **{code}** | {info['current']:+.2f} SD ({info.get('latest_date')}) | "
                    f"{f'{d7:+.2f}' if d7 is not None else '—'} | "
                    f"{f'{f7:+.2f}' if f7 is not None else '—'} | "
                    f"GEFS Day-7 Mean {info.get('gefs_day7')} |"
                )
        if sig.mjo.get("available"):
            ph = sig.mjo["phase"]
            lines.append(
                f"| **MJO (ROMI)** | Phase {ph}, Amp {sig.mjo['amplitude']:.2f} ({sig.mjo.get('latest_date')}) | "
                f"{sig.mjo.get('motion_7d')} | — | "
                f"{'Active' if sig.mjo.get('active') else 'Weak (<1.0)'} ({MJO_PHASE_REGIONS.get(ph, '')}) |"
            )
        if bundle.enso and bundle.enso.latest_nino34 is not None:
            el = bundle.enso
            lines.append(
                f"| **ENSO (Niño 3.4)** | {el.latest_nino34:+.2f}°C ({el.latest_period}) | Slow Bkgd | — | "
                f"{el.enso_state_label} (ONI {el.latest_oni if el.latest_oni is not None else 'N/A'}) |"
            )
        if sig.polar_vortex.get("available"):
            pv = sig.polar_vortex
            d7_u = pv.get("change_7d")
            lines.append(
                f"| **10 hPa 60°N Wind** | {pv['current_wind']:.1f} m/s ({pv.get('latest_date')}) | "
                f"{f'{d7_u:+.1f} m/s' if d7_u is not None else '—'} | "
                f"Min {pv.get('forecast_min')} m/s | "
                f"Major SSW: {pv.get('major_ssw_criteria_met')} |"
            )

        lines.append("")
        lines.append("## Forecast Evolution (Multi-Run Model Trend)")
        lines.append("")
        lines.append("| Metric | Model Trend / Signal Evolution | Runs |")
        lines.append("| :--- | :--- | :--- |")
        evol_map = sig.forecast_evolution or {}
        for code in ("NAO", "AO", "PNA"):
            ev = evol_map.get(code.lower()) or evol_map.get(code) or {}
            if ev.get("available"):
                n_r = int(ev.get("display_runs") or ev.get("run_count") or 1)
                lines.append(
                    f"| **{code}** | {ev.get('display_label')} (target {ev.get('target_date')}: {ev.get('current_run'):+.2f} SD) | {n_r} run(s) |"
                )
        pv_ev = evol_map.get("stratosphere") or {}
        if pv_ev.get("available"):
            n_r = int(pv_ev.get("display_runs") or pv_ev.get("run_count") or 1)
            lines.append(
                f"| **PV WIND** | {pv_ev.get('display_label')} (min {pv_ev.get('current_run_minimum'):+.1f} m/s) | {n_r} run(s) |"
            )

        lines.append("")
        lines.append("## Local Locations")
        for loc in bundle.locations:
            lines.append(f"### {loc.name} ({loc.station_id or 'Auto'})")
            lines.append(
                f"- **Current:** {loc.current_temp_f}°F, Pressure {loc.current_pressure_hpa} hPa "
                f"(24h Δ {loc.pressure_change_24h_hpa} hPa)"
            )
            lines.append(
                f"- **Anomalies (vs 1991–2020 NCEI Normal):** 7d Temp {loc.temp_anomaly_7d_f}°F, "
                f"30d Precip {loc.precip_30d_pct_normal}% of normal"
            )
            if loc.snow and loc.snow.has_useful_snow_data:
                lines.append(
                    f"- **Snow Watch ({loc.snow.station_name or loc.snow.station_id}):** "
                    f"Depth {loc.snow.current_depth_in}\", 7d Snowfall {loc.snow.snowfall_7d_in}\", "
                    f"7d NWS Forecast Snow {loc.snow.forecast_snow_7d_in}\""
                )
            lines.append("")

        return "\n".join(lines)
