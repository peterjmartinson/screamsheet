"""Unit tests for screamsheet.providers.extractors."""
from unittest.mock import patch, MagicMock

import pytest

from screamsheet.providers.extractors import MLBGameExtractor


# ---------------------------------------------------------------------------
# MLBGameExtractor.fetch_raw_data
# ---------------------------------------------------------------------------

class TestMLBGameExtractorFetchRawData:
    def _schedule_mock(self, game_pk=2025000001):
        m = MagicMock()
        m.json.return_value = {
            "totalItems": 1,
            "dates": [
                {
                    "games": [
                        {
                            "gamePk": game_pk,
                            "teams": {
                                "away": {"team": {"id": 121}},
                                "home": {"team": {"id": 143}},
                            },
                        }
                    ]
                }
            ],
        }
        return m

    def _live_mock(self, raw_data):
        m = MagicMock()
        m.json.return_value = raw_data
        return m

    def test_returns_dict_on_success(self, mlb_live_feed_response):
        schedule_mock = self._schedule_mock()
        live_mock = self._live_mock(mlb_live_feed_response)
        with patch("requests.get", side_effect=[schedule_mock, live_mock]):
            result = MLBGameExtractor.fetch_raw_data(team_id=143, date_str="2025-03-15")
        assert isinstance(result, dict)

    def test_returns_none_when_no_game_found(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"totalItems": 0, "dates": []}
        with patch("requests.get", return_value=mock_resp):
            result = MLBGameExtractor.fetch_raw_data(team_id=143, date_str="2025-03-15")
        assert result is None

    def test_returns_none_on_request_error(self):
        import requests as req_lib
        with patch("requests.get", side_effect=req_lib.exceptions.RequestException("fail")):
            result = MLBGameExtractor.fetch_raw_data(team_id=143, date_str="2025-03-15")
        assert result is None


# ---------------------------------------------------------------------------
# MLBGameExtractor.extract_key_info
# ---------------------------------------------------------------------------

class TestMLBGameExtractorExtractKeyInfo:
    def test_returns_string_for_none_data(self):
        result = MLBGameExtractor.extract_key_info(None)
        assert isinstance(result, str)

    def test_extracts_home_team(self, mlb_live_feed_response):
        result = MLBGameExtractor.extract_key_info(mlb_live_feed_response)
        assert isinstance(result, dict)
        assert result["home_team"] == "Philadelphia Phillies"

    def test_extracts_away_team(self, mlb_live_feed_response):
        result = MLBGameExtractor.extract_key_info(mlb_live_feed_response)
        assert result["away_team"] == "New York Mets"

    def test_extracts_scores(self, mlb_live_feed_response):
        result = MLBGameExtractor.extract_key_info(mlb_live_feed_response)
        assert result["home_score"] == 5
        assert result["away_score"] == 3

    def test_extracts_narrative_snippets(self, mlb_live_feed_response):
        result = MLBGameExtractor.extract_key_info(mlb_live_feed_response)
        assert "Strikeout" in result["narrative_snippets"]

    def test_returns_string_for_malformed_data(self):
        result = MLBGameExtractor.extract_key_info({"bad": "data"})
        assert isinstance(result, str)
