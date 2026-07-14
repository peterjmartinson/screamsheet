# Screamsheet Refactoring & Cleanup Suggestions

This document outlines a plan to bring the **Screamsheet** codebase closer to Uncle Bob Martin's "Clean Code" standards and adhere to your core programming principles: Single Responsibility Principle (SRP), Test-Driven Development (TDD), DRY (Don't Repeat Yourself), minimal/meaningful comments, descriptive naming, and ease of reading for a distracted programmer.

---

## 1. Candidate Screamsheets for Culling

Based on your list of active screamsheets (*MLB Sports, NHL Sports, NBA Sports, MLB Trade Rumors, MLB News, NHL News, Presidential News, Sky Tonight, and French MLB News*, with *NFL* as a work-in-progress), the following screamsheets, providers, renderers, and associated tests should be culled:

### B. FanGraphs Blogs (fangraphs)
*   **Screamsheet Class:** [fangraphs.py](file:///home/peter/Code/screamsheet/src/screamsheet/news/fangraphs.py)
*   **Data Provider:** [fangraphs_provider.py](file:///home/peter/Code/screamsheet/src/screamsheet/providers/fangraphs_provider.py)

### C. Players' Tribune (players_tribune)
*   **Screamsheet Class:** [players_tribune.py](file:///home/peter/Code/screamsheet/src/screamsheet/news/players_tribune.py)
*   **Data Provider:** [players_tribune_provider.py](file:///home/peter/Code/screamsheet/src/screamsheet/providers/players_tribune_provider.py)

*Note: Clean up references to these in the entry points/factories ([factory.py](file:///home/peter/Code/screamsheet/src/screamsheet/factory.py), [__main__.py](file:///home/peter/Code/screamsheet/src/screamsheet/__main__.py), [runner.py](file:///home/peter/Code/screamsheet/src/screamsheet/runner.py), [order.py](file:///home/peter/Code/screamsheet/src/screamsheet/order.py), [config.py](file:///home/peter/Code/screamsheet/src/screamsheet/config.py), and [__init__.py](file:///home/peter/Code/screamsheet/src/screamsheet/__init__.py)) when deleting these files.*

---

## 2. Key Architectural Cleanups (DRY & SRP)

### A. Unify PDF Page-Splitting Logic (DRY)
**The Problem:** The `generate()` methods in:
*   [base_sports.py](file:///home/peter/Code/screamsheet/src/screamsheet/sports/base_sports.py#L133-L165)
*   [base_news.py](file:///home/peter/Code/screamsheet/src/screamsheet/news/base_news.py#L67-L100)
*   [sky_tonight.py](file:///home/peter/Code/screamsheet/src/screamsheet/sky/sky_tonight.py#L97-L126)

are virtually identical. They construct the header (Title, Subtitle, Date) for the front page, iterate through sections, check if a section's `page_slot` is `"back"`, split them into `front_content` and `back_content`, and call `self._build_two_page_pdf(front_content, back_content)`.

**The Solution:** Pull this layout-generation logic up to the base class [BaseScreamsheet](file:///home/peter/Code/screamsheet/src/screamsheet/base/screamsheet.py). 

Provide a single, consolidated `generate()` method in `BaseScreamsheet` that:
1.  Calls `self.build_sections()` to load sections.
2.  Iterates through sections, sorting them into front/back page flowables depending on `section.page_slot`.
3.  Assembles headers.
4.  Delegates to `_build_two_page_pdf()`.

Subclasses only need to implement `build_sections()`, `get_title()`, and `get_subtitle()`, entirely eliminating duplicate boilerplate rendering logic.

### B. Consolidate and Deduplicate Common Data Types (DRY)
**The Problem:** There is high duplication of structures representing configuration and input schemas:
*   `TeamEntry` is declared in both [config.py](file:///home/peter/Code/screamsheet/src/screamsheet/config.py#L20-L23) and [order.py](file:///home/peter/Code/screamsheet/src/screamsheet/order.py#L20-L24).
*   `WeatherLocationConfig` (in `config.py`) and `WeatherLocationOptions` (in `order.py`) are identical structures.
*   `PersonConfig` (in `config.py`) and `PersonOptions` (in `order.py`) are identical structures.

This leads to a repetitive mapping layer (`_build_order_from_config` in `__main__.py`) which is tedious to maintain when settings expand.

**The Solution:** 
*   Expose shared contract dataclasses (e.g. `TeamEntry`, `WeatherLocation`, `PersonConfig`) in a central location or reuse them directly between configuration reading and order generation.
*   Let `ScreamsheetOrder` directly consume config schemas or inherit from them to reduce structural coupling and mapping code.

### C. Clean up Factory Bloat ([factory.py](file:///home/peter/Code/screamsheet/src/screamsheet/factory.py))
**The Problem:** 
*   **Hardcoded Constants:** The class contains a huge list of static team ID mappings (`MLB_PHILLIES = 143`, etc.), which belongs in a database or team lookup utility rather than hardcoded in the primary object-instantiation factory.
*   **API Polluted with Deprecated Arguments:** Factory methods like `create_mlb_screamsheet` still contain `team_id` and `team_name` arguments marked as deprecated in favor of `favorite_teams`. Keeping these adds visual clutter for programmers reading the code.
*   **OCP Violation:** The factory imports and constructs every concrete screamsheet subclass directly. If a new sheet type is added, the factory file must change.

**The Solution:**
*   Remove the long list of hardcoded team ID constants from `ScreamsheetFactory` and let it query `team_lookup_db.py` if name-to-ID mappings are ever needed.
*   Remove deprecated parameters from method signatures (updating tests using them).
*   *Alternative (Advanced Clean Code):* Use a registry pattern where screamsheet classes register themselves to the factory on module import, keeping `factory.py` completely decoupled from concrete classes.

### D. Missing Subclasses in Package Exports
**The Problem:**
[src/screamsheet/__init__.py](file:///home/peter/Code/screamsheet/src/screamsheet/__init__.py) exports some screamsheet types but omits others that are in active use:
*   `FrenchMLBNewsScreamsheet`
*   `NHLNewsScreamsheet`
*   `MLBNewsScreamsheet`
*   `PresidentialScreamsheet`
*   `SkyTonightScreamsheet`

**The Solution:** Add all active screamsheet types to the package level `__all__` list in `__init__.py` to provide a consistent package API.

---

## 3. Adhering to Your Principles

### A. Single Responsibility Principle (SRP)
*   **Data Providers vs Renderers:** The separation of data fetching (e.g. `MLBDataProvider`) and PDF rendering (`StandingsSection`) is already solid. Keep this separation strict.
*   **BaseScreamsheet Responsibility:** Let `BaseScreamsheet` be solely responsible for PDF generation and template layout. Let concrete sheets (like `MLBScreamsheet`) be responsible only for declaring which sections make up that sheet.

### B. Few Comments & Descriptive Naming
*   Many classes have comments explaining *what* they are doing. In Clean Code, code should document itself through descriptive names.
*   *Example Refactoring:* Instead of inline comments, write expressive method names:
    *   Instead of `played = self.provider.has_game(tid, self.date)  # checks if they played`, the naming is already descriptive.
    *   Rename utility methods to express intent. For example, `_pick_random_team` could be `_fallback_to_random_completed_game`.

### C. Test-Driven Development (TDD)
*   Screamsheet has an excellent coverage suite (over 800 tests). 
*   We can safely refactor by writing failing tests for our proposed unified base class layout logic first, then refactoring `BaseScreamsheet`, verifying that all 800+ tests continue to pass.

---

## 4. Refactoring Step-by-Step Roadmap

1.  **Phase 1: Cull Unused Sheets**
    *   Delete the FanGraphs and Players' Tribune code files and prompts.
    *   Remove their imports/references in `factory.py`, `__main__.py`, `runner.py`, `order.py`, `config.py`, and `__init__.py`.
    *   Run `pytest` to verify nothing is broken by the culling.
2.  **Phase 2: Pull Up `generate()` Layout Logic**
    *   Implement unified `generate()` in `BaseScreamsheet`.
    *   Remove overridden `generate()` methods in `SportsScreamsheet`, `NewsScreamsheet`, and `SkyTonightScreamsheet`.
    *   Run tests to verify layout generation works identically.
3.  **Phase 3: Clean up Factory and Config Models**
    *   Remove deprecated parameters in factory.
    *   Deduplicate options and configuration classes.
    *   Update tests.
