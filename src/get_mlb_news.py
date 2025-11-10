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
import feedparser
import os
from typing import List, Dict, Tuple
from get_game_summary import NewsStorySummarizer
from dotenv import load_dotenv
load_dotenv()

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

RSS_URL = 'https://feeds.feedburner.com/MlbTradeRumors'
FAVORITE_TEAMS = ['Phillies', 'Padres', 'Yankees']
# Priority mapping: 0=Phillies, 1=Padres, 2=Yankees
TEAM_PRIORITY = {team: i for i, team in enumerate(FAVORITE_TEAMS)}
MAX_ARTICLES = 4
SLOTS = [
    'Section 1', 
    'Section 2', 
    'Section 3', 
    'Section 4'
]
EXCLUSION_KEYWORDS = [
    'Top 50', 'Contest', 'Prediction', 'Subscribers', 'Email List', 
    'Presents Our', 'Podcast', 'Live Chat', 'Q&A', 'Ask Us Anything', 
    'Best of', 'MLBTR Chat', 'Front Office' # Added 'Front Office' for potential chat content
]
# ------------------------------

def is_garbage(entry: Dict) -> bool:
    """Checks if an article entry contains blacklisted promotional keywords."""
    title = entry.get('title', '').lower()
    summary = entry.get('summary', '').lower()
    
    # Combine check on both title and summary for any exclusion keywords
    for keyword in EXCLUSION_KEYWORDS:
        if keyword.lower() in title or keyword.lower() in summary:
            return True
    return False


def fetch_and_filter_articles() -> List[Dict]:
    """
    Fetches, filters (removes garbage), and prioritizes up to 4 articles.
    """
    feed = feedparser.parse(RSS_URL)
    
    # 1. Filter out garbage before starting the selection process
    clean_entries = [entry for entry in feed.entries if not is_garbage(entry)]
    
    # --- The rest of the logic remains the same, but operates on clean_entries ---
    final_selection = [None] * MAX_ARTICLES 
    selected_guids = set() 
    
    # 2. Fill Team Slots (Priority 1, 2, 3)
    for priority in sorted(TEAM_PRIORITY.values()):
        team_name = FAVORITE_TEAMS[priority]
        slot_index = priority + 1 
        
        for entry in clean_entries: # Use the filtered list
            title = entry.get('title', '')
            guid = entry.get('link', '') 

            if guid not in selected_guids and team_name in title:
                final_selection[slot_index] = entry
                selected_guids.add(guid)
                break 

    # 3. Fill League/General Slot (Index 0) and any Remaining Empty Slots
    remaining_entries = [entry for entry in clean_entries if entry.get('link', '') not in selected_guids]
    
    fill_index = 0
    entry_index = 0
    
    while fill_index < MAX_ARTICLES and entry_index < len(remaining_entries):
        if final_selection[fill_index] is None:
            entry = remaining_entries[entry_index]
            final_selection[fill_index] = entry
            selected_guids.add(entry.get('link', ''))
            entry_index += 1
            fill_index += 1
        else:
            fill_index += 1

    # 4. Format Output for Summarization
    output_list = []
    for i, entry in enumerate(final_selection):
        if entry is not None:
            output_list.append({'slot': SLOTS[i], 'entry': entry})
            
    return output_list

# --- Main Orchestration (Example) ---
def generate_news_sections(news_summarizer) -> Dict[str, str]:
    """
    Fetches articles, summarizes them, and returns a dictionary ready for PDF layout.
    """
    articles_to_summarize = fetch_and_filter_articles()
    
    final_output = {}
    
    for item in articles_to_summarize:
        entry = item['entry']
        slot = item['slot']
        
        title = entry.get('title', 'No Title')
        
        # Use the article summary or description as the content to be summarized
        content_to_summarize = entry.get('summary', entry.get('description', title))

        # --- Call the Gemini API for the final text ---
        summary_text = news_summarizer.get_accessible_summary(
            title=title,
            content=content_to_summarize
        )
        
        # The key is the page slot, the value is the final summarized text block
        final_output[slot] = {"title": title, "text": summary_text}
        
    return final_output


def generate_mlb_report(stories, filename="mlb_report.pdf"):
    """
    Generates a PDF report with game scores in two top columns and a standings grid at the bottom.

    Args:
        games (list): A list of dictionaries, where each dictionary represents a game.
        standings_df (pd.DataFrame): A DataFrame of team standings, assumed to be pre-sorted.
        filename (str): The name of the output PDF file.
    """
    # --- Adjust margins here ---
    margin = 36 # 0.5 inches in points
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin
    )
    story = []

    # Create a heading for the summary
    summary_heading_style = ParagraphStyle(
        name="SummaryHeading",
        parent=styles['h3'],
        fontName='Helvetica-Bold',
        fontSize=14,
        spaceAfter=12,
    )
    
    # Add the game summary text as a Paragraph
    summary_text_style = ParagraphStyle(
        name="SummaryText",
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
    )

    story_1 = stories["Section 1"]
    story_2 = stories["Section 2"]
    story_3 = stories["Section 3"]
    story_4 = stories["Section 4"]

    summary_1 = [
        Paragraph(story_1["title"], summary_heading_style),
        Paragraph(story_1["text"], summary_text_style)
    ]
    summary_2 = [
        Paragraph(story_2["title"], summary_heading_style),
        Paragraph(story_2["text"], summary_text_style)
    ]
    summary_3 = [
        Paragraph(story_3["title"], summary_heading_style),
        Paragraph(story_3["text"], summary_text_style)
    ]
    summary_4 = [
        Paragraph(story_4["title"], summary_heading_style),
        Paragraph(story_4["text"], summary_text_style)
    ]


    # --- Build the PDF ---
    story.append(Paragraph("MLB Scream Sheet", TITLE_STYLE))
    story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    story.append(Spacer(1, 12))
    story.extend(summary_1)
    story.append(Spacer(1, 24))
    story.extend(summary_2)
    story.append(PageBreak())
    story.extend(summary_3)
    story.append(Spacer(1, 24))
    story.extend(summary_4)
    doc.build(story)
    print(f"PDF file '{filename}' has been created.")


def main():

    today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    filename = f"MLB_News_{today_str}.pdf"
    runtime_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(runtime_dir, '..', 'Files')
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, filename)

    try:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
    except Exception as ex:
        print(f"No Gemini API Key found: {ex}")
        gemini_api_key = None
    news_summarizer = NewsStorySummarizer(gemini_api_key)
    
    final_output = generate_news_sections(news_summarizer)
    generate_mlb_report(final_output, output_file_path)
    

if __name__ == "__main__":
    main()
