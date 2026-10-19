"""Two fictional source APIs. Run on loopback port 8001; no real integrations."""
import hashlib, os, sqlite3
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Query, Response
from pydantic import BaseModel
from typing import Literal
ROOT=Path(__file__).resolve().parents[1]
DB=Path(os.getenv('QAWAFEL_PROVIDER_DB',str(ROOT/'runtime/provider.sqlite3')))
app=FastAPI(title='Fictional accounting & bank source APIs',version='1.2.0')

def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB)
    c.execute('CREATE TABLE IF NOT EXISTS source_state (id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER,profile TEXT,fault TEXT)')
    c.execute("INSERT OR IGNORE INTO source_state VALUES (1,1,'clean','healthy')");c.commit()
    return c

def state():
    with connect() as c:r=c.execute('SELECT revision,profile,fault FROM source_state WHERE id=1').fetchone()
    return dict(revision=r[0],profile=r[1],fault=r[2],simulation=True)

def consent(header):
    if header!='fictional-read-scope':raise HTTPException(403,'Fictional read scope required. This is not OAuth.')

def payload(kind,s):
    if kind=='accounting':return (ROOT/'data'/('invoices_clean.csv' if s['profile']=='clean' else 'invoices_with_issues.csv')).read_bytes()
    return (ROOT/'data/bank_statement.pdf').read_bytes()

@app.get('/health')
def health():return {'status':'ok','simulation':True}

@app.get('/{kind}/v1/manifest')
def manifest(kind:str,x_demo_consent:str=Header(default='')):
    consent(x_demo_consent)
    if kind not in ('accounting','bank'):raise HTTPException(404)
    s=state()
    if s['fault']=='unavailable':raise HTTPException(503,'Simulated provider outage')
    data=payload(kind,s);name='invoices.csv' if kind=='accounting' else 'statement.pdf'
    return {'source':kind,'entity_id':'fictional-cedar-001','period_start':'2025-10-01','period_end':'2026-09-30',
        'revision':s['revision'],'sha256':('0'*64 if s['fault']=='bad_hash' else hashlib.sha256(data).hexdigest()),
        'size':len(data),'path':f'/{kind}/v1/files/{name}?revision={s["revision"]}',
        'mode':'mock_snapshot','profile':s['profile']}

@app.get('/{kind}/v1/files/{name}')
def file(kind:str,name:str,revision:int=Query(...),x_demo_consent:str=Header(default='')):
    consent(x_demo_consent);s=state()
    if (kind,name) not in (('accounting','invoices.csv'),('bank','statement.pdf')):raise HTTPException(404)
    if s['fault']=='unavailable':raise HTTPException(503,'Simulated provider outage')
    if revision!=s['revision']:raise HTTPException(409,'Snapshot changed. Fetch manifests again.')
    return Response(payload(kind,s),media_type='text/csv' if kind=='accounting' else 'application/pdf')

class Scenario(BaseModel):
    profile:Literal['clean','issues']='clean'
    fault:Literal['healthy','unavailable','bad_hash']='healthy'

@app.post('/control/scenario')
def scenario(body:Scenario):
    with connect() as c:c.execute('UPDATE source_state SET revision=revision+1,profile=?,fault=? WHERE id=1',(body.profile,body.fault))
    return state()
