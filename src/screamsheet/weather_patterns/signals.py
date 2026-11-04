"""Deterministic signal-change calculations and rule-based flags for Weather Patterns.

All quantitative trends and regime flags are computed programmatically here so
the LLM never has to guess or calculate index changes.

Documented Rule Thresholds
--------------------------
- ``ao_strongly_negative``: Current CDAS AO <= -1.5 SD
- ``ao_strongly_positive``: Current CDAS AO >= +1.5 SD
- ``nao_strongly_negative``: Current CDAS NAO <= -1.5 SD
- ``nao_strongly_positive``: Current CDAS NAO >= +1.5 SD
- ``pna_strongly_positive``: Current CDAS PNA >= +1.5 SD
- ``pna_strongly_negative``: Current CDAS PNA <= -1.5 SD
- ``mjo_active``: Latest ROMI amplitude >= 1.0 SD
- ``polar_vortex_rapidly_weakening``: 7-day observed 10-hPa 60°N zonal wind change <= -10.0 m/s
  OR 7-day forecast change <= -15.0 m/s
- ``polar_vortex_reversal_observed``: Latest observed 10-hPa 60°N zonal wind < 0.0 m/s (easterly)
  during extended winter (Nov–Mar)
- ``polar_vortex_reversal_forecast``: Forecast minimum 10-hPa 60°N zonal wind < 0.0 m/s
  during extended winter (Nov–Mar) while currently westerly (>= 0.0 m/s)
- ``major_ssw_criteria_met``: Follows WMO / Charlton & Polvani (2007) diagnostic criteria:
  (1) Winter season (Nov–Mar; excludes Apr–May final warming),
  (2) 10-hPa 60°N zonal-mean zonal wind reverses from westerly to easterly (< 0 m/s), AND
  (3) 10-hPa 60–90°N polar cap temperature rises by >= 10 K over the preceding 7 days
      (confirming dynamic polar cap warming alongside wind reversal).
- ``pressure_persistently_high``: Primary location 7-day mean sea-level/barometric pressure >= 1024.0 hPa
  AND current pressure >= 1022.0 hPa
- ``major_pattern_change``: Any of AO, NAO, PNA has |7-day observed change| >= 1.5 SD,
  OR |7-day GEFS forecast change from current| >= 1.5 SD, OR sign flip with |change| >= 1.0 SD
- ``signals_conflicting``: High-latitude blocking/cold-East indicators and Pacific/tropical indicators
  point in opposing directions (e.g., negative AO/NAO paired with negative PNA or warm-phase MJO 4–6,
  or strongly positive AO/NAO paired with cold-favoring MJO 8/1/2 + El Niño).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import (
    DerivedSignals,
    ENSOBundle,
    LocalLocationBundle,
    MJOBundle,
    StratosphereBundle,
    TeleconnectionIndexBundle,
)


def _compute_teleconnection_summary(
    bundle: Optional[TeleconnectionIndexBundle],
) -> Dict[str, Any]:
    """Compute current value, 1d/7d/14d observed changes, and GEFS day-7/day-14 forecast summary."""
    if not bundle or not bundle.observations:
        return {"available": False}

    obs = bundle.observations
    current_pt = obs[-1]
    current_val = round(current_pt.value, 2)

    change_1d: Optional[float] = None
    if len(obs) >= 2:
        change_1d = round(current_pt.value - obs[-2].value, 2)

    change_7d: Optional[float] = None
    if len(obs) >= 8:
        change_7d = round(current_pt.value - obs[-8].value, 2)

    change_14d: Optional[float] = None
    if len(obs) >= 15:
        change_14d = round(current_pt.value - obs[-15].value, 2)

    gefs_day7: Optional[float] = None
    gefs_day7_iqr: Optional[List[float]] = None
    gefs_day14: Optional[float] = None
    gefs_day14_iqr: Optional[List[float]] = None
    forecast_change_7d: Optional[float] = None

    if bundle.forecasts:
        f7 = next(
            (f for f in bundle.forecasts if f.lead_days == 7),
            bundle.forecasts[min(6, len(bundle.forecasts) - 1)],
        )
        gefs_day7 = round(f7.ensemble_mean, 2)
        gefs_day7_iqr = [round(f7.ensemble_p25, 2), round(f7.ensemble_p75, 2)]
        forecast_change_7d = round(f7.ensemble_mean - current_pt.value, 2)

        f14 = next(
            (f for f in bundle.forecasts if f.lead_days == 14),
            bundle.forecasts[-1],
        )
        gefs_day14 = round(f14.ensemble_mean, 2)
        gefs_day14_iqr = [round(f14.ensemble_p25, 2), round(f14.ensemble_p75, 2)]

    return {
        "available": True,
        "latest_date": current_pt.date,
        "current": current_val,
        "change_1d": change_1d,
        "change_7d": change_7d,
        "change_14d": change_14d,
        "gefs_day7": gefs_day7,
        "gefs_day7_iqr": gefs_day7_iqr,
        "gefs_day14": gefs_day14,
        "gefs_day14_iqr": gefs_day14_iqr,
        "forecast_change_7d": forecast_change_7d,
    }


def _compute_stratosphere_summary(
    strat: Optional[StratosphereBundle],
) -> Dict[str, Any]:
    """Compute 10-hPa 60°N zonal wind changes, polar cap warming, and WMO SSW diagnostics."""
    if not strat or not strat.observations:
        return {"available": False}

    obs = strat.observations
    cur = obs[-1]
    cur_u = round(cur.zonal_wind_10hpa_60n, 2)
    cur_t = round(cur.polar_cap_temp_10hpa_60_90n, 2) if cur.polar_cap_temp_10hpa_60_90n is not None else None

    change_7d_u: Optional[float] = None
    change_7d_t: Optional[float] = None
    if len(obs) >= 8:
        prev7 = obs[-8]
        change_7d_u = round(cur.zonal_wind_10hpa_60n - prev7.zonal_wind_10hpa_60n, 2)
        if cur.polar_cap_temp_10hpa_60_90n is not None and prev7.polar_cap_temp_10hpa_60_90n is not None:
            change_7d_t = round(cur.polar_cap_temp_10hpa_60_90n - prev7.polar_cap_temp_10hpa_60_90n, 2)

    fcst = strat.forecasts or []
    forecast_min_u: Optional[float] = None
    forecast_min_date: Optional[str] = None
    forecast_end_u: Optional[float] = None
    forecast_max_t_rise: Optional[float] = None

    if fcst:
        min_pt = min(fcst, key=lambda p: p.zonal_wind_10hpa_60n)
        forecast_min_u = round(min_pt.zonal_wind_10hpa_60n, 2)
        forecast_min_date = min_pt.date
        forecast_end_u = round(fcst[-1].zonal_wind_10hpa_60n, 2)
        if cur.polar_cap_temp_10hpa_60_90n is not None:
            t_vals = [p.polar_cap_temp_10hpa_60_90n for p in fcst if p.polar_cap_temp_10hpa_60_90n is not None]
            if t_vals:
                forecast_max_t_rise = round(max(t_vals) - cur.polar_cap_temp_10hpa_60_90n, 2)

    # Check winter season (Nov-Mar) for SSW relevance
    try:
        dt = datetime.strptime(cur.date, "%Y-%m-%d")
        is_winter_season = dt.month in (11, 12, 1, 2, 3)
    except Exception:
        is_winter_season = True

    observed_reversal = bool(is_winter_season and cur_u < 0.0)
    forecast_reversal = bool(
        is_winter_season
        and forecast_min_u is not None
        and forecast_min_u < 0.0
    )

    # WMO Major SSW requires 60N 10hPa wind reversal (<0 m/s) during winter (not final warming)
    # accompanied by polar cap (60-90N) warming at 10 hPa.
    # Furthermore, require at least 2 consecutive days of easterly wind or >= +8K 7-day polar cap warming
    # so a single noisy slightly-negative data point is not automatically labeled a Major SSW.
    recent_easterly_days = sum(1 for p in obs[-3:] if p.zonal_wind_10hpa_60n < 0.0)
    warming_confirmed = (change_7d_t is not None and change_7d_t >= 8.0)
    major_ssw_observed = bool(
        is_winter_season
        and observed_reversal
        and (recent_easterly_days >= 2 and warming_confirmed)
    )

    return {
        "available": True,
        "latest_date": cur.date,
        "current_wind": cur_u,
        "change_7d": change_7d_u,
        "current_polar_cap_temp_k": cur_t,
        "polar_cap_temp_change_7d_k": change_7d_t,
        "forecast_min": forecast_min_u,
        "forecast_min_date": forecast_min_date,
        "forecast_end_wind": forecast_end_u,
        "forecast_max_temp_rise_k": forecast_max_t_rise,
        "observed_reversal": observed_reversal,
        "forecast_reversal": forecast_reversal,
        "major_ssw_criteria_met": major_ssw_observed,
    }


def _compute_mjo_summary(mjo: Optional[MJOBundle]) -> Dict[str, Any]:
    """Compute MJO phase, amplitude, active status, and 7-day progression."""
    if not mjo or not mjo.history:
        return {"available": False}

    hist = mjo.history
    cur = hist[-1]
    prev_7d = hist[-8] if len(hist) >= 8 else hist[0]

    # Determine eastward vs stationary/weak progression
    phase_diff = (cur.phase - prev_7d.phase) % 8
    if not cur.active and not prev_7d.active:
        motion = "weak / incoherent (inside unit circle)"
    elif phase_diff == 0:
        motion = f"stationary in Phase {cur.phase}"
    elif 1 <= phase_diff <= 4:
        motion = f"eastward from Phase {prev_7d.phase} to Phase {cur.phase}"
    else:
        motion = f"shifted from Phase {prev_7d.phase} to Phase {cur.phase}"

    return {
        "available": True,
        "latest_date": cur.date,
        "phase": cur.phase,
        "amplitude": round(cur.amplitude, 2),
        "active": cur.active,
        "previous_phase_7d": prev_7d.phase,
        "previous_amplitude_7d": round(prev_7d.amplitude, 2),
        "amplitude_change_7d": round(cur.amplitude - prev_7d.amplitude, 2),
        "motion_7d": motion,
    }


def _compute_enso_summary(enso: Optional[ENSOBundle]) -> Dict[str, Any]:
    """Summarize slow-moving ENSO background state."""
    if not enso or enso.latest_nino34 is None:
        return {"available": False}

    change_3m: Optional[float] = None
    if len(enso.nino34_series) >= 4:
        change_3m = round(
            enso.nino34_series[-1].nino34_anomaly - enso.nino34_series[-4].nino34_anomaly,
            2,
        )

    return {
        "available": True,
        "latest_period": enso.latest_period,
        "nino34": round(enso.latest_nino34, 2),
        "nino34_change_3m": change_3m,
        "oni": round(enso.latest_oni, 2) if enso.latest_oni is not None else None,
        "oni_season": enso.latest_oni_season,
        "roni": round(enso.latest_roni, 2) if enso.latest_roni is not None else None,
        "meiv2": round(enso.latest_meiv2, 2) if enso.latest_meiv2 is not None else None,
        "state": enso.enso_state_label,
    }


def compute_derived_signals(
    teleconnections: Dict[str, TeleconnectionIndexBundle],
    stratosphere: Optional[StratosphereBundle],
    mjo: Optional[MJOBundle],
    enso: Optional[ENSOBundle],
    locations: List[LocalLocationBundle],
) -> DerivedSignals:
    """Calculate all quantitative signal changes and deterministic flags."""
    ao_info = _compute_teleconnection_summary(teleconnections.get("AO"))
    nao_info = _compute_teleconnection_summary(teleconnections.get("NAO"))
    pna_info = _compute_teleconnection_summary(teleconnections.get("PNA"))
    pv_info = _compute_stratosphere_summary(stratosphere)
    mjo_info = _compute_mjo_summary(mjo)
    enso_info = _compute_enso_summary(enso)

    ao_cur = ao_info.get("current")
    nao_cur = nao_info.get("current")
    pna_cur = pna_info.get("current")

    ao_strongly_negative = bool(ao_cur is not None and ao_cur <= -1.5)
    ao_strongly_positive = bool(ao_cur is not None and ao_cur >= 1.5)
    nao_strongly_negative = bool(nao_cur is not None and nao_cur <= -1.5)
    nao_strongly_positive = bool(nao_cur is not None and nao_cur >= 1.5)
    pna_strongly_positive = bool(pna_cur is not None and pna_cur >= 1.5)
    pna_strongly_negative = bool(pna_cur is not None and pna_cur <= -1.5)

    mjo_active = bool(mjo_info.get("available") and mjo_info.get("active"))

    pv_change_7d = pv_info.get("change_7d")
    pv_cur = pv_info.get("current_wind")
    pv_fmin = pv_info.get("forecast_min")
    pv_fcst_drop = (
        (pv_fmin - pv_cur)
        if (pv_fmin is not None and pv_cur is not None)
        else 0.0
    )
    polar_vortex_rapidly_weakening = bool(
        (pv_change_7d is not None and pv_change_7d <= -10.0)
        or (pv_fcst_drop <= -15.0)
    )
    polar_vortex_reversal_observed = bool(pv_info.get("observed_reversal", False))
    polar_vortex_reversal_forecast = bool(pv_info.get("forecast_reversal", False))
    major_ssw_criteria_met = bool(pv_info.get("major_ssw_criteria_met", False))

    # Primary location pressure regime check
    pressure_persistently_high = False
    if locations:
        prim = locations[0]
        if (
            prim.pressure_mean_7d_hpa is not None
            and prim.current_pressure_hpa is not None
            and prim.pressure_mean_7d_hpa >= 1024.0
            and prim.current_pressure_hpa >= 1022.0
        ):
            pressure_persistently_high = True

    # Major pattern change check across AO, NAO, PNA
    major_pattern_change = False
    for info in (ao_info, nao_info, pna_info):
        if not info.get("available"):
            continue
        c7 = info.get("change_7d")
        f7 = info.get("forecast_change_7d")
        cur = info.get("current")
        day7 = info.get("gefs_day7")
        if (c7 is not None and abs(c7) >= 1.5) or (f7 is not None and abs(f7) >= 1.5):
            major_pattern_change = True
        if cur is not None and day7 is not None and (cur * day7 < 0) and abs(day7 - cur) >= 1.0:
            major_pattern_change = True

    # Conflicting signals check:
    # e.g. High-latitude blocking (AO/NAO < -0.5) vs Pacific troughing / warm East (PNA < -0.5)
    # or High-latitude positive AO/NAO (> +0.5) vs strongly positive PNA (> +0.75) or weakened PV
    signals_conflicting = False
    if ao_cur is not None and nao_cur is not None and pna_cur is not None:
        hl_mean = 0.5 * (ao_cur + nao_cur)
        # Typically, negative AO/NAO + positive PNA reinforce eastern North America troughing,
        # while positive AO/NAO + negative PNA reinforce eastern ridging/mildness.
        if (hl_mean <= -0.6 and pna_cur <= -0.6) or (hl_mean >= 0.6 and pna_cur >= 0.6):
            signals_conflicting = True
        # Or if stratosphere is reversing/weakening while tropospheric AO/NAO remain positive
        if (polar_vortex_reversal_forecast or polar_vortex_rapidly_weakening) and hl_mean >= 0.5:
            signals_conflicting = True
        # Or MJO active in warm phases (4, 5, 6) while AO/NAO are negative
        if mjo_active and mjo_info.get("phase") in (4, 5, 6) and hl_mean <= -0.6:
            signals_conflicting = True

    flags = {
        "ao_strongly_negative": ao_strongly_negative,
        "ao_strongly_positive": ao_strongly_positive,
        "nao_strongly_negative": nao_strongly_negative,
        "nao_strongly_positive": nao_strongly_positive,
        "pna_strongly_positive": pna_strongly_positive,
        "pna_strongly_negative": pna_strongly_negative,
        "mjo_active": mjo_active,
        "polar_vortex_rapidly_weakening": polar_vortex_rapidly_weakening,
        "polar_vortex_reversal_observed": polar_vortex_reversal_observed,
        "polar_vortex_reversal_forecast": polar_vortex_reversal_forecast,
        "major_ssw_criteria_met": major_ssw_criteria_met,
        "pressure_persistently_high": pressure_persistently_high,
        "major_pattern_change": major_pattern_change,
        "signals_conflicting": signals_conflicting,
    }

    notable: List[str] = []
    for name, info in (("AO", ao_info), ("NAO", nao_info), ("PNA", pna_info)):
        if info.get("available"):
            cur = info["current"]
            c7 = info.get("change_7d")
            f7 = info.get("gefs_day7")
            c7_str = f"{c7:+.2f}" if c7 is not None else "N/A"
            f7_str = f"{f7:+.2f}" if f7 is not None else "N/A"
            notable.append(f"{name}: current {cur:+.2f} SD (7d Δ: {c7_str}, GEFS Day-7 mean: {f7_str})")

    if pv_info.get("available"):
        u_cur = pv_info["current_wind"]
        u_c7 = pv_info.get("change_7d")
        u_fmin = pv_info.get("forecast_min")
        u_c7_str = f"{u_c7:+.1f} m/s" if u_c7 is not None else "N/A"
        u_fmin_str = f"{u_fmin:+.1f} m/s" if u_fmin is not None else "N/A"
        notable.append(
            f"10-hPa 60°N Wind: {u_cur:+.1f} m/s (7d Δ: {u_c7_str}, forecast min: {u_fmin_str})"
        )

    if mjo_info.get("available"):
        notable.append(
            f"MJO (ROMI): Phase {mjo_info['phase']} (amp {mjo_info['amplitude']:.2f}, "
            f"{'active' if mjo_info['active'] else 'inactive'}, {mjo_info['motion_7d']})"
        )

    if enso_info.get("available"):
        notable.append(
            f"ENSO: {enso_info['state']} (Niño 3.4 {enso_info['nino34']:+.2f}°C, period {enso_info['latest_period']})"
        )

    return DerivedSignals(
        ao=ao_info,
        nao=nao_info,
        pna=pna_info,
        polar_vortex=pv_info,
        mjo=mjo_info,
        enso=enso_info,
        flags=flags,
        notable_changes=notable,
    )
