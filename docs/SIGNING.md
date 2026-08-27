# APK 签名配置说明（Security · 安全）

> ⚠️ **重要安全警告，请先阅读**
>
> 本仓库**绝不提交**真实的签名密钥库（`.keystore` / `.jks`）与含密码的配置（`release-signing.properties`）。
> 这些文件包含**私钥与密码**，一旦推送到公开仓库即永久泄露（git 历史无法真正清除），攻击者可借此
> 冒充官方给恶意 APK 签名（供应链攻击），你的所有用户都会受牵连。
>
> 因此 `.gitignore` 已强制忽略：
> ```
> signing/
> *.keystore
> *.jks
> release-signing.properties
> ```
> 真实文件必须保存在本机 + 私密备份（不要放进仓库）。

---

## 一、真实签名文件在哪（本地）

以下文件**只在本地生成与保存**，属于你个人/团队的机密资产：

| 文件 | 说明 |
|------|------|
| `networktool-release.keystore` | 签名密钥库（含私钥与证书），**丢失则永远无法覆盖升级** |
| `release-signing.properties` | 构建时引用的签名配置（含密码） |

> 这两份文件已备份到仓库外的 `/root/network-tool-keystore-backup/`，请再额外备份到 U 盘/密码管理器。

---

## 二、脱敏模板（可提交到仓库的部分）

若需要把**签名配置结构**分享给协作者/新机器，只允许使用下面的**占位符模板**，不填真实值：

### `signing/release-signing.properties`（占位模板，不要填真值入库）

```properties
# Network Tool release signing configuration
# ⚠️ 此文件含私钥密码，仅在本地使用，严禁提交到仓库
# 本地使用时把下方 YOUR_ 占位符替换为真实值，并确保文件不被 git 跟踪

storeFile=/绝对路径/networktool-release.keystore
storePassword=YOUR_STORE_PASSWORD
keyAlias=YOUR_KEY_ALIAS
keyPassword=YOUR_KEY_PASSWORD
```

---

## 三、在新机器上如何生成/恢复签名

### 方式 A · 恢复已有密钥（推荐，确保升级一致）

把备份的 `networktool-release.keystore` 及密码恢复到本机 `signing/` 目录即可。**必须用原密钥**，否则无法覆盖升级。

### 方式 B · 全新生成密钥（仅首次使用）

```bash
keytool -genkeypair -v \
  -keystore networktool-release.keystore \
  -alias networktool \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass YOUR_STORE_PASSWORD \
  -keypass YOUR_KEY_PASSWORD \
  -dname "CN=Network Tool Team, OU=Network Tool, O=NetworkTool, L=Shanghai, ST=Shanghai, C=CN"
```

> **注意**：生成后请立即妥善备份 keystore + 两条密码。以后所有版本都必须用它签名。

---

## 四、用签名配置构建 Release APK

环境变量先指到 Android SDK，然后在 Cordova 项目目录执行：

```bash
export ANDROID_HOME=/path/to/android-sdk
export ANDROID_SDK_ROOT=$ANDROID_HOME
cd network-tool-app

# 方式 1（推荐）：gradle assembleRelease 直接出签名 APK
cd platforms/android
./gradlew assembleRelease \
  -PcdvReleaseSigningPropertiesFile=/绝对路径/signing/release-signing.properties

# 方式 2：通过 cordova 命令行（会同时产出 AAB 与 APK）
cd ../..
cordova build android --release \
  --gradleArg=-PcdvReleaseSigningPropertiesFile=/绝对路径/signing/release-signing.properties
```

**产物路径：**
- 签名 APK：`platforms/android/app/build/outputs/apk/release/app-release.apk`
- AAB（Play 商店用）：`platforms/android/app/build/outputs/bundle/release/app-release.aab`

### 仅构建 arm64-v8a 架构

在 `platforms/android/app/build-extras.gradle` 中加入（纯 WebView 应用无原生库时可选）：

```groovy
android {
    defaultConfig {
        ndk {
            abiFilters 'arm64-v8a'
        }
    }
}
```

---

## 五、验证签名是否生效

```bash
APKSIGNER=$(ls /path/to/android-sdk/build-tools/*/apksigner | tail -1)

# 校验签名（输出 Signer #1 certificate 且 v1/v2 为 true 即成功）
"$APKSIGNER" verify --verbose --print-certs app-release.apk

# 查看包信息
aapt dump badging app-release.apk | grep -E "package: name|versionName|minSdk"
```

---

## 六、签名密钥管理清单（安全）

- [ ] keystore 与密码**不提交**到任何仓库，仅保存在本机 + 私密备份
- [ ] 备份 `networktool-release.keystore` + 两条密码到 U 盘/密码管理器
- [ ] keystore 绝不通过聊天/邮件明文传输
- [ ] 若怀疑密钥泄露：立即作废，更换 alias 重新签名整个应用链路
- [ ] 换电脑/换人接手时，交接 keystore 走加密通道（如密码管理器共享）

---

## 相关文档

- [BUILD.md](BUILD.md) — APK 构建环境与命令
- [DEPLOY.md](DEPLOY.md) — 后端部署
