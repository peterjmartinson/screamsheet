# Issue #77 — Define the ScreamsheetOrder Contract

## Background

The screamsheet system is being extended to support an **orchestration layer** — an external Python program that will call screamsheet repeatedly, each time with a different set of options (e.g., different subscribers, different favorite teams, different output locations).

Currently, screamsheet reads its options exclusively from `config.yaml`. The orchestration layer cannot use that model because it needs to pass configuration in-memory at call time, without touching the filesystem.

Screamsheet itself should remain unaware of the orchestration layer. Its job is to accept a well-defined input object, validate it, generate the requested sheets, and return a result.

---

## Goal

Define a strict `ScreamsheetOrder` dataclass (or Pydantic model) that serves as the **only** public interface between any caller and the screamsheet engine. The contract lives inside the `screamsheet` package, and callers construct it themselves.

---

## The Contract

A `ScreamsheetOrder` is a dictionary-like object whose **top-level keys determine which sheets are produced**. If a key is absent, that sheet is not generated — no key means no sheet, no exceptions.

### Top-Level Keys

| Key | Sheet produced | Value type |
|---|---|---|
| `nhl` | NHL Sports / Standings | `NHLOrderOptions` |
| `mlb` | MLB Sports | `MLBOrderOptions` |
| `nba` | NBA Sports | `NBAOrderOptions` |
| `nfl` | NFL Sports | `NFLOrderOptions` |
| `mlb_news` | MLB News | `MLBNewsOrderOptions` |
| `mlb_trade_rumors` | MLB Trade Rumors | `MLBTradeRumorsOrderOptions` |
| `presidential` | Presidential | `PresidentialOrderOptions` |
| `sky` | Sky Tonight | `SkyOrderOptions` |
| `output` | *(global)* | `OutputOrderOptions` — destination directory |

All top-level keys are **optional**. An order with zero sport keys is valid (it simply generates nothing sport-related).

### Per-Sheet Options

Each options type mirrors the corresponding section of `config.yaml`. Initial field definitions:

```python
@dataclass
class TeamEntry:
    id: int
    name: str

@dataclass
class NHLOrderOptions:
    favorite_teams: list[TeamEntry]   # priority-ordered; used for game summary selection

@dataclass
class MLBOrderOptions:
    favorite_teams: list[TeamEntry]
    news_names: list[str]             # short names used to filter news/trade articles

@dataclass
class NBAOrderOptions:
    favorite_teams: list[TeamEntry]

@dataclass
class NFLOrderOptions:
    favorite_teams: list[TeamEntry]

@dataclass
class MLBNewsOrderOptions:
    weather: WeatherLocationOptions | None = None

@dataclass
class MLBTradeRumorsOrderOptions:
    weather: WeatherLocationOptions | None = None

@dataclass
class PresidentialOrderOptions:
    weather: WeatherLocationOptions | None = None

@dataclass
class WeatherLocationOptions:
    lat: float
    lon: float
    location_name: str

@dataclass
class SkyOrderOptions:
    lat: float
    lon: float
    location_name: str

@dataclass
class OutputOrderOptions:
    directory: str
```

### The Order Object

`branding` is **not** part of the order — it is a screamsheet-internal setting read from `config.yaml` at generation time. The orchestration layer has no reason to control it.

```python
@dataclass
class ScreamsheetOrder:
    output: OutputOrderOptions | None = None
    nhl: NHLOrderOptions | None = None
    mlb: MLBOrderOptions | None = None
    nba: NBAOrderOptions | None = None
    nfl: NFLOrderOptions | None = None
    mlb_news: MLBNewsOrderOptions | None = None
    mlb_trade_rumors: MLBTradeRumorsOrderOptions | None = None
    presidential: PresidentialOrderOptions | None = None
    sky: SkyOrderOptions | None = None
```

---

## Entry Point

Add a public function `run_order(order: ScreamsheetOrder) -> str` that:

1. Validates the order object.
2. Iterates only the keys that are present (non-`None`).
3. Generates each requested sheet.
4. Copies output PDFs to `order.output.directory` if provided.
5. Returns `"success"` on completion.

The existing `uv run screamsheet` CLI path should be refactored to **construct a `ScreamsheetOrder` from `config.yaml`** and then call `run_order()` — so the new contract is the single path through the engine.

---

## Extensibility

Adding a new sheet (e.g., `nhl_trade_rumors`) requires three steps:

1. Define a new `NHLTradeRumorsOrderOptions` dataclass in `order.py`.
2. Add `nhl_trade_rumors: NHLTradeRumorsOrderOptions | None = None` to `ScreamsheetOrder`.
3. Register the sheet in the dispatch map inside `run_order()` (see below).

Steps 1 and 2 are expected contract changes — they are intentional and auditable. Step 3 is the key to keeping `run_order()` itself closed to modification.

### Use a Registry, Not an `if/elif` Chain

If `run_order()` is written as a series of `if order.nhl: ... if order.mlb: ...` branches, every new sheet adds another branch and the function must be edited each time. Instead, maintain an internal dispatch registry:

```python
_REGISTRY: dict[str, Callable[[Any], None]] = {
    "nhl":              _run_nhl,
    "mlb":              _run_mlb,
    "nba":              _run_nba,
    "nfl":              _run_nfl,
    "mlb_news":         _run_mlb_news,
    "mlb_trade_rumors": _run_mlb_trade_rumors,
    "presidential":     _run_presidential,
    "sky":              _run_sky,
}

def run_order(order: ScreamsheetOrder) -> str:
    for field in dataclasses.fields(order):
        options = getattr(order, field.name)
        if options is not None and field.name in _REGISTRY:
            _REGISTRY[field.name](options)
    return "success"
```

With this pattern, `run_order()` never changes. Adding a new sheet only touches `order.py` (new type + new field) and one new entry in `_REGISTRY`. The loop handles it automatically.

### Summary

| Concern | Assessment |
|---|---|
| Adding a new `*OrderOptions` type | Straightforward — isolated to `order.py` |
| Adding a field to `ScreamsheetOrder` | Required but minimal; one line |
| Updating `run_order()` dispatch | None needed with the registry pattern |
| Callers (orchestration layer) | Only need to set the new field; everything else is unchanged |
| `config.yaml` → order translation | One new key mapping; easy to add |

The design scales well. The only thing to watch is keeping the `_REGISTRY` dict and the `ScreamsheetOrder` fields in sync — a missing registry entry for a present field must **never** silently no-op. `run_order()` should emit a `logging.warning` (or `logging.error`) when it encounters a non-`None` field with no registry entry, so the omission is immediately visible in logs without crashing the run.

---

## Test Harness

Both are required.

### Unit Test (CI gate)

Write a unit test in `tests/` that:
- Mocks the individual sheet generators so no API calls are made.
- Constructs a `ScreamsheetOrder` with a subset of keys.
- Calls `run_order()`.
- Asserts only the expected sheets were generated (mock was called the right number of times).
- Asserts missing keys produced no sheet.
- Asserts an invalid order (e.g., `TeamEntry` with missing `id`) raises `ValidationError`.

### Example Script (manual smoke-test)

Add a small script at `examples/run_order_example.py` that:
- Imports `screamsheet` as an external caller would.
- Constructs a minimal `ScreamsheetOrder` (e.g., NHL only).
- Calls `run_order()`.
- Prints the result.

Run with: `uv run python examples/run_order_example.py`

This script serves as living documentation for the orchestration layer.

---

## Acceptance Criteria

- [ ] `ScreamsheetOrder` and all `*OrderOptions` types are defined in `src/screamsheet/order.py` with full type annotations.
- [ ] `run_order(order: ScreamsheetOrder) -> str` is the single engine entry point; CLI path calls it.
- [ ] A unit test passes showing a valid order with only `nhl` set produces exactly one NHL sheet and no others.
- [ ] A unit test passes showing an order with no sport keys produces zero sheets and returns `"success"`.
- [ ] A unit test passes showing an invalid order (malformed `TeamEntry`) raises `ValidationError`.
- [ ] `examples/run_order_example.py` runs end-to-end with a real (or stubbed) NHL order.
- [ ] `README.md` documents `run_order()` as the programmatic API.

---

## Out of Scope (follow-up issues)

- Fallback behavior when no `favorite_teams` are set (e.g., pick a random team for the game summary).
- Per-subscriber delivery (email, print queue routing).
- Permutations of optional fields within each sheet's options.
