"""Download the same embedding model used by the local index at build time."""
from pathlib import Path
from huggingface_hub import hf_hub_download

path=Path(__file__).resolve().parents[1]/'models'/'lci-embedding'
path.parent.mkdir(parents=True,exist_ok=True)
repo='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
for filename in ['onnx/model_quint8_avx2.onnx','sentencepiece.bpe.model']:
    hf_hub_download(repo,filename,revision='a3ded7f',local_dir=path)
print('Cloud embedding model saved; inference does not require Gemini tokens')
