"""Weather section renderer (backward-compatible alias for WeatherComponent)."""
from reportlab.platypus import Image

from ..components.weather import WeatherComponent

WeatherSection = WeatherComponent

__all__ = ["WeatherSection", "WeatherComponent", "Image"]
