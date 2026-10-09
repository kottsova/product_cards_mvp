"""Razer's bounded technical sections; raw evidence precedes translation."""
import hashlib,json,re
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
from .adapters.common import SourceDocument,RawAttribute,PhotoCandidate,clean_text
from .adapters.structured_page import extract_dom_spec_table,extract_json_ld_product
from .razer_identity import model_relation,configuration_sensitive,components
LABELS={'Sensitivity':'Сенсор и чувствительность','Sensor':'Сенсор','Acceleration':'Скорость и ускорение','Polling Rate':'Частота опроса','Programmable Buttons':'Программируемые кнопки','Switch Type':'Тип переключателей','Scroll Type':'Колесо прокрутки','Cable Type':'Кабель','Other Features':'Дополнительные функции','Design Factor':'Форма корпуса','Connectivity':'Подключение','Battery Life':'Время работы','Battery':'Аккумулятор','Bluetooth':'Bluetooth','Frequency Response':'Частотный диапазон','Impedance':'Сопротивление','Drivers':'Динамики','Driver Size':'Диаметр динамиков','Microphone':'Микрофон','Lighting':'Подсветка','RGB':'Подсветка','Keycaps':'Кейкапы','Wrist Rest':'Подставка для запястий','Operating System':'Операционная система','Ports':'Порты','Wireless':'Беспроводное подключение','Storage':'Память','CPU':'Процессор','GPU':'Видеокарта','RAM':'Оперативная память','Display':'Экран','Color':'Цвет','Layout':'Раскладка','Switches':'Переключатели','Form Factor':'Формат'}
LABELS.update({'7.1 Codec Support (via HDMI)':'Поддержка звука 7.1 через HDMI','AMD Freesync Premium':'AMD FreeSync Premium','Additional Features':'Дополнительные функции','Advanced Optimus':'Advanced Optimus','Anti-Ghosting':'Защита от ложных нажатий','Audio Jack':'Аудиоразъём','Audio Usage':'Режимы использования звука','Cable Routing Options':'Прокладка кабеля','Carrying Case':'Футляр','Communication':'Беспроводное подключение','Dedicated Media Keys':'Мультимедийные клавиши','Dock Compatibility':'Совместимость с док-станцией','Gaming Mode':'Игровой режим','HDMI 2.1 output':'Выход HDMI 2.1','Headphones':'Характеристики наушников','Keyboard - Technology':'Технология клавиатуры','Keyboard Type':'Тип клавиатуры','Mechanical Action Buttons':'Механические кнопки','Mouse Feet':'Ножки мыши','Multi-Function Buttons':'Многофункциональные кнопки','NVIDIA G-Sync™ Enabled':'NVIDIA G-Sync','Neural Processing Units':'Нейропроцессор','On-earcup controls':'Управление на чашках','On-the-fly Macro Recording':'Запись макросов','RGB Backlighting':'Подсветка RGB','Razer Chroma':'Razer Chroma RGB','Security':'Безопасность','Speakers':'Динамики','System Requirement':'Системные требования','THX® Spatial Audio':'THX Spatial Audio','Technology':'Технология','Thermal System':'Система охлаждения','Thumbsticks':'Стики','Touchpad':'Тачпад','Triggers':'Триггеры','UHS-II SD Card Reader':'Кардридер UHS-II SD','USB Cable':'Кабель USB','USB Pass-Through':'Сквозной порт USB','USB-A 3.2 Gen 2':'Порты USB-A 3.2 Gen 2','USB4 Type-C Ports':'Порты USB4 Type-C'})
LABELS.update({'Programmable Controls':'Программируемые кнопки','Fully Programmable Keys':'Программируемые клавиши','Webcam':'Веб-камера','Calman Certified':'Сертификация Calman','On-board Memory Profiles':'Встроенные профили','Maximum Sensitivity (DPI)':'Максимальная чувствительность (DPI)','Max Speed (IPS)':'Максимальная скорость (IPS)','Max Acceleration (G)':'Максимальное ускорение (G)'})
def official(url):
 try:
  p=urlsplit(url);h=p.hostname or '';return p.scheme=='https' and p.port in {None,443} and not p.username and not p.password and any(h==x or h.endswith('.'+x) for x in ('razer.com','razerzone.com'))
 except ValueError:return False
def parse_page(html,url,article,name,category=''):
 soup=BeautifulSoup(html,'html.parser');title=clean_text(soup.title.get_text() if soup.title else '');heading=soup.select_one('h1');ident=model_relation(article,name,clean_text(heading.get_text(' ',strip=True)) if heading else title)
 if not official(url):ident.update(model_confirmed=False,model_relation='unproven',reason='Nonofficial host')
 report={'identity':ident,'raw_specs':[],'accepted_specs':[],'rejected_specs':[],'photos':[],'exact_photo_assets':[],'manuals':[],'verified_documents':[],'manual_status':'Не проверена','source_url':url,'source_type':'support' if 'mysupport.' in url else 'pdp'}
 scope=soup.select_one('#at-a-glance, #tab-technical-specifications, .tech-specs, #tech-specs')
 product=[x for x in extract_json_ld_product(html,url) if x.name in {'sku','mpn','name'}];skus={x.value.upper() for x in product if x.name in {'sku','mpn'}}
 from .razer_identity import key,model_name
 from .adapters.structured_page import _json_ld_blocks,_is_product_block
 single_product=sum(_is_product_block(x) for x in _json_ld_blocks(soup))==1
 product_names={key(x.value) for x in product if x.name=='name'}
 if not ident['model_confirmed'] and single_product and len(skus)==1 and skus=={article.upper()} and product_names=={key(model_name(name))} and components(article)['full_part'] and official(url):
  ident.update(model_confirmed=True,model=model_name(name),model_code=article,model_relation='model_confirmed',reason='Single Product JSON-LD name and exact returned commercial part')
 exact=bool(ident['model_confirmed'] and single_product and components(article)['full_part'] and skus=={article.upper()})
 if exact:ident.update(exact_sku=True,configuration_relation='full_sku')
 doc=SourceDocument('razer_configuration' if exact else 'razer_model','Razer Official',url,found_model=ident['model_code'] or ident['model'],match_level='full_sku' if exact else 'model_confirmed' if ident['model_confirmed'] else 'unknown',evidence=json.dumps(ident,ensure_ascii=False),html=html)
 fields=extract_dom_spec_table(str(scope),url) if scope else []
 conditional_labels=set()
 if scope:
  for row in scope.select('tr'):
   cells=row.find_all(['th','td'],recursive=False)
   if len(cells)>1 and row.select('[data-arr]'):conditional_labels.add(clean_text(cells[0].get_text(' ',strip=True)))
 fields += [x for x in extract_json_ld_product(html,url) if x.name not in {'name','sku','mpn','productID','gtin','gtin8','gtin12','gtin13','gtin14','json_ld_image'}]
 request=ident.get('requested_configuration',{})
 mismatches=[]
 for wanted,value in request.items():
  labels={'color':'color|colour|цвет','layout':'layout|расклад','switch':'switch|переключ','GPU':'gpu|graphics','RAM':'ram|memory','storage':'storage|installed','region':'region|регион'}.get(wanted,re.escape(wanted))
  matches=[x.value for x in fields if re.search(labels,x.name,re.I)]
  if not exact or len(set(matches))!=1 or key(matches[0])!=key(value):mismatches.append(wanted)
 if mismatches:
  ident['configuration_relation']='unproven';ident['configuration_gaps']=mismatches
 for field in fields:
  raw={'section':field.section or 'Technical Specifications','raw_label':field.name,'value':field.value,'extraction_role':field.role};report['raw_specs'].append(raw);reason=''
  if not ident['model_confirmed']:reason='model_not_proven'
  elif field.name.casefold() in {'category','variation','specification','razer synapse support','razer synapse','limited warranty'}:reason='identity_or_software_help'
  elif field.name in conditional_labels:reason='family_options_or_variant_values'
  elif exact and mismatches and configuration_sensitive(field.name,category):reason='configuration_specific'
  elif re.search('ноутбук',category,re.I) and re.search(r'installed|upgradeable|power adapt|in the box|material|size|resolution|refresh|brightness|response|hdr|bezels|calibrated|weight|dimension|keyboard.*switch',field.name,re.I):reason='configuration_specific'
  elif not exact and configuration_sensitive(field.name,category):reason='configuration_specific'
  elif re.search(r'available in|optional|options|depending|varies|black.*white|white.*black|quartz|RTX\s*\d+.*RTX\s*\d+',field.value,re.I):reason='family_options_or_variant_values'
  if reason:report['rejected_specs'].append({**raw,'reason':reason});continue
  label=LABELS.get(field.name,field.name)
  if re.search(r'approx.*dimension|^dimensions$',field.name,re.I):
   axes={k[0].upper():float(v) for k,v in re.findall(r'\b(Length|Width|Height|L|W|H):\s*(?:\d+(?:\.\d+)?\s*(?:in|inches|inch)\s*/\s*)?(\d+(?:\.\d+)?)\s*mm',field.value,re.I)}
   if len(axes)==3:
    for axis,label in (('W','Ширина'),('H','Высота'),('L','Глубина')):doc.attributes.append(RawAttribute(label,f"{axes[axis]:g} mm",'Габариты и вес'))
   else:report['rejected_specs'].append({**raw,'reason':'axis_or_product_context_unproven'});continue
  elif re.search(r'approx.*weight|^weight$',field.name,re.I):
   match=re.search(r'(\d+(?:\.\d+)?)\s*(kg|g)\b',field.value,re.I)
   if match:doc.attributes.append(RawAttribute('Вес',match[0],'Габариты и вес'))
  elif re.search(r'battery life|runtime',field.name,re.I):
   cells=scope.select('td li') if scope else []
   modes=[clean_text(x.get_text(' ',strip=True)) for x in cells if re.search(r'\b(?:hours?|hrs?)\b',x.get_text(),re.I)]
   for value in modes or [field.value]:
    mode=re.search(r'(?:\d[,.]?\d*\s*(?:Hz|GHz)|Bluetooth|RGB.*?(?:on|off)|ANC.*?(?:on|off)|playback|call)',value,re.I)
    doc.attributes.append(RawAttribute('Время работы ('+(mode[0] if mode else 'режим не указан')+')',value,'Автономность'))
  else:doc.attributes.append(RawAttribute(label,field.value,'Основные характеристики'))
  report['accepted_specs'].append(raw)
 # A support model image does not prove color/layout. Keep every image a candidate.
 images=[(urljoin(url,x['src']),False) for x in (scope.select('img[src]') if scope else [])]
 images += [(x.value,True) for x in extract_json_ld_product(html,url) if x.name=='json_ld_image']
 for target,jsonld_bound in dict.fromkeys(images):
  asset=hashlib.sha256(target.encode()).hexdigest()
  if not official(target):continue
  kind='marketing' if re.search('lifestyle|accessor|packag',target,re.I) else 'product_gallery'
  bound=bool(exact and single_product and not mismatches and jsonld_bound and kind=='product_gallery')
  colors=[x.value.casefold() for x in fields if re.fullmatch(r'colou?r',x.name,re.I)]
  if colors and any(c in target.casefold() and c not in colors for c in ('white','black','quartz')):bound=False
  wanted_layout=request.get('layout','').casefold()
  if wanted_layout and any(re.search(r'[/_-]'+c+r'[/_.-]',target,re.I) and c!=wanted_layout for c in ('us','uk','ru')):bound=False
  doc.photo_candidates.append(PhotoCandidate(target,asset,kind));report['photos'].append({'url':target,'asset_key':asset,'role':kind,'verified':bound,'relation':'exact_sku_gallery' if bound else 'model_render_candidate','reason':'Single exact Product image' if bound else 'Color/layout and appearance relation not proven'})
  if bound:report['exact_photo_assets'].append(asset)
 # Only documentation tables inside the article, not global compliance footer.
 article_scope=soup.select_one('.rn_AnswerText') or soup
 for table in article_scope.select('table'):
  if not re.search(r'Documentation\s*Language',table.get_text(' ',strip=True),re.I):continue
  for link in table.select('a[href]'):
   target=urljoin(url,link['href']);text=clean_text(link.get_text(' ',strip=True));kind='Safety' if re.search('safety|regulatory',text,re.I) else 'Quick Start' if re.search('quick',text,re.I) else 'User Guide' if re.search('user|master',text,re.I) else 'Other'
   if official(target) and '.pdf' in target.lower():report['manuals'].append({'url':target,'title':text,'type':kind,'language':'Русский' if re.search('Russian|русск',text,re.I) else 'Другой','relation':'model' if ident['model_confirmed'] else 'unproven','verified':False})
 return doc,report
