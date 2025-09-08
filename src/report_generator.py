from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, Spacer, Paragraph, TableStyle
# from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Frame, PageTemplate, FrameBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from report_content import TITLE_STYLE, SUBTITLE_STYLE
from datetime import datetime

class PDFReportGenerator:
    """
    A generic class to generate PDF reports with flexible layouts.
    """
    def __init__(self, filename: str):
        self.filename = filename
        self.doc = SimpleDocTemplate(
            self.filename,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        self.styles = getSampleStyleSheet()

    def generate_report(self, title: str, sections: list, layout: str = 'one_column'):
        """
        Builds the PDF report with a specified layout.
        
        Args:
            title (str): The main title of the report.
            sections (list): A list of lists of reportlab flowables.
            layout (str): 'one_column' or 'two_column'.
        """
        story = []
        
        # Add Title and Date
        story.append(Paragraph(title, TITLE_STYLE))
        story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
        story.append(Spacer(1, 12))

        if layout == 'one_column':
            # Add each section one after another
            for section in sections:
                story.extend(section)
        elif layout == 'two_column':
            # Create a parent table with two columns and add sections to it
            if len(sections) > 2:
                print("Warning: Two-column layout requested but more than two sections provided. Using first two sections.")
            
            # Use a list comprehension to create the table data
            table_data = [[
                sections[0],
                sections[1] if len(sections) > 1 else []
            ]]
            
            # The parent table styles to align content to the top
            parent_table_style = TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ])
            
            # Create the main table with equal column widths
            main_table = Table(table_data, colWidths=[self.doc.width / 2, self.doc.width / 2])
            main_table.setStyle(parent_table_style)
            story.append(main_table)
            
        else:
            print(f"Unsupported layout: '{layout}'. Using 'one_column'.")
            for section in sections:
                story.extend(section)

        self.doc.build(story)
        print(f"PDF saved as: {self.filename}")
