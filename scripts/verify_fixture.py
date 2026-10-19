"""Independent CSV/Decimal fixture check; does not import the application engine."""
import csv
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader(open(ROOT/'data/invoices_clean.csv')))
bank=list(csv.DictReader(open(ROOT/'data/bank_transactions.csv')))
net=sum(Decimal(r['net_amount']) for r in rows)
gross=sum(Decimal(r['net_amount'])+Decimal(r['vat_amount']) for r in rows)
receipts=sum(Decimal(t['amount']) for t in bank if t['kind']=='RECEIPT')
assert net==Decimal('2349483.58') and gross==Decimal('2701906.23')
assert receipts==Decimal('2114649.31')
by_id={r['invoice_id']:Decimal(r['net_amount'])+Decimal(r['vat_amount']) for r in rows}
paid={k:Decimal(0) for k in by_id}
for t in bank:
    if t['kind']=='RECEIPT':paid[t['reference']]+=Decimal(t['amount'])
assert all(paid[k]<=by_id[k] for k in paid)
assert sum(by_id[k]-paid[k] for k in by_id)==Decimal('587256.92')
assert sum(paid[k]==0 for k in paid)==63
print('Independent reference verified:',len(rows),'invoices;',net,'net;',receipts,'receipts;',gross-receipts,'outstanding.')
