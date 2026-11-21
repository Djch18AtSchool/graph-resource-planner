"""
Prueba E2E de la app web: Chromium real + Pyodide ejecutando el codigo Python del repositorio.

    uv run --group e2e pytest -m e2e                       # usa Google Chrome del sistema
    E2E_BROWSER_CHANNEL=chromium uv run --group e2e pytest -m e2e
    E2E_SCREENSHOTS=/ruta uv run --group e2e pytest -m e2e   # guarda capturas

Requiere red (descarga Pyodide y Cytoscape de los CDN).
"""
from __future__ import annotations

import http.server
import os
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
        expect(pg.locator("#output")).to_be_visible(timeout=PYODIDE_TIMEOUT_MS)    # corre el 1er ejemplo
        expect(pg.locator("#status")).to_have_text("Listo", timeout=ANALYZE_TIMEOUT_MS)
        yield pg
        browser.close()


def _shot(page: Page, name: str) -> None:
    folder = os.getenv("E2E_SCREENSHOTS")
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(folder) / f"{name}.png"), full_page=True)


def _wait_idle(page: Page) -> None:
    expect(page.locator("#run")).to_have_text("Asignar lotes", timeout=ANALYZE_TIMEOUT_MS)
    expect(page.locator("#status")).to_have_text("Listo", timeout=ANALYZE_TIMEOUT_MS)


def _metric(page: Page, key: str):
    return page.locator(f"[data-metric={key}] .v")


def test_first_example_runs_on_load_and_shows_batches(page: Page):
    expect(page.locator("#chi")).to_have_text("χ(G) = 4")
    expect(page.locator("#claim")).to_contain_text("no se puede hacer mejor")
    expect(_metric(page, "colors")).to_have_text("4")
    expect(page.locator("#strip .lot")).to_have_count(4)
    expect(page.locator("#plan")).to_contain_text("Lote 4")
    expect(page.locator("#step-label")).to_have_text("Paso 12/12")
    assert page.evaluate("document.querySelectorAll('#cy canvas').length") > 0
    _shot(page, "01-microservicios")
    assert not page.errors


def test_hovering_a_batch_in_the_strip_names_its_tasks(page: Page):
    page.hover("#strip .lot >> nth=1")
    expect(page.locator("#inspector")).to_contain_text("Lote 2, de t =")
    page.mouse.move(5, 5)
    expect(page.locator("#inspector")).to_contain_text("Listo:")


def test_step_by_step_explains_each_decision(page: Page):
    # Arrange
    page.click("#step-first")
    expect(page.locator("#inspector")).to_contain_text("Ninguna tarea tiene lote")
    # Act
    page.locator("#step").fill("3")
    # Assert
    expect(page.locator("#step-label")).to_have_text("Paso 3/12")
    expect(page.locator("#inspector")).to_contain_text("DSatur elige la tarea más acorralada")
    _shot(page, "02-paso-a-paso")
    page.click("#step-play")
    expect(page.locator("#step-label")).to_have_text("Paso 12/12", timeout=15_000)
    expect(page.locator("#inspector")).to_contain_text("Listo:")


def test_corona_example_shows_welsh_powell_uses_more_batches(page: Page):
    # Arrange: cambiar de algoritmo recalcula lo que está en pantalla
    page.click("[data-algorithm=welsh_powell]")
    _wait_idle(page)
    # Act
    page.select_option("#example", "corona")
    _wait_idle(page)
    # Assert
    expect(_metric(page, "colors")).to_have_text("5")
    expect(_metric(page, "alternative")).to_have_text("2")
    expect(page.locator("#chi")).to_have_text("χ(G) = 2")
    expect(page.locator("#claim")).to_contain_text("bastan 2")
    page.click("[data-layout=batches]")
    page.check("#clique")
    _shot(page, "03-corona-por-lotes")
    page.uncheck("#clique")
    page.click("[data-layout=force]")
    page.click("[data-algorithm=dsatur]")
    _wait_idle(page)
    expect(_metric(page, "colors")).to_have_text("2")


def test_detail_tabs(page: Page):
    page.select_option("#example", "examenes")
    _wait_idle(page)
    page.click("[data-tab=resources]")
    expect(page.locator("#resources table")).to_contain_text("K3")
    page.click("[data-tab=matrix]")
    expect(page.locator("#matrix table")).to_be_visible()
    page.click("[data-tab=times]")
    expect(page.locator("#times")).to_contain_text("Coloración")
    page.click("[data-tab=plan]")
    expect(page.locator("#plan .gantt-bar").first).to_be_visible()
    _shot(page, "04-examenes-gantt")


def test_invalid_text_shows_error_and_marks_the_line(page: Page):
    page.fill("#problem", "A: r\nB: s\nA: t")
    page.click("#run")
    expect(page.locator(".alert-error")).to_contain_text("aparece dos veces")
    expect(page.locator("#gutter .err")).to_have_text("3")
    _wait_idle(page)


def test_stress_1000_nodes_in_the_browser(page: Page):
    page.click("[data-n='1000']")
    _wait_idle(page)
    expect(_metric(page, "tasks")).to_have_text("1000")
    expect(page.locator("[data-layout=force]")).to_be_disabled()
    expect(page.locator("[data-layout=batches]")).to_have_attribute("aria-checked", "true")
    _shot(page, "05-estres-1000")
    assert not page.errors


def test_dark_theme_renders(page: Page):
    page.select_option("#example", "microservicios")
    _wait_idle(page)
    page.click("#theme-toggle")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    _shot(page, "06-pizarra")
    page.click("#theme-toggle")
    assert not page.errors
