## Problem
Currently, for sports scores and sports scream sheets (MLB, NHL, NBA, NFL), if no favorite teams have a game on the previous day, the sheet skips generating a box score and game summary. Similarly, in sports news scream sheets, article selection is strictly governed by the favorite teams list, leading to empty or non-ideal behavior if none are set or their stories aren't found.

## Requested Change
1. **Sports scream sheets (MLB, NHL, NBA, NFL – scores):**
    - If no favorite teams have played, select a random completed game from yesterday and feature its box score and summary (as if it were the favorite team).
    - If `favorite_teams` is empty or not provided, always fallback to highlighting a random team/game from yesterday.
    - Retain the current logic of checking favorite teams in order: if none found, then fallback.
2. **Sports news scream sheets:**
    - If `favorite_teams` is empty or not provided, fill with random/significant stories as default.
    - If an article can't be matched to any favorite team, fill remaining slots with non-repetitive, significant stories at random.
3. Apply these changes consistently for all four major sports.

## Acceptance Criteria
- All sports and sports news sheets include a box score/game summary or stories, even if no favorite team played or none are specified.
- Add/extend tests for the new fallback logic (sports and news) to ensure: 
    - Case: No favorite team games found → random game is used
    - Case: `favorite_teams` is empty → random game/story is used
- Document this behavior clearly in the repo README.

## Additional Notes
- See callout for fallback logic in [`ISSUE_77_ORDER_CONTRACT.md`](documentation/subscriber-setup/ISSUE_77_ORDER_CONTRACT.md).
- This would improve the UX, making sheets never feel "empty" even for non-fans or incorrectly configured sheets.