from pathlib import Path
from sqlite3 import connect
from hashlib import sha256
src=Path('data/batches.sqlite3'); dst=Path('reports/lg_live_batch_2026-09-29_stage49/batches_before_stage49.sqlite3')
if dst.exists():
 print('backup already exists',sha256(dst.read_bytes()).hexdigest())
else:
 with connect(src) as a, connect(dst) as b: a.backup(b)
 print('backup created',sha256(dst.read_bytes()).hexdigest())
print('source',sha256(src.read_bytes()).hexdigest())
