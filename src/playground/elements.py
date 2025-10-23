from datetime import datetime, timedelta
from lorem_text import lorem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    # SimpleDocTemplate,
    Table,
    # TableStyle,
    Paragraph,
    # Spacer,
    # Frame,
    # PageBreak,  # <-- Import the PageBreak flowable
)

styles = getSampleStyleSheet()
MARGIN = 36  # points, = 0.5 inches

class Section:

    _section_style = ParagraphStyle(
        name="DefaultSectionStyle",
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=12,
    )

    _section_heading_style = ParagraphStyle(
        name="DefaultSectionHeadingStyle",
        parent=styles['h3'],
        fontName='Helvetica-Bold',
        fontSize=14,
        spaceAfter=12,
    )

    def __init__(self):
        pass
