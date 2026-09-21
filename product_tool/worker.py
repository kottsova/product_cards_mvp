"""Bounded background worker for LG official regions and trusted suppliers."""
from __future__ import annotations
import argparse, logging, os, time
from pathlib import Path
from typing import Callable
from . import jobs
from .adapters.common import SourceDocument
from .adapters.lg import LGAdapter, LGRUAdapter, lg_base_model, normalize_lg_sku
from .adapters.mechta import MechtaAdapter
from .adapters.sulpak import SulpakAdapter

LOGGER=logging.getLogger(__name__)
PROJECT_DIR=Path(__file__).resolve().parents[1]
TOTAL_BUDGET_SECONDS=60
OFFICIAL_BUDGET_SECONDS=20
FALLBACK_BUDGET_SECONDS=30

def _save(database, product_id, document, stages):
    jobs.save_source_document(database,product_id,document,update_description=2 in stages,update_attributes=3 in stages,update_photos=4 in stages)

def run_once(database: Path, adapter_factory=None, *, clock: Callable[[],float]=time.monotonic) -> bool:
    job=jobs.claim_next(database)
    if job is None: return False
    job_id,product_id=job["id"],job["product_id"]
    try:
        product=jobs.get_product(database,product_id)
        if not product:
            jobs.finish(database,job_id,"error","Подтверждённый товар не найден."); return True
        if product["brand"].strip().casefold() not in {"lg","lg electronics","лджи","элджи"}:
            jobs.finish(database,job_id,"error","Fallback Mechta и Sulpak разрешён только для LG."); return True
        start=clock(); total_deadline=start+TOTAL_BUDGET_SECONDS
        full=normalize_lg_sku(product["search_code"]); base=lg_base_model(full); stages=job["stages"]
        jobs.progress(database,job_id,1,f"LG: проверяем полный артикул {full} и базовую модель {base}.")
        if adapter_factory:
            supplied=tuple(adapter_factory())
            if len(supplied)==3: lg_kz,sulpak,mechta=supplied; lg_ru=None
            else: lg_kz,lg_ru,sulpak,mechta=supplied
        else:
            lg_kz,lg_ru,sulpak,mechta=LGAdapter(clock=clock),LGRUAdapter(clock=clock),SulpakAdapter(clock=clock),MechtaAdapter(clock=clock)
        official_deadline=min(total_deadline,start+OFFICIAL_BUDGET_SECONDS)
        official_docs=[]
        for adapter in (lg_kz,lg_ru):
            if adapter is None: continue
            if clock()>=official_deadline:
                doc=SourceDocument(adapter.source_key,adapter.site_name,"",error="Регион не проверен: исчерпан общий 20-секундный бюджет официального поиска.")
            else: doc=adapter.find_source(full,deadline=official_deadline)
            official_docs.append(doc); _save(database,product_id,doc,stages)
            jobs.progress(database,job_id,1,f"{doc.site_name}: {doc.match_level}. {doc.error or doc.evidence}",level="warning" if doc.error or doc.match_level not in {"full_sku","base_model"} else "info",source_url=doc.url)
        fallback_deadline=min(total_deadline,clock()+FALLBACK_BUDGET_SECONDS)
        for adapter in (sulpak,mechta):
            if clock()>=fallback_deadline:
                doc=SourceDocument(adapter.source_key,adapter.site_name,"",error="Источник не проверен: исчерпан 30-секундный бюджет fallback.")
            else: doc=adapter.find_source(full,deadline=fallback_deadline)
            _save(database,product_id,doc,stages)
            jobs.progress(database,job_id,1,f"{doc.site_name}: {doc.match_level}. {doc.error or doc.evidence}",level="warning" if doc.error or doc.match_level!="full_sku" else "info",source_url=doc.url)
        if 3 in stages:
            jobs.progress(database,job_id,3,"Нормализуем и сравниваем характеристики."); jobs.resolve_product(database,product_id)
        if 6 in stages:
            ru=next((x for x in official_docs if x.source_key=="lg_ru"),None)
            if ru and lg_ru and ru.url and not ru.error and clock()<total_deadline:
                documents,error=lg_ru.find_documents(ru,base,deadline=total_deadline)
                jobs.save_documents(database,product_id,"lg_ru",documents)
                message=f"Русских инструкций найдено: {len(documents)}." if documents else error
            else:
                jobs.save_documents(database,product_id,"lg_ru",[]); message="Инструкции не проверены: официальная страница LG Россия недоступна."
            jobs.progress(database,job_id,6,message,level="info" if jobs.get_documents(database,product_id) else "warning",source_url=ru.url if ru else "")
        sources=jobs.get_source_pages(database,product_id); identity=jobs.identification_status(sources); counts=jobs.result_counts(database,product_id)
        confirmed=any(x["source_key"] in {"sulpak","mechta"} and x["match_level"]=="full_sku" for x in sources)
        summary=f" Реальных конфликтов: {counts['conflicts']}; только базовая модель LG: {counts['official_base_only']}; подтверждено поставщиком: {counts['supplier_confirmed']}."
        if sources and all(x["error"] for x in sources): jobs.finish(database,job_id,"error","Все источники недоступны. "+identity+summary)
        elif counts["conflicts"] or not confirmed: jobs.finish(database,job_id,"needs_review",identity+"."+summary)
        else: jobs.finish(database,job_id,"done",identity+"."+summary)
    except Exception:
        LOGGER.exception("Unexpected source comparison failure for job %s",job_id)
        jobs.finish(database,job_id,"error","Ошибка сравнения источников. Подробности смотрите в консоли worker.")
    return True

def main():
    parser=argparse.ArgumentParser(description="Worker сравнения источников LG")
    parser.add_argument("--data-dir",type=Path); parser.add_argument("--poll-interval",type=float,default=3.0); parser.add_argument("--once",action="store_true"); args=parser.parse_args()
    root=(args.data_dir or Path(os.environ.get("PRODUCT_CARDS_DATA_DIR") or PROJECT_DIR/"data")).resolve(); database=root/"batches.sqlite3"
    jobs.initialize(database); jobs.recover_interrupted(database); logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    try:
        while True:
            processed=run_once(database)
            if args.once: break
            if not processed: time.sleep(args.poll_interval)
    except KeyboardInterrupt: LOGGER.info("Worker остановлен.")
if __name__=="__main__": main()