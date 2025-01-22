FROM python:3.9-slim

WORKDIR /app

# 设置 Python 环境
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 添加新的环境变量默认值
ENV WAKE_INTERVAL=10

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY ollama_proxy.py .

# 暴露端口
EXPOSE 11434

# 启动应用
CMD ["python", "ollama_proxy.py"] 