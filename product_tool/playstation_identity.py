"""PlayStation evidence scopes. A hardware CFI is not a retail/bundle SKU."""
import re
from urllib.parse import urlsplit

BRANDS = frozenset({'playstation', 'sony interactive entertainment', 'sie', 'sony playstation'})
COLORS={'midnight black':'Чёрный (Midnight Black)','white':'Белый','cosmic red':'Красный (Cosmic Red)','cobalt blue':'Синий (Cobalt Blue)'}
SENSITIVE = frozenset({'storage','color','комплектация','optical_drive','region','revision','width','height','depth','weight','product_weight','product_dimensions'})

def configuration_sensitive(name):
    return (name in SENSITIVE or name in {'объем_накопителя','объём_накопителя','оптический_привод','оперативная_память'}
            or name.startswith(('product_dimensions__','color__','комплектация__','product_weight__')))

def hardware_specific(name):
    return (name in {'product_weight','product_dimensions','width','height','depth','weight','power','maximum_power','питание','максимальная_потребляемая_мощность','разъемы','разъёмы','battery_capacity','емкость_аккумулятора','ёмкость_аккумулятора'}
            or name.startswith(('product_dimensions__','product_weight__')))

def retail_specific(name):
    return name in {'color','комплектация','bundle','region','storefront','packaging'} or name.startswith(('color__','комплектация__'))

def official(url):
    p = urlsplit(url)
    try:
        return p.scheme == 'https' and (p.hostname == 'playstation.com' or bool(p.hostname and p.hostname.endswith('.playstation.com'))) and not p.username and not p.password and p.port in (None,443)
    except ValueError:
        return False

def model_key(title):
    t = re.sub(r'[®™]', '', title).casefold()
    # A compatibility mention of PS5 is not the accessory's product identity.
    if any(x in t for x in ('disc drive for', 'vertical stand', 'console covers', 'charging station', 'pulse explore')): return ''
    if 'dualsense' in t and not any(x in t for x in ('edge','charging station')): return 'dualsense'
    if 'playstation portal' in t: return 'portal'
    if 'pulse elite' in t: return 'elite'
    if 'ps5 pro' in t or 'playstation 5 pro' in t or 'playstation5 pro' in t: return 'pro'
    if 'ps5' in t or re.search(r'playstation\s*5',t): return 'ps5'
    return ''

def codes(label):
    # Combined official labels CFI-2016A/B name two hardware models.
    expanded = re.sub(r'(CFI-\d{4})A/B',r'\1A \1B',label.upper())
    return set(re.findall(r'(?<![A-Z0-9])CFI-[A-Z0-9]+(?:-[A-Z0-9]+)?(?![A-Z0-9])',expanded))

def document_type(label):
    t = label.casefold()
    if 'safety' in t or 'безопасност' in t: return 'Safety Guide'
    if 'quick' in t or 'кратк' in t: return 'Quick Start'
    if 'regulatory' in t or 'declaration' in t: return 'Regulatory'
    if 'instruction' in t or 'эксплуатац' in t: return 'User Guide'
    return 'Support article'

def hardware_family(url):
    path=urlsplit(url).path
    if '/ps5-docs/' in path:
        if re.search(r'/2[01]00(?:ab|a|b)?/',path): return 'ps5_slim'
        if re.search(r'/7[01]00/',path): return 'pro'
        if re.search(r'/1[012]00(?:ab|a|b)?/',path): return 'ps5_original'
    for segment,key in (('dualsense-wireless-controller-cfi-zct1w','dualsense'),('playstation-portal-remote-player','portal'),('pulse-elite-wireless-headset','elite')):
        if segment in path: return key
    return ''
