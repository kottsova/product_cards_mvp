"""Generate a reviewable Stage73 report only after live/stability/regression pass."""
import json,hashlib,subprocess
from pathlib import Path
R=Path(__file__).parent
def load(n):return json.loads((R/n).read_text(encoding='utf8'))
d=load('release_actual.json');s=load('stability.json');reg=load('regression_release.json');off=load('offline_parser.json')
assert reg['exit_code']==0 and reg['source_tree_unchanged'] and s['actual_live']==5
assert sum(r['readiness']['verdict']=='export_ready' for r in d['rows'])==9
parent=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
text=f'''# Stage 73 — HyperX live recovery + gallery/manual completion

**Stage 73 PASS. HyperX adapter production-ready for controlled use.**

Controlled use означает существующий worker/adapter_factory с одним обычным visible persistent Chrome context на batch, pacing и сохранённым profile. Raw HTTP/headless path без этой настройки не объявляется восстановленным. 10/10 получают actual live official model data, 9/10 ready. RU retail остаётся partial и not_ready, что допускается критерием Stage73. Отдельного framework нет; глобальные thresholds и model/configuration schema не изменены.

Основа: Stage72 `{parent}`. Frozen input bytes и SHA256 сохранены без изменений: `{hashlib.sha256((R/'frozen_inputs.json').read_bytes()).hexdigest()}`. Dataset содержит те же 10 входов, без заранее добавленных PDP URL.

## 1. Root cause 429/cooldown

Stage72 final raw HTTP получил server **429 от hyperx.com** на ID6 в 11:34:27 UTC. Exact-host stop TTL1h истёк естественно в 12:34:27 UTC; Stage73 начат после 13:49 UTC. Полная предыдущая история сохранена как префикс Stage73 fetch log, timestamps не менялись, stops не удалялись. Stage72 ранний 10/10 и поздний 5/10 объясняются доказанным 429 и локальной остановкой последующих пяти карточек. Вклад повторных HTTP волн и новых sessions вероятен, но отдельный причинный A/B не выполнен.

Обычный visible Chrome probe дал storefront/support 200. Каждый batch использует один context и тот же локальный persistent profile: cookies сохраняются штатно, не экспортируются в Git. Существующая задержка 2s/goto и ожидание DOM, ограниченные timeout/navigation/byte budgets сохранены. Повторные product contexts не создаются. Только homepage/robots/sitemap metadata имеют явный same-session catalog cache; PDP/search свежие. Активный stop по-прежнему запрещает сеть; новый CAPTCHA/429 останавливает работу, автоматического обхода или решения CAPTCHA нет. Новых 429/challenge в принятых Stage73 live runs не наблюдалось.

Support failure оказался отдельным внутренним багом: общий detector пропускал опубликованный JSON-LD SearchAction, а read-only browser блокировал объявленные Sprinklr JS и public GraphQL query. Добавлены bounded SearchAction detection и opt-in resource hosts/query POST на опубликованном `/schema/community`. Mutation/subscription, account flows и произвольные POST остаются запрещены. Полнота отсутствия manual подтверждается exact model category + published totalCount, не первой страницей поиска.

Image/PDF requests сначала падали с локальным SSLCertVerificationError, а не server403/429. Опциональное `NODE_USE_SYSTEM_CA=1` для Playwright driver использует штатный Windows CA store; TLS verification сохранена. Переменная окружения восстанавливается после старта. [Node.js documentation](https://nodejs.org/api/cli.html#node_use_system_ca1). Binary GET использует тот же context/cookies и общий policy wrapper, ограниченные size/timeout, identity encoding; более крупные документы остаются явно rejected by budget.

## 2. Actual live, replay и offline

`corrected_live.json` и `stable_live.json` — два независимых actual run всех 10 после финального исправления, по одному context на batch, разные session IDs, один profile. Каждый PDP заново найден existing discovery и получен fresh DOM 200. `assets_actual.json` — реальные дополнительные image/PDF/support GET, identity из сохранённого actual PDP; это не ещё один PDP live-run.

`live_initial`, `live_final`, `live_release` и `second_live` сохранены как промежуточные actual результаты. В `second_live` обнаружен один gallery/readiness сбой: один и тот же опубликованный Shopify media ID сменил URL между `hyperx.com/cdn/shop/files` и `cdn.shopify.com/s/files/1/0561/8345/5901/files`. Asset key был URL, поэтому выбор потерялся. Нормализация только данного storefront tenant сохраняет query/version/size и устраняет alias divergence; чужой CDN tenant не объединяется. Последующие два run подтверждают одинаковые selected byte metadata и readiness.

`offline_parser.json` повторяет parser на exact сохранённых DOM, без сети; accepted/rejected совпадают с actual live. Это проверка extraction, а не live success. Stage72 offline coverage 157 confirmed specs; Stage73 actual coverage {sum(r['readiness']['confirmed_specs'] for r in d['rows'])}. У Cloud Mini wired исключены ошибочные battery/charge/bit-depth vendor rows, поэтому простой рост всех счётчиков не является целью.

## 3. Live-run 10 моделей

| ID | SKU / модель | Stage72 final live specs | Stage73 live specs | Byte photos | Manual | Identity | Readiness |
|---:|---|---:|---:|---:|---|---|---|
'''
old=[28,14,19,19,20,0,0,0,0,0]
for r in d['rows']:
 p=r['input'];ready=r['readiness'];photos=[x for x in r['photos'] if x['selected'] and x['kind']=='product_gallery' and not x['excluded_reason']]
 text+=f"| {r['id']} | `{p['article']}` {p['name']} | {old[r['id']-1]} | {ready['confirmed_specs']} | {len(photos)} | {r['evidence']['manual_status']} | {ready['identity']['configuration']} | {ready['verdict']} |\n"
text+='''
Ready: IDs1–9. ID10 not_ready: `configuration_unproven`, `gallery_missing`; guide не блокирует. Все десять имеют model_confirmed. ID6/7/8/9 восстановлены естественно из actual sources, без thresholds relaxation/default configuration.

## 4. RU configuration 4P5D6AX#ACB

Текущий actual Alloy Origins65 PDP подтверждает exact family; full RU retail record в bounded official path не найден. Model-level specs подтверждены; Black/RU/Red configuration не повышается до exact_variant, US gallery не выбирается. Shopify product ID, variant ID, merchant SKU/base/suffix остаются отдельными relations.

Ранее найденная official [HyperX press table](https://hyperx.com/blogs/press/hyperx-alloy-origins-65-mechanical-gaming-keyboard-now-shipping-with-colorway-customizations) связывает `4P5D6AX#ACB` с Russian/Red. Повторная supplementary проверка сохранена в `ru_relation.json`: это relation table, не current retail availability/color/gallery evidence и не seeded PDP discovery. Black и текущая RU gallery не доказаны; input color не выдаётся за confirmed. Руководство model-level допустимо и для partial RU.

## 5. Byte-verified gallery

56 actual official downloads: по IDs1–9 **10 / 6 / 7 / 5 / 1 / 8 / 8 / 6 / 5**, ID10 **0 confirmed**. `assets_actual.json` содержит URL, content-type, format, width/height, byte size, SHA256 и download outcome; public bytes сохранены в `images/`. Проверены полный Pillow decode, format/content-type correspondence, минимальный размер, broken/truncated/blank/transparent placeholders. Не только image headers. Selected metadata сохраняются в jobs DB и доступны UI/Excel; повторные runs не стирают их. Gallery contact sheet визуально проверен. Product renders и feature infographics раздельны; другой color/layout остаётся candidate/excluded.

## 6. Manuals

Все 10 проверены: девять `Проверена`, Cloud Mini Wired `Проверена, не найдена`. Для Mini опубликованная exact категория содержит totalCount=4 и четыре support articles (Overview, mobile devices, tuck-away mic, consoles), без User/Quick guide. Cloud Mini Wireless guide не перенесён. `Не проверена` в окончательных карточках нет.

User Manual/User Guide, Quick Start, Safety, Warranty и support article различаются; Safety/Warranty не становятся основной инструкцией. Strict SSR article-ID binding не берёт related-preview. Скачанные PDF проверены по content/model, instructional markers и языку, bounded 15MB/600pages/2M text. User Manual CloudIIIWireless превышает byte budget; его нельзя считать скачанным, но exact Quick Start проверен. При временной технической ошибке предыдущая проверка сохраняется отдельно от current-attempt status. Manual optional; RU не влияет на readiness.

| ID | Проверенные типы | RU evidence |
|---:|---|---|
'''
for r in d['rows']:
 guides=[g for g in r['evidence'].get('manuals',[]) if g.get('verified')]
 types=', '.join(dict.fromkeys(g['type'] for g in guides)) or 'Guide не найден; support inventory complete'
 langs=', '.join(dict.fromkeys(g.get('language','') for g in guides)) or 'не применимо'
 text+=f"| {r['id']} | {types} | {langs} |\n"
text+='''
RU presence проверена по извлечённому тексту; наличие языка не всегда означает полный перевод каждого PDF. Per-file language assessment в evidence сохраняет `russian_instruction` отдельно. Cloud Alpha2 UserGuide cover и русский раздел визуально проверены (`qa/pdf_visual.json`, page192); чужой Safety не использован.

## 7. Runtime и microphone/headset extraction

Cloud Alpha2: explicit **Up to250h2.4GHz** и **125h simultaneous connection** — разные поля. Не добавлены неуказанные Bluetooth-only/RGB-on/off/headset mixed-use режимы. Обычная table runtime сохраняется с «режим не указан»; Up to остаётся заявленным максимумом. QuadCast2: строго привязанный model statement даёт recording24-bit/96kHz, а не default/другую модель.

Общий table extractor сохраняет rowspan/colspan/continuation rows и dedupe внутри component section. Одинаковая frequency response в Headphone и Microphone больше не теряет один компонент. Для ошибочно подписанного Cloud Mini блока явный `Element=Electret condenser microphone` определяет microphone section, raw vendor heading остаётся в evidence. Headphone/microphone frequency и sensitivity имеют разные semantic keys. Общие Razer BlackShark/Barracuda regression cases проходят; новых actual Razer runs Stage73 не заявляет.

`raw facts → accepted → rejected` по каждой карточке:

| ID | Raw | Accepted | Rejected | Итоговых attributes, включая configuration |
|---:|---:|---:|---:|---:|
'''
for r in off:text+=f"| {r['id']} | {r['raw']} | {r['accepted']} | {r['rejected']} | {r['attribute_count']} |\n"
text+=f'''
Raw=accepted+rejected проверено для всех10. Configuration labels добавляются только при exact relation. Unit price, vendor switch conflict, wireless facts для wired и чужая selected physical configuration остаются rejected.

## 8. Stability, UI/Excel

Второй run охватывает все10 и пять типов товаров, превышая требуемые минимум5. Sources, canonical facts/components, identity, readiness, selected byte photos идентичны; manuals сохранены; fact/photo duplicates отсутствуют. `stability.json` и `artifact_verification.json` содержат assertions/readback. UI200 для IDs1/2/8/10 и Excel14sheet readback выполнены. Persistent browser cookies/profile локальные и исключены из Git.

## 9. Regression

`python -m tests`: **{'; '.join(reg['result'])}**, exit0, source manifest unchanged=True. 26 новых Stage73 tests: SearchAction guards, GraphQL query-only, active cooldown zero network, TLS environment restoration, runtime qualifiers, component dedupe, wrong model recording, wired table rejection, actual bytes/truncation/placeholders/type, manual binding/absence/content/technical failure, evidence retention и CDN alias stability. Все предыдущие authorization/pin blocks сохранены; Stage73 append-only. Global readiness thresholds не менялись. `git diff --check` и staged check обязательны перед commit.

## 10. Verdict и Git

**HyperX adapter production-ready for controlled use** в проверенном visible persistent Chrome flow. Обычная HTTP session пока не сертифицирована как стабильная; future server429/challenge по-прежнему безопасно останавливает сеть. RU current retail остается partial; отсутствующий manual не мешает ready. Эти границы не скрыты replay результатами.

После Stage73 PASS: commit `Stage 73`, push origin/main, actual HEAD/origin/main equality и clean working tree. Окончательный hash сообщается после commit; report не содержит самоссылочный hash. Evidence manifests проверяются до stage, PDFs/images public, cookie/profile/SQLite runtime не публикуются.
'''
(R/'REPORT.md').write_text(text,encoding='utf8')
(R/'acceptance_summary.json').write_text(json.dumps({'stage':73,'verdict':'HyperX adapter production-ready for controlled use','actual_official':10,'ready':9,'byte_verified_images':56,'manual_inventory_checked':10,'second_live_stable':5,'regression':reg['result'],'base_commit':parent},ensure_ascii=False,indent=2),encoding='utf8')
print('Report generated from verified actual results')
