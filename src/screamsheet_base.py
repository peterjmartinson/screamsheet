from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Frame,
    PageBreak,  # <-- Import the PageBreak flowable
)
import pandas as pd
import requests
import os
import json

class Screamsheet:
    
    section_list = []

    def __init__(self) -> None:
        print("Initializing Screamsheet")

    def _add_section(self, content) -> None:
        new_section = ScreamsheetSection(content)
        section_list.append(new_section)

class ScreamsheetSection:
    pass
