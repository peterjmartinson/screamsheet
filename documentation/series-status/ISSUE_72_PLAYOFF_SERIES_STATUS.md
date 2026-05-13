## Problem / Motivation

For NHL playoff games, the screamsheet currently shows the game result in a compact two-row table (e.g.,
```
Carolina Hurricanes 4
@Philadelphia Flyers 2
```
). However, in playoff series, the progress of the overall best-of-7 series is an essential context. At present, there is no indication of series standing within the scores table, so users can't tell at a glance who is leading or if a team has won the series.

## Enhancement Proposal (Option 3 - Compact Badge, Short Team Names)

- For **playoff games only**, add a compact parenthetical series record to the winner or series leader's row in the scores table.
- Also, **shorten team names** to only the location (e.g., "Carolina", not "Carolina Hurricanes").
- Format:
  ```
  Carolina 4 (leads 3-1)
  Philadelphia 2
  ```
  or if the series is complete:
  ```
  Carolina 4 (won 4-1)
  Philadelphia 2
  ```

## Requirements

- Implement this change **exclusively for NHL playoff games**; regular season games should remain unchanged.
- Pull series record and status ("leads", "won") from the NHL API or derive as appropriate using existing data flows (see research task for details).
- Display the parenthetical as tight to the right of the winner/leader's score as possible; use small, unambiguous text.
- Only display this if the game is part of a playoff series and series metadata is available.
- Both teams' rows should use only the location name ("Carolina", "Philadelphia") to save space.
- The implementation should have minimal vertical and horizontal impact on the table. If necessary, tweak font size or spacing for compactness.

## Acceptance Criteria

- [ ] NHL playoff games in the scores table display a compact parenthetical series status as described.
- [ ] Team names are shown as locations only.
- [ ] No change is made to non-playoff (regular season) games.
- [ ] Feature is test-covered and robust to edge cases (e.g., tied series, elimination games, incomplete series data).
- [ ] Update documentation/README if screencap or output format is changed.
- [ ] All logic is behind a flag or only activates when series context is present.

## Research reference
See ongoing research task for guidance on NHL API capabilities and future expansion: https://github.com/peterjmartinson/screamsheet/tasks/8f23346d-58c1-45e2-8dda-e6d23027a232

## Possible future expansion
- Optionally, consider displaying season-series stats for regular season rivalry games (research required – out of scope for this issue).
