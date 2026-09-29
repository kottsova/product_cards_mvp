"""Validated stage-3 research registry and bounded checkpointed probes."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit

from .endpoint_probe import AccessProbe, ProbePolicy

DEFAULT_RESEARCH = Path(__file__).resolve().parents[1] / "config" / "source_research.v1.json"


def load_source_research(path: str | Path = DEFAULT_RESEARCH) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or len(payload.get("families", ())) != 50:
        raise ValueError("Unsupported or incomplete stage-3 source research registry")
    ids = [item["source_family_id"] for item in payload["families"]]
    ranks = [item["priority_rank"] for item in payload["families"]]
    if len(ids) != len(set(ids)) or ranks != list(range(1, 51)):
        raise ValueError("Research families must be unique and ranked 1..50")
    for item in payload["families"]:
        if item["research_status"] == "official_source_not_found":
            if item["candidate_url"] or not item["no_result_reason"]:
                raise ValueError("Negative research results must have no candidate URL and an explicit reason")
        elif not item["evidence"] or not item["page_hosts"]:
            raise ValueError("Verified sources require hosts and evidence")
    return payload


def run_bounded_research_probes(
    output_path: str | Path,
    *,
    registry_path: str | Path = DEFAULT_RESEARCH,
    min_interval_seconds: float = 1.0,
    timeout_seconds: float = 10.0,
    resume: bool = True,
) -> dict:
    """Probe only declared targets and checkpoint after every source family."""
    output_path = Path(output_path)
    payload = load_source_research(registry_path)
    if resume and output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        done = {x["source_family_id"]: x for x in existing.get("families", ())}
    else:
        done = {}
    probe = AccessProbe(policy=ProbePolicy(
        timeout_seconds=timeout_seconds,
        min_interval_seconds=min_interval_seconds,
    ))
    results = []
    for source in payload["families"]:
        family_id = source["source_family_id"]
        if family_id in done and done[family_id].get("checkpoint", {}).get("status") in {"complete", "stopped", "not_applicable"}:
            prior = done[family_id]
            has_homepage = any(x.get("capability") == "homepage" for x in prior.get("endpoint_results", ()))
            if has_homepage or not source["probe_targets"] or prior["checkpoint"]["status"] == "stopped":
                results.append(prior)
                continue
        item = dict(source)
        endpoints = []
        stopped = False
        stop_reason = ""
        allowed = tuple(dict.fromkeys(source["page_hosts"] + source["support_hosts"] + source["asset_document_hosts"]))
        targets = list(source["probe_targets"])
        if targets and not any(target["capability"] == "homepage" for target in targets):
            homepage = f"https://{allowed[0]}/"
            targets.insert(0, {"url": homepage, "capability": "homepage", "sample_type": "homepage"})
        for target in targets:
            result = probe.probe(
                target["url"], allowed_hosts=allowed,
                capability=target["capability"], sample_type=target["sample_type"],
            )
            endpoints.append(result.to_dict())
            if result.access_status.value in {"captcha_or_blocked", "rate_limited"}:
                stopped = True
                stop_reason = result.access_status.value
                break
        now = datetime.now(timezone.utc).isoformat()
        item["endpoint_results"] = endpoints
        item["checkpoint"] = {
            "status": "not_applicable" if not source["probe_targets"] else ("stopped" if stopped else "complete"),
            "last_checked_at": now,
            "stop_reason": stop_reason,
        }
        results.append(item)
        snapshot = {
            "schema_version": 1,
            "generated_at": now,
            "probe_policy": {
                "declared_targets_only": True,
                "min_interval_seconds": min_interval_seconds,
                "timeout_seconds": timeout_seconds,
                "stop_on_403_429_or_confirmed_challenge": True,
                "protection_bypass": False,
            },
            "families": results + [done[k] for k in done if k not in {x["source_family_id"] for x in results}],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snapshot
