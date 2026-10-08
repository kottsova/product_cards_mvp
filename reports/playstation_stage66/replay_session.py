"""Offline replay of observed public response bodies, with no SKU URL registry."""
import hashlib,json
from pathlib import Path

class CapturedSession:
    def __init__(self,root):
        self.root=Path(root);self.responses={}
        for filename in ('probe_http.json','playstation_fetch.json'):
            p=self.root/filename
            if p.exists():
                for entry in json.loads(p.read_text(encoding='utf-8')):
                    if entry.get('status_code') is not None:self.responses[entry['url']]=entry
    def get(self,url,**kwargs):
        record=self.responses.get(url,{});final=record.get('final_url') or url
        key=hashlib.sha256(final.encode()).hexdigest()[:20];suffix='.pdf' if final.lower().endswith('.pdf') else '.html'
        path=self.root/'playstation_captures'/(key+suffix)
        if path.exists():
            text=path.read_bytes().decode('latin-1') if suffix=='.pdf' else path.read_text(encoding='utf-8');status=200
        else:text='';status=record.get('status_code',404)
        return type('Response',(),dict(url=final,text=text,status_code=status if path.exists() else 404,truncated=False))()
