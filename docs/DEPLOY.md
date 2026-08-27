# 项目运行及迁移说明

## 项目架构

```
network-tool/
├── server.py              # Python Flask 后端服务
├── index.html             # PC 端网页前端
├── manifest.json          # PWA 配置
├── network-tool-app/      # Cordova Android 项目
│   ├── config.xml         # Cordova 配置文件
│   ├── package.json       # Node.js 依赖
│   ├── www/               # 移动端前端源码
│   ├── res/               # 应用资源
│   └── platforms/android/ # Android 平台代码
└── docs/                  # 文档
```

## 一、后端服务运行

### 环境要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install flask flask-cors requests
```

### 启动服务

```bash
# 方式一：直接运行
python3 server.py

# 方式二：指定端口（修改 server.py 中 PORT 变量）
# 默认端口为 8080
```

启动后输出示例：

```
==================================================
       网络诊断工具 - 本地服务器 v3.0
==================================================

本机访问: http://localhost:8080
手机访问: http://192.168.1.100:8080

请确保手机和电脑在同一局域网
```

### 后台运行（Linux）

```bash
# 使用 nohup
nohup python3 server.py > server.log 2>&1 &

# 使用 systemd（推荐）
# 创建 /etc/systemd/system/network-tool.service
```

systemd 服务文件示例：

```ini
[Unit]
Description=Network Diagnostic Tool Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/network-tool
ExecStart=/usr/bin/python3 /opt/network-tool/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable network-tool
sudo systemctl start network-tool
```

### 使用 Nginx 反向代理

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /networks/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持（路由跟踪功能需要）
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

## 二、PC 端使用

1. 启动后端服务 `python3 server.py`
2. 浏览器访问 `http://localhost:8080`
3. 局域网其他设备访问 `http://服务器IP:8080`

## 三、APK 安装使用

1. 安装 APK 文件到 Android 手机
2. 打开应用，点击右上角 ⚙️ 图标
3. 配置 API 服务器地址：
   - 格式：`http://服务器IP:8080`
   - 如果使用 Nginx 代理：`https://your-domain.com/networks`
4. 点击保存，即可使用

## 四、项目迁移

### 迁移到新服务器

#### 1. 复制项目文件

```bash
# 打包
tar czf network-tool.tar.gz network-tool/

# 传输
scp network-tool.tar.gz user@new-server:/opt/

# 解压
cd /opt && tar xzf network-tool.tar.gz
```

#### 2. 安装依赖

```bash
# Python 依赖
pip3 install flask flask-cors requests

# 系统工具（MTR/Traceroute/Whois/证书功能需要）
# Ubuntu/Debian
sudo apt install mtr traceroute iputils-ping dnsutils whois openssl

# CentOS/RHEL
sudo yum install mtr traceroute iputils bind-utils whois openssl
```

#### 3. 配置服务

```bash
# 设置目录权限
chown -R www-data:www-data /opt/network-tool

# 配置 systemd 服务（参考上面的配置）
sudo systemctl daemon-reload
sudo systemctl enable network-tool
sudo systemctl start network-tool
```

#### 4. 更新 APK 配置

APK 首次打开时配置新的服务器地址即可，或：
- 点击 ⚙️ 图标 → 修改服务器地址 → 保存

### 迁移到 Docker（推荐）

仓库根目录已提供生产可用的 `Dockerfile`、`docker-compose.yml` 与 `.dockerignore`。

```bash
# 构建镜像
docker build -t network-tool:3.0.0 .

# 运行（映射 8080，失败自动重启）
docker run -d --name network-tool --restart unless-stopped \
  -p 8080:8080 network-tool:3.0.0

# 或使用 docker compose（推荐，便于管理）
docker compose up -d
```

> **重要：构建须带 `--network=host`**
> 若服务器通过本机代理（如 `127.0.0.1:10809` 的 xray/v2ray）才能访问外网，
> 构建时容器内默认网络访问不到宿主机代理，会导致 `apt-get`/`pip` 超时：
> ```bash
> docker build --network=host -t network-tool:3.0.0 .
> ```
> 如果走的是透明代理/直连外网，则无需此参数。

**访问：** `http://localhost:8080`（服务与前端由 Flask 单进程托管）。

#### 镜像内容说明

- 基于 `python:3.11-slim`，内置 `iputils-ping / traceroute / mtr / dnsutils / whois / openssl / curl`，对应 `server.py` 的全部系统命令依赖。
- 为加速构建（国内网络），`Dockerfile` 已将 **Debian 源换成腾讯云镜像**、**pip 源换成阿里云镜像**。若你在海外/无代理环境，可去掉这两个镜像切换。
- 仅打包 `server.py + index.html + manifest.json`（前端为自包含单文件），`.gitignore`/`.dockerignore` 已排除密钥、构建产物、Cordova 工程等。

#### 常用运维命令

```bash
docker ps                        # 查看容器状态
docker logs -f network-tool       # 实时日志
docker restart network-tool       # 重启
docker rm -f network-tool         # 删除容器
docker compose up -d              # 用 compose 重建并运行
docker compose down               # 停止并移除
```

> 若替换旧版本：旧版本可能直接以 `python3 server.py` 后台进程运行并占用 8080。
> 迁移前先停掉旧进程释放端口：`kill <旧PID>` 或 `pkill -f server.py`，再启动容器。

## 五、网络配置

### 防火墙放行

```bash
# Ubuntu (ufw)
sudo ufw allow 8080/tcp

# CentOS (firewalld)
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload

# iptables
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
```

### 安全配置

在 `server.py` 中可调整：

```python
# 域名白名单（空列表表示不限制）
DOMAIN_WHITELIST = [
    # 'example.com',
    # '*.example.com',
]

# 限流：每 IP 每 60 秒最多 30 次请求
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60

# 并发限制：最多 5 个并发任务
MAX_CONCURRENT_TASKS = 5
```

## 六、验证服务

```bash
# 健康检查
curl http://localhost:8080/health
# 预期返回: {"status": "ok", "version": "2.0"}

# 测试 Ping 接口
curl -X POST http://localhost:8080/api/ping \
  -H "Content-Type: application/json" \
  -d '{"host": "baidu.com", "count": 2}'

# 测试 IP 接口
curl http://localhost:8080/api/ip
```

## 七、故障排查

| 问题 | 排查方式 |
|------|---------|
| 服务无法启动 | 检查端口是否被占用 `lsof -i :8080` |
| APK 连接失败 | 确认手机与服务器在同一网络，检查防火墙 |
| Ping 不可用 | 确认系统已安装 `ping` 命令，且有执行权限 |
| MTR 不可用 | 安装 mtr：`apt install mtr` 或 `yum install mtr` |
| Traceroute 不可用 | 安装：`apt install traceroute` |
| DNS 查询失败 | 安装 dig：`apt install dnsutils` |
| Whois 降级失败 | 安装：`apt install whois`（前端 RDAP 失败时走后端 whois；IP 输入始终走后端） |
| 证书查询失败 | 安装：`apt install openssl`，且需 `bash` 可用（`openssl s_client \| x509` 管道） |
| SSE 流式响应中断 | Nginx 配置 `proxy_buffering off` |
| APK HTTPS 混合内容 | 配置 SSL 证书或使用 HTTP |

## 八、端口说明

| 端口 | 协议 | 用途 |
|------|------|------|
| 8080 | TCP | 后端 API 服务（默认） |
