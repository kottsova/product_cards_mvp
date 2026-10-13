"""Qualification-only fault: real persistent Chrome, one synchronous hang.

This is not a production transport or a discovery source. The ordinary public
worker/session is used; only its first goto is deliberately made non-returning.
"""
import os,sys,json,time,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'product_tool/census'))
from product_tool.census.public_browser import PublicBrowserSession
MARKER=Path(os.environ['ELECTROLUX_QUALIFICATION_FAULT_MARKER'])
original=PublicBrowserSession.call
def injected_call(self,command,**args):
 if command=='goto' and not MARKER.exists():
  MARKER.write_text(json.dumps({'origin':'artificial synchronous call after real Chrome context launch','pid':os.getpid(),'url':args['url']}),encoding='utf8')
  while True:time.sleep(60)
 return original(self,command,**args)
PublicBrowserSession.call=injected_call
runpy.run_path(str(ROOT/'product_tool/census/browser_worker.py'),run_name='__main__')
