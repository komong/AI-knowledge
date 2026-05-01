"""从 drafts/_committed 全量重建索引。

适用场景:
- 换了 embedding 模型
- Qdrant 数据损坏
- 迁移到新机器

用法:
    python -m scripts.reindex --confirm
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.commit import parse_draft  # noqa: E402
from src.store import COLLECTION, Store  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "drafts" / "_committed"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="确认要清空并重建")
    args = parser.parse_args()

    if not args.confirm:
        print("这会清空 Qdrant 中的 dev_memory collection 并从归档重建。")
        print("确认请加 --confirm")
        return

    files = sorted(ARCHIVE_DIR.glob("*.md"))
    print(f"找到 {len(files)} 个归档草稿")

    store = Store()
    store.client.delete_collection(COLLECTION)
    store = Store()  # 重新创建 collection

    memories = []
    for f in files:
        try:
            memories.append(parse_draft(f))
        except Exception as e:
            print(f"跳过 {f.name}: {e}")

    n = store.upsert(memories)
    print(f"✓ 重建完成，{n} 条")


if __name__ == "__main__":
    main()
