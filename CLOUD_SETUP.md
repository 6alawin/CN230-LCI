# Cloud CPU Semantic Search

This deployment uses the same multilingual MiniLM model and 384-D vectors as the local app. Embedding inference runs on the service CPU and does not call Gemini.

## Versioned data snapshot

The prepared upload creates a new Render schema `lci_verified_20261115` containing the verified Local corpus (40,721 Exchange records, 21 Sources), related reference tables, import log, and 40,721 384-D embedding vectors. Existing public tables remain untouched. `scripts/upload_cloud_snapshot.py` refuses to overwrite an existing snapshot schema.

Uploaded and verified on 2026-11-15: 40,721 unique exchange IDs, 21 sources, and 40,721 vectors of dimension 384. Both unfiltered search and SRC-21 filtered retrieval passed against Render. `scripts/verify_cloud_snapshot.py` repeats these checks. Quantized/original query-vector cosine similarities on four Thai/English examples were 0.9960–0.9980. Development Windows memory for the web imports plus encoder after a maximum-length query was about 465 MiB; actual Linux hosting memory must also be verified.

## Render settings

Build command:

```sh
pip install -r requirements-cloud.txt && python scripts/download_cloud_model.py
```

Start command:

```sh
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set `SEARCH_BACKEND=local_model`, `CLOUD_SNAPSHOT_SCHEMA=lci_verified_20261115`, `LOCAL_MODEL_PATH=models/lci-embedding`, `OMP_NUM_THREADS=1`, and `TOKENIZERS_PARALLELISM=false`. Keep DATABASE_URL in Render secrets. `render-cloud.yaml` is an alternative blueprint for a separate service.

The current service remains on the previous search backend until these settings are applied. CPU/RAM capacity and hosting costs still apply; this is not unlimited free compute. Check memory on the chosen plan before switching production traffic.

The web runtime uses the publisher's ONNX AVX2 uint8 version, with masked mean pooling, length 128, and L2 normalization. This avoids loading PyTorch into the server. Existing 384-D full-precision document embeddings remain compatible with the same model's quantized query encoder; quantization can slightly change ranking. Validate query similarity and memory before enabling it. Original PyTorch inference measured about 1.1 GB RAM on the development machine.

## RAG

The Local Ollama service at 127.0.0.1 is not reachable from Render. This deployment supplies Semantic Search only, as the existing Render API did. Cloud RAG requires a separately hosted generation model or an external generation provider. Do not label the Cloud endpoint as full offline RAG.
