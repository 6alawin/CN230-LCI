"""Quantized MiniLM inference without importing PyTorch into the web process."""
from pathlib import Path
from threading import Lock
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

class CpuEmbedding:
    def __init__(self, model_path):
        path = Path(model_path)
        self.tokenizer = Tokenizer.from_file(str(path / 'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=128)
        self.tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        options.add_session_config_entry('session.disable_prepacking', '1')
        self.session = ort.InferenceSession(
            str(path / 'onnx/model_quint8_avx2.onnx'), options,
            providers=['CPUExecutionProvider'])
        self.lock = Lock()

    def encode(self, texts, **kwargs):
        tokens = self.tokenizer.encode_batch(texts)
        inputs = {
            'input_ids': np.asarray([t.ids for t in tokens], dtype=np.int64),
            'attention_mask': np.asarray([t.attention_mask for t in tokens], dtype=np.int64),
            'token_type_ids': np.asarray([t.type_ids for t in tokens], dtype=np.int64),
        }
        names = {i.name for i in self.session.get_inputs()}
        with self.lock:
            hidden = self.session.run(None, {k:v for k,v in inputs.items() if k in names})[0]
        mask = inputs['attention_mask'][..., None]
        pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
        return pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
