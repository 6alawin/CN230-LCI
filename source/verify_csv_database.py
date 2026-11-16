"""Verify each stored Exchange against its source CSV before marking it VERIFIED."""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import psycopg
from psycopg.rows import dict_row
from import_exchanges import read_source_rows, parse_exchange, EXPECTED_UNITS

ROOT=Path(__file__).resolve().parent.parent
expected={}; rejected=[]; rounded=0
for n in range(1,23):
    code=f'SRC-{n:02d}'
    for line,row in read_source_rows(code):
        try:
            item=parse_exchange(code,line,row)
            stored_amount=item['amount'].quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
            if stored_amount!=item['amount']: rounded+=1
            item['amount']=stored_amount
            expected[item['note']]=item
        except ValueError as exc:
            rejected.append({'source':code,'line':line,'reason':str(exc)})
report={'checked_at':datetime.now().isoformat(),'csv_valid_rows':len(expected),'csv_rejected_rows':rejected,'rounded_to_schema_scale_rows':rounded,'amount_comparison':'numeric(24,8), ROUND_HALF_UP'}
q='''SELECT e.exchange_id,e.note,e.amount,e.period_year AS year,e.period_month AS month,
 s.src_code,p.name AS process_name,p.process_type,f.name AS flow_name,f.product_type,
 pf.direction,u.symbol AS unit,u.quantity_type,e.validation_status
 FROM lci_exchange e JOIN source s USING(source_id) JOIN process_flow pf USING(process_flow_id)
 JOIN process p USING(process_id) JOIN flow f USING(flow_id) JOIN unit u USING(unit_id)'''
keys=['src_code','process_name','process_type','flow_name','product_type','direction','amount','unit','year','month']
with psycopg.connect('postgresql://cn230lci:portugalsql@localhost:5433/cn230lci',row_factory=dict_row) as conn:
    conn.execute('LOCK TABLE lci_exchange IN SHARE ROW EXCLUSIVE MODE')
    rows=conn.execute(q).fetchall()
    mismatches=[]; matched=[]; seen=Counter()
    for row in rows:
        item=expected.get(row['note']);seen[row['note']]+=1
        diffs=[key for key in keys if item is None or row[key]!=item[key]]
        if row['quantity_type']!=EXPECTED_UNITS.get(row['unit']):diffs.append('quantity_type')
        if diffs:mismatches.append({'exchange_id':row['exchange_id'],'note':row['note'],'fields':diffs})
        else:matched.append(row['exchange_id'])
    missing=[note for note in expected if note not in seen]
    duplicates=[note for note,count in seen.items() if count>1]
    report.update(database_rows=len(rows),matched_rows=len(matched),mismatches=mismatches,missing_csv_rows=missing,duplicate_import_keys=duplicates)
    if mismatches or missing or duplicates:
        report['result']='FAILED'; updated=0
    else:
        before=Counter(row['validation_status'] for row in rows)
        updated=conn.execute("UPDATE lci_exchange SET validation_status='VERIFIED' WHERE exchange_id=ANY(%s) AND validation_status='PENDING'",(matched,)).rowcount
        report.update(result='PASSED',status_before=dict(before),newly_verified=updated)
    report['status_after']={x['validation_status']:x['n'] for x in conn.execute('SELECT validation_status,count(*) AS n FROM lci_exchange GROUP BY validation_status')}
out=ROOT/'poster_assets'/'verification_report.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('csv_rejected_rows','mismatches','missing_csv_rows','duplicate_import_keys')},ensure_ascii=False))
print('Mismatches:',len(mismatches),'Missing:',len(missing),'Duplicates:',len(duplicates))
