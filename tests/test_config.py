"""Unit tests for screamsheet.config (load_config)."""
from pathlib import Path

import pytest
import yaml

from screamsheet.config import (
    LayoutConfig,
    ScreamsheetConfig,
    SportConfig,
    MLBConfig,
    TeamEntry,
    load_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path: Path, data: dict) -> Path:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(data), encoding="utf-8")
    return cfg_file


# ---------------------------------------------------------------------------
# Valid YAML loads to correct dataclasses
# ---------------------------------------------------------------------------

class TestLoadConfigValid:
    def test_returns_screamsheet_config(self, tmp_path):
        path = _write_yaml(tmp_path, {
            "nhl": {"favorite_teams": [{"id": 4, "name": "Philadelphia Flyers"}]},
            "mlb": {"favorite_teams": [{"id": 143, "name": "Philadelphia Phillies"}],
                    "news_names": ["Phillies"]},
        })
        cfg = load_config(path)
        assert isinstance(cfg, ScreamsheetConfig)

    def test_nhl_teams_parsed(self, tmp_path):
        path = _write_yaml(tmp_path, {
            "nhl": {"favorite_teams": [
                {"id": 4, "name": "Philadelphia Flyers"},
                {"id": 7, "name": "Buffalo Sabres"},
            ]},
        })
        cfg = load_config(path)
        assert len(cfg.nhl.favorite_teams) == 2
        assert cfg.nhl.favorite_teams[0] == TeamEntry(id=4, name="Philadelphia Flyers")
        assert cfg.nhl.favorite_teams[1] == TeamEntry(id=7, name="Buffalo Sabres")

    def test_mlb_teams_parsed(self, tmp_path):
        path = _write_yaml(tmp_path, {
            "mlb": {"favorite_teams": [{"id": 143, "name": "Philadelphia Phillies"}],
                    "news_names": ["Phillies", "Yankees"]},
        })
        cfg = load_config(path)
        assert isinstance(cfg.mlb, MLBConfig)
        assert cfg.mlb.favorite_teams[0] == TeamEntry(id=143, name="Philadelphia Phillies")
        assert cfg.mlb.news_names == ["Phillies", "Yankees"]

    def test_nba_teams_parsed(self, tmp_path):
        path = _write_yaml(tmp_path, {
            "nba": {"favorite_teams": [{"id": 1610612755, "name": "Philadelphia 76ers"}]},
        })
        cfg = load_config(path)
        assert cfg.nba.favorite_teams[0] == TeamEntry(id=1610612755, name="Philadelphia 76ers")

    def test_nfl_teams_parsed(self, tmp_path):
        path = _write_yaml(tmp_path, {
            "nfl": {"favorite_teams": [{"id": 4, "name": "Philadelphia Eagles"}]},
        })
        cfg = load_config(path)
        assert cfg.nfl.favorite_teams[0] == TeamEntry(id=4, name="Philadelphia Eagles")


# ---------------------------------------------------------------------------
# Missing optional sport sections default to empty
# ---------------------------------------------------------------------------

class TestLoadConfigDefaults:
    def test_missing_nba_section_defaults_to_empty(self, tmp_path):
        path = _write_yaml(tmp_path, {
            "nhl": {"favorite_teams": [{"id": 4, "name": "Philadelphia Flyers"}]},
        })
        cfg = load_config(path)
        assert cfg.nba.favorite_teams == []

    def test_missing_nfl_section_defaults_to_empty(self, tmp_path):
        path = _write_yaml(tmp_path, {})
        cfg = load_config(path)
        assert cfg.nfl.favorite_teams == []

    def test_missing_mlb_news_names_defaults_to_empty(self, tmp_path):
        path = _write_yaml(tmp_path, {
            "mlb": {"favorite_teams": [{"id": 143, "name": "Philadelphia Phillies"}]},
        })
        cfg = load_config(path)
        assert cfg.mlb.news_names == []

    def test_empty_yaml_file_returns_empty_config(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("", encoding="utf-8")
        cfg = load_config(cfg_file)
        assert cfg.nhl.favorite_teams == []
        assert cfg.mlb.favorite_teams == []


# ---------------------------------------------------------------------------
# Missing file raises FileNotFoundError
# ---------------------------------------------------------------------------

class TestLoadConfigMissingFile:
    def test_missing_file_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "config.yaml"
        with pytest.raises(FileNotFoundError):
            load_config(missing)

    def test_missing_file_error_mentions_example(self, tmp_path):
        missing = tmp_path / "config.yaml"
        with pytest.raises(FileNotFoundError, match="config.yaml.example"):
            load_config(missing)


# ---------------------------------------------------------------------------
# TeamEntry — id is optional (subscriber configs omit it)
# ---------------------------------------------------------------------------

class TestTeamEntryOptionalId:
    def test_team_entry_without_id_defaults_to_none(self):
        entry = TeamEntry(name="Philadelphia Flyers")
        assert entry.id is None

    def test_team_entry_with_id_retains_id(self):
        entry = TeamEntry(id=4, name="Philadelphia Flyers")
        assert entry.id == 4

    def test_subscriber_config_teams_parsed_without_id(self, tmp_path):
        path = _write_yaml(tmp_path, {
            "nhl": {"favorite_teams": [{"name": "Philadelphia Flyers"}]},
        })
        cfg = load_config(path)
        assert cfg.nhl.favorite_teams[0].name == "Philadelphia Flyers"
        assert cfg.nhl.favorite_teams[0].id is None


# ---------------------------------------------------------------------------
# LayoutConfig
# ---------------------------------------------------------------------------

class TestLayoutConfig:
    def test_layout_config_default_brand_footer_text(self):
        cfg = LayoutConfig()
        assert cfg.brand_footer_text == "distractedfortune.com"

    def test_load_config_reads_brand_footer_text_from_yaml(self, tmp_path):
        path = _write_yaml(tmp_path, {"layout": {"brand_footer_text": "example.com"}})
        cfg = load_config(path)
        assert cfg.layout.brand_footer_text == "example.com"

    def test_load_config_layout_uses_default_when_section_absent(self, tmp_path):
        path = _write_yaml(tmp_path, {})
        cfg = load_config(path)
        assert cfg.layout.brand_footer_text == "distractedfortune.com"
