---
name: "flask-vanilla-netdiag-scaffold"
description: "生成 Flad 单文件后端 + 原生单页前端 + Cordova APK 三种交付形态的网络诊断/运维工具骨架。当用户要新建一个类似 network-tool 的轻量网络诊断、后台、运维小工具时使用；包含目录、PWA/Cordova 配置、安全校验、SSE 与异步任务约定。"
---

# Flask + Vanilla + Cordova 轻量网络诊断工具脚手架

该 SKILL 用于一键搭建「网 → 后端执行系统命令 → 前端展示」的轻量网络/运维诊断工具，交付三端：**PC 网页（PWA）**、**Android APK（Cordova）**、后端**Python Flask 单文件**。前端为**纯原生 HTML/CSS/JS 单文件**，不引入框架与构建链。

参考项目骨架见 `server.py`、`index.html`、`network-tool-app/config.xml`。

---

## 一、目标形态与目录结构

```
<project>/
├── server.py              # Flask 单文件后端：API + 静态托管
├── index.html             # PC 前端：单文件（CSS/JS 内联），PWA 可安装
├── manifest.json          # PWA 配置
├── AGENTS.md              # 面向 AI 代理的项目指令
├── <app>/                 # Cordova Android 项目
│   ├── config.xml         # 唯一配置入口（权限/SDK/状态栏/明文流量）
│   ├── package.json       # 仅声明 cordova-android ^15
│   ├── www/index.html     # 与 PC 前端基本一致（含 file: 协议分支）
│   ├── www/manifest.json  # APK 内 PWA 配置
│   └── res/xml/network_security_config.xml  # 明文流量允许列表
└── docs/
    ├── BUILD.md           # APK 构建与签名
    └── DEPLOY.md          # 部署/迁移/Nginx/systemd/Docker/防火墙
```

**铁律：PC 前端与 `www/index.html` 必须保持同步**，否则 PC 与 APK 行为分裂。

## 二、后端最佳实践（`server.py`）

1. **单文件**：所有路由、装饰器、辅助函数集中管理；不拆分模块、不引入蓝图（Blueprint）与第三方 Web 框架/ORM。
2. **装饰器叠加顺序**：每个对外接口按 `@rate_limit_decorator` → `@concurrent_limit_decorator` → 业务 依次叠加。
3. **主机安全校验统一入口**：所有涉及用户输入主机的接口必须调用 `validate_host()`：
   - 正则 `^[a-zA-Z0-9._-]+$` 防命令注入；
   - 叠加 `check_domain_whitelist()`（支持 `*.example.com` 通配符，空列表=不限制）。
4. **返回结构统一**：带 `success` 字段；失败附 `error`，可选 `raw_output`。
5. **系统命令**：
   - `subprocess.run(..., capture_output=True, text=True, timeout=...)`，**必须设超时**；
   - 跨平台用 `platform.system()` 分支（Windows `ping -n`/Linux `ping -c`、`tracert`/`traceroute`、`nslookup`/`dig` 等）；
   - 命令缺失时提供降级（如 traceroute/MTR 回退 Python socket、文本解析）。
6. **限流/并发**：进程内 `defaultdict` + `threading.Lock` 的轻量实现，不引入 Redis 等外部依赖。客户端 IP 依次读 `X-Forwarded-For` → `X-Real-IP` → `remote_addr`。
7. **SSE 流式**：长任务（如 traceroute）用 `text/event-stream` + `Response(stream_with_context(...))` 逐跳输出 `data: {...}\n\n`；Nginx 反代必须 `proxy_buffering off`。
8. **CORS**：`CORS(app)` 默认全开，生产建议配合 Origin 白名单收紧。

### 安全配置区块（集中置于顶部）
| 配置 | 默认 | 作用 |
|------|------|------|
| `DOMAIN_WHITELIST` | `[]`（不限制） | 通配符 `*.example.com`；非空时仅放行匹配域名 |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW` | 30 / 60 | 每 IP 每窗口请求上限，超限 429 |
| `MAX_CONCURRENT_TASKS` | 5 | 全局并发信号量，超限 503 |

## 三、前端最佳实践（`index.html`）

1. **纯原生**：CSS 用 `<style>`、JS 用 `<script>` 内联，不引入 React/Vue/打包器，不外链资源（CSP 与 APK 离线友好）。单文件交付。
2. **异步任务三段式**：`startTask(name)` / `stopTask(name)` / `endTask(name)` + `AbortController` 管理取消；元素 ID 约定 `<name>-start-btn` / `<name>-stop-btn` / `<name>-result`。
3. **结果框**：`result-box` + `success/error/info/warning` 样式类，等宽字体，`white-space: pre-wrap`。
4. **历史记录**：写入 `localStorage['netDiagHistory']`，最多 20 条，新记录 `unshift` 到队首。
5. **端口/批量输入上限**：前后端同步限制（如端口 `80,443,1-1000` 混合解析，单次 ≤1000；批量主机 ≤100）。
6. **深色主题**：`#1a1a2e` 渐变背景，响应式 + 触摸优化。

### API 基址自动探测 `getApiBase()`（两处 index.html 必须一致）
- 优先 `localStorage['apiServer']`（用户通过 ⚙️ 设置）；
- 否则若 `window.location.protocol === 'file:'`（APK 环境）→ 回退内置默认后端地址；
- 否则取当前页面 `origin + pathname` 前缀（PC 自部署场景）。

### 协议自动探测 `setApiServer()`
保存前调用 `/health` 探测 HTTPS/HTTP 可用性，**优先 HTTPS**；这是 APK 在混合内容策略下可用的关键，勿删。

## 四、PWA / Cordova 配置

- **`manifest.json`**：`short_name`、`display: standalone`、`background_color`/`theme_color: #1a1a2e`、192/512 图标。
- **`config.xml`**：
  - `android-minSdkVersion=22`、`android-targetSdkVersion=36`；
  - `AndroidInsecureFileModeEnabled=true`（加载 file:// 前端）；
  - `AndroidMixedContentMode=always`（访问 HTTP 后端）——**两项必要，勿关闭**；
  - `StatusBarOverlaysWebView=false`、`StatusBarBackgroundColor=#1a1a2e`。
- **`network_security_config.xml`**：允许明文流量到 `localhost`、`127.0.0.1` 及用户后端域名；新增明文域名时在此追加 `<domain>`。
- **`platforms/android/`** 为构建产物，**不要手工编辑**（会被下次 `cordova build` 覆盖）。

## 五、文档与命令

- `docs/BUILD.md`：前置环境（Node/Java/Android SDK/Cordova）、`cordova build android [--release]`、签名（keytool/apksigner）、常见问题。
- `docs/DEPLOY.md`：后端运行（`pip install flask flask-cors requests`；`python3 server.py`）、systemd、Nginx 反代（含 `proxy_buffering off`）、Docker、防火墙、迁移、系统工具安装说明。
- 新增依赖系统命令的功能时，**同步补进 `docs/DEPLOY.md` 的系统工具安装说明**。
- 后端验证：`curl localhost:8080/health` → `{"status":"ok","version":"2.0"}`。

## 六、不要做的事

- 把后端拆成多文件 / 引入蓝图。
- 给前端引入 npm 依赖或构建链（单文件原生 JS 是交付约束）。
- 手工改 `platforms/android/` 下自动生成代码。
- 关闭 `AndroidInsecureFileModeEnabled` 或 `AndroidMixedContentMode=always`。
- 把 `DOMAIN_WHITELIST` 当作访问控制主手段（它只校验目标主机，不限制来源）。
- 为限流/并发装饰器引入 Redis 等外部依赖。

## 七、生成步骤（一键模板）

脚手架生成顺序：后端 `server.py`（安全配置区块 + 各 API 路由）→ PC `index.html`（快速操作区 + 各 Tab ）→ `manifest.json` → Cordova 三件套（`config.xml`/`www/index.html`/`network_security_config.xml`）→ `docs/BUILD.md` + `docs/DEPLOY.md` → `AGENTS.md`。随后按 2 中 System 提示安装系统工具包后 `python3 server.py` 验证 `/health` 与首个接口。

## 八、通用提交自查清单

- [ ] 两个 `index.html` 是否同步修改？
- [ ] 新增/修改 API 字段是否同步更新 README 接口文档与前端解析？
- [ ] 新增系统命令依赖是否补进 `docs/DEPLOY.md`？
- [ ] 涉及安全的改动是否更新安全配置表？
- [ ] 是否误改了 `platforms/android/`？（应为否）
- [ ] SSE 事件结构变更是否同步 `processLine()` 与 Nginx 配置说明？