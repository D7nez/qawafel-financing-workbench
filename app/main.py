from __future__ import annotations
import asyncio, io, json, os, sqlite3, threading, uuid
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app.analysis import DataError, VERSION, analyze, digest, read_bank, read_invoices
from app.bank import reconcile_status, simulate_status_errors
ROOT=Path(__file__).resolve().parents[1]
DB=Path(os.getenv('QAWAFEL_DB',str(ROOT/'runtime'/'analyses.sqlite3')))
LOCK=threading.Lock()
@asynccontextmanager
async def lifespan(app):
    scheduler=asyncio.create_task(sync_service.loop())
    try:yield
    finally:
        scheduler.cancel()
        with suppress(asyncio.CancelledError):await scheduler

app=FastAPI(lifespan=lifespan,title='Qawafel | Financing Evidence Workbench',version=VERSION,description='Local synthetic-data prototype. No real lending decisions or bank submission.')
app.mount('/static',StaticFiles(directory=ROOT/'app'/'static'),name='static')

def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB)
    c.execute('CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
    return c

@app.middleware('http')
async def safety_headers(request:Request,call_next):
    if request.method=='POST':
        raw=request.headers.get('content-length')
        if not raw or not raw.isdigit(): return Response('Content-Length required for local demo',status_code=411)
        if int(raw)>12_000_000:return Response('Request exceeds 12 MB',status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'" if not request.url.path.startswith('/docs') else "default-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com"
    return response

@app.get('/',include_in_schema=False)
def home():return FileResponse(ROOT/'app'/'static'/'index.html')

@app.get('/api/health')
def health():return {'status':'ok','version':VERSION,'mode':'local-synthetic-only'}

def run_analysis(ib,filename,bb):
    if not filename.lower().endswith(('.xlsx','.csv')):
        raise HTTPException(422,'Invoice file must be .xlsx or .csv.')
    if not bb.startswith(b'%PDF-'):
        raise HTTPException(422,'Bank statement must be a valid text PDF.')
    fingerprint=digest((VERSION+'|2026-09-30|'+digest(ib)+'|'+digest(bb)).encode())
    with LOCK:
        with connect() as c:
            existing=c.execute('SELECT payload FROM analyses WHERE fingerprint=?',(fingerprint,)).fetchone()
        if existing:
            result=json.loads(existing[0]);result['cached']=True;return result
        try:
            raw=read_invoices(ib,filename);txs,statements=read_bank(bb)
            result=analyze(raw,txs,statements,[{'name':'invoices','sha256':digest(ib)},{'name':'bank_statement','sha256':digest(bb)}])
        except DataError as e:raise HTTPException(422,str(e))
        result.update(id=str(uuid.uuid4()),created_at=datetime.now(timezone.utc).isoformat(),cached=False)
        with connect() as c:
            c.execute('INSERT OR IGNORE INTO analyses VALUES (?,?,?,?)',(result['id'],fingerprint,result['created_at'],json.dumps(result)))
            canonical=c.execute('SELECT payload FROM analyses WHERE fingerprint=?',(fingerprint,)).fetchone()
        stored=json.loads(canonical[0])
        stored['cached']=stored['id']!=result['id']
        return stored

@app.post('/api/demo/{profile}')
def demo(profile:str):
    if profile not in ('clean','issues'):raise HTTPException(404,'Choose clean or issues.')
    stem='invoices_clean' if profile=='clean' else 'invoices_with_issues'
    return run_analysis((ROOT/'data'/f'{stem}.xlsx').read_bytes(),stem+'.xlsx',(ROOT/'data'/'bank_statement.pdf').read_bytes())

@app.post('/api/analyses')
def upload(invoices:UploadFile=File(...),bank_statement:UploadFile=File(...)):
    ib=invoices.file.read(5_000_001);bb=bank_statement.file.read(5_000_001)
    if len(ib)>5_000_000 or len(bb)>5_000_000:raise HTTPException(413,'Each file must be at most 5 MB.')
    return run_analysis(ib,invoices.filename or '',bb)

@app.get('/api/analyses/{analysis_id}')
def get_analysis(analysis_id:str):
    with connect() as c:row=c.execute('SELECT payload FROM analyses WHERE id=?',(analysis_id,)).fetchone()
    if row is None:raise HTTPException(404,'Analysis not found.')
    return json.loads(row[0])

@app.get('/api/analyses/{analysis_id}/export')
def export(analysis_id:str):
    return Response(json.dumps(get_analysis(analysis_id),indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="financing-evidence.json"'})

ALLOWED={'invoices_clean.xlsx','invoices_with_issues.xlsx','invoices_clean.csv','invoices_with_issues.csv','bank_statement.pdf','manifest.json'}
@app.get('/api/samples/{name}')
def sample(name:str):
    if name not in ALLOWED:raise HTTPException(404,'Sample not found.')
    return FileResponse(ROOT/'data'/name,filename=name)

class BankObservation(BaseModel):
    status:str
    observed_at:str

class BankLab(BaseModel):
    observations:list[str | BankObservation]=Field(min_length=1,max_length=20)
@app.post('/api/bank-lab')
def bank_lab(body:BankLab):
    return reconcile_status([o if isinstance(o,str) else o.model_dump() for o in body.observations])

@app.post('/api/bank-lab/simulate')
def bank_simulation():return simulate_status_errors()

from app.automation import SyncService, router as automation_router
sync_service=SyncService(connect,run_analysis)
app.include_router(automation_router(sync_service))
