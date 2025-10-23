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

page_width = 8.5 * inch
left_margin = 1 * inch
right_margin = 1 * inch
available_width = page_width - left_margin - right_margin
styles = getSampleStyleSheet()

CENTERED_STYLE = ParagraphStyle(
    name="CenteredText",
    alignment=TA_CENTER
)

TITLE_STYLE = ParagraphStyle(
    name="Title",
    parent=styles['h1'],
    fontName='Helvetica-Bold',
    fontSize=28,
    spaceAfter=12,
    alignment=TA_CENTER
)

SUBTITLE_STYLE = ParagraphStyle(
    name="Subtitle",
    parent=styles['h2'],
    fontName='Helvetica',
    fontSize=18,
    spaceAfter=12,
    alignment=TA_CENTER
)

TEXT = lorem.paragraphs(2)

def make_title_section(title_text: str, subtitle_text: str = None) -> Paragraph:
    
    pass

def make_text_section(text_body) -> Paragraph: # reportlab.platypus.paragraph.Paragraph
    summary_text_style = styles['Normal']
    summary_text_style.fontName = 'Helvetica'
    summary_text_style = ParagraphStyle(
        name="SummaryText",
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=12,
    )
    summary = Paragraph(text_body, summary_text_style)
    return summary

def make_chart_section(list_of_lists) -> Table:
    pass

def get_chart_dimensions(c: Table) -> dict:
    required_width, required_height = c.wrap(available_width, 0)
    dimensions = {
      "width_pt": required_width,
      "height_pt": required_height,
      "width_inch": required_width / inch,
      "height_inch": required_height / inch
    }
    return dimensions

def make_columns_section(list_of_elements):
    pass

def get_columns_dimensions(c) -> dict:
    pass

def get_paragraph_dimensions(p: Paragraph) -> dict:
    required_width, required_height = summary.wrapOn(None, available_width, 100 * inch)
    dimensions = {
        "width_pt": required_width,
        "height_pt": required_height,
        "width_inch": required_width / inch,
        "height_inch": required_height / inch
    }
    return dimensions


if __name__ == "__main__":

    story = []
    story.append(Paragraph("MLB Scream Sheet", TITLE_STYLE))
    story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    print(f"page_width: {page_width}")
    print(f"left_margin: {left_margin}")
    print(f"right_margin: {right_margin}")
    print(f"available_width: {available_width}")

    summary = make_text_section(TEXT)
    dim = get_paragraph_dimensions(summary)

    title_text = "Daily Scream Sheet"
    subtitle_text = datetime.today().strftime("%A, %B %#d, %Y")
    title = make_title_section(title_text, subtitle_text)

    print(f"Text Height:\n  {dim['height_pt']} points\n  {dim['height_inch']:.2f} inches")
    print(f"Text Width:\n  {dim['width_pt']} points\n  {dim['width_inch']:.2f} inches")
    # story.append(Paragraph("MLB Scream Sheet", TITLE_STYLE))
    # story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    # story.append(Spacer(1, 12))
    # story.append(scores_table)
