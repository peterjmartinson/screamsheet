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

from get_headlines import fetch_and_process_headlines
from headline_translator import get_lexicon

styles = getSampleStyleSheet()

CENTERED_STYLE = ParagraphStyle(
    name="CenteredText",
    alignment=TA_CENTER
)

TITLE_STYLE = ParagraphStyle(
    name="Title",
    parent=styles['h1'],
    fontName='Helvetica-BoldOblique',
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

REGULAR_TEXT_STYLE = ParagraphStyle(
    name="SummaryText",
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=12,
)

def generate_screamsheet_pdf(headline_list, lexicon_entries, filename):
    # --- 1. Setup Document and Styles ---
    margin = 36 # 0.5 inches in points
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin
    )
    Story = []

    # Custom Styles
    styles.add(ParagraphStyle(name='TitleBanner', 
                              fontName='Helvetica-Bold', 
                              fontSize=36, 
                              alignment=1, # Center
                              spaceAfter=12,
                              textColor=colors.firebrick))
    
    styles.add(ParagraphStyle(name='SubHeader', 
                              fontName='Helvetica', 
                              fontSize=14, 
                              alignment=1,
                              spaceAfter=24,
                              textColor=colors.gray))
    
    styles.add(ParagraphStyle(name='SectionTitle', 
                              fontName='Helvetica-Bold', 
                              fontSize=18, 
                              spaceAfter=10,
                              textColor=colors.black))

    # --- 2. Get Data and Format Date ---
    headlines_text = "\n".headline_list
    # headlines_text, lexicon_entries = get_report_data()
    
    # --- 3. Add Title and Date (Banner Section) ---
    Story.append(Paragraph("Le Scream Sheet", TITLE_STYLE))
    Story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    # Story.append(Paragraph("Le SCREAMSHEET", styles['TitleBanner']))
    # Story.append(Paragraph(today, styles['SubHeader']))
    
    # --- 4. Add Headlines Block ---
    Story.append(Paragraph("Les gros titres du jour", styles['SectionTitle']))
    # Use a preformatted/Code style and replace newlines with <br/> for ReportLab
    Story.append(Paragraph(headlines_text, REGULAR_TEXT_STYLE))
    Story.append(Spacer(1, 24))

    # --- 5. Add Lexicon Block (Dynamic Table Layout) ---
    
    Story.append(Paragraph("French-English Lexicon", styles['SectionTitle']))

    # Only proceed if we have valid lexicon data
    if lexicon_entries and not lexicon_entries[0].startswith("ERROR"):
        num_entries = len(lexicon_entries)
        # Choose 4 columns if there are 20 or more entries, otherwise use 3.
        COLS = 4 if num_entries >= 20 else 3
        ROWS = (num_entries + COLS - 1) // COLS # Calculate rows needed

        # Prepare data for the ReportLab Table (column-major order)
        table_data = []
        for r in range(ROWS):
            row = []
            for c in range(COLS):
                index = c * ROWS + r
                # Fill table with data or empty string if we run out
                cell_content = lexicon_entries[index] if index < num_entries else '' 
                row.append(cell_content)
            table_data.append(row)

        # Table Creation and Styling
        lexicon_table = Table(table_data)
        lexicon_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 18), # Spacing between columns
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))

        Story.append(lexicon_table)
    else:
        Story.append(Paragraph(lexicon_entries[0], styles['Code']))
    
    # --- 6. Build the PDF ---
    doc.build(Story)
    print(f"\nPDF Report successfully generated: {filename}")


if __name__ == "__main__":

    today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    filename = f"le_monde_headlines_{today_str}.pdf"
    runtime_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(runtime_dir, '..', 'Files')
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, filename)

    headlines = fetch_and_process_headlines()
    lexicon = get_lexicon(headlines)
    generate_screamsheet_pdf(headlines, lexicon, output_file_path)
