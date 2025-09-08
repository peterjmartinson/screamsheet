import os
from datetime import datetime
from mlb import MLBDataFetcher
from report_content import create_scores_flowables, create_standings_flowables
from report_generator import PDFReportGenerator

scores_filename = "scores_20250818.json"
standings_filename = "standings_20250818.csv"

if __name__ == "__main__":
    # 1. Instantiate the data fetcher
    data_fetcher = MLBDataFetcher()

    # 2. Fetch the raw data
    section_one_data = data_fetcher.get_scores_last_24_hours(filename=scores_filename)
    section_two_data = data_fetcher.get_standings(2025, filename=standings_filename)

    # 3. Create flowables for each section
    section_one_flowables = create_scores_flowables(section_one_data)
    section_two_flowables = create_standings_flowables(section_two_data)

    # 4. Prepare output path
    today_str = datetime.utcnow().strftime("%Y%m%d")
    filename = f"MLB_Scream_Sheet_{today_str}.pdf"
    runtime_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(runtime_dir, '..', 'Files')
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, filename)

    # 5. Instantiate the generic report generator
    report_generator = PDFReportGenerator(output_file_path)

    # 6. Build the report with a specified layout
    # To use a one-column layout:
    report_generator.generate_report(
        title="MLB Scream Sheet",
        sections=[section_one_flowables, section_two_flowables],
        layout='one_column'
    )

    # To use a two-column layout:
    # report_generator.generate_report(
    #     title="MLB Scream Sheet",
    #     sections=[section_one_flowables, section_two_flowables],
    #     layout='two_column'
    # )
