"""Restore previously verified public PDF proofs without changing review decisions."""
from pathlib import Path
from urllib.parse import urlsplit
import argparse,hashlib,json,requests
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession
from product_tool.adapters.lenovo_documents import verify_pdf
parser=argparse.ArgumentParser();parser.add_argument('--captures',type=Path,required=True);args=parser.parse_args()
reviews=json.loads((args.captures/'manual_reviews.json').read_text(encoding='utf-8'))
session=PolicyAwareSession(args.captures/'restore_fetch_log.json',allowed_hosts=('download.lenovo.com',),underlying=BinarySafeSession(requests.Session()),max_bytes=50000000)
for article,review in reviews.items():
 for doc in review.get('documents',[]):
  if doc.get('format')!='pdf' or not doc.get('verified'):continue
  name=doc['proof_file'];expected=doc['proof_sha256'];url=doc['url'];parsed=urlsplit(url)
  if Path(name).name!=name or parsed.scheme!='https' or parsed.hostname!='download.lenovo.com':raise SystemExit('Invalid proof reference')
  path=args.captures/name
  if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==expected:continue
  response=session.get(url,timeout=30)
  if not response.ok or response.truncated:raise SystemExit('Technical blocker: incomplete official PDF response')
  raw=response.text.encode('latin-1')
  if hashlib.sha256(raw).hexdigest()!=expected or not verify_pdf(raw,article,doc['family']):raise SystemExit('Official PDF changed: new content requires a fresh review')
  path.write_bytes(raw);print('Restored verified public proof',article,name)
