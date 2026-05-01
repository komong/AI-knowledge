好，配置确定了。我直接把整套东西给你搭出来。

技术栈最终是：**Qdrant（Docker 本地）+ BGE-M3（本地 embedding）+ Python MCP Server + Markdown 草稿池 + Git 同步**。

这是说明文档。你先保存在本地一份md文档，然后你理解理解

我先把所有文件创建好，再讲怎么用。完整方案已经搭好，下载 `knowledge-mcp.zip` 解压即可。

## 整体设计回顾

四层结构对应你的三个需求：

| 你的需求 | 对应实现 |
|---|---|
| 跨工具共享 | MCP 协议，Claude Code / Cursor / Claude Desktop 都能接 |
| 本地优先 + 可同步 | Qdrant 跑 Docker，drafts 用 Git 同步，新机器 reindex 重建向量 |
| Agent 起草 + 我审核 | `draft_memory` 写 markdown 草稿，命令行 `commit` 才入库 |

## 关键的几个设计点

**1. 草稿用 markdown + frontmatter**，不是直接写库。这样你审核时就是改普通文本，IDE 里就能编辑，git diff 也清楚。这是"审核"环节能持续运转的关键。

**2. embedding 文本对 problem 加权**（在 `store.py` 的 `embedding_text` 里 problem 重复一次）。因为查询时你是用问题搜，不是用解搜，加权能显著提升检索准确度。

**3. `AGENT_GUIDE.md` 是飞轮的引擎**。光有工具不够，agent 不会自己想到去查、去存。这份 prompt 明确告诉它"什么时候查、什么时候存、什么不该存"。一定要塞进 `CLAUDE.md` 或 `.cursorrules`。

**4. `commit_memory` 故意不暴露给 agent**。入库只能你手动跑命令，这是"审核"这道闸的物理保证 —— 不是靠 agent 自觉，是它根本调不到。

## 启动顺序

```bash
docker compose up -d        # 起 Qdrant
uv venv && source .venv/bin/activate
uv pip install -e .         # 装依赖（首次会下 BGE-M3 ~2GB）
# 配置 MCP（见 SETUP.md 第 4-6 节）
# 把 AGENT_GUIDE.md 内容复制进 CLAUDE.md
```

## 几个你之后可能会想做的扩展

- **混合检索**：BGE-M3 同时支持 sparse 向量，启用后能让"精确关键词"（比如错误码、API 名）匹配更准。改 `embedder.py` 里的 `return_sparse=True` 就能开始。
- **去重/合并**：草稿越来越多后，加一个 `scripts/dedupe.py`，对相似度 > 0.9 的旧条目提示合并。
- **使用频率追踪**：在 payload 里加 `last_used_at` 和 `use_count`，在 `search_memory` 命中后更新，长期没用的可以归档。

有跑起来后遇到的问题随时告诉我，我帮你调。
