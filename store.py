"""Qdrant 读写封装。

Schema 设计（针对多语言开发场景）:
- problem: 问题描述（核心可检索字段）
- solution: 解决方案
- context: 触发场景（什么项目、什么栈下遇到的）
- language: 编程语言 tag（python/ts/go/rust/...）；多语言场景用列表
- tags: 自由标签
- source_file: 来源草稿文件名
- created_at: ISO 时间戳
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .embedder import EMBED_DIM, embed_text, embed_texts

COLLECTION = "dev_memory"


class Memory(BaseModel):
    id: str
    problem: str
    solution: str
    context: str = ""
    languages: List[str] = []
    tags: List[str] = []
    source_file: str = ""
    created_at: str = ""

    @classmethod
    def new(cls, **kwargs) -> "Memory":
        return cls(
            id=str(uuid.uuid4()),
            created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            **kwargs,
        )

    def embedding_text(self) -> str:
        """构造用于 embedding 的文本。

        把 problem 加权（重复一次）让检索更偏向问题匹配，
        因为查询时通常是『我遇到了 X』而不是『我有解 Y』。
        """
        parts = [
            f"问题: {self.problem}",
            f"问题: {self.problem}",  # 加权
            f"场景: {self.context}" if self.context else "",
            f"解决方案: {self.solution}",
            f"标签: {', '.join(self.tags)}" if self.tags else "",
            f"语言: {', '.join(self.languages)}" if self.languages else "",
        ]
        return "\n".join(p for p in parts if p)


class Store:
    def __init__(self, url: str = "http://localhost:6333"):
        self.client = QdrantClient(url=url)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        existing = {c.name for c in self.client.get_collections().collections}
        if COLLECTION in existing:
            return
        self.client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(
                size=EMBED_DIM,
                distance=qm.Distance.COSINE,
            ),
        )
        # 给常用过滤字段建索引，加速 filter 查询
        for field, schema in [
            ("languages", qm.PayloadSchemaType.KEYWORD),
            ("tags", qm.PayloadSchemaType.KEYWORD),
        ]:
            self.client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field,
                field_schema=schema,
            )

    def upsert(self, memories: List[Memory]) -> int:
        if not memories:
            return 0
        vectors = embed_texts([m.embedding_text() for m in memories])
        points = [
            qm.PointStruct(id=m.id, vector=vec, payload=m.model_dump())
            for m, vec in zip(memories, vectors)
        ]
        self.client.upsert(collection_name=COLLECTION, points=points)
        return len(points)

    def search(
        self,
        query: str,
        limit: int = 5,
        languages: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[dict]:
        vec = embed_text(query)
        must = []
        if languages:
            must.append(qm.FieldCondition(
                key="languages",
                match=qm.MatchAny(any=languages),
            ))
        if tags:
            must.append(qm.FieldCondition(
                key="tags",
                match=qm.MatchAny(any=tags),
            ))
        flt = qm.Filter(must=must) if must else None

        results = self.client.query_points(
            collection_name=COLLECTION,
            query=vec,
            query_filter=flt,
            limit=limit,
            with_payload=True,
        ).points

        return [
            {"score": round(r.score, 4), **r.payload}
            for r in results
        ]

    def delete(self, memory_id: str) -> None:
        self.client.delete(
            collection_name=COLLECTION,
            points_selector=qm.PointIdsList(points=[memory_id]),
        )

    def count(self) -> int:
        return self.client.count(collection_name=COLLECTION).count
