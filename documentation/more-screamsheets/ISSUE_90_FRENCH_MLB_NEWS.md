## Objective

Implement an automated data pipeline that fetches French-language Major League Baseball (MLB) articles based on a prioritized list of user-favorite teams, processes them using a configurable Large Language Model (LLM) API to generate tailored, leveled reading content for two target audiences, and compiles a comprehensive back-page contextual lexicon of rare words and idioms.

---

## Technical Specifications & Architecture

```
                       [ RDS.ca / TVA Sports ]
                                  │
                                  ▼
                     [ Data Scraper & Filter ] 
                       (Check Favorite Teams)
                                  │
                                  ▼
                   [ Configurable LLM API Engine ]
                    (Grok / Configured Endpoint)
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
 [ Generation Lane 1 ]                               [ Generation Lane 2 ]
  - Article 1 Text                                    - Article 2 Text
  - CEFR A2 (Max 300 words)                           - CEFR B2/C1 (Max 300 words)
        │                                                   │
        └─────────────────────────┬─────────────────────────┘
                                  ▼
                   [ Lexicon Aggregator & Parser ]
                    - Sub-section 1: Lemmas/Vocab
                    - Sub-section 2: Idioms & Phrasals
                                  │
                                  ▼
                   [ Layout Compiler / Markdown ]

```

### 1. Data Ingestion & Fallback Layer

* **Target Sources:** Scraping architecture must parse contemporary French-language Canadian sports engines covering Major League Baseball. Targeted feeds:
* **RDS MLB Feed:** `[https://www.rds.ca/baseball/mlb](https://www.rds.ca/baseball/mlb)`
* **TVA Sports MLB Feed:** `[https://www.tvasports.ca/baseball/mlb](https://www.tvasports.ca/baseball/mlb)`


* **Input Constraints:** Acceptance of a `FAVORITE_TEAMS` configuration array containing up to 3 strings (e.g., `["Phillies", "Blue Jays", "Orioles"]`).
* **Routing Logic:**
1. The ingestor loops through the specified `FAVORITE_TEAMS` list in priority order.
2. If an article headline or body matches a team, extract the text payload. Continue until **two separate articles** are acquired.
3. If less than two matching articles are found after exhausting the favorite teams list, collect remaining slots by picking un-matched articles at random from the main feed.
4. If `FAVORITE_TEAMS` is empty or null, select two sports articles entirely at random from the active feed.



### 2. General LLM Driver Layer

* **Abstraction Standard:** Implement an isolated API driver wrapper. Do not hardcode endpoint logic.
* **Configuration Keys:**
```ini
LLM_PROVIDER=grok # or open_ai, anthropic
LLM_MODEL_NAME=grok-2 # or alternative configurable string
LLM_API_KEY=env_api_key_secret
TEMPERATURE=0.3

```



```

### 3. Generation Requirements & Prompt Injections

The compiler must execute concurrent payloads ensuring the combined text assets match targeted learning frameworks. **Strict length limits are enforced at the API constraint level.**

#### Processing Lane A: The Younger Kid (CEFR A2)
*   **Payload Target:** Article 1 text.
*   **Constraint:** Hard limit of **300 words** maximum.
*   **Prompt Directives:**
    *   Translate/re-word into natural, authentic Québécois or standard French sports text.
    *   Target **CEFR A2** (Elementary / High Beginner).
    *   Restrict verb environments to *Présent de l'indicatif* and *Passé Composé*. Explicitly ban complex subordinate clauses, conditional tenses, and literary structures (*Passé Simple*).
    *   Retain foundational baseball terms (*un coup de circuit, le lanceur*) intact to maintain authentic sports character.

#### Processing Lane B: The Older Kid (CEFR B2/C1)
*   **Payload Target:** Article 2 text.
*   **Constraint:** Hard limit of **300 words** maximum.
*   **Prompt Directives:**
    *   Translate/re-word into rich, engaging French sports prose.
    *   Target **CEFR B2/C1** (Upper-Intermediate / Advanced College Vocabulary).
    *   Incorporate native idiomatic sports expressions and advanced structural pacing transitions (*bien que, tandis que, néanmoins*).
    *   Permit complete, natural modal flexibility (*Conditionnel, Subjonctif* clauses).

#### Processing Lane C: The Lexicon Aggregator
*   **Payload Target:** Raw text elements of *both* selected source articles.
*   **Output Constraint:** Enforce a strict JSON Schema signature response to automate layout population:
    ```json
    {
      "vocabulary": [
        { "french_lemma": "string", "part_of_speech": "string", "english_translation": "string" }
      ],
      "idiomatic_phrases": [
        { "french_phrase": "string", "literal_translation": "string", "contextual_meaning": "string" }
      ]
    }

```

* **Lexicon Parameters:**
* `vocabulary`: Limit to 5-10 uncommon nouns/verbs found in the passages, resolving back to their root infinitive or base dictionary lemma.
* `idiomatic_phrases`: Limit to 3-5 structural phrases, baseball jargon entries, or colloquial expressions whose true meaning is altered or missing when evaluated word-for-word (e.g., *"retirer sur des prises"*, *"connaître un passage à vide"*).



### 4. Layout & Screamsheet Output Specification

* The system output file must generate a scannable Markdown template or a single layout schema ready for local automated printing pipelines.
* **Front Structural Canvas:** Two-column split containing the A2 simplified article on the left, and the B2/C1 advanced article on the right.
* **Back Structural Canvas:** A unified language sheet split into two targeted blocks:
* **Section 1: Le Lexique Essentiel** (Table parsing the lemma vocabulary values).
* **Section 2: Les Tournures de Phrase** (Block formatting highlighting the idiom, literal meaning, and correct sport translation).



---

## Definition of Done (TDD Criteria)

* [ ] Unit tests verify fallback router correctly extracts random items when `FAVORITE_TEAMS` values return zero matches from the target DOM nodes.
* [ ] Structured schema check validates that raw LLM text streams are successfully parsed without dropping string tokens or throwing JSON anomalies.
* [ ] End-to-end integration verifies the execution cycle writes a clean compilation file within layout boundaries without breaking the 300-word caps per side.