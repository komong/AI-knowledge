"""轻量 Web UI 后端。

启动: python -m ui.app
访问: http://localhost:8765

API:
- GET  /api/stats              统计信息
- GET  /api/search?q=...       语义搜索已入库内容
- GET  /api/memories           分页浏览已入库
- DELETE /api/memories/{id}    删除一条
- GET  /api/drafts             列出草稿
- GET  /api/drafts/{filename}  读取草稿原文
- PUT  /api/drafts/{filename}  保存草稿编辑
- DELETE /api/drafts/{filename} 删除草稿
- POST /api/drafts/{filename}/commit  入库一条草稿
- POST /api/drafts/commit-all  批量入库所有草稿
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

import frontmatter
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from qdrant_client.http import models as qm

# 让 ui 模块能 import src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.commit import parse_draft  # noqa: E402
from src.store import COLLECTION, Store  # noqa: E402

ROOT = Path(__file__).resolve().parent
DRAFTS_DIR = Path(os.getenv("KNOWLEDGE_DRAFTS_DIR", ROOT / "drafts"))
ARCHIVE_DIR = DRAFTS_DIR / "_committed"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Knowledge UI")
_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        # 空字符串或未设置则走本地文件模式，与 server.py 保持一致
        url = os.getenv("QDRANT_URL")
        _store = Store(url=url if url else None)
    return _store


# ───────────── stats ─────────────

@app.get("/api/stats")
def stats():
    store = get_store()
    drafts = [p for p in DRAFTS_DIR.glob("*.md") if p.is_file()]
    archived = list(ARCHIVE_DIR.glob("*.md")) if ARCHIVE_DIR.exists() else []
    return {
        "indexed": store.count(),
        "drafts_pending": len(drafts),
        "drafts_committed": len(archived),
        "drafts_dir": str(DRAFTS_DIR),
    }


# ───────────── search ─────────────

@app.get("/api/search")
def search(q: str, limit: int = 10, lang: Optional[str] = None, tag: Optional[str] = None):
    if not q.strip():
        return {"results": []}
    store = get_store()
    languages = [lang] if lang else None
    tags = [tag] if tag else None
    return {"results": store.search(q, limit=limit, languages=languages, tags=tags)}


# ───────────── memories（已入库） ─────────────

@app.get("/api/memories")
def list_memories(offset: int = 0, limit: int = 20):
    """分页浏览已入库的所有记忆。"""
    store = get_store()
    points, _ = store.client.scroll(
        collection_name=COLLECTION,
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=False,
    )
    return {
        "total": store.count(),
        "items": [{"id": str(p.id), **p.payload} for p in points],
    }


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str):
    get_store().delete(memory_id)
    return {"status": "deleted", "id": memory_id}


# ───────────── drafts ─────────────

class DraftPayload(BaseModel):
    content: str  # 整个 markdown 文件内容（含 frontmatter）


def _safe_draft_path(filename: str) -> Path:
    """防止路径逃逸。"""
    p = (DRAFTS_DIR / filename).resolve()
    if not p.is_relative_to(DRAFTS_DIR.resolve()):
        raise HTTPException(400, "非法路径")
    return p


@app.get("/api/drafts")
def list_drafts():
    drafts = sorted(
        (p for p in DRAFTS_DIR.glob("*.md") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    items = []
    for p in drafts:
        try:
            post = frontmatter.load(p)
            items.append({
                "filename": p.name,
                "problem": post.metadata.get("problem", ""),
                "languages": post.metadata.get("languages", []),
                "tags": post.metadata.get("tags", []),
                "created_at": post.metadata.get("created_at", ""),
                "size": p.stat().st_size,
            })
        except Exception as e:
            items.append({"filename": p.name, "error": str(e)})
    return {"items": items}


@app.get("/api/drafts/{filename}")
def read_draft(filename: str):
    p = _safe_draft_path(filename)
    if not p.exists():
        raise HTTPException(404, "草稿不存在")
    return {"filename": filename, "content": p.read_text(encoding="utf-8")}


@app.put("/api/drafts/{filename}")
def update_draft(filename: str, payload: DraftPayload):
    p = _safe_draft_path(filename)
    if not p.exists():
        raise HTTPException(404, "草稿不存在")
    # 简单校验 frontmatter 合法
    try:
        frontmatter.loads(payload.content)
    except Exception as e:
        raise HTTPException(400, f"frontmatter 格式错误: {e}")
    p.write_text(payload.content, encoding="utf-8")
    return {"status": "saved"}


@app.delete("/api/drafts/{filename}")
def delete_draft(filename: str, reason: str = ""):
    p = _safe_draft_path(filename)
    if not p.exists():
        raise HTTPException(404, "草稿不存在")
    p.unlink()
    if reason:
        print(f"[discard] {filename} — {reason}")
    return {"status": "deleted"}


@app.post("/api/drafts/{filename}/commit")
def commit_draft(filename: str):
    p = _safe_draft_path(filename)
    if not p.exists():
        raise HTTPException(404, "草稿不存在")
    try:
        mem = parse_draft(p)
    except Exception as e:
        raise HTTPException(400, f"草稿格式错误: {e}")

    store = get_store()
    store.upsert([mem])

    ARCHIVE_DIR.mkdir(exist_ok=True)
    shutil.move(str(p), str(ARCHIVE_DIR / p.name))
    return {"status": "committed", "id": mem.id}


@app.post("/api/drafts/commit-all")
def commit_all():
    files = sorted(p for p in DRAFTS_DIR.glob("*.md") if p.is_file())
    if not files:
        return {"committed": 0, "errors": []}

    memories, errors = [], []
    file_by_name = {f.name: f for f in files}
    for f in files:
        try:
            memories.append(parse_draft(f))
        except Exception as e:
            errors.append({"file": f.name, "error": str(e)})

    if memories:
        get_store().upsert(memories)
        ARCHIVE_DIR.mkdir(exist_ok=True)
        for m in memories:
            src = file_by_name.get(m.source_file)
            if src and src.exists():
                shutil.move(str(src), str(ARCHIVE_DIR / src.name))

    return {"committed": len(memories), "errors": errors}


# ───────────── 静态文件 ─────────────

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main():
    import uvicorn
    port = int(os.getenv("UI_PORT", "8765"))
    print(f"\n知识库 UI 启动中...")
    print(f"草稿目录: {DRAFTS_DIR}")
    print(f"打开浏览器访问: http://localhost:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
