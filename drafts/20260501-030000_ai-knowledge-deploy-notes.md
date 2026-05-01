---
problem: "AI Knowledge 项目在 Windows+WSL 混合环境下部署时遇到的问题和解决方案"
languages: ["python", "yaml"]
tags: ["deployment", "windows", "wsl", "docker", "huggingface"]
created_at: "2026-05-01T03:00:00Z"
status: draft
---

# 问题

AI Knowledge 项目（Qdrant + BGE-M3 + MCP Server）在 Windows 宿主 + WSL Docker 的混合环境下部署遇到的问题。

# 场景

Windows 11 + WSL2 Ubuntu，Docker 仅安装在 WSL 内。Python MCP Server 运行在 Windows，Qdrant 运行在 WSL Docker。

# 解决方案

**1. Docker 在 WSL 不在 Windows**
- WSL Docker daemon 运行时，Windows 端通过 `wsl sudo docker` 调用
- WSL2 自动转发 localhost，Windows 访问 `localhost:6333` 直通 WSL 容器
- 启动命令：`echo "password" | wsl sudo -S docker compose up -d`
- 用户 nigel 不在 docker 组，必须用 sudo

**2. HuggingFace 国内无法直连，用镜像**
- 设置环境变量 `HF_ENDPOINT=https://hf-mirror.com`
- 否则 BGE-M3 模型下载会 ConnectTimeout
- 所有调用 embedder 的脚本都需要这个环境变量

**3. snapshot_download 遇到 .DS_Store 403 错误**
- hf-mirror.com 对某些文件返回 403
- 解决：`snapshot_download('BAAI/bge-m3', ignore_patterns=['*.DS_Store', 'imgs/*'])`

**4. 目录结构需要 src/ + scripts/**
- zip 解压后文件在根目录，但代码期望 src/store.py、scripts/commit.py
- 需要手动移动文件并创建 src/__init__.py

**5. Windows 用 py 启动器而非 python 命令**
- `py --version` 而非 `python --version`
- uv 安装后路径在 `$env:USERPROFILE\.local\bin\uv.exe`
