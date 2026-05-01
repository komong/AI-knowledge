# AI Knowledge 项目

## 项目定位

个人开发经验复利知识库，通过 MCP 协议接入 Claude Code、Cursor、Claude Desktop 等 AI 工具。

## 核心价值

**复利飞轮**：每次解决问题 → agent 起草记忆 → 审核入库 → 下次自动检索复用。

## 技术栈

| 组件 | 版本 | 作用 |
|------|------|------|
| Qdrant | Docker | 向量数据库，本地存储 |
| BGE-M3 | FlagEmbedding | 本地 embedding，离线运行 |
| MCP Server | Python | 提供 search_memory / draft_memory 工具 |
| Markdown | drafts/*.md | 草稿池，Git 同步 |

## 架构四层

```
┌─────────────┐  MCP 协议   ┌─────────────┐
│ Claude Code │  ────────→  │ MCP Server  │
│ Cursor      │             │ (Python)   │
│ Claude Desk │             └──────┬──────┘
└─────────────┘                    ↓
                         ┌────────┴────────┐
                         │ BGE-M3 Embedder │
                         └────────┬────────┘
                                  ↓
                         ┌────────┴────────┐
                         │ Qdrant VectorDB  │
                         └────────────────┘
```

## 工作流程

```
1. 遇到开发问题
   ↓
2. agent 调用 draft_memory(problem, solution, tags)
   ↓
3. 草稿写入 drafts/*.md（人类可读的 markdown）
   ↓
4. 你 review 审核（可批量处理）
   ↓
5. 运行 commit 命令 → 向量化 → 存入 Qdrant
   ↓
6. 下次开发时 agent 调用 search_memory(query) 检索
```

## 目录结构

```
knowledge-mcp/
├── docker-compose.yml   # Qdrant 本地实例配置
├── pyproject.toml     # Python 依赖
├── src/
│   ├── server.py      # MCP server 主入口
│   ├── embedder.py   # BGE-M3 embedding 封装
│   └── store.py      # Qdrant 读写封装
├── scripts/
│   ├── commit.py    # 草稿 → 向量库
│   └── reindex.py   # 全量重建索引
├── drafts/          # 待审核草稿（Git 跟踪）
└── data/qdrant/    # Qdrant 数据（Git 忽略）
```

## 关键设计

1. **problem 加权**：embedding 时 problem 重复一次，检索时用问题搜更准
2. **审核机制**：commit 命令不暴露给 agent，入库需你手动触发
3. **AGENT_GUIDE.md**：引导 agent 何时该查、何时该存

## 启动命令

```bash
# 1. 启动 Qdrant
docker compose up -d

# 2. 创建并激活虚拟环境
uv venv && source .venv/bin/activate

# 3. 安装依赖（首次约 2GB）
uv pip install -e .

# 4. 配置 MCP（见 SETUP.md）
# 5. 把 AGENT_GUIDE.md 复制到 CLAUDE.md
```

## 可用工具

- `knowledge-mcp`：MCP 服务器主命令
- `knowledge-commit`：草稿入库命令
- `knowledge-reindex`：全量重建索引命令