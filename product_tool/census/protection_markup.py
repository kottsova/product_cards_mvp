"""Distinguish access gates from CAPTCHA attached to optional site forms."""
import re
from bs4 import BeautifulSoup

def access_widgets(html):
    if isinstance(html,str) and not re.search(r'g-recaptcha|h-captcha|cf-chl-widget|challenge-form|captcha-container|iframe[^>]+(?:captcha|challenge)',html,re.I):
        return False
    soup=BeautifulSoup(html,'html.parser') if isinstance(html,str) else html
    for widget in soup.select('iframe[src*="captcha"],iframe[src*="challenge"],.g-recaptcha,.h-captcha,.cf-chl-widget,#challenge-form,.captcha-container'):
        if widget.get('id')=='challenge-form' or widget.find_parent(id='challenge-form'):
            return True
        # Optional form controls are not a document access gate. Require both
        # an enclosing form and explicit comment/review/feedback semantics.
        form=widget.find_parent('form')
        if form and re.search(r'challenge|verify|human|security',str(form.attrs),re.I):
            return True
        ancestors=[widget,form,form.parent if form else None,form.parent.parent if form and form.parent else None]
        context=' '.join(str(x.get('id',''))+' '+' '.join(x.get('class',[])) for x in ancestors if getattr(x,'attrs',None) and x.name not in {'html','body'})
        optional=form is not None and re.search(r'comment|review|feedback|newsletter|contact',context,re.I)
        if not optional:return True
    return False
