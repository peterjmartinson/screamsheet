"""Unit tests for screamsheet.news.clustering."""
import pytest
from datetime import datetime, timezone
from screamsheet.news.clustering import (
    FallbackLexicalVectorizer,
    TopicCluster,
    TopicClusterer,
)
from screamsheet.news.scoring import PoliticalNewsScorer, ClusterScorer


class TestTopicCluster:
    def test_sources_extracted_from_articles(self):
        articles = [
            {"title": "Story 1", "summary": "Text 1", "source": "BBC"},
            {"title": "Story 2", "summary": "Text 2", "source": "Politico"},
            {"title": "Story 3", "summary": "Text 3", "source": "BBC"},
        ]
        cluster = TopicCluster(topic="Story 1", articles=articles)
        assert cluster.sources == ["BBC", "Politico"]

    def test_to_prompt_data(self):
        dt = datetime.now(timezone.utc)
        articles = [
            {"title": "Story 1", "summary": "Text 1", "source": "BBC", "link": "https://bbc.com/1", "published": dt},
            {"title": "Story 2", "summary": "Text 2", "source": "Politico", "link": "https://politico.com/2", "published": dt},
        ]
        cluster = TopicCluster(topic="Main Topic", articles=articles, score=25.0)
        data = cluster.to_prompt_data()
        assert data["topic"] == "Main Topic"
        assert data["score"] == 25.0
        assert data["num_sources"] == 2
        assert len(data["reports"]) == 2
        assert data["reports"][0]["source"] == "BBC"


class TestFallbackLexicalVectorizer:
    def test_fit_transform_shapes(self):
        vectorizer = FallbackLexicalVectorizer()
        texts = [
            "Trump levies tariffs on Canadian steel imports",
            "Canada warns of retaliatory tariffs on American goods",
            "Phillies defeat Mets in game three of divisional series",
        ]
        matrix = vectorizer.fit_transform(texts)
        assert matrix.shape[0] == 3
        assert matrix.shape[1] > 0

    def test_similar_texts_have_higher_cosine_similarity(self):
        import numpy as np
        vectorizer = FallbackLexicalVectorizer()
        texts = [
            "Trump announces tariffs on Canada imports",
            "Tariffs announced by Trump on Canada goods",
            "Baseball playoffs begin with double header in Philadelphia",
        ]
        matrix = vectorizer.fit_transform(texts)
        sim_tariff = float(np.dot(matrix[0], matrix[1]))
        sim_unrelated = float(np.dot(matrix[0], matrix[2]))
        assert sim_tariff > sim_unrelated


class TestTopicClusterer:
    def test_clusters_group_similar_stories(self):
        articles = [
            {
                "title": "Trump imposes 25% tariffs on Canada and Mexico",
                "summary": "President Trump signed an executive order on trade tariffs.",
                "source": "Politico",
                "score": 25,
            },
            {
                "title": "Canada prepares retaliatory tariffs against United States",
                "summary": "Ottawa responded to the Trump executive order on trade tariffs.",
                "source": "BBC",
                "score": 20,
            },
            {
                "title": "Phillies acquire starting pitcher",
                "summary": "Philadelphia bolsters their baseball pitching staff.",
                "source": "MLB.com",
                "score": 10,
            },
        ]
        # Force fallback vectorizer to ensure deterministic offline test
        clusterer = TopicClusterer(similarity_threshold=0.25)
        # Monkeypatch _get_embeddings to use local TF-IDF
        clusterer._get_embeddings = lambda texts: FallbackLexicalVectorizer().fit_transform(texts)

        clusters = clusterer.cluster(articles)
        # Should create 2 clusters: one for tariffs, one for baseball
        assert len(clusters) == 2
        top_cluster = clusters[0]
        assert "tariff" in top_cluster.topic.lower() or "tariffs" in top_cluster.topic.lower()
        assert len(top_cluster.articles) == 2
        assert set(top_cluster.sources) == {"Politico", "BBC"}

    def test_empty_articles_returns_empty_list(self):
        clusterer = TopicClusterer()
        assert clusterer.cluster([]) == []

    def test_top_n_limits_output(self):
        articles = [
            {"title": f"Story {i}", "summary": f"Summary text for article number {i}", "score": i}
            for i in range(10)
        ]
        clusterer = TopicClusterer()
        clusterer._get_embeddings = lambda texts: FallbackLexicalVectorizer().fit_transform(texts)
        clusters = clusterer.cluster(articles, top_n=3)
        assert len(clusters) <= 3
