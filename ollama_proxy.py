from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
import httpx
import asyncio
import logging
import os
import argparse
import sys
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 解析命令行参数
parser = argparse.ArgumentParser(description='Ollama代理服务器')
parser.add_argument('--ollama-url', help='Ollama服务器URL')
parser.add_argument('--wake-url', help='唤醒服务器URL')
parser.add_argument('--timeout', type=int, help='简单请求的超时时间(秒)')
parser.add_argument('--model-timeout', type=int, help='模型推理请求的超时时间(秒)')
parser.add_argument('--port', type=int, help='代理服务器端口')
parser.add_argument('--wake-interval', type=int, default=10, help='唤醒间隔时间(分钟)')

args = parser.parse_args()

# 配置常量，优先使用环境变量，其次使用命令行参数
OLLAMA_URL = os.getenv('OLLAMA_URL') or args.ollama_url
WAKE_URL = os.getenv('WAKE_URL') or args.wake_url
TIMEOUT_SECONDS = os.getenv('TIMEOUT_SECONDS') or args.timeout
MODEL_TIMEOUT_SECONDS = int(os.getenv('MODEL_TIMEOUT_SECONDS') or args.model_timeout or 30)  # 默认30秒
PORT = os.getenv('PORT') or args.port
WAKE_INTERVAL = int(os.getenv('WAKE_INTERVAL') or args.wake_interval)

# 检查必要参数
missing_params = []
if not OLLAMA_URL:
    missing_params.append("OLLAMA_URL")
if not WAKE_URL:
    missing_params.append("WAKE_URL")
if not TIMEOUT_SECONDS:
    missing_params.append("TIMEOUT_SECONDS")
if not PORT:
    missing_params.append("PORT")

if missing_params:
    logger.error(f"缺少必要参数: {', '.join(missing_params)}")
    logger.error("请通过环境变量或命令行参数指定这些值")
    sys.exit(1)

# 确保数值类型正确
try:
    TIMEOUT_SECONDS = int(TIMEOUT_SECONDS)
    PORT = int(PORT)
except ValueError as e:
    logger.error("TIMEOUT_SECONDS 和 PORT 必须是整数")
    sys.exit(1)

# 添加上次唤醒时间的全局变量
last_wake_time = None

# 添加缓存相关的变量
models_cache = None
models_cache_time = None
CACHE_DURATION = timedelta(minutes=30)  # 缓存有效期30分钟

async def should_wake():
    """检查是否需要发送唤醒请求"""
    global last_wake_time
    if last_wake_time is None:
        return True
    return datetime.now() - last_wake_time > timedelta(minutes=WAKE_INTERVAL)

async def wake_ollama():
    """唤醒 Ollama 服务器"""
    global last_wake_time
    try:
        async with httpx.AsyncClient() as client:
            await client.get(WAKE_URL)
            last_wake_time = datetime.now()
            logger.info(f"已发送唤醒请求，更新唤醒时间: {last_wake_time}")
    except Exception as e:
        logger.error(f"唤醒请求失败: {str(e)}")

async def get_models_from_cache():
    """从缓存获取模型列表"""
    global models_cache, models_cache_time
    if models_cache is None or models_cache_time is None:
        return None
    if datetime.now() - models_cache_time > CACHE_DURATION:
        return None
    return models_cache

async def update_models_cache(data):
    """更新模型列表缓存"""
    global models_cache, models_cache_time
    models_cache = data
    models_cache_time = datetime.now()
    logger.info("模型列表缓存已更新")

# 输出当前配置
logger.info(f"使用配置:")
logger.info(f"OLLAMA_URL: {OLLAMA_URL}")
logger.info(f"WAKE_URL: {WAKE_URL}")
logger.info(f"TIMEOUT_SECONDS: {TIMEOUT_SECONDS}")
logger.info(f"MODEL_TIMEOUT_SECONDS: {MODEL_TIMEOUT_SECONDS}")
logger.info(f"PORT: {PORT}")
logger.info(f"WAKE_INTERVAL: {WAKE_INTERVAL} minutes")

app = FastAPI()

@app.get("/health")
async def health_check():
    logger.info("收到健康检查请求")
    return {"status": "healthy"}

@app.get("/api/tags")
async def list_models():
    try:
        # 首先尝试从缓存获取
        cached_models = await get_models_from_cache()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OLLAMA_URL}/api/tags",
                timeout=TIMEOUT_SECONDS  # 使用较短的超时时间
            )
            # 更新缓存并返回最新数据
            await update_models_cache(response.json())
            return response.json()
            
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        # 发生超时或连接错误时，触发唤醒
        logger.warning(f"获取标签列表失败，正在唤醒服务器: {str(e)}")
        asyncio.create_task(wake_ollama())
        
        # 如果有缓存，返回缓存数据
        if cached_models is not None:
            logger.info("返回缓存的标签列表")
            return JSONResponse(content=cached_models)
            
        # 如果没有缓存，返回503
        return JSONResponse(
            status_code=503,
            content={"message": "服务器正在唤醒中，请稍后重试"}
        )
        
    except Exception as e:
        logger.error(f"获取标签列表时发生未知错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request, path: str):
    # 避免代理 /health 请求
    if path == "health":
        return await health_check()
    
    # 其他请求的处理逻辑
    if await should_wake():
        logger.info("距离上次唤醒已超过设定时间，发送预防性唤醒请求")
        await wake_ollama()
    
    async with httpx.AsyncClient() as client:
        try:
            target_url = f"{OLLAMA_URL}/{path}"
            body = await request.body()
            headers = dict(request.headers)
            headers.pop('host', None)
            headers.pop('connection', None)
            
            # 根据请求类型选择不同的超时时间
            timeout = TIMEOUT_SECONDS if path == "api/tags" else MODEL_TIMEOUT_SECONDS
            
            response = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=headers,
                timeout=timeout,  # 使用动态超时时间
                follow_redirects=True
            )
            
            # 如果是标签列表请求且成功，更新缓存
            if path == "api/tags" and request.method == "GET" and response.status_code == 200:
                await update_models_cache(response.json())
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
        except httpx.TimeoutException:
            logger.warning("Ollama服务器超时，发送唤醒请求")
            # 如果是标签列表请求，尝试返回缓存
            if path == "api/tags" and request.method == "GET":
                cached_models = await get_models_from_cache()
                if cached_models is not None:
                    logger.info("返回缓存的标签列表")
                    return JSONResponse(content=cached_models)
            
            # 直接异步发送唤醒请求，不等待结果
            asyncio.create_task(wake_ollama())
            return JSONResponse(
                status_code=503,
                content={"message": "服务器正在唤醒中，请稍后重试"}
            )
        
        except httpx.RequestError as e:
            logger.error(f"请求错误: {str(e)}")
            # 如果是标签列表请求，尝试返回缓存
            if path == "api/tags" and request.method == "GET":
                cached_models = await get_models_from_cache()
                if cached_models is not None:
                    logger.info("返回缓存的标签列表")
                    return JSONResponse(content=cached_models)
                    
            return JSONResponse(
                status_code=502,
                content={"message": f"无法连接到Ollama服务器: {str(e)}"}
            )
                
        except Exception as e:
            logger.error(f"代理请求失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"message": f"代理请求失败: {str(e)}"}
            )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT) 