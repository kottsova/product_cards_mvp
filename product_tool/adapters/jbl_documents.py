"""Content verification for typed JBL guides; no filename-based language proof."""
import re
from .lg_documents import document_languages

def assess_guide(pages,model,kind):
 text=re.sub(r'\s+',' ','\n'.join(pages));language=document_languages(pages)
 normalized=lambda value:re.sub('[^a-z0-9]','',value.lower())
 token=normalized(model).removeprefix('jbl')
 related=bool(token and len(token)>=4 and token in normalized(text))
 if kind=='User Guide':title=bool(re.search(r'user guide|owner.?s manual|руководство пользователя',text,re.I))
 elif kind=='Quick Start Guide':title='quickstartguide' in normalized(text) or bool(re.search(r'краткое руководство',text,re.I))
 else:return {'verified':False,'reason':'not_user_guide_type','language_assessment':language}
 operations=[word for word in ('включ','заряд','подключ','сопряж','воспроизвед','управлен') if re.search(word,text,re.I)]
 # QSG is a distinct short operational document. Existing full-manual language thresholds remain unchanged.
 quick_ru=kind=='Quick Start Guide' and language.get('russian_present') and len(operations)>=2 and bool(re.search(r'(?<![A-Za-z])RU(?![A-Za-z])|русск',text,re.I))
 ru=language.get('russian_instruction') or quick_ru
 return {'verified':bool(related and title and ru),'model_relation_verified':related,'content_title_verified':title,'language_assessment':language,'quick_guide_ru_operations':operations,'acceptance_basis':'typed_short_RU_operations' if quick_ru else 'existing_full_manual_language_assessment','reason':'' if related and title and ru else 'Russian operational guide relation/content not proven'}
