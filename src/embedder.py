"""BGE-M3 本地 embedding 封装。

BGE-M3 选型理由:
- 中英文检索都强（你是多语言开发）
- 1024 维稠密向量，本地推理速度可接受
- 首次会下载 ~2GB 模型到 ~/.cache/huggingface
- 完全离线，隐私友好
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from FlagEmbedding import BGEM3FlagModel

MODEL_NAME = "BAAI/bge-m3"
EMBED_DIM = 1024


@lru_cache(maxsize=1)
def _get_model() -> BGEM3FlagModel:
    import torch
    use_fp16 = torch.cuda.is_available()
    return BGEM3FlagModel(MODEL_NAME, use_fp16=use_fp16)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """批量 embed，返回 dense 向量列表。"""
    if not texts:
        return []
    model = _get_model()
    output = model.encode(
        texts,
        batch_size=12,
        max_length=8192,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    return output["dense_vecs"].tolist()


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]
