"""Tests for settings persistence."""

from __future__ import annotations

import pytest

from ground_news_mcp import settings


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    """Redirect settings storage to a tmp dir."""
    monkeypatch.setattr(settings, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    yield tmp_path


@pytest.mark.unit
def test_defaults_when_no_file(tmp_settings):
    s = settings.get_settings()
    assert s["profile"] == "balanced"
    assert s["missing_perspectives"] is True


@pytest.mark.unit
def test_apply_profile_persists(tmp_settings):
    settings.update_settings("profile", "full")
    s = settings.get_settings()
    assert s["profile"] == "full"
    assert s["passive_context"] is True
    assert s["bias_checker"] is True


@pytest.mark.unit
def test_individual_setting_marks_custom(tmp_settings):
    settings.update_settings("bias_checker", True)
    s = settings.get_settings()
    assert s["profile"] == "custom"
    assert s["bias_checker"] is True


@pytest.mark.unit
def test_unknown_key_rejected(tmp_settings):
    with pytest.raises(ValueError):
        settings.update_settings("not_a_real_key", True)


@pytest.mark.unit
def test_unknown_profile_rejected(tmp_settings):
    with pytest.raises(ValueError):
        settings.update_settings("profile", "extreme")


@pytest.mark.unit
def test_non_bool_for_toggle_rejected(tmp_settings):
    with pytest.raises(TypeError):
        settings.update_settings("bias_checker", "yes")
