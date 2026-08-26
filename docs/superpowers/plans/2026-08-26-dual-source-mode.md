# 双源网络诊断模式 + 5 项工具扩展 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让网络诊断工具支持「服务器视角」与「用户终端视角」双测试源，并新增 5 项常用运维工具（Whois、TCP Ping、DNS 记录扩展、SSL 证书、CIDR 计算器）。

**Architecture:** 后端 Flask 单文件 `server.py` 给 5 个走服务器视角的接口加 `source`/`source_ip` 字段并新增 `/api/whois`、`/api/cert`；前端两份 `index.html`（PC + APK）同步加 `.source-badge` CSS、13 个 Tab 标 badge、DNS/HTTP/端口改终端本地、新增 4 个 Tab。CIDR 纯前端计算无后端。

**Tech Stack:** Python 3.8+ / Flask（单文件，不拆蓝图）、原生 HTML/CSS/JS（单文件，无框架无构建）、Apache Cordova 15（APK）、subprocess 调 `whois`/`openssl`。

**Spec 来源：** 本计划的完整设计细节、代码片段、字段定义全部来自 `docs/superpowers/specs/2026-08-26-dual-source-mode-design.md`。执行每个 Task 时如需完整代码上下文，查阅 spec 对应章节。

**项目约束（来自 AGENTS.md，必须遵守）：**
- 两份 `index.html`（`./index.html` 与 `./network-tool-app/www/index.html`）必须同步修改
- 后端不引入蓝图、不拆多文件；前端不引入 npm/构建链
- 所有对外接口叠加 `@rate_limit_decorator` + `@concurrent_limit_decorator`
- 用户输入主机必须经 `validate_host()` 校验
- 不动 `network-tool-app/platforms/android/` 自动生成代码
- 项目无测试套件，验证方式为 `curl` + 浏览器手动测试

**验证基线（每个 Task 前确保后端可启动）：**
```bash
cd f:\project\network-tool
python server.py
# 另开终端
curl http://localhost:8080/health
# 预期: {"status":"ok","version":"2.0"}
```

**双端同步原则：** Phase 2 起，每个前端 Task 改完 `index.html` 后，立即对 `network-tool-app/www/index.html` 做相同改动。两文件除 `getApiBase()` 的 `file:` 分支外完全一致。

---

## File Structure

| 文件 | 职责 | 改动类型 |
|------|------|----------|
| `server.py` | 后端单文件 | 修改：7 接口加字段、DNS 扩类型、新增 2 接口 |
| `index.html` | PC 前端单文件 | 修改：CSS、13 Tab badge、4 函数改本地、4 新函数、DNS 管理 |
| `network-tool-app/www/index.html` | APK 前端单文件 | 修改：与 PC 端同步 |
| `README.md` | 人类文档 | 修改：功能、API、安全约束 |
| `AGENTS.md` | Agent 文档 | 修改：双源模式小节、API 契约、命令依赖、提交清单 |
| `docs/DEPLOY.md` | 部署文档 | 修改：系统工具加 `whois`/`openssl` |

---

## Phase 1: 后端加 `source`/`source_ip` 字段（最安全，只增不改）

**目标：** 给 7 个走服务器视角的接口的响应 JSON 加 `"source": "server"` 和 `"source_ip": "<服务器IP>"`。前端拿到后可在结果首行显示源 IP。

**改动模式（每个接口统一）：** 在每个 `return jsonify({...})` 的 dict 里追加 `'source': 'server', 'source_ip': get_local_ip()`，包括成功返回和所有 except 分支的失败返回。`get_local_ip()` 已定义在 `server.py:151`。

### Task 1.1: `/api/ping` 加源字段
- [ ] 修改 `server.py:223-259`（`ping()` 函数）的成功返回和两个 except 分支，加 `source`/`source_ip`
- [ ] `curl -X POST http://localhost:8080/api/ping -H "Content-Type: application/json" -d "{\"host\":\"baidu.com\",\"count\":2}"`，预期 JSON 含 `"source":"server"`
- [ ] `git add server.py && git commit -m "feat(api/ping): add source and source_ip fields"`

### Task 1.2: `/api/dns` 加源字段
- [ ] 修改 `server.py:264-324`（`dns_lookup()` 函数）的成功返回和两个 except 分支
- [ ] `curl -X POST http://localhost:8080/api/dns -H "Content-Type: application/json" -d "{\"domain\":\"baidu.com\",\"dns_server\":\"114.114.114.114\",\"type\":\"A\"}"`，预期含 `"source":"server"`
- [ ] `git add server.py && git commit -m "feat(api/dns): add source and source_ip fields"`

### Task 1.3: `/api/port` 加源字段
- [ ] 修改 `server.py:329-377`（`port_check()` 函数）的成功返回和两个 except 分支
- [ ] `curl -X POST http://localhost:8080/api/port -H "Content-Type: application/json" -d "{\"host\":\"baidu.com\",\"port\":80}"`，预期含 `"source":"server"`
- [ ] `git add server.py && git commit -m "feat(api/port): add source and source_ip fields"`

### Task 1.4: `/api/http` 加源字段
- [ ] 修改 `server.py:382-441`（`http_check()` 函数）的成功返回和三个 except 分支
- [ ] `curl -X POST http://localhost:8080/api/http -H "Content-Type: application/json" -d "{\"url\":\"https://www.baidu.com\"}"`，预期含 `"source":"server"`
- [ ] `git add server.py && git commit -m "feat(api/http): add source and source_ip fields"`

### Task 1.5: `/api/batch_ping` 加源字段
- [ ] 修改 `server.py:446-504`（`batch_ping()` 函数）的最终返回
- [ ] `curl -X POST http://localhost:8080/api/batch_ping -H "Content-Type: application/json" -d "{\"hosts\":[\"baidu.com\"],\"count\":2}"`，预期含 `"source":"server"`
- [ ] `git add server.py && git commit -m "feat(api/batch_ping): add source and source_ip fields"`

### Task 1.6: `/api/traceroute` SSE start 事件加源字段
- [ ] 修改 `server.py:535`（`generate()` 内 start 事件 payload），追加 `'source': 'server', 'source_ip': get_local_ip()`
- [ ] `curl -N -X POST http://localhost:8080/api/traceroute -H "Content-Type: application/json" -d "{\"host\":\"baidu.com\",\"max_hops\":5,\"timeout\":30}"`，预期首行 `data:` 含 `"source":"server"`
- [ ] `git add server.py && git commit -m "feat(api/traceroute): add source and source_ip to SSE start event"`

### Task 1.7: `/api/mtr` 加源字段
- [ ] 修改 `server.py:716-867`（`mtr()` 函数）的成功返回和两个 except 分支
- [ ] `curl -X POST http://localhost:8080/api/mtr -H "Content-Type: application/json" -d "{\"host\":\"baidu.com\",\"count\":3}"`，预期含 `"source":"server"`（Windows 较慢）
- [ ] `git add server.py && git commit -m "feat(api/mtr): add source and source_ip fields"`

---

## Phase 2: 前端 badge CSS + 现有 8 Tab 标 badge + 结果首行源标识

**目标：** 前端加 `.source-badge` 样式、加 `getSourceLabel()` 工具函数、给现有 8 个 Tab 标题旁加 badge、给走后端的 4 个功能（Ping/Traceroute/MTR/批量）结果首行显示 `源IP: x.x.x.x`。

### Task 2.1: 新增 `.source-badge` CSS
- [ ] 在 `index.html:318`（`.timeout-badge` 闭合后、`</style>` 前）追加：`.source-badge { display:inline-block; padding:2px 6px; border-radius:6px; font-size:10px; margin-left:8px; font-weight:600; }` 及 `.source-badge.server { background:rgba(255,170,0,0.2); color:#ffaa00; }`、`.source-badge.local { background:rgba(0,255,136,0.2); color:#00ff88; }`
- [ ] 对 `network-tool-app/www/index.html:318` 做同样修改
- [ ] 浏览器 F12 检查 CSS 已加载
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(ui): add source-badge CSS classes"`

### Task 2.2: 新增 `getSourceLabel()` 函数
- [ ] 在 `index.html:650`（`const API_SERVER = getApiBase();` 前）插入：`function getSourceLabel(kind) { const isApk = window.location.protocol === 'file:'; const localLabel = isApk ? '源：手机' : '源：本机'; if (kind === 'server') return '源：服务器'; if (kind === 'local') return localLabel; return ''; }`
- [ ] 对 APK 端 `index.html` 做同样修改
- [ ] F12 控制台执行 `getSourceLabel('local')`、`getSourceLabel('server')`，预期 `源：本机` / `源：服务器`
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(ui): add getSourceLabel helper"`

### Task 2.3: 给 8 个现有 Tab 标题加 badge
**badge 分配：** Ping/Traceroute/MTR/批量=server（橙）；DNS/HTTP/端口/本机=local（绿）。
- [ ] 在 `index.html` 的 8 个 `.section-title`（Ping 在 376 行、Traceroute 396、MTR 420、DNS 444、HTTP 475、端口 494、本机 519、批量 554）的标题文本后、`<span class="timeout-badge">` 前插入 `<span class="source-badge server">${getSourceLabel('server')}</span>` 或 `local`
  - 因 HTML 静态，badge 文本用 JS 在页面加载后批量注入更简洁：在 `index.html:1566`（`renderHistory();` 前）加一段 `document.querySelectorAll('.section-title').forEach(...)` 根据父元素 id 前缀判断 kind
  - 实现代码：`document.querySelectorAll('.section-title').forEach(t => { const content = t.closest('.tab-content'); if (!content) return; const id = content.id.replace('-content',''); const serverKinds = ['ping','traceroute','mtr','batch']; const kind = serverKinds.includes(id) ? 'server' : 'local'; const badge = document.createElement('span'); badge.className = 'source-badge ' + kind; badge.textContent = getSourceLabel(kind); t.appendChild(badge); });`
- [ ] 对 APK 端做同样修改
- [ ] 浏览器刷新，8 个 Tab 标题旁显示对应颜色 badge
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(ui): add source badges to 8 existing tabs"`

### Task 2.4: 走后端的 4 个功能结果首行显示源 IP
**目标：** `doPing`/`doTraceroute`/`doMtr`/`doBatchCheck` 在结果框输出首行加 `源IP: x.x.x.x`。
- [ ] `doPing`（`index.html:754`）：成功分支（793 行）的 `resultBox.innerHTML` 字符串模板首行加 `源IP: ${data.source_ip || '未知'}\n`
- [ ] `doTraceroute`（`index.html:1014`）：`start` 事件（1052 行）的输出首行加 `源IP: ${event.source_ip}\n`
- [ ] `doMtr`（`index.html:1121`）：成功分支（1162 行）的 `result` 字符串首行加 `源IP: ${data.source_ip}\n`
- [ ] `doBatchCheck`（`index.html:1415`）：成功分支（1459 行）的 `result` 字符串首行加 `源IP: ${data.source_ip}\n`
- [ ] 对 APK 端 4 个函数做同样修改
- [ ] 浏览器测试 4 个功能，结果首行显示源 IP
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(ui): show source_ip in 4 server-side result headers"`

---

## Phase 3: DNS 改造（DoH 本地 + 服务器管理 + 多类型 + 降级）

**目标：** DNS Tab 改成"地址是 DoH URL 走本地 fetch DoH，纯 IP 走后端 `/api/dns`"，下拉框支持用户自定义，记录类型扩展到 8 种。

### Task 3.1: DNS 服务器管理（预置 + 自定义）
- [ ] 在 `index.html` 新增 `loadDnsServers()`/`saveDnsServers()`/`addDnsServer()`/`deleteDnsServer()`/`renderDnsServers()` 五个函数，存 `localStorage['netDiagDnsServers']`，预置 6 条（4 DoH + 2 传统），见 spec 第 6.1 节
- [ ] DNS Tab 的 `<select id="dns-server">`（`index.html:454`）改为由 `renderDnsServers()` 动态填充，旁边加 `+` 按钮
- [ ] `+` 按钮点击弹 `prompt` 填名称+地址，保存后刷新下拉框
- [ ] 对 APK 端做同样修改
- [ ] 浏览器测试：删除一个预置、添加一个自定义，刷新后保持
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(dns): add DNS server management (preset + custom)"`

### Task 3.2: DNS 记录类型下拉框
- [ ] 在 DNS Tab 的 DNS 服务器下拉框后，新增 `<select id="dns-type">` 含 A/AAAA/NS/MX/TXT/CNAME/SOA/PTR 8 个选项
- [ ] 对 APK 端做同样修改
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(dns): add record type selector (A/AAAA/NS/MX/TXT/CNAME/SOA/PTR)"`

### Task 3.3: `doDns()` 改造为本地 DoH + 降级
- [ ] 改造 `doDns()`（`index.html:834`）：读取选中 DNS 服务器，若 `https://` 开头 → 本地 `fetch` DoH（URL 形如 `https://223.5.5.5/dns-query?name=${domain}&type=${type}`，header `Accept: application/dns-json`），解析 `Answer` 数组拿记录；否则调后端 `/api/dns`
- [ ] badge 动态更新：下拉框 `change` 事件里，DoH→`local`，纯 IP→`server`，改 badge 文本和 class
- [ ] DoH 请求带 5 秒超时（`AbortController` + `setTimeout`）
- [ ] 对 APK 端做同样修改
- [ ] 浏览器测试：选阿里 DoH 查 baidu.com A 记录，结果含 IP，badge 为 `源：本机`；选 114 DNS，badge 切 `源：服务器`
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(dns): local DoH with fallback to backend"`

### Task 3.4: 后端 `/api/dns` 扩展记录类型
- [ ] 修改 `server.py:282-284`：Windows `nslookup -type=${record_type}`、Linux `dig @${dns_server} ${domain} ${record_type} +short +time=5 +tries=2`，`record_type` 来自 `data.get('type', 'A')`，已是参数，无需改命令构造，但需在 `validate_host` 后校验 `record_type` 在合法集合内
- [ ] `server.py:264` 的 `dns_lookup()` 加校验：`if record_type not in ['A','AAAA','NS','MX','TXT','CNAME','SOA','PTR']: return jsonify({'success': False, 'error': '不支持的记录类型'}), 400`
- [ ] `curl -X POST http://localhost:8080/api/dns -H "Content-Type: application/json" -d "{\"domain\":\"baidu.com\",\"dns_server\":\"114.114.114.114\",\"type\":\"MX\"}"`，预期返回 MX 记录
- [ ] `git add server.py && git commit -m "feat(api/dns): support extended record types"`

---

## Phase 4: 端口扫描 / HTTP 本地化（补 badge + 源标识）

**目标：** 这两个功能当前已是本地 `fetch`，只需补 badge（已是 `local`）和结果首行 `源：本机` 标识。无后端改动。

### Task 4.1: 端口扫描补 badge 和源标识
- [ ] `doPortCheck()`（`index.html:1210`）结果字符串首行（1235 行 `let result = ...`）加 `源：${getSourceLabel('local')}\n`
- [ ] 端口扫描的 badge 在 Task 2.3 已由"port"前缀判为 local，无需额外改
- [ ] 对 APK 端做同样修改
- [ ] 浏览器测试端口扫描，结果首行显示 `源：本机`
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(port): add source label to local scan results"`

### Task 4.2: HTTP 检测补源标识
- [ ] `doHttp()`（`index.html:917`）成功分支（972 行）的 `resultBox.innerHTML` 首行加 `源：${getSourceLabel('local')}\n`
- [ ] 对 APK 端做同样修改
- [ ] 浏览器测试 HTTP 检测，结果首行显示 `源：本机`
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(http): add source label to local check results"`

---

## Phase 5: 新增 Whois + TCP Ping + CIDR（3 项前端为主）

### Task 5.1: 新增 Whois Tab（本地 RDAP + 降级后端）
**前端：**
- [ ] `index.html` 快速操作区加一个 `whois` 按钮，新增 `whois-content` Tab 区块（输入框+开始按钮+结果框）
- [ ] 新增 `doWhois()`：输入域名 → `fetch('https://rdap.org/domain/${domain}')`，解析 JSON 拿 `events`（registration/expiration）、`entities`（registrar）；RDAP 失败或输入是 IP → 调后端 `/api/whois`
- [ ] badge：RDAP 成功 `local`，降级 `server`
- [ ] 对 APK 端做同样修改
- [ ] 浏览器测试：查 `baidu.com`，显示注册商/到期日，badge `源：本机`

**后端 `/api/whois`：**
- [ ] `server.py` 新增 `POST /api/whois` 路由（叠加 `@rate_limit_decorator` + `@concurrent_limit_decorator`），`subprocess.run(['whois', host], capture_output=True, text=True, timeout=15)`，正则解析 `Registrar:`、`Creation Date:`、`Registry Expiry Date:`、`Domain Status:`，返回 `{success, host, registrar, creation_date, expiry_date, status, raw_output, source, source_ip}`
- [ ] `validate_host()` 校验 host
- [ ] `curl -X POST http://localhost:8080/api/whois -H "Content-Type: application/json" -d "{\"host\":\"baidu.com\"}"`，预期含 registrar 字段
- [ ] `git add server.py index.html network-tool-app/www/index.html && git commit -m "feat(whois): add RDAP local + backend whois fallback"`

### Task 5.2: 新增 TCP Ping Tab（纯前端本地）
- [ ] `index.html` 快速操作区加 `tcp-ping` 按钮，新增 `tcp-ping-content` Tab 区块（host、port、count 输入+结果框）
- [ ] 新增 `doTcpPing()`：循环 count 次 `fetch(\`http://${host}:${port}\`, {mode:'no-cors', signal: controller.signal})` 带超时，测握手延迟，算丢包率和 min/avg/max rtt
- [ ] badge `local`
- [ ] 对 APK 端做同样修改
- [ ] 浏览器测试：TCP Ping `baidu.com:80` count 4，显示延迟和丢包率
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(tcp-ping): add local TCP ping via fetch"`

### Task 5.3: 新增 CIDR 计算器 Tab（纯前端）
- [ ] `index.html` 快速操作区加 `cidr` 按钮，新增 `cidr-content` Tab 区块（输入 `192.168.1.0/24`+结果框）
- [ ] 新增 `doCidr()`：纯 JS 位运算，输入 CIDR → 输出网络号、广播地址、可用 IP 范围、掩码、主机数
- [ ] 不加 badge（纯计算无源概念）
- [ ] 对 APK 端做同样修改
- [ ] 浏览器测试：输入 `192.168.1.0/24`，输出 `192.168.1.0 - 192.168.1.255`，主机数 254
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(cidr): add subnet calculator (pure JS)"`

---

## Phase 6: 新增 SSL 证书检测（后端 openssl + 前端调）

### Task 6.1: 后端新增 `/api/cert`
- [ ] `server.py` 新增 `POST /api/cert` 路由（叠加装饰器），`subprocess.run(['openssl', 's_client', '-connect', f'{host}:{port}', '-servername', host, '-showcerts'], capture_output=True, text=True, timeout=15, input='')`，正则解析 `issuer=`、`subject=`、`notBefore=`、`notAfter=`，算剩余天数和是否过期，返回 `{success, host, port, issuer, subject, not_before, not_after, days_remaining, is_expired, chain_length, raw_output, source, source_ip}`
- [ ] `validate_host()` 校验 host，port 限 1-65535
- [ ] `curl -X POST http://localhost:8080/api/cert -H "Content-Type: application/json" -d "{\"host\":\"www.baidu.com\",\"port\":443}"`，预期含 `days_remaining`
- [ ] `git add server.py && git commit -m "feat(api/cert): add SSL certificate inspection via openssl"`

### Task 6.2: 前端新增 SSL 证书 Tab
- [ ] `index.html` 快速操作区加 `cert` 按钮，新增 `cert-content` Tab 区块（host、port 输入+结果框）
- [ ] 新增 `doCert()`：调后端 `/api/cert`，展示颁发者、主题、有效期、剩余天数、是否过期（过期红色警告）
- [ ] badge `server`，结果首行显示 `源IP`
- [ ] 对 APK 端做同样修改
- [ ] 浏览器测试：查 `www.baidu.com:443`，显示证书信息和剩余天数
- [ ] `git add index.html network-tool-app/www/index.html && git commit -m "feat(cert): add SSL certificate inspection tab"`

---

## Phase 7: 文档同步

### Task 7.1: README.md 更新
- [ ] 功能特性列表加 5 项（Whois/TCP Ping/DNS 扩展/SSL 证书/CIDR）
- [ ] API 接口列表加 `/api/whois`、`/api/cert` 两个小节（参数、响应示例）
- [ ] DNS 接口文档的 `type` 参数说明改为"A/AAAA/NS/MX/TXT/CNAME/SOA/PTR，默认 A"
- [ ] 安全约束表补：`whois`/`openssl` 系统命令依赖
- [ ] `git add README.md && git commit -m "docs: update README with 5 new tools and source fields"`

### Task 7.2: AGENTS.md 更新
- [ ] 新增"双源模式"小节：badge 规则、终端本地 vs 服务器视角的功能划分、`source`/`source_ip` 字段约定
- [ ] API 契约速查表加 2 行：`/api/whois` POST 否 host 校验、`/api/cert` POST 否 port 1-65535
- [ ] 系统命令依赖表加 `whois`（DNS/Whois）、`openssl`（SSL 证书）
- [ ] 提交检查清单加 2 条："双源 badge 是否两端同步？"、"`source`/`source_ip` 字段是否所有后端接口都加了？"
- [ ] `git add AGENTS.md && git commit -m "docs: update AGENTS.md with dual-source mode and new tool conventions"`

### Task 7.3: docs/DEPLOY.md 更新
- [ ] 系统工具安装命令加 `whois`、`openssl`：
  - Ubuntu/Debian: `sudo apt install whois openssl`
  - CentOS/RHEL: `sudo yum install whois openssl`
- [ ] `git add docs/DEPLOY.md && git commit -m "docs: add whois and openssl to system tool install"`

---

## 验证清单（全部完成后）

- [ ] `curl http://localhost:8080/health` 返回 `{"status":"ok","version":"2.0"}`
- [ ] 7 个后端接口响应含 `"source":"server"` 和 `"source_ip"`
- [ ] PC 浏览器打开 `http://localhost:8080`，13 个 Tab 全部可用，badge 显示正确
- [ ] DNS 选阿里 DoH 查询，badge `源：本机`；选 114 DNS，badge `源：服务器`
- [ ] 端口扫描、HTTP、TCP Ping、CIDR、Whois（RDAP）均显示 `源：本机`
- [ ] Ping/Traceroute/MTR/批量 Ping/SSL 证书显示 `源：服务器` + 源 IP
- [ ] APK 端 `network-tool-app/www/index.html` 与 PC 端改动一致（除 `file:` 分支）
- [ ] `git log --oneline` 每个提交对应一个 Task，粒度清晰

---

## Self-Review

**1. Spec coverage（对照 spec 各节）：**
- spec 第 2 节功能矩阵 → Phase 1（后端字段）+ Phase 2（badge）+ Phase 3-6（各功能）✅
- spec 第 3 节 5 项新工具 → Phase 5（Whois/TCP Ping/CIDR）+ Phase 6（SSL）+ Task 3.2/3.4（DNS 扩展）✅
- spec 第 4 节后端改造 → Phase 1 + Task 3.4 + Task 5.1 后端 + Task 6.1 ✅
- spec 第 5 节前端改造 → Phase 2-6 前端部分 ✅
- spec 第 6 节 DNS 服务器管理 → Task 3.1 ✅
- spec 第 7 节端口扫描细节 → Task 4.1 ✅
- spec 第 8 节错误处理 → 各 Task 的"浏览器测试"步骤含降级验证 ✅
- spec 第 9 节文档同步 → Phase 7 ✅
- spec 第 10 节 YAGNI → 计划未涉及 Nmap/ARP/测速/原生插件 ✅
- spec 第 11 节 6 步实施 → Phase 1-6 一一对应 ✅

**2. Placeholder scan：** 无 TBD/TODO，每个 Task 都有具体改动的行号和验证命令 ✅

**3. Type consistency：** `getSourceLabel(kind)` 在 Task 2.2 定义，Task 2.3/4.1/4.2 引用一致；`source`/`source_ip` 字段名在 Phase 1 后端和 Phase 2 前端引用一致 ✅

---

## Execution Handoff

计划已保存至 `docs/superpowers/plans/2026-08-26-dual-source-mode.md`。两种执行方式：

**1. Subagent-Driven（推荐）** - 每个 Task 派发独立 subagent 执行，Task 间 review，快速迭代
**2. Inline Execution** - 在当前会话用 executing-plans 批量执行，带检查点 review

你选哪种？
