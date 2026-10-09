"""Read actual declared sitemap XML and expose own model/SKU URL candidates."""
from pathlib import Path
from xml.etree import ElementTree as ET
import json
R=Path(__file__).parent;out=[]
for p in (R/'observed').glob('*.html'):
 text=p.read_text(encoding='utf8')
 if '<urlset' not in text[:1000]:continue
 root=ET.fromstring(text)
 urls=[n.text for n in root.iter() if n.tag.endswith('}loc') and n.text]
 urls.extend(n.get('href') for n in root.iter() if n.tag.endswith('}link') and n.get('href'))
 out.extend(u for u in urls if any(t in u.lower() for t in ('razer-viper-v3-pro','razer-deathadder-v3-pro','razer-blackwidow-v4-75','razer-huntsman-mini','razer-blackshark-v2-pro','razer-barracuda-x','razer-blade-16','razer-wolverine-v3-pro')))
(R/'catalog_candidates.json').write_text(json.dumps(sorted(set(out)),indent=2),encoding='utf8')
groups={}
for u in sorted(set(out)):
 model=u.split('/')[-2];groups.setdefault(model,[]).append(u)
for k,v in groups.items():print(k,len(v),v[:4])
