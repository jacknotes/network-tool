# AGENTS.md

> 本文件面向 AI 编程代理（Codex / Claude Code / Cursor / Copilot 等）。
> README.md 给人类看，AGENTS.md 给 Agent 看 —— 修改本仓库前请先读完本文件。

## 项目概述

`network-tool` 是一个轻量网络诊断工具，包含两个交付物：

1. **PC 端网页** —— Python Flask 后端（`server.py`）+ 单文件前端（`index.html`），PWA 可安装。
2. **Android APK** —— 通过 Apache Cordova 打包（`network-tool-app/`），前端与 PC 端基本一致，运行时通过 `localStorage` 配置后端地址。

后端封装 `ping` / `traceroute` / `mtr` / `dig` / `nslookup` 等系统命令，并以 REST + SSE 暴露给前端。所有诊断能力由后端执行，前端只做调用与展示。

## 仓库布局

```
network-tool/
├── server.py                  # 后端：Flask 单文件，API + 静态托管（PC 端入口）
├── index.html                 # PC 前端：单文件，含全部 CSS/JS（约 1570 行）
├── manifest.json              # PC 端 PWA 配置
├── AGENTS.md                  # 本文件
├── network-tool-app/          # Cordova Android 项目
│   ├── config.xml             # Cordova 配置（权限、SDK、状态栏、明文流量）
│   ├── package.json           # 仅依赖 cordova-android ^15
│   ├── www/                   # 打包进 APK 的前端源码
│   │   ├── index.html         # 与 PC 端几乎一致（含 getApiBase() 的 file: 协议分支）
│   │   ├── manifest.json      # APK 内 PWA 配置
│   │   ├── css/index.css      # Cordova 模板残留样式（实际未启用）
│   │   ├── js/index.js        # Cordova deviceready 钩子（当前为空实现）
│   │   └── img/logo.png
│   └── res/xml/network_security_config.xml  # 允许明文流量到 localhost/127.0.0.1/tencent.markli.cn
└── docs/
    ├── BUILD.md               # APK 构建与签名
    └── DEPLOY.md              # 部署、迁移、Nginx、systemd、Docker
```

**注意**：`network-tool-app/platforms/android/` 目录在构建后生成，不要手工编辑。

## 关键运行时约定

### API 基址自动探测（务必保持两端一致）

前端 `getApiBase()`（PC 端 `index.html` 与 `network-tool-app/www/index.html` 中各有一份）逻辑：

- 优先读 `localStorage['apiServer']`（用户通过 ⚙️ 设置）
- 否则若 `window.location.protocol === 'file:'`（APK 环境）→ 回退到内置默认 `https://tencent.markli.cn/networks`
- 否则取当前页面 `origin + pathname` 前缀（PC 网页自部署场景）

**改动前端 API 调用逻辑时，两个 `index.html` 必须同步修改**，否则 PC 与 APK 行为会分裂。

### 协议自动探测

`setApiServer()` 会在保存前调用 `/health` 探测 HTTPS / HTTP 可用性，优先 HTTPS。修改保存逻辑时保留这一行为，否则会破坏 APK 在混合内容策略下的可用性。

### SSE 流式响应

`/api/traceroute` 使用 `text/event-stream`，前端通过 `response.body.getReader()` 逐行解析 `data: {...}\n\n`。Nginx 反代必须设置 `proxy_buffering off`（见 `docs/DEPLOY.md`）。改动事件结构时同步改前端 `processLine()`。

### 系统命令依赖

后端 `server.py` 通过 `subprocess` 调用系统命令，按 `platform.system()` 分支：

| 功能 | Windows | Linux |
|------|---------|-------|
| Ping | `ping -n` | `ping -c` |
| Traceroute | `tracert` | `traceroute`（缺失时回退到 Python 原生 socket 实现） |
| MTR | `tracert` 多次循环模拟 | `mtr --report --json`（缺失时回退到文本解析） |
| DNS | `nslookup` | `dig` |
| Whois | 不支持（前端 RDAP 降级失败时报错） | `whois` |
| SSL 证书 | 不支持（返回错误） | `openssl` + `bash`（`s_client | x509` 管道） |

**新增依赖系统命令的功能时**，必须在 `docs/DEPLOY.md` 的系统工具安装说明中补充对应包。

## 构建与运行命令

### 后端（开发与运行）

```bash
# 安装依赖
pip install flask flask-cors requests

# 运行（默认 0.0.0.0:8080，debug=False）
python3 server.py
```

无构建步骤，无测试套件。验证方式：

```bash
curl http://localhost:8080/health
# {"status":"ok","version":"2.0"}

curl -X POST http://localhost:8080/api/ping \
  -H "Content-Type: application/json" \
  -d '{"host":"baidu.com","count":2}'
```

### Android APK

详见 `docs/BUILD.md`，核心命令：

```bash
cd network-tool-app
npm install
cordova build android            # Debug
cordova build android --release  # Release 未签名
```

产物路径：`network-tool-app/platforms/android/app/build/outputs/apk/`。

## 编码约定

### Python（`server.py`）

- 单文件，所有路由、装饰器、辅助函数集中管理。
- 所有对外接口必须叠加 `@rate_limit_decorator` 与 `@concurrent_limit_decorator`（顺序：限流 → 并发 → 业务）。
- 用户输入的主机名必须经 `validate_host()` 校验（正则 `^[a-zA-Z0-9._-]+$` + 白名单）。
- 返回结构统一包含 `success` 字段；失败时附 `error` 与（可选）`raw_output`。
- 跨平台命令分支用 `platform.system()` 判断，不要硬编码 OS。
- 使用 `subprocess.run(..., capture_output=True, text=True, timeout=...)`，必须设超时。
- 不引入新的 Web 框架或 ORM；保持 Flask 单文件形态。

### 前端（`index.html` × 2）

- 纯原生 HTML/CSS/JS，**不引入** React/Vue/构建工具/打包器。
- 单文件交付：CSS 用 `<style>`，JS 用 `<script>`，不外链资源（CSP 与 APK 离线友好）。
- 异步任务用 `AbortController` 管理，`startTask/stopTask/endTask` 三段式，任务名与 DOM 元素 ID 约定 `<name>-start-btn` / `<name>-stop-btn` / `<name>-result`。
- 结果框用 `result-box` + `success/error/info/warning` 样式类，等宽字体，`white-space: pre-wrap`。
- 历史记录写入 `localStorage['netDiagHistory']`，最多 20 条，新记录 `unshift` 到队首。
- 端口解析支持 `80,443,1-1000` 混合格式，单次扫描上限 1000 个端口。
- 修改任一前端文件时，**同步修改另一份**，保持 PC 与 APK 行为一致。

### Cordova（`network-tool-app/`）

- `config.xml` 是唯一配置入口；`package.json` 仅声明 `cordova-android ^15`，不引入 JS 依赖。
- `res/xml/network_security_config.xml` 允许明文流量到 `localhost`、`127.0.0.1`、`tencent.markli.cn`。新增需要明文的后端域名时在此追加 `<domain>`。
- `AndroidInsecureFileModeEnabled=true` 与 `AndroidMixedContentMode=always` 是 APK 加载 `file://` 前端并访问 HTTP 后端的必要设置，不要关闭。
- `www/js/index.js` 当前为 Cordova 模板默认实现，未实际使用；如需原生能力再在此挂接 Cordova 插件。

## 安全约束（修改安全相关代码前必读）

配置集中在 `server.py` 顶部的「安全配置」区块：

| 配置 | 默认 | 作用 |
|------|------|------|
| `DOMAIN_WHITELIST` | `[]`（不限制） | 支持通配符 `*.example.com`；非空时仅放行匹配域名 |
| `RATE_LIMIT_REQUESTS` | 30 | 每 IP 每 `RATE_LIMIT_WINDOW` 秒最大请求数 |
| `RATE_LIMIT_WINDOW` | 60 | 限流时间窗口（秒） |
| `MAX_CONCURRENT_TASKS` | 5 | 全局并发信号量，超限返回 503 |

- `validate_host()` 是所有涉及用户输入主机的接口的统一入口，新增接口必须调用。
- `check_domain_whitelist()` 支持通配符，不要改成只支持精确匹配。
- `get_client_ip()` 依次读 `X-Forwarded-For` → `X-Real-IP` → `remote_addr`，反代场景下限流依赖前两个头，Nginx 必须正确透传（见 `docs/DEPLOY.md`）。
- 端口扫描、批量 Ping 在前后端均有数量上限，调整时两端同步。
- HTTP 检测接口 `verify=False` 用于绕过自签名证书，仅限诊断场景，不要迁移到对外公开服务。

## API 契约速查

完整字段见 README.md，此处仅列约束：

| 路由 | 方法 | 流式 | 关键约束 |
|------|------|------|----------|
| `/api/ping` | POST | 否 | `count`、`timeout` 由前端固定传 4/10 |
| `/api/dns` | POST | 否 | `dns_server` 必须为 IPv4，`type` 默认 `A` |
| `/api/traceroute` | POST | SSE | 事件 `start`/`hop`/`done`/`error`，`hop.data` 固定字段 |
| `/api/mtr` | POST | 否 | Windows 用 `tracert` 模拟，Linux 优先 `mtr --json` |
| `/api/port` | POST | 否 | `port` 1-65535，`timeout` 默认 5 |
| `/api/http` | POST | 否 | `verify=False`，跟随重定向 |
| `/api/batch_ping` | POST | 否 | `hosts` 上限 100 |
| `/api/ip` | GET | 否 | 多源回退：ip-api → ipinfo |
| `/api/whois` | POST | 否 | 前端优先终端本地 RDAP（rdap.org），失败或 IP 输入时降级后端 `whois` 命令 |
| `/api/cert` | POST | 否 | 后端 `openssl s_client \| x509` 管道，返回 subject/issuer/日期/SAN/days_left |
| `/health` | GET | 否 | 返回 `{"status":"ok","version":"2.0"}` |

改动响应字段时，务必同步改前端解析代码（两个 `index.html`）。

## 常见陷阱

1. **PC 与 APK 前端不同步** —— 两份 `index.html` 看似相同，但 APK 版本的 `getApiBase()` 多了 `file:` 协议分支。只改一份会导致 APK 无法连接后端。
2. **MTR 在 Windows 不可用** —— 代码用 `tracert` 循环模拟，性能差且字段不全；生产环境推荐 Linux + 原生 `mtr`。
3. **Traceroute 在 Linux 无 `traceroute` 命令时** —— 回退到 Python 原生 socket 实现，需 root 权限创建 `SOCK_RAW`，非 root 下会失败。
4. **Nginx 反代未关 buffering** —— SSE 会被缓冲，前端看不到逐跳输出。`proxy_buffering off; proxy_cache off;` 必加。
5. **CORS 全开** —— `CORS(app)` 默认放行所有来源，生产环境建议配合 `Origin` 白名单收紧。
6. **`/health` 版本号** —— 返回 `"version":"2.0"`，前端用于协议探测；改版本号会让 `setApiServer()` 的健康检查失败。
7. **`server.py` 的 `main()` 重复打印** —— 现有代码把启动信息打印了两次，属已知冗余，清理时不要改动 `app.run` 参数。

## 不要做的事

- 不要把后端拆成多文件 / 引入蓝图（Blueprints）。当前单文件形态是有意为之。
- 不要给前端引入 npm 依赖或构建链。单文件原生 JS 是交付约束。
- 不要在 `network-tool-app/platforms/android/` 下手工改代码，会被下次 `cordova build` 覆盖。
- 不要关闭 `AndroidInsecureFileModeEnabled` 或 `AndroidMixedContentMode=always`，否则 APK 无法访问 HTTP 后端。
- 不要把 `DOMAIN_WHITELIST` 当成访问控制的主要手段 —— 它只校验目标主机，不限制来源。
- 不要为限流/并发装饰器引入 Redis 等外部依赖，当前基于进程内 `defaultdict` + `threading.Lock` 是刻意的轻量实现。

## 提交检查清单

修改本仓库时，提交前自查：

- [ ] 两个 `index.html` 是否同步修改？
- [ ] 新增/修改 API 字段是否同步更新了 README 的接口文档与前端解析？
- [ ] 新增系统命令依赖是否补进了 `docs/DEPLOY.md`？
- [ ] 涉及安全的改动是否更新了上面的「安全约束」表？
- [ ] 是否动了 `platforms/android/` 下自动生成的代码？（应为否）
- [ ] SSE 事件结构变更是否同步了 `processLine()` 与 Nginx 配置说明？
