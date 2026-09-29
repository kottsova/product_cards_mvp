"""Stage 11.1 -- final card: updated 9A273AA export status (image evidence
upgraded to integrity+visual confirmation, identity framing corrected), plus
the HyperX adapter status with an explicit, scoped claim."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
STAGE11 = ROOT / 'reports/source_census_2026-09-23_stage11'
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_1'

stage11_card = json.loads((STAGE11 / 'card.json').read_text(encoding='utf-8'))
reaudit = json.loads((OUT / 'offline_card_reaudit.json').read_text(encoding='utf-8'))
phase1_images = json.loads((OUT / 'phase1_robots_and_images.json').read_text(encoding='utf-8'))
additional = json.loads((OUT / 'additional_rows_and_adapter_status.json').read_text(encoding='utf-8'))

# --- 9A273AA: carry forward Stage 11's exportable fields, but replace the image
# evidence entries with integrity+visual-verified ones, and correct the identity wording.
image_verification = []
for url, r in phase1_images['image_results'].items():
    image_verification.append({
        'url': url,
        'official_host_confirmed': r['host_is_official_confirmed_host'],
        'byte_integrity': r['completeness'],
        'sha256': r['sha256'],
        'bytes': r['declared_total_bytes'],
        'visual_content_confirmed': (
            'Yes -- both fetched images show a black cylindrical microphone with an RGB-lit '
            'honeycomb grille, an "HX" HyperX logo, a shock-mount cradle, a gain/mute knob with '
            'headphone icon, and (angle_2) a USB-C port -- consistent with the QuadCast 2S Black '
            'described on the same page. Neither image shows an unrelated product or a '
            'different color.'
        ),
    })

card = {
    'stage': '11.1',
    'scope': 'Re-audit of 9A273AA image/identity evidence, plus a scoped HyperX adapter-repeatability check across 2 additional catalog rows (keyboard, mouse). No other brand.',

    'quadcast_2s_9A273AA': {
        'identity_confirmation_corrected': reaudit['correction']['corrected_statement'],
        'image_evidence_upgraded': {
            'stage11_basis': 'filename-substring match only (SKU string present in each CDN URL)',
            'stage11_1_basis': 'official host confirmed + byte integrity verified (Range-assembled, size matches declared Content-Range total) + actual visual content inspected',
            'verified_images': image_verification,
            'note': (
                'Only 2 of the 9 known image URLs were fetched and inspected this stage (a small '
                'number, per instructions), not all 9. The other 7 remain filename-matched only, '
                'unless a future stage checks them the same way.'
            ),
        },
        'manual_status_unchanged': reaudit['manual_status_carried_forward_unchanged']['explicit_statement'],
        'export_fields_unchanged_from_stage11': stage11_card['exportable_fields_with_evidence'],
        'export_readiness_unchanged': stage11_card['export_readiness'],
    },

    'additional_catalog_rows_checked': additional['additional_catalog_rows'],

    'hyperx_adapter_status': {
        'scope_statement': (
            'HyperX (hyperx.com, Shopify) has now been checked live on 3 real product pages '
            'covering 3 different peripheral types (USB microphone, mechanical keyboard, '
            'wireless mouse), plus 2 earlier sanitized-fixture-only samples (a gaming headset '
            'and a keyboard+mouse bundle, Stage 8/8.1) that yielded no retained values by design.'
        ),
        'confirmed_compatible_primitive_field_shape_across_3_live_pages': [
            'JSON-LD Product with .sku/.productID/.gtin12 (identity field SHAPE only)',
            'JSON-LD Product.additionalProperty array (specification field SHAPE only -- NOT its value population, see below)',
            'JSON-LD Product.image with explicit width/height (media field AND value, reliable)',
            'A DOM specifications table (<td class="specs-label">/<td class="specs-value">) -- reliable VALUE source on all 3 pages',
        ],
        'confirmed_page_specific_not_a_shared_guarantee': [
            'additionalProperty VALUE population: empty on the microphone, 1/5 populated on the mouse, 6/10 populated on the keyboard -- the reader must check each page for non-empty values rather than assume them',
            'Exact catalog-row SKU match: confirmed on 2/3 checked rows (microphone, mouse); the keyboard\'s catalog row is a different regional/layout variant (RU vs the fetched page\'s US layout) -- not confirmed, not papered over',
        ],
        'corrected_from_stage8_1': [
            'The DOM "responsive_srcset" marker was treated in Stage 8.1 as a confirmed shared media primitive. Across all 3 live pages this project has now read in full, every genuine multi-width srcset belongs to the shared site logo, never a product photo -- product images are always single-URL. This marker should not be relied on for image resolution selection; the JSON-LD image.width/height is the reliable source instead.',
        ],
        'documents_still_unconfirmed': '0 PDF links found across all 5 HyperX product pages examined project-wide (3 live, 2 sanitized-fixture-only). A stable negative pattern, not proof of universal absence.',
        'adapter_verdict': (
            'HyperX supports a repeatable EXTRACTION SHAPE (JSON-LD Product + a DOM specs table) '
            'confirmed across 3 independent peripheral categories -- this is a genuine, evidenced '
            'compatible_primitive at the structural level. It does NOT support a fully repeatable '
            'IDENTITY-to-catalog-row guarantee: 2 of 3 checked rows matched exactly by SKU, one '
            'did not (a real regional-variant gap, not a data problem). A generic adapter can '
            'therefore extract HyperX product data reliably, but each catalog row\'s exact '
            'variant match must still be verified individually -- the shared template is not '
            'itself proof of a correct row-to-page match.'
        ),
    },

    'gaps': [
        '7 of the 9 known QuadCast 2S images remain filename-matched only, not integrity/visually verified',
        'Manual (Quick Start Guide) confirmed physically included; no online document or language confirmed for 9A273AA',
        'Keyboard catalog row (7G7A4AA#ACB, RU layout) has no confirmed exact-match official page -- only the US-layout sibling (7G7A4AA#ABA) was found',
        'Documents contract remains unconfirmed across the whole HyperX family sampled so far',
    ],
}

(OUT / 'card.json').write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding='utf-8')
print('adapter_verdict:', card['hyperx_adapter_status']['adapter_verdict'][:200])
