"""Semantic topic clustering and multi-source aggregation for news screamsheets."""
import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import numpy as np

from .scoring import BaseNewsScorer, ClusterScorer, PoliticalNewsScorer

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class TopicCluster:
    """Represents a group of semantically similar news articles."""

    topic: str
    articles: List[Dict[str, Any]]
    score: float = 0.0
    sources: List[str] = field(default_factory=list)
    primary_link: str = ""
    published: Optional[datetime] = None
    combined_summary: str = ""

    def __post_init__(self) -> None:
        if not self.sources and self.articles:
            seen = set()
            src_list = []
            for a in self.articles:
                src = a.get("source")
                if src and src not in seen:
                    seen.add(src)
                    src_list.append(src)
            self.sources = src_list

        if not self.primary_link and self.articles:
            self.primary_link = self.articles[0].get("link") or ""

        if self.published is None and self.articles:
            self.published = self.articles[0].get("published")

        if not self.combined_summary and self.articles:
            summaries = []
            for a in self.articles:
                s = (a.get("summary") or "").strip()
                if s and s not in summaries:
                    summaries.append(s)
            self.combined_summary = "\n\n".join(summaries)

    def to_prompt_data(self) -> Dict[str, Any]:
        """Convert cluster into structured payload for multi-source batch LLM generation."""
        reports = []
        for a in self.articles:
            reports.append({
                "source": a.get("source", "Unknown"),
                "title": a.get("title", ""),
                "summary": a.get("summary", ""),
                "link": a.get("link", ""),
            })
        return {
            "topic": self.topic,
            "score": self.score,
            "num_sources": len(self.sources),
            "sources": self.sources,
            "reports": reports,
            "link": self.primary_link,
            "id": self.primary_link,
        }


class FallbackLexicalVectorizer:
    """Pure Python + NumPy TF-IDF vectorizer used when API embedding models are unavailable."""

    def __init__(self, min_token_len: int = 3) -> None:
        self.min_token_len = min_token_len

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())
        tokens = [w for w in words if len(w) >= self.min_token_len]
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        return tokens + bigrams

    def fit_transform(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        docs_tokens = [self._tokenize(t) for t in texts]
        vocab: Dict[str, int] = {}
        for tokens in docs_tokens:
            for token in set(tokens):
                vocab[token] = vocab.get(token, 0) + 1

        vocab_index = {token: idx for idx, token in enumerate(vocab.keys())}
        num_docs = len(texts)
        num_terms = len(vocab_index)

        if num_terms == 0:
            return np.zeros((num_docs, 1), dtype=np.float32)

        mat = np.zeros((num_docs, num_terms), dtype=np.float32)
        for i, tokens in enumerate(docs_tokens):
            if not tokens:
                continue
            term_counts: Dict[str, int] = {}
            for t in tokens:
                term_counts[t] = term_counts.get(t, 0) + 1

            for term, count in term_counts.items():
                col = vocab_index[term]
                df = vocab[term]
                tf = 1.0 + math.log(count)
                idf = math.log((1.0 + num_docs) / (1.0 + df)) + 1.0
                mat[i, col] = tf * idf

        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return mat / norms


class TopicClusterer:
    """Groups news articles into semantic topic clusters using vector embeddings.

    Uses Gemini embeddings (or OpenAI) if available, with a deterministic
    TF-IDF fallback when running offline or without credentials.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.68,
        scorer: Optional[BaseNewsScorer] = None,
        cluster_scorer: Optional[ClusterScorer] = None,
        embedding_model: Optional[str] = None,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.scorer = scorer or PoliticalNewsScorer()
        self.cluster_scorer = cluster_scorer or ClusterScorer()
        self.embedding_model = embedding_model

    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embedding matrix for a list of texts."""
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        # 1. Try Gemini via google.genai Client
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                from google import genai

                client = genai.Client(api_key=gemini_key)
                model = self.embedding_model or "gemini-embedding-001"
                batch_size = 90
                embeddings = []
                for i in range(0, len(texts), batch_size):
                    chunk = texts[i : i + batch_size]
                    resp = client.models.embed_content(
                        model=model,
                        contents=chunk,
                    )
                    if hasattr(resp, "embeddings") and resp.embeddings:
                        embeddings.extend([e.values for e in resp.embeddings])

                if len(embeddings) == len(texts):
                    mat = np.array(embeddings, dtype=np.float32)
                    norms = np.linalg.norm(mat, axis=1, keepdims=True)
                    norms[norms == 0.0] = 1.0
                    return mat / norms
            except Exception as e:
                logger.warning("Gemini embeddings failed: %s. Falling back.", e)

        # 2. Try OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from langchain_openai import OpenAIEmbeddings

                model = self.embedding_model or "text-embedding-3-small"
                client = OpenAIEmbeddings(
                    model=model,
                    openai_api_key=openai_key,
                )
                embeddings = client.embed_documents(texts)
                mat = np.array(embeddings, dtype=np.float32)
                norms = np.linalg.norm(mat, axis=1, keepdims=True)
                norms[norms == 0.0] = 1.0
                return mat / norms
            except Exception as e:
                logger.warning("OpenAI embeddings failed: %s. Falling back.", e)

        # 3. Fallback to local TF-IDF
        logger.debug("Using fallback lexical vectorizer for topic clustering")
        vectorizer = FallbackLexicalVectorizer()
        return vectorizer.fit_transform(texts)

    def cluster(
        self,
        entries: List[Dict[str, Any]],
        top_n: Optional[int] = None,
    ) -> List[TopicCluster]:
        """Cluster news articles into cohesive topics and rank clusters by relevance.

        Args:
            entries: Normalized article dicts.
            top_n: Optional limit on number of clusters returned.

        Returns:
            List of TopicCluster objects sorted by cluster score descending.
        """
        if not entries:
            return []

        # Ensure entries have scores
        scored_entries = []
        for entry in entries:
            e = dict(entry)
            if "score" not in e or e["score"] is None:
                e["score"] = self.scorer.score(e)
            scored_entries.append(e)

        texts = [
            f"{e.get('title', '').strip()}. {e.get('summary', '').strip()}"
            for e in scored_entries
        ]

        vectors = self._get_embeddings(texts)
        if vectors.shape[0] == 0:
            return []

        # Cosine similarity matrix: S = V @ V.T
        sim_matrix = np.matmul(vectors, vectors.T)

        # Sort indices by article score descending
        sorted_indices = sorted(
            range(len(scored_entries)),
            key=lambda i: scored_entries[i].get("score", 0),
            reverse=True,
        )

        unassigned = set(sorted_indices)
        clusters: List[TopicCluster] = []

        for anchor_idx in sorted_indices:
            if anchor_idx not in unassigned:
                continue

            anchor_entry = scored_entries[anchor_idx]
            cluster_members = [anchor_entry]
            unassigned.remove(anchor_idx)

            # Find all matching articles exceeding the similarity threshold
            for other_idx in list(unassigned):
                other_entry = scored_entries[other_idx]
                src_a = (anchor_entry.get("source") or "").lower()
                src_b = (other_entry.get("source") or "").lower()
                general_sources = {"mlb.com", "nhl.com", "reuters", "ap", "google news", "bbc", "politico", "nyt", "npr", "washington post", "white house", ""}
                if src_a and src_b and src_a != src_b and src_a not in general_sources and src_b not in general_sources:
                    text_a = f"{anchor_entry.get('title', '')} {anchor_entry.get('summary', '')}".lower()
                    text_b = f"{other_entry.get('title', '')} {other_entry.get('summary', '')}".lower()
                    if src_b not in text_a and src_a not in text_b:
                        continue

                similarity = float(sim_matrix[anchor_idx, other_idx])
                if similarity >= self.similarity_threshold:
                    cluster_members.append(other_entry)
                    unassigned.remove(other_idx)

            # Score the cluster
            cluster_score = self.cluster_scorer.score_cluster(
                cluster_members,
                anchor_score=anchor_entry.get("score", 0),
            )

            cluster = TopicCluster(
                topic=anchor_entry.get("title") or "Untitled Topic",
                articles=cluster_members,
                score=cluster_score,
                primary_link=anchor_entry.get("link") or "",
                published=anchor_entry.get("published"),
            )
            clusters.append(cluster)

        clusters.sort(key=lambda c: c.score, reverse=True)

        if top_n is not None:
            clusters = clusters[:top_n]

        logger.info(
            "TopicClusterer: clustered %d articles into %d topics (top score: %.1f)",
            len(entries),
            len(clusters),
            clusters[0].score if clusters else 0.0,
        )
        return clusters
