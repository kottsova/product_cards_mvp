"""One bounded read of the observed LG support page using the existing browser worker."""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from product_tool.adapters import policy_fetch
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.census.browser_runtime import BrowserFailure, PlaywrightBrowser, discover_runtime

URL = "https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/"
LOG = ROOT / "data/lg_fetch_log.json"
OUT = Path(__file__).resolve().parent


def main() -> None:
    if "www.lg.com" in policy_fetch.stopped_hosts_from_fetch_log(policy_fetch.read_log(LOG)):
        raise RuntimeError("LG host already stopped by access policy")
    runtime = discover_runtime()
    if not runtime.available:
        raise RuntimeError(runtime.reason)
    budget = BrowserBudget(max_contexts=1, max_queries=1, max_navigations=1,
                           max_network_requests=60, deadline_seconds=45,
                           operation_timeout_seconds=10)
    browser = PlaywrightBrowser(runtime, budget, ("www.lg.com",))
    result: dict = {"url": URL, "budget": {"navigations": 1, "network_requests": 60, "seconds": 45}}
    try:
        browser.start()
        result["navigation"] = browser.call("goto", url=URL, queries=["P12ED.NSAR", "P12ED.USAR"])
        result["outcome"] = "rendered"
    except BrowserFailure as exc:
        result["outcome"] = str(exc)
        result["counts"] = exc.counts
        if str(exc) == "challenge_detected":
            policy_fetch.append_log_entry(LOG, {
                "url": URL, "status_code": 200, "final_url": URL,
                "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "access_status": "captcha_or_blocked", "protection_status": "challenge_confirmed",
            })
    finally:
        browser.close()
        (OUT / "browser_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    brief = {"outcome": result["outcome"]}
    brief["counts"] = result.get("navigation", {}).get("counts", result.get("counts", {}))
    print(json.dumps(brief, ensure_ascii=False))


if __name__ == "__main__":
    main()
