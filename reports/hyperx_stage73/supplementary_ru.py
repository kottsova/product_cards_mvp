"""Recheck a previously observed official press relation, not PDP discovery."""
import sys,json
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.census.public_browser import PublicBrowserSession
R=Path(__file__).parent
url='https://hyperx.com/blogs/press/hyperx-alloy-origins-65-mechanical-gaming-keyboard-now-shipping-with-colorway-customizations'
b=PublicBrowserSession(allowed_hosts=('hyperx.com',),fetch_log_path=R/'hyperx_fetch_log.json',profile_dir=Path('data/hyperx_stage73_chrome_profile'),visible=True,use_system_ca=True)
try:
 b.start();b.call('goto',url=url);result=b.call('document_snapshot');html=result.pop('html')
 (R/'ru_press_live.html').write_text(html,encoding='utf8')
 rows=[tr.get_text(' | ',strip=True) for tr in BeautifulSoup(html,'html.parser').select('tr') if '4P5D6AX#ACB' in tr.get_text()]
 text=BeautifulSoup(html,'html.parser').get_text(' ',strip=True);index=text.find('4P5D6AX#ACB');excerpt=text[max(0,index-250):index+200] if index>=0 else ''
 relation={'part':'4P5D6AX#ACB','model':'Alloy Origins 65','layout':'Russian','switch':'HyperX Red','color':'not confirmed','basis':'published Red Switch heading and literal part/layout entry','excerpt':excerpt} if 'HyperX Red Switch' in excerpt and 'Russian' in excerpt else None
 out={'origin':'actual supplementary GET of previously observed Stage72 official press; not PDP discovery','url':url,'browser':result,'exact_part_rows':rows,'published_part_relation':relation,'retail_configuration':'partial; no current RU variant/color/gallery binding','confirmed_configuration_not_promoted':True}
 (R/'ru_relation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(rows)
finally:b.close()
