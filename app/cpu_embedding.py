"""Quantized MiniLM inference without importing PyTorch into the web process."""
from pathlib import Path
from threading import Lock
import numpy as np
import onnxruntime as ort
import sentencepiece as spm

class CpuEmbedding:
    def __init__(self, model_path):
        path = Path(model_path)
        self.tokenizer = spm.SentencePieceProcessor(model_file=str(path / 'sentencepiece.bpe.model'))
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
        # XLM-R aligns SentencePiece IDs with Fairseq: unknown=3, other
        # normal pieces offset by one, and wraps each query in <s> / </s>.
        tokens = [[0] + [3 if token == 0 else token + 1
                         for token in self.tokenizer.encode(text, out_type=int)[:126]] + [2]
                  for text in texts]
        width = max(map(len, tokens))
        inputs = {
            'input_ids': np.asarray([t + [1] * (width-len(t)) for t in tokens], dtype=np.int64),
            'attention_mask': np.asarray([[1] * len(t) + [0] * (width-len(t)) for t in tokens], dtype=np.int64),
            'token_type_ids': np.zeros((len(tokens), width), dtype=np.int64),
        }
        names = {i.name for i in self.session.get_inputs()}
        with self.lock:
            hidden = self.session.run(None, {k:v for k,v in inputs.items() if k in names})[0]
        mask = inputs['attention_mask'][..., None]
        pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
        return pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
