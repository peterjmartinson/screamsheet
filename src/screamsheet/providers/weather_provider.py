"""NWS weather data provider."""
import os
import requests
from pathlib import Path
from typing import List, Dict, Optional


# Absolute path to icons bundled inside this package
_ASSETS_ROOT = Path(__file__).parent.parent / 'assets' / 'weather'

# NWS keyword → local icon filename
BW_ICON_MAP = {
    'SUNNY':          'wi-day-sunny.png',
    'CLEAR':          'wi-night-clear.png',
    'PARTLY SUNNY':   'wi-day-cloudy.png',
    'MOSTLY SUNNY':   'wi-day-cloudy.png',
    'PARTLY CLOUDY':  'wi-cloudy.png',
    'MOSTLY CLOUDY':  'wi-cloudy.png',
    'CLOUDY':         'wi-cloud.png',
    'RAIN':           'wi-rain.png',
    'SHOWERS':        'wi-rain.png',
    'LIGHT RAIN':     'wi-rain.png',
    'CHANCE RAIN':    'wi-rain.png',
    'RAIN LIKELY':    'wi-rain.png',
    'DRIZZLE':        'wi-rain.png',
    'SNOW':           'wi-snow.png',
    'HEAVY SNOW':     'wi-snow.png',
    'LIGHT SNOW':     'wi-snow.png',
    'SLEET':          'wi-rain-mix.png',
    'RAIN/SNOW':      'wi-rain-mix.png',
    'WINTERY MIX':    'wi-rain-mix.png',
    'THUNDERSTORM':   'wi-thunderstorm.png',
    'T-STORM':        'wi-thunderstorm.png',
    'FOG':            'wi-fog.png',
    'HAZE':           'wi-fog.png',
    'WINDY':          'wi-strong-wind.png',
    'BLUSTERY':       'wi-strong-wind.png',
    'DEFAULT':        'wi-na.png',
}

NWS_HEADERS = {
    'User-Agent': 'DailyScreamSheet (peter.j.martinson@gmail.com)',
    'Accept': 'application/ld+json',
}


class WeatherProvider:
    """
    Fetches and processes a 5-day NWS forecast for a given location.

    Args:
        lat:           Latitude of the target location.
        lon:           Longitude of the target location.
        location_name: Human-readable location label shown on the forecast.
    """

    def __init__(
        self,
        lat: float = 40.02,
        lon: float = -75.34,
        location_name: str = 'Bryn Mawr, PA',
    ):
        self.lat = lat
        self.lon = lon
        self.location_name = location_name
        self._nws_base = 'https://api.weather.gov'

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_5_day_forecast(self) -> List[Dict]:
        """
        Return up to 5 full-day forecast dicts, each with keys:
            day, location, description, icon_url, max_temp, min_temp
        Returns an empty list on any fetch failure.
        """
        periods = self._fetch_forecast_data()
        if not periods:
            return []

        forecast_list = []

        # Determine starting index based on whether it's currently day/night
        if periods[0]['isDaytime']:
            day_period_index = 0
            loop_start_index = 2
        else:
            day_period_index = 1
            loop_start_index = 3

        # --- Today ---
        today_day = periods[day_period_index]
        today_night = periods[day_period_index + 1] if day_period_index + 1 < len(periods) else None

        forecast_list.append(self._make_day_dict(
            name=today_day['name'],
            location=self.location_name,
            description=today_day.get('shortForecast', 'N/A'),
            icon_url=today_day.get('icon', ''),
            max_temp=today_day.get('temperature', 'N/A'),
            min_temp=today_night.get('temperature', 'N/A') if today_night else 'N/A',
        ))

        # --- Next 4 days ---
        for i in range(4):
            day_idx = loop_start_index + (i * 2)
            night_idx = day_idx + 1
            if day_idx >= len(periods):
                break
            day_p = periods[day_idx]
            night_p = periods[night_idx] if night_idx < len(periods) else None
            forecast_list.append(self._make_day_dict(
                name=day_p['name'].split()[0],
                location='',
                description=day_p.get('shortForecast', 'N/A'),
                icon_url=day_p.get('icon', ''),
                max_temp=day_p.get('temperature', 'N/A'),
                min_temp=night_p.get('temperature', 'N/A') if night_p else 'N/A',
            ))

        return forecast_list

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch_forecast_data(self) -> Optional[list]:
        """Call the NWS API and return the raw periods list, or None."""
        try:
            points_url = f'{self._nws_base}/points/{self.lat},{self.lon}'
            r = requests.get(points_url, headers=NWS_HEADERS, timeout=15)
            r.raise_for_status()
            forecast_url = r.json().get('forecast')
            if not forecast_url:
                print('WeatherProvider: No forecast URL in NWS points response.')
                return None

            r2 = requests.get(forecast_url, headers=NWS_HEADERS, timeout=15)
            r2.raise_for_status()
            return r2.json().get('periods')

        except requests.exceptions.RequestException as e:
            print(f'WeatherProvider: NWS request failed: {e}')
            return None
        except Exception as e:
            print(f'WeatherProvider: Unexpected error: {e}')
            return None

    def _make_day_dict(
        self,
        name: str,
        location: str,
        description: str,
        icon_url: str,
        max_temp,
        min_temp,
    ) -> Dict:
        """Build a forecast dict and substitute the NWS icon with a local B&W one."""
        day = {
            'day': name,
            'location': location,
            'description': description,
            'icon_url': icon_url,
            'max_temp': max_temp,
            'min_temp': min_temp,
        }
        return self._map_to_bw_icon(day)

    @staticmethod
    def _map_to_bw_icon(day_data: Dict) -> Dict:
        """Replace the NWS icon URL with the local B&W PNG path."""
        description = day_data.get('description', '').upper()
        icon_filename = BW_ICON_MAP['DEFAULT']
        for key, filename in BW_ICON_MAP.items():
            if key != 'DEFAULT' and key in description:
                icon_filename = filename
                break
        day_data['icon_url'] = str(_ASSETS_ROOT / icon_filename)
        return day_data
