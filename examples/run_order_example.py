"""Example: calling screamsheet from an external orchestration layer.

This script simulates exactly what an orchestration layer would do:
import screamsheet, construct a ScreamsheetOrder, call run_order().

Run with:
    uv run python examples/run_order_example.py
"""
from datetime import datetime

import screamsheet
from screamsheet.order import (
    NHLOrderOptions,
    OutputOrderOptions,
    ScreamsheetOrder,
    TeamEntry,
)

# Build a minimal order: NHL only, output to /tmp.
order = ScreamsheetOrder(
    output=OutputOrderOptions(directory="/tmp/screamsheet_example"),
    nhl=NHLOrderOptions(
        favorite_teams=[
            TeamEntry(id=4, name="Philadelphia Flyers"),
            TeamEntry(id=7, name="Buffalo Sabres"),
        ]
    ),
)

# run_order() generates only the sheets whose keys are set.
result = screamsheet.run_order(order, today=datetime.now())
print(f"Result: {result}")
