"""Replace SRC-18 with EPPO sector datasets in the local database, in one transaction."""
import csv
import os
from decimal import Decimal
from pathlib import Path
import psycopg

HERE = Path(__file__).resolve().parent
SOURCES = [
    ('SRC-18', 'dataset_11_65', 'OTHER ECONOMIC SECTORS', 'การปล่อย CO2 แยกตามชนิดเชื้อเพลิงในสาขาเศรษฐกิจอื่นๆ'),
    ('SRC-19', 'dataset_11_64', 'INDUSTRY', 'การปล่อย CO2 แยกตามชนิดเชื้อเพลิงในภาคอุตสาหกรรม'),
    ('SRC-20', 'dataset_11_63', 'TRANSPORT', 'การปล่อย CO2 แยกตามชนิดเชื้อเพลิงในภาคขนส่ง'),
    ('SRC-21', 'dataset_11_62', 'ELECTRICITY GENERATION', 'การปล่อย CO2 แยกตามชนิดเชื้อเพลิงในการผลิตไฟฟ้า'),
]
MONTHS = {name: i for i, name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'), 1)}

def main():
    all_rows = []
    for code, dataset, sector, title in SOURCES:
        with (HERE / f'{dataset}.csv').open(encoding='utf-8-sig', newline='') as f:
            for line, row in enumerate(csv.DictReader(f), 2):
                amount = Decimal(row['Quantity'].replace(',', ''))
                if not amount.is_finite() or amount < 0 or row['UNIT'] != 'Thousand Tons-CO2':
                    raise ValueError(f'{dataset} line {line}: invalid amount or unit')
                all_rows.append((code, dataset, sector, title, line, row['Fuel Type'].strip(), amount, int(row['Year']), MONTHS[row['Month'].strip()]))
    connection = os.getenv('LCI_LOCAL_DATABASE_URL', 'postgresql://cn230lci:portugalsql@localhost:5433/cn230lci')
    with psycopg.connect(connection) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT location_id FROM location WHERE country='Thailand'")
            location = cur.fetchone()[0]
            cur.execute("SELECT unit_id FROM unit WHERE symbol='Thousand Tons-CO2'")
            unit = cur.fetchone()[0]
            for code, dataset, sector, title in SOURCES:
                cur.execute("""INSERT INTO source (src_code,dataset_name,agency,data_owner,url,accessed_date)
                  VALUES (%s,%s,%s,%s,%s,CURRENT_DATE) ON CONFLICT(src_code) DO UPDATE SET
                  dataset_name=EXCLUDED.dataset_name, agency=EXCLUDED.agency, data_owner=EXCLUDED.data_owner,
                  url=EXCLUDED.url, accessed_date=EXCLUDED.accessed_date RETURNING source_id""",
                  (code,title,'ศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร (ศท.)','สำนักงานนโยบายและแผนพลังงาน (EPPO)',f'https://catalog.eppo.go.th/dataset/{dataset}'))
                sid = cur.fetchone()[0]
                cur.execute('DELETE FROM lci_import_log WHERE source_id=%s', (sid,))
                cur.execute('DELETE FROM lci_exchange WHERE source_id=%s', (sid,))
                cur.execute("""INSERT INTO process(name,process_type,location_id) VALUES (%s,'EMISSION',%s)
                  ON CONFLICT(name,process_type,location_id) DO UPDATE SET name=EXCLUDED.name RETURNING process_id""", (sector,location))
                pid = cur.fetchone()[0]
                batch = []
                for _, _, _, _, line, fuel, amount, year, month in (r for r in all_rows if r[0] == code):
                    flow = f'CO2 - {fuel}'
                    cur.execute("INSERT INTO flow(name,product_type) VALUES (%s,'EMISSION') ON CONFLICT(name) DO NOTHING RETURNING flow_id", (flow,))
                    found = cur.fetchone()
                    if not found:
                        cur.execute('SELECT flow_id FROM flow WHERE name=%s AND product_type=%s', (flow,'EMISSION'))
                        found = cur.fetchone()
                    if not found: raise ValueError(f'Conflicting flow: {flow}')
                    cur.execute("INSERT INTO process_flow(process_id,flow_id,direction) VALUES (%s,%s,'OUT') ON CONFLICT(process_id,flow_id) DO NOTHING RETURNING process_flow_id", (pid,found[0]))
                    pf = cur.fetchone()
                    if not pf:
                        cur.execute("SELECT process_flow_id FROM process_flow WHERE process_id=%s AND flow_id=%s AND direction='OUT'", (pid,found[0]))
                        pf = cur.fetchone()
                    if not pf: raise ValueError('Conflicting direction')
                    batch.append((pf[0],amount,unit,year,month,sid,f'Imported from {dataset}.csv row {line}'))
                cur.executemany("INSERT INTO lci_exchange(process_flow_id,amount,unit_id,period_year,period_month,source_id,validation_status,note) VALUES (%s,%s,%s,%s,%s,%s,'PENDING',%s)",batch)
                print(f'{code}: {len(batch)} rows')

if __name__ == '__main__': main()
