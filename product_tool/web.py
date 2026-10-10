"""Local web UI for uploading, reviewing, and confirming Excel batches."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
import logging
import os
from pathlib import Path
import requests
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openpyxl import load_workbook

from . import apple_pipeline, jbl_pipeline, lenovo_pipeline, lenovo_presentation, attribute_projection, bosch_presentation, bosch_readiness, card_evidence, card_presentation, exporter, jobs, lg_batch, manual_status, photo_metadata, product_description, samsung_readiness, storage
from .adapters.lg import lg_base_model
from .adapters.policy_fetch import migrate_legacy_stop_log
from .lg_identity import document_tied_to_article, photo_tied_to_article
from .display import display_access_error
from .importer import MAX_COLUMNS, MAX_FILE_BYTES, MAX_ROWS, ImportPreview, preview_xlsx


LOGGER = logging.getLogger(__name__)


def _display_access_stop(message: str) -> str:
    return display_access_error(message)


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
COLUMN_FIELDS = ("category", "brand", "name", "search_code", "fallback_code")
COLUMN_LABELS = {
    "category": "Категория",
    "brand": "Бренд",
    "name": "Название",
    "search_code": "Основной артикул",
    "fallback_code": "Запасная модель",
}


def _sheet_names(path: Path) -> list[str]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return workbook.sheetnames
    finally:
        workbook.close()


def _parse_mapping(form: Any, sheets: list[str]) -> tuple[str, dict[str, int | None]]:
    sheet_name = str(form.get("sheet_name", "")).strip()
    if sheet_name not in sheets:
        raise ValueError("Выберите лист из загруженного Excel.")
    mapping: dict[str, int | None] = {}
    for field in COLUMN_FIELDS:
        raw = str(form.get(field, "")).strip()
        if not raw:
            mapping[field] = None
            continue
        try:
            number = int(raw)
        except ValueError as exc:
            raise ValueError(f"Поле «{COLUMN_LABELS[field]}»: укажите номер колонки.") from exc
        if not 1 <= number <= MAX_COLUMNS:
            raise ValueError(
                f"Поле «{COLUMN_LABELS[field]}»: номер колонки должен быть от 1 до {MAX_COLUMNS}."
            )
        mapping[field] = number
    raw_header = str(form.get("header_row", "")).strip()
    try:
        header_row = int(raw_header)
    except ValueError as exc:
        raise ValueError("Укажите номер строки заголовков; 0 означает отсутствие заголовков.") from exc
    if not 0 <= header_row <= MAX_ROWS:
        raise ValueError(f"Строка заголовков должна быть от 0 до {MAX_ROWS}.")
    mapping["header_row"] = header_row
    if not any(mapping[field] for field in ("name", "brand", "search_code")):
        raise ValueError("Укажите хотя бы колонку названия, бренда или основного артикула.")
    return sheet_name, mapping


def _preview(path: Path, draft: dict[str, Any]) -> ImportPreview:
    mapping = draft["mapping"]
    if mapping is None:
        return preview_xlsx(path, sheet_name=draft["sheet_name"])
    return preview_xlsx(
        path,
        sheet_name=draft["sheet_name"],
        column_overrides={field: mapping[field] for field in COLUMN_FIELDS},
        header_row=mapping["header_row"],
    )


def create_app(data_dir: str | Path | None = None, *, start_worker: bool | None = None) -> FastAPI:
    """Create an app with its own data directory, including for isolated tests."""
    root = Path(data_dir or os.environ.get("PRODUCT_CARDS_DATA_DIR") or PROJECT_DIR / "data")
    root = root.resolve()
    uploads = root / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    database = root / "batches.sqlite3"
    jobs.initialize(database)
    lg_batch.initialize(database)
    # Access stops are stored beside the SQLite database, in append-only fetch logs.
    # Annotate legacy timed responses before the background worker starts.
    for fetch_log in root.glob("*_fetch_log.json"):
        migrate_legacy_stop_log(fetch_log)
    templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))

    # The ordinary one-command launch processes queued jobs as well as serving pages.
    # Isolated test apps keep their explicit data directory and opt in separately.
    if start_worker is None:
        start_worker = data_dir is None
    stop_worker = Event()

    def process_queue() -> None:
        from . import worker

        while not stop_worker.is_set():
            try:
                with worker.single_worker(root):
                    jobs.recover_interrupted(database)
                    while not stop_worker.is_set():
                        try:
                            processed = worker.run_once(database)
                        except Exception:
                            LOGGER.exception("Background job failed; worker will retry")
                            stop_worker.wait(3)
                        else:
                            if not processed:
                                stop_worker.wait(1)
            except RuntimeError:
                # A separately launched worker already owns this data directory.
                stop_worker.wait(3)
            except Exception:
                LOGGER.exception("Could not start background processing")
                stop_worker.wait(3)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        thread = None
        if start_worker:
            thread = Thread(target=process_queue, name="product-card-worker", daemon=True)
            thread.start()
        try:
            yield
        finally:
            stop_worker.set()
            if thread is not None:
                thread.join(timeout=5)

    app = FastAPI(title="Product Cards MVP", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    def render(request: Request, name: str, status_code: int = 200, **context: Any) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request, name=name, context=context, status_code=status_code
        )

    def error_page(request: Request, message: str, status_code: int = 400) -> HTMLResponse:
        return render(request, "error.html", status_code, message=message)

    def preview_page(
        request: Request,
        draft_id: str,
        *,
        message: str = "",
        status_code: int = 200,
        mapping_values: dict[str, Any] | None = None,
        edits: dict[int, dict[str, str]] | None = None,
    ) -> HTMLResponse:
        draft = storage.get_draft(database, draft_id)
        if draft is None:
            return error_page(request, "Черновик не найден или партия уже подтверждена.", 404)
        path = uploads / f"{draft_id}.xlsx"
        try:
            sheets = _sheet_names(path)
        except Exception:
            LOGGER.exception("Could not reopen uploaded workbook")
            return error_page(request, "Не удалось открыть сохранённый Excel. Загрузите файл снова.", 400)

        preview: ImportPreview | None = None
        try:
            preview = _preview(path, draft)
        except ValueError as exc:
            if not message:
                message = str(exc)
        except Exception:
            LOGGER.exception("Could not preview workbook")
            if not message:
                message = "Не удалось прочитать товары. Проверьте файл и номера колонок."

        mapping = mapping_values or draft["mapping"] or (
            asdict(preview.mapping) if preview else {**dict.fromkeys(COLUMN_FIELDS), "header_row": 0}
        )
        selected_sheet = (
            str(mapping_values.get("sheet_name")) if mapping_values and mapping_values.get("sheet_name")
            else draft["sheet_name"] or (preview.sheet_name if preview else sheets[0])
        )
        return render(
            request,
            "preview.html",
            status_code,
            draft=draft,
            sheets=sheets,
            selected_sheet=selected_sheet,
            mapping=mapping,
            column_fields=COLUMN_FIELDS,
            column_labels=COLUMN_LABELS,
            preview=preview,
            edits=edits or {},
            message=message,
        )

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        return render(request, "index.html", batches=storage.list_batches(database), message="")

    @app.post("/upload", response_class=HTMLResponse)
    async def upload(request: Request, file: UploadFile | None = File(default=None)) -> HTMLResponse:
        batches = storage.list_batches(database)
        filename = (file.filename if file else "") or ""
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if not filename:
            return render(
                request, "index.html", 400, batches=batches, message="Выберите файл .xlsx."
            )
        if Path(filename).suffix.lower() != ".xlsx":
            return render(
                request, "index.html", 400, batches=batches,
                message="Поддерживаются только файлы .xlsx.",
            )
        assert file is not None
        try:
            contents = await file.read(MAX_FILE_BYTES + 1)
        finally:
            await file.close()
        if not contents:
            return render(request, "index.html", 400, batches=batches, message="Файл пустой.")
        if len(contents) > MAX_FILE_BYTES:
            return render(
                request, "index.html", 400, batches=batches,
                message="Файл больше 10 МБ. Выберите книгу меньшего размера.",
            )

        draft_id = uuid4().hex
        path = uploads / f"{draft_id}.xlsx"
        path.write_bytes(contents)
        try:
            if not _sheet_names(path):
                raise ValueError("В книге нет листов")
        except Exception:
            path.unlink(missing_ok=True)
            LOGGER.warning("Rejected unreadable xlsx upload")
            return render(
                request, "index.html", 400, batches=batches,
                message="Не удалось открыть Excel. Проверьте, что это исправный файл .xlsx.",
            )
        try:
            storage.create_draft(database, draft_id, filename)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return RedirectResponse(f"/drafts/{draft_id}", status_code=303)

    @app.get("/drafts/{draft_id}", response_class=HTMLResponse)
    def show_preview(request: Request, draft_id: str) -> HTMLResponse:
        return preview_page(request, draft_id)

    @app.post("/drafts/{draft_id}/mapping", response_class=HTMLResponse)
    async def change_mapping(request: Request, draft_id: str) -> HTMLResponse:
        draft = storage.get_draft(database, draft_id)
        if draft is None:
            return error_page(request, "Черновик не найден или партия уже подтверждена.", 404)
        form = await request.form()
        values = {field: str(form.get(field, "")) for field in (*COLUMN_FIELDS, "header_row", "sheet_name")}
        try:
            sheet_name, mapping = _parse_mapping(form, _sheet_names(uploads / f"{draft_id}.xlsx"))
        except ValueError as exc:
            return preview_page(request, draft_id, message=str(exc), status_code=400, mapping_values=values)
        storage.update_draft_mapping(database, draft_id, sheet_name, mapping)
        return RedirectResponse(f"/drafts/{draft_id}", status_code=303)

    @app.post("/drafts/{draft_id}/confirm", response_class=HTMLResponse)
    async def confirm(request: Request, draft_id: str) -> HTMLResponse:
        draft = storage.get_draft(database, draft_id)
        if draft is None:
            return error_page(request, "Черновик не найден или партия уже подтверждена.", 404)
        try:
            preview = _preview(uploads / f"{draft_id}.xlsx", draft)
        except ValueError as exc:
            return preview_page(request, draft_id, message=str(exc), status_code=400)
        except Exception:
            LOGGER.exception("Could not confirm workbook")
            return preview_page(
                request, draft_id, message="Не удалось прочитать Excel. Проверьте файл и колонки.",
                status_code=400,
            )

        form = await request.form(max_fields=MAX_ROWS * 4 + 20)
        products: list[dict[str, Any]] = []
        edits: dict[int, dict[str, str]] = {}
        errors: list[str] = []
        for item in preview.products:
            row = item.row_number
            values = {
                field: str(form.get(f"{field}_{row}", "")).strip()
                for field in ("brand", "search_code", "alternate_code", "category")
            }
            edits[row] = values
            if not values["brand"] or not values["search_code"]:
                errors.append(f"Строка {row}: заполните бренд и основной артикул.")
            if any(len(value) > 500 for value in values.values()):
                errors.append(f"Строка {row}: значение длиннее 500 символов.")
            products.append({
                "row_number": row,
                "name": item.name,
                **values,
                "needs_confirmation": item.needs_confirmation,
                "issues": item.issues,
                "original_values": item.original_values,
            })
        if errors:
            message = " ".join(errors[:5])
            if len(errors) > 5:
                message += f" И ещё ошибок: {len(errors) - 5}."
            return preview_page(
                request, draft_id, message=message, status_code=400, edits=edits
            )
        storage.confirm_draft(database, draft_id, preview, products)
        return RedirectResponse(f"/batches/{draft_id}", status_code=303)

    @app.get("/batches/{batch_id}", response_class=HTMLResponse)
    def show_batch(request: Request, batch_id: str) -> HTMLResponse:
        batch = storage.get_batch(database, batch_id)
        if batch is None:
            return error_page(request, "Партия не найдена.", 404)
        groups: dict[str, list[dict[str, Any]]] = {}
        for product in batch["products"]:
            category = product["category"] or "Категория не определена"
            groups.setdefault(category, []).append(product)
        selected = lg_batch.selected_ids(database, batch_id)
        if not selected:
            selected = lg_batch.default_ids(batch["products"])
        lg_rows, lg_counts = lg_batch.batch_rows(database, batch["products"], selected)
        return render(request, "batch.html", batch=batch, groups=groups,
                      lg_rows=lg_rows, lg_selected=selected, lg_counts=lg_counts,
                      lg_products=[p for p in batch["products"] if lg_batch.is_lg(p)],
                      stages=jobs.STAGE_NAMES, batch_message=request.query_params.get("message", ""))

    @app.post("/batches/{batch_id}/lg-search", response_class=HTMLResponse)
    async def start_lg_batch(request: Request, batch_id: str) -> HTMLResponse:
        batch = storage.get_batch(database, batch_id)
        if batch is None:
            return error_page(request, "Партия не найдена.", 404)
        form = await request.form()
        try:
            product_ids = [int(value) for value in form.getlist("product_ids")]
            stages = [int(value) for value in form.getlist("stages")]
            result = lg_batch.queue_selected(database, batch_id, product_ids, stages)
        except (TypeError, ValueError) as exc:
            return error_page(request, str(exc), 400)
        from urllib.parse import quote
        message = (f"LG: выбрано {result['selected']}; новых заданий {result['new_jobs']}; "
                   f"уже в очереди или выполняются {result['already_active']}.")
        return RedirectResponse(f"/batches/{batch_id}?message={quote(message)}", status_code=303)


    def product_page(
        request: Request, product_id: int, *, message: str = "", status_code: int = 200
    ) -> HTMLResponse:
        product = jobs.get_product(database, product_id)
        if product is None:
            return error_page(request, "Товар не найден.", 404)
        history = jobs.list_jobs(database, product_id)
        latest = history[0] if history else None
        sources = jobs.get_source_pages(database, product_id)
        documents = (manual_status.effective_documents(database, product_id, product["search_code"])
                     if lg_batch.is_lg(product) else jobs.get_documents(database, product_id))
        from . import playstation_pipeline
        from . import xbox_pipeline
        from .xbox_identity import BRANDS as XBOX_BRANDS
        xbox_evidence = card_evidence.load(database,product_id,'xbox') if product['brand'].strip().casefold() in XBOX_BRANDS else None
        from . import razer_pipeline
        razer_evidence = card_evidence.load(database,product_id,'razer') if product['brand'].strip().casefold() == 'razer' else None
        hyperx_evidence = card_evidence.load(database,product_id,'hyperx') if product['brand'].strip().casefold() == 'hyperx' else None
        from .playstation_identity import BRANDS as PLAYSTATION_BRANDS
        playstation_evidence = card_evidence.load(database,product_id,"playstation") if product["brand"].strip().casefold() in PLAYSTATION_BRANDS else None
        apple_evidence = card_evidence.load(database, product_id, "apple") if product["brand"].strip().upper() == "APPLE" else None
        jbl_evidence = card_evidence.load(database, product_id, "jbl") if product["brand"].strip().upper() == "JBL" else None
        lenovo_evidence = card_evidence.load(database, product_id, "lenovo") if product["brand"].strip().upper() == "LENOVO" else None
        photos = jobs.get_photo_candidates(database, product_id)
        if lg_batch.is_lg(product):
            for document in documents:
                document["identity_confirmed"] = document.get("identity_confirmed", False)
            for photo in photos:
                photo["identity_confirmed"] = photo_tied_to_article(photo, sources)
                photo["can_inspect"] = photo["source_key"] in photo_metadata.ALLOWED_BY_SOURCE
                if playstation_evidence is not None:
                    photo['identity_confirmed']=playstation_pipeline.photo_verified(photo,playstation_evidence)
                photo["size_label"] = photo_metadata.format_file_size(photo.get("verified_bytes"))
        else:
            brand = product["brand"].strip().upper()
            bosch_evidence = card_evidence.load(database, product_id, "bosch_home") if brand == "BOSCH" else None
            samsung_evidence = card_evidence.load(database, product_id, "samsung_documents") if brand == "SAMSUNG" else None
            for document in documents:
                document["identity_confirmed"] = (bosch_presentation.document_verified(document, bosch_evidence, sources)
                    if bosch_evidence is not None else samsung_readiness.document_verified(document, samsung_evidence)
                    if brand == "SAMSUNG" else lenovo_pipeline.document_verified(document, lenovo_evidence) if brand == "LENOVO" else jbl_pipeline.document_verified(document, jbl_evidence) if brand == "JBL" else True)
            for photo in photos:
                photo["identity_confirmed"] = (samsung_readiness.photo_verified(photo, sources, product["search_code"])
                    if brand == "SAMSUNG" else lenovo_pipeline.photo_verified(photo, lenovo_evidence) if brand == "LENOVO" else jbl_pipeline.photo_verified(photo, jbl_evidence) if brand == "JBL" else True)
                photo["can_inspect"] = photo["source_key"] in photo_metadata.ALLOWED_BY_SOURCE
                photo["size_label"] = photo_metadata.format_file_size(photo.get("verified_bytes"))
                if brand == "LENOVO" and photo["identity_confirmed"]:
                    photo["identity_note"] = "Цвет рендера подтверждён. Раскладка клавиатуры на изображении иллюстративная."
        retained_manual_sources = {
            d["source_key"] for d in documents
            if d["identity_confirmed"] and d["language"] == "Русский"
        }
        if xbox_evidence is not None:
            for photo in photos:photo['identity_confirmed']=xbox_pipeline.photo_verified(photo,xbox_evidence)
        if razer_evidence is not None:
            for photo in photos:photo['identity_confirmed']=razer_pipeline.photo_verified(photo,razer_evidence)
            for document in documents:document['identity_confirmed']=razer_pipeline.document_verified(document,razer_evidence)
        events = []
        for event in jobs.list_events(database, latest["id"]) if latest else []:
            message = _display_access_stop(event["message"])
            if ("LG KZ support manual: no_verified_russian_instruction" in message
                    and "lg_kz_support" in retained_manual_sources):
                message = ("Повторная попытка проверки PDF не завершилась; "
                           "ранее проверенная русская инструкция сохранена.")
            events.append({**event, "message": message})
        lg_card = lg_batch.card_summary(database, product_id, latest) if lg_batch.is_lg(product) else None
        if lenovo_evidence is not None and latest and message == latest.get("message"):
            message = "Проверка Lenovo завершена; готовность и пробелы показаны ниже."
        comparison = attribute_projection.final_attribute_rows(database, product_id)
        card_attributes = card_presentation.present_card_rows(
            comparison, jobs.get_facts(database, product_id), sources, product["category"]
        )
        if lg_card:
            conflict_values = {item["key"]: item["values"] for item in lg_card.get("conflicts", [])}
            for row in comparison:
                row["conflict_values"] = conflict_values.get(row["normalized_name"], [])
        return render(
            request, "product.html", status_code,
            product=product,
            result=jobs.get_result(database, product_id),
            sources=[{**source, "error": _display_access_stop(source["error"]),
                       "description": product_description.product_description(source["description"])
                       if lg_batch.is_lg(product) else source["description"]} for source in sources],
            bosch_card=bosch_readiness.card_readiness(database, product_id) if any(src["source_key"] == "bosch_home" for src in sources) else None,
            playstation_evidence=playstation_evidence,
            playstation_card=playstation_pipeline.card_readiness(database,product_id) if playstation_evidence is not None else None,
            playstation_gaps=playstation_pipeline.GAPS,
            xbox_evidence=xbox_evidence,
            razer_evidence=razer_evidence,
            hyperx_evidence=hyperx_evidence,
            hyperx_card=__import__('product_tool.hyperx_audit',fromlist=['card_readiness']).card_readiness(database,product_id) if hyperx_evidence is not None else None,
            hyperx_gaps=__import__('product_tool.hyperx_presentation',fromlist=['GAPS']).GAPS,
            razer_card=razer_pipeline.card_readiness(database,product_id) if razer_evidence is not None else None,
            razer_gaps=razer_pipeline.GAPS,
            razer_reasons=__import__('product_tool.razer_presentation',fromlist=['REASONS']).REASONS,
            razer_config_labels=__import__('product_tool.razer_presentation',fromlist=['CONFIG_LABELS']).CONFIG_LABELS,
            xbox_card=xbox_pipeline.card_readiness(database,product_id) if xbox_evidence is not None else None,
            xbox_gaps=xbox_pipeline.GAPS,
            xbox_scopes=xbox_pipeline.SCOPES,
            apple_evidence=apple_evidence,
            apple_card=apple_pipeline.card_readiness(database, product_id) if apple_evidence is not None else None,
            jbl_evidence=jbl_evidence,
            jbl_card=jbl_pipeline.card_readiness(database, product_id) if jbl_evidence is not None else None,
            jbl_gaps=jbl_pipeline.GAPS,
            jbl_verdicts=jbl_pipeline.VERDICTS,
            lenovo_card=lenovo_pipeline.card_readiness(database, product_id) if lenovo_evidence is not None else None,
            lenovo_evidence=lenovo_evidence,
            lenovo_verdicts=lenovo_presentation.VERDICTS,
            lenovo_gaps=lenovo_presentation.GAPS,
            lenovo_scopes=lenovo_presentation.SCOPES,
            lg_card=lg_card,
            comparison=comparison,
            card_attributes=card_attributes,
            counts=jobs.result_counts(database, product_id),
            documents=documents,
            manual_status=hyperx_evidence.get('manual_status','Не проверена') if hyperx_evidence is not None else razer_evidence.get('manual_status','Не проверена') if razer_evidence is not None else xbox_evidence.get('manual_status','Не проверена') if xbox_evidence is not None else playstation_evidence.get("manual_status","Не проверена") if playstation_evidence is not None else apple_evidence.get("manual_status", "Не проверена") if apple_evidence is not None else lenovo_evidence.get("manual_status", "Не проверена") if lenovo_evidence is not None else jbl_evidence.get("manual_status", "Не проверена") if jbl_evidence is not None else manual_status.russian_status(database, product_id, product["search_code"], lg=lg_batch.is_lg(product)),
            manual_reason=manual_status.unchecked_reason(database, product_id, product["search_code"]) if lg_batch.is_lg(product) else "",
            manual_search=manual_status.completed_search(database, product_id) if lg_batch.is_lg(product) else None,
            photos=photos,
            identification_status=jobs.identification_status(sources),
            base_model=lg_base_model(product["search_code"]) if product["brand"].strip().upper() == "LG" else "",
            latest=latest,
            events=events,
            stages=jobs.STAGE_NAMES,
            message=message,
            active=bool(latest and latest["status"] in jobs.ACTIVE),
        )

    @app.get("/products/{product_id}", response_class=HTMLResponse)
    def show_product(request: Request, product_id: int) -> HTMLResponse:
        return product_page(request, product_id)

    @app.post("/products/{product_id}/search", response_class=HTMLResponse)
    async def start_product_search(request: Request, product_id: int) -> HTMLResponse:
        if jobs.get_product(database, product_id) is None:
            return error_page(request, "Товар не найден.", 404)
        form = await request.form()
        try:
            selected = [int(value) for value in form.getlist("stages")]
        except (TypeError, ValueError):
            return product_page(
                request, product_id, message="Выберите этапы 1–4.", status_code=400
            )
        try:
            jobs.enqueue(database, product_id, selected)
        except ValueError as exc:
            return product_page(request, product_id, message=str(exc), status_code=400)
        return RedirectResponse(f"/products/{product_id}", status_code=303)

    @app.post("/products/{product_id}/attributes/{attribute_ref}/decision", response_class=HTMLResponse)
    async def save_attribute_decision(
        request: Request, product_id: int, attribute_ref: str
    ) -> HTMLResponse:
        if jobs.get_product(database, product_id) is None:
            return error_page(request, "Товар не найден.", 404)
        form = await request.form()
        value = str(form.get("value", "")).strip()
        unit = str(form.get("unit", "")).strip()
        if not value:
            return product_page(
                request, product_id, message="Укажите итоговое значение.", status_code=400
            )
        resolved = next((item for item in jobs.get_resolved(database, product_id) if str(item["id"]) == attribute_ref or item["normalized_name"] == attribute_ref), None)
        if resolved is None:
            return product_page(request, product_id, message="Характеристика не найдена.", status_code=404)
        jobs.save_manual_decision(
            database, product_id, resolved["normalized_name"], value, unit,
            "manual_user_override",
        )
        return RedirectResponse(f"/products/{product_id}#comparison", status_code=303)

    @app.get("/batches/{batch_id}/export.xlsx")
    def export_batch(batch_id: str) -> Response:
        batch = storage.get_batch(database, batch_id)
        if batch is None:
            return Response("Партия не найдена.", status_code=404, media_type="text/plain; charset=utf-8")
        content = exporter.export_batch(database, batch_id)
        return Response(
            content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="batch-{batch_id}.xlsx"'},
        )

    @app.post("/products/{product_id}/photos/{photo_id}/inspect", response_class=HTMLResponse)
    def inspect_photo(request: Request, product_id: int, photo_id: int) -> HTMLResponse:
        photo = jobs.get_photo_candidate(database, product_id, photo_id)
        if photo is None:
            return error_page(request, "Фото не найдено.", 404)
        try:
            measured = photo_metadata.inspect_saved_photo(
                photo["url"], photo["source_key"],
                root / photo_metadata.log_name(photo["source_key"]),
            )
        except (ValueError, OSError, requests.RequestException) as exc:
            return product_page(request, product_id,
                message=f"Параметры фото не определены: {exc}")
        jobs.save_photo_metadata(database, product_id, photo_id, photo["url"],
            width=int(measured["width"]), height=int(measured["height"]),
            size_bytes=int(measured["size_bytes"]), image_format=str(measured["format"]))
        return RedirectResponse(f"/products/{product_id}#photos", status_code=303)

    @app.post("/products/{product_id}/photos", response_class=HTMLResponse)
    async def save_photo_selection(request: Request, product_id: int) -> HTMLResponse:
        if jobs.get_product(database, product_id) is None:
            return error_page(request, "Товар не найден.", 404)
        form = await request.form()
        action = str(form.get("action", "exact"))
        if action == "official":
            jobs.set_photo_selection(database, product_id, [], mode="official")
        elif action == "none":
            jobs.set_photo_selection(database, product_id, [], mode="none")
        elif action.startswith("source:"):
            jobs.set_photo_selection(database, product_id, [], mode="source", source_key=action.split(":", 1)[1])
        else:
            jobs.set_photo_selection(database, product_id, [str(x) for x in form.getlist("asset_keys")])
        return RedirectResponse(f"/products/{product_id}#photos", status_code=303)
    return app
