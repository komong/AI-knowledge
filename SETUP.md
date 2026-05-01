# 安装与接入

## 1. 启动 Qdrant

```bash
cd knowledge-mcp
docker compose up -d
```

确认起来了：`curl http://localhost:6333/collections` 应该返回 JSON。

## 2. 安装 Python 依赖

推荐用 [uv](https://github.com/astral-sh/uv)，比 pip 快很多：

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

或者用传统 pip：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

> 首次 import `FlagEmbedding` 时会下载 BGE-M3 模型（~2GB）到 `~/.cache/huggingface/`，
> 这是一次性的。之后完全离线。

## 3. 验证

```bash
# 起一条测试草稿
python -c "
from src.server import draft_memory
print(draft_memory(
    problem='Python asyncio 中 task 被 cancel 后 finally 块执行顺序',
    solution='cancel() 会在下一个 await 点抛 CancelledError，finally 块会执行。如果 finally 里有 await，必须用 shield 保护否则会被再次 cancel。',
    context='Python 3.11 + asyncio',
    languages=['python'],
    tags=['async', 'gotcha']
))
"

# 入库
python -m scripts.commit

# 检索
python -c "
from src.store import Store
import json
print(json.dumps(Store().search('async cancel 资源清理'), ensure_ascii=False, indent=2))
"
```

## 4. 接入 Claude Code

编辑 `~/.config/claude/claude_desktop_config.json`（macOS 是 `~/Library/Application Support/Claude/claude_desktop_config.json`），
或者用 `claude mcp add` 命令。最简单的做法是直接编辑配置文件加入：

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "/绝对路径/knowledge-mcp/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/绝对路径/knowledge-mcp",
      "env": {
        "QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
```

## 5. 接入 Cursor

Cursor 在 Settings → MCP 里加：

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "/绝对路径/knowledge-mcp/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/绝对路径/knowledge-mcp"
    }
  }
}
```

## 6. 接入 Claude Desktop

同 Claude Code，配置文件位置：
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

## 7. 同步到其他机器

`drafts/` 目录用 git 跟踪即可：

```bash
git init
git add drafts/ src/ scripts/ pyproject.toml docker-compose.yml README.md SETUP.md .gitignore AGENT_GUIDE.md
git commit -m "init"
git remote add origin <你的私有仓库>
git push
```

新机器拉下来后跑 `python -m scripts.reindex --confirm` 重建向量库即可。

## 8. 让 agent 自动用起来

把 `AGENT_GUIDE.md` 的内容复制到你的 `CLAUDE.md` / `.cursorrules` / Claude Desktop 的 system prompt 里，
agent 就会主动调用 search 和 draft 工具。
