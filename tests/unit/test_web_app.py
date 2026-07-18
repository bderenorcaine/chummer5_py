"""WP13: the web app skeleton runs end to end and the HTMX round trip actually swaps DOM content."""

from fastapi.testclient import TestClient

from chummer5.web.app import create_app


def test_index_page_serves_trivial_page() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Chummer5" in response.text
    assert "Ping the server" in response.text


def test_htmx_round_trip_returns_incremented_fragment() -> None:
    client = TestClient(create_app())

    response = client.post("/ui/counter", data={"count": "0"})

    assert response.status_code == 200
    assert '<span id="counter-value">1</span>' in response.text
    # The returned fragment is swappable in place: it carries the same id="counter" the
    # index page's hx-target selector matches, and no <html>/<body> wrapper.
    assert response.text.strip().startswith('<div id="counter">')


def test_htmx_round_trip_increments_from_a_nonzero_starting_count() -> None:
    client = TestClient(create_app())

    response = client.post("/ui/counter", data={"count": "5"})

    assert '<span id="counter-value">6</span>' in response.text


def test_vendored_htmx_is_served_locally_not_from_a_cdn() -> None:
    client = TestClient(create_app())

    index = client.get("/")
    assert "/static/vendor/htmx/htmx.min.js" in index.text
    assert "cdn" not in index.text.lower()

    script = client.get("/static/vendor/htmx/htmx.min.js")
    assert script.status_code == 200
    assert "htmx" in script.text
