"""Refresh changed validation text and vectors after database verification."""
import json
import os
import numpy as np
import psycopg
from local_demo import INDEX, DATABASE_URL, model

with psycopg.connect(DATABASE_URL) as conn:
    statuses=dict(conn.execute('SELECT exchange_id,validation_status FROM lci_exchange').fetchall())
with np.load(INDEX,allow_pickle=False) as f:
    vectors=f['vectors'];docs=[json.loads(x) for x in f['documents']]
changed=[]
for i,doc in enumerate(docs):
    status=statuses.get(doc['entity_id'])
    if status and not doc['content'].endswith('สถานะ '+status):
        doc['content']=doc['content'].rsplit('สถานะ ',1)[0]+'สถานะ '+status
        changed.append(i)
if changed:
    vectors[changed]=model().encode([docs[i]['content'] for i in changed],batch_size=32,normalize_embeddings=True,show_progress_bar=True,convert_to_numpy=True)
    tmp=INDEX.with_name('local_lci_index_verified.npz')
    np.savez_compressed(tmp,vectors=vectors,documents=np.array([json.dumps(d,ensure_ascii=False) for d in docs]))
    os.replace(tmp,INDEX)
print('Updated indexed records:',len(changed))
