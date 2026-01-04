# 使用Python 3.11官方镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 复制项目依赖文件
COPY pyproject.toml ./

# 安装uv包管理器（更快的依赖安装）
RUN pip install --no-cache-dir uv

# 使用uv安装项目依赖
RUN uv pip install --system -e .

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/

# 下载构建后的前端构建文件
RUN curl -L -o /app/dist.zip http://github.com/NekoBotTeam/Nekobot-Dashboard/releases/latest/download/dist.zip && \
    unzip -o /app/dist.zip -d /app && \
    rm /app/dist.zip

# 暴露端口
EXPOSE 6285

# 设置健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:6285/health || exit 1

# 启动应用
CMD ["python", "main.py"]