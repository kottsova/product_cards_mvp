"""Reuse established audit tools; never modify historical reports."""
from pathlib import Path
R=Path(__file__).parent;old=R.parent/'xbox_stage68'
s=(old/'replay.py').read_text(encoding='utf8')
s=s.replace("((R/'xbox_fetch.json',R/'xbox_captures'),(R/'explore_http.json',R/'observed'))", "((R/'live_final_a'/'xbox_fetch.json',R/'live_final_a'/'xbox_captures'),)")
s=s.replace("R/'dataset.json'", "R.parent/'xbox_stage68'/'dataset.json'").replace("R/'dataset.sha256'", "R.parent/'xbox_stage68'/'dataset.sha256'")
s=s.replace('stage=68','stage=69').replace('Stage 68','Stage 69').replace('xb68','xb69')
(R/'replay.py').write_text(s,encoding='utf8')
s=(old/'inspect_photos.py').read_text(encoding='utf8').replace('acceptance_final.json','live_final_b.json')
(R/'inspect_photos.py').write_text(s,encoding='utf8')
for name in ('verify_images.py','run_regression.py'):
 (R/name).write_text((old/name).read_text(encoding='utf8'),encoding='utf8')
s=(old/'qa_ui_excel.py').read_text(encoding='utf8').replace("R/'acceptance_release_final.sqlite3'","R/'live_final_b'/'batches.sqlite3'").replace('xb68','xb69').replace('(3,4,7,9,10)','(1,2,4,8,10)')
s=s.replace("book.close()", "assert book['Связи Xbox'].max_row > 10\n assert book['Принятые факты Xbox'].max_row > 100\n book.close()")
(R/'qa_ui_excel.py').write_text(s,encoding='utf8')
s=(old/'render_excel.mjs').read_text(encoding='utf8').replace('xbox_stage68','xbox_stage69')
s=s.replace("['Документы Xbox','A1:G8','documents']", "['Документы Xbox','A1:G8','documents'],['Связи Xbox','A1:I6','relations'],['Принятые факты Xbox','A1:G8','accepted']")
(R/'render_excel.mjs').write_text(s,encoding='utf8')
s=(old/'record_migration.py').read_text(encoding='utf8').replace('Stage 68','Stage 69').replace('STAGE68','STAGE69')
s=s.replace("if n.startswith('product_tool/')", "if n.startswith('product_tool/')")
s=s.replace('user-authorized Xbox dispatch; separate model, Store Product ID/SKU and hardware evidence; scoped Russian UI/Excel; shared policy/search/sitemap/normalization. Prior brand branches and readiness thresholds preserved.', 'user-authorized Xbox exact discovery, official catalog/search routing, hardware-retail relations, scoped extraction/photos, bounded network retry and attended fallback. Prior brand defaults and numeric readiness thresholds preserved.')
(R/'record_migration.py').write_text(s,encoding='utf8')
print('Stage 69 checks prepared from existing audit tools')
