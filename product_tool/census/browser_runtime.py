"""Read-only runtime discovery and bounded worker transport. No install/download path."""
from dataclasses import dataclass,asdict
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading

@dataclass(frozen=True)
class BrowserRuntime:
    available:bool
    python:str=''
    runtime_version:str='unavailable'
    browser_version:str='unavailable'
    reason:str=''
    def to_dict(self):return asdict(self)


def discover_runtime():
    root=Path(__file__).resolve().parents[2]
    candidates=[Path(sys.executable),root.parent/'.venv/Scripts/python.exe']
    code="import json,os,importlib.metadata,playwright;from pathlib import Path;from playwright.sync_api import sync_playwright;p=sync_playwright().start();path=p.chromium.executable_path;print(json.dumps({'version':importlib.metadata.version('playwright'),'binary':path,'exists':os.path.isfile(path),'browser_version':next(x['browserVersion'] for x in json.loads((Path(playwright.__file__).parent/'driver/package/browsers.json').read_text())['browsers'] if x['name']=='chromium')}));p.stop()"
    for python in dict.fromkeys(candidates):
        if not python.exists():continue
        try:
            result=subprocess.run([str(python),'-c',code],capture_output=True,text=True,timeout=8)
            if result.returncode:continue
            value=json.loads(result.stdout)
            if value['exists']:
                # Browser version from installed package manifest, checked again at launch.
                package=Path(value['binary']).parents[2]
                return BrowserRuntime(True,str(python),'playwright-'+value['version'],value['browser_version'])
        except (OSError,ValueError,subprocess.TimeoutExpired):continue
    return BrowserRuntime(False,reason='No usable installed Python Playwright and Chromium pair')


class BrowserFailure(Exception):
    def __init__(self,outcome,counts=None):super().__init__(outcome);self.counts=counts or {}


class PlaywrightBrowser:
    def __init__(self,runtime,budget,allowed_hosts):
        self.runtime=runtime;self.budget=budget;self.hosts=allowed_hosts;self.process=None;self.messages=queue.Queue();self.counts={};self.closed=False
    def _reader(self):
        for line in self.process.stdout:
            try:self.messages.put(json.loads(line))
            except ValueError:pass
    def start(self):
        worker=Path(__file__).with_name('browser_worker.py')
        self.process=subprocess.Popen([self.runtime.python,str(worker)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        threading.Thread(target=self._reader,daemon=True).start()
        return self.call('start',policy={**asdict(self.budget),'allowed_hosts':self.hosts})
    def call(self,command,**args):
        if self.closed:raise BrowserFailure('interaction_blocked')
        try:
            self.process.stdin.write(json.dumps({'command':command,**args})+'\n');self.process.stdin.flush()
        except OSError:raise BrowserFailure('browser_javascript_error',self.counts)
        try:message=self.messages.get(timeout=self.budget.operation_timeout_seconds+2)
        except queue.Empty:
            self.process.kill();self.process.wait(timeout=3)
            raise BrowserFailure('browser_javascript_error',self.counts)
        self.counts=message.get('counts',message.get('result',{}).get('counts',self.counts))
        if not message['ok']:raise BrowserFailure(message['error'],self.counts)
        return message['result']
    def close(self):
        if self.closed:return
        try:
            if self.process and self.process.poll() is None:self.call('close')
        except (BrowserFailure,OSError):pass
        finally:
            self.closed=True
            if self.process:
                if self.process.poll() is None:self.process.kill()
                self.process.wait(timeout=3)
                for stream in (self.process.stdin,self.process.stdout):
                    if stream:stream.close()
