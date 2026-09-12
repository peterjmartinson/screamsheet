"""Unit tests for screamsheet.news.scoring."""
import pytest
from screamsheet.news.scoring import (
    BaseNewsScorer,
    PoliticalNewsScorer,
    SportsNewsScorer,
    ClusterScorer,
)


class TestBaseNewsScorer:
    def test_substance_multiplier_empty(self):
        scorer = BaseNewsScorer()
        assert scorer.calculate_substance_multiplier("") == 0.0
        assert scorer.calculate_substance_multiplier("   ") == 0.0

    def test_substance_multiplier_short(self):
        scorer = BaseNewsScorer()
        # 10 words -> 0.4
        text = "word " * 10
        assert scorer.calculate_substance_multiplier(text) == 0.4

    def test_substance_multiplier_long(self):
        scorer = BaseNewsScorer()
        # 150 words -> 1.0
        text = "word " * 150
        assert scorer.calculate_substance_multiplier(text) == 1.0

    def test_substance_multiplier_interpolated(self):
        scorer = BaseNewsScorer()
        # 75 words -> halfway between 30 and 120 -> 0.4 + 0.6 * (45/90) = 0.7
        text = "word " * 75
        mult = scorer.calculate_substance_multiplier(text)
        assert 0.69 <= mult <= 0.71

    def test_has_substantial_text(self):
        scorer = BaseNewsScorer()
        assert scorer.has_substantial_text("word " * 50, min_words=40) is True
        assert scorer.has_substantial_text("word " * 20, min_words=40) is False


class TestPoliticalNewsScorer:
    def test_keyword_scoring(self):
        scorer = PoliticalNewsScorer()
        entry = {
            "title": "Trump imposes tariffs on imports",
            "summary": "President Trump announced sweeping tariffs today in Washington.",
            "source": "Politico",
        }
        score = scorer.score(entry)
        assert score > 0

    def test_white_house_bonus_with_substantial_text(self):
        scorer = PoliticalNewsScorer(white_house_bonus=25, min_white_house_words=60)
        entry_substantial = {
            "title": "Statement on Energy Policy",
            "summary": "Official briefing text regarding national energy strategy. " * 15,
            "source": "White House",
        }
        score_substantial = scorer.score(entry_substantial)

        entry_thin = {
            "title": "Statement on Energy Policy",
            "summary": "Short statement with only ten words here today.",
            "source": "White House",
        }
        score_thin = scorer.score(entry_thin)

        # Substantial text must receive the authority bonus, thin text should not
        assert score_substantial >= 25
        assert score_thin < 25

    def test_unrelated_text_scores_zero(self):
        scorer = PoliticalNewsScorer()
        entry = {
            "title": "Local high school bake sale",
            "summary": "Cookies and cakes were sold for charity.",
            "source": "Local Gazette",
        }
        assert scorer.score(entry) == 0


class TestSportsNewsScorer:
    def test_favorite_team_tiers(self):
        scorer = SportsNewsScorer(
            sport="mlb",
            favorite_teams=["Phillies", "Padres", "Yankees"],
        )
        rich_summary = "Detailed analysis of game operations and athletic performance. " * 20

        philly_entry = {
            "title": "Phillies sign star shortstop",
            "summary": rich_summary,
        }
        padres_entry = {
            "title": "Padres trade for starting pitcher",
            "summary": rich_summary,
        }
        general_entry = {
            "title": "Royals win regular season finale",
            "summary": rich_summary,
        }

        score_philly = scorer.score(philly_entry)
        score_padres = scorer.score(padres_entry)
        score_general = scorer.score(general_entry)

        # Tier 1 (Phillies) > Tier 2 (Padres) > General (Royals)
        assert score_philly > score_padres > score_general

    def test_junk_keywords_filter(self):
        scorer = SportsNewsScorer(
            sport="mlb",
            favorite_teams=["Phillies"],
            junk_keywords=["fantasy", "stream games"],
        )
        entry = {
            "title": "Phillies fantasy baseball outlook",
            "summary": "How to draft your favorite players.",
        }
        assert scorer.score(entry) == 0


class TestClusterScorer:
    def test_multi_source_bonus(self):
        scorer = ClusterScorer(multi_source_bonus_2=15, multi_source_bonus_3_plus=30)
        rich_summary = "Extensive policy briefing on international trade and negotiations. " * 15

        articles_1_source = [
            {"title": "Tariff news", "summary": rich_summary, "source": "Reuters", "score": 20}
        ]
        articles_2_sources = [
            {"title": "Tariff news", "summary": rich_summary, "source": "Reuters", "score": 20},
            {"title": "Tariff response", "summary": rich_summary, "source": "BBC", "score": 18},
        ]
        articles_3_sources = [
            {"title": "Tariff news", "summary": rich_summary, "source": "Reuters", "score": 20},
            {"title": "Tariff response", "summary": rich_summary, "source": "BBC", "score": 18},
            {"title": "White House statement", "summary": rich_summary, "source": "White House", "score": 25},
        ]

        score_1 = scorer.score_cluster(articles_1_source)
        score_2 = scorer.score_cluster(articles_2_sources)
        score_3 = scorer.score_cluster(articles_3_sources)

        assert score_3 > score_2 > score_1
