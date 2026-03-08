"""Unit tests for screamsheet.providers.weather_provider (WeatherProvider)."""
from unittest.mock import patch, MagicMock, call

import pytest

from screamsheet.providers.weather_provider import WeatherProvider, BW_ICON_MAP


@pytest.fixture
def provider():
    return WeatherProvider(lat=40.02, lon=-75.34, location_name="Bryn Mawr, PA")


# ---------------------------------------------------------------------------
# get_5_day_forecast
# ---------------------------------------------------------------------------

class TestGet5DayForecast:
    def test_returns_list(self, provider, nws_points_response, nws_forecast_response):
        points_mock = MagicMock()
        points_mock.json.return_value = nws_points_response

        forecast_mock = MagicMock()
        periods = nws_forecast_response["properties"]["periods"]
        forecast_mock.json.return_value = periods

        with patch.object(provider, "_fetch_forecast_data", return_value=periods):
            result = provider.get_5_day_forecast()

        assert isinstance(result, list)

    def test_returns_up_to_5_days(self, provider, nws_forecast_response):
        periods = nws_forecast_response["properties"]["periods"]
        with patch.object(provider, "_fetch_forecast_data", return_value=periods):
            result = provider.get_5_day_forecast()
        assert len(result) <= 5

    def test_returns_empty_list_on_fetch_failure(self, provider):
        with patch.object(provider, "_fetch_forecast_data", return_value=None):
            result = provider.get_5_day_forecast()
        assert result == []

    def test_day_dict_has_required_keys(self, provider, nws_forecast_response):
        periods = nws_forecast_response["properties"]["periods"]
        with patch.object(provider, "_fetch_forecast_data", return_value=periods):
            result = provider.get_5_day_forecast()
        if result:
            for key in ("day", "description", "icon_url", "max_temp", "min_temp"):
                assert key in result[0]

    def test_location_in_today_entry(self, provider, nws_forecast_response):
        periods = nws_forecast_response["properties"]["periods"]
        with patch.object(provider, "_fetch_forecast_data", return_value=periods):
            result = provider.get_5_day_forecast()
        if result:
            assert result[0]["location"] == "Bryn Mawr, PA"


# ---------------------------------------------------------------------------
# _map_to_bw_icon
# ---------------------------------------------------------------------------

class TestMapToBwIcon:
    def test_sunny_maps_to_day_sunny(self):
        day = {"description": "Sunny", "icon_url": ""}
        result = WeatherProvider._map_to_bw_icon(day)
        assert "wi-day-sunny" in result["icon_url"]

    def test_rain_maps_to_rain_icon(self):
        day = {"description": "Rain", "icon_url": ""}
        result = WeatherProvider._map_to_bw_icon(day)
        assert "wi-rain" in result["icon_url"]

    def test_unknown_description_maps_to_default(self):
        day = {"description": "UNKNOWN_CONDITION_XYZ", "icon_url": ""}
        result = WeatherProvider._map_to_bw_icon(day)
        assert "wi-na" in result["icon_url"]

    def test_icon_url_is_string(self):
        day = {"description": "Clear", "icon_url": ""}
        result = WeatherProvider._map_to_bw_icon(day)
        assert isinstance(result["icon_url"], str)


# ---------------------------------------------------------------------------
# BW_ICON_MAP sanity check
# ---------------------------------------------------------------------------

class TestBwIconMap:
    def test_default_key_present(self):
        assert "DEFAULT" in BW_ICON_MAP

    def test_all_values_end_with_png(self):
        for key, val in BW_ICON_MAP.items():
            assert val.endswith(".png"), f"Icon for '{key}' does not end with .png"
