"""Compare the cloud query encoder with the original local encoder."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from app.cpu_embedding import CpuEmbedding

texts=['การปล่อยคาร์บอนจากการผลิตไฟฟ้า','การขนส่งน้ำมันดิบ','ก๊าซธรรมชาติในอุตสาหกรรม','electricity generation from coal']
quantized=CpuEmbedding('models/lci-embedding').encode(texts)
assert quantized.shape==(4,384)
assert np.isfinite(quantized).all()
assert np.allclose(np.linalg.norm(quantized,axis=1),1,atol=1e-5)
from sentence_transformers import SentenceTransformer
original=SentenceTransformer('models/lci-embedding',device='cpu',local_files_only=True).encode(texts,normalize_embeddings=True)
cosines=np.sum(quantized*original,axis=1)
print('Original/quantized cosine similarities:',cosines.round(4).tolist())
assert min(cosines)>0.98,cosines
print('Quantized encoder compatibility passed')
