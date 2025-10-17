import pytest
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import black
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.units import inch
from typing import Dict, Union, Any

# --- Fixture for Shared Setup ---


@pytest.fixture
def reportlab_styles() -> Dict[str, Union[ParagraphStyle, TableStyle, Any]]:
    """Fixture to provide necessary styles and test data for all tests."""
    styles = getSampleStyleSheet()

    # 1. Custom Paragraph Style
    header_style = styles['h1'].clone('CustomHeader')
    header_style.alignment = TA_CENTER

    # 2. Table Data
    table_data = [['Col 1', 'Col 2'], ['Data A', 'Data B']]

    # 3. Table Style
    table_style = TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, black),
        ('BACKGROUND', (0, 0), (-1, 0), black)
    ])

    return {
        'styles': styles,
        'header_style': header_style,
        'table_data': table_data,
        'table_style': table_style,
    }

# --- Test Functions ---

def test_paragraph_style_application(reportlab_styles: Dict[str, Any]):
    """Tests that custom ParagraphStyle attributes are correctly applied."""
    styles = reportlab_styles['styles']
    header_style = reportlab_styles['header_style']

    text = "This is the Title Text"
    p = Paragraph(text, header_style)

    # Assert
    # Check that the paragraph object exists
    assert isinstance(p, Paragraph)
    # Check a key style attribute (alignment is centered)
    assert p.style.alignment == TA_CENTER
    # Check font name integrity
    assert p.style.fontName == 'Helvetica-Bold'  # Default for h1


def test_table_creation_and_styling(reportlab_styles: Dict[str, Any]):
    """Tests that Table and TableStyle are created correctly."""
    table_data = reportlab_styles['table_data']
    table_style = reportlab_styles['table_style']

    t = Table(table_data)
    t.setStyle(table_style)

    # Assert
    assert isinstance(t, Table)
    # Check that a style was applied (table has calculated column widths)
    assert t._colWidths is not None
    # Check number of rows matches the data
    assert len(t._argW) == 2


def test_flowable_height_calculation(reportlab_styles: Dict[str, Any]):
    """Tests that wrap() correctly calculates the required height for layout logic."""
    styles = reportlab_styles['styles']

    # Arrange
    fixed_width = 6.5 * inch  # Standard width for a letter page with 1-inch margins

    # Long paragraph that must wrap
    long_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua." * 5
    p = Paragraph(long_text, styles['Normal'])

    # Act
    # The height value (1000) is arbitrary, we only care about the returned required_height
    p_required_width, p_required_height = p.wrapOn(None, fixed_width, 1000)

    # Assert
    # The height must be greater than the standard line height (e.g., more than twice the font size)
    assert p_required_height > styles['Normal'].fontSize * 2
    # Ensure that the flowable width required is exactly the fixed width provided
    # pytest's assert almost equal
    assert p_required_width == pytest.approx(fixed_width)
