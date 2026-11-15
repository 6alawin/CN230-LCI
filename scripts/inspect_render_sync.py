"""Read remote database status without logging credentials."""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import json
import psycopg

def remote_url():
    entries={}
    for line in (Path(__file__).resolve().parents[1]/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1);entries[k.strip()]=v.strip().strip('\"').strip("'")
    p=urlsplit(entries['DATABASE_URL']);params=dict(parse_qsl(p.query));params['sslmode']='require'
    return urlunsplit((p.scheme,p.netloc,p.path,urlencode(params),p.fragment))

if __name__=='__main__':
    try:
        with psycopg.connect(remote_url(),connect_timeout=15) as conn:
            print('Render connection: OK')
            for name in ['source','process','flow','process_flow','unit','location','lci_exchange']:
                print(name,conn.execute(f'SELECT count(*) FROM {name}').fetchone()[0])
            print('Sources:',json.dumps(conn.execute('SELECT src_code FROM source ORDER BY src_code').fetchall()))
    except Exception as exc:
        print('Render connection failed:',type(exc).__name__)
        raise SystemExit(1)
