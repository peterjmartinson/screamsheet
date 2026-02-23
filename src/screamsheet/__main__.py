"""
Main entry point for the screamsheet system.

This demonstrates how to use the new modular screamsheet architecture.

Example usage:
    # Create an MLB screamsheet for the Phillies
    from screamsheet import ScreamsheetFactory
    
    sheet = ScreamsheetFactory.create_mlb_screamsheet(
        output_filename='phillies_daily.pdf',
        team_id=ScreamsheetFactory.MLB_PHILLIES,
        team_name='Philadelphia Phillies'
    )
    sheet.generate()
    
    # Create an NHL screamsheet for the Flyers
    sheet = ScreamsheetFactory.create_nhl_screamsheet(
        output_filename='flyers_daily.pdf',
        team_id=ScreamsheetFactory.NHL_FLYERS,
        team_name='Philadelphia Flyers'
    )
    sheet.generate()
    
    # Create a news screamsheet
    sheet = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
        output_filename='mlb_news.pdf',
        favorite_teams=['Phillies', 'Padres', 'Yankees']
    )
    sheet.generate()
"""
from .factory import ScreamsheetFactory
from .sports import MLBScreamsheet, NHLScreamsheet, NFLScreamsheet, NBAScreamsheet
from .news import MLBTradeRumorsScreamsheet

__all__ = [
    'ScreamsheetFactory',
    'MLBScreamsheet',
    'NHLScreamsheet',
    'NFLScreamsheet',
    'NBAScreamsheet',
    'MLBTradeRumorsScreamsheet',
]


def main():
    """
    Example of how to generate screamsheets.
    
    Uncomment the sections you want to generate.
    """
    
    # Generate MLB screamsheet for Blue Jays
    # mlb_sheet = ScreamsheetFactory.create_mlb_screamsheet(
    #     output_filename='Files/mlb_bluejays.pdf',
    #     team_id=ScreamsheetFactory.MLB_BLUEJAYS,
    #     team_name='Toronto Blue Jays'
    # )
    # mlb_sheet.generate()
    # print("Generated MLB screamsheet")
    
    # Generate NHL screamsheet for Flyers
    # nhl_sheet = ScreamsheetFactory.create_nhl_screamsheet(
    #     output_filename='Files/nhl_flyers.pdf',
    #     team_id=ScreamsheetFactory.NHL_FLYERS,
    #     team_name='Philadelphia Flyers'
    # )
    # nhl_sheet.generate()
    # print("Generated NHL screamsheet")
    
    # Generate NFL screamsheet (no specific team - just scores and standings)
    # nfl_sheet = ScreamsheetFactory.create_nfl_screamsheet(
    #     output_filename='Files/nfl_weekly.pdf'
    # )
    # nfl_sheet.generate()
    # print("Generated NFL screamsheet")
    
    # Generate NBA screamsheet
    # nba_sheet = ScreamsheetFactory.create_nba_screamsheet(
    #     output_filename='Files/nba_daily.pdf'
    # )
    # nba_sheet.generate()
    # print("Generated NBA screamsheet")
    
    # Generate MLB Trade Rumors news screamsheet
    # news_sheet = ScreamsheetFactory.create_mlb_trade_rumors_screamsheet(
    #     output_filename='Files/mlb_trade_rumors.pdf',
    #     favorite_teams=['Phillies', 'Padres', 'Yankees'],
    #     max_articles=4,
    #     include_weather=True
    # )
    # news_sheet.generate()
    # print("Generated MLB Trade Rumors screamsheet")
    
    print("Uncomment the sections in main() to generate screamsheets")


if __name__ == "__main__":
    main()
