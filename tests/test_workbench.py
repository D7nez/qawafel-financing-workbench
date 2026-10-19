import copy, io, json, os
from pathlib import Path
import pytest
from app.analysis import DataError, analyze, read_bank, read_invoices, money
from app.bank import reconcile_status
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture(scope='module')
def inputs():
    return (read_invoices((ROOT/'data/invoices_clean.xlsx').read_bytes(),'invoices.xlsx'),*read_bank((ROOT/'data/bank_statement.pdf').read_bytes()))

def test_independent_ledger_totals(inputs):
    rows,txs,statements=inputs;d=analyze(*inputs)
    # Golden sums are from the seeded fixture, not recomputed by production functions.
    assert d['metrics']['net_revenue']==2349483.58
    assert d['metrics']['gross_invoiced']==2701906.23
    assert d['metrics']['matched_collections']==2114649.31
    assert d['metrics']['outstanding']==587256.92
    assert round(sum(d['aging'].values()),2)==587256.92
    assert d['counts']['blockers']==0
    assert sum(money(r['net_amount']) for r in rows)==234948358
    assert statements[0]['opening']+sum(t['amount'] for t in txs)==statements[-1]['closing']
    assert d['metrics']['owner_transfers_excluded']==100000
    assert len(d['monthly'])==12

def test_dirty_rows_quarantined(inputs):
    raw=read_invoices((ROOT/'data/invoices_with_issues.xlsx').read_bytes(),'bad.xlsx')
    d=analyze(raw,*inputs[1:]);codes=[x['code'] for x in d['issues']]
    assert d['status']=='Needs data correction'
    assert d['counts']['valid_invoices']==308
    assert codes.count('INVALID_ROW')==3 and codes.count('DUPLICATE_ID')==1
    assert len(d['unmatched'])>0

def test_duplicate_is_never_double_counted(inputs):
    rows,txs,s=inputs;d=analyze(rows+[dict(rows[0])],txs,s)
    assert d['metrics']['net_revenue']==2349483.58
    assert d['counts']['blockers']==1

def test_missing_month_blocks(inputs):
    rows,txs,s=inputs;d=analyze([r for r in rows if not r['issue_date'].startswith('2025-10')],txs,s)
    assert any(i['code']=='MISSING_MONTH' for i in d['issues'])

def test_overpayment_does_not_inflate_collections(inputs):
    rows,txs,s=inputs;first=next(t for t in txs if t['kind']=='RECEIPT');extra={**first,'id':'TX-EXTRA','amount':10**10}
    d=analyze(rows,txs+[extra],s)
    assert d['metrics']['matched_collections']==2114649.31
    assert any(t['reason']=='Would exceed invoice balance' for t in d['unmatched'])

def test_split_receipts_and_early_payment(inputs):
    rows,txs,s=inputs;one=next(t for t in txs if t['kind']=='RECEIPT');a=one['amount']//2
    split=[t for t in txs if t['id']!=one['id']]+[{**one,'amount':a},{**one,'id':'TX-SPLIT','amount':one['amount']-a}]
    assert analyze(rows,split,s)['metrics']['matched_collections']==2114649.31
    early=[{**t,'date':__import__('datetime').date(2025,1,1)} if t['id']==one['id'] else t for t in txs]
    assert any(t['reason']=='Receipt predates invoice' for t in analyze(rows,early,s)['unmatched'])

def test_model_reproducible_and_detects_planted_case(inputs):
    a,b=analyze(*inputs),analyze(*inputs)
    assert a['anomalies']==b['anomalies']
    assert 'INV-202605-010' in [x['invoice_id'] for x in a['anomalies']]

@pytest.mark.parametrize('value',['NaN','Infinity','1.001','1,000.00',None])
def test_invalid_amounts(value):
    with pytest.raises(DataError):money(value)

def test_invalid_pdf_is_rejected():
    with pytest.raises(DataError):read_bank(b'not a pdf')

def test_formula_rejected(inputs):
    rows=copy.deepcopy(inputs[0]);rows[0]['net_amount']='=1000+1'
    assert any(i['code']=='INVALID_ROW' and i['source']=='invoices row 2' for i in analyze(rows,*inputs[1:])['issues'])

def test_bank_repetition_is_not_confirmation():
    assert reconcile_status(['APPROVED']*3)['state']=='UNVERIFIED'
    assert reconcile_status(['APPROVED','REJECTED'])['conflict']
    assert reconcile_status(['GARBAGE'])['state']=='UNKNOWN'
    assert not reconcile_status(['PENDING','UNDER_REVIEW','APPROVED'])['conflict']

def test_api_upload_cache_export_and_rejections(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    monkeypatch.setattr(main,'DB',tmp_path/'test.sqlite3');client=TestClient(main.app)
    assert client.get('/api/health').status_code==200
    a=client.post('/api/demo/clean');assert a.status_code==200
    b=client.post('/api/demo/clean');assert b.json()['cached'] and a.json()['id']==b.json()['id']
    files={'invoices':('data.xlsx',(ROOT/'data/invoices_clean.xlsx').read_bytes()),'bank_statement':('bank.pdf',(ROOT/'data/bank_statement.pdf').read_bytes())}
    c=client.post('/api/analyses',files=files);assert c.status_code==200 and c.json()['id']==a.json()['id']
    e=client.get('/api/analyses/'+a.json()['id']+'/export');assert e.status_code==200 and e.json()['metrics']==a.json()['metrics']
    assert client.get('/api/analyses/missing').status_code==404
    assert client.post('/api/demo/nope').status_code==404
    assert client.get('/api/samples/not-allowed').status_code==404
    assert client.post('/api/analyses',files={'invoices':('bad.csv',b'x,y\n1,2'),'bank_statement':('b.pdf',b'bad')}).status_code==422
    assert client.post('/api/bank-lab',json={'observations':['APPROVED']*3}).json()['state']=='UNVERIFIED'
    assert client.post('/api/demo/clean',content=b'x',headers={'content-length':'12000001'}).status_code==413
    assert 'frame-ancestors' in client.get('/').headers['content-security-policy']

def test_tampered_balance_pdf_rejected(monkeypatch):
    import pdfplumber
    class Page:
        def extract_text(self):return 'QAWAFEL_SYNTHETIC_V1\nPERIOD | 2025-10-01 | 2025-10-31 | 1.00 | 3.00\nTX | A | 2025-10-03 | RECEIPT | INV-1 | 1.00 | SAR'
    class PDF:
        pages=[Page()]
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(pdfplumber,'open',lambda _:PDF())
    with pytest.raises(DataError,match='coverage'):read_bank(b'%PDF-test')

@pytest.mark.parametrize('v',['2026-01-01garbage','01/02/2026','2026-02-30',''])
def test_dates_strict(v):
    from app.analysis import iso
    with pytest.raises(DataError):iso(v)

def test_bank_balance_and_duplicate_transactions_rejected(monkeypatch,inputs):
    import pdfplumber
    class Page:
        def __init__(self,text):self.text=text
        def extract_text(self):return self.text
    class PDF:
        def __init__(self,text):self.pages=[Page(text)]
        def __enter__(self):return self
        def __exit__(self,*args):pass
    txs,statements=inputs[1:]
    def text(duplicate=False,bad_balance=False):
        lines=['QAWAFEL_SYNTHETIC_V1']
        for n,s in enumerate(statements):lines.append(f"PERIOD | {s['start']} | {s['end']} | {s['opening']/100:.2f} | {(s['closing']+(100 if n==0 and bad_balance else 0))/100:.2f}")
        for t in txs:lines.append(f"TX | {t['id']} | {t['date']} | {t['kind']} | {t['reference']} | {t['amount']/100:.2f} | SAR")
        if duplicate:lines.append(lines[-1])
        return '\n'.join(lines)
    monkeypatch.setattr(pdfplumber,'open',lambda _:PDF(text(bad_balance=True)))
    with pytest.raises(DataError,match='reconciliation'):read_bank(b'%PDF-test')
    monkeypatch.setattr(pdfplumber,'open',lambda _:PDF(text(duplicate=True)))
    with pytest.raises(DataError,match='Duplicate bank transaction'):read_bank(b'%PDF-test')

def test_cache_does_not_bypass_file_type_validation(tmp_path,monkeypatch):
    from fastapi import HTTPException
    import app.main as main
    monkeypatch.setattr(main,'DB',tmp_path/'cache.sqlite3')
    ib=(ROOT/'data/invoices_clean.xlsx').read_bytes();bb=(ROOT/'data/bank_statement.pdf').read_bytes()
    main.run_analysis(ib,'good.xlsx',bb)
    with pytest.raises(HTTPException) as e:main.run_analysis(ib,'renamed.exe',bb)
    assert e.value.status_code==422

@pytest.mark.parametrize('value,expected',[(2335.4199999999996,233542),(0.1+0.2,30),(12.34,1234)])
def test_float_representation_noise_only(value,expected):
    assert money(value)==expected

@pytest.mark.parametrize('v',[1.001,2335.4199,True,'2335.4199999999996'])
def test_meaningful_fractional_cents_not_silently_rounded(v):
    with pytest.raises(DataError):money(v)

def test_xlsx_missing_dimensions_and_blank_row_provenance():
    from openpyxl import Workbook
    import zipfile,re
    from app.analysis import FIELDS
    wb=Workbook();ws=wb.active;ws.append(FIELDS);ws.append(['A','C','2026-01-01','2026-01-31',2335.4199999999996,350.31,'SAR']);ws.append([None]*7);ws.append(['B','C','2026-01-02','2026-01-31',100,15,'SAR'])
    original=io.BytesIO();wb.save(original);out=io.BytesIO()
    with zipfile.ZipFile(original) as a,zipfile.ZipFile(out,'w') as b:
        for item in a.infolist():
            content=a.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':content=re.sub(rb'<dimension[^>]*/>',b'',content)
            b.writestr(item,content)
    rows=read_invoices(out.getvalue(),'example.xlsx')
    assert len(rows)==2 and [r['_source_row'] for r in rows]==[2,4]
    assert money(rows[0]['net_amount'])==233542

def test_customer_evidence_balances_and_settlement_duration(inputs):
    d=analyze(*inputs);customers=d['customer_risk']
    assert round(sum(c['overdue'] for c in customers),2)==d['metrics']['overdue']
    assert round(sum(c['outstanding'] for c in customers),2)==d['metrics']['outstanding']
    assert round(sum(c['not_overdue'] for c in customers),2)==d['metrics']['not_overdue_receivables']
    assert d['metrics']['overdue_90_plus']==101662.97
    assert d['metrics']['no_payment_invoice_count']==63
    by_id={c['id']:c for c in customers}
    assert by_id['CUST-03']['weighted_days_to_full_payment']>by_id['CUST-01']['weighted_days_to_full_payment']
    # Verify an individual fully settled invoice directly from receipt dates.
    target=next(i for i in d['invoices'] if i['outstanding']==0)
    receipts=[t for t in inputs[1] if t['kind']=='RECEIPT' and t['reference']==target['invoice_id']]
    assert sum(t['amount'] for t in receipts)==money(target['gross'])
    assert all(t['date']>=__import__('datetime').date.fromisoformat(target['issued']) for t in receipts)

def test_anomaly_priority_is_financial_not_model_score(inputs):
    anomalies=analyze(*inputs)['anomalies']
    assert anomalies==sorted(anomalies,key=lambda a:(-a['outstanding'],-a['amount'],a['score'],a['invoice_id']))
    assert anomalies[0]['invoice_id']=='INV-202605-010'

def test_bank_timestamps_reversals_timeouts_and_simulation():
    from app.bank import simulate_status_errors
    allowed=reconcile_status([{'status':'PENDING','observed_at':'2026-10-18T10:00:00Z'},{'status':'APPROVED','observed_at':'2026-10-18T11:00:00Z'}])
    assert not allowed['conflict'] and not allowed['verified']
    assert reconcile_status(['UNDER_REVIEW','PENDING'])['conflict']
    stale=reconcile_status([{'status':'APPROVED','observed_at':'2026-10-18T11:00:00Z'},{'status':'PENDING','observed_at':'2026-10-18T10:00:00Z'}])
    assert stale['observed']=='APPROVED' and stale['stale_observation_indices']==[1]
    assert reconcile_status([{'status':'PENDING','observed_at':'2026-10-18T10:00:00'}])['state']=='UNKNOWN'
    assert reconcile_status(['PENDING','TIMEOUT'])['state']=='UNKNOWN'
    sim=simulate_status_errors();assert sim==simulate_status_errors()
    assert sim['correlated_all_three_wrong']>sim['independent_all_three_wrong']

def test_synthetic_scenario_variability_and_reproducibility(tmp_path,monkeypatch):
    from scripts import generate_data
    monkeypatch.setattr(generate_data,'DATA',tmp_path)
    generate_data.generate();a=(tmp_path/'invoices_clean.csv').read_bytes()
    manifest=json.loads((tmp_path/'manifest.json').read_text())
    assert len(set(manifest['monthly_invoice_counts'].values()))>5
    assert sum(manifest['monthly_invoice_counts'].values())==manifest['invoice_count']==311
    generate_data.generate();assert (tmp_path/'invoices_clean.csv').read_bytes()==a

def test_concurrent_cache_writers_share_canonical_id(tmp_path,monkeypatch):
    import app.main as main
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import nullcontext
    import threading
    monkeypatch.setattr(main,'DB',tmp_path/'concurrent.sqlite3')
    # Remove process-local serialization to exercise competing database writers.
    monkeypatch.setattr(main,'LOCK',nullcontext())
    barrier=threading.Barrier(2);original=main.analyze
    def simultaneous(*args,**kwargs):
        result=original(*args,**kwargs);barrier.wait(timeout=15);return result
    monkeypatch.setattr(main,'analyze',simultaneous)
    ib=(ROOT/'data/invoices_clean.xlsx').read_bytes();bb=(ROOT/'data/bank_statement.pdf').read_bytes()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,b=list(pool.map(lambda _:main.run_analysis(ib,'input.xlsx',bb),range(2)))
    assert a['id']==b['id'] and a['cached']!=b['cached']
    with main.connect() as c:assert c.execute('SELECT count(*) FROM analyses').fetchone()[0]==1
