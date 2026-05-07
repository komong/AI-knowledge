"""
scripts/sync_embed.py

功能：扫描 drafts/_committed/ 目录，找出还没有 embed 进 Qdrant 的词条，
      补跑 embed 并写入 Qdrant。

使用方式：
    cd /你的知识库根目录
    python scripts/sync_embed.py

配合 sync.sh 使用：
    git pull && python scripts/sync_embed.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# 把项目根目录加入 sys.path，确保能 import src.*
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.store import Memory, Store

# ── 常量 ────────────────────────────────────────────────────────────────────
COMMITTED_DIR = ROOT / "drafts" / "_committed"
SYNC_RECORD   = ROOT / "data" / ".synced_files.json"   # 记录已 embed 的文件


# ── 已同步记录 ───────────────────────────────────────────────────────────────
def load_synced() -> set[str]:
    """读取已经 embed 过的文件名集合。"""
    if SYNC_RECORD.exists():
        return set(json.loads(SYNC_RECORD.read_text(encoding="utf-8")))
    return set()


def save_synced(synced: set[str]) -> None:
    SYNC_RECORD.parent.mkdir(parents=True, exist_ok=True)
    SYNC_RECORD.write_text(
        json.dumps(sorted(synced), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Markdown 解析 ────────────────────────────────────────────────────────────
def parse_md(path: Path) -> Memory | None:
    """
    从 _committed/ 下的 Markdown 文件解析出 Memory 对象。

    支持两种格式：
    1. 标准 frontmatter（--- yaml ---）
    2. #/## 标题段落格式（# 问题 / ## 解决方案 / # 场景 等）
    """
    text = path.read_text(encoding="utf-8")

    # ── 尝试解析 frontmatter ──────────────────────────────────────────────
    fm_match = re.match(r"^---\n(.+?)\n---\n(.*)$", text, re.DOTALL)
    if fm_match:
        try:
            import yaml  # 仅在有 frontmatter 时才需要
            meta = yaml.safe_load(fm_match.group(1))
            body = fm_match.group(2).strip()
            return Memory.new(
                problem   = meta.get("problem", ""),
                solution  = meta.get("solution", body),
                context   = meta.get("context", ""),
                languages = _to_list(meta.get("languages") or meta.get("language")),
                tags      = _to_list(meta.get("tags")),
                source_file = path.name,
            )
        except Exception:
            pass  # frontmatter 解析失败，fallback 到标题模式

    # ── 按 #/## 标题段落解析 ──────────────────────────────────────────────
    sections: dict[str, str] = {}
    current_key = None
    lines = text.splitlines()
    for line in lines:
        heading = re.match(r"^#{1,2}\s+(.+)", line)
        if heading:
            current_key = heading.group(1).strip()
            sections[current_key] = ""
        elif current_key is not None:
            sections[current_key] += line + "\n"

    # 字段映射（兼容中英文标题）
    problem  = _pick(sections, ["问题", "Problem", "problem"]).strip()
    solution = _pick(sections, ["解决方案", "Solution", "solution"]).strip()
    context  = _pick(sections, ["场景", "Context", "context", "触发场景"]).strip()
    tags_raw = _pick(sections, ["标签", "Tags", "tags"]).strip()
    lang_raw = _pick(sections, ["语言", "Language", "languages"]).strip()

    if not problem and not solution:
        print(f"  ⚠ 跳过（无法解析）: {path.name}")
        return None

    # 如果连 problem 都没有，用文件名兜底
    if not problem:
        problem = path.stem

    return Memory.new(
        problem     = problem,
        solution    = solution,
        context     = context,
        languages   = _parse_inline_list(lang_raw),
        tags        = _parse_inline_list(tags_raw),
        source_file = path.name,
    )


# ── 工具函数 ─────────────────────────────────────────────────────────────────
def _to_list(val) -> list[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(v).strip() for v in val if v]
    return [s.strip() for s in str(val).split(",") if s.strip()]


def _pick(d: dict, keys: list[str]) -> str:
    for k in keys:
        if k in d:
            return d[k]
    return ""


def _parse_inline_list(raw: str) -> list[str]:
    """把 'python, ts, go' 或 '- python\n- ts' 解析成列表。"""
    if not raw:
        return []
    # 去掉 markdown 列表符号
    raw = re.sub(r"^\s*[-*]\s+", "", raw, flags=re.MULTILINE)
    items = re.split(r"[,\n]+", raw)
    return [i.strip() for i in items if i.strip()]


# ── 主流程 ───────────────────────────────────────────────────────────────────
def main() -> None:
    if not COMMITTED_DIR.exists():
        print(f"❌ 目录不存在: {COMMITTED_DIR}")
        sys.exit(1)

    md_files = sorted(COMMITTED_DIR.glob("*.md"))
    if not md_files:
        print("✅ _committed/ 目录为空，无需同步。")
        return

    synced  = load_synced()
    pending = [f for f in md_files if f.name not in synced]

    if not pending:
        print(f"✅ 所有 {len(md_files)} 条词条已是最新，无需同步。")
        return

    print(f"📥 发现 {len(pending)} 条待同步词条：")
    for f in pending:
        print(f"   - {f.name}")

    # 解析
    memories: list[Memory] = []
    for f in pending:
        print(f"\n🔍 解析: {f.name}")
        m = parse_md(f)
        if m:
            memories.append(m)
            print(f"   问题: {m.problem[:60]}{'...' if len(m.problem) > 60 else ''}")

    if not memories:
        print("\n⚠ 没有可解析的词条，退出。")
        return

    # Embed + 写入 Qdrant
    print(f"\n🚀 开始 embed，共 {len(memories)} 条（首次加载模型约需 10-30 秒）...")
    store = Store()
    count = store.upsert(memories)
    print(f"✅ 成功写入 Qdrant: {count} 条")

    # 更新同步记录
    synced.update(f.name for f in pending[:len(memories)])
    save_synced(synced)

    # 汇总
    print(f"\n📊 当前 Qdrant 总词条数: {store.count()}")
    print("🎉 同步完成！")


if __name__ == "__main__":
    main()
