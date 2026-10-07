"""JBL model facts and color/region evidence have separate identity scopes."""
import re
COLORS={'BLK':'Black','WHT':'White','BLU':'Blue','RED':'Red','GRN':'Green','PNK':'Pink','PUR':'Purple','TEAL':'Teal','CAMO':'Camo','SQUAD':'Squad'}
REGIONS={'EU','EP','AM','AS','IN','CN','JP','UK'}
def components(code):
 code=re.sub(r'\s+','',str(code)).upper()
 for color in sorted(COLORS,key=len,reverse=True):
  match=re.fullmatch(r'(.+?)'+color+r'([A-Z]{2})?',code)
  if match and (not match[2] or match[2] in REGIONS):return {'model_code':match[1],'color':COLORS[color],'region':match[2] or '','full_code':code}
 return {'model_code':code,'color':'','region':'','full_code':code}
def model_relation(requested,sku,mpn,pid,*,context,official,single):
 req,actual=components(requested),components(sku)
 consistent=bool(sku and sku==mpn and (not pid or pid==sku))
 exact=official and context and single and consistent and sku==requested
 same=official and context and single and consistent and req['model_code']==actual['model_code']
 return {'model_relation':'exact_model' if same else 'unproven','variant_relation':'exact_sku' if exact else 'same_color_other_region' if same and req['color'] and req['color']==actual['color'] else 'other_color' if same and req['color'] else 'model_only','requested_components':req,'returned_components':actual,'exact_sku':bool(exact),'model_confirmed':bool(same)}
def image_color(url):
 from urllib.parse import unquote
 text=unquote(url).lower()
 return next((v for v in COLORS.values() if re.search(r'(?<![a-z])'+v.lower()+r'(?![a-z])',text)), '')
def variant_field(label):
 return bool(re.search(r'colou?r|farbe|warna|packag|verpack|комплект|упаков|accessor|included|in the box|box contents|\bcable\b|\bkabel\b|power cord|power adapt(?:er|or)',label,re.I))
