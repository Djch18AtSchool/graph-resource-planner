"""
Prueba E2E de la app web (React + TypeScript) con el motor en Python corriendo en Pyodide.

    pnpm --dir web build                                   # genera web/dist (incluye el motor empaquetado)
    uv run --group e2e pytest -m e2e                       # usa Google Chrome del sistema
    E2E_BROWSER_CHANNEL=chromium uv run --group e2e pytest -m e2e
    E2E_SCREENSHOTS=/ruta uv run --group e2e pytest -m e2e   # guarda capturas

Si web/dist no existe, la prueba lo construye con pnpm. Requiere red (descarga Pyodide del CDN).
"""
from __future__ import annotations

import http.server
import os
import re
import shutil
import subprocess
import threading
from functools import partial
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import Page, expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e
ROOT = Path(__file__).resolve().parents[2]
SITE = Path(os.getenv("E2E_SITE", ROOT / "web" / "dist"))
ENGINE_TIMEOUT_MS = 240_000
STEP_TIMEOUT_MS = 30_000


def _ensure_site() -> Path:
    if not (SITE / "index.html").exists():
        if not shutil.which("pnpm"):
            pytest.skip("No existe web/dist y pnpm no está instalado")
        subprocess.run(["pnpm", "install", "--frozen-lockfile"], cwd=ROOT / "web", check=True)
        subprocess.run(["pnpm", "run", "build"], cwd=ROOT / "web", check=True)
    return SITE


@pytest.fixture(scope="module")
def site_url():
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(_ensure_site()))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


@pytest.fixture(scope="module")
def page(site_url):
    channel = os.getenv("E2E_BROWSER_CHANNEL", "chrome")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=None if channel == "chromium" else channel)
        pg = browser.new_page(viewport={"width": 1440, "height": 960})
        pg.errors = []
        pg.on("pageerror", lambda exc: pg.errors.append(str(exc)))
        pg.goto(site_url)
        expect(pg.get_by_role("button", name="E-commerce")).to_be_enabled(timeout=ENGINE_TIMEOUT_MS)
        yield pg
        browser.close()


def _shot(page: Page, name: str) -> None:
    folder = os.getenv("E2E_SCREENSHOTS")
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(folder) / f"{name}.png"), full_page=True)


def _step_label(page: Page):
    return page.get_by_test_id("step-label")


def test_step1_starts_blank_with_example_pills(page: Page):
    expect(page.get_by_role("heading", name="¿Qué tareas hay que ejecutar?")).to_be_visible()
    expect(page.get_by_text("Aquí aparecerán sus tareas")).to_be_visible()
    expect(page.locator(".cm-placeholder")).to_contain_text("Escriba una tarea por línea")
    expect(page.get_by_role("button", name="Ver conflictos")).to_be_disabled()
    _shot(page, "00-en-blanco")
    page.get_by_role("button", name="E-commerce").click()
    expect(page.get_by_text("12 tareas, 8 recursos")).to_be_visible()
    expect(page.get_by_text("Se detectaron 19 conflictos entre tareas.")).to_be_visible()
    _shot(page, "01-tareas")
    assert not page.errors


def test_step_explanation_is_a_popover(page: Page):
    tip = page.get_by_role("tooltip")
    expect(tip).to_have_count(0)
    page.get_by_role("button", name=re.compile("Qué hacer en este paso")).hover()
    expect(tip).to_contain_text("no pueden ejecutarse al mismo tiempo")
    _shot(page, "01b-popover")
    page.mouse.move(5, 5)
    expect(tip).to_have_count(0)


def test_step1_marks_errors_and_blocks_advancing(page: Page):
    # Arrange
    page.locator(".cm-content").click()
    page.keyboard.press("Control+A")
    # Act
    page.keyboard.type("A: r\nA: s")
    # Assert
    expect(page.get_by_text("Revise la línea 2")).to_be_visible(timeout=STEP_TIMEOUT_MS)
    expect(page.get_by_role("button", name="Ver conflictos")).to_be_disabled()
    _shot(page, "02-error")
    page.get_by_role("button", name="E-commerce").click()
    expect(page.get_by_role("button", name="Ver conflictos")).to_be_enabled(timeout=STEP_TIMEOUT_MS)


def test_step2_explains_each_dsatur_decision(page: Page):
    page.get_by_role("button", name="Ver conflictos").click()
    expect(_step_label(page)).to_have_text("Paso 0 de 12")
    for _ in range(3):
        page.get_by_role("button", name="Paso siguiente").click()
    expect(_step_label(page)).to_have_text("Paso 3 de 12")
    expect(page.get_by_text("Era la más acorralada")).to_be_visible()
    expect(page.get_by_text("siguiente", exact=True)).to_be_visible()
    _shot(page, "03-paso-a-paso")
    page.get_by_role("button", name="Reproducir").click()
    expect(_step_label(page)).to_have_text("Paso 12 de 12", timeout=STEP_TIMEOUT_MS)
    expect(page.get_by_text("Ninguna línea une dos tareas del mismo color")).to_be_visible()
    page.get_by_role("radio", name="Agrupado por lote").click()
    expect(page.locator(".react-flow__node")).to_have_count(12)
    _shot(page, "04-por-lotes")


def test_step2_matrix_view(page: Page):
    page.get_by_role("radio", name="Matriz").click()
    expect(page.get_by_text("A[i][j] = 1")).to_be_visible()
    page.get_by_role("radio", name="Grafo").click()


def test_step3_shows_the_plan_as_stages(page: Page):
    page.get_by_role("button", name="Ver plan").click()
    expect(page.get_by_test_id("chi")).to_have_text("χ(G) = 4")
    expect(page.get_by_text("Es el mínimo posible")).to_be_visible()
    expect(page.get_by_text("Lote 4", exact=True)).to_be_visible()
    _shot(page, "05-plan")
    page.get_by_role("radio", name="Cronograma").click()
    expect(page.get_by_text("Lote 1", exact=False).first).to_be_visible()
    assert not page.errors


def test_hard_case_suggests_switching_to_dsatur(page: Page):
    # Arrange: caso corona con Welsh-Powell
    page.get_by_role("button", name="Tareas").click()
    page.get_by_role("button", name="Caso difícil").click()
    expect(page.get_by_text("Se detectaron 20 conflictos entre tareas.")).to_be_visible(timeout=STEP_TIMEOUT_MS)
    page.get_by_role("button", name="Ver conflictos").click()
    page.get_by_role("radio", name="Welsh-Powell").click()
    expect(page.get_by_text("Welsh-Powell", exact=True).first).to_be_visible()
    # Act
    page.get_by_role("button", name="Ver plan").click()
    # Assert
    expect(page.get_by_text("Pero bastan 2.")).to_be_visible(timeout=STEP_TIMEOUT_MS)
    _shot(page, "06-caso-dificil")
    page.get_by_role("button", name="Usar DSatur").click()
    expect(page.get_by_text("DSatur agrupa las 10 tareas en 2 lotes.")).to_be_visible(timeout=STEP_TIMEOUT_MS)


def test_stress_page_runs_10_100_and_1000(page: Page):
    page.get_by_role("button", name="Prueba de estrés").click()
    page.get_by_role("button", name="Ejecutar prueba").click()
    rows = page.get_by_test_id("stress-table").locator("tbody tr")
    expect(rows).to_have_count(3, timeout=ENGINE_TIMEOUT_MS)
    expect(rows.nth(2)).to_contain_text("1000")
    _shot(page, "07-estres")
    assert not page.errors
