import os

from pipeline.openai_utils import get_openai_api_key


def test_get_key_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    assert get_openai_api_key() == "test-key-123"


def test_get_key_absent_not_required(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert get_openai_api_key(required=False) is None

