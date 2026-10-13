"""Only Stage 81 anonymous public response artifacts; preserve original proof hashes."""
import sys,json,re,hashlib,subprocess,gzip
from pathlib import Path
from bs4 import BeautifulSoup
R=Path(__file__).parent
files=[Path(p) for p in subprocess.check_output(['git','ls-files','--others','--exclude-standard',str(R)],text=True).splitlines()]
pattern=re.compile(r'("(?:cookie|clientIpAddress)"\s*:\s*)"(?:\\.|[^"\\])*"',re.I)
cache={};updates=[];mapping={}
def sanitize(text):
 text,n=pattern.subn(lambda m:m[1]+'"[redacted]"',text)
 if 'self.__next_f.push' in text:
  for script in BeautifulSoup(text,'html.parser').select('script'):
   old=script.get_text();match=re.fullmatch(r'self\.__next_f\.push\((\[.*\])\)',old,re.S)
   if not match:continue
   try:chunk=json.loads(match[1])
   except ValueError:continue
   if len(chunk)!=2 or chunk[0]!=1 or not isinstance(chunk[1],str):continue
   new,hits=pattern.subn(lambda m:m[1]+'"[redacted]"',chunk[1])
   if hits:chunk[1]=new;text=text.replace(old,'self.__next_f.push('+json.dumps(chunk,ensure_ascii=False)+')',1);n+=hits
 return text,n
for p in files:
 if p.suffix not in {'.html','.gz','.bin'}:continue
 raw=p.read_bytes();compressed=p.suffix=='.gz'
 try:body=gzip.decompress(raw) if compressed else raw;text=body.decode('utf8')
 except (UnicodeError,OSError):continue
 old=hashlib.sha256(body).hexdigest()
 if old not in cache:
  changed,n=sanitize(text);cache[old]=(changed.encode('utf8'),n)
 stored,n=cache[old]
 if stored==body:continue
 encoded=gzip.compress(stored,mtime=0) if compressed else stored;p.write_bytes(encoded)
 new=hashlib.sha256(stored).hexdigest();mapping[old]=new
 updates.append({'file':str(p),'original_response_sha256':old,'stored_sha256':new,'redactions':['cookie','clientIpAddress'],'matches':n})
def amend(x):
 if isinstance(x,dict):
  x=dict(x)
  for key in ('sha256','html_sha256'):
   if x.get(key) in mapping:
    original=x[key];x['original_response_'+key]=original;x[key]=mapping[original];x['privacy_redactions']=['cookie','clientIpAddress']
  return {k:'[redacted]' if k.casefold() in {'cookie','clientipaddress'} and v not in (None,'','[redacted]') else amend(v) for k,v in x.items()}
 if isinstance(x,list):return [amend(v) for v in x]
 if isinstance(x,str):return sanitize(x)[0] if pattern.search(x) or 'self.__next_f.push' in x else x
 return x
for p in files:
 if p.suffix!='.json' or p.name=='publication_amendments.json':continue
 try:x=json.loads(p.read_text(encoding='utf8'))
 except (ValueError,UnicodeError):continue
 y=amend(x)
 if x!=y:p.write_text(json.dumps(y,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(R/'publication_amendments.json').write_text(json.dumps({'scope':'Stage 81 only; no historical Stage 79/80 files edited','fields_only':['cookie','clientIpAddress'],'files':updates,'unique_responses_checked':len(cache)},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print({'unique_response_bodies_checked':len(cache),'privacy_amendments':len(updates)},flush=True)
