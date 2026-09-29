"""Bounded Samsung route check for one charger and one cable, using observed URLs only."""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))
logging.disable(logging.CRITICAL)

import requests
from product_tool.adapters.common import SourceError, fetch_with_retry
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log
from product_tool.adapters.policy_session import PolicyAwareSession, RequestBudget, record_responses, request_budget
from product_tool.adapters.samsung import parse_product_page, product_data_codes
from product_tool.adapters.samsung_source import PAGE_HOSTS, USER_AGENT
from product_tool.adapters.sitemap_urls import sitemap_locs

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def stopped(path):
    if not path.exists():
        return []
    return sorted(stopped_hosts_from_fetch_log(x for x in json.loads(path.read_text(encoding="utf-8")) if isinstance(x, dict)))

def main():
    declaration=json.loads((STAGE/"raw/route_declaration.json").read_text(encoding="utf-8"))
    assert now() > declaration["declared_at"]
    assert declaration["budget"]["max_real_requests_total"] == 6
    workdir=STAGE/"route_check/workdir"
    assert not workdir.exists(), "run once only"
    workdir.mkdir(parents=True)
    plain=requests.Session()
    plain.headers.update({"User-Agent":USER_AGENT,"Accept-Language":"ru-RU,ru;q=0.9,en;q=0.7"})
    log=workdir/"samsung_fetch_log.json"
    client=PolicyAwareSession(log,allowed_hosts=PAGE_HOSTS,underlying=plain,max_bytes=declaration["budget"]["page_cap_bytes"],min_interval_seconds=declaration["budget"]["pacing_seconds"])
    budget=RequestBudget(max_per_row=6,max_total=6)
    budget.begin_row("official_route_check")
    steps=[]
    all_urls=[]
    page_results={}
    halted=""
    def get(url,kind):
        nonlocal halted
        if halted or stopped(log):
            steps.append({"kind":kind,"url":url,"skipped":"host stopped"})
            return None
        try:
            response=fetch_with_retry(client,url,deadline=1e12,clock=lambda:0.0)
        except SourceError as exc:
            error=str(exc)[:250]
            steps.append({"kind":kind,"url":url,"error":error})
            if any(marker in error for marker in ("policy_host_stopped","HTTP 401","HTTP 403","HTTP 429","challenge")) or stopped(log):
                halted=error
            return None
        steps.append({"kind":kind,"url":url,"status":response.status_code,"bytes":len(response.content),"truncated":bool(response.truncated)})
        return response
    with record_responses(STAGE/"route_check/responses"),request_budget(budget):
        index=get(declaration["planned_addresses"]["index"],"index")
        listed=sitemap_locs(index.text) if index else []
        if index and declaration["planned_addresses"]["im"] in listed:
            im=get(declaration["planned_addresses"]["im"],"sitemap")
            if im:
                all_urls+=sitemap_locs(im.text)
        if index and declaration["planned_addresses"]["assorted"] in listed:
            assorted=get(declaration["planned_addresses"]["assorted"],"sitemap")
            if assorted:
                all_urls+=sitemap_locs(assorted.text)
        charger_code="EP-T4511XBEGEU"
        cable_code="EP-DA705BBRGRU"
        exact_charger=[u for u in all_urls if charger_code.casefold() in u.casefold()]
        exact_cable=[u for u in all_urls if cable_code.casefold() in u.casefold()]
        family=declaration["observed"]["charger_family_other_region_url"]
        charger_url=exact_charger[0] if len(exact_charger)==1 else family if family in all_urls else ""
        cable_url=declaration["observed"]["cable_exact_url_candidate"] if declaration["observed"]["cable_exact_url_candidate"] in exact_cable else ""
        for code,url,label in ((charger_code,charger_url,"charger"),(cable_code,cable_url,"cable")):
            if not url:
                page_results[code]={"page_url":"","route":"no currently listed page candidate"}
                continue
            response=get(url,"product_page")
            if response is None:
                page_results[code]={"page_url":url,"route":"page not fetched"}
                continue
            card=parse_product_page(response.text,url,code)
            page_results[code]={
                "page_url":url,"route":"exact_sitemap_candidate" if code.casefold() in url.casefold() else "observed_other_region_family_candidate",
                "identity":{"level":card.identity.level,"strength":card.identity.evidence_strength,"jsonld_sku":card.identity.jsonld_sku,"title":card.identity.title,"is_product_page":card.identity.is_product_page,"evidence":card.identity.evidence,"open_differences":card.identity.open_differences},
                "product_data_codes":sorted(product_data_codes(response.text)),
                "specs":[{"name":s.name,"value":s.value} for s in card.specs],
                "photos":{"full_size":len(card.photos.photos),"thumbnails":len(card.photos.thumbnails),"three_d":len(card.photos.three_d)},
                "document_links":[{"href":d.href,"file_name":d.file_name,"model_name":d.model_name,"language_hint":d.language_hint} for d in card.documents],
                "gaps":card.gaps,
            }
    result={"declared_at":declaration["declared_at"],"started_at":steps[0].get("at",now()) if steps else now(),"finished_at":now(),"budget":{"max":6,"spent":budget.total,"log":budget.log},"steps":steps,"current_index_locs":listed,"currently_listed_exact_charger_urls":exact_charger if index else [],"currently_listed_exact_cable_urls":exact_cable if index else [],"pages":page_results,"stopped_hosts":stopped(log),"halted":halted}
    (STAGE/"raw/route_check_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"spent":budget.total,"stopped_hosts":result["stopped_hosts"],"steps":steps,"pages":{k:{"route":v.get("route"),"page_url":v.get("page_url"),"identity":v.get("identity"),"specs":len(v.get("specs",[])),"photos":v.get("photos"),"document_links":v.get("document_links")} for k,v in page_results.items()}},ensure_ascii=True,indent=2))

if __name__=="__main__":
    main()
