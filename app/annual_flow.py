"""Annual sector flows from disjoint reporting scopes, with month coverage."""
from calendar import monthrange
from collections import defaultdict
from decimal import Decimal
import psycopg
from psycopg import sql

SECTORS = {
    "refining": "กลั่นน้ำมัน", "electricity": "ผลิตไฟฟ้า", "cooking": "หุงต้ม",
    "industry": "อุตสาหกรรม", "transport": "ขนส่ง", "other": "การใช้อื่น", "co2": "การปล่อย CO₂"
}
TYPES = {"coal": "COAL", "gas": "NATURAL_GAS", "oil": "OIL"}
CO2 = {"coal": "CO2 - COAL / LIGNITE", "gas": "CO2 - NATURAL GAS", "oil": "CO2 - OIL"}
SOURCES = ['SRC-04','SRC-09','SRC-11','SRC-15','SRC-18','SRC-19','SRC-20','SRC-21','SRC-22']


def sector_for(row):
    source, process, kind = row['source_code'], row['process'], row['process_type']
    if kind == 'EMISSION':
        return 'co2'
    if source == 'SRC-04':
        return 'refining'
    if source == 'SRC-22':
        return 'electricity' if row['product'] in ('DIESEL','FUEL OIL') else None
    if source in ('SRC-11','SRC-15') and process.startswith('ELECTRICITY'):
        return 'electricity'
    if process == 'INDUSTRY':
        return 'industry'
    if source == 'SRC-09' and process == 'COOKING':
        return 'cooking'
    if (source == 'SRC-09' and process == 'AUTOMOBILE') or (source == 'SRC-11' and process == 'NGV'):
        return 'transport'
    return 'other'


def annualize(rows, year, fuel):
    groups = {}
    for row in rows:
        if fuel != 'all':
            match = row['product'] == CO2[fuel] if row['process_type'] == 'EMISSION' else row['product_type'] == TYPES[fuel]
            if not match:
                continue
        sector = sector_for(row)
        if sector is None:
            continue
        key = (sector,row['source_code'],row['process'],row['product'],row['unit'])
        if key not in groups:
            groups[key] = dict(sector=sector,source_code=row['source_code'],process=row['process'],
                               product=row['product'],source_unit=row['unit'],unit=row['unit'],
                               amount=Decimal(0),months=[],exchange_ids=[],conversion='sum')
        item = groups[key]
        month = row['month']
        if month in item['months']:
            raise ValueError('พบข้อมูลเดือนซ้ำภายในชุดเดียวกัน กรุณาตรวจ Exchange ก่อนรวมรายปี')
        value = Decimal(row['amount'])
        if row['unit'] in ('BBL/DAY','MMSCFD'):
            value *= monthrange(year,month)[1]
            item['unit'] = 'BBL' if row['unit'] == 'BBL/DAY' else 'MMSCF'
            item['conversion'] = 'monthly_rate_times_calendar_days'
        elif row['unit'] in ('1,000 Tons','Thousand Tons'):
            value *= 1000
            item['unit'] = 'Ton'
            item['conversion'] = 'thousand_tons_to_tons'
        item['amount'] += value
        item['months'].append(month)
        item['exchange_ids'].append(row['entity_id'])
    nodes=[]
    for sector,label in SECTORS.items():
        records=[item for item in groups.values() if item['sector']==sector]
        totals=defaultdict(Decimal)
        for item in records:
            totals[item['unit']] += item['amount']
            item['amount']=format(item['amount'],'f')
            item['months'].sort()
            item['complete']=len(item['months'])==12
            item['missing_months']=[m for m in range(1,13) if m not in item['months']]
        nodes.append(dict(id=sector,label=label,records=records,
                          summaries=[dict(amount=format(value,'f'),unit=unit) for unit,value in totals.items()],
                          complete=bool(records) and all(r['complete'] for r in records)))
    return dict(year=year,fuel=fuel,nodes=nodes)


def read_annual_flow(database_url,schema,fuel='all',year=None):
    if fuel not in ('all',*TYPES):
        raise ValueError('เลือก all, coal, gas หรือ oil')
    with psycopg.connect(database_url,connect_timeout=10) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SET LOCAL statement_timeout = '8000ms'")
        conn.execute(sql.SQL('SET LOCAL search_path TO {}, public').format(sql.Identifier(schema)))
        years=[r[0] for r in conn.execute("SELECT DISTINCT period_year FROM lci_exchange WHERE validation_status='VERIFIED' AND period_month BETWEEN 1 AND 12 ORDER BY 1 DESC").fetchall()]
        if year is None and years:
            year=years[1] if len(years)>1 else years[0]
        raw=conn.execute("""SELECT e.exchange_id,s.src_code,p.name,p.process_type,f.name,f.product_type,
                   e.period_month,e.amount::text,u.symbol
            FROM lci_exchange e JOIN source s USING(source_id)
            JOIN process_flow pf USING(process_flow_id) JOIN process p USING(process_id)
            JOIN flow f USING(flow_id) JOIN unit u USING(unit_id)
            WHERE e.period_year=%s AND e.period_month BETWEEN 1 AND 12 AND e.validation_status='VERIFIED'
              AND s.src_code=ANY(%s)
              AND ((pf.direction='IN' AND p.process_type IN ('DOMESTIC_USE','REFINING'))
                   OR (pf.direction='OUT' AND p.process_type='EMISSION'))
            ORDER BY s.src_code,p.name,f.name,e.period_month""",(year,SOURCES)).fetchall()
    rows=[dict(zip(('entity_id','source_code','process','process_type','product','product_type','month','amount','unit'),r)) for r in raw]
    result=annualize(rows,year,fuel)
    result['years']=years
    return result
