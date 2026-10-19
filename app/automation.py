"""Local pull orchestration for two mock HTTP sources, with persisted run history.

One application worker owns this demo scheduler. No bank submission is performed.
"""
from __future__ import annotations
import asyncio, hashlib, json, logging, uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from typing import Literal
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.analysis import VERSION

def utc():return datetime.now(timezone.utc)
def stamp():return utc().isoformat()
class SourceFailure(Exception):pass
class ConsentStopped(Exception):pass

class ConsentRequest(BaseModel):
    accepted:bool
    expires_in_minutes:int=Field(default=60,ge=1,le=480)
class ScheduleRequest(BaseModel):
    enabled:bool
    interval_seconds:int=Field(default=60,ge=10,le=86400)

class ScenarioRequest(BaseModel):
    profile:Literal['clean','issues']='clean'
    fault:Literal['healthy','unavailable','bad_hash']='healthy'

class SyncService:
    BASE='http://127.0.0.1:8001'
    def __init__(self,connect,analyze,transport=None):
        self.connect=connect;self.analyze=analyze;self.transport=transport
        self.lock=asyncio.Lock()

    def db(self):
        c=self.connect()
        c.execute('CREATE TABLE IF NOT EXISTS sync_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS sync_runs (id TEXT PRIMARY KEY,started_at TEXT,finished_at TEXT,trigger TEXT,status TEXT,detail TEXT,analysis_id TEXT,revision TEXT)')
        defaults={'consent_expires_at':None,'consent_generation':0,'enabled':False,'interval_seconds':60,'next_due':None,'fingerprint':None,'last_analysis_id':None,'last_source_revision':None,'failure_count':0}
        c.execute('INSERT OR IGNORE INTO sync_state VALUES (1,?)',(json.dumps(defaults),));c.commit()
        return c

    def state(self):
        with self.db() as c:return json.loads(c.execute('SELECT payload FROM sync_state WHERE id=1').fetchone()[0])

    def update(self,**values):
        # The local service uses one event loop; no await occurs inside this update.
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            s=json.loads(c.execute('SELECT payload FROM sync_state WHERE id=1').fetchone()[0]);s.update(values)
            c.execute('UPDATE sync_state SET payload=? WHERE id=1',(json.dumps(s),))
        return s

    def active(self,s=None):
        s=s or self.state()
        return bool(s['consent_expires_at'] and datetime.fromisoformat(s['consent_expires_at'])>utc())

    def check_consent(self,generation):
        s=self.state()
        if not self.active(s) or s['consent_generation']!=generation:raise ConsentStopped('Demo consent expired or was revoked. No new fetch/result publication.')

    def set_consent(self,accepted,minutes=60):
        s=self.state()
        self.update(consent_expires_at=(utc()+timedelta(minutes=minutes)).isoformat() if accepted else None,
            consent_generation=s['consent_generation']+1,enabled=False,next_due=None)

    def schedule(self,enabled,interval):
        if enabled and not self.active():raise HTTPException(403,'Grant fictional read consent first.')
        self.update(enabled=enabled,interval_seconds=interval,next_due=stamp() if enabled else None)

    def public(self):
        s=self.state()
        with self.db() as c:
            rows=c.execute('SELECT id,started_at,finished_at,trigger,status,detail,analysis_id,revision FROM sync_runs ORDER BY started_at DESC LIMIT 20').fetchall()
        keys=['id','started_at','finished_at','trigger','status','detail','analysis_id','revision']
        return {**s,'consent_active':self.active(s),'running':self.lock.locked(),'runs':[dict(zip(keys,r)) for r in rows],
            'simulation':True,'source_url':self.BASE,'scope':'fictional-cedar-001 / Oct 2025-Sep 2026 / invoices + bank statement read only',
            'scheduler_note':'Runs while the app server is running; one worker only. Not a real provider consent/OAuth flow.'}

    async def fetch(self,client,path,generation,max_size):
        self.check_consent(generation)
        # Never follow source-supplied external URLs, redirects or proxy environment settings.
        if not path.startswith('/') or path.startswith('//') or urlsplit(path).netloc:raise SourceFailure('Unexpected source path.')
        chunks=[];size=0
        async with client.stream('GET',self.BASE+path,headers={'X-Demo-Consent':'fictional-read-scope'}) as r:
            if r.status_code!=200:raise SourceFailure(f'Source returned HTTP {r.status_code}; retry safely on next scheduled pull.')
            async for chunk in r.aiter_bytes():
                self.check_consent(generation);size+=len(chunk)
                if size>max_size:raise SourceFailure('Source payload exceeds configured limit.')
                chunks.append(chunk)
        return b''.join(chunks)

    async def run(self,trigger='manual'):
        if self.lock.locked():raise HTTPException(409,'A synchronization is already running.')
        if not self.active():raise HTTPException(403,'Grant unexpired fictional read consent first.')
        async with self.lock:
            s=self.state();generation=s['consent_generation'];rid=str(uuid.uuid4());started=stamp()
            with self.db() as c:c.execute('INSERT INTO sync_runs VALUES (?,?,NULL,?,?,?,NULL,NULL)',(rid,started,trigger,'running','Fetching mock manifests'))
            status='failed';detail='';analysis_id=None;revision=None;out=None
            try:
                async with httpx.AsyncClient(transport=self.transport,timeout=5,trust_env=False,follow_redirects=False) as client:
                    manifests=[]
                    for kind in ('accounting','bank'):
                        raw=await self.fetch(client,f'/{kind}/v1/manifest',generation,64000)
                        try:m=json.loads(raw)
                        except (ValueError,TypeError):raise SourceFailure('Malformed source manifest.')
                        name='invoices.csv' if kind=='accounting' else 'statement.pdf'
                        if not isinstance(m,dict) or m.get('entity_id')!='fictional-cedar-001' or m.get('period_start')!='2025-10-01' or m.get('period_end')!='2026-09-30' or m.get('source')!=kind or type(m.get('revision')) is not int:
                            raise SourceFailure('Source entity, scope, period or revision mismatch.')
                        expected=f'/{kind}/v1/files/{name}?revision={m["revision"]}'
                        if m.get('path')!=expected or not isinstance(m.get('sha256'),str) or len(m['sha256'])!=64:
                            raise SourceFailure('Source path/hash contract mismatch.')
                        manifests.append(m)
                    if manifests[0]['revision']!=manifests[1]['revision']:raise SourceFailure('Sources are not at one coherent mock snapshot; retry.')
                    revision=str(manifests[0]['revision'])
                    fingerprint=hashlib.sha256((VERSION+'|'+'|'.join(m['sha256'] for m in manifests)).encode()).hexdigest()
                    if fingerprint==s['fingerprint'] and s['last_analysis_id']:
                        self.check_consent(generation)
                        status='unchanged';analysis_id=s['last_analysis_id'];detail='Source hashes unchanged; file downloads and analysis skipped.'
                        self.update(last_source_revision=revision,failure_count=0)
                    else:
                        documents=[]
                        for m in manifests:
                            data=await self.fetch(client,m['path'],generation,5_000_000)
                            if hashlib.sha256(data).hexdigest()!=m['sha256'] or len(data)!=m.get('size'):raise SourceFailure('Source checksum/size mismatch; no checkpoint advanced.')
                            documents.append(data)
                        self.check_consent(generation)
                        out=await asyncio.to_thread(self.analyze,documents[0],'source.csv',documents[1])
                        self.check_consent(generation)
                        analysis_id=out['id'];status='needs_review' if out['counts']['blockers'] else 'synced'
                        detail=f"Imported snapshot; {out['counts']['blockers']} data blockers. No bank submission or financing decision."
                        self.update(fingerprint=fingerprint,last_analysis_id=analysis_id,last_source_revision=revision,failure_count=0)
            except asyncio.CancelledError:
                status='interrupted';detail='Server stopping; no synchronization checkpoint advanced.'
                raise
            except ConsentStopped as e:status='consent_stopped';detail=str(e)
            except (httpx.HTTPError,SourceFailure,HTTPException) as e:
                detail=e.detail if isinstance(e,HTTPException) else str(e)
                if isinstance(e,httpx.HTTPError):detail='Mock source unreachable or timed out. Start the source API; automatic retry is bounded.'
                self.update(failure_count=self.state()['failure_count']+1)
            except Exception:
                logging.exception('Local source synchronization failed')
                detail='Unexpected processing failure; checkpoint retained. Inspect local server logs.'
                self.update(failure_count=self.state()['failure_count']+1)
            finally:
                with self.db() as c:c.execute('UPDATE sync_runs SET finished_at=?,status=?,detail=?,analysis_id=?,revision=? WHERE id=?',(stamp(),status,detail,analysis_id,revision,rid))
                latest=self.state()
                if latest['enabled'] and self.active(latest):
                    delay=min(3600,latest['interval_seconds']*2**min(latest['failure_count'],6))
                    self.update(next_due=(utc()+timedelta(seconds=delay)).isoformat())
            return {'run_id':rid,'status':status,'detail':detail,'analysis_id':analysis_id,'analysis':out if status in ('synced','needs_review') else None}

    async def tick(self):
        s=self.state()
        if not self.active(s):
            if s['enabled']:self.update(enabled=False,next_due=None)
            return
        if s['enabled'] and not self.lock.locked() and s['next_due'] and datetime.fromisoformat(s['next_due'])<=utc():await self.run('scheduled')

    async def loop(self):
        # Historical in-flight records cannot be resumed after a process restart.
        with self.db() as c:c.execute("UPDATE sync_runs SET status='interrupted',finished_at=?,detail='Server restarted; checkpoint retained, next pull can retry.' WHERE status='running'",(stamp(),))
        while True:
            try:await self.tick()
            except asyncio.CancelledError:raise
            except Exception:logging.exception('Local synchronization scheduler tick failed')
            await asyncio.sleep(2)

def router(service):
    r=APIRouter(prefix='/api/automation',tags=['Mock source automation'])
    @r.get('/status')
    async def status():return service.public()
    @r.post('/consent')
    async def consent(body:ConsentRequest):
        if not body.accepted:raise HTTPException(422,'Consent checkbox must be accepted explicitly.')
        service.set_consent(True,body.expires_in_minutes);return service.public()
    @r.post('/revoke')
    async def revoke():service.set_consent(False);return service.public()
    @r.post('/schedule')
    async def schedule(body:ScheduleRequest):service.schedule(body.enabled,body.interval_seconds);return service.public()
    @r.post('/scenario')
    async def scenario(body:ScenarioRequest):
        if not service.active():raise HTTPException(403,'Grant fictional read consent before changing this demo scenario.')
        try:
            async with httpx.AsyncClient(transport=service.transport,timeout=5,trust_env=False) as client:
                response=await client.post(service.BASE+'/control/scenario',json=body.model_dump())
                response.raise_for_status();return response.json()
        except httpx.HTTPError:raise HTTPException(503,'Mock source unavailable. Start python scripts/run_local.py.')
    @r.post('/sync')
    async def sync():return await service.run()
    return r
