# Blueprint: Topic Clustering, Unified Scoring, and Multi-Source Batch LLM Generation

## 1. Problem Statement

Across daily screamsheets (especially the Presidential Screamsheet and Sports News screamsheets):
1. **Redundant Topic Coverage**: When a major event occurs (e.g., U.S. tariffs on Canada or a key player trade), multiple independent RSS feeds report on the same event with different headlines. Standard fuzzy string matching (`difflib.SequenceMatcher`) misses semantic equivalence, causing all 4 rendered sections of a screamsheet to cover the same story.
2. **Thin Material & Variable Depth**: Individual RSS items often contain only a 1-sentence teaser. Prompting an LLM with a single sentence forces it to pad, speculate, or produce repetitive summaries.
3. **Missing White House Body Text**: The White House briefing room listing page (`/news/`) contains titles and dates but empty summary snippets. Without scraping the destination article page, official statements get prioritized based on title alone with zero supporting text.

---

## 2. Architectural Solution

```
Raw Articles Fetched (RSS Feeds + White House)
       │
       ▼
[Step 1: Text Enrichment & Scraping]
       │  • If summary is missing or thin (< 40 words), scrape article page
       │  • Specifically extract paragraph text for White House releases
       ▼
[Step 2: Article-Level Scoring]
       │  • Presidential: Keyword relevance weights + White House authority bonus
       │  • Sports: Favorite team tier bonuses (+35 / +20 / +10)
       │  • Quality gate: Thin content penalized if under 40 words
       ▼
[Step 3: Vector Embeddings & In-Memory Clustering]
       │  • Generate semantic embeddings for "title. summary"
       │  • Pairwise cosine similarity matrix via NumPy
       │  • Agglomerative grouping (cosine >= 0.75) into Topic Clusters
       ▼
[Step 4: Cluster-Level Scoring & Qualification]
       │  • Anchor score = max(member article scores)
       │  • Multi-source confirmation bonus (+15 for 2 sources, +30 for 3+ sources)
       │  • Substance gate: Combined unique text must exceed minimum word threshold
       │  • Select Top 4 distinct Topic Clusters
       ▼
[Step 5: Multi-Source Batch Prompting]
       │  • Pack all reports in each winning cluster into a single structured payload
       │  • LLM acts as an editorial wire desk, synthesizing multiple perspectives
       │    into a cohesive, attributed 2-3 paragraph article
       ▼
[Step 6: Render Screamsheet PDF]
       • Formats Top 4 diverse, rich articles across front and back pages
```

---

## 3. Detailed Component Specifications

### A. White House & Article Body Scraping
- **Target**: `screamsheet.providers.political_news_provider.WhiteHouseProvider`
- When fetching items from `https://www.whitehouse.gov/news/`, enrich entries with full text scraped from the article URL (targeting `div.entry-content p` or `div.wp-block-post-content p`).
- Ensure fallback timeout handling and robust caching.

### B. Scoring Engine (`screamsheet.news.scoring`)
1. **Article-Level Scoring**:
   - `BaseScore` + `DomainBonus` + `AuthorityBonus`
   - **Sports**: Match favorite teams using `team_lookup_db`:
     - Primary favorite: `+35`
     - Secondary favorite: `+20`
     - Tertiary favorite: `+10`
   - **Presidential**: Scored via `KEYWORD_WEIGHTS`.
   - **White House Authority Bonus**: `+25` bonus applied **only if** `len(summary.split()) >= 80`. If text is missing or thin, bonus is `0`.
   - **Thin-content Penalty**: Articles with $< 30$ words receive a `0.4x` score multiplier.

2. **Cluster-Level Scoring**:
   $$\text{ClusterScore} = \max(\text{ArticleScores}) + \text{MultiSourceBonus}$$
   - Multi-source bonus:
     - 1 source: `0`
     - 2 distinct sources: `+15`
     - 3+ distinct sources: `+30`
   - **Substance Qualification**: Clusters must have $\ge 100$ combined words across member summaries to qualify for the final 4.

### C. Semantic Topic Clustering (`screamsheet.news.clustering`)
- **Engine**: `TopicClusterer`
- **Embedding Provider**: Uses Gemini `text-embedding-004` (fallback to OpenAI `text-embedding-3-small`, with local TF-IDF fallback if offline or no keys).
- **Algorithm**:
  1. Embed normalized text `f"{title}. {summary}"` for each article.
  2. Compute cosine similarity matrix: $S_{ij} = \frac{u_i \cdot u_j}{\|u_i\| \|u_j\|}$.
  3. Sort articles by descending article score.
  4. Greedy clustering:
     - Anchor cluster with top unscored article.
     - Add any article with cosine similarity $\ge 0.75$.
     - Mark as clustered and repeat.
  5. Merge members into `TopicCluster`:
     - `topic`: Representative title (anchor title).
     - `score`: Calculated cluster score.
     - `sources`: List of distinct sources.
     - `articles`: List of member articles.

### D. Multi-Source Batch Prompting
- **Summarizer**: `PoliticalNewsSummarizer` (and shared base for general news).
- **Prompt Input Format**:
  ```json
  {
    "topic": "U.S. Announces 25% Tariffs on Canadian Imports",
    "sources": ["White House", "BBC", "Politico"],
    "articles": [
      {
        "source": "White House",
        "title": "Statement on Trade Enforcement",
        "summary": "The President signed an executive order..."
      },
      {
        "source": "BBC",
        "title": "Ottawa promises reciprocal action",
        "summary": "Canadian leadership convened an emergency cabinet meeting..."
      }
    ]
  }
  ```
- **Prompt Directive**:
  Instructs the LLM to synthesize the reports into a cohesive 2–3 paragraph article, highlighting key agreements and contrasts, attributing source perspectives, and avoiding repetitive statements.

---

## 4. Rollout Plan
1. **Test Bed**: Presidential Screamsheet pipeline (`PoliticalNewsProvider`, `PoliticalNewsProcessor`, `PoliticalNewsSummarizer`).
2. **Expansion**: Generalize `TopicClusterer` and `NewsScorer` for `MLBNewsScreamsheet`, `MLBTradeRumorsScreamsheet`, and `NHLNewsScreamsheet`.
