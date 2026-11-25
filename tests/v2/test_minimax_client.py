import os


def test_minimax_key_prefers_available_legacy_environment_variable(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "primary")
    monkeypatch.setenv("api_key_minimax", "legacy")
    from client.minimaxAPI.client import get_minimax_api_key

    assert get_minimax_api_key() == "legacy"


def test_minimax_defaults_are_configurable(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("api_key_minimax", "legacy")
    monkeypatch.delenv("MINIMAX_IMAGE_MODEL", raising=False)
    from client.minimaxAPI.client import DEFAULT_MINIMAX_IMAGE_MODEL, image_model

    assert image_model() == DEFAULT_MINIMAX_IMAGE_MODEL
