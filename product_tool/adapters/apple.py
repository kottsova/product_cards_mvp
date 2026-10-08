"""Conservative Apple order-page adapter on the shared HTTP/source interfaces.
Unresolved configuration options remain evidence candidates, never facts.
"""
import json,re,time,hashlib
from pathlib import Path
from urllib.parse import urlsplit,quote
from bs4 import BeautifulSoup
from .common import SourceDocument,RawAttribute,PhotoCandidate,clean_text,utc_now
from .policy_session import PolicyAwareSession

def official(url):
 p=urlsplit(url)
 try:return p.scheme=='https' and (p.hostname=='apple.com' or bool(p.hostname and p.hostname.endswith('.apple.com'))) and not p.username and not p.password and p.port in {None,443}
 except ValueError:return False

def objects(x):
 if isinstance(x,dict):
  yield x
  for v in x.values():yield from objects(v)
 elif isinstance(x,list):
  for v in x:yield from objects(v)

def structured(soup):
 out=[]
 for s in soup.select('script[type="application/ld+json"]'):
  try:out.extend(objects(json.loads(s.get_text())))
  except (ValueError,TypeError):pass
 return out

def selection(soup):
 for s in soup.select('script'):
  t=s.get_text()
  if 'window.PRODUCT_SELECTION_BOOTSTRAP' not in t or 'productSelectionData:' not in t:continue
  try:return json.JSONDecoder().raw_decode(t.split('productSelectionData:',1)[1].lstrip())[0]
  except ValueError:pass
 return {}

def parse_page(html,url,article):
 b=BeautifulSoup(html,'html.parser');title=clean_text(b.h1.get_text(' ',strip=True)) if b.h1 else '';data=structured(b);products=[x for x in data if x.get('@type')=='Product'];sku=article.strip().upper();ev={'identity':{'model':'unproven','configuration':'unproven','variant':'unproven','part_number':sku,'hardware_model_numbers':[]},'raw_specs':[],'configuration_candidates':[],'photo_candidates':[],'manual_status':'Не проверена','manuals':[]}
 doc=SourceDocument('apple','Apple',url,found_model=title,html=html)
 if not official(url) or len(products)!=1:
  doc.error='Not an official single Product order page';return doc,ev
 product=products[0];offers=product.get('offers',[]);offers=offers if isinstance(offers,list) else [offers];returned={str(x.get('sku','')).upper() for x in offers if isinstance(x,dict) and x.get('@type')=='Offer'};returned.add(str(product.get('sku','')).upper());exact=bool(re.fullmatch(r'[A-Z0-9]{5,8}[A-Z]{2}/A',sku)) and sku in returned and len(returned-{''})==1
 select=selection(b);matches=[x for x in select.get('products',[]) if x.get('partNumber','').upper()==sku]
 if matches:
  fingerprints={json.dumps({k:v for k,v in x.items() if k.startswith('dimension') and k!='dimensionSteporder'},sort_keys=True) for x in matches}
  if len(fingerprints)==1:
   ev['selected_configuration']=json.loads(next(iter(fingerprints)));ev['identity'].update(model='model_from_order_record',variant='color_from_order_record',configuration='partial_order_record')
   for x in matches[:1]:
    color=x.get('dimensionColor');storage=x.get('dimensionCapacity') or x.get('dimensionStorage')
    for label,value in [('Цвет',color),('Объём накопителя',storage)]:
     if value:ev['configuration_candidates'].append({'section':'Configuration','raw_label':label,'value':value,'reason':'Selection record; remaining commercial configuration requires resolution'})
   image=select.get('imageDictionary',{}).get(matches[0].get('imageKey'),{})
   for source in image.get('sources',[]):
    u=source.get('srcSet','');color=matches[0].get('dimensionColor','');key=matches[0].get('imageKey','');path=urlsplit(u).path.lower();host=urlsplit(u).hostname or ''
    if color and key and image.get('imageName')==key and key.lower() in path and color.lower() in key.lower() and host.endswith('.cdn-apple.com'):
     asset=hashlib.sha256(u.encode()).hexdigest();doc.photo_candidates.append(PhotoCandidate(u,asset));doc.photos.append(u)
    else:ev['photo_candidates'].append({'url':u,'reason':'Selection image model/color relation not proven'})
   ev['exact_photo_assets']=[x.asset_key for x in doc.photo_candidates]
 if not exact:
  doc.match_level='base_model';doc.evidence='Official model/selection candidate; no exact single-order configuration admitted';return doc,ev
 ev['identity'].update(model='exact_order_model',configuration='exact_part_number',variant='exact_order_variant');ev['returned_sku']=sku
 doc.match_level='full_sku';doc.evidence='Exact commercial SKU in official Product Offer; conditional/family fields withheld'
 tech=b.select_one('.rf-pdp-techspecssection .rc-pdsection-mainpanel');groups=[]
 if tech:
  section=''
  for node in tech.find_all(['h4','p'],recursive=True):
   if node.name=='h4':section=clean_text(node.get_text(' ',strip=True));continue
   value=clean_text(node.get_text(' ',strip=True));
   if value:groups.append((section,value))
 ev['raw_specs']=[dict(section=s,raw_label=s,value=v) for s,v in groups]
 config_sections={'Memory','Storage','Capacity','Finish','Chip'}
 ambiguous={s for s in config_sections if len({v for sec,v in groups if sec==s and re.search(r'\d+\s*(?:GB|TB|core)',v,re.I)})>1}
 # Chip includes CPU, GPU and Neural Engine; multiple fields are not alternatives.
 ambiguous.discard('Chip')
 for sec in {'Memory','Storage','Capacity'}:
  values={v.upper() for section,value in groups if section==sec for v in re.findall(r'\d+\s*(?:GB|TB)',value,re.I)}
  if len(values)>1:ambiguous.add(sec)
 labels={'Chip':'Процессор','Memory':'Оперативная память','Storage':'Объём накопителя','Capacity':'Объём накопителя','Finish':'Цвет','Wireless':'Беспроводная связь','Camera':'Камера','Audio':'Аудио','Charging and Expansion':'Разъёмы','Display':'Экран','Battery and Power':'Питание','Power and Battery':'Питание','Size and Weight':'Габариты и вес'}
 for sec,value in groups:
  reason=''
  if sec in ambiguous:reason='family_configuration_options'
  elif sec=='Chip' and any(len(set(re.findall(r'\d+.core '+kind,value,re.I)))>1 for kind in ('CPU','GPU')):reason='family_configuration_options'
  elif re.search(r'configurable|available|optional|depending|varies|up to.*(?:GB|TB)|or \d+.*core',value,re.I):reason='conditional_or_available_option'
  elif sec not in labels:reason='unsupported_raw_field'
  if reason:ev['configuration_candidates'].append(dict(section=sec,raw_label=sec,value=value,reason=reason));continue
  name=labels[sec]
  if sec=='Chip':
   if re.search(r'\d+-core CPU',value):name='Ядра CPU'
   elif re.search(r'\d+-core GPU',value):name='Ядра GPU'
   elif 'Neural' in value:name='Neural Engine'
   elif 'Apple' not in value:ev['configuration_candidates'].append(dict(section=sec,raw_label=sec,value=value,reason='chip_feature_metadata'));continue
  elif sec in {'Battery and Power','Power and Battery'}:
   if re.search('stream',value,re.I) and re.search('video',value,re.I):name='Время потокового воспроизведения видео'
   elif re.search('video|movie',value,re.I):name='Время воспроизведения видео'
   elif re.search('web',value,re.I):name='Время работы в интернете'
   elif re.search('audio',value,re.I):name='Время воспроизведения аудио'
   elif re.search('watt.hour',value,re.I):name='Энергия аккумулятора, Вт·ч'
   else:ev['configuration_candidates'].append(dict(section=sec,raw_label=sec,value=value,reason='power_metadata'));continue
  elif sec=='Size and Weight':
   found=re.search(r'(Width|Height|Depth|Weight):\s*(.*)',value,re.I)
   if not found:continue
   name={'width':'Ширина товара','height':'Высота товара','depth':'Глубина товара','weight':'Вес товара'}[found[1].lower()];value=found[2]
   metric=re.search(r'([0-9.]+)\s*(cm|mm|kg|grams)',value,re.I)
   if not metric:ev['configuration_candidates'].append(dict(section=sec,raw_label=sec,value=value,reason='metric_dimension_unresolved'));continue
   number=float(metric[1]);unit=metric[2].lower();value=str(number*10 if unit=='cm' else number/1000 if unit=='grams' else number);name+=', кг' if unit in {'kg','grams'} else ', мм'
  elif sec in {'Display','Wireless','Camera','Audio','Charging and Expansion'}:
   # Preserve individual statements without merging different metrics into one fact.
   ev['configuration_candidates'].append(dict(section=sec,raw_label=sec,value=value,reason='model_feature_requires_canonical_mapping'));continue
  doc.attributes.append(RawAttribute(name,value,section=sec,value_cell=True))
 for x in data:
  if x.get('@type')!='ImageGallery' or not official(x.get('url','')):continue
  for im in x.get('associatedMedia',[]):
   u=im.get('contentUrl','');host=urlsplit(u).hostname or ''
   if host.endswith('.cdn-apple.com'):
    colors=('midnight','silver','spaceblack','spacegray','skyblue','blacktitanium','whitetitanium','natural','desert','pink','ultramarine','teal','blue','white','black','rosegold')
    compact=lambda v:re.sub(r'[^a-z]','',v.lower())
    alts=[im.get('alt','') for im in b.select('img[alt]') if urlsplit(im.get('src','')).path==urlsplit(u).path]
    alt=' '.join(dict.fromkeys(alts));ev.setdefault('gallery_audit',[]).append({'url':u,'alt':alt})
    if re.search(r'box|packaging|shipping',alt,re.I):
     ev['photo_candidates'].append({'url':u,'reason':'Packaging image; not product gallery'});continue
    primary_alt=re.sub(r'black display bezel|black bezel|black display', '',alt,flags=re.I)
    alt_colors=[c for c in colors if c in compact(primary_alt)]
    if alt_colors and not all(c in compact(title) for c in alt_colors):
     ev['photo_candidates'].append({'url':u,'reason':'Family/multiple or conflicting exterior colors in image description'});continue
    observed=[c for c in colors if c in compact(urlsplit(u).path)]
    if not observed and not alt_colors:
     ev['photo_candidates'].append({'url':u,'reason':'Image color relation unverified'});continue
    if observed and not all(c in compact(title) for c in observed):
     ev['photo_candidates'].append({'url':u,'reason':'Conflicting gallery color; not confirmed'});continue
    key=hashlib.sha256(u.encode()).hexdigest();doc.photo_candidates.append(PhotoCandidate(u,key));doc.photos.append(u)
 ev['exact_photo_assets']=[x.asset_key for x in doc.photo_candidates]
 ev['configuration_complete']=not ambiguous and any(x.name=='Объём накопителя' for x in doc.attributes)
 return doc,ev

class AppleAdapter:
 def __init__(self,*,fetch_log_path=None,trace_callback=None,clock=time.monotonic):
  self.clock=clock;self.log=Path(fetch_log_path or 'data/apple_fetch.json');self.session=PolicyAwareSession(self.log,allowed_hosts=('apple.com',));self.trace_callback=trace_callback;self.reports={};self.capture_dir=self.log.parent/'apple_captures';self.capture_dir.mkdir(parents=True,exist_ok=True)
 def emit(self,**event):
  if self.trace_callback:self.trace_callback(dict(timestamp=utc_now(),**event))
 def find_source(self,article,*,name='',category='',deadline=None):
  deadline=deadline or self.clock()+45;sku=article.upper();
  if not re.fullmatch(r'[A-Z0-9]{5,8}[A-Z]{2}/A',sku):
   self.reports[sku]={'identity':{'model':'unproven','configuration':'unproven','variant':'unproven'},'manual_status':'Не проверена'};return SourceDocument('apple','Apple','',error='Commercial part number required; hardware/family token is insufficient')
  suffix=sku.split('/')[0][-2:];region={'CL':'ca','ZD':'uk'}.get(suffix,'');regions=list(dict.fromkeys([region,'','uk','ca']));best=SourceDocument('apple','Apple','',error='No exact official order page');queries=[sku,name,f'site:apple.com "{sku}"']
  for region in regions:
   if self.clock()>=deadline:break
   u='https://www.apple.com/'+(region+'/' if region else '')+'shop/product/'+quote(sku.lower(),safe='/')
   z=self.session.get(u,timeout=min(10,max(.1,deadline-self.clock())));accepted=False;ev={}
   if z.ok:
    file=hashlib.sha256(z.url.encode()).hexdigest()+'.html';(self.capture_dir/file).write_text(z.text,encoding='utf-8');(self.capture_dir/(file+'.json')).write_text(json.dumps(dict(url=z.url,status=z.status_code,sha256=hashlib.sha256((self.capture_dir/file).read_bytes()).hexdigest(),query=sku,provider='official_order_http')),encoding='utf-8')
    doc,ev=parse_page(z.text,z.url,sku);accepted=doc.match_level=='full_sku' and not doc.error
    if accepted or (not best.url and doc.match_level=='base_model'):best=doc;self.reports[sku]=ev
   self.emit(event='apple_official',query=sku,provider='official_order_http',url=z.url,region=region or 'us',source_type='order_page',accepted=accepted,reason=best.evidence if accepted else z.marker or f'HTTP {z.status_code}; exact Product SKU absent',identity_relation=ev.get('identity',{}))
   if accepted:break
  if best.match_level!='full_sku' and self.clock()<deadline:
   family=re.search(r'\b(iPhone \d+(?: Pro(?: Max)?| Plus)?|AirPods \d+(?: Pro)?)\b',name,re.I)
   if family:
    slug=family[1].lower().replace(' ','-');kind='iphone' if slug.startswith('iphone') else 'airpods';u=f'https://www.apple.com/shop/buy-{kind}/{slug}'
    z=self.session.get(u,timeout=min(10,max(.1,deadline-self.clock())))
    if z.ok:
     file=hashlib.sha256(z.url.encode()).hexdigest()+'.html';(self.capture_dir/file).write_text(z.text,encoding='utf-8');(self.capture_dir/(file+'.json')).write_text(json.dumps(dict(url=z.url,status=z.status_code,sha256=hashlib.sha256((self.capture_dir/file).read_bytes()).hexdigest(),query=sku,provider='official_family_store')),encoding='utf-8')
     candidate,report=parse_page(z.text,z.url,sku)
     if candidate.match_level in {'full_sku','base_model'}:best=candidate;self.reports[sku]=report
    self.emit(event='apple_family_store',query=name,provider='official_store_http',url=z.url,region='us',source_type='store_selection',accepted=best.match_level=='full_sku',reason='Selection options are not automatically exact configuration',identity_relation=self.reports.get(sku,{}).get('identity',{}))
  if best.match_level!='full_sku' and self.clock()<deadline:
   from .lg_browser_search import LGBrowserSearch
   from ..census.browser_contracts import BrowserBudget
   remaining=max(1,deadline-self.clock());hosts=('www.apple.com','apple.com','support.apple.com');search=LGBrowserSearch(self.log.with_name('apple_browser_search_log.json'),official_host='www.apple.com',official_hosts=hosts,allowed_hosts=hosts+('www.google.com','google.com','gstatic.com'),clock=self.clock,budget=BrowserBudget(deadline_seconds=min(20,remaining),operation_timeout_seconds=min(10,remaining)))
   try:
    q=f'site:apple.com "{sku}"';result=search.search_provider('google',q)
    self.emit(event='apple_external_search',query=q,provider='shared_google',url='',region='global',source_type='search',accepted=False,reason=result.outcome,identity_relation='discovery_only')
    for found in result.candidates[:2]:
     u=found.url
     if not official(u) or self.clock()>=deadline:continue
     z=self.session.get(u,timeout=min(10,max(.1,deadline-self.clock())))
     if not z.ok:continue
     file=hashlib.sha256(z.url.encode()).hexdigest()+'.html';(self.capture_dir/file).write_text(z.text,encoding='utf-8');(self.capture_dir/(file+'.json')).write_text(json.dumps(dict(url=z.url,status=z.status_code,sha256=hashlib.sha256((self.capture_dir/file).read_bytes()).hexdigest(),query=sku,provider='official_family_store')),encoding='utf-8')
     candidate,report=parse_page(z.text,z.url,sku);accepted=candidate.match_level=='full_sku' and not candidate.error
     self.emit(event='apple_external_candidate',query=q,provider='shared_google',url=z.url,region='global',source_type='pdp_or_support',accepted=accepted,reason=candidate.error or candidate.evidence,identity_relation=report.get('identity',{}))
     if accepted:best=candidate;self.reports[sku]=report;break
   finally:search.close()
  if best.match_level!='full_sku' and not self.reports.get(sku,{}).get('selected_configuration') and self.clock()<deadline:
   from ..apple_catalog import lookup
   catalog=lookup(self,sku,deadline)
   if catalog:best,report=catalog;self.reports[sku]=report
  ev=self.reports.setdefault(sku,{});ev['query_variants']=queries
  self.enrich_model(best,ev,sku,deadline)
  return best

 def enrich_model(self,doc,ev,sku,deadline):
  """Order evidence establishes the model; its Tech Specs need not repeat the SKU."""
  from ..apple_identity import identify,MODELS,parse_model,plain
  b=BeautifulSoup(doc.html,'html.parser');matches=[x for x in selection(b).get('products',[]) if x.get('partNumber','').upper()==sku]
  key=identify(doc.found_model) if doc.match_level=='full_sku' else ''
  if matches and len({x.get('familyType') for x in matches})==1:
   family=matches[0].get('familyType','');candidate=identify(re.sub(r'(iphone)(\d+)',r'\1 \2',family,flags=re.I))
   if candidate and all(x.get('dimensionColor') for x in matches):key=candidate
  if not key:return
  ev['model_key']=key;ev['identity']['model']='model_confirmed';ev['model_name']=MODELS[key][0]
  if MODELS[key][2]=='mac':
   doc.attributes=[RawAttribute('Время беспроводной работы в интернете',a.value,section=a.section,value_cell=a.value_cell) if a.name=='Время работы в интернете' else a for a in doc.attributes]
  config={};ev['configuration_fields']=config
  def add(field,label,value,proof):
   config[field]=value;ev.setdefault('configuration_proofs',[]).append(dict(field=field,value=value,url=doc.url,proof=proof))
   if label:doc.attributes=[x for x in doc.attributes if x.name!=label];doc.attributes.append(RawAttribute(label,value,section='Configuration',value_cell=True))
  if matches:
   for field,label,read in [('color','Цвет',lambda x:x.get('dimensionColor','')),('storage','Объём накопителя',lambda x:(re.search(r'(?:^|-)(\d+(?:gb|tb))(?:-|$)',x.get('seoUrlToken',''),re.I) or [None,''])[1])]:
    values={read(x).upper() if field=='storage' else read(x) for x in matches}
    if len(values)==1 and '' not in values:add(field,label,next(iter(values)),'All exact partNumber records agree; no available-option inference')
   if 'color' in config:ev['identity']['variant']='exact_model_color'
   ev['identity']['configuration']='exact_order_record' if 'storage' in config else 'partial_order_record'
   if config.get('storage') and config.get('color'):
    doc.match_level='full_sku';doc.evidence='Exact partNumber selection records agree on model, color and storage; carrier choice remains separate'
    ev['configuration_candidates']=[c for c in ev.get('configuration_candidates',[]) if c['section']!='Configuration']
  if doc.match_level=='full_sku':
   title=doc.found_model;t=plain(title)
   capacity=re.search(r'\b(\d+\s*(?:GB|TB))\b',title,re.I)
   if capacity and MODELS[key][2] in {'iphone','ipad'}:add('storage','Объём накопителя',capacity[1],'Exact single-SKU PDP title')
   for attr in list(doc.attributes):
    if attr.name=='Объём накопителя':config['storage']=attr.value
    if attr.name=='Оперативная память':config['memory']=attr.value
    if attr.name=='Ядра GPU':config['gpu']=attr.value
   colors=['Black Titanium','White Titanium','Space Black','Space Gray','Sky Blue','Rose Gold','Midnight','Silver','Pink','Ultramarine','Teal','Blue','White','Black']
   for c in colors:
    if plain(c) in t:add('color','Цвет',c,'Exact single-SKU PDP title');break
   if t.startswith('refurbished'):add('condition','Состояние товара','Refurbished','Official PDP explicitly says Refurbished')
   if key=='watch10':
    size=re.search(r'\b(42|46)mm\b',t.replace(' mm','mm'))
    if size:add('case_size','Размер корпуса, мм',size[1],'Exact single-SKU PDP title')
    if 'aluminum' in t:config['material']='aluminum'
    elif 'titanium' in t:config['material']='titanium'
    if 'gps + cellular' in t or 'gps+cellular' in t:config['connectivity']='GPS + Cellular'
    elif 'gps' in t:config['connectivity']='GPS'
    # Stage 64 order section mixes both body sizes. Route through scoped model tables.
    doc.attributes=[x for x in doc.attributes if x.section!='Size and Weight']
   if key=='ipada16':
    if 'wi-fi + cellular' in t:config['connectivity']='Wi-Fi + Cellular'
    elif 'wi-fi' in t:config['connectivity']='Wi-Fi'
    doc.attributes=[x for x in doc.attributes if x.section not in {'Size and Weight','Power and Battery'}]
  region=re.search(r'apple.com/(uk|ca)/',doc.url);ev['storefront_region']=region[1] if region else 'us';config['storefront_region']=ev['storefront_region']
  # SKU suffix alone is never evidence of radio/SIM configuration or purchase condition.
  u='https://support.apple.com/en-us/'+MODELS[key][1]
  if self.clock()>=deadline:ev['model_fetch_error']='row_deadline';return
  z=self.session.get(u,timeout=min(10,max(.1,deadline-self.clock())))
  if z.ok:
   file=hashlib.sha256(z.url.encode()).hexdigest()+'.html';(self.capture_dir/file).write_text(z.text,encoding='utf-8')
   model,audit=parse_model(z.text,z.url,key,config);self.model_document=model;ev['model_evidence']=audit
   if not model.error and key=='airpods4anc' and ev.get('catalog_identity'):
    # Catalog does not assert a color. This asset depicts the exact ANC model,
    # not a color-selected family render or a different generation.
    for image in BeautifulSoup(z.text,'html.parser').select('img[src]'):
     asset_url=image.get('src','')
     if official(asset_url) and '121204-airpods-4-anc' in urlsplit(asset_url).path:
      asset_key=hashlib.sha256(asset_url.encode()).hexdigest();model.photo_candidates.append(PhotoCandidate(asset_url,asset_key));model.photos.append(asset_url);ev['exact_photo_assets']=[asset_key];ev['photo_scope']='exact_model; catalog publishes no SKU color field'
   ev['configuration_candidates']=ev.get('configuration_candidates',[])+audit['candidates']
   self.emit(event='apple_model_specs',query=MODELS[key][0],provider='official_support_http',url=z.url,region='us',source_type='model_tech_specs',accepted=not model.error,reason=model.error or model.evidence,identity_relation='exact_model_generation')
  else:ev['model_fetch_error']=z.marker or str(z.status_code)
  ev['configuration_complete']=bool(config.get('storage')) if MODELS[key][2] in {'iphone','ipad','mac'} else bool(config.get('case_size') and config.get('connectivity')) if key=='watch10' else bool(ev.get('catalog_identity')) if key=='airpods4anc' else False
  for candidate in ev.get('photo_candidates',[]):candidate.update(model_relation='exact_model' if key else 'unproven',color_relation='candidate')
  if self.clock()<deadline:self.check_manual(ev,key,deadline)
  from ..photo_metadata import inspect_saved_photo
  for candidate in ev.get('photo_candidates',[]):
   if self.clock()>=deadline:break
   try:
    measured=inspect_saved_photo(candidate['url'],'apple',self.log.with_name('apple_image_fetch.json'))
    candidate.update(width=measured['width'],height=measured['height'],file_size=measured['size_bytes'],format=measured['format'])
   except ValueError as exc:candidate['metadata_error']=str(exc)

 def check_manual(self,ev,key,deadline):
  from ..apple_identity import MODELS,plain
  guide=MODELS[key][3];kind='ios' if guide=='iphone' else 'ipados' if guide=='ipad' else 'watchos' if guide=='watch' else 'web' if guide=='airpods' else 'mac'
  u=f'https://support.apple.com/ru-ru/guide/{guide}/welcome/{kind}'
  z=self.session.get(u,timeout=min(10,max(.1,deadline-self.clock())));report={'type':'User Guide' if guide not in {'macbook-air','macbook-pro'} else 'Getting Started Guide','url':z.url,'verified':False,'language':'Не проверена','model_relation':'unverified','status':z.status_code}
  if z.ok:
   b=BeautifulSoup(z.text,'html.parser');report['title']=clean_text(b.h1.get_text(' ',strip=True)) if b.h1 else '';report['language']='Русский' if (b.html and b.html.get('lang','').startswith('ru') and re.search('[А-Яа-я]{4}',b.get_text())) else 'Не проверена'
   file=hashlib.sha256(z.url.encode()).hexdigest()+'.html';(self.capture_dir/file).write_text(z.text,encoding='utf-8')
   # A model-specific chapter in the official guide is positive model coverage.
   links=[(clean_text(a.get_text(' ',strip=True)),a.get('href','')) for a in b.select('a[href]')]
   wanted=plain(MODELS[key][0]);matches=[(label,url) for label,url in links if plain(label)==wanted and '/guide/' in url]
   if matches and self.clock()<deadline:
    label,url=matches[0];chapter=self.session.get(url,timeout=min(10,max(.1,deadline-self.clock())))
    if chapter.ok:
     cb=BeautifulSoup(chapter.text,'html.parser');text=cb.get_text(' ',strip=True)
     report.update(chapter_url=chapter.url,chapter_title=clean_text(cb.h1.get_text(' ',strip=True)) if cb.h1 else '')
     if plain(report['chapter_title'])==plain(label) and plain(label) in plain(text) and re.search('[А-Яа-я]{4}',text) and cb.html and cb.html.get('lang','').startswith('ru'):
      report.update(verified=True,model_relation='exact_model_chapter',language='Русский')
     file=hashlib.sha256(chapter.url.encode()).hexdigest()+'.html';(self.capture_dir/file).write_text(chapter.text,encoding='utf-8')
  ev['manuals']=[report];ev['manual_status']='Проверена' if report['verified'] else 'Не проверена'
