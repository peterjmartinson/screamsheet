"""NOAA Space Weather Prediction Center (SWPC) Provider.

Authoritative Sources:
  - GOES Primary 1-Day X-Ray Flux (0.1–0.8 nm & 0.05–0.4 nm, 1-min resolution):
    https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json
  - NOAA Planetary K-Index (3-hour Kp geomagnetic activity):
    https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json
  - Solar Cycle 25 Observed Sunspot Numbers (Monthly & 13-Month Smoothed):
    https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json
  - Solar Cycle 25 Predicted Progression & Range:
    https://services.swpc.noaa.gov/json/solar-cycle/predicted-solar-cycle.json
    https://services.swpc.noaa.gov/json/solar-cycle/solar-cycle-25-predicted.json
  - GOES SUVI Solar X-Ray / EUV Disk Image (94 Å Fe XVIII flare channel / 195 Å):
    https://services.swpc.noaa.gov/images/animations/suvi/primary/094/latest.png
"""
from __future__ import annotations

import base64
import io
import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from PIL import Image

from ..base import DataProvider
from ..db import weather_cache_fetch
from ..weather_patterns.models import (
    KpIndexPoint,
    SolarCycleMonthPoint,
    SourceProvenance,
    SpaceWeatherBundle,
    XRayFluxPoint,
)

logger = logging.getLogger(__name__)

SWPC_XRAYS_1D_URL = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"
SWPC_KP_INDEX_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
SWPC_OBSERVED_CYCLE_URL = "https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json"
SWPC_PREDICTED_CYCLE_URL = "https://services.swpc.noaa.gov/json/solar-cycle/predicted-solar-cycle.json"
SWPC_SC25_BASELINE_URL = "https://services.swpc.noaa.gov/json/solar-cycle/solar-cycle-25-predicted.json"
SWPC_SUVI_094_URL = "https://services.swpc.noaa.gov/images/animations/suvi/primary/094/latest.png"
SWPC_SUVI_195_URL = "https://services.swpc.noaa.gov/images/animations/suvi/primary/195/latest.png"


def classify_xray_flare(flux_wm2: Optional[float]) -> str:
    """Classify 0.1–0.8 nm GOES X-ray flux (W/m²) into standard NOAA flare class (A, B, C, M, X)."""
    if flux_wm2 is None or flux_wm2 <= 0 or math.isnan(flux_wm2):
        return "Unavailable"
    if flux_wm2 >= 1e-4:
        return f"X{flux_wm2 / 1e-4:.1f}"
    if flux_wm2 >= 1e-5:
        return f"M{flux_wm2 / 1e-5:.1f}"
    if flux_wm2 >= 1e-6:
        return f"C{flux_wm2 / 1e-6:.1f}"
    if flux_wm2 >= 1e-7:
        return f"B{flux_wm2 / 1e-7:.1f}"
    return f"A{max(0.1, flux_wm2 / 1e-8):.1f}"


def classify_geomagnetic_kp(kp: Optional[float]) -> str:
    """Classify Planetary K-index into NOAA G-scale / geomagnetic status."""
    if kp is None or math.isnan(kp):
        return "Unavailable"
    if kp >= 9.0:
        return "G5 Extreme Storm"
    if kp >= 8.0:
        return "G4 Severe Storm"
    if kp >= 7.0:
        return "G3 Strong Storm"
    if kp >= 6.0:
        return "G2 Moderate Storm"
    if kp >= 5.0:
        return "G1 Minor Storm"
    if kp >= 4.0:
        return "Active (Kp 4)"
    if kp >= 3.0:
        return "Unsettled (Kp 3)"
    return "Quiet (G0)"


def process_suvi_image_to_bw_b64(raw_png_bytes: bytes, output_px: int = 380) -> str:
    """Convert raw GOES SUVI RGBA PNG into a high-contrast B&W grayscale PNG (base64 string)."""
    im = Image.open(io.BytesIO(raw_png_bytes)).convert("L")
    w, h = im.size
    if w >= 600 and h >= 600:
        margin_x = int(w * 0.13)
        margin_top = int(h * 0.11)
        margin_bot = int(h * 0.15)
        im = im.crop((margin_x, margin_top, w - margin_x, h - margin_bot))
    im = im.resize((output_px, output_px), Image.Resampling.LANCZOS)
    arr = np.array(im, dtype=np.float32)
    p_hi = max(80.0, float(np.percentile(arr, 99.6)))
    norm = np.clip(arr / p_hi, 0.0, 1.0) ** 0.62
    out_im = Image.fromarray((norm * 255.0).astype(np.uint8))
    buf = io.BytesIO()
    out_im.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


class SpaceWeatherProvider(DataProvider):
    """Fetches and caches space weather observations and Solar Cycle 25 data from NOAA SWPC."""

    def __init__(
        self,
        use_cache: bool = True,
        refresh_cache: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(**config)
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache

    @staticmethod
    def parse_xray_json(raw_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse SWPC xrays-1-day.json into downsampled 5-min series + exact 24h peak & latest."""
        by_time: Dict[str, Dict[str, float]] = {}
        for row in raw_list:
            if not isinstance(row, dict):
                continue
            ts = str(row.get("time_tag") or "").strip()
            energy = str(row.get("energy") or "").strip()
            flux = row.get("flux")
            if not ts or flux is None:
                continue
            try:
                f_val = float(flux)
            except (ValueError, TypeError):
                continue
            if f_val <= 0:
                continue
            slot = by_time.setdefault(ts, {})
            if energy == "0.1-0.8nm":
                slot["long"] = f_val
            elif energy == "0.05-0.4nm":
                slot["short"] = f_val

        sorted_times = sorted(by_time.keys())
        if not sorted_times:
            return {
                "series": [],
                "latest_flux": None,
                "max_flux": None,
            }

        all_long = [
            (ts, by_time[ts]["long"])
            for ts in sorted_times
            if "long" in by_time[ts] and by_time[ts]["long"] > 0
        ]
        latest_flux = all_long[-1][1] if all_long else None
        max_ts = max(all_long, key=lambda x: x[1])[0] if all_long else None
        max_flux = max(all_long, key=lambda x: x[1])[1] if all_long else None

        sampled: List[Dict[str, Any]] = []
        n = len(sorted_times)
        for idx, ts in enumerate(sorted_times):
            if idx % 5 == 0 or idx == n - 1 or ts == max_ts:
                entry = by_time[ts]
                sampled.append(
                    {
                        "timestamp": ts,
                        "flux_long": entry.get("long"),
                        "flux_short": entry.get("short"),
                    }
                )
        return {
            "series": sampled,
            "latest_flux": latest_flux,
            "max_flux": max_flux,
        }

    @staticmethod
    def parse_kp_json(raw_list: List[Any], max_bars: int = 16) -> List[Dict[str, Any]]:
        """Parse SWPC noaa-planetary-k-index.json (supports both dict-row and list-row formats)."""
        pts: List[Dict[str, Any]] = []
        for row in raw_list:
            if isinstance(row, dict):
                ts = str(row.get("time_tag") or "").strip()
                kp_raw = row.get("Kp", row.get("kp"))
                a_raw = row.get("a_running")
            elif isinstance(row, list) and len(row) >= 2:
                if str(row[0]).lower() == "time_tag":
                    continue
                ts = str(row[0]).strip()
                kp_raw = row[1]
                a_raw = row[2] if len(row) >= 3 else None
            else:
                continue
            if not ts or kp_raw is None:
                continue
            try:
                kp_val = float(kp_raw)
                a_val = float(a_raw) if a_raw is not None else None
                pts.append({"timestamp": ts, "kp": kp_val, "a_running": a_val})
            except (ValueError, TypeError):
                continue
        pts.sort(key=lambda x: x["timestamp"])
        return pts[-max_bars:]

    @staticmethod
    def parse_solar_cycle(
        observed_raw: List[Dict[str, Any]],
        predicted_raw: List[Dict[str, Any]],
        baseline_raw: Optional[List[Dict[str, Any]]] = None,
        start_ym: str = "2019-12",
        end_ym: str = "2030-12",
    ) -> List[Dict[str, Any]]:
        """Merge observed monthly/smoothed SSN and SWPC forward forecast for Solar Cycle 25."""
        by_ym: Dict[str, Dict[str, Any]] = {}

        for row in predicted_raw or []:
            if not isinstance(row, dict):
                continue
            ym = str(row.get("time-tag") or row.get("time_tag") or "").strip()
            if not ym or ym < start_ym or ym > end_ym:
                continue
            slot = by_ym.setdefault(ym, {"period": ym})
            pred_v = row.get("predicted_ssn")
            if pred_v is not None and float(pred_v) >= 0:
                slot["predicted_ssn"] = float(pred_v)
            low_v = row.get("low_ssn", row.get("low25_ssn"))
            high_v = row.get("high_ssn", row.get("high25_ssn"))
            if low_v is not None and float(low_v) >= 0:
                slot["predicted_low"] = float(low_v)
            if high_v is not None and float(high_v) >= 0:
                slot["predicted_high"] = float(high_v)

        for row in observed_raw or []:
            if not isinstance(row, dict):
                continue
            ym = str(row.get("time-tag") or row.get("time_tag") or "").strip()
            if not ym or ym < start_ym or ym > end_ym:
                continue
            slot = by_ym.setdefault(ym, {"period": ym})
            ssn_v = row.get("ssn")
            if ssn_v is not None and float(ssn_v) >= 0:
                slot["observed_ssn"] = float(ssn_v)
            sm_v = row.get("smoothed_ssn")
            if sm_v is not None and float(sm_v) >= 0:
                slot["smoothed_ssn"] = float(sm_v)

        return [by_ym[k] for k in sorted(by_ym.keys())]

    def get_space_weather_bundle(
        self, target_date: Optional[datetime] = None
    ) -> SpaceWeatherBundle:
        """Fetch and assemble the complete SpaceWeatherBundle (cached with 3h fresh TTL)."""
        def _fetch_all() -> Dict[str, Any]:
            xray_data: Dict[str, Any] = {"series": [], "latest_flux": None, "max_flux": None}
            try:
                r_x = requests.get(SWPC_XRAYS_1D_URL, timeout=15)
                if r_x.ok:
                    xray_data = self.parse_xray_json(r_x.json())
            except Exception as exc:
                logger.warning("SWPC GOES X-ray fetch failed: %s", exc)

            kp_rows: List[Dict[str, Any]] = []
            try:
                r_kp = requests.get(SWPC_KP_INDEX_URL, timeout=15)
                if r_kp.ok:
                    kp_rows = self.parse_kp_json(r_kp.json(), max_bars=16)
            except Exception as exc:
                logger.warning("SWPC Kp index fetch failed: %s", exc)

            cycle_rows: List[Dict[str, Any]] = []
            try:
                r_obs = requests.get(SWPC_OBSERVED_CYCLE_URL, timeout=15)
                r_pred = requests.get(SWPC_PREDICTED_CYCLE_URL, timeout=15)
                r_base = requests.get(SWPC_SC25_BASELINE_URL, timeout=15)
                obs_j = r_obs.json() if r_obs.ok else []
                pred_j = r_pred.json() if r_pred.ok else []
                base_j = r_base.json() if r_base.ok else []
                cycle_rows = self.parse_solar_cycle(obs_j, pred_j, base_j)
            except Exception as exc:
                logger.warning("SWPC Solar Cycle 25 fetch failed: %s", exc)

            sun_b64: Optional[str] = None
            sun_wl = "GOES SUVI 094 Å (X-Ray)"
            sun_ts: Optional[str] = None
            for wl_label, img_url in (
                ("GOES SUVI 094 Å (X-Ray)", SWPC_SUVI_094_URL),
                ("GOES SUVI 195 Å (EUV)", SWPC_SUVI_195_URL),
            ):
                try:
                    r_im = requests.get(img_url, timeout=15)
                    if r_im.ok and len(r_im.content) > 1000:
                        sun_b64 = process_suvi_image_to_bw_b64(r_im.content, output_px=380)
                        sun_wl = wl_label
                        sun_ts = r_im.headers.get("Last-Modified")
                        break
                except Exception as exc:
                    logger.debug("SUVI image fetch (%s) failed: %s", img_url, exc)

            if not xray_data.get("series") and not kp_rows and not cycle_rows:
                raise RuntimeError("All NOAA SWPC space weather endpoints were unreachable")

            return {
                "xray": xray_data,
                "kp": kp_rows,
                "solar_cycle": cycle_rows,
                "sun_image_png_b64": sun_b64,
                "sun_image_wavelength": sun_wl,
                "sun_image_timestamp": sun_ts,
            }

        res = weather_cache_fetch(
            cache_key="swpc_space_weather_bundle",
            source_url=SWPC_XRAYS_1D_URL,
            fetcher=_fetch_all,
            fresh_hours=3.0,
            max_stale_hours=72.0,
            use_cache=self.use_cache,
            refresh_cache=self.refresh_cache,
        )

        xray_series: List[XRayFluxPoint] = []
        latest_xray_flux: Optional[float] = None
        max_24h_xray_flux: Optional[float] = None
        kp_series: List[KpIndexPoint] = []
        solar_cycle_series: List[SolarCycleMonthPoint] = []
        sun_b64: Optional[str] = None
        sun_wl = "GOES SUVI 094 Å (X-Ray)"
        sun_ts: Optional[str] = None

        if res.data and isinstance(res.data, dict):
            x_dict = res.data.get("xray") or {}
            for item in x_dict.get("series") or []:
                xray_series.append(
                    XRayFluxPoint(
                        timestamp=str(item["timestamp"]),
                        flux_long=float(item["flux_long"]) if item.get("flux_long") is not None else None,
                        flux_short=float(item["flux_short"]) if item.get("flux_short") is not None else None,
                    )
                )
            if x_dict.get("latest_flux") is not None:
                latest_xray_flux = float(x_dict["latest_flux"])
            if x_dict.get("max_flux") is not None:
                max_24h_xray_flux = float(x_dict["max_flux"])

            for item in res.data.get("kp") or []:
                kp_series.append(
                    KpIndexPoint(
                        timestamp=str(item["timestamp"]),
                        kp=float(item["kp"]),
                        a_running=float(item["a_running"]) if item.get("a_running") is not None else None,
                    )
                )

            cutoff_ym = target_date.strftime("%Y-%m") if target_date else None
            for item in res.data.get("solar_cycle") or []:
                ym = str(item["period"])
                obs_v = (
                    float(item["observed_ssn"])
                    if (item.get("observed_ssn") is not None and (not cutoff_ym or ym <= cutoff_ym))
                    else None
                )
                sm_v = (
                    float(item["smoothed_ssn"])
                    if (item.get("smoothed_ssn") is not None and (not cutoff_ym or ym <= cutoff_ym))
                    else None
                )
                solar_cycle_series.append(
                    SolarCycleMonthPoint(
                        period=ym,
                        observed_ssn=obs_v,
                        smoothed_ssn=sm_v,
                        predicted_ssn=float(item["predicted_ssn"]) if item.get("predicted_ssn") is not None else None,
                        predicted_low=float(item["predicted_low"]) if item.get("predicted_low") is not None else None,
                        predicted_high=float(item["predicted_high"]) if item.get("predicted_high") is not None else None,
                    )
                )

            sun_b64 = res.data.get("sun_image_png_b64")
            sun_wl = str(res.data.get("sun_image_wavelength") or sun_wl)
            sun_ts = res.data.get("sun_image_timestamp")

        latest_kp = kp_series[-1].kp if kp_series else None
        recent_24h_kp = [p.kp for p in kp_series[-8:]]
        max_24h_kp = max(recent_24h_kp) if recent_24h_kp else latest_kp

        obs_months = [p for p in solar_cycle_series if p.observed_ssn is not None]
        current_period = obs_months[-1].period if obs_months else None
        current_obs_ssn = obs_months[-1].observed_ssn if obs_months else None
        current_pred_ssn = obs_months[-1].predicted_ssn if obs_months else None
        sm_months = [p for p in solar_cycle_series if p.smoothed_ssn is not None]
        current_sm_ssn = sm_months[-1].smoothed_ssn if sm_months else None

        valid_str = (
            xray_series[-1].timestamp
            if xray_series
            else (kp_series[-1].timestamp if kp_series else current_period)
        )
        available = bool(xray_series or kp_series or solar_cycle_series)

        prov = SourceProvenance(
            source_name="NOAA SWPC",
            product="GOES SUVI X-Ray, X-Ray Flux (24h), Planetary Kp & Solar Cycle 25",
            url=SWPC_XRAYS_1D_URL,
            retrieved_at=res.fetched_at,
            valid_through=valid_str,
            from_cache=res.from_cache,
            is_stale=res.is_stale,
            age_hours=res.age_hours,
            available=available,
            error=res.error if not available else None,
        )

        return SpaceWeatherBundle(
            xray_series=xray_series,
            latest_xray_flux=latest_xray_flux,
            latest_xray_class=classify_xray_flare(latest_xray_flux),
            max_24h_xray_flux=max_24h_xray_flux,
            max_24h_xray_class=classify_xray_flare(max_24h_xray_flux),
            kp_series=kp_series,
            latest_kp=latest_kp,
            max_24h_kp=max_24h_kp,
            geomag_scale_label=classify_geomagnetic_kp(max_24h_kp),
            solar_cycle_series=solar_cycle_series,
            current_cycle_period=current_period,
            current_observed_ssn=current_obs_ssn,
            current_smoothed_ssn=current_sm_ssn,
            current_predicted_ssn=current_pred_ssn,
            sun_image_png_b64=sun_b64,
            sun_image_wavelength=sun_wl,
            sun_image_timestamp=sun_ts,
            provenance=prov,
        )
