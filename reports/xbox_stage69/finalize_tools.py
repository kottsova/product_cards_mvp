"""Select the last unchanged production version for audit tools."""
from pathlib import Path
R=Path(__file__).parent
for n in ('replay.py','check_manuals.py'):
 p=R/n;p.write_text(p.read_text(encoding='utf8').replace('live_final_a','live_final_e'),encoding='utf8')
for n in ('inspect_photos.py','qa_ui_excel.py'):
 p=R/n;p.write_text(p.read_text(encoding='utf8').replace('live_final_b','live_final_f'),encoding='utf8')
print('Final tools use independent live C/D, not earlier diagnostic runs')
