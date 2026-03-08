"""NHL box score fetching, parsing, and table rendering.

Migrated from src/get_box_score_nhl.py during modularisation cleanup.
"""
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass

from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors


@dataclass
class PlayerSkater:
    name: str
    goals: int
    assists: int
    points: int
    shots_on_goal: int
    pim: int


@dataclass
class PlayerGoalie:
    name: str
    shots_against: int
    saves: int
    save_percentage: Optional[float]


def get_game_boxscore(game_pk: int) -> Optional[Dict[str, Any]]:
    """Fetch box score data for a completed NHL game."""
    try:
        boxscore_url = f"https://api-web.nhle.com/v1/gamecenter/{game_pk}/boxscore"
        response = requests.get(boxscore_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching NHL box score data: {e}")
        return None


def parse_nhl_boxscore(
    boxscore_data: Optional[Dict[str, Any]], team_id: int
) -> Dict[str, List[Any]]:
    """Parse NHL box score data into skater and goalie stat lists."""
    if not boxscore_data:
        return {'skater_stats': [], 'goalie_stats': []}

    target_team_code = (
        "homeTeam" if boxscore_data['homeTeam']['id'] == team_id else "awayTeam"
    )

    raw_skaters = (
        boxscore_data['playerByGameStats'][target_team_code]['forwards']
        + boxscore_data['playerByGameStats'][target_team_code]['defense']
    )

    skater_stats: List[PlayerSkater] = []
    for player in raw_skaters:
        skater_stats.append(PlayerSkater(
            name=player['name']['default'],
            goals=player.get('goals', 0),
            assists=player.get('assists', 0),
            points=player.get('points', 0),
            shots_on_goal=player.get('shots', 0),
            pim=player.get('pim', 0),
        ))

    goalie_stats: List[PlayerGoalie] = []
    raw_goalies = boxscore_data['playerByGameStats'][target_team_code]['goalies']
    for player in raw_goalies:
        shots_against = player.get('shotsAgainst', 0)
        saves = player.get('saves', 0)
        sv_pct: Optional[float] = (
            saves / shots_against if shots_against and shots_against > 0 else None
        )
        goalie_stats.append(PlayerGoalie(
            name=player['name']['default'],
            shots_against=shots_against,
            saves=saves,
            save_percentage=sv_pct,
        ))

    return {'skater_stats': skater_stats, 'goalie_stats': goalie_stats}


def create_nhl_boxscore_tables(
    boxscore_stats: Dict[str, List[Union[PlayerSkater, PlayerGoalie]]]
) -> Dict[str, Table]:
    """Create ReportLab Table objects for NHL skater and goalie stats."""
    skater_stats: List[PlayerSkater] = boxscore_stats['skater_stats']
    goalie_stats: List[PlayerGoalie] = boxscore_stats['goalie_stats']

    skater_data = [["Skater", "G", "A", "P", "SOG", "PIM"]]
    for player in skater_stats:
        skater_data.append([
            player.name, player.goals, player.assists,
            player.points, player.shots_on_goal, player.pim,
        ])

    skater_table = Table(skater_data)
    skater_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    goalie_data = [["Goaltender", "SA", "SV", "SV%"]]
    for player in goalie_stats:
        goalie_data.append([
            player.name, player.shots_against, player.saves, player.save_percentage,
        ])

    goalie_table = Table(goalie_data)
    goalie_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    return {'skater_table': skater_table, 'goalie_table': goalie_table}


def get_nhl_boxscore(team_id: int, game_pk: int) -> Dict[str, Table]:
    """Fetch, parse, and render NHL box score tables for a given team and game."""
    box_score_data = get_game_boxscore(game_pk)

    if not box_score_data:
        return {
            'skater_table': Table([['No Skater Data Found']]),
            'goalie_table': Table([['No Goalie Data Found']]),
        }

    parsed_stats = parse_nhl_boxscore(box_score_data, team_id)
    return create_nhl_boxscore_tables(parsed_stats)
