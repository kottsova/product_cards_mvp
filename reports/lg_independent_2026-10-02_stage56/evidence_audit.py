from __future__ import annotations
import json,sys
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from product_tool import jobs
from product_tool.adapters.lg import _product_designation,lg_base_model
from product_tool.fetch_history import latest_source_snapshot
from product_tool.lg_identity import photo_tied_to_article
HERE=Path(__file__).resolve().parent
DB=ROOT/"data/stage56/stage56.sqlite3"
OUT=HERE/"evidence_audit.json"
def main():
 if OUT.exists():raise SystemExit("Already audited")
 first=json.loads((HERE/"first_pass.json").read_text(encoding="utf8"))
 issues=[]; pages=0; facts=0; photos=0; unconfirmed_candidates=0; support_as_pdp=0
 for row in first["rows"]:
  pid=row["product_id"]; article=row["article"]
  source_list=jobs.get_source_pages(DB,pid)
  source={p["source_key"]:p for p in source_list}
  for p in source_list:
   if p["source_key"] not in ("lg_kz","lg_ru") or p["match_level"]!="full_sku":continue
   pages+=1
   snap=latest_source_snapshot(DB,pid,p["source_key"])
   if not snap or snap["source_url"]!=p["url"] or not snap["content"]:
    issues.append([article,p["source_key"],"missing_matching_snapshot"]);continue
   region=p["source_key"][3:]
   _,level,_=_product_designation(BeautifulSoup(snap["content"],"html.parser"),article,lg_base_model(article),region=region)
   if level!="full_sku":issues.append([article,p["source_key"],"snapshot_not_exact",level])
  all_facts=jobs.get_facts(DB,pid)
  for x in jobs.get_resolved(DB,pid):
   if not x["full_sku_confirmed"] or x["conflict"] or not x["selected_value"]:continue
   facts+=1
   src=x["selected_source"]
   if src not in ("lg_kz","lg_ru","lg_global","sulpak","dns"):
    issues.append([article,x["normalized_name"],"unexpected_confirmed_source",src]);continue
   p=source.get(src)
   if not p or p["match_level"] not in ("full_sku","model_and_code_confirmed") or p["error"]:
    issues.append([article,x["normalized_name"],"not_exact_page",src]);continue
   if not any(f["source_key"]==src and f["normalized_name"]==x["normalized_name"]
              and f["normalized_value"]==x["selected_value"] for f in all_facts):
    issues.append([article,x["normalized_name"],"confirmed_value_without_fact",src])
  for photo in jobs.get_photo_candidates(DB,pid,include_excluded=False):
   if not photo["selected"]:continue
   if photo_tied_to_article(photo,source_list):
    photos+=1
   else:
    unconfirmed_candidates+=1
  support_as_pdp+=sum(1 for p in source_list if p["source_key"].endswith("_support") and p["source_key"] in row["official_exact_regions"])
 payload={"exact_kz_ru_pages_rechecked_from_html":pages,"confirmed_facts_audited":facts,
          "confirmed_selected_photos_audited":photos,"selected_unconfirmed_photo_candidates":unconfirmed_candidates,
          "support_pages_counted_as_pdp":support_as_pdp,
          "false_confirmed_detected":len(issues),"issues":issues}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print(json.dumps({k:v for k,v in payload.items() if k!="issues"}))
if __name__=="__main__":main()
