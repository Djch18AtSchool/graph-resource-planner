"""
Prueba E2E de la app web: Chromium real + Pyodide ejecutando el codigo Python del repositorio.

    uv run --group e2e pytest -m e2e                       # usa Google Chrome del sistema
    E2E_BROWSER_CHANNEL=chromium uv run --group e2e pytest -m e2e
    E2E_SCREENSHOTS=/ruta uv run --group e2e pytest -m e2e   # guarda capturas

Requiere red (descarga Pyodide y las bibliotecas JS de los CDN). Solo usa el modo offline: no
llama a ningun LLM ni necesita API key.
"""
from __future__ import annotations

import http.server
import os
import re
import threading
from functools import partial
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import Page, expect, sync_playwright  # noqa: E402

from scripts.build_web import build  # noqa: E402

pytestmark = pytest.mark.e2e
PYODIDE_TIMEOUT_MS = 240_000
ANALYZE_TIMEOUT_MS = 60_000


@pytest.fixture(scope="module")
def site_url(tmp_path_factory):
    site = build(tmp_path_factory.mktemp("site") / "dist")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


@pytest.fixture(scope="module")
def page(site_url):
    channel = os.getenv("E2E_BROWSER_CHANNEL", "chrome")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=None if channel == "chromium" else channel)
        context = browser.new_context(viewport={"width": 1400, "height": 1000})
        pg = context.new_page()
        pg.errors = []
        pg.on("pageerror", lambda exc: pg.errors.append(str(exc)))
        pg.goto(site_url)
        expect(pg.locator("#status")).to_have_text("Python listo", timeout=PYODIDE_TIMEOUT_MS)
        yield pg
        browser.close()


def _shot(page: Page, name: str) -> None:
    folder = os.getenv("E2E_SCREENSHOTS")
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(folder) / f"{name}.png"), full_page=True)


def _run(page: Page) -> None:
    page.click("#run")
    expect(page.locator("#run")).to_have_text("Analizar", timeout=ANALYZE_TIMEOUT_MS)


def test_natural_language_offline_produces_plan_and_crossing_free_drawing(page: Page):
    # Arrange
    page.fill("#text", "Arquitectura de e-commerce con pagos, inventario y notificaciones")
    # Act
    _run(page)
    # Assert
    expect(page.locator("#output")).to_be_visible()
    expect(page.locator("#metrics")).to_contain_text("χ(G) = 4 (exacto)")
    expect(page.locator("#crossings")).to_have_text("0 cruce(s) en el dibujo")
    expect(page.locator("#plan")).to_contain_text("Lote 4")
    assert page.evaluate("document.querySelectorAll('#cy canvas').length") > 0
    _shot(page, "01-ecommerce-planar")
    assert not page.errors


def test_non_planar_example_shows_kuratowski_and_virtual_nodes(page: Page):
    # Arrange
    page.click("[data-mode=example]")
    page.select_option("#example", "ml")
    # Act
    _run(page)
    # Assert
    expect(page.locator("#metrics")).to_contain_text("K3,3")
    expect(page.locator("#kura-wrap")).to_be_visible()
    page.check("#kura")
    expect(page.locator("#crossings")).to_have_text("0 cruce(s) en el dibujo")
    _shot(page, "02-ml-kuratowski")
    page.click("[data-layout=spring]")
    expect(page.locator("#crossings")).to_have_text(re.compile(r"^[1-9]\d* cruce"))
    _shot(page, "03-ml-spring")
    page.click("[data-layout=planar]")


def test_report_matrix_and_times_tabs(page: Page):
    page.click("[data-tab=report]")
    expect(page.locator("#report")).to_contain_text("Datos verificados")
    _shot(page, "04-report")
    page.click("[data-tab=matrix]")
    expect(page.locator("#matrix table")).to_be_visible()
    page.click("[data-tab=times]")
    expect(page.locator("#times")).to_contain_text("Dibujo plano")


def test_invalid_json_shows_friendly_error(page: Page):
    page.click("[data-mode=json]")
    page.fill("#spec-json", '{"nodes": [{"id": "a", "label": "A"}], "edges": [{"source": "a", "target": "z", "kind": "conflict"}]}')
    _run(page)
    expect(page.locator(".alert-error")).to_contain_text("nodos inexistentes")


def test_anthropic_without_key_is_blocked_client_side(page: Page):
    page.select_option("#provider", "anthropic")
    page.fill("#api-key", "")
    page.click("[data-mode=text]")
    page.click("#run")
    expect(page.locator(".alert-error")).to_contain_text("API key")
    page.select_option("#provider", "offline")
    assert not page.errors
