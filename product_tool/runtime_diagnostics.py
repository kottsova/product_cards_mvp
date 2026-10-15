"""Read-only startup fingerprint and append-only ordinary worker diagnostics."""
import hashlib,os,sys,subprocess
from datetime import datetime,timezone
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def runtime_identity():
    root=Path(__file__).resolve().parents[1]
    files={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted((root/'product_tool').rglob('*')) if p.is_file() and p.suffix in {'.py','.html','.js','.css'}}
    try:
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True,timeout=3).strip()
        dirty=bool(subprocess.check_output(['git','status','--porcelain','--','product_tool'],cwd=root,text=True,timeout=3).strip())
    except (OSError,subprocess.SubprocessError):head='unavailable';dirty=None
    return dict(pid=os.getpid(),executable=sys.executable,argv=sys.argv,started_at=datetime.now(timezone.utc).isoformat(),
                commit=head,production_dirty=dirty,source_fingerprint=hashlib.sha256(repr(sorted(files.items())).encode()).hexdigest(),source_files=files)

def record_active(database,product_id,event,**fields):
    from . import storage,discovery_trace
    with storage._connection(database) as c:
        job=c.execute("SELECT id FROM search_jobs WHERE product_id=? AND status='running' ORDER BY rowid DESC LIMIT 1",(product_id,)).fetchone()
    if job:
        discovery_trace.initialize(database)
        discovery_trace.record(database,job['id'],product_id,dict(timestamp=datetime.now(timezone.utc).isoformat(),event=event,**fields))
