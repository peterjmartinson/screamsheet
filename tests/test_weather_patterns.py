"""Unit tests for the Weather Patterns & Teleconnections screamsheet.

All tests use saved in-memory fixtures and make zero live network calls.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from reportlab.graphics.shapes import Drawing

from screamsheet.config import load_config
from screamsheet.db.weather_cache_db import weather_cache_fetch
from screamsheet.db.weather_patterns_db import (
    WEATHER_PATTERNS_SCHEMA_VERSION,
    compute_teleconnection_verification_stats,
    find_historical_teleconnection_analogs,
    get_forecast_vintages_for_metric,
    get_local_pressure_history,
    get_stratosphere_obs_history,
    get_teleconnection_obs_history,
    get_weather_schema_version,
    init_weather_patterns_db,
    persist_weather_patterns_bundle,
    save_stratosphere_forecast_vintage,
    save_teleconnection_forecast_vintage,
    save_teleconnection_observations,
)
from screamsheet.factory import ScreamsheetFactory
from screamsheet.llm.summarizers import WeatherPatternsSummarizer
from screamsheet.providers import (
    ClimateHistoryProvider,
    ENSOProvider,
    MJOProvider,
    NWSWeatherPatternsProvider,
    SnowProvider,
    StratosphereProvider,
    TeleconnectionProvider,
)
from screamsheet.providers.enso_provider import classify_enso_state
from screamsheet.weather_patterns import (
    DailyForecastSummary,
    ENSOBundle,
    ENSOMonthlyPoint,
    HourlyPressurePoint,
    LocalLocationBundle,
    MJOBundle,
    SnowDailyPoint,
    SourceProvenance,
    StratosphereBundle,
    StratosphereDailyPoint,
    TeleconnectionDailyObs,
    TeleconnectionForecastDay,
    TeleconnectionIndexBundle,
    WeatherPatternsDataBundle,
    WeatherPatternsScreamsheet,
    build_enso_sparkline,
    build_forecast_evolution_chart,
    build_local_pressure_chart,
    build_local_temperature_chart,
    build_mjo_phase_diagram,
    build_polar_vortex_chart,
    build_snow_watch_chart,
    build_teleconnections_chart,
    compute_derived_signals,
)


# ---------------------------------------------------------------------------
# Saved Raw Text / JSON Fixtures
# ---------------------------------------------------------------------------

CDAS_AO_CSV_FIXTURE = """year,month,day,ao_index_cdas
2026,10,20,0.450
2026,10,27,-0.120
2026,10,28,-0.350
2026,10,29,-0.620
2026,10,30,-0.880
2026,10,31,-1.050
2026,11,01,-1.180
2026,11,02,-1.250
2026,11,03,-1.640
"""

GEFS_AO_CSV_FIXTURE = """lead,member,time,ao_index,valid_time
0,0,2026-11-03,-1.60,2026-11-03
0,1,2026-11-03,-1.68,2026-11-03
1,0,2026-11-03,-1.40,2026-11-04
1,1,2026-11-03,-1.60,2026-11-04
1,2,2026-11-03,-1.20,2026-11-04
1,3,2026-11-03,-1.80,2026-11-04
7,0,2026-11-03,-1.95,2026-11-10
7,1,2026-11-03,-2.35,2026-11-10
7,2,2026-11-03,-1.55,2026-11-10
7,3,2026-11-03,-2.15,2026-11-10
"""

ROMI_MJO_TEXT_FIXTURE = """2026 10 25 00   0.35000  -0.42000   0.54672
2026 10 27 00   0.62000  -0.55000   0.82879
2026 10 30 00   0.95000  -0.82000   1.25495
2026 11 01 00   1.12000  -0.95000   1.46864
2026 11 02 00   1.28000  -0.65000   1.43558
2026 11 03 00   1.35000  -0.40000   1.40801
"""

NINO34_ASCII_FIXTURE = """ YR   MON  TOTAL   ClimAdjust   ANOM
2026    8  26.42      26.86    -0.44
2026    9  26.15      26.75    -0.60
2026   10  25.98      26.68    -0.70
"""

ONI_ASCII_FIXTURE = """ SEAS  YR   TOTAL   ANOM
 JJA 2026   26.55  -0.45
 JAS 2026   26.28  -0.58
 ASO 2026   26.05  -0.66
"""

MEI_V2_TEXT_FIXTURE = """1979 2026
2025  -0.65 -0.58 -0.49 -0.41 -0.35 -0.38 -0.44 -0.52 -0.61 -0.68 -0.72 -0.75
2026  -0.70 -0.62 -0.55 -0.48 -0.50 -0.56 -0.63 -0.71 -0.79 -0.84 -999.00 -999.00
-999.00
"""

GSFC_STRAT_ASCII_FIXTURE = """Date            T           U
2026-10-26   212.50       29.40
2026-10-27   213.10       28.20
2026-10-28   213.50       26.80
2026-10-29   214.00       24.50
2026-10-30   214.80       22.10
2026-10-31   215.20       19.40
2026-11-01   215.90       17.00
2026-11-02   216.40       15.20
2026-11-03   217.90       11.80
2026-11-06   221.00        4.50
2026-11-09   224.20       -1.40
"""

ACIS_CLIMATE_JSON_FIXTURE = {
    "meta": {"name": "PHILADELPHIA INTL AP"},
    "data": [
        [f"2026-10-{d:02d}", "66", "46", "56.0", "53.0", "+3.0", "0.05", "0.10"]
        for d in range(5, 32)
    ]
    + [
        ["2026-11-01", "62", "42", "52.0", "52.4", "-0.4", "0.00", "0.10"],
        ["2026-11-02", "65", "45", "55.0", "52.0", "+3.0", "0.05", "0.10"],
        ["2026-11-03", "67", "47", "57.0", "51.5", "+5.5", "0.00", "0.10"],
    ],
}

ACIS_SNOW_JSON_MANSFIELD_FIXTURE = {
    "meta": {"name": "MOUNT MANSFIELD", "elev": 3950},
    "data": [
        ["2026-10-28", "0.0", "0"],
        ["2026-10-29", "1.5", "1"],
        ["2026-10-30", "3.2", "4"],
        ["2026-10-31", "0.0", "3"],
        ["2026-11-01", "0.5", "4"],
        ["2026-11-02", "2.0", "6"],
        ["2026-11-03", "1.0", "7"],
    ],
}


# ---------------------------------------------------------------------------
# Provider Parser Unit Tests
# ---------------------------------------------------------------------------

def test_teleconnection_provider_parsers():
    obs = TeleconnectionProvider.parse_cdas_csv(
        CDAS_AO_CSV_FIXTURE, target_date=datetime(2026, 11, 3), history_days=60
    )
    assert len(obs) == 9
    assert obs[-1].date == "2026-11-03"
    assert obs[-1].value == pytest.approx(-1.64)

    fcst = TeleconnectionProvider.parse_gefs_csv(
        GEFS_AO_CSV_FIXTURE, target_date=datetime(2026, 11, 3), forecast_days=14
    )
    assert len(fcst) == 2
    assert fcst[0].init_date == "2026-11-03"
    assert fcst[0].valid_date == "2026-11-04"
    assert fcst[0].ensemble_mean == pytest.approx(-1.50)
    assert fcst[0].ensemble_min == pytest.approx(-1.80)
    assert fcst[0].ensemble_max == pytest.approx(-1.20)
    assert fcst[1].valid_date == "2026-11-10"
    assert fcst[1].ensemble_mean == pytest.approx(-2.00)


def test_mjo_provider_romi_parser_and_phases():
    pts = MJOProvider.parse_romi_text(ROMI_MJO_TEXT_FIXTURE)
    assert len(pts) == 6
    first = pts[0]
    assert first.date == "2026-10-25"
    assert first.active is False  # amplitude 0.55 < 1.0

    latest = pts[-1]
    assert latest.date == "2026-11-03"
    assert latest.active is True  # amplitude 1.41 >= 1.0
    # PC1 = +1.35, PC2 = -0.40 -> comp1 = -0.40, comp2 = -1.35 (Phase 2)
    assert latest.component_1 == pytest.approx(-0.40)
    assert latest.component_2 == pytest.approx(-1.35)
    assert latest.phase == 2


def test_enso_provider_parsers():
    nino_pts = ENSOProvider.parse_nino34_ascii(NINO34_ASCII_FIXTURE)
    assert len(nino_pts) == 3
    assert nino_pts[-1].period == "2026-10"
    assert nino_pts[-1].nino34_anomaly == pytest.approx(-0.70)

    oni_rows = ENSOProvider.parse_oni_ascii(ONI_ASCII_FIXTURE)
    assert oni_rows[-1] == ("ASO", 2026, -0.66)

    mei_rows = ENSOProvider.parse_meiv2_data(MEI_V2_TEXT_FIXTURE)
    assert mei_rows[-1][2] == pytest.approx(-0.84)

    assert "La Niña" in classify_enso_state(-0.70, -0.66)
    assert "El Niño" in classify_enso_state(0.80, 0.75)
    assert "Neutral" in classify_enso_state(0.15, 0.10)


def test_stratosphere_provider_and_wmo_ssw_criteria():
    obs, fcst = StratosphereProvider.parse_gsfc_ascii(
        GSFC_STRAT_ASCII_FIXTURE, target_date=datetime(2026, 11, 3)
    )
    assert len(obs) == 9
    assert len(fcst) == 2
    assert obs[-1].date == "2026-11-03"
    assert obs[-1].zonal_wind_10hpa_60n == pytest.approx(11.8)
    assert fcst[-1].zonal_wind_10hpa_60n == pytest.approx(-1.4)

    strat_bundle = StratosphereBundle(observations=obs, forecasts=fcst)
    sig = compute_derived_signals({}, strat_bundle, None, None, [])
    # Forecast drops to -1.40 m/s on 2026-11-09: forecast_reversal is True, observed_reversal is False
    assert sig.flags["polar_vortex_reversal_forecast"] is True
    assert sig.flags["polar_vortex_reversal_observed"] is False
    # CRITICAL RULE: forecast crossing zero alone must NOT set major_ssw_criteria_met!
    assert sig.flags["major_ssw_criteria_met"] is False

    # Now test a true observed winter wind reversal accompanied by >=8 K polar cap warming over 7 days
    ssw_obs = [
        StratosphereDailyPoint(f"2026-01-{d:02d}", 22.0 - d * 2.0, 205.0, is_forecast=False)
        for d in range(1, 9)
    ] + [
        StratosphereDailyPoint("2026-01-09", -2.5, 219.0, is_forecast=False),
        StratosphereDailyPoint("2026-01-10", -5.0, 224.0, is_forecast=False),
    ]
    ssw_sig = compute_derived_signals({}, StratosphereBundle(observations=ssw_obs), None, None, [])
    assert ssw_sig.flags["polar_vortex_reversal_observed"] is True
    assert ssw_sig.flags["major_ssw_criteria_met"] is True


def test_climate_history_provider_anomalies():
    stn_name, pts = ClimateHistoryProvider.parse_acis_stndata(ACIS_CLIMATE_JSON_FIXTURE)
    assert stn_name == "PHILADELPHIA INTL AP"
    assert len(pts) == 30
    anoms = ClimateHistoryProvider.compute_anomalies(pts)
    assert anoms["temp_anomaly_7d_f"] is not None
    assert anoms["precip_30d_pct_normal"] is not None
    assert anoms["precip_30d_pct_normal"] == pytest.approx(46.0, abs=2.0)


def test_snow_provider_graceful_omission_and_active_detection():
    stn, elev, pts = SnowProvider.parse_acis_snow_data(ACIS_SNOW_JSON_MANSFIELD_FIXTURE)
    assert stn == "MOUNT MANSFIELD"
    assert elev == pytest.approx(3950.0)

    active_bundle = SnowProvider.build_snow_bundle(
        station_id="USC00435416",
        station_name=stn,
        elevation_ft=elev,
        points=pts,
        forecast_snow_7d_in=4.5,
    )
    assert active_bundle.has_useful_snow_data is True
    assert active_bundle.current_depth_in == pytest.approx(7.0)
    assert active_bundle.snowfall_7d_in == pytest.approx(8.2)

    zero_pts = [
        SnowDailyPoint("2026-11-01", 0.0, 0.0),
        SnowDailyPoint("2026-11-02", 0.0, 0.0),
        SnowDailyPoint("2026-11-03", 0.0, 0.0),
    ]
    empty_bundle = SnowProvider.build_snow_bundle(
        station_id="KPHL",
        station_name="PHILADELPHIA INTL AP",
        elevation_ft=10.0,
        points=zero_pts,
        forecast_snow_7d_in=0.0,
    )
    assert empty_bundle.has_useful_snow_data is False


def test_nws_provider_parsers():
    features = [
        {
            "properties": {
                "timestamp": "2026-11-03T12:00:00+00:00",
                "temperature": {"value": 15.0},
                "dewpoint": {"value": 5.0},
                "windSpeed": {"value": 14.0},
                "windDirection": {"value": 270.0},
                "seaLevelPressure": {"value": 102650.0},
                "textDescription": "Clear",
            }
        },
        {
            "properties": {
                "timestamp": "2026-11-02T12:00:00+00:00",
                "temperature": {"value": 12.0},
                "dewpoint": {"value": 4.0},
                "windSpeed": {"value": 18.0},
                "windDirection": {"value": 315.0},
                "seaLevelPressure": {"value": 102000.0},
                "textDescription": "Mostly Sunny",
            }
        },
    ]
    summary, p_hist = NWSWeatherPatternsProvider.parse_observations_features(features)
    assert summary["temp_f"] == pytest.approx(59.0)
    assert summary["pressure_hpa"] == pytest.approx(1026.5)
    assert len(p_hist) == 2

    afd_text = """000
FXUS61 KPHI 031200
AFDPHI
.SYNOPSIS...
High pressure centered over New England will maintain dry and seasonable weather through Thursday. A cold front approaches Friday.
&&
.NEAR TERM /THROUGH TONIGHT/...
Clear skies tonight.
"""
    syn = NWSWeatherPatternsProvider.extract_afd_synopsis(afd_text)
    assert "High pressure centered over New England" in syn


# ---------------------------------------------------------------------------
# Derived Signals, LLM Packet, Charts, and Full PDF / Markdown Generation
# ---------------------------------------------------------------------------

def _make_sample_bundle() -> WeatherPatternsDataBundle:
    ao_obs = TeleconnectionProvider.parse_cdas_csv(
        CDAS_AO_CSV_FIXTURE, target_date=datetime(2026, 11, 3)
    )
    ao_fcst = TeleconnectionProvider.parse_gefs_csv(
        GEFS_AO_CSV_FIXTURE, target_date=datetime(2026, 11, 3)
    )
    ao_bundle = TeleconnectionIndexBundle(
        index_name="AO",
        level_label="1000 hPa",
        observations=ao_obs,
        forecasts=ao_fcst,
        obs_provenance=SourceProvenance(
            "NOAA CPC",
            "AO CDAS",
            "https://ftp.cpc.ncep.noaa.gov/cwlinks/",
            "2026-11-04T07:00:00Z",
            valid_through="2026-11-03",
        ),
    )
    nao_bundle = TeleconnectionIndexBundle(
        index_name="NAO",
        level_label="500 hPa",
        observations=[
            TeleconnectionDailyObs(f"2026-10-{d:02d}", 0.20) for d in range(25, 32)
        ] + [
            TeleconnectionDailyObs("2026-11-01", -0.80),
            TeleconnectionDailyObs("2026-11-02", -1.20),
            TeleconnectionDailyObs("2026-11-03", -1.55),
        ],
        forecasts=[
            TeleconnectionForecastDay("2026-11-04", 1, "2026-11-03", -1.55, -1.90, -1.10, -1.70, -1.35, 0.25, 31),
            TeleconnectionForecastDay("2026-11-10", 7, "2026-11-03", -1.65, -2.20, -1.10, -1.90, -1.40, 0.40, 31),
        ],
    )
    pna_bundle = TeleconnectionIndexBundle(
        index_name="PNA",
        level_label="500 hPa",
        observations=[
            TeleconnectionDailyObs(f"2026-10-{d:02d}", 0.40) for d in range(25, 32)
        ] + [
            TeleconnectionDailyObs("2026-11-01", 1.10),
            TeleconnectionDailyObs("2026-11-02", 1.35),
            TeleconnectionDailyObs("2026-11-03", 1.60),
        ],
        forecasts=[
            TeleconnectionForecastDay("2026-11-04", 1, "2026-11-03", 1.65, 1.30, 1.95, 1.50, 1.80, 0.20, 31),
            TeleconnectionForecastDay("2026-11-10", 7, "2026-11-03", 1.75, 1.20, 2.20, 1.55, 1.95, 0.35, 31),
        ],
    )

    mjo_pts = MJOProvider.parse_romi_text(ROMI_MJO_TEXT_FIXTURE)
    mjo_bundle = MJOBundle(history=mjo_pts)

    enso_pts = [
        ENSOMonthlyPoint("2026-08", -0.44, 26.42, -0.45, -0.50, -0.71),
        ENSOMonthlyPoint("2026-09", -0.60, 26.15, -0.58, -0.62, -0.79),
        ENSOMonthlyPoint("2026-10", -0.70, 25.98, -0.66, -0.70, -0.84),
    ]
    enso_bundle = ENSOBundle(
        nino34_series=enso_pts,
        latest_period="2026-10",
        latest_nino34=-0.70,
        latest_oni=-0.66,
        latest_oni_season="ASO 2026",
        latest_roni=-0.70,
        latest_meiv2=-0.84,
        enso_state_label="Weak La Niña / La Niña Advisory",
    )

    strat_obs, strat_fcst = StratosphereProvider.parse_gsfc_ascii(
        GSFC_STRAT_ASCII_FIXTURE, target_date=datetime(2026, 11, 3)
    )
    strat_bundle = StratosphereBundle(observations=strat_obs, forecasts=strat_fcst)

    _, clim_pts = ClimateHistoryProvider.parse_acis_stndata(ACIS_CLIMATE_JSON_FIXTURE)
    phl_loc = LocalLocationBundle(
        name="Philadelphia",
        lat=39.9526,
        lon=-75.1652,
        station_id="KPHL",
        station_name="Philadelphia Intl AP",
        grid_id="PHI",
        current_temp_f=58.0,
        current_dewpoint_f=41.0,
        current_pressure_hpa=1027.4,
        current_wind_mph=9.0,
        current_conditions="Mostly Clear",
        pressure_series=[
            HourlyPressurePoint("2026-11-01T12:00:00Z", 1022.5),
            HourlyPressurePoint("2026-11-02T12:00:00Z", 1025.8),
            HourlyPressurePoint("2026-11-03T12:00:00Z", 1027.4),
        ],
        pressure_min_7d_hpa=1022.5,
        pressure_max_7d_hpa=1027.4,
        pressure_mean_7d_hpa=1025.2,
        pressure_change_24h_hpa=1.6,
        daily_forecasts=[
            DailyForecastSummary("2026-11-04", "Wed", 64.0, 44.0, 10, 0.0, 0.0, "Sunny", "NW 8 mph"),
            DailyForecastSummary("2026-11-05", "Thu", 66.0, 46.0, 20, 0.05, 0.0, "Partly Sunny", "SW 10 mph"),
        ],
        afd_synopsis="High pressure remains anchored over the Mid-Atlantic.",
        climate_series=clim_pts,
        temp_anomaly_7d_f=3.2,
        temp_anomaly_14d_f=2.8,
        precip_30d_in=1.40,
        precip_30d_normal_in=2.80,
        precip_30d_pct_normal=50.0,
        snow=SnowProvider.build_snow_bundle(
            "KPHL", "PHILADELPHIA", 10.0,
            [SnowDailyPoint("2026-11-03", 0.0, 0.0)], 0.0,
        ),
    )

    _, elev, snow_pts = SnowProvider.parse_acis_snow_data(ACIS_SNOW_JSON_MANSFIELD_FIXTURE)
    stowe_loc = LocalLocationBundle(
        name="Stowe, VT",
        lat=44.4654,
        lon=-72.6874,
        station_id="KMVL",
        station_name="Morrisville-Stowe State Airport",
        grid_id="BTV",
        current_temp_f=34.0,
        current_dewpoint_f=26.0,
        current_pressure_hpa=1024.0,
        current_wind_mph=12.0,
        current_conditions="Light Snow Showers",
        pressure_series=[
            HourlyPressurePoint("2026-11-02T12:00:00Z", 1018.0),
            HourlyPressurePoint("2026-11-03T12:00:00Z", 1024.0),
        ],
        pressure_min_7d_hpa=1018.0,
        pressure_max_7d_hpa=1024.0,
        pressure_mean_7d_hpa=1021.0,
        pressure_change_24h_hpa=6.0,
        daily_forecasts=[
            DailyForecastSummary("2026-11-04", "Wed", 38.0, 24.0, 60, 0.35, 3.2, "Snow Showers", "NW 15 mph"),
            DailyForecastSummary("2026-11-05", "Thu", 41.0, 27.0, 30, 0.10, 1.0, "Mostly Cloudy", "W 10 mph"),
        ],
        climate_series=clim_pts,
        temp_anomaly_7d_f=-2.4,
        temp_anomaly_14d_f=-1.1,
        precip_30d_in=3.60,
        precip_30d_normal_in=3.40,
        precip_30d_pct_normal=105.9,
        snow=SnowProvider.build_snow_bundle(
            "USC00435416", "MOUNT MANSFIELD", elev, snow_pts, 4.2
        ),
    )

    tele = {"AO": ao_bundle, "NAO": nao_bundle, "PNA": pna_bundle}
    locs = [phl_loc, stowe_loc]
    derived = compute_derived_signals(tele, strat_bundle, mjo_bundle, enso_bundle, locs)

    return WeatherPatternsDataBundle(
        report_date="2026-11-04",
        teleconnections=tele,
        stratosphere=strat_bundle,
        mjo=mjo_bundle,
        enso=enso_bundle,
        locations=locs,
        derived=derived,
        provenance_list=[ao_bundle.obs_provenance] if ao_bundle.obs_provenance else [],
    )


def test_derived_signals_and_llm_packet():
    bundle = _make_sample_bundle()
    sig = bundle.derived
    assert sig.ao["change_7d"] == pytest.approx(-1.52)
    assert sig.flags["ao_strongly_negative"] is True
    assert sig.flags["nao_strongly_negative"] is True
    assert sig.flags["pna_strongly_positive"] is True
    assert sig.flags["mjo_active"] is True
    assert sig.flags["polar_vortex_rapidly_weakening"] is True
    assert sig.flags["polar_vortex_reversal_forecast"] is True
    assert sig.flags["major_ssw_criteria_met"] is False
    assert sig.flags["pressure_persistently_high"] is True
    assert sig.flags["major_pattern_change"] is True

    packet = bundle.to_llm_packet()
    assert packet["OBSERVATIONS"]["teleconnections"]["AO"]["latest_value_sd"] == pytest.approx(-1.64)
    assert packet["DERIVED_CHANGES"]["flags"]["major_ssw_criteria_met"] is False
    # Philadelphia has no useful snow data -> 'snow_observations' key omitted
    assert "snow_observations" not in packet["LOCAL_WEATHER"][0]
    # Stowe has useful snow data -> 'snow_observations' key included
    assert "snow_observations" in packet["LOCAL_WEATHER"][1]
    assert packet["LOCAL_WEATHER"][1]["snow_observations"]["current_snow_depth_in"] == pytest.approx(7.0)

    summarizer = WeatherPatternsSummarizer()
    prompt = summarizer._build_llm_prompt(
        {"weather_packet_json": "{}", "max_words": 200}
    )
    assert "PATTERN:" in prompt
    assert "WHAT CHANGED:" not in prompt
    assert "WHAT IT MAY MEAN:" not in prompt
    assert "LOCAL WATCH:" in prompt
    assert "100–200 words" in prompt


def test_charts_and_screamsheet_pdf_generation(tmp_path: Path):
    bundle = _make_sample_bundle()

    assert isinstance(build_teleconnections_chart(bundle.teleconnections), Drawing)
    assert isinstance(build_polar_vortex_chart(bundle.stratosphere), Drawing)
    assert isinstance(build_mjo_phase_diagram(bundle.mjo), Drawing)
    assert isinstance(build_enso_sparkline(bundle.enso), Drawing)
    assert isinstance(build_local_pressure_chart(bundle.locations[0]), Drawing)
    assert isinstance(build_local_temperature_chart(bundle.locations[0]), Drawing)
    assert isinstance(build_snow_watch_chart(bundle.locations[1].snow), Drawing)

    pdf_path = tmp_path / "weather_patterns_test.pdf"
    sheet = WeatherPatternsScreamsheet(
        output_filename=str(pdf_path),
        target_date=datetime(2026, 11, 4),
        data_bundle=bundle,
        gemini_api_key="",
        grok_api_key="",
        use_cache=False,
    )
    generated = sheet.generate_pdf(pdf_path)
    assert generated.exists()
    assert generated.stat().st_size > 2000

    md = sheet.render_markdown()
    assert "Climate Teleconnections" in md
    assert "PATTERN:" in md
    assert "WHAT CHANGED:" not in md
    assert "WHAT IT MAY MEAN:" not in md
    assert "MOUNT MANSFIELD" in md


def test_config_and_factory_and_runner_integration(tmp_path: Path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        """
weather_patterns:
  locations:
    - name: "Philadelphia"
      lat: 39.9526
      lon: -75.1652
      station: "KPHL"
    - name: "Stowe, VT"
      lat: 44.4654
      lon: -72.6874
  history_days: 45
  forecast_days: 10
  charts:
    snow: false
  narrative:
    enabled: false
    max_words: 180
""",
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert len(cfg.weather_patterns.locations) == 2
    assert cfg.weather_patterns.locations[0].station == "KPHL"
    assert cfg.weather_patterns.locations[1].station is None
    assert cfg.weather_patterns.history_days == 45
    assert cfg.weather_patterns.charts.snow is False
    assert cfg.weather_patterns.narrative.enabled is False
    assert cfg.weather_patterns.narrative.max_words == 180

    sheet = ScreamsheetFactory.create_weather_patterns_screamsheet(
        output_filename=str(tmp_path / "factory_wp.pdf"),
        weather_patterns_config=cfg.weather_patterns,
        date=datetime(2026, 11, 4),
    )
    assert isinstance(sheet, WeatherPatternsScreamsheet)


def test_weather_cache_db_stale_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "test_cache.db"
    monkeypatch.setenv("SCREAMSHEET_DB", str(db_file))

    def _good_fetcher() -> str:
        return "cached-payload-v1"

    res1 = weather_cache_fetch(
        cache_key="test:key:1",
        source_name="TestSource",
        fresh_ttl_seconds=-10,
        stale_ttl_seconds=3600,
        fetcher=_good_fetcher,
        use_cache=True,
    )
    assert res1.payload == "cached-payload-v1"
    assert res1.is_stale is False

    def _failing_fetcher() -> str:
        raise RuntimeError("Simulated NOAA network outage")

    res2 = weather_cache_fetch(
        cache_key="test:key:1",
        source_name="TestSource",
        fresh_ttl_seconds=3600,
        stale_ttl_seconds=3600,
        fetcher=_failing_fetcher,
        use_cache=True,
    )
    assert res2.payload == "cached-payload-v1"
    assert res2.is_stale is True
    assert "Simulated NOAA network outage" in (res2.error or "")


# ---------------------------------------------------------------------------
# V2 Institutional Memory Database, Forecast Vintages, Evolution & Verification Tests
# ---------------------------------------------------------------------------

def test_v2_schema_init_and_idempotent_observation_ingestion(tmp_path: Path):
    db_file = tmp_path / "wp_v2.db"
    init_weather_patterns_db(db_file)
    assert get_weather_schema_version(db_file) == WEATHER_PATTERNS_SCHEMA_VERSION

    bundle = _make_sample_bundle()
    counts1 = persist_weather_patterns_bundle(bundle, db_path=db_file)
    assert counts1["teleconnection_obs"] > 0
    assert counts1["stratosphere_obs"] > 0
    assert counts1["mjo_obs"] > 0
    assert counts1["enso_obs"] > 0
    assert counts1["local_obs"] > 0
    assert counts1["teleconnection_forecasts"] > 0

    # Re-running with identical data must be idempotent (0 new/modified rows)
    counts2 = persist_weather_patterns_bundle(bundle, db_path=db_file)
    assert counts2["teleconnection_obs"] == 0
    assert counts2["stratosphere_obs"] == 0
    assert counts2["mjo_obs"] == 0
    assert counts2["enso_obs"] == 0
    assert counts2["local_obs"] == 0
    assert counts2["teleconnection_forecasts"] == 0

    # Verify stored observations can be queried back
    ao_hist = get_teleconnection_obs_history("AO", db_path=db_file)
    assert len(ao_hist) == 9
    assert ao_hist[-1].value == pytest.approx(-1.64)

    strat_hist = get_stratosphere_obs_history(db_path=db_file)
    assert len(strat_hist) == 9
    assert strat_hist[-1].zonal_wind_10hpa_60n == pytest.approx(11.8)

    phl_press = get_local_pressure_history("Philadelphia", "KPHL", db_path=db_file)
    assert len(phl_press) == 3
    assert phl_press[-1].pressure_hpa == pytest.approx(1027.4)


def test_v2_forecast_vintage_preservation_and_evolution_signals(tmp_path: Path):
    """Verify successive model runs targeting the same valid date are preserved and evolution is calculated."""
    db_file = tmp_path / "wp_vintages.db"

    # Simulate 4 successive daily GEFS runs (Nov 3, Nov 4, Nov 5, Nov 6) all predicting valid_date 2026-11-15
    nao_runs = [
        ("2026-11-03", 12, -0.40, -0.90, 0.10),
        ("2026-11-04", 11, -0.80, -1.25, -0.35),
        ("2026-11-05", 10, -1.30, -1.70, -0.90),
        ("2026-11-06", 9, -1.90, -2.20, -1.60),
    ]
    for init_d, lead_d, mean_v, p25_v, p75_v in nao_runs:
        save_teleconnection_forecast_vintage(
            index_name="NAO",
            forecasts=[
                TeleconnectionForecastDay(
                    valid_date="2026-11-15",
                    lead_days=lead_d,
                    init_date=init_d,
                    ensemble_mean=mean_v,
                    ensemble_min=mean_v - 0.6,
                    ensemble_max=mean_v + 0.6,
                    ensemble_p25=p25_v,
                    ensemble_p75=p75_v,
                    ensemble_std=0.35,
                    member_count=31,
                    members=[mean_v] * 31,
                )
            ],
            db_path=db_file,
        )

    vintages = get_forecast_vintages_for_metric("NAO", model="GEFS", db_path=db_file)
    # CRITICAL: All 4 forecast runs for 2026-11-15 must remain in the database!
    assert len(vintages) == 4
    assert [v["points"][0]["value"] for v in vintages] == pytest.approx([-0.40, -0.80, -1.30, -1.90])

    # Simulate 4 successive stratospheric 10-hPa zonal wind runs strengthening into a reversal (< 0 m/s)
    pv_runs = [
        ("2026-11-03", 8.0),
        ("2026-11-04", 4.0),
        ("2026-11-05", -2.0),
        ("2026-11-06", -7.0),
    ]
    for init_d, u_min in pv_runs:
        sb = StratosphereBundle(
            observations=[StratosphereDailyPoint(init_d, 15.0, 215.0, is_forecast=False)],
            forecasts=[StratosphereDailyPoint("2026-11-12", u_min, 224.0, is_forecast=True)],
        )
        save_stratosphere_forecast_vintage(sb, run_date=init_d, db_path=db_file)

    pv_vintages = get_forecast_vintages_for_metric("U60N_10HPA", model="GEOS5_FP", db_path=db_file)
    assert len(pv_vintages) == 4

    bundle = _make_sample_bundle()
    fcst_map = {"NAO": vintages, "U60N_10HPA": pv_vintages}
    sig = compute_derived_signals(
        teleconnections=bundle.teleconnections,
        stratosphere=bundle.stratosphere,
        mjo=bundle.mjo,
        enso=bundle.enso,
        locations=bundle.locations,
        forecast_vintages=fcst_map,
    )

    nao_ev = sig.forecast_evolution["nao"]
    assert nao_ev["available"] is True
    assert nao_ev["target_date"] == "2026-11-15"
    assert nao_ev["current_run"] == pytest.approx(-1.90)
    assert nao_ev["previous_run"] == pytest.approx(-1.30)
    assert nao_ev["three_runs_ago"] == pytest.approx(-0.40)
    assert nao_ev["consecutive_runs_negative"] == 3
    assert nao_ev["trend"] == "strengthening_negative_signal"
    assert "stronger negative signal" in nao_ev["display_label"]

    pv_ev = sig.forecast_evolution["stratosphere"]
    assert pv_ev["available"] is True
    assert pv_ev["current_run_minimum"] == pytest.approx(-7.0)
    assert pv_ev["previous_run_minimum"] == pytest.approx(-2.0)
    assert pv_ev["three_runs_ago_minimum"] == pytest.approx(8.0)
    assert pv_ev["consecutive_runs_forecasting_reversal"] == 2
    assert pv_ev["first_run_showing_reversal"] == "2026-11-05"
    assert pv_ev["trend"] == "strengthening_reversal_signal"

    # Now test when a previously forecast wind reversal disappears in recent runs:
    # Nov 3: -8, Nov 4: -5, Nov 5: +1, Nov 6: +7
    db_file_dis = tmp_path / "wp_disappear.db"
    for init_d, u_min in [("2026-11-03", -8.0), ("2026-11-04", -5.0), ("2026-11-05", 1.0), ("2026-11-06", 7.0)]:
        sb = StratosphereBundle(
            observations=[StratosphereDailyPoint(init_d, 18.0, 212.0, is_forecast=False)],
            forecasts=[StratosphereDailyPoint("2026-11-12", u_min, 215.0, is_forecast=True)],
        )
        save_stratosphere_forecast_vintage(sb, run_date=init_d, db_path=db_file_dis)

    pv_dis_vintages = get_forecast_vintages_for_metric("U60N_10HPA", model="GEOS5_FP", db_path=db_file_dis)
    sig_dis = compute_derived_signals(
        teleconnections=bundle.teleconnections,
        stratosphere=bundle.stratosphere,
        mjo=bundle.mjo,
        enso=bundle.enso,
        locations=bundle.locations,
        forecast_vintages={"U60N_10HPA": pv_dis_vintages},
    )
    pv_ev_dis = sig_dis.forecast_evolution["stratosphere"]
    assert pv_ev_dis["previously_forecast_reversal_disappeared"] is True
    assert pv_ev_dis["trend"] == "previously_forecast_reversal_disappeared"
    assert any("disappeared" in b for b in sig_dis.what_changed["STRATOSPHERE"])

    # Also verify the V2 Forecast Evolution Chart renders cleanly
    evo_chart = build_forecast_evolution_chart(fcst_map, bundle.teleconnections, bundle.stratosphere)
    assert isinstance(evo_chart, Drawing)


def test_v2_stale_fetch_does_not_manufacture_forecast_vintage(tmp_path: Path):
    """If today's external fetch failed and returned stale cache, do not create a new forecast vintage."""
    db_file = tmp_path / "wp_stale_guard.db"
    bundle = _make_sample_bundle()
    # Mark AO forecast provenance as stale fallback
    bundle.teleconnections["AO"].fcst_provenance = SourceProvenance(
        source_name="NOAA CPC / NCEP GEFS",
        product="AO GEFS",
        url="https://ftp.cpc.ncep.noaa.gov/cwlinks/",
        retrieved_at="2026-11-02T00:00:00Z",
        from_cache=True,
        is_stale=True,
        available=True,
    )
    persist_weather_patterns_bundle(bundle, db_path=db_file)
    ao_vintages = get_forecast_vintages_for_metric("AO", db_path=db_file)
    assert len(ao_vintages) == 0


def test_v2_verification_and_analog_queries(tmp_path: Path):
    db_file = tmp_path / "wp_verify.db"

    # Seed 12 days of observations and D+3 forecasts so sample_count >= 10 (meaningful sample)
    obs_list = [
        TeleconnectionDailyObs(f"2026-10-{10 + i:02d}", -1.0 + 0.1 * i)
        for i in range(15)
    ]
    save_teleconnection_observations("NAO", obs_list, db_path=db_file)

    for i in range(12):
        init_d = f"2026-10-{7 + i:02d}"
        valid_d = f"2026-10-{10 + i:02d}"
        true_v = -1.0 + 0.1 * i
        pred_v = true_v - 0.15  # slight error
        save_teleconnection_forecast_vintage(
            "NAO",
            [
                TeleconnectionForecastDay(
                    valid_date=valid_d,
                    lead_days=3,
                    init_date=init_d,
                    ensemble_mean=pred_v,
                    ensemble_min=pred_v - 0.3,
                    ensemble_max=pred_v + 0.3,
                    ensemble_p25=pred_v - 0.1,
                    ensemble_p75=pred_v + 0.1,
                    ensemble_std=0.15,
                    member_count=31,
                )
            ],
            db_path=db_file,
        )

    ver = compute_teleconnection_verification_stats(
        "NAO", lead_days_list=(3, 7), min_samples_for_skill_claim=10, db_path=db_file
    )
    assert ver["by_lead"]["D+3"]["sample_count"] == 12
    assert ver["by_lead"]["D+3"]["has_meaningful_sample"] is True
    assert ver["by_lead"]["D+3"]["mae"] == pytest.approx(0.15, abs=0.01)
    assert ver["by_lead"]["D+3"]["correlation"] == pytest.approx(1.0, abs=0.01)
    # D+7 has 0 samples -> has_meaningful_sample must be False
    assert ver["by_lead"]["D+7"]["sample_count"] == 0
    assert ver["by_lead"]["D+7"]["has_meaningful_sample"] is False

    # Test historical analog query
    save_teleconnection_observations(
        "AO", [TeleconnectionDailyObs("2026-01-15", -1.60)], db_path=db_file
    )
    save_teleconnection_observations(
        "NAO", [TeleconnectionDailyObs("2026-01-15", -1.50)], db_path=db_file
    )
    save_teleconnection_observations(
        "PNA", [TeleconnectionDailyObs("2026-01-15", 1.55)], db_path=db_file
    )
    analogs = find_historical_teleconnection_analogs(
        ao_target=-1.64,
        nao_target=-1.55,
        pna_target=1.60,
        max_distance_sd=0.5,
        reference_date="2026-11-04",
        db_path=db_file,
    )
    assert len(analogs) == 1
    assert analogs[0]["date"] == "2026-01-15"
    assert analogs[0]["distance_sd"] < 0.15


def test_bom_rmm_parser_and_teleconnection_effects_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test Australian BOM RMM parsing, climate.db querying, auto-bootstrap, and LLM packet inclusion."""
    import sqlite3
    from datetime import datetime
    from screamsheet.providers.mjo_provider import MJOProvider
    from screamsheet.providers.teleconnection_effects_provider import (
        TeleconnectionEffectsProvider,
        classify_teleconnection_state,
    )

    bom_text = (
        "RMM values up to real time\n"
        " year, month, day, RMM1, RMM2, phase, amplitude.\n"
        " 2026 11 5 -0.7356 -1.9707 2 2.1035 Gottschalk10\n"
        " 2026 11 6 -0.9242 -2.0711 2 2.2679 Gottschalk10\n"
    )
    mjo_pts = MJOProvider.parse_bom_rmm_text(bom_text)
    assert len(mjo_pts) == 2
    assert mjo_pts[-1].date == "2026-11-06"
    assert mjo_pts[-1].phase == 2
    assert mjo_pts[-1].active is True

    assert classify_teleconnection_state("AO", -1.7) == "strong_negative"
    assert classify_teleconnection_state("NAO", -0.8) == "negative"
    assert classify_teleconnection_state("PNA", 1.2) == "positive"
    assert classify_teleconnection_state("NINO34", -0.7) == "la_nina"

    # Build a synthetic climate.db with location, teleconnection_effect, and mjo_effect
    clim_db = tmp_path / "climate.db"
    conn = sqlite3.connect(str(clim_db))
    conn.executescript(
        """
        CREATE TABLE location (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            era5_latitude REAL,
            era5_longitude REAL,
            bootstrap_status TEXT NOT NULL DEFAULT 'pending',
            bootstrap_date TEXT,
            history_start TEXT,
            history_end TEXT
        );
        CREATE TABLE teleconnection_effect (
            location_id TEXT NOT NULL,
            code TEXT NOT NULL,
            season TEXT NOT NULL,
            state TEXT NOT NULL,
            lag_start_days INTEGER NOT NULL,
            lag_end_days INTEGER NOT NULL,
            variable TEXT NOT NULL,
            mean_effect REAL,
            median_effect REAL,
            sample_count INTEGER NOT NULL,
            p_value REAL,
            confidence TEXT NOT NULL
        );
        CREATE TABLE mjo_effect (
            location_id TEXT NOT NULL,
            season TEXT NOT NULL,
            phase INTEGER NOT NULL,
            lag_start_days INTEGER NOT NULL,
            lag_end_days INTEGER NOT NULL,
            variable TEXT NOT NULL,
            mean_effect REAL,
            median_effect REAL,
            sample_count INTEGER NOT NULL,
            p_value REAL,
            confidence TEXT NOT NULL
        );
        INSERT INTO location VALUES (
            'philadelphia_pa', 'Philadelphia, PA', 39.95, -75.16, 40.03, -75.27,
            'complete', '2026-11-11T00:00:00Z', '1979-01-01', '2026-11-06'
        );
        INSERT INTO teleconnection_effect VALUES
            ('philadelphia_pa', 'AO', 'OND', 'strong_negative', 0, 5, 'tmean_anomaly_c', -1.8, -1.7, 450, 0.001, 'high'),
            ('philadelphia_pa', 'AO', 'OND', 'strong_negative', 0, 5, 'precip_mm', 0.4, -0.2, 450, 0.25, 'low'),
            ('philadelphia_pa', 'NAO', 'OND', 'strong_negative', 0, 5, 'tmean_anomaly_c', -1.4, -1.3, 410, 0.002, 'high'),
            ('philadelphia_pa', 'PNA', 'OND', 'strong_positive', 0, 5, 'tmean_anomaly_c', -1.1, -1.0, 380, 0.01, 'high'),
            ('philadelphia_pa', 'NINO34', 'OND', 'la_nina', 0, 5, 'tmean_anomaly_c', 0.3, 0.2, 900, 0.12, 'medium');
        INSERT INTO mjo_effect VALUES
            ('philadelphia_pa', 'OND', 1, 6, 10, 'tmean_anomaly_c', -0.9, -0.8, 120, 0.03, 'high');
        """
    )
    conn.commit()
    conn.close()

    bundle = _make_sample_bundle()
    prov = TeleconnectionEffectsProvider(
        climate_db_path=clim_db,
        teleconnections_dir=tmp_path / "nonexistent_tele_dir",
        auto_bootstrap=False,
    )
    loc0 = bundle.locations[0]
    prov.enrich_location_teleconnection_effects(
        loc0,
        teleconnections=bundle.teleconnections,
        mjo=bundle.mjo,
        enso=bundle.enso,
        target_date=datetime(2026, 11, 4),
    )

    assert loc0.teleconnection_effects["location_id"] == "philadelphia_pa"
    assert loc0.teleconnection_effects["season"] == "OND"
    ao_eff = loc0.teleconnection_effects["teleconnections"]["AO"]
    assert ao_eff["current_state"] == "strong_negative"
    assert ao_eff["current_state_effects"][0]["temp_anomaly_mean_c"] == pytest.approx(-1.8)
    assert ao_eff["current_state_effects"][0]["temp_anomaly_mean_f"] == pytest.approx(-3.24)
    assert ao_eff["current_state_effects"][0]["temp_confidence"] == "high"

    # Verify LLM packet contains LOCAL_TELECONNECTION_CLIMATOLOGY
    packet = bundle.to_llm_packet()
    assert "LOCAL_TELECONNECTION_CLIMATOLOGY" in packet
    assert packet["LOCAL_TELECONNECTION_CLIMATOLOGY"][0]["location_id"] == "philadelphia_pa"

    # Verify subprocess auto-bootstrap is triggered when location is missing from climate.db
    fake_tele_dir = tmp_path / "fake_tele"
    (fake_tele_dir / "scripts").mkdir(parents=True)
    (fake_tele_dir / "scripts" / "bootstrap_location.py").write_text("# stub\n", encoding="utf-8")

    called_cmds: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        called_cmds.append(list(cmd))
        # Simulate bootstrap_location.py writing status='complete' into clim_db
        c = sqlite3.connect(str(clim_db))
        c.execute(
            "INSERT INTO location VALUES ('stowe_vt', 'Stowe, VT', 44.46, -72.68, 44.5, -72.7, 'complete', '2026-11-11', '1979-01-01', '2026-11-06');"
        )
        c.commit()
        c.close()

        class _Proc:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return _Proc()

    monkeypatch.setattr("subprocess.run", _fake_run)
    prov_auto = TeleconnectionEffectsProvider(
        climate_db_path=clim_db,
        teleconnections_dir=fake_tele_dir,
        auto_bootstrap=True,
    )
    loc1 = bundle.locations[1]  # Stowe, VT
    prov_auto.enrich_location_teleconnection_effects(
        loc1,
        teleconnections=bundle.teleconnections,
        mjo=bundle.mjo,
        enso=bundle.enso,
        target_date=datetime(2026, 11, 4),
    )
    assert len(called_cmds) == 1
    assert "--id" in called_cmds[0] and "stowe_vt" in called_cmds[0]
    assert loc1.teleconnection_effects["location_id"] == "stowe_vt"


def test_teleconnection_effects_provider_graceful_fallback_when_db_missing_or_corrupt(tmp_path, monkeypatch):
    """Ensure Climate Screamsheet runs cleanly when climate.db is missing, empty, or corrupted on the server."""
    import sqlite3

    from screamsheet.providers.teleconnection_effects_provider import TeleconnectionEffectsProvider

    called_cmds: list[list[str]] = []
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: called_cmds.append(list(cmd)))

    # Case 1: climate.db does not exist at all on the prod server
    missing_db = tmp_path / "nonexistent_climate.db"
    bundle = _make_sample_bundle()
    prov_missing = TeleconnectionEffectsProvider(
        climate_db_path=missing_db,
        teleconnections_dir=tmp_path / "fake_tele",
        auto_bootstrap=True,
    )
    loc0 = bundle.locations[0]
    prov_missing.enrich_location_teleconnection_effects(
        loc0,
        teleconnections=bundle.teleconnections,
        mjo=bundle.mjo,
        enso=bundle.enso,
        target_date=datetime(2026, 11, 4),
    )
    assert not missing_db.exists()
    assert len(called_cmds) == 0
    assert loc0.teleconnection_effects is None
    assert loc0.teleconnection_effects_provenance is not None
    assert loc0.teleconnection_effects_provenance.available is False

    # Case 2: climate.db exists on disk, has location row 'complete', but effect tables are missing/corrupt
    broken_db = tmp_path / "broken_climate.db"
    conn = sqlite3.connect(str(broken_db))
    conn.execute(
        "CREATE TABLE location (id TEXT PRIMARY KEY, name TEXT, latitude REAL, longitude REAL, bootstrap_status TEXT);"
    )
    conn.execute(
        "INSERT INTO location VALUES ('philadelphia', 'Philadelphia', 39.95, -75.16, 'complete');"
    )
    conn.commit()
    conn.close()

    prov_broken = TeleconnectionEffectsProvider(
        climate_db_path=broken_db,
        teleconnections_dir=tmp_path / "fake_tele",
        auto_bootstrap=False,
    )
    prov_broken.enrich_location_teleconnection_effects(
        loc0,
        teleconnections=bundle.teleconnections,
        mjo=bundle.mjo,
        enso=bundle.enso,
        target_date=datetime(2026, 11, 4),
    )
    assert loc0.teleconnection_effects is None
    assert loc0.teleconnection_effects_provenance is not None
    assert loc0.teleconnection_effects_provenance.available is False

    # Verify fallback narrative and LLM packet still generate cleanly without historical climatology
    narrative = WeatherPatternsScreamsheet._build_deterministic_fallback_narrative(bundle)
    assert "PATTERN:" in narrative
    assert "LOCAL WATCH:" in narrative
    packet = bundle.to_llm_packet()
    assert "LOCAL_TELECONNECTION_CLIMATOLOGY" not in packet

