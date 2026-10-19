"""Real local HTTP + browser check, including the recurring scheduler."""
import json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='qawafel-source-check-') as tmp:
    env={**os.environ,'QAWAFEL_DB':str(Path(tmp)/'workbench.sqlite3'),'QAWAFEL_PROVIDER_DB':str(Path(tmp)/'provider.sqlite3')}
    server=subprocess.Popen([sys.executable,'scripts/run_local.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                urlopen('http://127.0.0.1:8000/api/health',timeout=1);urlopen('http://127.0.0.1:8001/health',timeout=1);break
            except Exception:time.sleep(.2)
        else:raise RuntimeError('Local source/workbench failed to start; check ports 8000/8001.')
        with sync_playwright() as p:
            opts={'executable_path':os.environ['CHROME_EXECUTABLE']} if os.getenv('CHROME_EXECUTABLE') else {}
            browser=p.chromium.launch(**opts,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1080});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8000');page.click('[data-view="automation"]')
            page.check('#demoConsent');page.click('#grantConsent');expect(page.locator('#consentStatus')).to_contain_text('active until')
            page.click('#syncNow');expect(page.locator('#autoMessage')).to_contain_text('Imported snapshot',timeout=20000)
            expect(page.locator('#syncHistory')).to_contain_text('synced');page.click('#syncNow');expect(page.locator('#autoMessage')).to_contain_text('unchanged')
            page.select_option('#syncInterval','10');page.click('#startSchedule');expect(page.locator('#syncHistory')).to_contain_text('scheduled',timeout=15000)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                state=json.load(urlopen('http://127.0.0.1:8000/api/automation/status'))
                if sum(r['trigger']=='scheduled' for r in state['runs'])>=2:break
                time.sleep(.5)
            else:raise AssertionError('Recurring scheduler did not produce a second scheduled run.')
            page.click('#stopSchedule');expect(page.locator('#autoState')).to_contain_text('Schedule paused')
            page.select_option('#sourceProfile','issues');page.click('#applyScenario');expect(page.locator('#autoMessage')).to_contain_text('Updated')
            page.click('#syncNow');expect(page.locator('#syncHistory')).to_contain_text('needs_review',timeout=15000)
            page.click('#openSynced');expect(page.locator('#status')).to_have_text('Needs data correction')
            page.click('[data-view="automation"]');page.select_option('#sourceFault','unavailable');page.click('#applyScenario');expect(page.locator('#autoMessage')).to_contain_text('Updated')
            page.click('#syncNow');expect(page.locator('#autoMessage')).to_contain_text('HTTP 503')
            page.select_option('#sourceFault','bad_hash');page.click('#applyScenario');expect(page.locator('#autoMessage')).to_contain_text('Updated')
            page.click('#syncNow');expect(page.locator('#autoMessage')).to_contain_text('checksum')
            page.select_option('#sourceProfile','clean');page.select_option('#sourceFault','healthy');page.click('#applyScenario');expect(page.locator('#autoMessage')).to_contain_text('Updated')
            page.click('#syncNow');expect(page.locator('#autoMessage')).to_contain_text('Imported snapshot',timeout=15000)
            page.click('#revokeConsent');expect(page.locator('#consentStatus')).to_contain_text('No active')
            page.click('#syncNow');expect(page.locator('#autoMessage')).to_contain_text('consent first')
            if os.getenv('AUTOMATION_QA_DIR'):
                dest=Path(os.environ['AUTOMATION_QA_DIR']);dest.mkdir(exist_ok=True,parents=True)
                page.screenshot(path=str(dest/'automation-desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(dest/'automation-mobile.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors,errors;browser.close()
        print('Automation HTTP/browser passed: grant, pull, unchanged, two real scheduled runs, changed snapshot, open package, outage, hash failure, recovery and revocation.')
    finally:
        server.send_signal(signal.SIGINT)
        try:server.wait(timeout=15)
        except subprocess.TimeoutExpired:server.terminate();server.wait(timeout=5)
