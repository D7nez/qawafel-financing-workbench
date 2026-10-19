"""Optional browser smoke check. Install requirements-ui.txt and Chromium first."""
import os, subprocess, time, sys
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8765'],cwd=ROOT,stdout=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:urlopen('http://127.0.0.1:8765/api/health',timeout=1);break
        except Exception:time.sleep(.2)
    with sync_playwright() as p:
        options={'executable_path':os.environ['CHROME_EXECUTABLE']} if os.getenv('CHROME_EXECUTABLE') else {}
        browser=p.chromium.launch(**options,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1050});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8765');page.click('#clean');expect(page.locator('#status')).to_have_text('Ready for analyst review')
        expect(page.locator('#triage')).to_contain_text('101,663');assert page.locator('#anomalies tbody tr').count()==3
        page.click('[data-view="ledger"]');page.fill('#search','INV-202605-010');assert page.locator('#ledgerTable tbody tr').count()==1
        page.click('#issues');expect(page.locator('#status')).to_have_text('Needs data correction')
        page.click('[data-view="quality"]');expect(page.locator('#qualitySummary')).to_contain_text('blockers')
        page.click('[data-view="bank"]');page.click('#bankStable');expect(page.locator('#bankOutput')).to_contain_text('UNVERIFIED')
        page.click('#bankProgress');expect(page.locator('#bankOutput')).to_contain_text('Progression is allowed')
        page.click('#bankTimeout');expect(page.locator('#bankOutput')).to_contain_text('Outcome unknown')
        page.click('#bankSimulate');expect(page.locator('#bankOutput')).to_contain_text('independent_all_three_wrong')
        page.locator('summary').click();page.set_input_files('#invoiceFile',str(ROOT/'data/invoices_clean.xlsx'));page.set_input_files('#bankFile',str(ROOT/'data/bank_statement.pdf'));page.locator('#upload button').click();expect(page.locator('#status')).to_have_text('Ready for analyst review')
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        assert not errors,errors;browser.close();print('UI smoke passed: demo, dirty, ledger, bank lab, upload, mobile; no JS errors.')
finally:
    server.terminate();server.wait(timeout=10)
