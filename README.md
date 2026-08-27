# 网络诊断工具 (Network Diagnostic Tool)

> 版本：v3.0 ｜ 协议：MIT License
>
> 一个面向 IT 运维人员的轻量网络诊断工具，支持 **PC 端网页访问**与 **Android APK 安装使用**两种形态，后端为 Python Flask，前端为原生 HTML/CSS/JS（无框架依赖），移动端通过 Apache Cordova 打包。

## 功能特性

- **Ping 检测** - ICMP 连通性测试，返回丢包率与最小/平均/最大延迟
- **路由跟踪** - Traceroute 路径追踪，SSE 流式逐跳实时输出
- **MTR 诊断** - 网络质量综合分析（丢包率、平均/最好/最差延迟、标准差）
- **DNS 查询** - 域名解析检测，支持自定义 DNS 服务器与 8 种记录类型（A/AAAA/NS/MX/TXT/CNAME/SOA/PTR）
- **端口扫描** - TCP 端口状态检测，支持范围扫描（如 `1-1000`）与服务名识别
- **HTTP 检测** - 网站可达性测试，返回状态码与响应时间
- **批量检测** - 多主机批量 Ping，一次最多 100 台主机
- **Whois 查询** - 域名注册信息（终端本地 RDAP 优先，失败降级服务器 whois）
- **TCP Ping** - 前端本地 fetch 测量 TCP 连通延迟，多轮统计 min/avg/max
- **CIDR 计算器** - 纯前端子网计算（网络/广播地址、掩码、可用主机数、私网判断）
- **SSL 证书** - 证书主体、签发机构、有效期、剩余天数、SAN（后端 openssl）
- **本机信息** - 公网 IP、运营商、User Agent、屏幕分辨率、设备像素比
- **双源标识** - 所有接口区分「服务器视角」与「终端本地」源，结果首行显示源 IP 或「本地」
- **检测历史** - 本地存储最近 20 条检测记录
- **任务可中止** - 每个 Tab 均支持「开始 / 停止」按钮，基于 `AbortController` 取消请求
- **安全防护** - 请求限流、并发限制、域名白名单

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端 | Python 3.8+ / Flask | 单文件 `server.py`，集成限流、并发控制、SSE |
| 依赖 | flask-cors、requests | 跨域与 HTTP 探测 |
| PC 前端 | 原生 HTML/CSS/JS | 单文件 `index.html`，PWA 可安装 |
| 移动端 | Apache Cordova 12+ / cordova-android 15 | 打包为 Android APK |
| Android | minSdk 22 / targetSdk 36 | 允许明文流量以兼容自建 HTTP 后端 |

## 项目结构

```
network-tool/
├── server.py              # Python Flask 后端服务（API + 静态托管）
├── index.html             # PC 端前端页面（含全部样式与脚本）
├── manifest.json          # PWA 配置（PC 端可安装）
├── network-tool-app/      # Cordova 移动端项目
│   ├── config.xml         # Cordova 应用配置（权限、SDK 版本、状态栏等）
│   ├── package.json       # Node.js 依赖（cordova-android）
│   ├── network_security_config.xml → res/xml/
│   ├── www/               # 移动端前端源码（打包进 APK）
│   │   ├── index.html     # 与 PC 端基本一致的前端页面
│   │   ├── manifest.json  # PWA 配置
│   │   ├── css/index.css  # Cordova 默认样式（实际未启用）
│   │   ├── js/index.js    # Cordova deviceready 钩子
│   │   └── img/logo.png   # 应用图标
│   ├── res/xml/            # 网络安全配置（允许明文流量到 localhost / tencent.markli.cn）
│   └── platforms/android/  # Android 平台代码（构建后生成）
└── docs/                  # 文档目录
    ├── BUILD.md           # APK 构建与签名说明
    └── DEPLOY.md          # 部署、迁移、Nginx、systemd、Docker 说明
```

## API接口列表

### 1. Ping检测
- **接口**: `POST /api/ping`
- **描述**: ICMP Ping连通性检测
- **参数**:
  ```json
  {
    "host": "baidu.com",    // 目标主机(域名或IP)
    "count": 4,             // 发送包数量
    "timeout": 10           // 超时时间(秒)
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "ip": "220.181.38.148",
    "packets_sent": 4,
    "packets_received": 4,
    "packet_loss": 0,
    "min_rtt": 12.5,
    "avg_rtt": 15.2,
    "max_rtt": 18.3
  }
  ```

### 2. DNS查询
- **接口**: `POST /api/dns`
- **描述**: DNS域名解析查询
- **参数**:
  ```json
  {
    "domain": "google.com",           // 域名
    "dns_server": "114.114.114.114",  // DNS服务器（纯 IP 走后端；DoH 地址如 https://223.5.5.5/resolve 由终端本地解析）
    "type": "A"                       // 记录类型：A/AAAA/NS/MX/TXT/CNAME/SOA/PTR
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "domain": "google.com",
    "type": "A",
    "records": ["142.250.190.78"],
    "source": "server",               // 后端解析时为 server
    "source_ip": "172.18.0.1"         // 执行解析的服务器 IP（DoH 本地解析时不返回此字段，前端显示「源：本机」）
  }
  ```
- **双源说明**: 若 `dns_server` 以 `https://` 开头，前端直接 fetch DoH JSON 接口（终端本地解析，5 秒超时）；纯 IP 地址则调后端 `/api/dns`。前端 badge 会根据选中 DNS 服务器动态切换「终端本地」/「服务器」标签。

### 3. 路由跟踪
- **接口**: `POST /api/traceroute`
- **描述**: Traceroute路由路径跟踪(Server-Sent Events流式输出)
- **参数**:
  ```json
  {
    "host": "baidu.com",
    "max_hops": 30,         // 最大跳数
    "timeout": 30           // 超时时间(秒)
  }
  ```
- **响应**: SSE事件流
  - `start` - 开始事件
  - `hop` - 每跳数据 `{hop, ip, hostname, rtt}`
  - `done` - 完成事件

### 4. MTR诊断
- **接口**: `POST /api/mtr`
- **描述**: MTR(My Traceroute)网络质量诊断
- **参数**:
  ```json
  {
    "host": "baidu.com",
    "count": 10,            // 检测次数
    "timeout": 60           // 超时时间(秒)
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "host": "baidu.com",
    "count": 10,
    "total_hops": 12,
    "hops": [
      {
        "hop": 1,
        "ip": "192.168.1.1",
        "hostname": "gateway",
        "sent": 10,
        "lost": 0,
        "lost_percent": 0,
        "avg": 2.5,
        "best": 1.2,
        "worst": 5.3,
        "stdev": 1.1
      }
    ]
  }
  ```

### 5. 端口检测
- **接口**: `POST /api/port`
- **描述**: TCP端口状态检测
- **参数**:
  ```json
  {
    "host": "baidu.com",
    "port": 80,             // 端口号(1-65535)
    "timeout": 5            // 超时时间(秒)
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "host": "baidu.com",
    "port": 80,
    "open": true,
    "latency_ms": 15.5
  }
  ```

### 6. HTTP检测
- **接口**: `POST /api/http`
- **描述**: HTTP/HTTPS网站可达性检测
- **参数**:
  ```json
  {
    "url": "https://www.baidu.com",
    "timeout": 10           // 超时时间(秒)
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "url": "https://www.baidu.com",
    "status_code": 200,
    "latency_ms": 156.3,
    "final_url": "https://www.baidu.com/"
  }
  ```

### 7. 批量Ping
- **接口**: `POST /api/batch_ping`
- **描述**: 批量主机连通性检测
- **参数**:
  ```json
  {
    "hosts": ["baidu.com", "google.com", "github.com"],
    "count": 2,             // 每个主机发送包数量
    "timeout": 5            // 超时时间(秒)
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "total": 3,
    "online": 2,
    "results": [...]
  }
  ```

### 8. IP信息
- **接口**: `GET /api/ip`
- **描述**: 获取公网IP和运营商信息
- **参数**: 无
- **响应**:
  ```json
  {
    "success": true,
    "ip": "123.45.67.89",
    "country": "中国",
    "region": "广东省",
    "city": "深圳市",
    "isp": "中国电信"
  }
  ```

### 9. Whois查询
- **接口**: `POST /api/whois`
- **描述**: 域名注册信息查询（前端优先走终端本地 RDAP `https://rdap.org/domain/<host>`，失败或输入 IP 时降级调后端 whois）
- **参数**:
  ```json
  {
    "host": "baidu.com"
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "host": "baidu.com",
    "registrar": "MarkMonitor Inc.",
    "creation_date": "1999-10-11",
    "expiry_date": "2026-10-11",
    "status": "ok",
    "source": "server",
    "source_ip": "172.18.0.1"
  }
  ```
- **降级**: 服务器需安装 `whois` 命令；前端 RDAP 走终端本地，不消耗后端资源

### 10. SSL证书查询
- **接口**: `POST /api/cert`
- **描述**: SSL 证书信息查询（后端 openssl 获取，服务器视角）
- **参数**:
  ```json
  {
    "host": "baidu.com",
    "port": 443            // 默认 443
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "host": "baidu.com",
    "port": 443,
    "subject": "C=CN, ST=...",
    "issuer": "C=US, O=DigiCert...",
    "not_before": "Mar  3 00:00:00 2024 GMT",
    "not_after": "Mar  3 23:59:59 2027 GMT",
    "san": "DNS:baidu.com, DNS:www.baidu.com",
    "days_left": 189,
    "source": "server",
    "source_ip": "172.18.0.1"
  }
  ```
- **依赖**: 服务器需安装 `openssl`（与 `bash` 用于管道）

### 11. 健康检查
- **接口**: `GET /health`
- **描述**: 服务健康状态检查
- **响应**: `{"status": "ok", "version": "2.0"}`

## 快速开始

### Docker 一键运行（推荐）

官方镜像已发布到 Docker Hub，拉取即可运行（内部已内置 pip 依赖与所有系统命令工具）：

```bash
# 拉取镜像并启动（默认监听 0.0.0.0:8080）
docker run -d --name network-tool --restart unless-stopped -p 8080:8080 jacknotes/network-tool:v3.0.0
```

启动成功后浏览器访问：

```
本机访问: http://localhost:8080
手机访问: http://192.168.x.x:8080
```

如需用 `docker compose`，可参考 [`docs/DEPLOY.md`](docs/DEPLOY.md) 中的示例配置。

---

### 后端服务（从源码运行）

```bash
# 1. 安装依赖
pip install flask flask-cors requests

# 2. （可选）系统工具，提供原生 ping/traceroute/mtr/dig/whois/openssl 能力
# Ubuntu/Debian
sudo apt install mtr traceroute iputils-ping dnsutils whois openssl
# CentOS/RHEL
sudo yum install mtr traceroute iputils bind-utils whois openssl

# 3. 启动服务（默认监听 0.0.0.0:8080）
python3 server.py
```

启动成功后终端会打印本机与局域网访问地址：

```
本机访问: http://localhost:8080
手机访问: http://192.168.x.x:8080
```

> ⚠️ Linux 上 MTR / Traceroute 需要 `mtr`、`traceroute` 系统命令，未安装时对应接口会回退到 Python 原生实现或返回错误。

### PC 端使用

1. 启动后端服务（见上）
2. 浏览器访问：
   - 本机：`http://localhost:8080`
   - 局域网：`http://服务器IP:8080`
3. 可作为 PWA 安装（`manifest.json` 已配置）

### Android APK 使用

1. 安装 APK 文件到手机（构建方法见 `docs/BUILD.md`）
2. 打开应用，点击右上角 ⚙️ 图标
3. 配置 API 服务器地址：
   - 局域网：`http://服务器IP:8080`
   - 公网/Nginx：`https://your-domain.com/networks`
4. 保存后自动检测协议（优先 HTTPS，不可用时回退 HTTP）

### API 服务器配置说明

前端 `getApiBase()` 会自动判断运行环境：

- **PC 网页**：取当前页面 `origin + pathname` 前缀，例如部署到 `https://tencent.markli.cn/network/` 时自动以 `https://tencent.markli.cn/network` 作为 API 基址
- **APK（file 协议）**：使用用户配置的 `localStorage['apiServer']`，未配置时回退到内置默认地址
- **健康检查**：设置服务器时会调用 `/health` 探测协议可用性

## 前端说明

### 技术栈
- 纯 HTML / CSS / JavaScript，无框架依赖
- 单文件 `index.html`（约 1570 行），样式与脚本内联
- 响应式布局，深色主题，触摸优化

### 主要功能模块

1. **快速操作区** - 8 个功能入口按钮（Ping / 路由 / MTR / DNS / HTTP / 端口 / 本机 / 批量）
2. **标签页切换** - Ping / 路由 / MTR / DNS / HTTP / 本机（端口与批量通过快速操作区进入）
3. **结果展示** - 等宽字体，支持 `success` / `error` / `info` / `warning` 四种样式
4. **任务控制** - 每个功能 Tab 配备「开始 / 停止」按钮，基于 `AbortController` 取消
5. **历史记录** - `localStorage` 存储最近 20 条检测记录，可清空
6. **API 设置** - ⚙️ 图标，支持自动协议探测

### 移动端适配
- 响应式布局
- 触摸优化（`-webkit-tap-highlight-color: transparent`）
- 深色主题（`#1a1a2e` 渐变背景）

## 安全特性

| 特性 | 配置项 | 默认值 | 说明 |
|------|--------|--------|------|
| 请求限流 | `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW` | 30 次 / 60 秒 | 每 IP 独立计数，超限返回 `429` |
| 并发限制 | `MAX_CONCURRENT_TASKS` | 5 | 信号量控制，超限返回 `503` |
| 域名白名单 | `DOMAIN_WHITELIST` | `[]`（不限制） | 支持通配符 `*.example.com` |
| 主机校验 | `validate_host()` | 正则 `^[a-zA-Z0-9._-]+$` | 防止命令注入 |
| 端口校验 | `port_check()` | 1-65535 | 拒绝非法端口 |
| 批量上限 | `batch_ping()` | 100 台主机 | 防止滥用 |
| 端口扫描上限 | 前端 `parsePorts()` | 1000 个 | 防止大范围扫描 |

> 配置位置：`server.py` 顶部 `安全配置` 区块。

## 依赖要求

### 后端运行
- Python 3.8+
- Flask
- flask-cors
- requests
- 系统命令（可选但推荐）：`ping`、`traceroute`/`tracert`、`mtr`、`dig`/`nslookup`

### Android 构建
- Node.js 16+
- Cordova CLI 12+
- cordova-android 15+（`package.json` 已锁定）
- JDK 11+（推荐 17）
- Android SDK API 34+ / build-tools 34.0.0
- Gradle 8.x（Cordova 自动管理）

详见 `docs/BUILD.md`。

## 验证服务

```bash
# 健康检查
curl http://localhost:8080/health
# 预期: {"status":"ok","version":"2.0"}

# 测试 Ping 接口
curl -X POST http://localhost:8080/api/ping \
  -H "Content-Type: application/json" \
  -d '{"host": "baidu.com", "count": 2}'

# 测试 IP 信息接口
curl http://localhost:8080/api/ip
```

## 文档导航

| 文档 | 说明 |
|------|------|
| [docs/BUILD.md](docs/BUILD.md) | APK 构建环境、构建命令、签名、常见问题 |
| [docs/DEPLOY.md](docs/DEPLOY.md) | 后端部署、systemd、Nginx 反代、Docker、迁移、防火墙 |
| [AGENTS.md](AGENTS.md) | 面向 AI 编程代理的项目指令文件（构建/测试/约定） |

## 许可证

MIT License
