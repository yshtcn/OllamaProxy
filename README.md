# Ollama Proxy

## 项目背景

随着大语言模型的普及，越来越多的个人用户选择在本地部署 Ollama 服务来使用 AI 模型。然而，这带来了一个普遍的问题：

- Ollama 通常需要部署在高性能台式机上（配备强大的GPU）
- 24小时开机运行会导致较高的电费支出
- 设置电脑定时睡眠可以节省电力，但会导致 Ollama 服务不可用
- 用户需要手动唤醒电脑才能继续使用服务

Ollama Proxy 正是为解决这个问题而设计：它允许用户在保持节能的同时，仍然可以随时便捷地使用 Ollama 服务。项目采用了两个关键策略来提升用户体验：

1. **智能唤醒机制**：通过请求管理，在需要时自动唤醒服务器，在空闲时允许系统进入睡眠状态，实现了服务可用性和节能环保的平衡。

2. **模型信息缓存**：即使在服务器处于睡眠状态时，也能立即响应模型列表查询请求。这意味着：
   - 用户可以随时查看可用的模型列表
   - 客户端应用无需等待服务器唤醒即可获取基本信息
   - 提供更流畅的用户体验，减少等待时间

通过这种设计，Ollama Proxy 不仅解决了节能问题，还确保了服务响应的及时性，为用户提供了一个既环保又高效的解决方案。

Ollama Proxy 是一个为 Ollama 服务设计的智能代理服务器，它提供了以下主要功能：

1. 自动唤醒功能
2. 请求转发
3. 模型列表缓存
4. 健康检查
5. 超时控制

## 主要特性

### 1. 自动唤醒功能
- 定期发送唤醒请求，防止 Ollama 服务进入休眠状态
- 可配置唤醒间隔时间
- 在请求超时时自动触发唤醒

### 2. 智能请求转发
- 支持所有 Ollama API 端点的请求转发
- 动态超时控制：对不同类型的请求使用不同的超时时间
  - 普通请求：可配置的短超时时间
  - 模型推理请求：较长的超时时间（默认30秒）

### 3. 模型列表缓存
- 缓存 `/api/tags` 接口返回的模型列表
- 缓存有效期为30分钟
- 当主服务不可用时返回缓存数据

### 4. 健康检查
- 提供 `/health` 端点进行健康状态检查
- Docker 容器集成了健康检查配置

## 配置参数

支持通过环境变量或命令行参数进行配置：

| 参数 | 环境变量 | 说明 | 默认值 |
|------|----------|------|--------|
| `--ollama-url` | `OLLAMA_URL` | Ollama服务器URL | http://localhost:11434 |
| `--wake-url` | `WAKE_URL` | 唤醒服务器URL | http://localhost:11434/api/generate |
| `--timeout` | `TIMEOUT_SECONDS` | 简单请求超时时间(秒) | 10 |
| `--model-timeout` | `MODEL_TIMEOUT_SECONDS` | 模型推理请求超时时间(秒) | 30 |
| `--port` | `PORT` | 代理服务器端口 | 11434 |
| `--wake-interval` | `WAKE_INTERVAL` | 唤醒间隔时间(分钟) | 10 |

## 部署方式

### 使用 Docker Compose（推荐）

1. 创建 `.env` 文件（可选）并配置环境变量
2. 使用以下命令启动服务：
```bash
docker-compose up -d
```

### 使用 Docker

```bash
docker run -d \
  -p 11434:11434 \
  -e OLLAMA_URL=http://localhost:11434 \
  -e WAKE_URL=http://localhost:11434/api/generate \
  -e TIMEOUT_SECONDS=10 \
  -e PORT=11434 \
  yshtcn/ollama-proxy:latest
```

### 手动部署

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 运行服务：
```bash
python ollama_proxy.py \
  --ollama-url http://localhost:11434 \
  --wake-url http://localhost:11434/api/generate \
  --timeout 10 \
  --port 11434
```

## 构建 Docker 镜像

项目提供了 PowerShell 脚本 `ollama_proxy_docker_builder.ps1` 用于自动构建和推送 Docker 镜像：

1. 以管理员权限运行脚本
2. 脚本会自动：
   - 检查 Docker 环境
   - 构建镜像并添加版本标签
   - 推送镜像到 Docker Hub
   - 更新 latest 标签

## 依赖项

- Python 3.9+
- FastAPI
- Uvicorn
- HTTPX

## 注意事项

1. 确保 Ollama 服务正在运行且可访问
2. 配置正确的 OLLAMA_URL 和 WAKE_URL
3. 根据网络环境调整超时时间
4. Docker 部署时注意端口映射和网络配置
5. 可以搭配 [WolGoWeb](https://github.com/xiaoxinpro/WolGoWeb) 项目使用，实现远程唤醒功能：
   - WolGoWeb 提供了网络唤醒（WOL）功能
   - 可以通过 HTTP API 远程唤醒目标主机
   - 支持多种部署方式（Docker、直接部署等）
   - 配置 WAKE_URL 为 WolGoWeb 的唤醒接口，即可实现远程唤醒 Ollama 服务器

## 健康检查

服务提供了 `/health` 端点，返回格式如下：
```json
{
    "status": "healthy"
}
```

Docker 容器配置了自动健康检查：
- 检查间隔：30秒
- 超时时间：10秒
- 重试次数：3次
