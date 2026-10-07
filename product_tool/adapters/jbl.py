"""JBL official PDP adapter: strict returned SKU, shared policy and source storage."""
from __future__ import annotations
import hashlib,json,re,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit,quote
import requests
from bs4 import BeautifulSoup
from .common import SourceDocument,RawAttribute,PhotoCandidate,ProductDocument,clean_text,utc_now
from .policy_session import PolicyAwareSession
from .lg_documents import BinarySafeSession
from .jbl_documents import assess_guide
from ..jbl_identity import components,model_relation,image_color,variant_field
HOSTS=('jbl.com','uk.jbl.com','de.jbl.com','global.jbl.com','ru.jbl.com','support.jbl.com','id.jbl.com','jbl.kz')
REGIONS=('ru.jbl.com','uk.jbl.com','de.jbl.com','id.jbl.com','global.jbl.com','www.jbl.com')
def article_code(value):return clean_text(value).upper()
def official(url):
 p=urlsplit(url)
 try:return p.scheme=='https' and (p.hostname=='jbl.com' or bool(p.hostname and p.hostname.endswith('.jbl.com')) or p.hostname=='jbl.kz') and not p.username and not p.password and p.port in {None,443}
 except ValueError:return False
def queries(article,name=''):
 base=components(article)['model_code']
 return [f'site:jbl.com "{article}"',f'site:jbl.com "{base}"',f'site:jbl.com {name}'.strip()]
def doc_type(title):
 text=title.casefold()
 if re.search('app|приложен',text):return 'App Guide'
 if re.search('warranty|garantie|гарант',text):return 'Warranty'
 if re.search('safety|sicherheit|безопас',text):return 'Safety Sheet'
 if re.search('quick|kurzanleitung|qsg|кратк',text):return 'Quick Start Guide'
 if re.search('owner|user|manual|руководств',text):return 'User Guide'
 if re.search('spec sheet|datenblatt',text):return 'Spec Sheet'
 return 'Regulatory/Other'
def _objects(value):
 if isinstance(value,dict):
  yield value
  for v in value.values():yield from _objects(v)
 elif isinstance(value,list):
  for v in value:yield from _objects(v)
def parse_pdp(html,url,article):
 soup=BeautifulSoup(html,'html.parser');article=article_code(article);products=[]
 for tag in soup.select('script[type="application/ld+json"]'):
  try:products.extend(x for x in _objects(json.loads(tag.string or tag.get_text())) if x.get('@type')=='Product')
  except (ValueError,TypeError):pass
 root=soup.select_one('.product-wrapper[data-pid], .product-info.product-detail')
 scope=root or soup
 micro=lambda prop:clean_text((scope.select_one(f'[itemprop="{prop}"]') or {}).get('content','')) or (clean_text(scope.select_one(f'[itemprop="{prop}"]').get_text(' ',strip=True)) if scope.select_one(f'[itemprop="{prop}"]') else '')
 product=products[0] if len(products)==1 else {}
 sku=article_code(product.get('sku') or micro('sku'));mpn=article_code(product.get('mpn') or micro('mpn'))
 if not mpn:
  tag=soup.select_one('.pdp-specs [itemprop="mpn"]');mpn=article_code(tag.get_text(' ',strip=True)) if tag else ''
 pid=article_code(root.get('data-pid','')) if root else ''
 name=clean_text(product.get('name') or micro('name'))
 identity=model_relation(article,sku,mpn,pid,context=root is not None,official=official(url),single=len(products)<=1)
 exact=identity['exact_sku'];model_exact=identity['model_confirmed']
 relation='exact_sku' if exact else 'other_variant' if sku else 'family_only' if name else 'unknown'
 report={'article':article,'query_variants':queries(article,name),'identity':{**identity,'relation':relation,'requested':article,'returned_sku':sku,'returned_mpn':mpn,'data_pid':pid,'model':name,'reason':'Returned SKU + MPN + product context' if exact else 'Official coherent SKU/MPN confirms same model; variant evidence separate' if model_exact else 'Base name / request URL does not establish model'},'raw_specs':[],'accepted_specs':[],'rejected_specs':[],'photos':[],'manuals':[],'verified_documents':[],'exact_photo_assets':[],'manual_status':'Не проверена','support_urls':[]}
 doc=SourceDocument('jbl','JBL Official',url,found_model=sku or name,match_level='full_sku' if exact else 'model_confirmed' if model_exact else 'base_model' if name else 'unknown',evidence=json.dumps(report['identity'],ensure_ascii=False),html=html)
 specs=soup.select_one('#pdp-specs--specifications-content')
 if specs:
  section='Specifications'
  for node in specs.children:
   if getattr(node,'name',None) in {'h3','h4'}:section=clean_text(node.get_text(' ',strip=True))
   elif getattr(node,'name',None)=='dl':
    for dt in node.select('dt'):
     dd=dt.find_next_sibling('dd')
     if dd:report['raw_specs'].append({'section':section,'raw_label':clean_text(dt.get_text(' ',strip=True)),'value':clean_text(dd.get_text(' ',strip=True))})
 else:
  for row in soup.select('.spec-row'):
   k=row.select_one('.spec-key');v=row.select_one('.spec-value');container=row.find_parent(class_='spec-accordion');heading=container.select_one('h3') if container else None
   if k and v:report['raw_specs'].append({'section':clean_text(heading.get_text(' ',strip=True)) if heading else 'Specifications','raw_label':clean_text(k.get_text(' ',strip=True)),'value':clean_text(v.get_text(' ',strip=True))})
 for raw in report['raw_specs']:
  label,value=raw['raw_label'],raw['value'];reason=''
  if not model_exact:reason='model_not_proven'
  elif not exact and variant_field(label):reason='variant_specific_field'
  elif not exact and re.search('USB|MP3|file format|sampling rate|bitrate',label,re.I) and re.search('US version|other versions|region|service only',specs.get_text() if specs else soup.select_one('.pdp-specs').get_text() if soup.select_one('.pdp-specs') else '',re.I):reason='regional_technical_difference'
  elif re.search(r'optional|varies|depending|only available|available in|other versions|service only|OTA update|depending on region|USA.*Europe|je nach Region',value,re.I):reason='conditional_or_regional_option'
  elif re.search(r'number of microphones|anzahl.*mikrofon',label,re.I) and not re.fullmatch(r'\d+',value):reason='invalid_microphone_count'
  if reason:report['rejected_specs'].append({**raw,'reason':reason})
  else:doc.attributes.append(RawAttribute(label,value,raw['section']));report['accepted_specs'].append(raw)
 # Marketing lives only inside the dedicated PDP description, never FAQ/support.
 description=soup.select_one('#pdp-specs--description-content')
 if description is None:
  description=next((x.select_one('.accordion-content') for x in soup.select('.pdp-specs .spec-accordion') if x.select_one('h3') and 'description' in x.select_one('h3').get_text().lower()),None)
 if model_exact and description:doc.description=clean_text(description.get_text(' ',strip=True))
 box=soup.select_one('#pdp-specs--box-contents-content, .pdp-specs .box-contents, .box-content, .whats-in-the-box')
 if box:
  value=clean_text(box.get_text(' ',strip=True))
  if value:
   if exact and not re.search(r'depending|varies|optional|region|je nach',value,re.I):doc.attributes.append(RawAttribute('Комплектация',value,'Комплектация'))
   else:report['rejected_specs'].append({'section':'Комплектация','raw_label':'Комплектация','value':value,'reason':'variant_specific_field'})
 # Only JSON-LD exact product images or microdata images in exact PDP scope.
 images=product.get('image',[]) if isinstance(product.get('image',[]),list) else [product.get('image')]
 images=[x for x in images if isinstance(x,str) and x]
 if not images:images=[x.get('data-zoom') or x.get('data-src') or x.get('src') for x in soup.select('.hero-gallery.-main img[itemprop="image"]')]
 color=''
 variation=scope.select_one('.product-variations[data-current]')
 if variation:
  try:color=json.loads(variation['data-current']).get('color',{}).get('displayValue','')
  except (ValueError,TypeError):pass
 report['identity']['color']=color
 for image in dict.fromkeys(x for x in images if x):
  image=urljoin(url,image);key=hashlib.sha256(image.encode()).hexdigest();kind='marketing' if re.search(r'lifestyle|packag|accessor',image,re.I) else 'feature' if re.search(r'diagram|technical|infographic',image,re.I) else 'product_gallery';wanted=identity['requested_components']['color'];observed=image_color(image);color_match=bool(wanted and identity['returned_components']['color']==wanted and (not color or color.casefold()==wanted.casefold()) and (not observed or observed==wanted))
  bound=official(image) and kind=='product_gallery' and model_exact and (color_match if wanted else exact)
  doc.photo_candidates.append(PhotoCandidate(image,key,kind=kind))
  report['photos'].append({'url':image,'asset_key':key,'relation':'exact_sku_gallery' if bound and exact else 'model_color_gallery' if bound else 'candidate','color':color,'role':kind,'verified':bound})
  if bound:report['exact_photo_assets'].append(key)
 # Document relationship derives from a dedicated PDP download section, not footer links.
 downloads=soup.select_one('#pdp-specs--documents-content')
 links=downloads.select('a[href]') if downloads else soup.select('.pdp-specs a[href*="/pdfs/"]')
 for link in links:
  target=urljoin(url,link.get('href',''));title=clean_text(link.get_text(' ',strip=True))
  if '.pdf' not in target.lower() or not official(target) or not title:continue
  report['manuals'].append({'type':doc_type(title),'title':title,'url':target,'language':'unknown','relation':'family_model' if name else 'unknown','verified':False,'pdp_exact':model_exact})
 for link in soup.select('a[href]'):
  target=urljoin(url,link['href'])
  if official(target) and urlsplit(target).hostname=='support.jbl.com' and ('product-registration' in target or '.html' in target):report['support_urls'].append(target)
 return doc,report
class JBLAdapter:
 source_key='jbl';site_name='JBL Official'
 def __init__(self,*,clock=time.monotonic,fetch_log_path=Path('data/jbl_fetch_log.json'),session=None,trace_callback=None,search_provider=None,capture_dir=None):
  self.clock=clock;self.http=session or PolicyAwareSession(fetch_log_path,allowed_hosts=HOSTS,clock=clock,underlying=BinarySafeSession(requests.Session()),max_bytes=50_000_000)
  self.capture_dir=Path(capture_dir) if capture_dir else Path(fetch_log_path).parent/'jbl_captures';self.reports={};self.trace_callback=trace_callback;self.search_provider=search_provider;self.documents=[]
 def trace(self,**item):
  if self.trace_callback:self.trace_callback({'event':'jbl_discovery','timestamp':utc_now(),**item})
 def _capture(self,article):
  path=self.capture_dir/(article+'.manifest.json')
  try:manifest=json.loads(path.read_text(encoding='utf-8'))
  except (OSError,ValueError):return None
  if manifest.get('article')!=article:return None
  for item in manifest.get('records',[]):
   file=item.get('file','')
   if item.get('status')!=200 or item.get('challenge') or Path(file).name!=file or not official(item.get('final_url','')):continue
   try:data=(self.capture_dir/file).read_bytes()
   except OSError:continue
   if hashlib.sha256(data).hexdigest()!=item.get('sha256'):continue
   doc,report=parse_pdp(data.decode('utf-8'),item['final_url'],article)
   if doc.match_level in {'full_sku','model_confirmed'}:return doc,report
  return None
 def find_source(self,article,*,name='',category='',deadline=None):
  article=article_code(article);deadline=deadline or self.clock()+60
  if not re.fullmatch(r'[A-Z0-9-]{5,50}',article):return SourceDocument('jbl',self.site_name,'',error='Invalid full article')
  saved=self._capture(article)
  if saved and (saved[1]['exact_photo_assets'] or not components(article)['color']):
   doc,report=saved;self.reports[article]=report;self.trace(provider='attended_capture',query=article,url=doc.url,region=urlsplit(doc.url).hostname.split('.')[0],source_type='pdp',accepted=True,reason='Verified capture bytes; model and variant checked separately',identity_relation=report['identity']['relation'],model_relation=report['identity']['model_relation'],variant_relation=report['identity']['variant_relation']);return doc
  best=saved;official_deadline=max(self.clock(),deadline-20)
  # Regional exact first; published sitemap before remaining official regions.
  for index,host in enumerate(REGIONS):
   if self.clock()>=official_deadline:break
   if index==1:
    robots=self.http.get('https://www.jbl.com/robots.txt',timeout=min(8,max(1,official_deadline-self.clock())))
    for sitemap in re.findall(r'^Sitemap:\s*(https://\S+)',robots.text,re.M)[:1]:
     if not official(sitemap):continue
     z=self.http.get(sitemap,timeout=min(8,max(1,official_deadline-self.clock())))
     self.trace(provider='official_sitemap',query=article,url=sitemap,region='us',source_type='sitemap',accepted=False,reason=z.marker or 'Index discovery; not identity',identity_relation='unknown')
   part=components(article);base=part['model_code'];region=part['region'];regionaless=article[:-len(region)] if region else article
   candidates=list(dict.fromkeys((article,regionaless)))
   for candidate_code in candidates:
    if self.clock()>=official_deadline:break
    url=f'https://{host}/'+quote(candidate_code)+'.html'
    try:z=self.http.get(url,timeout=min(8,max(1,official_deadline-self.clock())))
    except Exception as e:self.trace(provider='regional_exact',query=article,url=url,region=host.split('.')[0],source_type='pdp',accepted=False,reason=str(e),identity_relation='unknown');continue
    if not z.ok:self.trace(provider='regional_exact',query=article,url=url,region=host.split('.')[0],source_type='pdp',accepted=False,reason=z.marker or str(z.status_code),identity_relation='unknown');continue
    doc,report=parse_pdp(z.text,z.url,article);accepted=doc.match_level in {'full_sku','model_confirmed'}
    self.trace(provider='regional_exact',query=article,url=z.url,region=host.split('.')[0],source_type='pdp',accepted=accepted,reason=report['identity']['reason'],identity_relation=report['identity']['relation'],model_relation=report['identity']['model_relation'],variant_relation=report['identity']['variant_relation'])
    if accepted and (report['exact_photo_assets'] or not part['color']):
     self.reports[article]=report;self.capture_dir.mkdir(parents=True,exist_ok=True);file=article+'_http.html';data=z.text.encode('utf-8');(self.capture_dir/file).write_bytes(data);(self.capture_dir/(article+'.manifest.json')).write_text(json.dumps({'article':article,'records':[{'file':file,'sha256':hashlib.sha256(data).hexdigest(),'final_url':z.url,'status':200,'challenge':False,'provider':'policy_http'}]},indent=2),encoding='utf-8');return doc
    if best is None or accepted:best=(doc,report)
   # Verified Harman regional search endpoint; the official server resolves model names.
   if host=='id.jbl.com' and self.clock()<official_deadline:
    native=self.regional_search(article,name,deadline=official_deadline)
    if native:
     doc,report=native;self.reports[article]=report
     self.capture_dir.mkdir(parents=True,exist_ok=True);file=article+'_http.html';data=doc.html.encode('utf-8');(self.capture_dir/file).write_bytes(data)
     (self.capture_dir/(article+'.manifest.json')).write_text(json.dumps({'article':article,'records':[{'file':file,'sha256':hashlib.sha256(data).hexdigest(),'final_url':doc.url,'status':200,'challenge':False,'provider':'regional_official_search'}]},indent=2),encoding='utf-8');return doc
  if self.clock()<official_deadline:
   support='https://support.jbl.com/gb/en/'
   try:
    response=self.http.get(support,timeout=min(8,max(1,official_deadline-self.clock())))
    self.trace(provider='support',query=article,url=support,region='gb',source_type='support',accepted=False,reason=response.marker or 'Support landing is discovery only; no exact SKU proof',identity_relation='family_only')
   except Exception as exc:self.trace(provider='support',query=article,url=support,region='gb',source_type='support',accepted=False,reason=str(exc),identity_relation='unknown')
  # Same shared injected search provider; no JBL search engine.
  if self.search_provider is None and self.clock()<deadline:self.search_provider=self.shared_search
  if self.search_provider and self.clock()<deadline:
   for candidate in self.search_provider(queries(article,name),deadline=deadline):
    url=getattr(candidate,'url','')
    if not official(url):continue
    z=self.http.get(url,timeout=8)
    if not z.ok:continue
    doc,report=parse_pdp(z.text,z.url,article)
    accepted=doc.match_level in {'full_sku','model_confirmed'}
    self.trace(provider='external_search',query=queries(article,name)[1],url=z.url,region=urlsplit(z.url).hostname,source_type='pdp',accepted=accepted,reason=report['identity']['reason'],model_relation=report['identity']['model_relation'],variant_relation=report['identity']['variant_relation'])
    if accepted:self.reports[article]=report;return doc
  else:self.trace(provider='external_search',query=queries(article,name)[0],url='',region='global',source_type='search',accepted=False,reason='External search deadline exhausted',identity_relation='unknown')
  if best:doc,report=best;self.reports[article]=report;return doc
  self.reports[article]={'article':article,'query_variants':queries(article,name),'identity':{'relation':'unknown'},'manuals':[],'manual_status':'Не проверена','exact_photo_assets':[],'verified_documents':[],'raw_specs':[],'accepted_specs':[],'rejected_specs':[]}
  return SourceDocument('jbl',self.site_name,'',error='Official access/discovery gap; exact full SKU not proven')
 def regional_search(self,article,name,*,deadline):
  from ..jbl_identity import COLORS,REGIONS
  term=re.sub(r'\b(?:'+ '|'.join(map(re.escape,list(COLORS.values())+list(REGIONS)))+r')\b','',name,flags=re.I)
  term=re.sub(r'^\s*JBL\s*','',term,flags=re.I);term=' '.join(term.split()) or components(article)['model_code']
  url='https://id.jbl.com/en/search?q='+quote(term)
  try:response=self.http.get(url,timeout=min(8,max(1,deadline-self.clock())))
  except Exception as exc:
   self.trace(provider='regional_official_search',query=term,url=url,region='id',source_type='search',accepted=False,reason=str(exc),model_relation='unproven',variant_relation='unproven');return None
  self.trace(provider='regional_official_search',query=term,url=response.url,region='id',source_type='search',accepted=False,reason=response.marker or 'Official server search/redirect is discovery only',model_relation='discovery_only',variant_relation='unproven')
  if not response.ok:return None
  doc,report=parse_pdp(response.text,response.url,article)
  if doc.match_level in {'full_sku','model_confirmed'} and report['exact_photo_assets']:
   self.trace(provider='regional_official_search',query=term,url=doc.url,region='id',source_type='pdp',accepted=True,reason=report['identity']['reason'],model_relation=report['identity']['model_relation'],variant_relation=report['identity']['variant_relation']);return doc,report
  soup=BeautifulSoup(response.text,'html.parser');wanted=components(article)['color'];links=[]
  for tag in soup.select('.product-tile .product-swatches a[title], .product-tile a.thumb-link'):
   if tag.find_parent(class_='product-swatches') and tag.get('title','').casefold()!=wanted.casefold():continue
   target=urljoin(response.url,tag.get('href',''))
   if official(target) and target not in links:links.append(target)
  for target in links[:4]:
   if self.clock()>=deadline:break
   z=self.http.get(target,timeout=min(8,max(1,deadline-self.clock())))
   if not z.ok:continue
   doc,report=parse_pdp(z.text,z.url,article);accepted=doc.match_level in {'full_sku','model_confirmed'} and bool(report['exact_photo_assets'])
   self.trace(provider='regional_official_search',query=term,url=z.url,region='id',source_type='pdp',accepted=accepted,reason=report['identity']['reason'],model_relation=report['identity']['model_relation'],variant_relation=report['identity']['variant_relation'])
   if accepted:return doc,report
  return None
 def shared_search(self,query_plan,*,deadline):
  from .lg_browser_search import LGBrowserSearch
  from ..census.browser_contracts import BrowserBudget
  hosts=tuple(dict.fromkeys(HOSTS+('www.jbl.com','ca.jbl.com','kh.jbl.com','th.jbl.com','ch.jbl.com','pl.jbl.com','dk.jbl.com','in.jbl.com')))
  search=LGBrowserSearch(self.http.log_path.with_name('jbl_browser_search_log.json'),official_host='www.jbl.com',official_hosts=hosts,allowed_hosts=hosts+('www.google.com','google.com','gstatic.com','www.bing.com','bing.com','duckduckgo.com'),clock=self.clock,budget=BrowserBudget(deadline_seconds=min(60,max(1,deadline-self.clock())),operation_timeout_seconds=min(10,max(1,deadline-self.clock()))))
  search.trace_callback=self.trace_callback
  try:
   for query in query_plan[:3]:
    if self.clock()>=deadline:break
    result=search.search_provider('google',query)
    self.trace(provider='external_search',query=query,url='',region='global',source_type='search',accepted=bool(result.candidates),reason=result.outcome,model_relation='discovery_only',variant_relation='unproven')
    yield from result.candidates
    if result.outcome in {'runtime_unavailable','challenge_detected','rate_limited','http_denied','host_stopped'}:break
  finally:search.close()
 def find_documents(self,document,article):
  from io import BytesIO
  from pypdf import PdfReader
  report=self.reports[article];documents=[];checked=True
  cache_path=self.capture_dir/(article+'.documents.json')
  try:cache=json.loads(cache_path.read_text(encoding='utf-8'))
  except (OSError,ValueError):cache={}
  for item in report.get('manuals',[]):
   if item['type'] not in {'User Guide','Quick Start Guide'} or not item.get('pdp_exact'):continue
   try:
    saved=cache.get(item['url'],{});raw=None
    file=saved.get('file','')
    if file and Path(file).name==file:
     try:
      data=(self.capture_dir/file).read_bytes()
      if hashlib.sha256(data).hexdigest()==saved.get('sha256'):raw=data
     except OSError:pass
    if raw is None:
     z=self.http.get(item['url'],timeout=12)
     if not z.ok or z.truncated:checked=False;item['technical_blocker']='response_size_budget_exceeded' if z.truncated else z.marker or str(z.status_code);continue
     raw=z.text.encode('latin-1')
    if not raw.startswith(b'%PDF-'):checked=False;continue
    reader=PdfReader(BytesIO(raw))
    if len(reader.pages)>300:checked=False;item['technical_blocker']='Document page budget exceeded';continue
    pages=[p.extract_text() or '' for p in reader.pages]
    if sum(len(t) for t in pages)<100:checked=False;item['technical_blocker']='Insufficient extractable text; visual/OCR review required';continue
    name=report['identity'].get('model','');assessment=assess_guide(pages,name,item['type'])
    item.update(assessment,pages=len(pages),proof_sha256=hashlib.sha256(raw).hexdigest())
    self.capture_dir.mkdir(parents=True,exist_ok=True);file=item['proof_sha256']+'.pdf';(self.capture_dir/file).write_bytes(raw);item['proof_file']=file;cache[item['url']]={'file':file,'sha256':item['proof_sha256']}
    if not item['verified'] and assessment['language_assessment'].get('russian_present') and len(assessment.get('quick_guide_ru_operations',[]))>=2 and not (assessment.get('model_relation_verified') and assessment.get('content_title_verified')):
     checked=False;item['technical_blocker']='Russian operations present; extracted document model/title needs visual review'
    if item['verified']:
     item['language']='Русский';report['verified_documents'].append(item['url']);documents.append(ProductDocument(item['type']+' — '+item['title'],'Русский','','',item['url'],document.url,article,name,document.url,True))
   except Exception as e:checked=False;item['technical_blocker']=str(e)[:150]
  report['manual_status']='Проверена' if documents else 'Проверена, не найдена' if checked and report.get('manuals') and document.match_level in {'full_sku','model_confirmed'} else 'Не проверена';report['manual_check_complete']=checked
  self.capture_dir.mkdir(parents=True,exist_ok=True);cache_path.write_text(json.dumps(cache,indent=2),encoding='utf-8')
  self.documents=documents;return documents
