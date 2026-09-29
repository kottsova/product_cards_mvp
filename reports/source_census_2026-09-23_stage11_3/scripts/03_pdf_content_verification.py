"""Stage 11.3 -- content verification of the fetched PDF: page count, model
and manufacturer-code mentions, per-page language detection, and whether the
document identifies itself as manufacturer-produced. Reads from the scratch
copy already assembled in phase 2 (no new network request)."""
import json
import pathlib
import re

import pypdf

OUT = pathlib.Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage11_3')
PDF_PATH = pathlib.Path(
    r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp'
    r'\1741bb85-29db-47a4-97a9-ed84155ebc47\scratchpad\stage11_3_pdf\hyperx_quadcast_2s_instrukcia.pdf'
)

reader = pypdf.PdfReader(str(PDF_PATH))
n_pages = len(reader.pages)
page_texts = []
for i, page in enumerate(reader.pages):
    try:
        text = page.extract_text() or ''
    except Exception as exc:
        text = f'<extract_failed: {exc}>'
    page_texts.append(text)

full_text = '\n'.join(page_texts)

model_hits = len(re.findall(r'quadcast\s*2\s*s', full_text, re.I))
sku_hits = len(re.findall(r'9A273AA', full_text, re.I))
hyperx_hits = len(re.findall(r'hyperx', full_text, re.I))
kingston_hits = len(re.findall(r'kingston', full_text, re.I))

# Detect language per page by simple script/keyword heuristics (Cyrillic vs Latin vs common words)
LANG_MARKERS = {
    'ru': [r'\bинструкция\b', r'\bмикрофон\b', r'\bруководств', r'[а-яА-ЯёЁ]{4,}'],
    'en': [r'\bmicrophone\b', r'\binstruction', r'\buser guide\b', r'\bwarranty\b'],
    'uk': [r'\bмікрофон\b', r'\bінструкці'],
    'kk': [r'\bмикрофон\b.*қазақ', r'құрылғы'],
}


def detect_languages(text):
    found = []
    for lang, patterns in LANG_MARKERS.items():
        if any(re.search(p, text, re.I) for p in patterns):
            found.append(lang)
    return found


page_languages = [detect_languages(t) for t in page_texts]
languages_present = sorted(set(lang for langs in page_languages for lang in langs))

# Manufacturer attribution: does the document identify HyperX (or its corporate parent) as author?
manufacturer_statement_context = []
for m in re.finditer(r'.{0,80}hyperx.{0,80}', full_text, re.I):
    manufacturer_statement_context.append(m.group(0).replace('\n', ' '))

result = {
    'pdf_url': 'https://drv.dns-shop.ru/drivers/Manuals/H/hyperx-quadcast-2-s_instrukcia_104913_30102025.pdf',
    'page_count': n_pages,
    'model_name_quadcast_2s_mentions_in_pdf_text': model_hits,
    'manufacturer_code_9A273AA_mentions_in_pdf_text': sku_hits,
    'hyperx_mentions_in_pdf_text': hyperx_hits,
    'kingston_mentions_in_pdf_text': kingston_hits,
    'languages_detected_per_page': page_languages,
    'languages_present_overall': languages_present,
    'sample_hyperx_context_strings': manufacturer_statement_context[:8],
    'full_text_first_2000_chars': full_text[:2000],
}
(OUT / 'pdf_content_verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print('pages:', n_pages)
print('model_hits:', model_hits, 'sku_hits:', sku_hits, 'hyperx_hits:', hyperx_hits)
print('languages_present_overall:', languages_present)
print('sample context:', manufacturer_statement_context[:3])
