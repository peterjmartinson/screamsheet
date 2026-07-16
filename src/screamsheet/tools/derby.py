"""CLI utility for generating the MLB Home Run Derby PDF Screamsheet or Markdown summary."""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from screamsheet.factory import ScreamsheetFactory
from screamsheet.providers.mlb_provider import MLBDataProvider
from screamsheet.renderers.derby_markdown import format_derby_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MLB Home Run Derby PDF Screamsheet or Markdown summary.")
    parser.add_argument(
        "--date",
        type=str,
        help="Date of the Home Run Derby in YYYY-MM-DD format (defaults to today or yesterday).",
    )
    parser.add_argument(
        "--game-pk",
        type=int,
        help="Explicit MLB API gamePk for the Home Run Derby (optional).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output filepath for the generated PDF Screamsheet (default: Files/Home_Run_Derby_YYYY-MM-DD.pdf).",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Print the morning newsletter Markdown summary instead of generating a PDF.",
    )
    args = parser.parse_args()

    provider = MLBDataProvider()
    target_date = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now()
    
    game_pk = args.game_pk
    if game_pk is None:
        game_pk = provider.get_derby_game_pk(target_date)
        if game_pk is None and not args.date:
            target_date = target_date - timedelta(days=1)
            game_pk = provider.get_derby_game_pk(target_date)

    if game_pk is None:
        date_str = target_date.strftime("%Y-%m-%d")
        print(f"Error: Could not find an MLB Home Run Derby event on or around {date_str}. Please verify the date or provide --game-pk.", file=sys.stderr)
        sys.exit(1)

    date_str = target_date.strftime("%Y-%m-%d")
    print(f"Fetching Home Run Derby data for gamePk={game_pk} (Date: {date_str})...\n", file=sys.stderr)

    if args.markdown:
        data = provider.get_home_run_derby_summary(date=target_date, game_pk=game_pk)
        if not data:
            print("Error: No Home Run Derby data returned from API.", file=sys.stderr)
            sys.exit(1)
        markdown = format_derby_markdown(data)
        print(markdown)
    else:
        output_file = args.output or f"Files/Home_Run_Derby_{date_str}.pdf"
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        sheet = ScreamsheetFactory.create_home_run_derby_screamsheet(
            output_filename=output_file,
            date=target_date,
            game_pk=game_pk,
        )
        pdf_path = sheet.generate()
        print(f"🎉 Successfully generated printable PDF Screamsheet: {pdf_path}")


if __name__ == "__main__":
    main()
