from pathlib import Path
from product_tool.adapters.policy_session import PolicyAwareSession,record_responses
from bs4 import BeautifulSoup
import json
root=Path('reports/lenovo_stage60')
s=PolicyAwareSession(root/'structure_fetch_log.json',allowed_hosts=('lenovo.com','psref.lenovo.com','pcsupport.lenovo.com','support.lenovo.com'))
urls=['https://psref.lenovo.com/Detail/2475?M=21ML005BUS','https://psref.lenovo.com/Detail/2475?M=21ML001UCK','https://psref.lenovo.com/Product/ThinkPad/ThinkPad_T14_Gen_5_Intel','https://www.lenovo.com/us/en/p/laptops/thinkpad/thinkpadt/thinkpad-t14-gen-5-14-inch-intel/21ml005bus','https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-t-series-laptops/thinkpad-t14-gen-5-type-21ml-21mm/21ml/21ml005bus']
with record_responses(root/'structure_responses'):
 for i,u in enumerate(urls):
  r=s.get(u,timeout=10)
  (root/f'structure_{i}.html').write_text(r.text,encoding='utf-8')
  soup=BeautifulSoup(r.text,'html.parser')
  print(json.dumps({'url':u,'final':r.url,'status':r.status_code,'marker':r.marker,'bytes':len(r.content),'text':soup.get_text(' ',strip=True)[:2200],'scripts':[x.get('src') for x in soup.select('script[src]')][-12:]},ensure_ascii=True),flush=True)
