"""Verify Russian HTML User Guides by document content and machine-type coverage.

Guide contents are documentation evidence, never configuration specifications.
"""
import re
from io import BytesIO
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

def verify_pdf(data, article, family):
    from pypdf import PdfReader
    from .lg_documents import document_languages
    if not data.startswith(b'%PDF-'):return None
    try:
        reader=PdfReader(BytesIO(data))
        if len(reader.pages)>300:return None
        pages=[page.extract_text() or '' for page in reader.pages]
    except Exception:return None
    text='\n'.join(pages);head=re.sub(r'\s+',' ','\n'.join(pages[:3]))
    if re.search(r'hardware maintenance|руководство по техническому обслуживанию',head,re.I):return None
    language=document_languages(pages)
    normalized=lambda value:re.sub(r'[^a-z0-9]','',value.lower())
    name=normalized(re.sub(r'\bMonitor\b','',family,flags=re.I))
    type_found=bool(re.search(r'(?<![A-Za-z0-9])'+re.escape(article[:4])+r'(?![A-Za-z0-9])',text,re.I))
    family_found=bool(name and len(name)>=6 and name in normalized(head))
    title_found=bool(re.search(r'user guide|руководство пользователя|инструкция по эксплуатации',head,re.I))
    if not (type_found or family_found) or not title_found or not language.get('russian_instruction'):return None
    return {'type':'User Guide','language':'Русский','verified':True,'relation':'family_model','pages':len(pages),
            'language_assessment':language,'family':family,'machine_type_in_document':type_found,'family_in_title':family_found,
            'evidence':'Full PDF text assessed by existing language thresholds and model-family/type binding; no configuration specs imported'}

def verify_sg(payload, article, source_url, guide_type):
    parsed=urlsplit(source_url)
    if parsed.scheme!='https' or parsed.hostname not in {'support.lenovo.com','pcsupport.lenovo.com'} or guide_type!='User Guide':return None
    match=re.search(r'/documentation/(SG\d+)',parsed.path,re.I)
    if not match:return None
    for item in payload.get('data',[]):
        if not isinstance(item,dict) or item.get('docId','').upper()!=match[1].upper():continue
        soup=BeautifulSoup(item.get('body',''),'html.parser')
        html=soup.find('html');meta=soup.find('meta',attrs={'name':'prodname'})
        types=re.findall(r'[A-Z0-9]{4}',meta.get('content','').upper()) if meta else []
        text=soup.get_text(' ',strip=True)
        language=item.get('language','').upper()
        if language=='RU' and html and html.get('lang','').lower()=='ru' and article[:4].upper() in types and len(re.findall('[А-Яа-я]',text))>=40:
            return {'type':'User Guide','language':'Русский','relation':'family_model','verified':True,
                    'machine_types':types,'doc_id':match[1],'evidence':'Russian guide body and prodname machine-type metadata; configuration options in guide are not product facts'}
    return None
