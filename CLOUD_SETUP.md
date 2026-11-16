# Cloud deployment

The active Render service uses `app.main:app`, the `local_model` backend, a quantized ONNX version of multilingual MiniLM and a PostgreSQL snapshot containing `semantic_local_documents` with 384-dimensional vectors. The public demo uses a snapshot of 42,599 verified exchanges from 22 sources, checked on 16 November 2026.

Build: `pip install -r requirements-cloud.txt && python scripts/download_cloud_model.py`

Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Configure `DATABASE_URL`, `SEARCH_BACKEND=local_model`, `CLOUD_SNAPSHOT_SCHEMA`, `LOCAL_MODEL_PATH`, `OMP_NUM_THREADS=1` and `TOKENIZERS_PARALLELISM=false` in the Render service. Configure `GEMINI_API_KEY` for the RAG answer. Keep credentials in the service environment.

The older Gemini embedding notebook and scripts use a separate 768-dimensional index. They do not build the current 384-dimensional index. Creating a fresh database requires importing and validating the CSV data, generating compatible embeddings and preparing a snapshot before using this backend.