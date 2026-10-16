"""Preserve actual inputs and old UI, then apply narrow template presentation edit."""
import json,shutil,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent
for filename,source in [('LG_12_original.xlsx',root/'data/uploads/a3e4a1df3c1d4876a9028a59e1c2b6a5.xlsx'),('Mixed_original.xlsx',root/'reports/import_stage84/Ordinary_3_columns.xlsx')]:
 shutil.copyfile(source,out/filename)
(out/'batch_before.html').write_bytes(subprocess.check_output(['git','show','HEAD:product_tool/templates/batch.html']))
p=root/'product_tool/templates/product.html';s=p.read_text(encoding='utf8')
old="<td>{{ s.evidence or '—' }}</td><td>{{ s.error or '—' }}</td>"
new="<td>{% if s.source_key == 'sulpak' %}{{ 'Sulpak временно недоступен' if s.error else ('Кандидат Sulpak не подтверждён' if s.match_level != 'full_sku' else 'Артикул подтверждён содержимым страницы') }}<details><summary>Диагностика доступа</summary>{{ s.evidence or '—' }} · {{ s.error or '—' }}</details>{% else %}{{ s.evidence or '—' }}{% endif %}</td><td>{{ '—' if s.source_key == 'sulpak' else (s.error or '—') }}</td>"
assert old in s
p.write_text(s.replace(old,new),encoding='utf8')
