import json
from pathlib import Path

STAGE84 = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_4')
OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_5')

evidence84 = json.loads((STAGE84 / 'evidence.json').read_text(encoding='utf-8'))
card84 = json.loads((STAGE84 / 'card_summary.json').read_text(encoding='utf-8'))

review = {
    "schema_version": "stage8_5_offline_evidence_review.v1",
    "source": "reports/source_census_2026-09-22_stage8_4/evidence.json + card_summary.json (read-only)",
    "independent_evidence_strands": {
        "catalog_article": {
            "value": "MS23K3614AK/BW",
            "source": "data/catalog_2026-09-21_filtered.xlsx, seller_article column (row: 'Микроволновая печь MS23K3614AK/BW', alt name includes '23 л')",
            "independence_note": "Comes from the seller's own catalog file, entirely independent of Samsung's website.",
        },
        "official_page_sku": {
            "value": "MS23K3614AK/BW",
            "source": "JSON-LD Product.sku on https://www.samsung.com/kz_ru/microwave-ovens/solo/ms23k3614akbw/",
            "independence_note": "Comes from Samsung's own structured product data, independent of the catalog file and independent of any PDF link.",
        },
        "official_page_color": {
            "value": "Черный (Black)",
            "source": "HTML <title> tag on the same product page (not the URL slug)",
            "independence_note": "A separate on-page element from the JSON-LD block; confirms a variant-defining attribute the JSON-LD itself did not carry.",
        },
        "pdf_link_modelname_parameter": {
            "value": "MS23K3614AK",
            "source": "Query parameter ModelName= in the manual download URL found on the product page",
            "independence_note": (
                "This is EVIDENCE OF LINKAGE ONLY -- it tells us which model Samsung's own download-center system associated with this "
                "download link. It is NOT independent confirmation of what the PDF file actually contains once opened. Per this stage's "
                "explicit instruction, a link parameter is not treated as proof of document content -- only opening and reading the PDF "
                "itself can confirm that."
            ),
        },
    },
    "cross_check_result": {
        "catalog_article_matches_page_sku": True,
        "matching_strength": "Exact character-for-character match between two independent sources (seller catalog vs. Samsung's own JSON-LD) -- this is strong identity evidence and is unaffected by whatever the PDF-content check below finds.",
    },
    "what_stage_8_4_did_and_did_not_establish_about_the_manual": {
        "established": "The manual URL is reachable (HTTP 200), redirects to a first-party samsung.com subdomain, and the response begins with PDF magic bytes ('%PDF-1.6') -- i.e. it is a real PDF file, not a broken link or an HTML error page.",
        "not_established": (
            "Stage 8.4 did NOT open or parse the PDF's actual content. Its 'document_type: User Manual' and 'language: RU-UK-KK-UZ' claims "
            "were based on the URL's own CDCttType=UM query parameter and the filename's language-code suffix -- both first-party but both "
            "still metadata ABOUT the link, not confirmation of what is written inside the file. This stage treats that distinction as "
            "material and re-verifies it by content."
        ),
    },
    "plan_for_this_stage": (
        "1) Fetch the PDF's actual bytes (no saved bytes exist from Stage 8.4 -- only a length + magic-byte check was recorded, not the content itself). "
        "2) Extract text via pypdf (added to the local, gitignored .venv for this purpose -- no project file changed). "
        "3) Search the extracted text for the exact model code MS23K3614AK/BW or an explicitly stated covering model family. "
        "4) Determine actual document language(s) from the extracted text itself, not the filename. "
        "5) Re-check product-page specification completeness from already-saved Stage 8.4 evidence (no new request). "
        "6) Verify the confirmed image belongs to this model using already-saved evidence, with a live reachability check only if needed."
    ),
}
json.dump(review, open(OUT / 'evidence_separation.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote evidence_separation.json')
