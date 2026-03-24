# 网络诊断工具 (Network Diagnostic Tool)

一个面向IT运维人员的网络诊断工具，支持PC端网页访问和Android APK安装使用。

## 功能特性

- **Ping检测** - ICMP连通性测试
- **路由跟踪** - Traceroute路径追踪
- **MTR诊断** - 网络质量综合分析
- **DNS查询** - 域名解析检测
- **端口扫描** - TCP端口状态检测
- **HTTP检测** - 网站可达性测试
- **批量检测** - 多主机批量Ping
- **本机信息** - 公网IP和网络信息

## 项目结构

```
network-tool/
├── server.py              # Python后端服务
├── index.html             # PC端前端页面
├── manifest.json          # PWA配置文件
├── network-tool-app/      # Cordova移动端项目
│   ├── config.xml         # Cordova配置
│   ├── package.json       # Node.js依赖
│   ├── www/               # 移动端前端源码
│   │   └── index.html
│   ├── res/               # 应用资源(图标等)
│   └── platforms/         # 平台特定代码
│       └── android/
└── docs/                  # 文档目录
    ├── BUILD.md           # APK构建说明
    └── DEPLOY.md          # 部署迁移说明
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
    "dns_server": "114.114.114.114",  // DNS服务器
    "type": "A"                       // 记录类型
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "domain": "google.com",
    "records": ["142.250.190.78"]
  }
  ```

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

### 9. 健康检查
- **接口**: `GET /health`
- **描述**: 服务健康状态检查
- **响应**: `{"status": "ok", "version": "2.0"}`

## 使用说明

### PC端使用

1. 启动后端服务：
   ```bash
   python3 server.py
   ```

2. 浏览器访问：
   - 本机: `http://localhost:8080`
   - 局域网: `http://服务器IP:8080`

### Android APK使用

1. 安装APK文件到手机
2. 首次打开需要配置API服务器地址
3. 点击右上角⚙️图标设置服务器地址
4. 输入格式: `http://服务器IP:8080`

## 前端说明

### 技术栈
- 纯HTML/CSS/JavaScript
- 无框架依赖
- 响应式设计

### 主要功能模块

1. **快速操作区** - 8个功能入口按钮
2. **标签页切换** - Ping/路由/MTR/DNS/HTTP/本机
3. **结果展示** - 等宽字体显示，支持成功/失败/警告样式
4. **历史记录** - 本地存储最近20条检测记录
5. **API设置** - 支持自定义后端服务器地址

### 移动端适配
- 响应式布局
- 触摸优化
- 深色主题

## 安全特性

- **请求限流**: 每IP每60秒最多30次请求
- **并发限制**: 最多5个并发任务
- **域名白名单**: 可配置允许检测的域名(默认不限制)

## 依赖要求

### 后端
- Python 3.8+
- Flask
- flask-cors
- requests

### Android构建
- Node.js 16+
- Cordova CLI
- JDK 11+
- Android SDK

## 许可证

MIT License
