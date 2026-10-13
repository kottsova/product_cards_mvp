"""Native Electrolux Next PDP ownership; no recursive product merging."""
import hashlib,json,re
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
from .adapters.common import SourceDocument,RawAttribute,PhotoCandidate

HOSTS=('electrolux.co.uk','electrolux.ie','electrolux.se','electrolux.de','electrolux.pl')
MEDIA_HOSTS=HOSTS+('electrolux.com','electroluxgroup.eu','electrolux.bynder.com','electrolux-ui.com')
def official(url):
 try:
  p=urlsplit(url);h=p.hostname or ''
  return p.scheme=='https' and p.port in {None,443} and not p.username and not p.password and any(h==x or h.endswith('.'+x) for x in HOSTS)
 except ValueError:return False
def key(s):return re.sub('[^A-Z0-9]','',str(s).upper())
def payload(html):
 s=BeautifulSoup(html,'html.parser');n=s.select_one('script#__NEXT_DATA__[type="application/json"]')
 try:return json.loads(n.string or n.get_text())['props']['pageProps']['pageData'] if n else {}
 except (ValueError,KeyError,TypeError):return {}
def components(node):
 yield node
 for c in node.get('components',[]):yield from components(c)
def catalog_links(html,url,model):
 d=payload(html);out=[]
 for c in components(d):
  props=c.get('props',{});p=props.get('productList',{}).get('settings',{}).get('productData',{})
  for code,item in p.items():
   u=urljoin(url,item.get('pageUrl',''))
   if key(urlsplit(u).path.rstrip('/').rsplit('/',1)[-1])==key(model) and official(u):out.append((u,code,'native official catalog productData'))
 s=BeautifulSoup(html,'html.parser')
 for a in s.select('a[href]'):
  u=urljoin(url,a['href']).split('#')[0]
  if key(urlsplit(u).path.rstrip('/').rsplit('/',1)[-1])==key(model) and official(u):out.append((u,'','published official link'))
 return list(dict.fromkeys(out))

def flight_dicts(html):
 """Decode native Flight JSON records without executing scripts or references."""
 s=BeautifulSoup(html,'html.parser');objects=[]
 def walk(x):
  if isinstance(x,dict):
   objects.append(x)
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 for script in s.select('script'):
  match=re.fullmatch(r'self\.__next_f\.push\((\[.*\])\)',script.get_text(),re.S)
  if not match:continue
  try:
   chunk=json.loads(match[1])
   if len(chunk)==2 and chunk[0]==1 and isinstance(chunk[1],str):
    for line in chunk[1].splitlines():
     if re.match(r'^[0-9a-f]+:',line):
      try:walk(json.loads(line.split(':',1)[1]))
      except ValueError:pass
  except (ValueError,TypeError):continue
 return objects

def inventory(html,url,model,requested_pnc=''):
 """Published modelData owns the complete PNC list, never technical equivalence."""
 out={'url':url,'model':model,'relations':[],'requested_pnc':requested_pnc,'requested_relation':'unproven','technical_equivalence':False}
 if not official(url):return out
 s=BeautifulSoup(html,'html.parser');owners=[x['modelData'] for x in flight_dicts(html) if isinstance(x.get('modelData'),dict)]
 owners=[o for o in owners if o.get('success') is True and key(o.get('data',{}).get('code',''))==key(model)]
 if len(owners)!=1:return out
 codes=owners[0]['data'].get('appliances',[])
 if not isinstance(codes,list) or any(not isinstance(p,str) or not re.fullmatch(r'\d{11}',p) for p in codes):return out
 printed=[b.get('aria-label') for b in s.select('button[role="menuitem"][aria-label]') if re.fullmatch(r'\d{11}',b['aria-label'])]
 if set(printed)!=set(codes):return out
 out['relations']=[{'model':model,'pnc':p,'pnc_base':p[:9],'revision':p[9:],'source_url':url,'scope':'published inventory existence; specs/docs/gallery equivalence unproven'} for p in dict.fromkeys(codes)]
 out['requested_relation']='published_exact_revision' if requested_pnc in codes else 'not_in_published_inventory' if requested_pnc else 'model_inventory_confirmed'
 return out

def revision_owner(html,url,model,pnc):
 """Exact appliance owner is distinct from subordinate spare-part products."""
 out={'url':url,'model':model,'pnc':pnc,'confirmed':False,'technical_equivalence':False,'gallery':[]}
 if not official(url) or not re.fullmatch(r'\d{11}',pnc):return out
 owners=[x['appliance'] for x in flight_dicts(html) if x.get('type')=='productCategorySearchPageWsDTO' and isinstance(x.get('appliance'),dict)]
 if len(owners)!=1:return out
 owner=owners[0]
 if owner.get('code')!=pnc or not any(key(x.get('code',''))==key(model) for x in owner.get('models',[]) if isinstance(x,dict)):return out
 out.update(confirmed=True,pnc_base=pnc[:9],revision=pnc[9:],service_name=owner.get('name',''),relation='native exact appliance owner; no subordinate-part specs/docs accepted')
 image=owner.get('image',{}).get('url','');target=urlsplit(image)
 if target.scheme=='https' and target.port in {None,443} and not target.username and not target.password and any(target.hostname==h or (target.hostname or '').endswith('.'+h) for h in MEDIA_HOSTS):
  out['gallery']=[{'url':image,'asset_key':hashlib.sha256(image.encode()).hexdigest()[:24],'kind':'product_gallery','alt':model+' official exact revision appliance image','product_code':pnc,'color':'','relation_url':url,'relation':'native appliance.image for exact model and 11-digit PNC; finish not inferred'}]
 return out

def media_asset(url):
 """Two published Electrolux display presets for the same UUID/file, no query crop."""
 p=urlsplit(url)
 if p.query or p.fragment or p.scheme!='https' or p.port not in {None,443} or p.username or p.password:return None
 if not any(p.hostname==h or (p.hostname or '').endswith('.'+h) for h in MEDIA_HOSTS):return None
 m=re.search(r'/(?:services/eml/)?transform/(?:WS_PV|WS_PN)/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})/([^/]+)$',p.path,re.I)
 return (m[1].lower(),m[2]) if m else None

LABELS={
 'Washing Capacity (Kg)':'Номинальная загрузка при стирке, кг','Drying Capacity (kg)':'Номинальная загрузка при сушке, кг','Drying Capacity (Kg)':'Номинальная загрузка при сушке, кг','Dryer Type':'Тип сушильной машины','Max Spin Speed (rpm)':'Максимальная скорость отжима, об/мин','Motor Type':'Тип двигателя','Drum Volume (L)':'Объём барабана, л','Program List':'Программы','Functions (Main Oven)':'Режимы нагрева духовки','Push Button Functions':'Функции управления','Connectivity':'Подключение','Cavity Size (L)':'Объём камеры духовки, л','Cleaning':'Очистка духовки','Temperature Range':'Диапазон температуры','Product Type':'Тип устройства','Main Colour':'Цвет / отделка','Included Accessories':'Комплектация','Optional Accessories':'Дополнительные аксессуары (не входят в комплект)','Net weight (kg)':'Вес товара, кг','Gross weight (kg)':'Вес с упаковкой, кг','Voltage (V)':'Напряжение питания, В','Frequency (Hz)':'Частота сети, Гц','Total Electricity Loading (W)':'Мощность подключения, Вт','Plug or Hardwired':'Подключение к электросети','Cord Length (m)':'Длина кабеля, м','Recommended fuse (A)':'Рекомендуемый предохранитель, А','Energy Rating':'Класс энергоэффективности (шкала источника)','Energy Consumption per 100 wash cycles (kWh)':'Энергопотребление на 100 циклов стирки, кВт·ч','Annual Energy Consumption (kWh)':'Годовое энергопотребление, кВт·ч','Noise Rating (dB)':'Класс шума (маркировка источника)','Noise level, dB(A) (EU 2017/1369)':'Уровень шума, дБ(A) (EU 2017/1369)','Noise (dB)':'Уровень шума, дБ','Spin Energy Rating':'Класс эффективности отжима','Condensation Efficiency Rating':'Класс эффективности конденсации','Remaining Moisture (%)':'Остаточная влажность, %','Eco 40-60 Programme Duration (Hours & Minutes)':'Продолжительность Eco 40–60, ч:мин','Water Consumption (L)':'Расход воды, л','Number of place settings':'Количество комплектов посуды','Number of programmes':'Количество программ','Number of cooking zones':'Количество зон нагрева','Hob Energy type':'Тип варочной панели','Control Type':'Тип управления','Cooling Technology':'Технология охлаждения','Climate Class':'Климатический класс','Fridge Capacity (L)':'Объём холодильной камеры, л','Freezer Capacity (L)':'Объём морозильной камеры, л','Total Volume (L)':'Общий объём, л','Main Oven Conventional Mode - Energy consumption per cycle (Kwh)':'Энергопотребление за цикл — обычный нагрев, кВт·ч','Main Oven Fan Mode - Energy consumption per cycle (Kwh)':'Энергопотребление за цикл — нагрев с вентилятором, кВт·ч','Energy efficiency index EEI Main Oven':'Индекс энергоэффективности духовки EEI','Steam Category':'Категория пара','Series':'Серия','Interior Light':'Подсветка','Display':'Дисплей','Bar Code':'EAN','Produktnummer (PNC)':'PNC','Färg':'Цвет / отделка','Ljudnivå, dB(A)':'Уровень шума, дБ(A)','Nettovikt, kg':'Вес товара, кг','Bruttovikt, kg':'Вес с упаковкой, кг','Effekt, W':'Мощность, Вт','Volym dammpåse, liter':'Объём мешка для пыли, л'}
# Without a relation to the requested PNC, only model classification survives.
# Capacity/programs/functions stay on the published product until equivalence is proved.
MODEL_SAFE={'Product Type','Series','Hob Energy type'}
LABELS.update({'Dishwasher Programs':'Программы посудомоечной машины','Number of Place Settings':'Количество комплектов посуды','Number of Programmes':'Количество программ','Number of Temperatures':'Количество температурных режимов','Drying System':'Система сушки','Anti-flood Device Type':'Защита от протечек','Lower Spray Arm Type':'Нижний разбрызгиватель','Upper Spray Arm Type':'Верхний разбрызгиватель','Floor beam':'Индикация на полу','Cutlery Basket':'Корзина для столовых приборов','Cutlery Drawer':'Ящик для столовых приборов','Water Supply':'Подача воды','Depth max (mm)':'Максимальная глубина товара, мм','Inlet Hose Length (cm)':'Длина заливного шланга, см','Outlet Hose Length (cm)':'Длина сливного шланга, см','Inlet Pipe Type':'Тип заливного шланга','Wheels/Feet':'Колёса / опоры','Drawer Compartments':'Отделения дозатора','Drum Material':'Материал барабана','Door Colour':'Цвет дверцы','Energy Rating (Wash&Dry)':'Класс энергоэффективности — стирка и сушка (шкала источника)','Energy Consumption per 100 wash/dry cycles (kWh)':'Энергопотребление на 100 циклов стирки и сушки, кВт·ч','Noise Rating':'Класс шума','Noise level, dB(A) (EU 2017/1369)':'Уровень шума, дБ(A) (EU 2017/1369)','Woolmark':'Woolmark','Chiller Compartment':'Зона охлаждения','Door Hinge Position':'Расположение петель / перенавешивание','Egg Trays':'Лотки для яиц','Freezer - Number Of Drawers':'Ящики морозильной камеры','Freezer - Recommended Temp (°C)':'Рекомендуемая температура морозильной камеры, °C','Freezer Defrost Type':'Размораживание морозильной камеры','Freezer Light Type':'Подсветка морозильной камеры','Freezing Capacity (kg)':'Мощность замораживания (период не указан), кг','Fridge - Number of Shelves':'Полки холодильной камеры','Fridge - Recommended Temp (°C)':'Рекомендуемая температура холодильной камеры, °C','Fridge Defrost Type':'Размораживание холодильной камеры','Fridge Light Type':'Подсветка холодильной камеры','Hatch Doors':'Откидные дверцы','High-Temp Indicator Type':'Индикация повышенной температуры','Holiday Function':'Режим отпуска','Installation':'Тип установки','Minimum Ambient Temperature (°C)':'Минимальная температура окружающей среды, °C','Number of thermostats':'Количество термостатов','Oven Energy Source':'Источник энергии духовки','Oven control type':'Управление духовкой','Max Power Grill - Top Oven (W)':'Максимальная мощность гриля верхней духовки, Вт','Max power oven, W':'Максимальная мощность духовки, Вт','Largest Surface area':'Максимальная площадь поверхности (единица не указана)','N° of cavities':'Количество камер духовки','Main Oven - Shelf Support':'Направляющие основной духовки','Main Oven - Shelves Included':'Решётки в комплекте основной духовки','Main Oven - Trays Included':'Противни в комплекте основной духовки','Cavity coating':'Покрытие камеры духовки','Interior light':'Подсветка камеры','Lamp power (W)':'Мощность лампы, Вт','Timer Type':'Тип таймера','Hob Safety':'Безопасность варочной панели','Frame Type':'Окантовка варочной панели','LED Colour':'Цвет светодиодов','Gas Supply: Natural Gas':'Подключение природного газа','LPG Conversion Kit Included':'Комплект перехода на сжиженный газ','Wok burner':'Горелка Wok','Left Front - Power/Diameter':'Передняя левая зона — мощность / диаметр','Left Rear - Power/Diameter':'Задняя левая зона — мощность / диаметр','Front Middle - Power/Diameter':'Передняя средняя зона — мощность / диаметр','Rear Middle - Power/Diameter':'Задняя средняя зона — мощность / диаметр','Right Front - Power/Diameter':'Передняя правая зона — мощность / диаметр','Right Rear - Power/Diameter':'Задняя правая зона — мощность / диаметр','Autofunktion':'Автоматический режим','Bipackat tillbehör':'Аксессуары в комплекте','Dammpåsar som medföljer':'Мешки для пыли в комплекте','Dammupptagning matta (%)':'Сбор пыли на ковре, %','EAN-kod':'EAN','Elektronisk display':'Электронный дисплей','Familj':'Семейство','Filterindikator':'Индикатор фильтра','Filtreringseffektivitet hela dammsugaren %':'Эффективность фильтрации пылесоса, %','Fjärrkontroll':'Дистанционное управление','Främre hjul':'Переднее колесо','Fullpåse indikator':'Индикатор заполнения мешка','Handtag':'Рукоятка','Hjul/Fötter':'Колёса / опоры','Kombinationsmunstycke':'Комбинированная насадка','Kontroll':'Управление','Ljudeffektnivå, dB':'Уровень звуковой мощности, дБ','Maskintyp':'Тип пылесоса','Mjukstart':'Плавный пуск','Motoreffekt, max (Watt)':'Максимальная мощность двигателя, Вт','Motorfilter':'Фильтр двигателя','Munstycke med LED-belysning':'Насадка со светодиодной подсветкой','Möjlighet att sänka effekten':'Регулировка мощности','Nominell effekt':'Номинальная мощность (единица источником не указана)','Parkeringsläge för röret':'Парковочное положение трубы','Placering tillbehör':'Размещение аксессуаров','Påstyp':'Тип мешка','Påsvolym, liter':'Объём мешка для пыли, л','Räckvidd, m':'Радиус действия, м','Rörsystem':'Труба','Sladdvinda':'Сматывание кабеля','Typ av handtag':'Ручки для переноски','Utblåsfilter':'Выходной фильтр','Vikt, endast maskin kg':'Вес товара, кг','Årlig energiförbrukning, kWh':'Годовое энергопотребление, кВт·ч'})
LABELS.update({'LED Colour':'Цвет подсветки (LED)','Vikt, endast maskin kg':'Вес только устройства, кг'})
def label(raw):return LABELS.get(raw,raw if re.search('[а-яё]',raw,re.I) else 'Характеристика: '+raw)
def mapped(row):
 raw,value=' '.join(row['label'].split()),row['value'];sec=row['section'];out=[]
 if raw=='Produktmått H x B x D, mm':raw='Dimensions (mm) (HxWxD)'
 axes=re.search(r'\((H[xX]W[xX]D|W[xX]D)\)',raw)
 if 'Dimensions' in raw and axes:
  nums=re.findall(r'\d+(?:\.\d+)?',value)
  if len(nums)==len(axes[1].split('x')):
   scope='ниши' if 'Built-in' in raw else 'упаковки' if 'Pack' in raw else 'товара'
   for axis,n in zip(axes[1].split('x'),nums):out.append(RawAttribute({'H':'Высота','W':'Ширина','D':'Глубина'}[axis]+' '+scope+', мм',n+(' (макс.)' if axis=='D' and re.search(r'\(max\)',value,re.I) else ''),{'ниши':'Встраивание','упаковки':'Упаковка','товара':'Габариты товара'}[scope]))
   return out
 if raw in {'Program List','Functions (Main Oven)','Dishwasher Programs'}:sec='Программы'
 elif sec=='Energy' or re.search(r'energy|water consumption|noise|eco.*duration',raw,re.I):sec='Энергия — шкала и период источника'
 elif 'weight' in raw.lower():sec='Упаковка' if 'Gross' in raw else 'Габариты товара'
 else:sec={'Performance':'Основные характеристики','Prestanda':'Основные характеристики','Installation':'Подключение и установка','Other':'Прочие характеристики','Övrigt':'Прочие характеристики','Energi':'Энергия — шкала и период источника'}.get(sec,sec)
 return [RawAttribute(label(raw),value,sec)]

def parse(html,url,model,requested_pnc='',requested_region='',requested_color='',catalog_relations=()):
 ev={'identity':{'model':model,'model_relation':'unproven','requested_pnc':requested_pnc,'requested_region':requested_region},'raw_facts':[],'accepted_facts':[],'rejected_facts':[],'document_inventory':[],'gallery_inventory':[],'manual_status':'Не проверена','verified_documents':[],'model_gallery_assets':[]}
 doc=SourceDocument('electrolux','Electrolux official',url,html=html)
 if not official(url):doc.error='Non-official PDP';return doc,ev
 page=payload(html)
 owners=[c for c in components(page) if c.get('name')=='PDPContainer']
 if len(owners)!=1:doc.evidence='No unique native PDPContainer; catalog/family is discovery only';return doc,ev
 owner=owners[0];top=next((c.get('props',{}) for c in owner.get('components',[]) if c.get('name')=='TopArea'),{})
 found=top.get('modelId','');pnc=key(top.get('productCode',''));region={'electrolux.co.uk':'UK','electrolux.ie':'IE','electrolux.se':'SE','electrolux.de':'DE','electrolux.pl':'PL'}.get((urlsplit(url).hostname or '').removeprefix('www.'),'')
 ev['identity'].update(found_model=found,product_code=pnc,pnc_base=pnc[:9],revision=pnc[9:] if len(pnc)==11 else None,region=region,ean=top.get('ean',''),family=top.get('pageHeading',''),product_code_relation='unproven')
 doc.found_model=found
 if key(found)!=key(model):doc.match_level='mismatch';doc.evidence='PDPContainer model differs';return doc,ev
 if key(owner.get('props',{}).get('productCode',''))!=pnc:doc.match_level='mismatch';doc.error='PDP owner and TopArea PNC disagree';return doc,ev
 ev['identity']['model_relation']='model_confirmed'
 region_ok=not requested_region or requested_region==region
 # Same numeric product is published in the input-region catalog. This proves
 # the cross-region model/base-PNC route, not regional mains or energy claims.
 bridge=[r for r in catalog_relations if not requested_pnc and r.get('model')==model and r.get('product_code')==pnc and r.get('region')==requested_region and official(r.get('source_url','')) and r.get('source_type')=='native_catalog_productData']
 cross_region=not region_ok and bool(bridge)
 exact=(not requested_pnc or key(requested_pnc)==pnc) and (region_ok or cross_region)
 # A 9-digit publication proves base only, never revision 00/01 by padding.
 ev['identity']['product_code_relation']='published_product_confirmed' if exact else 'base_pnc_partial' if key(requested_pnc)[:9]==pnc[:9] and region_ok else 'different_product_or_region'
 ev['identity']['configuration_confirmed']=exact
 if cross_region:
  ev['identity'].update(product_code_relation='same_product_in_requested_region_catalog',region_relation='Cross-region same published PNC; region-sensitive facts remain candidates',catalog_relations=bridge)
 doc.match_level='full_sku' if exact else 'model_confirmed';doc.evidence=json.dumps(ev['identity'],ensure_ascii=False)
 spec=next((c for c in components(owner) if c.get('name')=='FullSpecification'),{})
 color=next((r.get('infoText','') for s in spec.get('props',{}).get('attributes',[]) for r in s.get('items',[]) if r.get('label') in {'Main Colour','Färg'}),'')
 ev['identity']['published_finish']=color
 if requested_color and key(requested_color)!=key(color):
  exact=False;ev['identity']['configuration_confirmed']=False;ev['identity']['product_code_relation']='finish_unproven';doc.match_level='model_confirmed';doc.evidence=json.dumps(ev['identity'],ensure_ascii=False)
 def component_path(node,target,path='$.props.pageProps.pageData'):
  if node is target:return path
  for index,child in enumerate(node.get('components',[])):
   found_path=component_path(child,target,path+f'.components[{index}]')
   if found_path:return found_path
  return ''
 spec_path=component_path(page,spec)
 for section_index,section in enumerate(spec.get('props',{}).get('attributes',[])):
  # Specification prose is marketing/feature inventory, not a technical pair.
  for row_index,row in enumerate(section.get('items',[])):
   raw={'section':section.get('label',''),'label':row.get('label',''),'value':row.get('infoText',''),'scope':'model' if row.get('label') in MODEL_SAFE else 'product_code','product_code':pnc,'region':region,'structured_path':spec_path+f'.props.attributes[{section_index}].items[{row_index}]','parent_context':{'component':'FullSpecification','section_index':section_index,'section_label':section.get('label',''),'section_metadata':{k:v for k,v in section.items() if k!='items'}},'evidence_relation':'model_shared' if row.get('label') in MODEL_SAFE else 'revision_specific' if exact and len(pnc)==11 else 'exact_pnc' if exact else 'unknown'}
   ev['raw_facts'].append(raw)
   if re.search(r'(?:product (?:number|no)|produktnummer).*\(?PNC\)?',raw['label'],re.I) and key(raw['value'])!=pnc:
    ev['rejected_facts'].append({**raw,'reason':'Malformed or contradictory PNC field; not a technical fact'});continue
   if not raw['value'] or raw['section'] in {'Specification','Specifikation','Specifikationer'} or raw['label'].strip().lower() in {'no','yes'}:ev['rejected_facts'].append({**raw,'reason':'Marketing/feature prose or malformed label, not a structured technical pair'});continue
   if cross_region and (raw['section'] in {'Energy','Energi'} or re.search(r'voltage|frequency|plug|hardwired|electricity loading|recommended fuse|energy|water consumption',raw['label'],re.I)):
    ev['rejected_facts'].append({**raw,'reason':'Regional electrical/regulatory evidence not transferred from another region'});continue
   if raw['evidence_relation']=='unknown':ev['rejected_facts'].append({**raw,'reason':'PNC/revision/region relation unproven'});continue
   fields=mapped(raw);doc.attributes.extend(fields);ev['accepted_facts'].append({**raw,'canonical_fields':[f.name for f in fields]})
 for g in top.get('imageGallery',{}).get('galleryItems',[]):
  u=urljoin(url,g.get('imageUrl',''));alt=g.get('altText','');kind='technical_diagram' if re.search('installation|diagram|dimension|drawing',alt,re.I) else 'lifestyle' if re.search('room|environment|lifestyle',alt,re.I) else 'product_gallery'
  asset=hashlib.sha256(u.encode()).hexdigest()[:24];eligible=exact and (not requested_color or key(requested_color)==key(color))
  ev['gallery_inventory'].append({'url':u,'asset_key':asset,'kind':kind,'alt':alt,'color':color,'eligible':eligible,'product_code':pnc,'relation':'published exact-model/product gallery; no unprinted supplier color claim'})
  doc.photo_candidates.append(PhotoCandidate(u,asset,kind=kind));doc.photos.append(u)
 for c in components(owner):
  if c.get('name')!='DocumentsContent':continue
  props=c.get('props',{})
  for bucket in ('document','installation'):
   for item in props.get(bucket,{}).get('documents',[]):
    name=item.get('name','');kind={'user manual':'User Manual','product user manual':'User Manual','produktmanual':'User Manual','installation instructions':'Installation Instructions','installation manual':'Installation Instructions','installationsanvisningar':'Installation Instructions','safety instructions':'Safety','safety information':'Safety','energy label':'Energy Label','energietikett':'Energy Label','product information sheet':'Product Fiche','produktinformationsblad':'Product Fiche','specification sheet':'Specification Sheet','produktinformation':'Specification Sheet','quick guides':'Quick Guide'}.get(name.lower(),'Installation Drawing' if bucket=='installation' else name)
    # DocumentsContent.productCode is often the marketing model; .pnc owns
    # the numeric code. Preserve both rather than treating their names as aliases.
    printed=[key(props.get(k,'')) for k in ('pnc','productCode') if props.get(k)]
    numeric=[v for v in printed if re.fullmatch(r'\d{9}(?:\d{2})?',v)]
    document_code=next(iter(numeric),pnc)
    url_code=re.search(r'/(?:GB|EU)EnergyLabel/(\d{9})/',item.get('url',''))
    relation=exact and not (cross_region and kind in {'Energy Label','Product Fiche'}) and all(v==pnc for v in numeric) and all(v==key(found) for v in printed if v not in numeric) and (not url_code or url_code[1]==pnc[:9])
    ev['document_inventory'].append({'type':kind,'title':name,'url':urljoin(url,item.get('url','')),'model':found,'product_code':document_code,'region':region,'relation_url':url,'identity_verified':relation,'bytes_verified':False,'language':'Не проверен','standard_context':re.search(r'/(GBEnergyLabel|EUEnergyLabel)/',item.get('url','')).group(1) if re.search(r'/(GBEnergyLabel|EUEnergyLabel)/',item.get('url','')) else 'Unspecified; no old/new scale inference','date':item.get('approvalDate','')})
 desc=owner.get('props',{}).get('productDescription',{}).get('description','')
 collisions={}
 for index,row in enumerate(ev['raw_facts']):
  if row['section'] not in {'Specification','Specifikation','Specifikationer'}:
   collisions.setdefault((row['section'],row['label']),[]).append({**row,'row_index':index,'source_url':url})
 ev['source_field_collisions']=[{'classification':'same_owner_duplicate_label_different_values','model':found,'product_code':pnc,'revision':ev['identity']['revision'],'section':sec,'label':name,'rows':rows,'resolution':'Retained; no union, renaming, first-value selection or revision inference'} for (sec,name),rows in collisions.items() if len({r['value'] for r in rows})>1]
 doc.description=desc # Only native ProductDescription; never SupportModule/reviews/FAQ.
 return doc,ev

def evidence_graph(ev,pdp_url):
 """Typed relations are per evidence item; existence is not equivalence."""
 i=ev['identity'];model=i.get('found_model',i['model']);requested=i.get('requested_pnc','')
 edges=[{'from':model,'to':i.get('product_code',''),'relation':'exact_pnc' if i.get('model_relation')=='model_confirmed' else 'unknown','evidence_type':'identity','source_url':pdp_url}]
 for item in ev.get('pnc_inventory',{}).get('relations',[]):
  edges.append({'from':model,'to':item['pnc'],'relation':'exact_pnc','evidence_type':'inventory','source_url':item['source_url']})
 revision=ev.get('requested_revision',{})
 if revision.get('confirmed'):
  edges.append({'from':model,'to':requested,'relation':'revision_specific','evidence_type':'identity','source_url':revision['url']})
  edges.append({'from':requested,'to':pdp_url,'relation':'unknown','evidence_type':'specifications/documents','source_url':revision['url'],'reason':'Native appliance owner prints model code but no explicit relation to this PDP technical payload'})
 for row in ev.get('raw_facts',[]):
  edges.append({'from':pdp_url,'to':row['structured_path'],'relation':row['evidence_relation'],'evidence_type':'specification','label':row['label'],'product_code':row['product_code']})
 for item in ev.get('gallery_inventory',[]):
  edges.append({'from':requested or i.get('product_code',''),'to':item['url'],'relation':'revision_specific' if item.get('revision_owner_image') or requested and item.get('product_code')==requested and revision.get('confirmed') else 'exact_pnc' if item['eligible'] else 'unknown','evidence_type':'photo','source_url':item.get('relation_url',pdp_url)})
 for item in ev.get('document_inventory',[]):
  edges.append({'from':requested or i.get('product_code',''),'to':item['url'],'relation':'revision_specific' if item['identity_verified'] and len(item['product_code'])==11 else 'exact_pnc' if item['identity_verified'] else 'unknown','evidence_type':item['type'],'source_url':item['relation_url']})
 return {'nodes':{'model':model,'published_pnc':i.get('product_code'),'requested_pnc':requested,'pdp':pdp_url},'edges':edges,'types':['exact_pnc','model_shared','revision_specific','unknown']}
