#!/usr/bin/env python3
"""
Example script demonstrating the new modular screamsheet system.

This script shows various ways to generate screamsheets using the new architecture.
"""

from datetime import datetime
import sys
import os

# Add src to path so we can import screamsheet
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from screamsheet import ScreamsheetFactory


def generate_all_sports():
    """Generate screamsheets for all sports."""
    
    print("Generating sports screamsheets...")
    
    # MLB - Blue Jays
    print("  - MLB (Blue Jays)...")
    mlb = ScreamsheetFactory.create_mlb_screamsheet(
        output_filename='Files/mlb_bluejays_modular.pdf',
        team_id=ScreamsheetFactory.MLB_BLUEJAYS,
        team_name='Toronto Blue Jays'
    )
    mlb.generate()
    
    # NHL - Flyers
    print("  - NHL (Flyers)...")
    nhl = ScreamsheetFactory.create_nhl_screamsheet(
        output_filename='Files/nhl_flyers_modular.pdf',
        team_id=ScreamsheetFactory.NHL_FLYERS,
        team_name='Philadelphia Flyers'
    )
    nhl.generate()
    
    # NFL - Weekly scores and standings only
    print("  - NFL (Weekly)...")
    nfl = ScreamsheetFactory.create_nfl_screamsheet(
        output_filename='Files/nfl_weekly_modular.pdf'
    )
    nfl.generate()
    
    # NBA - Daily scores and standings only
    print("  - NBA (Daily)...")
    nba = ScreamsheetFactory.create_nba_screamsheet(
        output_filename='Files/nba_daily_modular.pdf'
    )
    nba.generate()
    
    print("Sports screamsheets generated!")


def generate_news():
    """Generate news screamsheet."""
    
    print("Generating news screamsheet...")
    
    news = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
        output_filename='Files/mlb_trade_rumors_modular.pdf',
        favorite_teams=['Phillies', 'Padres', 'Yankees'],
        max_articles=4,
        include_weather=True
    )
    news.generate()
    
    print("News screamsheet generated!")


def generate_custom_example():
    """
    Example of creating a custom screamsheet with specific configuration.
    """
    
    print("Generating custom screamsheet...")
    
    # Create a screamsheet for a specific date
    custom_date = datetime(2026, 1, 8)
    
    mlb = ScreamsheetFactory.create_mlb_screamsheet(
        output_filename='Files/mlb_custom_date.pdf',
        team_id=ScreamsheetFactory.MLB_PHILLIES,
        team_name='Philadelphia Phillies',
        date=custom_date
    )
    mlb.generate()
    
    print(f"Custom screamsheet generated for {custom_date.strftime('%Y-%m-%d')}!")


def main():
    """Main entry point."""
    
    print("=== Screamsheet Generation Example ===\n")
    
    # Create Files directory if it doesn't exist
    os.makedirs('Files', exist_ok=True)
    
    # Choose what to generate
    choice = input("""
What would you like to generate?
1. All sports screamsheets
2. News screamsheet
3. Custom example (specific date)
4. Everything
5. Exit

Enter choice (1-5): """).strip()
    
    if choice == '1':
        generate_all_sports()
    elif choice == '2':
        generate_news()
    elif choice == '3':
        generate_custom_example()
    elif choice == '4':
        generate_all_sports()
        print()
        generate_news()
        print()
        generate_custom_example()
    elif choice == '5':
        print("Exiting...")
        return
    else:
        print("Invalid choice. Exiting...")
        return
    
    print("\n=== Done! ===")


if __name__ == "__main__":
    main()
