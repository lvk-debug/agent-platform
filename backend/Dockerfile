FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
# EXTRAS 由 docker-compose 传入（默认包含 qdrant 向量库客户端）
ARG EXTRAS=postgres,qdrant,sqlite
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[${EXTRAS}]"

# 复制应用代码
COPY . .

# 创建数据目录（/app/models 用于挂载离线 embedding 模型缓存）
RUN mkdir -p /app/data /app/uploads /app/logs /app/models

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
