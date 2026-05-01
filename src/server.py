"""MCP Server: 把知识库能力暴露给 Claude Code / Cursor / Claude Desktop。

提供的工具:
- search_memory: 检索历史经验（agent 遇到问题时主动调用）
- draft_memory:  起草一条新经验（agent 解决问题后主动调用，写入草稿池）
- list_drafts:   列出待审核草稿
- read_draft:    读取某条草稿全文
- stats:         库存量统计

注意: commit_memory 不暴露给 agent —— 入库必须经过你审核后用命令行执行。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .store import Store

# 草稿目录默认在项目根，可用环境变量覆盖（方便用户把草稿放到自己同步的目录）
DRAFTS_DIR = Path(os.getenv(
    "KNOWLEDGE_DRAFTS_DIR",
    Path(__file__).resolve().parent.parent / "drafts",
))
DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

mcp = FastMCP("knowledge")
_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store(url=QDRANT_URL)
    return _store


def _slugify(text: str, max_len: int = 50) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", text).strip()
    text = re.sub(r"\s+", "-", text)
    return text[:max_len] or "untitled"


@mcp.tool()
def search_memory(
    query: str,
    limit: int = 5,
    languages: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """检索历史开发经验。

    使用时机: 当遇到一个问题、bug、设计决策时，先调用这个工具看看以前是否
    遇到过类似情况。即使不完全匹配，相关经验也常常有启发。

    Args:
        query: 自然语言问题描述，越具体越好。例如 "Python asyncio 中 cancel 后清理资源" 比 "异步问题" 更好。
        limit: 返回结果数，默认 5
        languages: 按编程语言过滤，例如 ["python", "typescript"]
        tags: 按标签过滤，例如 ["debugging", "performance"]

    Returns:
        JSON 字符串，包含匹配的经验列表（按相似度排序），每条含 problem / solution / context / score。
    """
    store = get_store()
    results = store.search(query, limit=limit, languages=languages, tags=tags)
    if not results:
        return json.dumps({
            "results": [],
            "hint": "知识库中暂无相关经验，解决后记得调用 draft_memory 沉淀。",
        }, ensure_ascii=False, indent=2)
    return json.dumps({"results": results}, ensure_ascii=False, indent=2)


@mcp.tool()
def draft_memory(
    problem: str,
    solution: str,
    context: str = "",
    languages: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """起草一条新的开发经验，写入草稿池等待用户审核。

    使用时机: 当你刚解决了一个值得复用的问题时调用。判断标准：
    - 这个解法非显然（搜不到或踩了坑才找到的）
    - 未来很可能再遇到类似情况
    - 涉及项目特定的约定、陷阱、性能优化、调试技巧

    不要为琐碎事项起草（比如修个 typo、加个明显的 import）。

    Args:
        problem: 问题的精确描述。写成"未来的我搜什么关键词能找到这条"的样子。
        solution: 解决方案。简洁但完整，包含关键代码片段和原理说明。
        context: 触发场景，例如 "Django 4.2 + Celery 6 + Redis broker"
        languages: 涉及的编程语言，例如 ["python"] 或 ["typescript", "python"]
        tags: 自由标签，例如 ["async", "memory-leak", "ci"]

    Returns:
        草稿文件路径和提示。
    """
    languages = languages or []
    tags = tags or []

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(problem)
    filename = f"{timestamp}_{slug}.md"
    filepath = DRAFTS_DIR / filename

    # 用 frontmatter + markdown 格式，人类可读、易编辑
    content = f"""---
problem: {json.dumps(problem, ensure_ascii=False)}
languages: {json.dumps(languages, ensure_ascii=False)}
tags: {json.dumps(tags, ensure_ascii=False)}
created_at: {datetime.utcnow().isoformat(timespec="seconds")}Z
status: draft
---

# 问题

{problem}

# 场景

{context or "_(未填写)_"}

# 解决方案

{solution}
"""
    filepath.write_text(content, encoding="utf-8")

    return json.dumps({
        "status": "drafted",
        "file": str(filepath),
        "next_step": "用户 review 后运行 `python -m scripts.commit` 入库",
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def list_drafts() -> str:
    """列出当前草稿池中所有待审核的经验。"""
    drafts = sorted(DRAFTS_DIR.glob("*.md"))
    items = [
        {"file": d.name, "size": d.stat().st_size, "modified": datetime.fromtimestamp(d.stat().st_mtime).isoformat(timespec="seconds")}
        for d in drafts
    ]
    return json.dumps({"count": len(items), "drafts": items}, ensure_ascii=False, indent=2)


@mcp.tool()
def read_draft(filename: str) -> str:
    """读取某条草稿的完整内容。"""
    filepath = DRAFTS_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        return json.dumps({"error": f"草稿不存在: {filename}"}, ensure_ascii=False)
    # 防止路径逃逸
    if DRAFTS_DIR.resolve() not in filepath.resolve().parents:
        return json.dumps({"error": "非法路径"}, ensure_ascii=False)
    return filepath.read_text(encoding="utf-8")


@mcp.tool()
def stats() -> str:
    """知识库统计信息：已入库条数、待审核草稿数。"""
    store = get_store()
    return json.dumps({
        "indexed": store.count(),
        "drafts_pending": len(list(DRAFTS_DIR.glob("*.md"))),
        "drafts_dir": str(DRAFTS_DIR),
        "qdrant": QDRANT_URL,
    }, ensure_ascii=False, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
