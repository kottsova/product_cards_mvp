"""Bounded published Support Center navigation; guide titles alone never verify a manual."""
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
from ..hyperx_page import model_matches
from ..census.search_routes import detect_routes
import re,json

GUIDE_TYPES=('User Manual','User Guide','Master Guide','Quick Start Guide','Safety','Warranty')

def article_content(html,url):
    """Only the SSR node whose published article ID equals the current URL."""
    article_id=urlsplit(url).path.rstrip('/').rsplit('/',1)[-1]
    for script in BeautifulSoup(html,'html.parser').select('script'):
        match=re.search(r'window\.__APOLLO_STATE__\s*=\s*',script.get_text())
        if not match:continue
        try:data,_=json.JSONDecoder().raw_decode(script.get_text()[match.end():])
        except ValueError:continue
        for node in data.values():
            if isinstance(node,dict) and node.get('id')==article_id and (node.get('parsedContent') or node.get('content')):
                return node.get('title') or node.get('subject') or '',node.get('parsedContent') or node.get('content')
    return '',''

def category_inventory(html,url):
    """A model category is complete only with explicit count covering its links."""
    soup=BeautifulSoup(html,'html.parser');article_id=urlsplit(url).path.rstrip('/').rsplit('/',1)[-1]
    links={urljoin(url,a['href']):a.get_text(' ',strip=True) for a in soup.select('a[href]') if '/articles/' in a['href'] and urlsplit(urljoin(url,a['href'])).hostname=='supportcenter.hyperx.com'}
    counts=[]
    def walk(node):
        if not isinstance(node,dict):return
        for key,value in node.items():
            if isinstance(value,dict):
                if article_id in key and isinstance(value.get('totalCount'),int):counts.append(value['totalCount'])
                walk(value)
    for script in soup.select('script'):
        match=re.search(r'window\.__APOLLO_STATE__\s*=\s*',script.get_text())
        if not match:continue
        try:data,_=json.JSONDecoder().raw_decode(script.get_text()[match.end():])
        except ValueError:continue
        walk(data)
    return links, bool(counts and max(counts)<=len(links)),counts

CATEGORIES={'Гарнитуры':'Headset','Клавиатуры':'Keyboard','Мыши':'Mouse','Микрофоны':'Microphone','Контроллеры':'Controller'}

def inspect_guides(doc, name, category, fetch):
    checks=[];candidates=[]
    soup=BeautifulSoup(doc.html,'html.parser')
    roots=list(dict.fromkeys(urljoin(doc.url,a['href']) for a in soup.select('a[href]') if urlsplit(urljoin(doc.url,a['href'])).hostname=='supportcenter.hyperx.com'))
    if not roots:return candidates,checks,'PDP does not declare a support route'
    root=roots[0];html=fetch(root)
    checks.append({'url':root,'checked':bool(html),'kind':'support_index'})
    routes=detect_routes(html,root,allowed_hosts=('supportcenter.hyperx.com',))
    route=next((r for r in routes if r.executable),None)
    if route:
        query=name.split('[',1)[0].replace('HyperX ','').strip().removesuffix(' Wired')
        url=route.query_url('"'+query+'"');html=fetch(url)
        checks.append({'url':url,'query':query,'checked':bool(html),'kind':'published_model_search','complete':False,'reason':'first search page; exact typed guides checked, no absence inferred from pagination'})
    else:
        s=BeautifulSoup(html,'html.parser')
        link=next((a for a in s.select('a[href]') if a.get_text(' ',strip=True)==CATEGORIES.get(category)),None)
        if link is None:return candidates,checks,'support category route unavailable'
        url=urljoin(root,link['href']);html=fetch(url)
        checks.append({'url':url,'checked':bool(html),'kind':'support_category','complete':False,'reason':'SSR contains ten popular articles, not full manual inventory'})
    for a in BeautifulSoup(html,'html.parser').select('a[href]'):
        title=a.get_text(' ',strip=True)
        kind=next((k for k in GUIDE_TYPES if k.casefold() in title.casefold()),'')
        if not kind:continue
        model=title.replace(kind,'').strip()
        if not model_matches(name,model):continue
        target=urljoin(url,a['href'])
        if urlsplit(target).hostname!='supportcenter.hyperx.com' or '/articles/' not in urlsplit(target).path:continue
        body=fetch(target)
        node_title,content=article_content(body,target)
        downloads=list(dict.fromkeys(urljoin(target,x['href']) for x in BeautifulSoup(content or body,'html.parser').select('a[href]') if '.pdf' in x['href'].casefold()))
        candidates.append({'title':node_title or title,'type':kind,'url':target,'download_candidates':downloads,'article_content':content,'language':'Не проверен','verified':False,'reason':'typed model guide discovered; content verification follows'})
        checks.append({'url':target,'checked':bool(body),'kind':'guide_article'})
        if len(candidates)>=3:break
    if not candidates and route:
        # Follow a published exact-model Overview breadcrumb to the complete
        # model category; a paginated search miss never means "not found".
        for anchor in BeautifulSoup(html,'html.parser').select('a[href]'):
            title=anchor.get_text(' ',strip=True)
            if not title.endswith('Overview') or not model_matches(name,title.removesuffix('Overview').strip()):continue
            overview=urljoin(url,anchor['href'])
            if urlsplit(overview).hostname!='supportcenter.hyperx.com' or '/articles/' not in overview:continue
            body=fetch(overview)
            for breadcrumb in BeautifulSoup(body,'html.parser').select('a[href]'):
                category_url=urljoin(overview,breadcrumb['href'])
                if '/categories/' not in category_url or urlsplit(category_url).hostname!='supportcenter.hyperx.com' or not model_matches(name,breadcrumb.get_text(' ',strip=True)):continue
                inventory=fetch(category_url);links,complete,counts=category_inventory(inventory,category_url)
                checks.append({'url':category_url,'checked':bool(inventory),'kind':'exact_model_category','complete':complete,'article_count':counts,'published_articles':links})
                if complete and not any(any(t.casefold() in title.casefold() for t in GUIDE_TYPES) for title in links.values()):
                    return candidates,checks,'inventory_complete:no_primary_manual'
                break
            break
    return candidates,checks,'Проверен опубликованный model search; найденные guides требуют проверки содержимого.'

def verify_guides(guides,name,code,download):
    """Use shared content/language assessment for HTML guides and bounded PDFs."""
    import pymupdf
    from .lg_documents import assess_document
    from .common import ProductDocument,clean_text
    model=name.split('[',1)[0].replace('HyperX ','').strip()
    documents=[];technical=[]
    for guide in guides:
        kind=guide['type'];guide['files']=[]
        if kind in {'Safety','Warranty'}:
            guide['reason']='separate safety/warranty document, not a primary manual';continue
        content=BeautifulSoup(guide.get('article_content',''),'html.parser').get_text(' ',strip=True)
        assessment=assess_document([guide['title']+'\n'+content],[model,code]) if content else {}
        # A download link by itself is not an HTML instruction.
        if len(content)>300 and assessment.get('accepted'):
            guide.update(verified=True,format='HTML',assessment=assessment,language=','.join(assessment['languages']['present']),reason='exact model guide title and instructional article content')
            documents.append(ProductDocument(guide['title'],guide['language'],'',str(len(content.encode()))+' B',guide['url'],guide['url'],model,model,guide['url'],primary=kind in {'User Manual','User Guide','Master Guide'}))
        for url in guide['download_candidates'][:2]:
            record={'url':url,'verified':False}
            try:
                data,receipt=download(url);record.update(receipt)
                if not data.startswith(b'%PDF-'):raise ValueError('not a PDF response')
                with pymupdf.open(stream=data,filetype='pdf') as reader:
                    if len(reader)>600:raise ValueError('PDF page budget exceeded')
                    pages=[];characters=0
                    for page in reader:
                        text=page.get_text();characters+=len(text)
                        if characters>2_000_000:raise ValueError('PDF text budget exceeded')
                        pages.append(text)
                assessment=assess_document([clean_text(p) for p in pages],[model,code])
                record.update(assessment=assessment,verified=bool(assessment['accepted']),pages=len(pages))
                if record['verified']:
                    languages=','.join(assessment['languages']['present'])
                    guide.update(verified=True,format='PDF',language=languages,reason='downloaded PDF content confirms model and instructional type')
                    documents.append(ProductDocument(guide['title'],languages,'',str(len(data))+' B',url,guide['url'],model,model,guide['url'],primary=kind in {'User Manual','User Guide','Master Guide'}))
            except Exception as exc:record['error']=str(exc);technical.append({'url':url,'reason':str(exc)})
            guide['files'].append(record)
        guide.pop('article_content',None)
    status='Проверена' if any(g.get('verified') for g in guides) else 'Не проверена'
    return documents,status,technical
