"""A test client for hosted mode (WP141).

Hosted mode refuses a non-GET request whose `Origin` isn't `CHUMMER5_PUBLIC_URL` (the root
`conftest.py` sets it to `PUBLIC_URL` for every test), and its cookies are `Secure`, which httpx
only sends over https. So a hosted client talks to `PUBLIC_URL` and sends it as its `Origin`, the
way a browser on the real site would.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

PUBLIC_URL = "https://testserver"


def hosted_client(app: FastAPI, **kwargs: Any) -> TestClient:
    kwargs.setdefault("follow_redirects", False)
    headers = {"Origin": PUBLIC_URL, **kwargs.pop("headers", {})}
    return TestClient(app, base_url=PUBLIC_URL, headers=headers, **kwargs)
