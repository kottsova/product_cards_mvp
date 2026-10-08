"""Read-only rendering of the official hardware specification pages."""
import json,re
from pathlib import Path
import pypdfium2 as pdfium
r=Path('reports/playstation_stage66');out=[]
for code in ('CFI-1216A','CFI-1216B','CFI-2016A_B','CFI-7021'):
    pdf=pdfium.PdfDocument(r/(code+'.pdf'))
    for i in range(len(pdf)):
        page=pdf[i];text=page.get_textpage().get_text_range()
        if 'Specifications' in text and ('Main Processor' in text or 'External dimensions' in text):
            name=f'{code}_spec_page_{i+1}.png';page.render(scale=1.4).to_pil().save(r/name);out.append(dict(code=code,page=i+1,file=name));break
(r/'document_render.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(out)
