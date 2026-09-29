"""Stage 11.2 -- offline extraction of the full structured text-description
block (the data-description attribute), which pairs each of the 5 annotated
gallery images with its own heading+paragraph. No new network request."""
import html
import json
import re
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
STAGE11 = ROOT / 'reports/source_census_2026-09-23_stage11'
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_2'

text = (STAGE11 / 'raw/hyperx_quadcast_2s_product_page.html.txt').read_text(encoding='utf-8', errors='replace')
m = re.search(r'data-description="([^"]+)"', text)
raw = html.unescape(m.group(1))

# Split into <b>Heading</b><br><br>Paragraph blocks
blocks = re.findall(r'<b>([^<]+)</b>\s*(?:<br>\s*)*(.*?)(?=<b>|$)', raw, re.S)
sections = []
for heading, body in blocks:
    body_plain = re.sub(r'<[^>]+>', ' ', body)
    body_plain = re.sub(r'\s+', ' ', body_plain).strip()
    if body_plain:
        sections.append({'heading': heading.strip(), 'text': body_plain})

# Map headings to the 5 annotated gallery image slugs found in phase 0
heading_to_image_slug = {
    'Dynamic Lighting Display': 'annotated_2_dynamic_en (also referenced by the overview bullet list)',
    'Tap-to-Mute Sensor': 'annotated_3_tap_en',
    'Versatile Multifunction Knob': 'annotated_4_versatile_en',
    'Redesigned Detachable Shock Mount': 'annotated_5_redesigned_en',
    'Four Selectable Polar Patterns': 'annotated_1_future_en (overview slide; "Future Ready Audio" bullet covers polar patterns + audio capability)',
}
for s in sections:
    s['likely_gallery_image'] = heading_to_image_slug.get(s['heading'])

output = {
    'source': 'data-description attribute on the product page (already-saved Stage 11 HTML, re-read offline)',
    'sections': sections,
}
(OUT / 'text_sections.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
for s in sections:
    print('-', s['heading'])
