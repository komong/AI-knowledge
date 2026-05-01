"""把 drafts/ 里的草稿读出来，向量化后存入 Qdrant，归档原文件。

用法:
    python -m scripts.commit                # 处理所有草稿
    python -m scripts.commit --file xxx.md  # 只处理某个文件
    python -m scripts.commit --dry-run      # 只打印不写入
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import frontmatter

# 让脚本能直接 python -m scripts.commit
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.store import Memory, Store  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DRAFTS_DIR = ROOT / "drafts"
ARCHIVE_DIR = ROOT / "drafts" / "_committed"


def parse_draft(filepath: Path) -> Memory:
    post = frontmatter.load(filepath)
    meta = post.metadata
    body = post.content

    # 从 markdown body 里提取 context 和 solution 段落
    context = _extract_section(body, "场景")
    solution = _extract_section(body, "解决方案")
    problem = meta.get("problem") or _extract_section(body, "问题")

    if not problem or not solution:
        raise ValueError(f"草稿缺少必要字段: {filepath.name}")

    return Memory.new(
        problem=problem.strip(),
        solution=solution.strip(),
        context=(context or "").strip(),
        languages=meta.get("languages", []) or [],
        tags=meta.get("tags", []) or [],
        source_file=filepath.name,
    )


def _extract_section(body: str, header: str) -> str:
    """从 markdown 中提取 # header 之后到下一个 # 之前的内容。"""
    lines = body.splitlines()
    capturing = False
    captured: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if capturing:
                break
            if header in stripped:
                capturing = True
                continue
        elif capturing:
            captured.append(line)
    text = "\n".join(captured).strip()
    return "" if text == "_(未填写)_" else text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="只处理指定的草稿文件名")
    parser.add_argument("--dry-run", action="store_true", help="只解析不入库")
    args = parser.parse_args()

    if args.file:
        files = [DRAFTS_DIR / args.file]
    else:
        files = sorted(p for p in DRAFTS_DIR.glob("*.md") if p.is_file())

    if not files:
        print("没有待入库的草稿。")
        return

    memories: list[Memory] = []
    for f in files:
        try:
            mem = parse_draft(f)
            memories.append(mem)
            print(f"✓ 解析: {f.name}")
            print(f"  problem: {mem.problem[:80]}")
            print(f"  languages: {mem.languages}, tags: {mem.tags}")
        except Exception as e:
            print(f"✗ 跳过 {f.name}: {e}")

    if args.dry_run:
        print(f"\n[dry-run] 将入库 {len(memories)} 条")
        return

    if not memories:
        return

    print(f"\n开始向量化并入库（首次会加载 BGE-M3 模型，需要点时间）...")
    store = Store()
    n = store.upsert(memories)
    print(f"✓ 入库 {n} 条")

    # 归档已提交的草稿
    ARCHIVE_DIR.mkdir(exist_ok=True)
    for mem in memories:
        src = DRAFTS_DIR / mem.source_file
        if src.exists():
            shutil.move(str(src), str(ARCHIVE_DIR / mem.source_file))
    print(f"✓ 已归档到 {ARCHIVE_DIR}")
    print(f"\n当前库存量: {store.count()}")


if __name__ == "__main__":
    main()
