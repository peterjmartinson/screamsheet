from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,  # <-- Import the PageBreak flowable
)
import feedparser
import os
from typing import List, Dict
from get_llm_summary import NewsSummarizer
from print_weather import generate_weather_report
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

NEWS_COLUMN_STYLE = TableStyle([
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('LEFTPADDING', (0,0), (0,0), 0),
    ('RIGHTPADDING', (1,0), (1,0), 0),
    ('RIGHTPADDING', (0,0), (0,0), 10),
    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ('TOPPADDING', (0,0), (-1,-1), 0),
])

SUMMARY_HEADING_STYLE = ParagraphStyle(
    name="SummaryHeading",
    parent=styles['h3'],
    fontName='Helvetica-Bold',
    fontSize=14,
    spaceAfter=12,
)

SUMMARY_TEXT_STYLE = ParagraphStyle(
    name="SummaryText",
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=12,
)

RSS_URL = 'https://feeds.feedburner.com/MlbTradeRumors'
FAVORITE_TEAMS = ['Phillies', 'Padres', 'Yankees']
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
    'Best of', 'MLBTR Chat', 'Front Office'
]

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
def generate_news_sections(news_summarizer, dummy=False) -> Dict[str, str]:
    """
    Fetches articles, summarizes them, and returns a dictionary ready for PDF layout.
    """
    if dummy:
        final_output = {
            'Section 1': {'title': 'Pirates, Noah Murdock Agree To Minor League Deal', 'text': 'The Pittsburgh Pirates have inked free agent reliever Noah Murdock to a minor league deal, as he announced on social media last week. The 6-foot-8 right-hander made his MLB debut this season as a Rule 5 draft pick with the Oakland Athletics, but his performance was anything but stellar. Over five appearances, Murdock posted a brutal 9.00 ERA, walking more batters than he struck out and generally looking like a guy who forgot his lucky socks.\n\nDigging into the freshest dirt on X—formerly Twitter—reveals some juicy fan reactions that add a layer of hilarity to this signing. According to posts from MLB insider Jeff Passan and fan accounts like @PiratesProspects, Murdock\'s towering frame has sparked memes comparing him to a giraffe trying to pitch, with one viral thread joking that he\'s "taller than the Pirates\' playoff chances." Sources like The Athletic\'s transaction tracker confirm the deal was low-risk, but users are already roasting the team\'s desperation for bullpen help.\n\nHell, if Murdock can turn things around in the minors, it might just be the damn miracle Pittsburgh needs after their shitty season. Fans are buzzing with cautious optimism, but let\'s be real—this guy\'s debut was a fucking disaster, so expect more laughs if he flames out again. Still, in the wild world of baseball, even a long-shot like this could spark some unexpected fireworks.'},
            'Section 2': {'title': 'Phillies Claim Pedro León', 'text': "The Philadelphia Phillies have snagged outfielder Pedro León off waivers from the Baltimore Orioles, boosting their roster from 33 to 34 players. The move was first reported by Francys Romero of BeisbolFR before the official announcement, following the Orioles' decision to designate the 28-year-old for assignment just days ago. Once a promising prospect, León's career has seen its ups and downs, but this could be a fresh start in Philly.\n\nLeón, who turns 28 in May, was signed by the Astros as an international free agent back in 2020 with high expectations, but injuries and inconsistent performance have kept him from cracking the majors consistently. He's shown flashes of power in the minors, hitting 20 homers in Triple-A last season, though his batting average hovered around .240—solid but not superstar material. Phillies fans are buzzing about the low-risk pickup, hoping he adds depth to an outfield that's been hit or miss.\n\nNow, let's get real: this guy's been bouncing around like a damn pinball, from Houston to Baltimore and now Philly—what the hell is next, a stint in Japan? Scouring X (formerly Twitter), insider Jeff Passan noted León's raw tools could make him a steal if he stays healthy, but fan reactions are split, with some calling it a bullshit desperation move for a team chasing playoffs. Shit, if he doesn't pan out, the Phillies might as well have claimed a bag of peanuts—hilarious how prospects flame out, right?"},
            'Section 3': {'title': 'Rangers Non-Tender Adolis Garcia, Jonah Heim', 'text': 'The Texas Rangers just dropped a bombshell by non-tendering contracts to outfielder Adolis Garcia, catcher Jonah Heim, and relievers Josh Sborz and Jacob Webb. These players were all arbitration-eligible for the last time, heading into their final year under team control. Instead of negotiating deals, the Rangers cut them loose, making them instant free agents.\n\nGarcia, a fan favorite and power hitter, slugged 39 homers in 2023 but saw his numbers dip this year amid injuries. Heim, the steady backstop, earned All-Star nods but struggled offensively lately. Sborz and Webb provided bullpen depth, though their inconsistencies might explain the team\'s bold move to reshape the roster.\n\nOver on X, the dirt is flying fast—Rangers insider Jeff Wilson tweeted that Garcia\'s camp was "pissed as hell" about the snub, citing sources close to the player who called it a "fucking betrayal after his MVP-level playoff run." Fans are roasting the front office, with one viral post from @TexasFanatic89 joking that the team is "shitting the bed harder than a hangover brunch," while MLB analyst Ken Rosenthal reports whispers of budget cuts forcing this "balls-to-the-wall gamble" on new talent.'},
            'Section 4': {'title': 'American League Non-Tenders: 11/21/25', 'text': 'The American League wrapped up its non-tender decisions on November 21, 2025, with teams making their calls on arbitration-eligible players. It was a surprisingly subdued night, as most clubs held onto their rosters without major shakeups. The only real drama came from the Texas Rangers, who cut ties with some notable names, sending them straight into free agency without the hassle of waivers.\n\nA handful of squads trimmed the edges of their 40-man rosters by non-tendering pre-arbitration players, clearing space for potential offseason moves. This keeps the market buzzing with fresh talent, though nothing earth-shattering emerged from the announcements. Fans were left wondering if bigger trades or signings are lurking just around the corner.\n\nNow, for the freshest dirt on X—formerly Twitter—where baseball insiders are spilling the beans: According to MLB Network\'s Jon Heyman, the Rangers\' decision to dump those marquee players reeks of salary dumping, with one source calling it "a chickenshit move to avoid arbitration hell." Shit, if that\'s not a sign of tighter purses ahead, I don\'t know what is—expect some pissed-off agents to make this offseason a goddamn circus.'}
        }
        return final_output

    articles_to_summarize = fetch_and_filter_articles()
    
    final_output = {}
    
    for item in articles_to_summarize:
        entry = item['entry']
        slot = item['slot']
        
        title = entry.get('title', 'No Title')
        
        # Use the article summary or description as the content to be summarized
        content_to_summarize = entry.get('summary', entry.get('description', title))
        story = {'title': title, 'summary': content_to_summarize}

        summary_text = news_summarizer.generate_summary(llm_choice='grok', data=story)
        
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

    col_width = doc.width / 2.0

    story = []
    summaries = []
    for key, section in stories.items():
        summary = [Paragraph(section["title"], SUMMARY_HEADING_STYLE)]
        summary_paragraphs = [p for p in section["text"].split('\n\n') if p.strip()]
        for paragraph in summary_paragraphs:
            summary.append(Paragraph(paragraph, SUMMARY_TEXT_STYLE))
            summary.append(Spacer(1, 12))
        summaries.append(summary)

    row_1_data = [[summaries[0], summaries[1]]]
    table_1 = Table(row_1_data, colWidths=[col_width, col_width])
    table_1.setStyle(NEWS_COLUMN_STYLE)

    row_2_data = [[summaries[2], summaries[3]]]
    table_2 = Table(row_2_data, colWidths=[col_width, col_width])
    table_2.setStyle(NEWS_COLUMN_STYLE)

    weather = generate_weather_report()

    # --- Build the PDF ---
    story.append(Paragraph("MLB Scream Sheet", TITLE_STYLE))
    story.append(Paragraph(datetime.today().strftime("%A, %B %#d, %Y"), SUBTITLE_STYLE))
    story.append(Spacer(1, 20))
    story.append(weather)
    story.append(Spacer(1, 12))
    story.append(table_1)
    story.append(PageBreak())
    story.append(table_2)
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
    news_summarizer = NewsSummarizer(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "MOCK_GEMINI_KEY"),
        grok_api_key=os.getenv("GROK_API_KEY", "MOCK_GROK_KEY")
    )
    
    stories = generate_news_sections(news_summarizer)
    generate_mlb_report(stories, output_file_path)

if __name__ == "__main__":
    main()
