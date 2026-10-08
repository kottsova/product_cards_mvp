"""Capture official public structure with the shared policy-aware HTTP client."""
import hashlib, json, time
from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.adapters.policy_session import PolicyAwareSession

ROOT=Path('reports/playstation_stage66')
URLS={
 'manuals_gb':'https://www.playstation.com/en-gb/support/hardware/manuals/',
 'manuals_ru':'https://www.playstation.com/ru-ru/support/hardware/manuals/',
 'ps5':'https://www.playstation.com/en-gb/ps5/',
 'pro':'https://www.playstation.com/en-gb/ps5/ps5-pro/',
 'dualsense':'https://www.playstation.com/en-gb/accessories/dualsense-wireless-controller/',
 'portal':'https://www.playstation.com/en-gb/accessories/playstation-portal-remote-player/',
 'elite':'https://www.playstation.com/en-gb/accessories/pulse-elite-wireless-headset/',
 'robots':'https://www.playstation.com/robots.txt',
 'sitemap':'https://www.playstation.com/sitemap.xml',
 'sitemap_index':'https://www.playstation.com/sitemap_index.xml',
 'sitemap_gb':'https://www.playstation.com/en-gb/sitemap.xml',
 'sitemap_ru':'https://www.playstation.com/ru-ru/sitemap.xml',
 'direct_home':'https://direct.playstation.com/en-gb/',
 'direct_black':'https://direct.playstation.com/en-gb/buy-accessories/dualsense-wireless-controller-midnight-black-for-ps5-pc-mac-mobile',
 'direct_bundle':'https://direct.playstation.com/en-gb/buy-consoles/playstation5-digital-edition-console-825-gb-fortnite-flowering-chaos-bundle',
 'support_legacy':'https://support.playstation.com/',
 'sie':'https://sonyinteractive.com/en/our-company/',
}

def main():
 session=PolicyAwareSession(ROOT/'probe_http.json',allowed_hosts=('playstation.com','sonyinteractive.com'))
 old=json.loads((ROOT/'source_structure.json').read_text(encoding='utf-8')) if (ROOT/'source_structure.json').exists() else []
 import sys
 out=[v for v in old if v['key'] not in (sys.argv[1:] if len(sys.argv)>1 else URLS)]
 for key,url in URLS.items():
  if len(sys.argv)>1 and key not in sys.argv[1:]:continue
  try:
   response=session.get(url,timeout=10);body=response.text
   (ROOT/(key+'.html')).write_text(body,encoding='utf-8')
   soup=BeautifulSoup(body,'html.parser')
   links=[dict(label=a.get_text(' ',strip=True),url=a.get('href')) for a in soup.select('a[href]') if any(x in (str(a.get('href'))+a.get_text()).lower() for x in ('cfi','manual','sitemap','.pdf','product','ps5'))]
   structured=[s.get_text()[:12000] for s in soup.select('script[type="application/ld+json"]')]
   out.append(dict(key=key,url=url,final_url=response.url,status=response.status_code,bytes=len(response.content),sha256=hashlib.sha256(response.content).hexdigest(),h1=[h.get_text(' ',strip=True) for h in soup.select('h1')],links=links,structured=structured,scripts=[s.get('src') for s in soup.select('script[src]')],cfi_lines=[x for x in body.splitlines() if 'CFI-' in x][:12]))
   print(key,response.status_code,len(response.content),flush=True)
  except Exception as e:
   out.append(dict(key=key,url=url,error=str(e)));print(key,str(e),flush=True)
  (ROOT/'source_structure.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
