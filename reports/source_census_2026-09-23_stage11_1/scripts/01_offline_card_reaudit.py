"""Stage 11.1 -- offline re-audit of Stage 11's card for 9A273AA. No network
requests. Stage 11's own files are read-only and unmodified; this writes a
NEW file in this stage's own directory.

Corrections made explicit here:
1. Stage 11 treated Product.sku and Product.offers.sku both matching the
   catalog's seller article as if they were two data points. They are not --
   both come from the same JSON-LD block on the same single fetch of the same
   single page. This is ONE data point, restated in two places within one
   document, not independent corroboration.
2. Stage 11 accepted 9 images as evidence solely because the SKU string
   appears in each filename. That is necessary but not sufficient: it does
   not by itself confirm the file is reachable at that exact URL from an
   official host, that the bytes are intact, or that the pixels actually show
   this product. Those three additional checks are performed in the next
   script (02_image_integrity_check.py) and referenced here.
3. The manual/document status is carried forward unchanged: a Quick Start
   Guide is listed as a box-content item on the official spec table; no
   online document or language has been confirmed.
"""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
STAGE11 = ROOT / 'reports/source_census_2026-09-23_stage11'
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_1'

stage11_card = json.loads((STAGE11 / 'card.json').read_text(encoding='utf-8'))
phase1 = json.loads((STAGE11 / 'phase1_robots_and_product_fetch.json').read_text(encoding='utf-8'))
product = phase1['json_ld_products_raw'][0]

idv = stage11_card['identity_verification_separate_step']

correction = {
    'stage11_claim_reexamined': {
        'quoted_field': 'sku_exact_match',
        'quoted_value': idv['sku_exact_match'],
        'quoted_conclusion_text': idv['conclusion'],
    },
    'correction': {
        'issue': (
            'Stage 11\'s conclusion described the match as confirmed "by exact code match" and '
            'listed both ".sku" and ".offers.sku" as if checking two fields strengthened the '
            'claim. Both values were read from ONE JSON-LD <script> block on ONE fetch of ONE '
            'URL in ONE request (phase1_robots_and_product_fetch.json, seq 2). offers.sku is '
            'schema.org\'s own required near-duplicate of the parent Product.sku on the same '
            'Offer sub-object -- it is not a second, independently-sourced signal (e.g. a '
            'second page, a second host, or a structured-data type unrelated to Offers).'
        ),
        'corrected_statement': (
            'The catalog seller article 9A273AA matches ONE extracted value (the page\'s '
            'Product.sku, which schema.org also mirrors onto .offers.sku by convention) from '
            'ONE official page fetch. This is still a genuine, strong, exact-code-level match -- '
            'far stronger than the descriptive-consistency-only matches used for other brands '
            'in this project -- but it is one source, one document, one request, not two '
            'independent confirmations. Stage 11\'s underlying fact (the codes match) is '
            'unchanged; only the "how many independent signals" framing is corrected.'
        ),
        'does_this_change_the_identity_verdict': False,
        'why_not': (
            'A single official first-party source stating an exact manufacturer/seller code is '
            'still the strongest single-page identity signal used anywhere in this project. The '
            'correction narrows the *epistemic weight* claimed (one source, not two) without '
            'weakening the underlying fact.'
        ),
    },
    'manual_status_carried_forward_unchanged': {
        'quick_start_guide_listed_in_box_contents': True,
        'source': "official spec table, \"What's In The Box\" row, read in Stage 11",
        'online_document_confirmed': False,
        'language_confirmed': False,
        'explicit_statement': (
            'Unchanged from Stage 11: a Quick Start Guide is confirmed, by the official page\'s '
            'own text, to physically ship with this product. No online document or its language '
            'has been confirmed. This is not re-examined further this stage -- the task scope is '
            'the image-evidence re-audit and the adapter-repeatability question, not a renewed '
            'document search.'
        ),
    },
    'image_evidence_gap_identified': (
        'Stage 11 accepted 9 images as evidence using only a filename-substring check (the SKU '
        '"9a273aa" appears in each CDN URL). It never fetched the bytes, checked integrity, or '
        'viewed the actual pixels. That is addressed in 02_image_integrity_check.py, this stage.'
    ),
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'offline_card_reaudit.json').write_text(json.dumps(correction, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(correction['correction'], indent=2, ensure_ascii=False))
