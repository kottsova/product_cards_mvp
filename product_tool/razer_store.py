"""Literal SSR retail nodes; no SKU suffix decoding or selected-default guesses."""
import json,re
from urllib.parse import urlsplit,urljoin
from bs4 import BeautifulSoup
from .razer_identity import model_relation,model_name,key,requested_configuration,components
from .adapters.structured_page import ExtractedField,CONFIRMED
from .adapters.common import clean_text

def region_of(url):
 locale=urlsplit(url).path.split('/')[1]
 m=re.fullmatch(r'([a-z]{2})-([a-z]{2})',locale)
 return m[2]+'-'+m[1].upper() if m else 'en-US' if locale.startswith('gaming-') else ''

def option_equal(label,wanted,actual):
 if key(wanted)==key(actual):return True
 # These are words in explicitly labelled options, never part-number digits.
 if label=='switch' and wanted.casefold() in {'orange','yellow','green','linear','clicky'}:
  return bool(re.search(r'\b'+re.escape(wanted)+r'\b',actual,re.I)) and not re.search(r'\bor\b|/',actual,re.I)
 if label=='layout':return key(actual) in {key(wanted)+'layout',key(wanted)+'keyboardlayout'}
 if label=='GPU':return bool(re.fullmatch(r'(?:GeForce\s+)?'+re.escape(wanted)+r'(?:\s*\([^)]*\))?',actual,re.I))
 if label=='storage':return key(actual)==key(wanted)+'ssd'
 return False

def extract_store(soup,url,article,name,model_evidence=None):
 result={'fields':[],'rejected':[],'relations':[],'images':[],'model_confirmed':False,'configuration_confirmed':False,'selected_codes':[]}
 script=soup.select_one('script#ng-state[type="application/json"]')
 if script is None:return result
 try:state=json.loads(script.string or script.get_text())
 except (ValueError,TypeError):return result
 marketing=state.get('razerProductMarketingData',{})
 nodes=marketing.get('variants',[]) if isinstance(marketing,dict) else []
 # Product-page state has exact entities; only its declared product collection.
 entities=state.get('cx-state',{}).get('products',{}).get('entities',{})
 if isinstance(entities,dict):
  for entity in entities.values():
   if isinstance(entity,dict):
    value=entity.get('details',{}).get('value',{})
    if isinstance(value,dict) and value.get('code'):nodes.append(value)
 wanted=requested_configuration(name);matching=[];seen=set()
 for node in nodes:
  if not isinstance(node,dict):continue
  code=str(node.get('code',''));base=str(node.get('baseProductName',''))
  relation=model_relation(article,name,base+' | '+code)
  if not relation['model_confirmed'] and model_evidence and model_evidence.get('model_confirmed'):
   plain=re.sub(r'\s*\(\d{4}\)\s*$','',model_name(name))
   hardware=model_relation(article,plain,base+' | '+code)
   if hardware['model_confirmed'] and model_evidence.get('model_code','').upper().rstrip('X').startswith(article.upper()):
    relation={**hardware,'reason':'Official Support confirms generation; SSR binds the same printed hardware code to this retail node'}
  options={};features={}
  for group in node.get('variantOptions',[]):
   for q in group.get('variantOptionQualifiers',[]):
    label=str(q.get('qualifier','')).casefold();aliases={'colour':'color','keyboardlayout':'layout','keyboard-layout':'layout','switchtype':'switch','switch-type':'switch'};label=aliases.get(label,label)
    if label in {'color','layout','switch','model','GPU','RAM','storage'}:options[label]=str(q.get('value',''))
  for group in node.get('classifications',[]):
   for feature in group.get('features',[]):
    label=str(feature.get('name',''));values=[clean_text(BeautifulSoup(str(v.get('value','')),'html.parser').get_text(' ',strip=True)) for v in feature.get('featureValues',[])]
    if label and values:features[label]='; '.join(values)
    # Explicit layout/switch labels are also published in classifications.
    if re.fullmatch(r'(?:Keyboard )?Layout',label,re.I):options['layout']='; '.join(values)
    if re.fullmatch(r'Colou?r(?: / Design)?',label,re.I):options['color']='; '.join(values)
    if re.fullmatch(r'(?:Keyboard )?Switch Type',label,re.I):options['switch']='; '.join(values)
  # Qualifier schema suffixes are not a device generation/year.
  laptop_aliases={'color':'color','graphic':'GPU','memory':'RAM','storage':'storage','keyboard-layout':'layout'}
  for group in node.get('variantOptions',[]):
   for q in group.get('variantOptionQualifiers',[]):
    match=re.fullmatch(r'laptop-(.+)-\d{4}',str(q.get('qualifier','')))
    if match and match[1] in laptop_aliases:options[laptop_aliases[match[1]]]=str(q.get('value',''))
  # Only an explicit pre-loaded/default switch declaration qualifies an
  # assembled node. Sound-test alternatives and barebones stay candidates.
  if options.get('switch') and 'orange' not in options['switch'].casefold():
   for heading in soup.select('h2,h3,h4'):
    text=clean_text(heading.get_text(' ',strip=True));following=heading.find_next_sibling()
    if re.search(r'Razer.*Orange.*Mechanical Switch',text,re.I) and following and re.search(r'Pre.Loaded',following.get_text(' ',strip=True),re.I):
     if any(q.get('value')=='Fully assembled' for g in node.get('variantOptions',[]) for q in g.get('variantOptionQualifiers',[])) and re.search('tactile',options['switch'],re.I):options['switch']=text
  options['region']=region_of(url)
  accepted=relation['model_confirmed']
  config=accepted and all(option_equal(k,v,options.get(k,'')) for k,v in wanted.items())
  if components(article)['full_part']:config=config and code.upper()==article.upper()
  result['relations'].append({'model':base,'hardware_code':relation['model_code'],'retail_sku':code,'retail_url':urljoin(url,node.get('url','')),'source_url':url,'options':options,'model_confirmed':accepted,'requested_configuration_matches':config,'reason':relation['reason']})
  if not accepted or code in seen:continue
  seen.add(code);matching.append((node,options,features,config));result['model_confirmed']=True
 selected=[n for n in matching if n[3]] if wanted or components(article)['full_part'] else matching
 result['configuration_confirmed']=bool(selected and (wanted or components(article)['full_part']))
 result['selected_codes']=[n[0]['code'] for n in selected]
 # Equal values on all applicable model nodes are model-level evidence.
 # A differing/missing value stays a candidate. Never take the first variant.
 pool=selected or matching
 labels=set().union(*(n[2] for n in pool)) if pool else set()
 for label in sorted(labels):
  values={n[2].get(label,'') for n in pool}
  if len(values)==1 and '' not in values:
   value=next(iter(values));result['fields'].append(ExtractedField(label,value,url,'ng-state retail classifications; codes='+','.join(n[0]['code'] for n in pool),'embedded_json',CONFIRMED))
  else:result['rejected'].append({'section':'Store SSR','raw_label':label,'value':' | '.join(sorted(values)),'extraction_role':'embedded_json','reason':'retail_variants_differ_or_missing'})
 for node,options,features,config in matching:
  for image in node.get('images',[]):
   if image.get('format')!='product' or image.get('imageType') not in {'PRIMARY','GALLERY'}:continue
   target=urljoin(url,image.get('url',''))
   requested_photo={k:v for k,v in wanted.items() if k in {'color','layout','switch'}}
   bound=all(option_equal(k,v,options.get(k,'')) for k,v in requested_photo.items())
   if code.startswith('RZ03-') and not options.get('layout'):bound=False
   result['images'].append({'url':target,'verified':bound,'relation':'retail_node_color_layout','retail_sku':node['code'],'options':options,'role':'product_gallery'})
 return result
