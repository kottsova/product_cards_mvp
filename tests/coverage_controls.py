"""Control cases for the coverage executor: real HyperX pages saved in Stages
11/11.1 and the ordinary LG/Sulpak adapters, all served from memory.

Nothing here opens a socket. `run_controls()` is used by both the unit tests
(tests/test_coverage_queue.py) and the Stage 17 report script.
"""
from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from product_tool.adapters.common import SourceDocument
from product_tool.adapters.hyperx import HyperXAdapter, KNOWN_URLS
from product_tool.adapters.lg import LG_KZ_SITEMAP, LG_RU_SITEMAP, LGAdapter, LGRUAdapter, lg_base_model, normalize_lg_sku
from product_tool.adapters.sulpak import SulpakAdapter
from product_tool.census.endpoint_probe import ProbePolicy
from product_tool.coverage import executor, planner

ROOT = Path(__file__).resolve().parents[1]
STAGE11_RAW = ROOT / "reports/source_census_2026-09-23_stage11/raw"
STAGE11_1_RAW = ROOT / "reports/source_census_2026-09-23_stage11_1/raw"
MICROPHONE_PAGE = STAGE11_RAW / "hyperx_quadcast_2s_product_page.html.txt"
MOUSE_PAGE = STAGE11_1_RAW / "hyperx_mouse_product_page.html.txt"
KEYBOARD_PAGE = STAGE11_1_RAW / "hyperx_keyboard_product_page.html.txt"
NO_DELAY = ProbePolicy(min_interval_seconds=0.0)  # in-memory transports need no politeness delay
KEYBOARD_URL = "https://hyperx.com/products/hyperx-alloy-rise-75-mechanical-gaming-keyboard"


class FixtureResponse:
    """Shaped for both fetch stacks: AccessProbe (HyperX) and fetch_with_retry (LG, Sulpak)."""

    def __init__(self, url: str, text: str, status: int = 200):
        self.url, self.text, self.status_code = url, text, status
        self.content = text.encode("utf-8")
        self.history = ()
        self.headers: dict = {}
        self.encoding = "utf-8"
        self.cookies = type("Cookies", (), {"get_dict": lambda self: {}})()

    def iter_content(self, chunk_size):
        return iter((self.content,))

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")


class FixtureSession:
    """Serves saved pages; any URL it does not hold is refused and recorded."""

    def __init__(self, pages: dict[str, tuple[int, str]]):
        self.pages = pages
        self.calls: list[str] = []
        self.refused: list[str] = []
        self.headers: dict = {}

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url.endswith("/sitemap.xml") and url not in self.pages:
            raise AssertionError(f"unexpected sitemap {url}")
        if url not in self.pages:
            self.refused.append(url)
            import requests

            raise requests.ConnectionError(f"no fixture transport for {url}")
        status, text = self.pages[url]
        return FixtureResponse(url, text, status)


class NoDealer:
    """The dealer fallback is not what these controls exercise."""
    source_key, site_name, document_urls = "dns", "DNS", {}

    def find_source(self, search_code, *, deadline, model_tokens=None, brand="", name="", missing_fields=None):
        return SourceDocument("dns", "DNS", "", match_level="unknown", evidence="Нет проверенного дилерского кандидата.")

    def find_documents(self, search_code, *, deadline, **kwargs):
        return [], "Дилерский документ не проверялся в контрольном прогоне."


def _hyperx_session(*, blocked_url: str = "") -> FixtureSession:
    pages = {
        KNOWN_URLS["9A273AA"]: (200, MICROPHONE_PAGE.read_text(encoding="utf-8")),
        KNOWN_URLS["A1KY6AA"]: (200, MOUSE_PAGE.read_text(encoding="utf-8")),
        KEYBOARD_URL: (200, KEYBOARD_PAGE.read_text(encoding="utf-8")),
    }
    if blocked_url:
        pages[blocked_url] = (403, "blocked")
    return FixtureSession(pages)


def _lg_pages(sku: str, sulpak_url: str) -> dict[str, tuple[int, str]]:
    full, base = normalize_lg_sku(sku), lg_base_model(sku)
    kz_url = f"https://www.lg.com/kz/microwave-ovens/{full.lower()}/"
    kz = (f'<html><body><h1>LG {full}</h1><section id="pdp-overview-section"><p>Микроволновая печь {full}.</p></section>'
          '<section id="pdp-specs-section"><div class="c-compare-selling--all">'
          '<div class="c-compare-selling__item"><span class="c-compare-selling__spec-name">Объем</span><span class="c-compare-selling__spec-desc">20 л</span></div>'
          '<div class="c-compare-selling__item"><span class="c-compare-selling__spec-name">Цвет</span><span class="c-compare-selling__spec-desc">Серебристый</span></div>'
          '</div></section></body></html>')
    sulpak = (f'<html><body><h1>Микроволновая печь LG {full}</h1><p>Артикул: {full}</p><table class="characteristics">'
              '<tr><th>Объем</th><td>20 л</td></tr><tr><th>Цвет</th><td>Серебристый</td></tr></table></body></html>')
    sitemap = f"<urlset><url><loc>{escape(kz_url)}</loc></url></urlset>"
    return {LG_KZ_SITEMAP: (200, sitemap), kz_url: (200, kz), sulpak_url: (200, sulpak),
            LG_RU_SITEMAP: (200, "<urlset></urlset>")}  # the RU sitemap lists no page for this row


def _unit(plan_units: list[dict], brand: str, sku: str) -> dict:
    return next(u for u in plan_units if u["brand"] == brand and u["seller_sku"] == sku)


def run_controls(out_dir: Path, plan_units: list[dict] | None = None) -> dict:
    """Run every control through executor.run_units() and return the checkpoint."""
    if plan_units is None:
        plan_units = planner.build_plan()["units"]
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = out_dir / "control_checkpoint.json"
    for stale in (checkpoint_path, out_dir / "batches.sqlite3", out_dir / "hyperx_fetch_log.json"):
        if stale.exists():
            stale.unlink()
    clock = lambda: 0.0  # noqa: E731 - fixed clock: fixtures never time out

    def hyperx_factories(session):
        log = out_dir / "hyperx_fetch_log.json"
        return executor.RunFactories(
            session=session,
            hyperx_adapter_factory=lambda: HyperXAdapter(session, clock=clock, fetch_log_path=log, policy=NO_DELAY),
            dns_adapter_factory=lambda: NoDealer(),
        )

    mic, mouse = _unit(plan_units, "HYPERX", "9A273AA"), _unit(plan_units, "HYPERX", "A1KY6AA")
    duo = _unit(plan_units, "HYPERX", "4P5E2AA")           # no confirmed URL
    keyboard = _unit(plan_units, "HYPERX", "7G7A4AA#ACB")  # confirmed region mismatch
    session = _hyperx_session()
    factories = hyperx_factories(session)
    executor.run_units([mic, mouse, duo, keyboard], workdir=out_dir, checkpoint_path=checkpoint_path, factories=factories, clock=clock)

    # The keyboard is stopped by the plan itself. To show what the ordinary
    # adapter does with the negative variant, force the same row through
    # run_once() as if an exact URL had been supplied for it.
    forced = dict(keyboard, status="ready_to_run", reason="forced_negative_control", next_action="run_once", hosts=["hyperx.com"], unit_id="control-negative-keyboard", catalog_row=keyboard["catalog_row"] + 100000)
    negative_session = _hyperx_session()
    executor.run_units(
        [forced], workdir=out_dir, checkpoint_path=checkpoint_path,
        factories=executor.RunFactories(
            session=negative_session,
            hyperx_adapter_factory=lambda: HyperXAdapter(negative_session, clock=clock, urls={"7G7A4AA#ACB": KEYBOARD_URL}, fetch_log_path=out_dir / "negative_fetch_log.json", policy=NO_DELAY),
            dns_adapter_factory=lambda: NoDealer(),
            fetch_log_paths=(out_dir / "negative_fetch_log.json",),
        ), clock=clock)

    # A second pass over the finished checkpoint: nothing is called again.
    calls_before = list(session.calls)
    executor.run_units([mic, mouse, duo, keyboard], workdir=out_dir, checkpoint_path=checkpoint_path, factories=factories, clock=clock)
    assert session.calls == calls_before, "resume made a new call"

    # Host stop across a "restart": one 403, then a brand-new adapter and session.
    stop_dir = out_dir / "host_stop"
    stop_dir.mkdir(exist_ok=True)
    stop_checkpoint = stop_dir / "control_checkpoint.json"
    for stale in (stop_checkpoint, stop_dir / "batches.sqlite3", stop_dir / "hyperx_fetch_log.json"):
        if stale.exists():
            stale.unlink()
    blocking = _hyperx_session(blocked_url=KNOWN_URLS["9A273AA"])
    stop_log = stop_dir / "hyperx_fetch_log.json"
    first = executor.RunFactories(session=blocking, hyperx_adapter_factory=lambda: HyperXAdapter(blocking, clock=clock, fetch_log_path=stop_log, policy=NO_DELAY), dns_adapter_factory=lambda: NoDealer(), fetch_log_paths=(stop_log,))
    executor.run_units([mic], workdir=stop_dir, checkpoint_path=stop_checkpoint, factories=first, clock=clock)
    restarted = _hyperx_session()  # a new process: new session, new adapter, same log on disk
    second = executor.RunFactories(session=restarted, hyperx_adapter_factory=lambda: HyperXAdapter(restarted, clock=clock, fetch_log_path=stop_log, policy=NO_DELAY), dns_adapter_factory=lambda: NoDealer(), fetch_log_paths=(stop_log,))
    executor.run_units([mouse], workdir=stop_dir, checkpoint_path=stop_checkpoint, factories=second, clock=clock)
    assert restarted.calls == [], "a stopped host was contacted after restart"

    # LG: the ordinary official + supplier adapters against fixtures, on a real catalog row.
    # An isolated fake-transport control still runs one LG row even when the
    # real LG host is stopped. Production planning keeps the stop unchanged.
    lg_unit = next(u for u in plan_units if u["brand"] == "LG" and u["category"] == "Микроволновые печи")
    lg_unit = dict(lg_unit, status="ready_to_run", reason="forced_offline_fixture_control", next_action="run_once")
    sulpak_url = "https://www.sulpak.kz/g/mikrovolnovaya_pech_lg_" + lg_unit["seller_sku"].lower()
    lg_session = FixtureSession(_lg_pages(lg_unit["seller_sku"], sulpak_url))
    lg_dir = out_dir / "lg"
    lg_dir.mkdir(exist_ok=True)
    lg_checkpoint = lg_dir / "control_checkpoint.json"
    for stale in (lg_checkpoint, lg_dir / "batches.sqlite3"):
        if stale.exists():
            stale.unlink()
    lg_factories = executor.RunFactories(
        session=lg_session,
        adapter_factory=lambda: (LGAdapter(lg_session, clock=clock), LGRUAdapter(lg_session, clock=clock),
                                 SulpakAdapter(lg_session, clock=clock, urls={lg_unit["seller_sku"].upper(): sulpak_url})),
        dns_adapter_factory=lambda: NoDealer(),
    )
    executor.run_units([lg_unit], workdir=lg_dir, checkpoint_path=lg_checkpoint, factories=lg_factories, clock=clock)

    return {
        "main": executor.load_checkpoint(checkpoint_path),
        "host_stop": executor.load_checkpoint(stop_checkpoint),
        "lg": executor.load_checkpoint(lg_checkpoint),
        "sessions": {"hyperx_calls": session.calls, "negative_calls": negative_session.calls, "restarted_session_calls": restarted.calls, "lg_calls": lg_session.calls,
                     "lg_refused": lg_session.refused},
        "units": {"mic": mic["unit_id"], "mouse": mouse["unit_id"], "duo": duo["unit_id"], "keyboard": keyboard["unit_id"],
                  "negative_control": "control-negative-keyboard", "lg": lg_unit["unit_id"]},
    }


if __name__ == "__main__":
    import sys
    import tempfile

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    print(json.dumps(executor.summarize(run_controls(target)["main"]), ensure_ascii=False, indent=2))
