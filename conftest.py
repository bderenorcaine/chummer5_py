"""Test-wide isolation (WP137): every test runs in local mode against its own throwaway database,
whatever the developer's shell exports, so no test can touch a real `CHUMMER5_DB`."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUMMER5_DB", str(tmp_path / "chummer5-test.db"))
    monkeypatch.delenv("CHUMMER5_MODE", raising=False)
    monkeypatch.delenv("CHUMMER5_CHARACTER_QUOTA", raising=False)
    monkeypatch.delenv("CHUMMER5_SESSION_DAYS", raising=False)
    monkeypatch.delenv("CHUMMER5_SESSION_IDLE_MINUTES", raising=False)
    monkeypatch.delenv("CHUMMER5_UPLOAD_MAX_MB", raising=False)
    monkeypatch.delenv("CHUMMER5_TRUSTED_PROXY", raising=False)
    # WP141: hosted mode needs a public URL; tests/fixtures/hosted.py's client matches it.
    monkeypatch.setenv("CHUMMER5_PUBLIC_URL", "https://testserver")
