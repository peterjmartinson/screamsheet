"""Black-and-white print-friendly ReportLab vector charts for Weather Patterns.

All charts are constructed using ``reportlab.graphics.shapes`` primitives so they
render as crisp, resolution-independent vector graphics on home laser/inkjet
printers without relying on color to distinguish series. Series are differentiated
by line style (solid, dashed, dotted), stroke weight, and geometric markers
(filled circle, open square, diamond/triangle), with subtle grayscale fills for
reference zones and ensemble spread.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from reportlab.graphics.shapes import (
    Circle,
    Drawing,
    Group,
    Line,
    Polygon,
    PolyLine,
    Rect,
    String,
)
from reportlab.lib import colors

from .models import (
    ENSOBundle,
    LocalLocationBundle,
    MJOBundle,
    SnowLocationBundle,
    StratosphereBundle,
    TeleconnectionIndexBundle,
)

# Grayscale palette tuned for B&W printing
BLACK = colors.HexColor("#000000")
DARK_GRAY = colors.HexColor("#333333")
MID_GRAY = colors.HexColor("#666666")
LIGHT_GRAY = colors.HexColor("#B8B8B8")
GRID_GRAY = colors.HexColor("#D8D8D8")
SHADE_GRAY = colors.HexColor("#E6E6E6")
SHADE_LIGHT = colors.HexColor("#F2F2F2")
WHITE = colors.HexColor("#FFFFFF")

MJO_PHASE_REGIONS = {
    1: "W. Hem. & Africa",
    2: "Indian Ocean",
    3: "Indian Ocean",
    4: "Maritime Continent",
    5: "Maritime Continent",
    6: "Western Pacific",
    7: "Western Pacific",
    8: "W. Hem. & Africa",
}


def _draw_marker(
    g: Group,
    shape: str,
    x: float,
    y: float,
    size: float = 2.4,
    stroke: colors.Color = BLACK,
    fill: colors.Color = WHITE,
) -> None:
    """Draw a small geometric point marker for B&W series differentiation."""
    if shape == "circle_filled":
        g.add(Circle(x, y, size, strokeColor=stroke, fillColor=stroke, strokeWidth=0.7))
    elif shape == "square_open":
        g.add(
            Rect(
                x - size,
                y - size,
                size * 2,
                size * 2,
                strokeColor=stroke,
                fillColor=fill,
                strokeWidth=0.9,
            )
        )
    elif shape == "diamond":
        pts = [x, y + size * 1.25, x + size * 1.25, y, x, y - size * 1.25, x - size * 1.25, y]
        g.add(Polygon(pts, strokeColor=stroke, fillColor=fill, strokeWidth=0.9))
    elif shape == "triangle":
        pts = [
            x,
            y + size * 1.3,
            x + size * 1.2,
            y - size * 1.0,
            x - size * 1.2,
            y - size * 1.0,
        ]
        g.add(Polygon(pts, strokeColor=stroke, fillColor=fill, strokeWidth=0.9))


def _short_date(d_str: str) -> str:
    """Format YYYY-MM-DD as MM/DD."""
    if len(d_str) >= 10 and d_str[4] == "-":
        return f"{d_str[5:7]}/{d_str[8:10]}"
    return d_str[-5:]


# ---------------------------------------------------------------------------
# Chart 1: AO / NAO / PNA Teleconnections (Observed + GEFS Forecast)
# ---------------------------------------------------------------------------

def build_teleconnections_chart(
    teleconnections: Dict[str, TeleconnectionIndexBundle],
    width: float = 564.0,
    height: float = 166.0,
    history_days: int = 50,
    forecast_days: int = 14,
) -> Drawing:
    """Build primary standardized AO / NAO / PNA chart with observed + GEFS forecast."""
    d = Drawing(width, height)
    d.hAlign = "CENTER"
    g = Group()

    pad_l, pad_r, pad_t, pad_b = 20.0, 2.0, 25.0, 20.0
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    x0, y0 = pad_l, pad_b
    x1, y1 = x0 + plot_w, y0 + plot_h

    g.add(
        String(
            0,
            height - 10,
            "CHART 4: ARCTIC (AO), NORTH ATLANTIC (NAO) & PACIFIC-NORTH AMERICAN (PNA) INDICES (SD)",
            fontName="Helvetica-Bold",
            fontSize=9.0,
            fillColor=BLACK,
        )
    )

    obs_dates_set = set()
    fcst_dates_set = set()
    for code in ("AO", "NAO", "PNA"):
        b = teleconnections.get(code)
        if not b:
            continue
        for pt in b.observations[-history_days:]:
            obs_dates_set.add(pt.date)
        last_obs = b.observations[-1].date if b.observations else ""
        fcst_pts = [f for f in b.forecasts if f.valid_date > last_obs][:forecast_days]
        for f in fcst_pts:
            fcst_dates_set.add(f.valid_date)

    obs_dates = sorted(obs_dates_set)[-history_days:]
    last_obs_global = obs_dates[-1] if obs_dates else ""
    fcst_dates = sorted(dt for dt in fcst_dates_set if dt > last_obs_global)[:forecast_days]
    all_dates = obs_dates + fcst_dates

    if len(all_dates) < 2:
        g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=MID_GRAY, fillColor=SHADE_LIGHT))
        g.add(
            String(
                x0 + plot_w / 2,
                y0 + plot_h / 2,
                "Teleconnection time-series data unavailable",
                fontName="Helvetica-Oblique",
                fontSize=8,
                textAnchor="middle",
                fillColor=MID_GRAY,
            )
        )
        d.add(g)
        return d

    date_to_idx = {dt: i for i, dt in enumerate(all_dates)}
    n_pts = len(all_dates)

    vals: List[float] = [-2.5, 2.5]
    for code in ("AO", "NAO", "PNA"):
        b = teleconnections.get(code)
        if not b:
            continue
        for pt in b.observations[-history_days:]:
            vals.append(pt.value)
        for f in b.forecasts[: forecast_days + 1]:
            vals.append(f.ensemble_mean)
            vals.append(f.ensemble_p25)
            vals.append(f.ensemble_p75)

    y_min = max(-4.5, math.floor(min(vals) * 2.0) / 2.0 - 0.3)
    y_max = min(4.5, math.ceil(max(vals) * 2.0) / 2.0 + 0.3)
    if y_max <= y_min:
        y_min, y_max = -3.0, 3.0

    def _x(idx: int) -> float:
        return x0 + (idx / max(1, n_pts - 1)) * plot_w

    def _y(val: float) -> float:
        clamped = max(y_min, min(y_max, val))
        return y0 + ((clamped - y_min) / (y_max - y_min)) * plot_h

    today_idx = len(obs_dates) - 1 if obs_dates else 0
    today_x = _x(today_idx)
    if fcst_dates:
        g.add(
            Rect(
                today_x,
                y0,
                x1 - today_x,
                plot_h,
                strokeColor=None,
                fillColor=SHADE_LIGHT,
            )
        )

    g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=BLACK, fillColor=None, strokeWidth=0.7))

    for tick in (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0):
        if y_min <= tick <= y_max:
            ty = _y(tick)
            is_zero = abs(tick) < 1e-6
            g.add(
                Line(
                    x0,
                    ty,
                    x1,
                    ty,
                    strokeColor=BLACK if is_zero else GRID_GRAY,
                    strokeWidth=1.0 if is_zero else 0.5,
                    strokeDashArray=None if is_zero else [2, 2],
                )
            )
            g.add(
                String(
                    x0 - 4,
                    ty - 2.5,
                    f"{tick:+.0f}" if tick != 0 else "0.0",
                    fontName="Helvetica-Bold" if is_zero else "Helvetica",
                    fontSize=7.2,
                    textAnchor="end",
                    fillColor=BLACK if is_zero else DARK_GRAY,
                )
            )

    # GEFS interquartile spread (p25-p75) shaded bands
    for code in ("AO", "NAO", "PNA"):
        b = teleconnections.get(code)
        if not b or not b.forecasts:
            continue
        spread_pts: List[Tuple[int, float, float]] = []
        if b.observations and b.observations[-1].date in date_to_idx:
            last_o = b.observations[-1]
            spread_pts.append((date_to_idx[last_o.date], last_o.value, last_o.value))
        for f in b.forecasts:
            if f.valid_date in date_to_idx and f.valid_date > last_obs_global:
                spread_pts.append((date_to_idx[f.valid_date], f.ensemble_p25, f.ensemble_p75))
        if len(spread_pts) >= 2:
            poly_coords: List[float] = []
            for idx_val, p25_v, _ in spread_pts:
                poly_coords.extend([_x(idx_val), _y(p25_v)])
            for idx_val, _, p75_v in reversed(spread_pts):
                poly_coords.extend([_x(idx_val), _y(p75_v)])
            g.add(
                Polygon(
                    poly_coords,
                    strokeColor=None,
                    fillColor=SHADE_GRAY,
                )
            )

    if obs_dates and fcst_dates:
        g.add(
            Line(
                today_x,
                y0,
                today_x,
                y1,
                strokeColor=BLACK,
                strokeWidth=0.9,
                strokeDashArray=[3, 2],
            )
        )
        g.add(
            String(
                today_x - 3,
                y1 - 8,
                "OBS",
                fontName="Helvetica-Bold",
                fontSize=5.8,
                textAnchor="end",
                fillColor=DARK_GRAY,
            )
        )
        g.add(
            String(
                today_x + 3,
                y1 - 8,
                "GEFS 31-MEM FCST",
                fontName="Helvetica-Bold",
                fontSize=5.8,
                textAnchor="start",
                fillColor=DARK_GRAY,
            )
        )

    styles = {
        "AO": {
            "stroke": BLACK,
            "width": 1.6,
            "dash": None,
            "marker": "circle_filled",
        },
        "NAO": {
            "stroke": DARK_GRAY,
            "width": 1.3,
            "dash": [5, 2.5],
            "marker": "square_open",
        },
        "PNA": {
            "stroke": BLACK,
            "width": 1.1,
            "dash": [1.5, 2.0],
            "marker": "diamond",
        },
    }

    for code in ("AO", "NAO", "PNA"):
        b = teleconnections.get(code)
        if not b:
            continue
        st = styles[code]
        obs_xy: List[Tuple[int, float]] = [
            (date_to_idx[pt.date], pt.value)
            for pt in b.observations[-history_days:]
            if pt.date in date_to_idx
        ]
        fcst_xy: List[Tuple[int, float]] = []
        if obs_xy:
            fcst_xy.append(obs_xy[-1])
        for f in b.forecasts:
            if f.valid_date in date_to_idx and f.valid_date > last_obs_global:
                fcst_xy.append((date_to_idx[f.valid_date], f.ensemble_mean))

        if len(obs_xy) >= 2:
            flat_obs: List[float] = []
            for idx_val, v in obs_xy:
                flat_obs.extend([_x(idx_val), _y(v)])
            g.add(
                PolyLine(
                    flat_obs,
                    strokeColor=st["stroke"],
                    strokeWidth=st["width"],
                    strokeDashArray=st["dash"],
                )
            )
            for k, (idx_val, v) in enumerate(obs_xy):
                if k == len(obs_xy) - 1 or (len(obs_xy) - 1 - k) % 6 == 0:
                    _draw_marker(
                        g,
                        st["marker"],
                        _x(idx_val),
                        _y(v),
                        size=2.1,
                        stroke=st["stroke"],
                    )

        if len(fcst_xy) >= 2:
            flat_fcst: List[float] = []
            for idx_val, v in fcst_xy:
                flat_fcst.extend([_x(idx_val), _y(v)])
            g.add(
                PolyLine(
                    flat_fcst,
                    strokeColor=st["stroke"],
                    strokeWidth=max(0.9, st["width"] - 0.3),
                    strokeDashArray=st["dash"] or [3, 1.5],
                )
            )
            for k, (idx_val, v) in enumerate(fcst_xy[1:], start=1):
                if k == len(fcst_xy) - 1 or k % 4 == 0:
                    _draw_marker(
                        g,
                        st["marker"],
                        _x(idx_val),
                        _y(v),
                        size=1.9,
                        stroke=st["stroke"],
                    )

    step = max(1, (n_pts - 1) // 7)
    tick_indices = list(range(0, n_pts, step))
    if (n_pts - 1) not in tick_indices:
        tick_indices.append(n_pts - 1)
    for idx_val in tick_indices:
        tx = _x(idx_val)
        g.add(Line(tx, y0, tx, y0 - 3, strokeColor=BLACK, strokeWidth=0.6))
        g.add(
            String(
                tx,
                y0 - 11,
                _short_date(all_dates[idx_val]),
                fontName="Helvetica",
                fontSize=7.4,
                textAnchor="middle",
                fillColor=BLACK,
            )
        )

    leg_x = x1 - 315.0
    leg_y = height - 19
    for i, code in enumerate(("AO", "NAO", "PNA")):
        st = styles[code]
        b = teleconnections.get(code)
        val_txt = (
            f"{b.observations[-1].value:+.2f}"
            if (b and b.observations)
            else "N/A"
        )
        lx = leg_x + i * 108
        g.add(
            Line(
                lx,
                leg_y + 2.5,
                lx + 16,
                leg_y + 2.5,
                strokeColor=st["stroke"],
                strokeWidth=st["width"],
                strokeDashArray=st["dash"],
            )
        )
        _draw_marker(g, st["marker"], lx + 8, leg_y + 2.5, size=2.0, stroke=st["stroke"])
        g.add(
            String(
                lx + 20,
                leg_y,
                f"{code}: {val_txt} SD",
                fontName="Helvetica-Bold",
                fontSize=7.6,
                fillColor=BLACK,
            )
        )

    d.add(g)
    return d


# ---------------------------------------------------------------------------
# Chart 2: Stratospheric Polar Vortex (10 hPa 60°N Zonal Wind & Polar Cap Temp)
# ---------------------------------------------------------------------------

def build_polar_vortex_chart(
    strat: Optional[StratosphereBundle],
    width: float = 252.0,
    height: float = 140.0,
    history_days: int = 45,
) -> Drawing:
    """Build 10-hPa 60°N Zonal Wind (m/s) history + forecast chart with 0 m/s reversal line."""
    d = Drawing(width, height)
    g = Group()

    pad_l, pad_r, pad_t, pad_b = 26.0, 2.0, 23.0, 20.0
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    x0, y0 = pad_l, pad_b
    x1, y1 = x0 + plot_w, y0 + plot_h

    g.add(
        String(
            2,
            height - 9,
            "CHART 1: STRATOSPHERIC POLAR VORTEX (10 hPa 60°N U-WIND)",
            fontName="Helvetica-Bold",
            fontSize=7.8,
            fillColor=BLACK,
        )
    )

    obs = strat.observations[-history_days:] if (strat and strat.observations) else []
    fcst = strat.forecasts if (strat and strat.forecasts) else []
    pts = [p for p in (obs + fcst) if p.zonal_wind_10hpa_60n is not None]

    if len(pts) < 2:
        g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=MID_GRAY, fillColor=SHADE_LIGHT))
        g.add(
            String(
                x0 + plot_w / 2,
                y0 + plot_h / 2,
                "Stratospheric 10-hPa wind data unavailable",
                fontName="Helvetica-Oblique",
                fontSize=7.5,
                textAnchor="middle",
                fillColor=MID_GRAY,
            )
        )
        d.add(g)
        return d

    n_pts = len(pts)
    u_vals = [float(p.zonal_wind_10hpa_60n) for p in pts]
    y_min = min(-10.0, math.floor(min(u_vals) / 10.0) * 10.0 - 5.0)
    y_max = max(35.0, math.ceil(max(u_vals) / 10.0) * 10.0 + 5.0)

    def _x(idx: int) -> float:
        return x0 + (idx / max(1, n_pts - 1)) * plot_w

    def _y(val: float) -> float:
        clamped = max(y_min, min(y_max, val))
        return y0 + ((clamped - y_min) / (y_max - y_min)) * plot_h

    zero_y = _y(0.0)
    if zero_y > y0:
        g.add(
            Rect(
                x0,
                y0,
                plot_w,
                zero_y - y0,
                strokeColor=None,
                fillColor=SHADE_GRAY,
            )
        )
        g.add(
            String(
                x0 + 3,
                y0 + 3,
                "EASTERLY / REVERSAL (< 0 m/s)",
                fontName="Helvetica-Bold",
                fontSize=5.3,
                fillColor=DARK_GRAY,
            )
        )

    g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=BLACK, fillColor=None, strokeWidth=0.7))

    step_y = 10.0 if (y_max - y_min) <= 65 else 20.0
    tick = math.ceil(y_min / step_y) * step_y
    while tick <= y_max:
        ty = _y(tick)
        is_zero = abs(tick) < 1e-6
        g.add(
            Line(
                x0,
                ty,
                x1,
                ty,
                strokeColor=BLACK if is_zero else GRID_GRAY,
                strokeWidth=1.1 if is_zero else 0.5,
                strokeDashArray=None if is_zero else [2, 2],
            )
        )
        g.add(
            String(
                x0 - 3,
                ty - 2,
                f"{tick:.0f}",
                fontName="Helvetica-Bold" if is_zero else "Helvetica",
                fontSize=6.0,
                textAnchor="end",
                fillColor=BLACK,
            )
        )
        tick += step_y

    obs_indices = [i for i, p in enumerate(pts) if not p.is_forecast]
    fcst_indices = [i for i, p in enumerate(pts) if p.is_forecast]

    if obs_indices and fcst_indices:
        div_x = _x(obs_indices[-1])
        g.add(
            Line(
                div_x,
                y0,
                div_x,
                y1,
                strokeColor=BLACK,
                strokeWidth=0.8,
                strokeDashArray=[2.5, 2],
            )
        )

    if len(obs_indices) >= 2:
        coords: List[float] = []
        for idx_val in obs_indices:
            coords.extend([_x(idx_val), _y(float(pts[idx_val].zonal_wind_10hpa_60n))])
        g.add(PolyLine(coords, strokeColor=BLACK, strokeWidth=1.5))
        last_o = obs_indices[-1]
        _draw_marker(
            g,
            "circle_filled",
            _x(last_o),
            _y(float(pts[last_o].zonal_wind_10hpa_60n)),
            size=2.3,
        )

    if fcst_indices:
        start_idx = obs_indices[-1] if obs_indices else fcst_indices[0]
        f_coords: List[float] = [
            _x(start_idx),
            _y(float(pts[start_idx].zonal_wind_10hpa_60n)),
        ]
        for idx_val in fcst_indices:
            f_coords.extend([_x(idx_val), _y(float(pts[idx_val].zonal_wind_10hpa_60n))])
        g.add(
            PolyLine(
                f_coords,
                strokeColor=BLACK,
                strokeWidth=1.3,
                strokeDashArray=[4, 2],
            )
        )
        last_f = fcst_indices[-1]
        _draw_marker(
            g,
            "square_open",
            _x(last_f),
            _y(float(pts[last_f].zonal_wind_10hpa_60n)),
            size=2.1,
        )

    latest_o = obs[-1] if obs else None
    u_txt = (
        f"Obs U: {latest_o.zonal_wind_10hpa_60n:.1f} m/s"
        if latest_o
        else "Obs U: N/A"
    )
    t_txt = (
        f"Cap T(60-90N): {latest_o.polar_cap_temp_10hpa_60_90n:.1f} K"
        if (latest_o and latest_o.polar_cap_temp_10hpa_60_90n is not None)
        else ""
    )
    min_f_txt = (
        f"Min Fcst: {min(p.zonal_wind_10hpa_60n for p in fcst):.1f} m/s"
        if fcst
        else ""
    )
    sub = " | ".join(s for s in (u_txt, min_f_txt, t_txt) if s)
    g.add(
        String(
            x0,
            height - 18,
            sub,
            fontName="Helvetica",
            fontSize=6.5,
            fillColor=DARK_GRAY,
        )
    )

    for idx_val in (0, n_pts // 2, n_pts - 1):
        tx = _x(idx_val)
        g.add(Line(tx, y0, tx, y0 - 2.5, strokeColor=BLACK, strokeWidth=0.6))
        g.add(
            String(
                tx,
                y0 - 11,
                _short_date(pts[idx_val].date),
                fontName="Helvetica",
                fontSize=6.5,
                textAnchor="middle",
                fillColor=BLACK,
            )
        )

    d.add(g)
    return d


# ---------------------------------------------------------------------------
# Chart 3: MJO Wheeler-Hendon Phase Space Diagram + Compact Status Box
# ---------------------------------------------------------------------------

def build_mjo_phase_diagram(
    mjo: Optional[MJOBundle],
    width: float = 252.0,
    height: float = 140.0,
    trail_days: int = 40,
) -> Drawing:
    """Build 2D MJO phase-space diagram with unit circle + compact status readout."""
    d = Drawing(width, height)
    g = Group()

    g.add(
        String(
            2,
            height - 9,
            "CHART 2: MJO PHASE SPACE (NOAA PSL ROMI) & STATUS",
            fontName="Helvetica-Bold",
            fontSize=7.8,
            fillColor=BLACK,
        )
    )

    box_size = min(height - 32.0, 104.0)
    bx0, by0 = 14.0, 11.0
    cx, cy = bx0 + box_size / 2.0, by0 + box_size / 2.0
    max_r = 3.0

    def _px(c1: float) -> float:
        clamped = max(-max_r, min(max_r, c1))
        return cx + (clamped / max_r) * (box_size / 2.0)

    def _py(c2: float) -> float:
        clamped = max(-max_r, min(max_r, c2))
        return cy + (clamped / max_r) * (box_size / 2.0)

    g.add(Rect(bx0, by0, box_size, box_size, strokeColor=BLACK, fillColor=WHITE, strokeWidth=0.7))

    unit_r = (1.0 / max_r) * (box_size / 2.0)
    g.add(
        Circle(
            cx,
            cy,
            unit_r,
            strokeColor=DARK_GRAY,
            fillColor=SHADE_GRAY,
            strokeWidth=0.7,
        )
    )

    half = box_size / 2.0
    for angle_deg in (0, 45, 90, 135, 180, 225, 270, 315):
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        scale = half / max(abs(cos_a), abs(sin_a))
        x_in = cx + unit_r * cos_a
        y_in = cy + unit_r * sin_a
        x_out = cx + scale * cos_a
        y_out = cy + scale * sin_a
        g.add(
            Line(
                x_in,
                y_in,
                x_out,
                y_out,
                strokeColor=LIGHT_GRAY,
                strokeWidth=0.5,
                strokeDashArray=[1.5, 1.5],
            )
        )

    phase_angles = [
        (1, 202.5),
        (2, 247.5),
        (3, 292.5),
        (4, 337.5),
        (5, 22.5),
        (6, 67.5),
        (7, 112.5),
        (8, 157.5),
    ]
    lbl_r = half * 0.82
    for ph_num, ang_deg in phase_angles:
        rad = math.radians(ang_deg)
        lx = cx + lbl_r * math.cos(rad)
        ly = cy + lbl_r * math.sin(rad) - 2.2
        g.add(
            String(
                lx,
                ly,
                str(ph_num),
                fontName="Helvetica-Bold",
                fontSize=5.8,
                textAnchor="middle",
                fillColor=MID_GRAY,
            )
        )

    g.add(String(cx, by0 - 8, "Indian Ocean (2-3)", fontName="Helvetica", fontSize=5.2, textAnchor="middle", fillColor=DARK_GRAY))
    g.add(String(cx, by0 + box_size + 2, "W. Pacific (6-7)", fontName="Helvetica", fontSize=5.2, textAnchor="middle", fillColor=DARK_GRAY))

    pts = mjo.history[-trail_days:] if (mjo and mjo.history) else []
    if len(pts) >= 2:
        older = pts[:-7] if len(pts) > 7 else []
        recent = pts[-8:] if len(pts) > 7 else pts
        if len(older) >= 2:
            c_old: List[float] = []
            for p in older:
                c_old.extend([_px(p.component_1), _py(p.component_2)])
            g.add(
                PolyLine(
                    c_old,
                    strokeColor=MID_GRAY,
                    strokeWidth=0.8,
                    strokeDashArray=[2, 1.5],
                )
            )
        if len(recent) >= 2:
            c_rec: List[float] = []
            for p in recent:
                c_rec.extend([_px(p.component_1), _py(p.component_2)])
            g.add(PolyLine(c_rec, strokeColor=BLACK, strokeWidth=1.6))

        _draw_marker(
            g,
            "square_open",
            _px(pts[0].component_1),
            _py(pts[0].component_2),
            size=1.8,
            stroke=MID_GRAY,
        )
        last_p = pts[-1]
        _draw_marker(
            g,
            "circle_filled",
            _px(last_p.component_1),
            _py(last_p.component_2),
            size=2.6,
            stroke=BLACK,
        )

    rx = bx0 + box_size + 8.0
    rw = width - rx - 2.0
    ry = by0
    g.add(Rect(rx, ry, rw, box_size, strokeColor=BLACK, fillColor=SHADE_LIGHT, strokeWidth=0.6))

    latest = pts[-1] if pts else None
    lines_txt: List[Tuple[str, str]] = []
    if latest:
        status_lbl = "ACTIVE (>=1.0)" if latest.active else "INACTIVE (<1.0)"
        p7 = pts[-8] if len(pts) >= 8 else pts[0]
        motion = (
            f"Ph {p7.phase} -> Ph {latest.phase}"
            if p7.phase != latest.phase
            else f"Stationary Ph {latest.phase}"
        )
        region = MJO_PHASE_REGIONS.get(latest.phase, "")
        lines_txt = [
            ("Date:", latest.date),
            ("Status:", status_lbl),
            ("Phase:", f"Phase {latest.phase}"),
            ("Region:", region),
            ("Amp:", f"{latest.amplitude:.2f}"),
            ("ROMI:", f"({latest.component_1:+.2f}, {latest.component_2:+.2f})"),
            ("7d Move:", motion),
        ]
    else:
        lines_txt = [("Status:", "Unavailable")]

    ty = ry + box_size - 12.0
    for k_lbl, v_lbl in lines_txt:
        g.add(String(rx + 4, ty, k_lbl, fontName="Helvetica-Bold", fontSize=6.8, fillColor=DARK_GRAY))
        g.add(String(rx + 38, ty, v_lbl[:22], fontName="Helvetica", fontSize=6.8, fillColor=BLACK))
        ty -= 13.8

    d.add(g)
    return d


# ---------------------------------------------------------------------------
# Chart 4: ENSO Background Context (18-24 Month Niño 3.4 Sparkline + Readout)
# ---------------------------------------------------------------------------

def build_enso_sparkline(
    enso: Optional[ENSOBundle],
    width: float = 252.0,
    height: float = 118.0,
    months: int = 24,
) -> Drawing:
    """Build 24-month Niño 3.4 anomaly sparkline with ±0.5°C thresholds and index table."""
    d = Drawing(width, height)
    g = Group()

    g.add(
        String(
            2,
            height - 9,
            "CHART 3: ENSO BACKGROUND — NINO 3.4 ANOMALY (°C, 24M)",
            fontName="Helvetica-Bold",
            fontSize=7.8,
            fillColor=BLACK,
        )
    )

    pad_l, pad_r, pad_t, pad_b = 26.0, 96.0, 18.0, 18.0
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    x0, y0 = pad_l, pad_b
    x1, y1 = x0 + plot_w, y0 + plot_h

    pts = enso.nino34_series[-months:] if (enso and enso.nino34_series) else []
    if len(pts) < 2:
        g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=MID_GRAY, fillColor=SHADE_LIGHT))
        g.add(
            String(
                x0 + plot_w / 2,
                y0 + plot_h / 2,
                "ENSO history unavailable",
                fontName="Helvetica-Oblique",
                fontSize=7,
                textAnchor="middle",
                fillColor=MID_GRAY,
            )
        )
        d.add(g)
        return d

    vals = [p.nino34_anomaly for p in pts] + [-1.0, 1.0]
    y_min = min(-1.5, math.floor(min(vals) * 2.0) / 2.0 - 0.35)
    y_max = max(1.5, math.ceil(max(vals) * 2.0) / 2.0 + 0.35)
    n_pts = len(pts)

    def _x(idx: int) -> float:
        return x0 + (idx + 0.5) * (plot_w / n_pts)

    def _y(val: float) -> float:
        clamped = max(y_min, min(y_max, val))
        return y0 + ((clamped - y_min) / (y_max - y_min)) * plot_h

    g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=BLACK, fillColor=WHITE, strokeWidth=0.6))

    tick_candidates = [(0.5, "+0.5"), (0.0, "0.0"), (-0.5, "-0.5")]
    if y_max >= 2.2:
        tick_candidates.insert(0, (2.0, "+2.0"))
    elif y_max >= 1.6:
        tick_candidates.insert(0, (1.5, "+1.5"))
    if y_min <= -2.2:
        tick_candidates.append((-2.0, "-2.0"))
    elif y_min <= -1.6:
        tick_candidates.append((-1.5, "-1.5"))

    for thresh, lbl in tick_candidates:
        if y_min <= thresh <= y_max:
            ty = _y(thresh)
            is_zero = abs(thresh) < 1e-6
            g.add(
                Line(
                    x0,
                    ty,
                    x1,
                    ty,
                    strokeColor=BLACK if is_zero else MID_GRAY,
                    strokeWidth=0.8 if is_zero else 0.5,
                    strokeDashArray=None if is_zero else [2, 2],
                )
            )
            g.add(
                String(
                    x0 - 2,
                    ty - 2,
                    lbl,
                    fontName="Helvetica",
                    fontSize=5.5,
                    textAnchor="end",
                    fillColor=BLACK,
                )
            )

    zero_y = _y(0.0)
    bar_w = max(2.0, (plot_w / n_pts) * 0.65)
    for i, p in enumerate(pts):
        bx = _x(i) - bar_w / 2.0
        by = _y(p.nino34_anomaly)
        bh = abs(by - zero_y)
        bottom = min(by, zero_y)
        fill_c = DARK_GRAY if p.nino34_anomaly >= 0 else SHADE_GRAY
        g.add(
            Rect(
                bx,
                bottom,
                bar_w,
                max(0.8, bh),
                strokeColor=BLACK,
                fillColor=fill_c,
                strokeWidth=0.4,
            )
        )

    for idx_val in (0, n_pts // 2, n_pts - 1):
        tx = _x(idx_val)
        g.add(
            String(
                tx,
                y0 - 9,
                pts[idx_val].period,
                fontName="Helvetica",
                fontSize=5.3,
                textAnchor="middle",
                fillColor=BLACK,
            )
        )

    rx = x1 + 6.0
    rw = width - rx - 2.0
    g.add(Rect(rx, y0, rw, plot_h, strokeColor=BLACK, fillColor=SHADE_LIGHT, strokeWidth=0.6))
    readout = [
        ("State:", enso.enso_state_label if enso else "N/A"),
        ("Period:", (enso.latest_period or "N/A") if enso else "N/A"),
        (
            "Nino3.4:",
            f"{enso.latest_nino34:+.2f} C" if (enso and enso.latest_nino34 is not None) else "N/A",
        ),
        (
            "ONI:",
            f"{enso.latest_oni:+.2f} C" if (enso and enso.latest_oni is not None) else "N/A",
        ),
        (
            "RONI:",
            f"{enso.latest_roni:+.2f} C" if (enso and enso.latest_roni is not None) else "N/A",
        ),
        (
            "MEI.v2:",
            f"{enso.latest_meiv2:+.2f}" if (enso and enso.latest_meiv2 is not None) else "N/A",
        ),
    ]
    ty = y0 + plot_h - 11.5
    for k_lbl, v_lbl in readout:
        g.add(String(rx + 3, ty, k_lbl, fontName="Helvetica-Bold", fontSize=6.6, fillColor=DARK_GRAY))
        g.add(String(rx + 36, ty, v_lbl[:15], fontName="Helvetica", fontSize=6.6, fillColor=BLACK))
        ty -= 12.8

    d.add(g)
    return d


# ---------------------------------------------------------------------------
# Chart 5: Local Sea-Level Pressure History (hPa)
# ---------------------------------------------------------------------------

def build_local_pressure_chart(
    loc: LocalLocationBundle,
    width: float = 258.0,
    height: float = 156.0,
) -> Drawing:
    """Build 7-day sea-level pressure chart (hPa) for a configured location."""
    d = Drawing(width, height)
    g = Group()

    stn_lbl = f" — {loc.station_id}" if loc.station_id else ""
    g.add(
        String(
            4,
            height - 10,
            f"CHART 5: BAROMETRIC PRESSURE (hPa){stn_lbl}",
            fontName="Helvetica-Bold",
            fontSize=7.8,
            fillColor=BLACK,
        )
    )

    pad_l, pad_r, pad_t, pad_b = 34.0, 10.0, 26.0, 20.0
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    x0, y0 = pad_l, pad_b
    x1, y1 = x0 + plot_w, y0 + plot_h

    pts = loc.pressure_series
    if len(pts) < 2:
        g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=MID_GRAY, fillColor=SHADE_LIGHT))
        g.add(
            String(
                x0 + plot_w / 2,
                y0 + plot_h / 2,
                "Station pressure time series unavailable",
                fontName="Helvetica-Oblique",
                fontSize=7,
                textAnchor="middle",
                fillColor=MID_GRAY,
            )
        )
        d.add(g)
        return d

    vals = [p.pressure_hpa for p in pts] + [1013.25]
    y_min = math.floor((min(vals) - 2.0) / 5.0) * 5.0
    y_max = math.ceil((max(vals) + 2.0) / 5.0) * 5.0
    if y_max <= y_min:
        y_min, y_max = 1000.0, 1030.0
    n_pts = len(pts)

    def _x(idx: int) -> float:
        return x0 + (idx / max(1, n_pts - 1)) * plot_w

    def _y(val: float) -> float:
        clamped = max(y_min, min(y_max, val))
        return y0 + ((clamped - y_min) / (y_max - y_min)) * plot_h

    g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=BLACK, fillColor=WHITE, strokeWidth=0.6))

    if y_min <= 1013.25 <= y_max:
        std_y = _y(1013.25)
        g.add(
            Line(
                x0,
                std_y,
                x1,
                std_y,
                strokeColor=MID_GRAY,
                strokeWidth=0.7,
                strokeDashArray=[3, 2],
            )
        )
        g.add(
            String(
                x1 - 3,
                std_y + 2,
                "Std 1013.2 hPa",
                fontName="Helvetica-Oblique",
                fontSize=5.2,
                textAnchor="end",
                fillColor=MID_GRAY,
            )
        )

    step_y = 5.0 if (y_max - y_min) <= 25.0 else 10.0
    tk = y_min
    while tk <= y_max:
        ty = _y(tk)
        g.add(Line(x0, ty, x1, ty, strokeColor=GRID_GRAY, strokeWidth=0.4))
        g.add(
            String(
                x0 - 3,
                ty - 2,
                f"{tk:.0f}",
                fontName="Helvetica",
                fontSize=5.6,
                textAnchor="end",
                fillColor=BLACK,
            )
        )
        tk += step_y

    coords: List[float] = []
    for i, p in enumerate(pts):
        coords.extend([_x(i), _y(p.pressure_hpa)])
    g.add(PolyLine(coords, strokeColor=BLACK, strokeWidth=1.3))
    _draw_marker(g, "circle_filled", _x(n_pts - 1), _y(pts[-1].pressure_hpa), size=2.1)

    cur_s = f"Latest: {loc.current_pressure_hpa:.1f} hPa" if loc.current_pressure_hpa else ""
    chg_s = (
        f"24h Chg: {loc.pressure_change_24h_hpa:+.1f} hPa"
        if loc.pressure_change_24h_hpa is not None
        else ""
    )
    rng_s = (
        f"7d Range: {loc.pressure_min_7d_hpa:.1f}–{loc.pressure_max_7d_hpa:.1f} hPa"
        if (loc.pressure_min_7d_hpa is not None and loc.pressure_max_7d_hpa is not None)
        else ""
    )
    sub = " | ".join(s for s in (cur_s, chg_s, rng_s) if s)
    g.add(String(x0, height - 20, sub, fontName="Helvetica", fontSize=6.4, fillColor=DARK_GRAY))

    for idx_val in (0, n_pts // 2, n_pts - 1):
        tx = _x(idx_val)
        g.add(
            String(
                tx,
                y0 - 11,
                _short_date(pts[idx_val].timestamp[:10]),
                fontName="Helvetica",
                fontSize=6.5,
                textAnchor="middle",
                fillColor=BLACK,
            )
        )

    d.add(g)
    return d


# ---------------------------------------------------------------------------
# Chart 6: Local Temperature Anomaly (30d vs NCEI Normal) + 7d NWS Forecast
# ---------------------------------------------------------------------------

def build_local_temperature_chart(
    loc: LocalLocationBundle,
    width: float = 258.0,
    height: float = 156.0,
) -> Drawing:
    """Build split panel: 30d daily temp anomaly (°F vs 1991-2020 normal) + 7d NWS High/Low."""
    d = Drawing(width, height)
    g = Group()

    g.add(
        String(
            4,
            height - 10,
            "CHART 6: TEMP ANOMALY (30d) & 7d FORECAST",
            fontName="Helvetica-Bold",
            fontSize=7.8,
            fillColor=BLACK,
        )
    )

    pad_l, pad_r, pad_t, pad_b = 26.0, 24.0, 26.0, 20.0
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    x0, y0 = pad_l, pad_b
    x1, y1 = x0 + plot_w, y0 + plot_h

    split_x = x0 + plot_w * 0.60

    g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=BLACK, fillColor=WHITE, strokeWidth=0.6))
    g.add(Rect(split_x, y0, x1 - split_x, plot_h, strokeColor=BLACK, fillColor=SHADE_LIGHT, strokeWidth=0.6))

    clim_pts = [p for p in loc.climate_series[-30:] if p.temp_departure_f is not None]
    if clim_pts:
        deps = [float(p.temp_departure_f) for p in clim_pts if p.temp_departure_f is not None] + [-10.0, 10.0]
        d_min = min(-15.0, math.floor(min(deps) / 5.0) * 5.0 - 3.0)
        d_max = max(18.0, math.ceil(max(deps) / 5.0) * 5.0 + 6.0)
        n_c = len(clim_pts)
        left_w = split_x - x0 - 4.0

        def _cy(val: float) -> float:
            clamped = max(d_min, min(d_max, val))
            return y0 + ((clamped - d_min) / (d_max - d_min)) * plot_h

        zero_y = _cy(0.0)
        g.add(Line(x0, zero_y, split_x, zero_y, strokeColor=BLACK, strokeWidth=0.7))
        for tk in (-10.0, 0.0, 10.0):
            if d_min <= tk <= d_max:
                ty = _cy(tk)
                g.add(
                    String(
                        x0 - 2,
                        ty - 2,
                        f"{tk:+.0f}F" if tk != 0 else "0F",
                        fontName="Helvetica",
                        fontSize=5.2,
                        textAnchor="end",
                        fillColor=BLACK,
                    )
                )

        bw = max(1.5, (left_w / n_c) * 0.68)
        for i, p in enumerate(clim_pts):
            dep = float(p.temp_departure_f or 0.0)
            bx = x0 + 2.0 + (i + 0.5) * (left_w / n_c) - bw / 2.0
            by = _cy(dep)
            bh = abs(by - zero_y)
            g.add(
                Rect(
                    bx,
                    min(by, zero_y),
                    bw,
                    max(0.7, bh),
                    strokeColor=BLACK,
                    fillColor=DARK_GRAY if dep >= 0 else WHITE,
                    strokeWidth=0.4,
                )
            )
        g.add(
            String(
                x0 + 3,
                y1 - 7,
                "30d Departure vs Normal (°F)",
                fontName="Helvetica-Bold",
                fontSize=5.2,
                fillColor=DARK_GRAY,
            )
        )
        g.add(
            String(
                x0 + 4,
                y0 - 9,
                _short_date(clim_pts[0].date),
                fontName="Helvetica",
                fontSize=5.2,
                fillColor=BLACK,
            )
        )
        g.add(
            String(
                split_x - 4,
                y0 - 9,
                _short_date(clim_pts[-1].date),
                fontName="Helvetica",
                fontSize=5.2,
                textAnchor="end",
                fillColor=BLACK,
            )
        )

    fcsts = [
        f
        for f in loc.daily_forecasts[:7]
        if f.high_f is not None or f.low_f is not None
    ]
    if len(fcsts) >= 2:
        t_vals: List[float] = []
        for f in fcsts:
            if f.high_f is not None:
                t_vals.append(f.high_f)
            if f.low_f is not None:
                t_vals.append(f.low_f)
        f_min = math.floor((min(t_vals) - 5.0) / 10.0) * 10.0
        f_max = math.ceil((max(t_vals) + 12.0) / 10.0) * 10.0
        if f_max <= f_min:
            f_min, f_max = 20.0, 70.0
        right_w = x1 - split_x - 8.0
        n_f = len(fcsts)

        def _fx(idx: int) -> float:
            return split_x + 4.0 + (idx / max(1, n_f - 1)) * right_w

        def _fy(val: float) -> float:
            clamped = max(f_min, min(f_max, val))
            return y0 + ((clamped - f_min) / (f_max - f_min)) * plot_h

        for tk in (f_min, (f_min + f_max) / 2.0, f_max):
            ty = _fy(tk)
            g.add(
                String(
                    x1 + 2,
                    ty - 2,
                    f"{tk:.0f}F",
                    fontName="Helvetica",
                    fontSize=5.2,
                    textAnchor="start",
                    fillColor=BLACK,
                )
            )

        hi_coords: List[float] = []
        lo_coords: List[float] = []
        for i, f in enumerate(fcsts):
            if f.high_f is not None:
                hi_coords.extend([_fx(i), _fy(f.high_f)])
            if f.low_f is not None:
                lo_coords.extend([_fx(i), _fy(f.low_f)])

        if len(hi_coords) >= 4:
            g.add(PolyLine(hi_coords, strokeColor=BLACK, strokeWidth=1.2))
            for i in range(0, len(hi_coords), 2):
                _draw_marker(g, "circle_filled", hi_coords[i], hi_coords[i + 1], size=1.7)
        if len(lo_coords) >= 4:
            g.add(
                PolyLine(
                    lo_coords,
                    strokeColor=DARK_GRAY,
                    strokeWidth=1.0,
                    strokeDashArray=[3, 1.5],
                )
            )
            for i in range(0, len(lo_coords), 2):
                _draw_marker(g, "square_open", lo_coords[i], lo_coords[i + 1], size=1.6)

        g.add(
            String(
                split_x + 3,
                y1 - 7,
                "7d NWS Hi/Lo (°F)",
                fontName="Helvetica-Bold",
                fontSize=5.2,
                fillColor=DARK_GRAY,
            )
        )
        g.add(
            String(
                _fx(n_f - 1),
                y0 - 9,
                _short_date(fcsts[-1].date),
                fontName="Helvetica",
                fontSize=5.2,
                textAnchor="end",
                fillColor=BLACK,
            )
        )

    anom7 = (
        f"7d Temp Anom: {loc.temp_anomaly_7d_f:+.1f}°F"
        if loc.temp_anomaly_7d_f is not None
        else ""
    )
    anom14 = (
        f"14d Anom: {loc.temp_anomaly_14d_f:+.1f}°F"
        if loc.temp_anomaly_14d_f is not None
        else ""
    )
    pcp30 = (
        f"30d Precip: {loc.precip_30d_pct_normal:.0f}% of normal"
        if loc.precip_30d_pct_normal is not None
        else ""
    )
    sub = " | ".join(s for s in (anom7, anom14, pcp30) if s)
    g.add(String(x0, height - 20, sub, fontName="Helvetica", fontSize=6.4, fillColor=DARK_GRAY))

    d.add(g)
    return d


# ---------------------------------------------------------------------------
# Chart 7: Snow Watch (Depth & Daily Snowfall for Active Snow Locations)
# ---------------------------------------------------------------------------

def build_snow_watch_chart(
    snow: SnowLocationBundle,
    width: float = 530.0,
    height: float = 135.0,
) -> Drawing:
    """Build snow depth profile & daily snowfall bar chart for snowy locations."""
    d = Drawing(width, height)
    g = Group()

    stn_lbl = f" ({snow.station_name or snow.station_id})" if (snow.station_name or snow.station_id) else ""
    g.add(
        String(
            4,
            height - 10,
            f"CHART 7: SNOW DEPTH & DAILY SNOWFALL (INCHES){stn_lbl[:45]}",
            fontName="Helvetica-Bold",
            fontSize=7.8,
            fillColor=BLACK,
        )
    )

    pad_l, pad_r, pad_t, pad_b = 28.0, 12.0, 26.0, 20.0
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    x0, y0 = pad_l, pad_b
    x1, y1 = x0 + plot_w, y0 + plot_h

    pts = snow.daily_series[-35:] if snow.daily_series else []
    if len(pts) < 2:
        g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=MID_GRAY, fillColor=SHADE_LIGHT))
        d.add(g)
        return d

    max_v = max(
        [2.0]
        + [float(p.snow_depth_in or 0.0) for p in pts]
        + [float(p.snowfall_in or 0.0) for p in pts]
    )
    y_max = math.ceil(max_v * 1.2)
    n_pts = len(pts)

    def _x(idx: int) -> float:
        return x0 + (idx / max(1, n_pts - 1)) * plot_w

    def _y(val: float) -> float:
        clamped = max(0.0, min(y_max, val))
        return y0 + (clamped / y_max) * plot_h

    g.add(Rect(x0, y0, plot_w, plot_h, strokeColor=BLACK, fillColor=WHITE, strokeWidth=0.6))

    depth_pts = [(i, float(p.snow_depth_in or 0.0)) for i, p in enumerate(pts) if p.snow_depth_in is not None]
    if len(depth_pts) >= 2:
        poly: List[float] = [_x(depth_pts[0][0]), y0]
        line_c: List[float] = []
        for idx_val, dv in depth_pts:
            poly.extend([_x(idx_val), _y(dv)])
            line_c.extend([_x(idx_val), _y(dv)])
        poly.extend([_x(depth_pts[-1][0]), y0])
        g.add(Polygon(poly, strokeColor=None, fillColor=SHADE_GRAY))
        g.add(PolyLine(line_c, strokeColor=BLACK, strokeWidth=1.4))

    bw = max(1.8, (plot_w / n_pts) * 0.55)
    for i, p in enumerate(pts):
        sf = float(p.snowfall_in or 0.0)
        if sf > 0:
            bx = _x(i) - bw / 2.0
            bh = _y(sf) - y0
            g.add(Rect(bx, y0, bw, max(1.0, bh), strokeColor=BLACK, fillColor=BLACK, strokeWidth=0.3))

    for tk in (0.0, y_max / 2.0, y_max):
        ty = _y(tk)
        g.add(
            String(
                x0 - 3,
                ty - 2,
                f"{tk:.0f}\"",
                fontName="Helvetica",
                fontSize=5.5,
                textAnchor="end",
                fillColor=BLACK,
            )
        )

    sub_parts = [
        f"Current Depth: {snow.current_depth_in:.1f}\"" if snow.current_depth_in is not None else "",
        f"7d Snowfall: {snow.snowfall_7d_in:.1f}\"" if snow.snowfall_7d_in is not None else "",
        f"7d NWS Fcst Snow: {snow.forecast_snow_7d_in:.1f}\"" if snow.forecast_snow_7d_in is not None else "",
    ]
    g.add(
        String(
            x0,
            height - 18,
            " | ".join(s for s in sub_parts if s),
            fontName="Helvetica",
            fontSize=5.4,
            fillColor=DARK_GRAY,
        )
    )

    for idx_val in (0, n_pts // 2, n_pts - 1):
        g.add(
            String(
                _x(idx_val),
                y0 - 9,
                _short_date(pts[idx_val].date),
                fontName="Helvetica",
                fontSize=5.4,
                textAnchor="middle",
                fillColor=BLACK,
            )
        )

    d.add(g)
    return d
