# Add screamsheet: 4 MLB.com news articles via prioritized team RSS feeds (configurable priorities) 

### Summary
Implement a new screamsheet that aggregates four news articles from MLB.com using available RSS feeds, prioritizing coverage from Phillies, then Padres, then Yankees. This should be in the style and structure of the existing trade rumors screamsheet.

### Details & Requirements
- Identify and use the following RSS feeds for fetching articles:
  - Phillies: https://www.mlb.com/phillies/feeds/news/rss.xml
  - Padres: https://www.mlb.com/padres/feeds/news/rss.xml
  - Yankees: https://www.mlb.com/yankees/feeds/news/rss.xml
  - General MLB: https://www.mlb.com/feeds/news/rss.xml (for fill-in if needed)
- The system should fetch and summarize four articles (prioritizing Phillies, then Padres, then Yankees; use general MLB feed only if fewer than four total are found).
- Follow the architecture and output style of the existing trade rumors screamsheet.
- Make it easy to modify the team priority order (e.g., replace Yankees with Dodgers, or use just two teams plus general MLB news) via a config variable or simple code change.
- Add new provider (e.g., `MLBNewsRssProvider`) and screamsheet class.
- Document the new screamsheet in the repo's README.
- Add tests for the new provider and screamsheet (mocking RSS responses if possible).

### Acceptance Criteria
- New screamsheet prioritizes Phillies news, with Padres/Yankees as fallback, then general MLB news.
- Only up to four articles presented, with clear source attribution.
- Generated for printout (one-page format).
- Team priorities must be customizable in code/config.
- `README.md` updated for new functionality.
- Tests included.

### References
- Existing trade rumors screamsheet implementation for architecture reference.