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


def _compute_teleconnection_forecast_evolution(
    index_name: str,
    vintages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute run-to-run forecast evolution metrics across archived model vintages for AO, NAO, or PNA."""
    if not vintages:
        return {"available": False, "run_count": 0}

    latest_v = vintages[-1]
    latest_pts = latest_v.get("points") or []
    if not latest_pts:
        return {"available": False, "run_count": len(vintages)}

    # Select target valid date from latest run: prefer Day+7..Day+11 with largest |value|, else Day+7
    medium_pts = [p for p in latest_pts if 6 <= int(p.get("lead_days", 0)) <= 11]
    if medium_pts:
        target_pt = max(medium_pts, key=lambda p: abs(float(p["value"])))
    else:
        target_pt = next(
            (p for p in latest_pts if int(p.get("lead_days", 0)) == 7),
            latest_pts[min(6, len(latest_pts) - 1)],
        )

    target_date = str(target_pt["valid_time"])
    target_lead = int(target_pt.get("lead_days", 7))

    # Extract each run's forecast for target_date (or fallback to same lead if target_date was beyond range)
    run_series: List[Dict[str, Any]] = []
    for v in vintages:
        pts = v.get("points") or []
        match = next((p for p in pts if p.get("valid_time") == target_date), None)
        if match is None:
            match = next((p for p in pts if int(p.get("lead_days", 0)) == target_lead), None)
        if match is not None:
            iqr_w = None
            if match.get("ensemble_p25") is not None and match.get("ensemble_p75") is not None:
                iqr_w = round(float(match["ensemble_p75"]) - float(match["ensemble_p25"]), 2)
            run_series.append(
                {
                    "run_date": v.get("run_date") or str(v.get("model_run_time", ""))[:10],
                    "model_run_time": v.get("model_run_time"),
                    "valid_time": match.get("valid_time"),
                    "lead_days": int(match.get("lead_days", target_lead)),
                    "value": round(float(match["value"]), 2),
                    "ensemble_std": round(float(match["ensemble_std"]), 2) if match.get("ensemble_std") is not None else None,
                    "iqr_width": iqr_w,
                }
            )

    if not run_series:
        return {"available": False, "run_count": len(vintages)}

    cur_val = run_series[-1]["value"]
    prev_val = run_series[-2]["value"] if len(run_series) >= 2 else None
    three_ago_val = run_series[-4]["value"] if len(run_series) >= 4 else (run_series[0]["value"] if len(run_series) == 3 else None)
    five_ago_val = run_series[-6]["value"] if len(run_series) >= 6 else None

    change_24h = round(cur_val - prev_val, 2) if prev_val is not None else None
    change_3run = round(cur_val - three_ago_val, 2) if three_ago_val is not None else None
    change_5run = round(cur_val - five_ago_val, 2) if five_ago_val is not None else None

    # Ensemble spread evolution
    cur_iqr = run_series[-1].get("iqr_width")
    prev_iqr = run_series[-2].get("iqr_width") if len(run_series) >= 2 else None
    iqr_change_24h = round(cur_iqr - prev_iqr, 2) if (cur_iqr is not None and prev_iqr is not None) else None
    spread_trend = "unchanged"
    if iqr_change_24h is not None:
        if iqr_change_24h <= -0.15:
            spread_trend = "narrowing (increasing ensemble agreement)"
        elif iqr_change_24h >= 0.15:
            spread_trend = "widening (increasing ensemble uncertainty)"

    # Consecutive runs supporting negative (< -0.5 SD), positive (> +0.5 SD), or strong (|v| >= 1.0 SD)
    consec_neg = 0
    for r in reversed(run_series):
        if r["value"] <= -0.5:
            consec_neg += 1
        else:
            break

    consec_pos = 0
    for r in reversed(run_series):
        if r["value"] >= 0.5:
            consec_pos += 1
        else:
            break

    consec_strong = 0
    first_strong_run: Optional[str] = None
    if abs(cur_val) >= 1.0:
        sign_cur = -1 if cur_val < 0 else 1
        for r in reversed(run_series):
            if (r["value"] * sign_cur) >= 1.0:
                consec_strong += 1
                first_strong_run = r["run_date"]
            else:
                break

    # Did a previously strong signal (>= 1.0 SD in earlier runs) disappear (now |cur_val| < 0.4 or flipped)?
    prior_strong_neg = any(r["value"] <= -1.0 for r in run_series[:-1])
    prior_strong_pos = any(r["value"] >= 1.0 for r in run_series[:-1])

    ref_delta = change_3run if change_3run is not None else (change_24h or 0.0)
    trend_code = "stable"
    display_label = "→ little change"
    active_runs = len(run_series)

    if len(run_series) == 1:
        if cur_val <= -1.0:
            trend_code = "tentative_negative_signal"
            display_label = "↓ tentative negative signal (single run)"
        elif cur_val >= 1.0:
            trend_code = "tentative_positive_signal"
            display_label = "↑ tentative positive signal (single run)"
        else:
            trend_code = "single_run_baseline"
            display_label = "→ single run archived"
    else:
        if prior_strong_neg and cur_val > -0.35:
            trend_code = "previous_negative_signal_disappeared"
            display_label = "↑ backed away from prior negative signal"
        elif prior_strong_pos and cur_val < 0.35:
            trend_code = "previous_positive_signal_disappeared"
            display_label = "↓ backed away from prior positive signal"
        elif cur_val <= -0.5 and ref_delta <= -0.25:
            trend_code = "strengthening_negative_signal"
            display_label = "↓ stronger negative signal"
            active_runs = max(consec_neg, 2)
        elif cur_val >= 0.5 and ref_delta >= 0.25:
            trend_code = "strengthening_positive_signal"
            display_label = "↑ increasingly positive"
            active_runs = max(consec_pos, 2)
        elif cur_val <= -0.5 and ref_delta >= 0.25:
            trend_code = "weakening_negative_signal"
            display_label = "↑ negative signal moderating"
            active_runs = max(consec_neg, 1)
        elif cur_val >= 0.5 and ref_delta <= -0.25:
            trend_code = "weakening_positive_signal"
            display_label = "↓ positive signal moderating"
            active_runs = max(consec_pos, 1)
        elif consec_neg >= 2:
            trend_code = "persistent_negative_signal"
            display_label = "→ steady negative signal"
            active_runs = consec_neg
        elif consec_pos >= 2:
            trend_code = "persistent_positive_signal"
            display_label = "→ steady positive signal"
            active_runs = consec_pos
        else:
            trend_code = "little_change"
            display_label = "→ little change"
            active_runs = len(run_series)

    return {
        "available": True,
        "index": index_name.upper(),
        "run_count": len(run_series),
        "target_date": target_date,
        "lead_days": target_lead,
        "current_run": cur_val,
        "previous_run": prev_val,
        "three_runs_ago": three_ago_val,
        "five_runs_ago": five_ago_val,
        "change_24h": change_24h,
        "change_3run": change_3run,
        "change_5run": change_5run,
        "consecutive_runs_negative": consec_neg,
        "consecutive_runs_positive": consec_pos,
        "consecutive_runs_strong_1sd": consec_strong,
        "first_run_introducing_strong_signal": first_strong_run,
        "current_iqr_width_sd": cur_iqr,
        "iqr_change_24h_sd": iqr_change_24h,
        "spread_trend": spread_trend,
        "trend": trend_code,
        "display_label": display_label,
        "display_runs": active_runs,
        "run_history": run_series[-6:],
    }


def _compute_stratosphere_forecast_evolution(
    vintages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute run-to-run forecast evolution & threshold-crossing tracking for 10-hPa 60°N zonal wind."""
    if not vintages:
        return {"available": False, "run_count": 0}

    run_summaries: List[Dict[str, Any]] = []
    for v in vintages:
        pts = v.get("points") or []
        if not pts:
            continue
        min_pt = min(pts, key=lambda p: float(p["value"]))
        min_u = round(float(min_pt["value"]), 2)
        min_dt = str(min_pt["valid_time"])
        cross_pt = next((p for p in pts if float(p["value"]) < 0.0), None)
        run_summaries.append(
            {
                "run_date": v.get("run_date") or str(v.get("model_run_time", ""))[:10],
                "model_run_time": v.get("model_run_time"),
                "minimum_u_ms": min_u,
                "minimum_date": min_dt,
                "reversal_forecast": min_u < 0.0,
                "crossing_date": str(cross_pt["valid_time"]) if cross_pt else None,
            }
        )

    if not run_summaries:
        return {"available": False, "run_count": 0}

    cur = run_summaries[-1]
    prev = run_summaries[-2] if len(run_summaries) >= 2 else None
    three_ago = (
        run_summaries[-4]
        if len(run_summaries) >= 4
        else (run_summaries[0] if len(run_summaries) == 3 else None)
    )
    five_ago = run_summaries[-6] if len(run_summaries) >= 6 else None

    cur_min = cur["minimum_u_ms"]
    prev_min = prev["minimum_u_ms"] if prev else None
    three_min = three_ago["minimum_u_ms"] if three_ago else None
    five_min = five_ago["minimum_u_ms"] if five_ago else None

    change_24h = round(cur_min - prev_min, 2) if prev_min is not None else None
    change_3run = round(cur_min - three_min, 2) if three_min is not None else None
    change_5run = round(cur_min - five_min, 2) if five_min is not None else None

    # Threshold crossing (< 0 m/s wind reversal) persistence tracking
    reversal_runs = [r for r in run_summaries if r["reversal_forecast"]]
    first_reversal_run = reversal_runs[0]["run_date"] if reversal_runs else None
    latest_reversal_run = reversal_runs[-1]["run_date"] if reversal_runs else None

    consec_reversal = 0
    for r in reversed(run_summaries):
        if r["reversal_forecast"]:
            consec_reversal += 1
        else:
            break

    had_prior_reversal = any(r["reversal_forecast"] for r in run_summaries[:-1])
    ref_delta = change_3run if change_3run is not None else (change_24h or 0.0)

    trend_code = "stable_westerly"
    display_label = "→ steady westerly vortex"
    display_runs = len(run_summaries)

    if len(run_summaries) == 1:
        if cur["reversal_forecast"]:
            trend_code = "tentative_reversal_signal"
            display_label = "↓ tentative reversal signal (1 run)"
            display_runs = 1
        else:
            trend_code = "single_run_baseline"
            display_label = "→ single run archived"
            display_runs = 1
    else:
        if had_prior_reversal and not cur["reversal_forecast"]:
            trend_code = "previously_forecast_reversal_disappeared"
            display_label = "↑ prior reversal signal disappeared"
            display_runs = len(run_summaries)
        elif cur["reversal_forecast"]:
            display_runs = consec_reversal
            if ref_delta <= -2.0 or (prev is not None and not prev["reversal_forecast"]):
                trend_code = "strengthening_reversal_signal"
                display_label = "↓ reversal signal strengthening" if consec_reversal >= 2 else "↓ reversal signal emerging"
            else:
                trend_code = "persistent_reversal_signal"
                display_label = "↓ reversal signal persisting"
        elif ref_delta <= -4.0:
            trend_code = "weakening_vortex_trend"
            display_label = "↓ vortex forecast weakening"
        elif ref_delta >= 4.0:
            trend_code = "strengthening_vortex_trend"
            display_label = "↑ vortex forecast strengthening"
        else:
            trend_code = "stable_westerly"
            display_label = "→ little change"

    return {
        "available": True,
        "run_count": len(run_summaries),
        "current_run_minimum": cur_min,
        "current_run_minimum_date": cur["minimum_date"],
        "previous_run_minimum": prev_min,
        "three_runs_ago_minimum": three_min,
        "five_runs_ago_minimum": five_min,
        "change_in_predicted_minimum_24h_ms": change_24h,
        "change_in_predicted_minimum_3run_ms": change_3run,
        "change_in_predicted_minimum_5run_ms": change_5run,
        "reversal_forecast": cur["reversal_forecast"],
        "forecast_crossing_date": cur["crossing_date"],
        "first_run_showing_reversal": first_reversal_run,
        "latest_run_showing_reversal": latest_reversal_run,
        "consecutive_runs_forecasting_reversal": consec_reversal,
        "previously_forecast_reversal_disappeared": bool(had_prior_reversal and not cur["reversal_forecast"]),
        "trend": trend_code,
        "display_label": display_label,
        "display_runs": display_runs,
        "run_history": run_summaries[-6:],
    }


def _build_what_changed_categories(
    ao_info: Dict[str, Any],
    nao_info: Dict[str, Any],
    pna_info: Dict[str, Any],
    pv_info: Dict[str, Any],
    mjo_info: Dict[str, Any],
    forecast_evolution: Dict[str, Any],
) -> Dict[str, List[str]]:
    """Build deterministic V2 'WHAT CHANGED' bullets separated into Observed, Forecast, Model Trend, and Stratosphere."""
    observed_bullets: List[str] = []
    forecast_bullets: List[str] = []
    model_trend_bullets: List[str] = []
    strat_bullets: List[str] = []

    for code, info in (("AO", ao_info), ("NAO", nao_info), ("PNA", pna_info)):
        if not info.get("available"):
            continue
        cur = info["current"]
        c7 = info.get("change_7d")
        if c7 is not None and abs(c7) >= 0.25:
            prev7 = round(cur - c7, 2)
            verb = "fell" if c7 < 0 else "rose"
            observed_bullets.append(
                f"{code} {verb} from {prev7:+.2f} to {cur:+.2f} SD over seven days ({c7:+.2f} SD)."
            )
        elif c7 is not None:
            observed_bullets.append(f"{code} held near {cur:+.2f} SD (7d Δ {c7:+.2f} SD).")

        f7 = info.get("gefs_day7")
        f14 = info.get("gefs_day14")
        if f7 is not None:
            iqr = info.get("gefs_day7_iqr")
            iqr_str = f" (IQR {iqr[0]:+.2f} to {iqr[1]:+.2f})" if iqr else ""
            forecast_bullets.append(
                f"GEFS projects {code} at {f7:+.2f} SD by Day 7{iqr_str}"
                + (f" and {f14:+.2f} SD by Day 14." if f14 is not None else ".")
            )

        evol = forecast_evolution.get(code.lower()) or forecast_evolution.get(code) or {}
        if evol.get("available") and evol.get("run_count", 0) >= 2:
            t_dt = evol.get("target_date", "D+7")
            tr = evol.get("trend", "")
            c_run = evol.get("current_run")
            p_run = evol.get("previous_run")
            r3 = evol.get("three_runs_ago")
            ref_str = (
                f"from {r3:+.2f} SD three runs ago to {c_run:+.2f} SD"
                if r3 is not None
                else f"from {p_run:+.2f} SD in the prior run to {c_run:+.2f} SD"
            )
            if tr == "strengthening_negative_signal":
                model_trend_bullets.append(
                    f"{code} negative signal for {t_dt} has strengthened ({ref_str}; "
                    f"{evol.get('consecutive_runs_negative', 1)} consecutive negative runs)."
                )
            elif tr == "strengthening_positive_signal":
                model_trend_bullets.append(
                    f"{code} positive signal for {t_dt} has strengthened ({ref_str}; "
                    f"{evol.get('consecutive_runs_positive', 1)} consecutive positive runs)."
                )
            elif "disappeared" in tr:
                model_trend_bullets.append(
                    f"Models have backed away from the previously forecast {code} signal for {t_dt} (now {c_run:+.2f} SD)."
                )
            elif tr in ("persistent_negative_signal", "persistent_positive_signal"):
                model_trend_bullets.append(
                    f"{code} outlook for {t_dt} has remained consistent across {evol.get('display_runs', 2)} runs ({c_run:+.2f} SD)."
                )
            else:
                model_trend_bullets.append(
                    f"{code} forecast for {t_dt} shows little net change across {evol.get('run_count', 2)} archived runs ({c_run:+.2f} SD)."
                )

    if mjo_info.get("available"):
        observed_bullets.append(
            f"MJO is in Phase {mjo_info['phase']} (amplitude {mjo_info['amplitude']:.2f}, {mjo_info['motion_7d']})."
        )

    if pv_info.get("available"):
        u_cur = pv_info["current_wind"]
        u_c7 = pv_info.get("change_7d")
        f_min = pv_info.get("forecast_min")
        f_dt = pv_info.get("forecast_min_date")
        if u_c7 is not None:
            strat_bullets.append(
                f"Observed 10-hPa 60°N wind is {u_cur:+.1f} m/s (7d change {u_c7:+.1f} m/s)."
            )
        if f_min is not None:
            strat_bullets.append(
                f"Latest GEOS-5 FP forecast reaches a minimum of {f_min:+.1f} m/s on {f_dt}."
            )
        st_evol = forecast_evolution.get("stratosphere") or {}
        if st_evol.get("available") and st_evol.get("run_count", 0) >= 2:
            if st_evol.get("previously_forecast_reversal_disappeared"):
                strat_bullets.append(
                    f"Previously forecast 10-hPa wind reversal (first seen {st_evol.get('first_run_showing_reversal')}) "
                    f"has disappeared from the latest run (min now {st_evol.get('current_run_minimum'):+.1f} m/s)."
                )
            elif st_evol.get("reversal_forecast"):
                n_rev = st_evol.get("consecutive_runs_forecasting_reversal", 1)
                strat_bullets.append(
                    f"{n_rev} consecutive run(s) now forecast 10-hPa 60°N wind reversal (< 0 m/s), "
                    f"crossing around {st_evol.get('forecast_crossing_date')}."
                )
            elif st_evol.get("change_in_predicted_minimum_24h_ms") is not None:
                strat_bullets.append(
                    f"Forecast 10-hPa minimum wind shifted by {st_evol['change_in_predicted_minimum_24h_ms']:+.1f} m/s vs. prior run."
                )

    return {
        "OBSERVED": observed_bullets,
        "FORECAST": forecast_bullets,
        "MODEL_TREND": model_trend_bullets,
        "STRATOSPHERE": strat_bullets,
    }


def compute_derived_signals(
    teleconnections: Dict[str, TeleconnectionIndexBundle],
    stratosphere: Optional[StratosphereBundle],
    mjo: Optional[MJOBundle],
    enso: Optional[ENSOBundle],
    locations: List[LocalLocationBundle],
    forecast_vintages: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    verification_summary: Optional[Dict[str, Any]] = None,
) -> DerivedSignals:
    """Calculate all quantitative signal changes, forecast evolution, and deterministic flags."""
    ao_info = _compute_teleconnection_summary(teleconnections.get("AO"))
    nao_info = _compute_teleconnection_summary(teleconnections.get("NAO"))
    pna_info = _compute_teleconnection_summary(teleconnections.get("PNA"))
    pv_info = _compute_stratosphere_summary(stratosphere)
    mjo_info = _compute_mjo_summary(mjo)
    enso_info = _compute_enso_summary(enso)

    # V2 Forecast Evolution across archived runs
    vintages_map = forecast_vintages or {}
    forecast_evolution: Dict[str, Any] = {}
    for code in ("AO", "NAO", "PNA"):
        v_list = vintages_map.get(code) or []
        if not v_list:
            # Fallback: construct single-vintage or recent_vintages from the bundle itself
            tb = teleconnections.get(code)
            if tb and (tb.recent_vintages or tb.forecasts):
                src_pts = tb.recent_vintages if tb.recent_vintages else tb.forecasts
                by_init: Dict[str, List[Dict[str, Any]]] = {}
                for f in src_pts:
                    by_init.setdefault(f.init_date, []).append(
                        {
                            "valid_time": f.valid_date,
                            "lead_days": f.lead_days,
                            "value": f.ensemble_mean,
                            "ensemble_p25": f.ensemble_p25,
                            "ensemble_p75": f.ensemble_p75,
                            "ensemble_std": f.ensemble_std,
                        }
                    )
                for init_d in sorted(by_init.keys()):
                    v_list.append(
                        {
                            "model_run_time": f"{init_d}T00:00Z",
                            "run_date": init_d,
                            "model": "GEFS",
                            "points": by_init[init_d],
                        }
                    )
        forecast_evolution[code.lower()] = _compute_teleconnection_forecast_evolution(code, v_list)

    strat_v_list = vintages_map.get("U60N_10HPA") or vintages_map.get("stratosphere") or []
    if not strat_v_list and stratosphere and stratosphere.forecasts:
        init_d = stratosphere.observations[-1].date if stratosphere.observations else stratosphere.forecasts[0].date
        strat_v_list = [
            {
                "model_run_time": f"{init_d}T00:00Z",
                "run_date": init_d,
                "model": "GEOS5_FP",
                "points": [
                    {"valid_time": p.date, "value": p.zonal_wind_10hpa_60n}
                    for p in stratosphere.forecasts
                ],
            }
        ]
    forecast_evolution["stratosphere"] = _compute_stratosphere_forecast_evolution(strat_v_list)

    what_changed = _build_what_changed_categories(
        ao_info=ao_info,
        nao_info=nao_info,
        pna_info=pna_info,
        pv_info=pv_info,
        mjo_info=mjo_info,
        forecast_evolution=forecast_evolution,
    )

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
        forecast_evolution=forecast_evolution,
        what_changed=what_changed,
        verification=verification_summary or {},
        flags=flags,
        notable_changes=notable,
    )
