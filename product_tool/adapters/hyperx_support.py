"""Bounded published Support Center navigation; guide titles alone never verify a manual."""
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
from ..hyperx_page import model_matches

CATEGORIES={'Гарнитуры':'Headset','Клавиатуры':'Keyboard','Мыши':'Mouse','Микрофоны':'Microphone','Контроллеры':'Controller'}

def inspect_guides(doc, name, category, fetch):
    checks=[];candidates=[]
    soup=BeautifulSoup(doc.html,'html.parser')
    roots=list(dict.fromkeys(urljoin(doc.url,a['href']) for a in soup.select('a[href]') if urlsplit(urljoin(doc.url,a['href'])).hostname=='supportcenter.hyperx.com'))
    if not roots:return candidates,checks,'PDP does not declare a support route'
    root=roots[0];html=fetch(root)
    checks.append({'url':root,'checked':bool(html),'kind':'support_index'})
    s=BeautifulSoup(html,'html.parser')
    link=next((a for a in s.select('a[href]') if a.get_text(' ',strip=True)==CATEGORIES.get(category)),None)
    if link is None:return candidates,checks,'support category route unavailable'
    url=urljoin(root,link['href']);html=fetch(url)
    checks.append({'url':url,'checked':bool(html),'kind':'support_category','complete':False,'reason':'SSR contains ten popular articles, not the full model manual list'})
    for a in BeautifulSoup(html,'html.parser').select('a[href]'):
        title=a.get_text(' ',strip=True)
        kind=next((k for k in ('User Guide','Master Guide','Quick Start Guide','Safety','Warranty') if k.casefold() in title.casefold()),'')
        if not kind:continue
        model=title.replace(kind,'').strip()
        if not model_matches(name,model):continue
        target=urljoin(url,a['href'])
        if urlsplit(target).hostname!='supportcenter.hyperx.com':continue
        body=fetch(target)
        downloads=[urljoin(target,x['href']) for x in BeautifulSoup(body,'html.parser').select('a[href]') if '.pdf' in x['href'].casefold()]
        candidates.append({'title':title,'type':kind,'url':target,'download_candidates':downloads,'language':'Не проверен','verified':False,'reason':'guide article found; downloadable content/model/language not verified'})
        checks.append({'url':target,'checked':bool(body),'kind':'guide_article'})
        if len(candidates)>=2:break
    return candidates,checks,'Проверены опубликованные разделы поддержки. Полный список руководств и русский язык документов пока не проверены.'
