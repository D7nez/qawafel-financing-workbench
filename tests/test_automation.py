"""HTTP transport checks for fictional source synchronization."""
import asyncio
from datetime import timedelta
import httpx
import pytest
from fastapi import HTTPException
from app.automation import SyncService, utc

@pytest.fixture
def system(tmp_path,monkeypatch):
    import app.main as main
    import app.mock_provider as provider
    monkeypatch.setattr(main,'DB',tmp_path/'workbench.sqlite3');monkeypatch.setattr(provider,'DB',tmp_path/'source.sqlite3')
    calls=[]
    class Recording(httpx.AsyncBaseTransport):
        def __init__(self):self.inner=httpx.ASGITransport(app=provider.app)
        async def handle_async_request(self,request):
            calls.append((request.method,request.url.path));return await self.inner.handle_async_request(request)
    return SyncService(main.connect,main.run_analysis,transport=Recording()),provider,calls

def test_consent_required_and_source_scope(system):
    s,p,calls=system
    async def run():
        with pytest.raises(HTTPException) as e:await s.run()
        assert e.value.status_code==403 and not calls
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=p.app),base_url=s.BASE) as c:
            assert (await c.get('/accounting/v1/manifest')).status_code==403
    asyncio.run(run())

def test_pull_then_unchanged_skips_files(system):
    s,p,calls=system;s.set_consent(True)
    async def run():
        a=await s.run();assert a['status']=='synced' and a['analysis']['counts']['valid_invoices']==311
        n=len(calls);b=await s.run();assert b['status']=='unchanged' and b['analysis_id']==a['analysis_id']
        assert len(calls)==n+2 and all('/manifest' in path for _,path in calls[n:])
        with s.connect() as c:assert c.execute('SELECT count(*) FROM analyses').fetchone()[0]==1
        assert len(s.public()['runs'])==2
    asyncio.run(run())

def test_changed_source_requires_review(system):
    s,p,calls=system;s.set_consent(True)
    async def run():
        a=await s.run();p.scenario(p.Scenario(profile='issues'));b=await s.run()
        assert b['status']=='needs_review' and b['analysis']['counts']['blockers']==5
        assert b['analysis_id']!=a['analysis_id'] and s.state()['last_source_revision']=='2'
        assert (await s.run())['status']=='unchanged'
    asyncio.run(run())

@pytest.mark.parametrize('fault',['unavailable','bad_hash'])
def test_fault_retains_checkpoint_and_recovers(system,fault):
    s,p,calls=system;s.set_consent(True)
    async def run():
        a=await s.run();fingerprint=s.state()['fingerprint'];p.scenario(p.Scenario(profile='issues',fault=fault))
        assert (await s.run())['status']=='failed'
        assert s.state()['fingerprint']==fingerprint and s.state()['last_analysis_id']==a['analysis_id']
        assert s.state()['failure_count']==1
        p.scenario(p.Scenario(profile='issues'));assert (await s.run())['status']=='needs_review'
        assert s.state()['failure_count']==0
    asyncio.run(run())

def test_schedule_and_expiry(system):
    s,p,calls=system;s.set_consent(True);s.schedule(True,10)
    async def run():
        await s.tick();assert s.public()['runs'][0]['trigger']=='scheduled';n=len(calls)
        await s.tick();assert len(calls)==n
        s.update(consent_expires_at=(utc()-timedelta(seconds=1)).isoformat());await s.tick()
        assert not s.state()['enabled'] and len(calls)==n
        with pytest.raises(HTTPException):await s.run()
    asyncio.run(run())

def test_revoke_during_fetch(system):
    s,p,calls=system;s.set_consent(True);inner=s.transport
    class Revoke(httpx.AsyncBaseTransport):
        async def handle_async_request(self,request):
            r=await inner.handle_async_request(request)
            if request.url.path=='/bank/v1/manifest':s.set_consent(False)
            return r
    s.transport=Revoke()
    async def run():
        assert (await s.run())['status']=='consent_stopped'
        assert s.state()['fingerprint'] is None and not any('/files/' in path for _,path in calls)
    asyncio.run(run())

def test_revoke_during_processing_prevents_publication(system):
    s,p,calls=system;s.set_consent(True);original=s.analyze
    def revoked(*args):
        result=original(*args);s.set_consent(False);return result
    s.analyze=revoked
    async def run():
        r=await s.run();assert r['status']=='consent_stopped' and r['analysis_id'] is None
        assert s.state()['last_analysis_id'] is None
        # Previously downloaded work may complete in the local cache, as documented.
        with s.connect() as c:assert c.execute('SELECT count(*) FROM analyses').fetchone()[0]==1
    asyncio.run(run())

def test_parallel_sync_returns_busy(system):
    s,p,calls=system;s.set_consent(True)
    async def run():
        entered,release=asyncio.Event(),asyncio.Event();inner=s.transport
        class Slow(httpx.AsyncBaseTransport):
            async def handle_async_request(self,request):
                entered.set();await release.wait();return await inner.handle_async_request(request)
        s.transport=Slow();first=asyncio.create_task(s.run());await entered.wait()
        with pytest.raises(HTTPException) as e:await s.run()
        assert e.value.status_code==409
        release.set();assert (await first)['status']=='synced'
    asyncio.run(run())

def test_state_survives_new_service(system):
    s,p,calls=system;s.set_consent(True)
    async def run():
        a=await s.run();restored=SyncService(s.connect,s.analyze,s.transport)
        assert restored.active() and restored.state()['last_analysis_id']==a['analysis_id']
        assert (await restored.run())['status']=='unchanged'
    asyncio.run(run())

def test_external_manifest_path_rejected(system):
    s,p,calls=system;s.set_consent(True);inner=s.transport
    class Bad(httpx.AsyncBaseTransport):
        async def handle_async_request(self,request):
            r=await inner.handle_async_request(request)
            if request.url.path=='/accounting/v1/manifest':
                await r.aread();body=r.json();body['path']='https://external.invalid/steal';return httpx.Response(200,json=body)
            return r
    s.transport=Bad()
    async def run():
        r=await s.run();assert r['status']=='failed' and 'path' in r['detail']
        assert not any('/files/' in path for _,path in calls)
    asyncio.run(run())

def test_automation_routes(system):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.automation import router
    s,p,calls=system;app=FastAPI();app.include_router(router(s));client=TestClient(app)
    assert client.post('/api/automation/sync').status_code==403
    assert client.post('/api/automation/consent',json={'accepted':False}).status_code==422
    assert client.post('/api/automation/consent',json={'accepted':True}).json()['consent_active']
    assert client.post('/api/automation/schedule',json={'enabled':True,'interval_seconds':10}).json()['enabled']
    assert client.post('/api/automation/scenario',json={'profile':'clean'}).status_code==200
    assert client.post('/api/automation/sync').json()['status']=='synced'
    assert not client.post('/api/automation/revoke').json()['consent_active']
    assert not client.get('/api/automation/status').json()['enabled']

def test_bounded_outage_backoff(system):
    s,p,calls=system;s.set_consent(True);s.schedule(True,10);p.scenario(p.Scenario(fault='unavailable'))
    async def run():
        from datetime import datetime
        start=utc();await s.tick();state=s.state();delay=(datetime.fromisoformat(state['next_due'])-start).total_seconds()
        assert 19<delay<25 and state['failure_count']==1
    asyncio.run(run())

def test_scheduler_restart_marks_unfinished_run(system):
    s,p,calls=system
    with s.db() as c:c.execute("INSERT INTO sync_runs VALUES ('old',?,NULL,'scheduled','running','',NULL,NULL)",(utc().isoformat(),))
    async def run():
        from contextlib import suppress
        task=asyncio.create_task(s.loop());await asyncio.sleep(.05);task.cancel()
        with suppress(asyncio.CancelledError):await task
        assert s.public()['runs'][0]['status']=='interrupted'
    asyncio.run(run())

@pytest.mark.parametrize('mode',['wrong_entity','mixed_revision'])
def test_scope_or_snapshot_mismatch_prevents_downloads(system,mode):
    s,p,calls=system;s.set_consent(True);inner=s.transport
    class Changed(httpx.AsyncBaseTransport):
        async def handle_async_request(self,request):
            r=await inner.handle_async_request(request)
            if request.url.path=='/bank/v1/manifest':
                await r.aread();body=r.json()
                if mode=='wrong_entity':body['entity_id']='another-entity'
                else:body['revision']+=1;body['path']='/bank/v1/files/statement.pdf?revision=2'
                return httpx.Response(200,json=body)
            return r
    s.transport=Changed()
    async def run():
        assert (await s.run())['status']=='failed'
        assert s.state()['fingerprint'] is None and not any('/files/' in path for _,path in calls)
    asyncio.run(run())

def test_network_timeout_recorded_without_checkpoint(system):
    s,p,calls=system;s.set_consent(True)
    class Timeout(httpx.AsyncBaseTransport):
        async def handle_async_request(self,request):raise httpx.ReadTimeout('simulated',request=request)
    s.transport=Timeout()
    async def run():
        r=await s.run();assert r['status']=='failed' and 'timed out' in r['detail']
        assert s.state()['failure_count']==1 and s.state()['fingerprint'] is None
    asyncio.run(run())
