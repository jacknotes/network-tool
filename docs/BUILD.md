# APK 构建说明

## 前置环境要求

| 工具 | 版本要求 | 说明 |
|------|---------|------|
| Node.js | 16+ | JavaScript 运行环境 |
| npm | 随 Node.js 安装 | 包管理工具 |
| JDK | 11+ | Java 开发工具包 |
| Android SDK | API 34+ | Android 开发工具包 |
| Gradle | 8.x | Android 构建工具（Cordova 自动管理） |
| Cordova CLI | 12+ | 移动应用构建框架 |

## 环境配置

### 1. 安装 Node.js

```bash
# 检查版本
node -v    # 需要 v16+
npm -v
```

### 2. 安装 JDK

```bash
# Ubuntu/Debian
sudo apt install openjdk-17-jdk

# CentOS/RHEL
sudo yum install java-17-openjdk-devel

# 验证
java -version
```

### 3. 配置 Android SDK

```bash
# 设置环境变量（加入 ~/.bashrc 或 ~/.zshrc）
export ANDROID_HOME=/path/to/android-sdk
export ANDROID_SDK_ROOT=$ANDROID_HOME
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools

# 安装必要组件
sdkmanager "platforms;android-34"
sdkmanager "build-tools;34.0.0"
sdkmanager "platform-tools"
```

### 4. 安装 Cordova CLI

```bash
npm install -g cordova

# 验证安装
cordova --version
```

## 构建步骤

### 方式一：使用已有的 platforms 项目（推荐）

项目已包含完整的 Android 平台代码，可直接构建：

```bash
# 进入 Cordova 项目目录
cd network-tool-app

# 构建 Debug APK
cordova build android

# 构建 Release APK（未签名）
cordova build android --release
```

### 方式二：从头添加平台构建

如果需要重新初始化 Android 平台：

```bash
cd network-tool-app

# 添加 Android 平台（如 platforms 目录损坏时）
cordova platform add android

# 安装依赖
npm install

# 构建
cordova build android
```

### 方式三：使用 Gradle 直接构建

```bash
cd network-tool-app/platforms/android

# Debug 版本
./gradlew assembleDebug

# Release 版本
./gradlew assembleRelease
```

## APK 输出路径

构建完成后，APK 文件位于：

```
network-tool-app/platforms/android/app/build/outputs/apk/
├── debug/
│   └── app-debug.apk          # Debug 版本
└── release/
    └── app-release-unsigned.apk  # Release 未签名版本
```

## Release APK 签名

### 1. 生成签名密钥

```bash
keytool -genkey -v -keystore network-tool.keystore \
  -alias networktool \
  -keyalg RSA \
  -keysize 2048 \
  -validity 3650
```

### 2. 签名 APK

```bash
# 对齐
zipalign -v 4 \
  app-release-unsigned.apk \
  app-release-aligned.apk

# 签名
apksigner sign \
  --ks network-tool.keystore \
  --ks-key-alias networktool \
  --out app-release-signed.apk \
  app-release-aligned.apk
```

### 3. 验证签名

```bash
apksigner verify app-release-signed.apk
```

## 常见问题

### Gradle 下载慢

在 `gradle.properties` 中添加镜像源：

```properties
org.gradle.jvmargs=-Xmx2048m
# 国内镜像
systemProp.http.proxyHost=mirrors.aliyun.com
systemProp.https.proxyHost=mirrors.aliyun.com
```

或在 `build.gradle` 的 `repositories` 中添加：

```groovy
maven { url 'https://maven.aliyun.com/repository/google' }
maven { url 'https://maven.aliyun.com/repository/public' }
```

### Android SDK 找不到

```bash
# 确认环境变量生效
echo $ANDROID_HOME
echo $ANDROID_SDK_ROOT

# 或在 local.properties 中手动指定
# sdk.dir=/path/to/android-sdk
```

### JDK 版本不兼容

```bash
# 查看当前 JDK
java -version

# 切换 JDK 版本（多版本共存时）
update-alternatives --config java
```

### 构建内存不足

```bash
# 增加 Gradle 内存
export GRADLE_OPTS="-Xmx4096m -XX:MaxPermSize=512m"
```

### Cordova 版本不兼容

```bash
# 查看当前版本
cordova -v

# 查看已安装的平台版本
cordova platform ls

# 更新平台
cordova platform update android@latest
```
