# 双源网络诊断模式 + 5 项工具扩展 — 设计文档

> 日期：2026-08-26
> 状态：已确认，待转入实施计划
> 作者：用户与 AI 协同设计（brainstorming 流程）

## 1. 目标与范围

### 1.1 背景

项目当前有两个交付目标：

1. **Linux 服务器 Web 对外服务**：以部署服务器为源，向目标执行诊断（已实现）
2. **Android APP**：以手机为源，向目标执行诊断（当前未实现——APP 只是"远程控制台"，所有诊断仍由后端执行）

经 brainstorming 确认，当前 APP 并未实现"以手机为源"，且 Web 端也具备部分"终端本地"能力。本次改造旨在补齐"用户终端作为测试源"的能力。

### 1.2 核心目标

- 支持「服务器视角」与「用户终端视角」双测试源
- Web 端和 APP 端在能力允许范围内共享"终端本地"视角
- 新增 5 项常用运维工具（Whois、TCP Ping、DNS 记录扩展、SSL 证书、CIDR 计算器）

### 1.3 改造范围

- 现有代码增量改造
- 不引入 Web 框架/构建链
- 不引入 Cordova 原生插件（ICMP Ping 原生插件留作未来升级）
- 不拆分后端单文件、不引入蓝图
- 不动 `network-tool-app/platforms/android/` 自动生成代码

---

## 2. 功能视角矩阵（核心设计）

| 功能 | 后端接口 | Web 端 | APP 端 | badge |
|------|----------|--------|--------|-------|
| ICMP Ping | `/api/ping` | 服务器 | 服务器 | `源：服务器` |
| Traceroute | `/api/traceroute` (SSE) | 服务器 | 服务器 | `源：服务器` |
| MTR | `/api/mtr` | 服务器 | 服务器 | `源：服务器` |
| 批量 Ping | `/api/batch_ping` | 服务器 | 服务器 | `源：服务器` |
| DNS（A/AAAA/NS/MX/TXT/CNAME/SOA/PTR） | `/api/dns`（降级） | **本地 DoH** | **本地 DoH** | `源：本机`/`源：服务器` |
| HTTP | 不用 | **本地 fetch** | **本地 fetch** | `源：本机` |
| 端口扫描 | 不用 | **本地 fetch** | **本地 fetch** | `源：本机` |
| 本机信息 | 不用 | **本地** | **本地** | `源：本机` |
| **Whois** 🆕 | `/api/whois`（降级） | **本地 RDAP** | **本地 RDAP** | `源：本机`/`源：服务器` |
| **TCP Ping** 🆕 | 不用 | **本地 fetch** | **本地 fetch** | `源：本机` |
| **SSL 证书** 🆕 | `/api/cert` | 服务器 | 服务器 | `源：服务器` |
| **CIDR 计算器** 🆕 | 不用 | **本地计算** | **本地计算** | 无 badge（纯计算） |

**注**：
- `源：本机`（Web）/ `源：手机`（APK）通过 `window.location.protocol === 'file:'` 判断区分
- CIDR 为纯计算无"源"概念，不加 badge
- SSL 证书为"单源"特例（终端浏览器无法拿证书细节），仅服务器端

---

## 3. 新工具实现细节

### 3.1 Whois 查询

- **终端本地**：`fetch('https://rdap.org/domain/${domain}')`，拿 JSON（注册商、注册/到期日期、状态）
  - RDAP 是 WHOIS 的现代 HTTP 版，跨域友好
- **降级**：RDAP 失败或用户填了 IP（非域名）→ 调后端 `/api/whois`（`subprocess` 跑 `whois` 命令）
- **badge**：RDAP 成功 `源：本机`，降级 `源：服务器`

### 3.2 TCP Ping

- **终端本地**：`fetch(\`http://${host}:${port}\`, {mode:'no-cors', signal})` 带超时，测握手延迟，重复 N 次算丢包率和延迟
- **参数**：host、port、count（默认 4）、timeout（默认 3s）
- **badge**：`源：本机`
- **限制**：`no-cors` 无法区分握手成功与跨域拒绝，结果可能偏乐观（与现有端口扫描同源限制）

### 3.3 DNS 记录类型扩展

- **改造现有 `/api/dns` 和前端 `doDns()`**：`type` 支持 `A`（现有）、`AAAA`、`NS`、`MX`、`TXT`、`CNAME`、`SOA`、`PTR`
- **DoH 本地**：DoH JSON 协议天然支持上述类型，`fetch` 时传 `type` 参数即可
- **UI**：DNS Tab 增加记录类型下拉框
- **降级**：纯 IP DNS 服务器 + 非 A 类型 → 调后端 `dig`/`nslookup`

### 3.4 SSL 证书检测

- **仅服务器端**：`/api/cert` 用 `openssl s_client -connect ${host}:${port} -servername ${host}` 解析证书链
- **返回**：颁发者、主题、有效期、剩余天数、是否过期、链长度
- **badge**：`源：服务器`（终端浏览器无法拿证书细节）
- **限制**：仅 HTTPS 目标；需服务器装 `openssl`

### 3.5 CIDR/IP 子网计算器

- **纯前端 JS**：无网络请求，无后端接口
- **功能**：输入 `192.168.1.0/24` → 网络号、广播地址、可用范围、掩码、主机数
- **badge**：无（纯计算无"源"概念）
- **实现**：纯 JS 位运算，两端共用

---

## 4. 后端改造（`server.py`）

### 4.1 新增接口

#### `POST /api/whois`
- `subprocess` 跑 `whois ${host}`
- 解析关键字段：Registrar、Creation Date、Registry Expiry Date、Domain Status
- 返回 `{success, host, registrar, creation_date, expiry_date, status, raw_output, source, source_ip}`
- 叠加 `@rate_limit_decorator` + `@concurrent_limit_decorator`
- `validate_host()` 校验

#### `POST /api/cert`
- `subprocess` 跑 `openssl s_client -connect ${host}:${port} -servername ${host} -showcerts`
- 解析证书链：颁发者、主题、有效期起止、剩余天数、是否过期、链长度
- 返回 `{success, host, port, issuer, subject, not_before, not_after, days_remaining, is_expired, chain_length, raw_output, source, source_ip}`
- 叠加装饰器 + `validate_host()`
- 仅 HTTPS（port 443 或 url 以 https 开头）

### 4.2 现有接口加字段

`/api/ping`、`/api/traceroute`（SSE start 事件）、`/api/mtr`、`/api/batch_ping`、`/api/dns`、`/api/whois`、`/api/cert` 响应增加：

```python
'source': 'server',
'source_ip': get_local_ip(),
```

### 4.3 DNS 接口扩展

`/api/dns` 的 `type` 参数支持扩展（`AAAA/NS/MX/TXT/CNAME/SOA/PTR`），`dig`/`nslookup` 命令传对应类型。

### 4.4 约束（遵守 AGENTS.md）

- 新接口叠加 `@rate_limit_decorator` + `@concurrent_limit_decorator`
- `validate_host()` 校验 host
- `whois`/`openssl` 依赖补进 `docs/DEPLOY.md`
- 不拆单文件、不引入蓝图

---

## 5. 前端改造（`index.html` × 2，两端同步）

### 5.1 CSS

```css
.source-badge { display:inline-block; padding:2px 6px; border-radius:6px; font-size:10px; margin-left:8px; }
.source-badge.server { background:rgba(255,170,0,0.2); color:#ffaa00; }
.source-badge.local   { background:rgba(0,255,136,0.2); color:#00ff88; }
```

### 5.2 HTML

- 8 个现有功能 + 5 个新功能 = 13 个 `.section-title` 加 badge（CIDR 除外）
- 快速操作区从 4×2 改为 5×3 布局（15 格，留 2 格空位或放设置入口），避免宫格数不对称
- DNS Tab 增加记录类型下拉框（A/AAAA/NS/MX/TXT/CNAME/SOA/PTR）
- DNS 服务器下拉框加 `+` 自定义按钮
- 新增 4 个 Tab：`whois`、`tcp-ping`、`cert`、`cidr`
  - TCP Ping 独立 Tab，不与端口扫描合并（功能定位不同：TCP Ping 测延迟丢包，端口扫描测开闭状态）

### 5.3 JS

#### 新增函数
- `getSourceLabel(kind)`：生成 badge 文本，`kind ∈ {server, local}`，区分 Web（`源：本机`）/ APK（`源：手机`）
- `loadDnsServers()` / `addDnsServer()` / `deleteDnsServer()`：DNS 服务器管理，存 `localStorage['netDiagDnsServers']`
- `doWhois()`：RDAP 本地 + 降级后端
- `doTcpPing()`：本地 fetch 带超时
- `doCert()`：调后端 `/api/cert`
- `doCidr()`：纯 JS 计算

#### 改造函数
- `doDns()`：DoH 本地 + 纯 IP 降级后端 + 多类型支持 + 下拉框 `change` 动态更新 badge
- `doHttp()`：已是本地，加 badge + 结果首行源标识
- `doPortCheck()`：已是本地，加 badge
- `doPing/doTraceroute/doMtr/doBatchCheck`：调后端，结果首行显示 `源IP: x.x.x.x`

### 5.4 badge 规则

- 调后端的 5 项（Ping/Traceroute/MTR/批量Ping/SSL）→ `源：服务器`，结果首行 `源IP`
- 终端本地的 6 项（DNS/HTTP/端口/本机/Whois/TCP Ping）→ `源：本机`（Web）或 `源：手机`（APK）
- DNS/Whois 降级时动态切 `源：服务器`
- CIDR 无 badge

---

## 6. DNS 服务器管理（自动识别协议）

### 6.1 预置列表

写入 `localStorage['netDiagDnsServers']`，`builtin:true`：

| 名称 | 值 | 类型 |
|------|-----|------|
| 阿里 DNS | `https://223.5.5.5/dns-query` | DoH |
| 腾讯 DNS | `https://1.12.12.12/dns-query` | DoH |
| Google DNS | `https://8.8.8.8/resolve` | DoH |
| Cloudflare | `https://1.1.1.1/dns-query` | DoH |
| 114 DNS | `114.114.114.114` | 传统（降级后端） |
| 百度 DNS | `180.76.76.76` | 传统（降级后端） |

### 6.2 用户自定义

- 入口：DNS Tab 下拉框旁 `+` 按钮，弹出表单填「名称 + 地址」
- 存储：`localStorage['netDiagDnsServers']`，格式 `[{name, url, builtin:false}]`
- 预置 4 个 DoH + 2 个传统也可被用户隐藏/删除（删除后恢复默认）

### 6.3 协议识别

- 地址 `https://` 开头 → DoH 本地执行，badge `源：本机/手机`
- 否则 → 调后端 `/api/dns`，badge `源：服务器`
- 下拉框 `change` 事件动态更新 badge

---

## 7. 端口扫描本地化细节

- **实现**：`fetch(\`http://${host}:${port}\`, {mode:'no-cors', signal: controller.signal})` + `setTimeout` 超时控制
- **判定**：`no-cors` 模式下 `fetch` 不抛错视为"可达"（端口开放），抛错或超时视为"关闭"
- **限制**：
  - `no-cors` 无法区分"端口关闭"和"目标拒绝跨域"，HTTPS 目标可能误判
  - 只能测 TCP，且无法拿服务名（保留现有 `services` 映射表硬编码）
  - 比 `socket.connect_ex` 精度低，但对运维"端口是否开着"的快速判断够用
- **上限不变**：单次扫描 1000 个端口（前端 `parsePorts` 已有校验）

---

## 8. 错误处理与降级

| 场景 | 处理 |
|------|------|
| DoH 请求失败（网络/CORS） | 结果框显示错误，建议切换 DNS 服务器或用纯 IP（降级后端） |
| 端口扫描 `fetch` 全部超时 | 提示"目标可能不支持跨域探测，建议用后端视角" |
| HTTP `no-cors` 失败 | 显示不可达（维持现状） |
| 后端 `source_ip` 获取失败 | `get_local_ip()` 已有回退到 `127.0.0.1`，显示该值 |
| APP 未配置后端地址且选了"降级后端"的 DNS | 提示"此 DNS 服务器需后端支持，请先配置 API 地址" |
| Whois RDAP 失败 | 降级调后端 `/api/whois` |
| SSL `openssl` 未安装 | 返回错误，提示安装 `openssl` |
| TCP Ping 目标跨域拒绝 | 结果偏乐观，UI 标注限制说明 |

---

## 9. 文档同步

### 9.1 README.md
- 功能特性加 5 项
- API 接口加 `whois`/`cert`
- DNS 类型扩展说明
- 安全约束表补 `whois`/`openssl`

### 9.2 AGENTS.md
- 新增"双源模式"小节
- API 契约表加 2 行（`/api/whois`、`/api/cert`）
- 系统命令依赖表加 `whois`/`openssl`
- 提交清单加"双源 badge 是否两端同步？"项

### 9.3 docs/DEPLOY.md
- 系统工具安装加 `whois`、`openssl`

---

## 10. 不在范围（YAGNI）

- **不引入** Cordova 原生插件做 ICMP Ping（H3 留作未来升级）
- **不引入** root 模式 Traceroute/MTR（H4 留作未来升级）
- **不引入** Nmap（跟端口扫描重叠、终端做不了）
- **不加** ARP/路由表/接口查询（属服务器自检，定位不符）
- **不加** 测速（跨域目标难找、两端能力都不够好）
- **不重写** 后端单文件、**不引入** npm 构建链（遵守 AGENTS.md 硬约束）
- **不动** `network-tool-app/platforms/android/` 自动生成代码
- **不改** 限流/并发装饰器（双源模式不影响安全配置）

---

## 11. 实施顺序（6 步，每步两端同步）

按风险递增分 6 步，每步两端同步：

1. **后端加 `source`/`source_ip` 字段**（最安全，只增不改）
2. **前端加 badge CSS + 现有 8 个 Tab 标 badge + 结果首行源标识**（纯展示）
3. **DNS 改造**：DoH 本地 + 服务器管理 + 多类型 + 降级
4. **端口扫描/HTTP 本地化**（已是本地，补 badge 和源标识）
5. **新增 Whois + TCP Ping + CIDR**（3 项纯前端或本地+降级）
6. **新增 SSL 证书**（后端 openssl + 前端调）

---

## 12. 提交检查清单

修改本仓库时，提交前自查：

- [ ] 两个 `index.html` 是否同步修改？
- [ ] 新增/修改 API 字段是否同步更新了 README 的接口文档与前端解析？
- [ ] 新增系统命令依赖（`whois`/`openssl`）是否补进了 `docs/DEPLOY.md`？
- [ ] 涉及安全的改动是否更新了 AGENTS.md 的「安全约束」表？
- [ ] 是否动了 `platforms/android/` 下自动生成的代码？（应为否）
- [ ] SSE 事件结构变更是否同步了 `processLine()` 与 Nginx 配置说明？
- [ ] **双源 badge 是否两端同步？**（新增）
- [ ] **`source`/`source_ip` 字段是否所有后端接口都加了？**（新增）

---

## 附录：brainstorming 决策记录

| 决策点 | 选项 | 选择 |
|--------|------|------|
| 双源模式 | A 双源 / B 纯本地 / C 远程控制台 / D root 原生 | **A** |
| 本地化范围 | A1 全 4 项 / A2 分批 / A3 最小 / A4 原生 DNS | **A1** |
| UI 呈现 | C1 badge / C2 结果首行 / C3 折叠区 / C4 双做 | **C1** |
| DNS 实现 | D1 纯 DoH / D2 精简 / D3 降级 / D4 原生 | **E2 自定义+预置+自动识别** |
| 协议识别 | E1 严格 DoH / E2 自动识别 / E3 用户选 | **E2** |
| HTTP 精度 | F1 可达性 / F2 cors 降级 / F3 走后端 / F4 双跑 | **F1** |
| 后端源标识 | G1 靠 badge / G2 加字段 / G3 警告 / G4 双做 | **G2** |
| 双源覆盖范围 | H1 仅 APP / H2 APP+Web / H3 +原生ICMP / H4 全 | **H2** |
| 新工具 | I1 全 5 项 / I2 2 项 / I3 下次 / I4 自选 | **I1** |
