# Network Diagnostic Tool - Server Image
# 网络诊断工具后端镜像
# 依赖系统命令：ping / traceroute / mtr / dig / whois / openssl / bash
FROM python:3.11-slim

# 使用更快的 Debian 镜像源（腾讯云），避免默认源过慢
RUN sed -i 's|deb.debian.org/debian|mirrors.cloud.tencent.com/debian|g; s|security.debian.org/debian-security|mirrors.cloud.tencent.com/debian-security|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org/debian|mirrors.cloud.tencent.com/debian|g; s|security.debian.org/debian-security|mirrors.cloud.tencent.com/debian-security|g' /etc/apt/sources.list

# 安装系统诊断工具（映射 server.py 的 subprocess 调用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    traceroute \
    mtr \
    dnsutils \
    whois \
    openssl \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖（无需 requirements.txt，直接安装项目所需包；用阿里镜像避免 pypi 慢/超时）
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ flask flask-cors requests

# 只拷贝后端运行所需文件（index.html 为自包含单文件前端）
COPY server.py .
COPY index.html .
COPY manifest.json .

EXPOSE 8080

# server.py 内部会 os.chdir 到自身目录并监听 0.0.0.0:8080
CMD ["python3", "server.py"]
