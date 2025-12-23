import requests
from datetime import datetime
from typing import List, Dict, Optional
import os
import sys

# --- LOCAL ASSETS CONFIGURATION ---
# Base path for your local weather icons
# NOTE: This is the path relative to where your code will process the icon (e.g., in a template/HTML generator)
LOCAL_ASSETS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'weather')
LOCAL_ASSETS_PATH = "/assets/weather"

# Mapping NWS Keywords to LOCAL ICON FILENAMES
# These are the 12 files you selected from the Erik Flowers set.
# We map the keywords found in the 'shortForecast' to the corresponding local SVG file.
BW_ICON_MAP = {
    # Sunny / Clear / Cloudy
    'SUNNY': 'wi-day-sunny.png',            # 1. Sunny
    'CLEAR': 'wi-night-clear.png',          # 12. Night/Low Temp (Fallback for clear night)
    'PARTLY SUNNY': 'wi-day-cloudy.png',    # 2. Mostly Sunny
    'MOSTLY SUNNY': 'wi-day-cloudy.png',
    'PARTLY CLOUDY': 'wi-cloudy.png',       # 3. Partly Cloudy
    'MOSTLY CLOUDY': 'wi-cloudy.png',
    'CLOUDY': 'wi-cloud.png',               # 4. Overcast/Cloudy

    # Rain / Precipitation
    'RAIN': 'wi-rain.png',                  # 5. Rain
    'SHOWERS': 'wi-rain.png',
    'LIGHT RAIN': 'wi-rain.png',
    'CHANCE RAIN': 'wi-rain.png',
    'RAIN LIKELY': 'wi-rain.png',
    'DRIZZLE': 'wi-rain.png',

    # Snow / Sleet
    'SNOW': 'wi-snow.png',                  # 7. Snow
    'HEAVY SNOW': 'wi-snow.png',
    'LIGHT SNOW': 'wi-snow.png',
    'SLEET': 'wi-rain-mix.png',             # 8. Mixed Precip
    'RAIN/SNOW': 'wi-rain-mix.png',
    'WINTERY MIX': 'wi-rain-mix.png',

    # Thunderstorms
    'THUNDERSTORM': 'wi-thunderstorm.png',  # 6. Thunderstorm
    'T-STORM': 'wi-thunderstorm.png',

    # Other conditions
    'FOG': 'wi-fog.png',                    # 9. Fog
    'HAZE': 'wi-fog.png',
    'WINDY': 'wi-strong-wind.png',          # 10. Wind
    'BLUSTERY': 'wi-strong-wind.png',

    # Default/Fallback
    'DEFAULT': 'wi-na.png' # wi-na.png (Not Available) is a great general fallback icon
}


# Constants for Bryn Mawr, PA (approximate)
# NWS API requires latitude and longitude
LATITUDE = 40.02
LONGITUDE = -75.34
LOCATION_NAME = "Bryn Mawr, PA"
NWS_API_BASE = "https://api.weather.gov"

# NWS API requires a User-Agent header (use your project name/email)
HEADERS = {
    'User-Agent': 'DailyScreamSheet (peter.j.martinson@gmail.com)',
    'Accept': 'application/ld+json'
}

def map_to_bw_icon(day_data: dict) -> dict:
    """
    Substitutes the color NWS icon URL with a path to a local black-and-white
    SVG icon from the assets folder.
    """
    description = day_data.get('description', '').upper()

    # 1. Determine the icon filename
    icon_filename = BW_ICON_MAP['DEFAULT']

    # Iterate through the map to find a matching keyword in the forecast description
    for key, filename in BW_ICON_MAP.items():
        # print(f"is {key} in {description}?")
        if key != 'DEFAULT' and key in description:
            icon_filename = filename
            break

    # 2. Construct the full local file path
    # Example: /assets/weather/wi-day-sunny.svg
    # icon_path = f"{LOCAL_ASSETS_PATH}/{icon_filename}"
    icon_path = os.path.join(LOCAL_ASSETS_ROOT, icon_filename)
    # Update the icon URL key with the new local path
    day_data['icon_url'] = icon_path

    return day_data

def _fetch_forecast_data() -> Optional[Dict]:
    """
    Fetches the 7-day forecast data from the NWS API.
    Returns the parsed JSON response or None on failure.
    """
    try:
        # 1. Get the forecast grid endpoint for the location (points/lat,lon)
        points_url = f"{NWS_API_BASE}/points/{LATITUDE},{LONGITUDE}"
        points_response = requests.get(points_url, headers=HEADERS)
        points_response.raise_for_status() # Raise HTTPError for bad responses

        forecast_url = points_response.json().get('forecast')
        if not forecast_url:
            print("Error: Could not find forecast URL from points API.")
            return None

        # 2. Get the actual 7-day forecast (14 periods)
        forecast_response = requests.get(forecast_url, headers=HEADERS)
        forecast_response.raise_for_status()

        return forecast_response.json().get('periods')

    except requests.exceptions.RequestException as e:
        print(f"Error fetching NWS data: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def get_5_day_forecast() -> List[Dict]:
    """
    Fetches 7-day forecast data and processes it into 5 full-day entries,
    handling the possibility of a Night-period start, and mapping the icon.
    """
    periods = _fetch_forecast_data()
    if not periods:
        return []

    forecast_list = []

    # --- Determine the Starting Index for Full Day Processing ---

    # The current day is either periods[0] (if daytime) or periods[1] (if nighttime start)
    if periods[0]['isDaytime']:
        # Scenario A: It's currently daytime (Start with Day period)
        day_period_index = 0
        loop_start_index = 2
    else:
        # Scenario B: It's currently nighttime (Skip current 'Tonight', start processing next Day)
        day_period_index = 1
        loop_start_index = 3


    # --- 1. Process "Today" (The first full daytime period) ---

    today_day_period = periods[day_period_index]

    # The low temp for "Today" comes from the subsequent Night period.
    today_night_period = periods[day_period_index + 1] if day_period_index + 1 < len(periods) else None

    # Get max temp (from Day) and min temp (from subsequent Night)
    max_temp = today_day_period.get('temperature', 'N/A')
    min_temp = today_night_period.get('temperature', 'N/A') if today_night_period else 'N/A'

    day_forecast = {
        'day': today_day_period['name'],
        'location': LOCATION_NAME,
        'description': today_day_period.get('shortForecast', 'N/A'),
        # NWS ICON URL is fetched but will be replaced below
        'icon_url': today_day_period.get('icon', ''),
        'max_temp': max_temp,
        'min_temp': min_temp
    }

    # --- ICON MAPPING APPLIED HERE ---
    forecast_list.append(map_to_bw_icon(day_forecast))


    # --- 2. Process the remaining 4 full days ---

    days_to_process = 4

    for i in range(days_to_process):
        day_index = loop_start_index + (i * 2)
        night_index = day_index + 1

        if day_index >= len(periods):
            break

        day_period = periods[day_index]
        night_period = periods[night_index] if night_index < len(periods) else None

        # Get the day name (e.g., "Monday", "Tuesday")
        day_name = day_period['name'].split()[0]

        day_forecast = {
            'day': day_name,
            'location': '',
            'description': day_period.get('shortForecast', 'N/A'),
            # NWS ICON URL is fetched but will be replaced below
            'icon_url': day_period.get('icon', ''),
            'max_temp': day_period.get('temperature', 'N/A'),
            'min_temp': night_period.get('temperature', 'N/A') if night_period else 'N/A'
        }

        # --- ICON MAPPING APPLIED HERE ---
        forecast_list.append(map_to_bw_icon(day_forecast))

    return forecast_list

# Example of usage (if running this script directly):
if __name__ == '__main__':
    print("--- 5-Day Forecast for Bryn Mawr, PA ---")
    forecast = get_5_day_forecast()
    for day in forecast:
        # Example output showing the new local icon path:
        # {'day': 'Today', ..., 'icon_url': '/assets/weather/wi-day-sunny.svg', ...}
        print(day)
