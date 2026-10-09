"""Public Xbox Support content contract and typed document inspection."""
import hashlib,json,re
from io import BytesIO
from urllib.parse import urljoin,urlencode,unquote
from bs4 import BeautifulSoup
from pypdf import PdfReader
from .adapters.lg_documents import document_bytes
from .adapters.common import clean_text
from .xbox_identity import official

def document_role(text):
    # First-page role, never a mention of a user guide in legal/support prose.
    cover=clean_text(text[:2500])
    if re.search(r'safety|regulatory|product guide|product and regulatory|безопасност|нормативн',cover,re.I):return 'Safety/Regulatory'
    if re.search(r'^(?:Xbox\s+.*?\s+)?(?:User Guide|Руководство пользователя)\b',cover,re.I):return 'User Guide'
    if re.search(r'quick start|setup guide|краткое руководство',cover,re.I):return 'Setup Guide'
    return 'Unclassified document'

def support_documents(a,shell,article,expected,deadline):
    result=dict(manuals=[],manual_status='Не проверена',manual_search_complete=False)
    if not shell:return result
    script=next((urljoin(shell.url,n['src']) for n in BeautifulSoup(shell.text,'html.parser').select('script[src]') if '/assets/index-' in n['src']),None)
    if not script or not official(script):return result
    js=a.fetch(script,article,'xbox_support','catalog',deadline)
    # Validate the public declaration before building the GET contract.
    if not js or not all(t in js.text for t in ('https://content.support.xboxlive.com/content','VITE_CMS_CONTENT_PATH:"/SXC"','?path=${O.id}&language=${D.targetLanguage}&market=${D.country}','method:a.HttpMethod.Get')):return result
    api='https://content.support.xboxlive.com/content?'+urlencode({'path':'/SXC/hardware-network/console/manuals-specs','language':'ru-RU','market':'RU'})
    response=a.fetch(api,article,'xbox_support_content','api',deadline)
    if not response:return result
    try:data=json.loads(response.text)
    except ValueError:return result
    def sections(node):
        if isinstance(node,dict):
            if 'Heading' in node and isinstance(node.get('SectionItems'),list):yield node
            for value in node.values():yield from sections(value)
        elif isinstance(node,list):
            for item in node:yield from sections(item)
    rows=[]
    for section in sections(data.get('ContentList',[])):
        heading=section.get('Heading','');lower=heading.lower();key=str(section.get('#Name','')).lower()
        match='series-xs' in key if expected in {'series_x','series_s'} else 'elite' in key if expected=='elite' else key=='xbox accessories' if expected in {'controller','headset'} else False
        if not match:continue
        for item in section['SectionItems']:
            u=item.get('Url','');title=item.get('Name','')
            if item.get('#Type')=='Link' and official(u) and '.pdf' in u.lower():
                rows.append(dict(type='Unclassified document',title=title,url=u,language='Не проверена',verified=False,relation='official_family_manual_index',source_url=shell.url,api_url=response.url,section=heading))
    unique=list({m['url']:m for m in rows}.values());result['manuals']=unique
    russian=[m for m in unique if re.search(r'Russian|Русск|Россия',m['title'],re.I) or re.search(r'\bRU\b',unquote(m['url']))]
    for m in russian[:1]:
        z=a.fetch(m['url'],article,'official_document','manual',deadline)
        if not z:continue
        try:
            raw=document_bytes(z)
            if not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-2048:]:raise ValueError('Incomplete PDF')
            pdf=PdfReader(BytesIO(raw));pages=[p.extract_text() or '' for p in pdf.pages];text='\n'.join(pages)
            russian_content=len(re.findall(r'[А-Яа-яЁё]',text))>300
            role=document_role(pages[0])
            # Multilingual first pages may be English Safety followed by RU safety.
            if role=='Unclassified document' and re.search('безопасност|regulatory|safety',text,re.I):role='Safety/Regulatory'
            m.update(type=role,language='Русский' if russian_content else 'Не проверена',verified=russian_content,sha256=hashlib.sha256(raw).hexdigest(),pages=len(pages),cover_text=clean_text(pages[0])[:500])
        except Exception as e:m['error']=str(e)
    # A checked index alone is not a completed User Guide search; inspect its RU file.
    checked=[m for m in russian if m['verified']]
    if checked:
        result['manual_search_complete']=len(checked)==len(russian)
        if any(m['type']=='User Guide' for m in checked):result['manual_status']='Проверена'
        elif result['manual_search_complete']:result['manual_status']='Проверена, не найдена'
    result['manual_search_reason']='Official family manual index; available Russian document role checked; User Guide evaluated separately from Safety/Regulatory'
    return result
