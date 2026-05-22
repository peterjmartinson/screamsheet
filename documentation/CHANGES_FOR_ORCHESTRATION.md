# Screamsheet Engine Changes for Subscriber Orchestration

This document describes the changes required in the `screamsheet` repo to
support the `screamsheet-subscribers` orchestration system (Phase 2).

See `screamsheet-subscribers/documentation/ORCHESTRATION_PLAN.md` for the
overall architecture.

---

## Change 1 — `ScreamsheetResult` dataclass (`order.py`)

Add the following dataclass to `src/screamsheet/order.py`:

```python
from dataclasses import dataclass, field

@dataclass
class ScreamsheetResult:
    """Return value of runner.run_order().

    subscriber_name: human-readable label for log / summary email
    sheets_generated: list of PDF filenames (basename only) written to disk
    options_summary: sheet_key -> list of option strings for the summary email
                     e.g. {"mlb": ["Phillies", "Nationals"],
                            "mlb_news": ["Philadelphia PA"]}
    errors: non-fatal error messages; empty list == clean run
    """
    subscriber_name: str
    sheets_generated: list[str] = field(default_factory=list)
    options_summary: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
```

`subscriber_name` is supplied by the caller (the orchestrator sets it to the
subscriber's name from their YAML file).

---

## Change 2 — `run_order()` return type and fault tolerance (`runner.py`)

Current signature:
```python
def run_order(order: ScreamsheetOrder, today: datetime | None = None) -> str:
```

New signature:
```python
def run_order(
    order: ScreamsheetOrder,
    today: datetime | None = None,
    subscriber_name: str = "",
) -> ScreamsheetResult:
```

**Behaviour changes:**

1. **Per-sheet exception isolation**: each sheet is generated inside a
   `try/except`. If a sheet raises, the exception message is appended to
   `result.errors` and the loop continues to the next sheet.
   A failed sheet does NOT appear in `result.sheets_generated`.

2. **Return value**: return a `ScreamsheetResult` with all fields populated
   instead of the literal string `"success"`.

3. **`options_summary` population**: after each successful sheet, append a
   human-readable list of options. Minimum requirement:
   - Sport sheets: list of team names (from `TeamEntry.name`)
   - News/weather sheets: `location_name` string (e.g. `"Bryn Mawr, PA"`) if weather is present
   - Boolean sheets: `["enabled"]`

---

## Change 3 — Write PDFs directly to `output.directory` (`runner.py`)

Currently `run_order()` writes PDFs to `Files/<name>_<date>.pdf` and then
copies them to `output.directory`.

**Change**: write directly to `output.directory` and remove the intermediate
`Files/` write + copy step.

The orchestrator always sets `order.output.directory` to a dedicated staging
subdirectory (e.g. `staging/peter_20260519_063000/`). The `Files/` directory
should no longer be used as an intermediary.

> **Note**: if any other callers (e.g. `examples/run_order_example.py`,
> `screamsheet.sh`) rely on `Files/` being populated as a side effect, update
> those callers to set an explicit `output.directory`.

---

## Change 4 — Verify `weather=None` guard in renderers (`order.py` already done)

`MLBNewsOrderOptions`, `MLBTradeRumorsOrderOptions`, and `PresidentialOrderOptions`
already declare `weather: WeatherLocationOptions | None = None` in `order.py`
(no change needed there).

What must be verified: when `weather=None`, does the renderer skip the weather
section silently? If not, add a guard:

```python
if options.weather is not None:
    render_weather_section(canvas, options.weather, ...)
```

With `peter-test.yaml` always supplying `lat`/`lon`/`location_name` for all
weather-capable sheets, this path may be untested. Add a test that passes
`weather=None` and confirms the PDF renders without error.

---

## Summary of files to change

| File | Change |
|------|--------|
| `src/screamsheet/order.py` | Add `ScreamsheetResult` dataclass |
| `src/screamsheet/runner.py` | Update `run_order()` return type, add `subscriber_name` param, add per-sheet fault tolerance, write directly to `output.directory` |
| Relevant renderer(s) | Verify/add `weather=None` guard (see Change 4) |
| `examples/run_order_example.py` | Update to set explicit `output.directory` |
| `tests/` | Add tests for `ScreamsheetResult`, fault tolerance, direct output path, `weather=None` render |

---

## Acceptance criteria

- `run_order()` returns a `ScreamsheetResult` (not `"success"`)
- A sheet that raises an exception does not prevent other sheets from running
- The raised exception message appears in `result.errors`
- PDFs appear in `order.output.directory`, not in `Files/`
- A news sheet order with `weather=None` renders without error and without a
  weather section
- All existing tests remain green
