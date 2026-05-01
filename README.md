# Knowledge MCP — 开发经验复利知识库

一个跨 IDE / agent 共享的本地知识库，用 MCP 协议接入 Claude Code、Cursor、Claude Desktop 等。

## 设计理念

**复利飞轮**：每次解决问题 → agent 起草记忆 → 你审核 → 入库 → 下次自动检索复用。

## 架构

```
开发中遇到问题
    ↓
agent 调用 draft_memory(problem, solution, tags, language)
    ↓
草稿写入 drafts/*.md（人类可读的 markdown）
    ↓
你 review（可以让 Claude 帮你批量过）
    ↓
运行 commit 命令 → 向量化 → 存入 Qdrant
    ↓
下次开发时 agent 调用 search_memory(query) 检索
```

## 目录结构

```
knowledge-mcp/
├── docker-compose.yml      # Qdrant 本地实例
├── pyproject.toml          # Python 依赖
├── src/
│   ├── server.py           # MCP server 主入口
│   ├── embedder.py         # BGE-M3 本地 embedding
│   └── store.py            # Qdrant 读写封装
├── scripts/
│   ├── commit.py           # 草稿 → 向量库
│   └── reindex.py          # 全量重建索引
├── drafts/                 # 待审核的草稿（git 跟踪）
└── data/                   # Qdrant 持久化数据（git 忽略）
```

## 快速开始

见 SETUP.md
