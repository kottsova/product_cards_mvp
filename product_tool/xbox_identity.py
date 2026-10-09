"""Typed Xbox identifiers. Public catalogue IDs are not manufacturer parts."""
import re
from urllib.parse import urlsplit,urlunsplit

BRANDS={'xbox','microsoft xbox','microsoft gaming'}
HOSTS=('xbox.com','microsoft.com','xboxservices.com','xboxlive.com','aka.ms')
ROUTES={'series_x':'consoles/xbox-series-x','series_s':'consoles/xbox-series-s','controller':'accessories/controllers/xbox-wireless-controller','elite':'accessories/controllers/elite-wireless-controller-series-2','headset':'accessories/headsets/xbox-wireless-headset'}

def official(url):
    z=urlsplit(url);h=(z.hostname or '').casefold()
    return z.scheme=='https' and not z.username and not z.password and z.port in (None,443) and any(h==a or h.endswith('.'+a) for a in HOSTS)

def official_asset(url):
    z=urlsplit(url)
    return official(url) or (z.scheme=='https' and z.hostname=='img-prod-cms-rt-microsoft-com.akamaized.net' and not z.username and not z.password and z.port in (None,443))

def family(text):
    t=re.sub(r'[-_\s]+',' ',str(text).casefold())
    if 'replacement' in t or 'refurbished' in t or 'series 2 core' in t:return ''
    if 'elite' in t and 'series 2' in t:return 'elite'
    if 'wireless headset' in t:return 'headset'
    if 'wireless controller' in t:return 'controller'
    if re.search(r'\bseries x\b',t):return 'series_x'
    if re.search(r'\bseries s\b',t):return 'series_s'
    return ''

def identifier(article):
    a=article.strip().upper()
    if re.fullmatch(r'[A-Z0-9]{12}(?:/[A-Z0-9]{4})?',a):
        p,*s=a.split('/');return dict(type='store_product_id/store_sku_id' if s else 'store_product_id',product_id=p,sku_id=s[0] if s else '',hardware_model='',part_number='')
    return dict(type='hardware_model_number' if re.fullmatch(r'\d{4}',a) else 'commercial_configuration',product_id='',sku_id='',hardware_model=a if re.fullmatch(r'\d{4}',a) else '',part_number='')

def configuration_sensitive(name):
    return any(t in name.casefold() for t in ('storage','накопител','доступное_пользователю','color','цвет','комплект','bundle','game_pass','игра_в_комплекте','region','регион','sku','part_number','optical','привод','product_dimensions','product_weight','габарит','вес')) and not any(t in name.casefold() for t in ('расширения','внешних_usb','expandable','expansion'))

def product_url(url):
    if not official(url):return False
    h=(urlsplit(url).hostname or '').lower();p=urlsplit(url).path.lower()
    return h in {'www.microsoft.com','www.xbox.com'} and ('/d/' in p or '/p/' in p or '/consoles/' in p or '/accessories/' in p or '/configure/' in p) and not any(x in p for x in ('replacement','refurbished','/b/','all-consoles'))

def search_kind(url):
    return 'product' if product_url(url) else 'support' if official(url) and 'support' in url else 'unknown'

def canonical_product_url(url):
    """Drop PDP tracking/tab/payment alternatives; preserve the published path."""
    p=urlsplit(url)
    if not product_url(url):return ''
    return urlunsplit((p.scheme,p.netloc,p.path.rstrip('/').lower(),'',''))

def hue(text):
    t=str(text).casefold()
    return next((c for c in ('white','black','blue','red','green') if re.search(r'\b'+c+r'\b',t)),'')

def storage_size(text):
    values={int(float(n)*(1000 if u.casefold()=='tb' else 1)) for n,u in re.findall(r'\b(\d+(?:\.\d+)?)\s*(TB|GB)\b',str(text),re.I)}
    return next(iter(values)) if len(values)==1 else None

def retail_request(article,name):
    text=' '.join((article,name)).casefold()
    return dict(storage=storage_size(text),color=hue(text),disc='Digital' if 'digital' in text else 'Disc' if re.search(r'\bdisc\b',text) else '',bundle='bundle' in text)

def retail_specific(name):
    return any(t in name.casefold() for t in ('color','цвет','комплект','bundle','game_pass','игра_в_комплекте','region','регион','sku','part_number'))
