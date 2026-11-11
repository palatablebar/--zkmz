FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai \
    PYTHONPATH=/app/backend

WORKDIR /app

# 复用 backend 依赖层（同一 requirements.txt，构建缓存共享）
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120 -r /app/backend/requirements.txt

COPY backend /app/backend
COPY worker /app/worker

WORKDIR /app/backend
CMD ["bash", "/app/worker/entrypoint.sh"]
