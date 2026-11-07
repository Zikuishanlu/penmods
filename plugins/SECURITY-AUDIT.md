# PenMods 插件包安全审计报告

审计时间：2026-10-25　｜　对象：`C:\Users\The_never_land\Desktop\plugin` 下 10 个插件包
方式：纯静态分析（解包 + QML/JS 阅读 + 原生 ELF 符号与字符串提取），**未在设备上动态运行**

---

## 一、总体结论

这批插件**没有发现后门、木马、隐藏外联或持久化驻留**：6 个原生二进制全部为 aarch64 ELF，字符串与符号构成高度自洽（都是"哔哩哔哩客户端 / 番茄阅读器 / 终端 / 播放器"该有的样子），没有硬编码 C2、没有 `curl|sh`、没有 base64 载荷、没有自启动写入，所有对外域名只有 bilibili 系、open-meteo、wttr.in、geetest 和**一个裸 IP**。

真正的风险来自三处**设计本身**，而不是恶意代码：

1. **shell_plugin 是一个 root 交互式终端** —— 装它等于把整机 root shell 交给拿到设备的人。
2. **fanqie_plugin 用明文 HTTP 直连裸 IP `101.35.133.34:5000`** —— 阅读/搜索内容在链路上可被读取和篡改。
3. **bili_plugin 拉起多个本地服务**（8000 后端、8666 短信登录）并自动化过极验验证码 —— 本地接口无鉴权、cookie 明文落盘、账号有风控风险。

风险总览：

| 插件 | 等级 | 一句话 |
|---|---|---|
| shell_plugin | 🔴 严重（设计性） | 任意命令执行，root 权限，无沙箱 |
| fanqie_plugin | 🟠 高 | 明文 HTTP + 裸 IP 第三方，流量可被 MITM |
| bili_plugin | 🟠 中高 | 本地无鉴权 API、8666 `/pull` 交付 cookie、自动过极验、cookie 明文存储 |
| texteditor | 🟡 中 | `file://` XHR 可读写任意路径（root 下=任意文件覆盖） |
| browser | 🟡 中低 | 可抓任意 URL/`file://`（含本机文件），但内容经过转义，XSS 面已消除 |
| weather | 🟢 低中 | 把公网 IP 送给 B 站换取城市；日志写本地文件 |
| calculator | 🟢 低 | `eval` 白名单有效，注入已封堵 |
| 2048 / minesweeper | 🟢 低 | 纯本地逻辑 |

整合包 `chajian_fixed.zip` 与散装包**逐文件 sha256 完全一致**（见附录），不是另一套代码，可放心二选一。

---

## 二、分级风险清单

### 🔴 S1　shell_plugin：root 终端（设计如此，但风险最高）

- `libshell_plugin.so` 内是 Konsole `Vt102Emulation` 终端仿真 + `ShellController` 伪终端（`adoptExistingPty`、`writeToMaster`、`armMasterReader`、`sendKey/sendInput/sendCommand`），`qml/main.qml` 提供完整软键盘（Ctrl/Alt/Shift、^C/^D）。
- 二进制含 `execve`，**不含任何 URL/IP，不依赖 libQt5Network** → 没有隐藏外联。
- 但插件在 PenMods 里与主程序同进程、**以 root 运行、无沙箱**。因此"能打字"等于"能 `rm -rf /`、能改写 /userdisk、能起守护进程"。
- 附带疑点：`metadata.json` 作者字段写的是 **"OpenAI"**，与其它插件（"姓胡的胡萝卜 & DeepSeek"）不一致，来源标注不规范。

**处置**：只从可信来源安装；不用时删除或改名 `main_so`；不要把设备借给他人。

### 🟠 H1　fanqie_plugin：明文 HTTP 直连裸 IP

- 唯一上游：`http://101.35.133.34:5000`，路由 `/api/search`、`/api/detail`、`/api/content`、`/api/discover`、`/api/discover/style`、`/api/book`，参数含 `book_id`、`item_id`、`page`、`gender`。
- **无 TLS、无证书校验、无域名**：同一 Wi-Fi 下的攻击者（ARP/DNS/热点劫持）可读取你看什么书、搜什么词，并可返回被篡改的正文。
- 该 IP 的归属与运营方无法从代码判断，属于"不明第三方"。

**处置**：介意隐私就别在公共 Wi-Fi 下用；作者侧应换 HTTPS + 域名 + 证书固定。

### 🟠 H2　bili_plugin：多个本地服务 + 自动过验证码

1. **后端 `server`（Go）**：`setupRoutes`、`handleLoginImport`、`handleVideoPlayurl/Merge`、`handleVideoSubtitleASS*`、`handleLikeToggle/CoinAdd/FavToggle`、`handleHistory*`、`loadCookies/saveCookies`、`appSign/piliPlusAppSign`、`validateMergePath`。**没有任何鉴权中间件**（只有 `loggingMiddleware`、`recoverMiddleware`）。
   - 客户端固定连 `http://127.0.0.1:8000`，端口可用 `PORT` 环境变量覆盖；二进制里同时存在 `127.0.0.1` 与 `0.0.0.0` 两个字面量，**静态无法 100% 断定默认绑定地址**（见第六节复核命令）。
   - 一旦实际绑定 `0.0.0.0`，局域网内任何人可无鉴权调用：导出 cookie、导入登录、触发下载、写文件（`handleVideoMerge` 落盘 `/userdisk/Music/bili/...`）→ 升级为高危。
2. **`bili-sms`（Go）**：短信登录助手，监听 `:8666`，提供 `/pull`（`handlePull` + `collectCookiesForPull` + `extractRefreshToken`，把登录后的 **cookies 与 refresh_token** 以 JSON 交回），并内嵌 jQuery + 极验 geetest SDK，走 `passport.bilibili.com/x/passport-login/{captcha,sms/send,web/login/sms}`。启动日志是 `服务启动，监听于：http://%s/verify.html`——**设计意图就是让你用手机/电脑浏览器访问 `http://笔的IP:8666/verify.html` 去拖滑块**，所以极可能监听 `0.0.0.0`。
   - 后果：登录窗口期内，同网段任何人都能打开该页、也能调 `/pull` 抢走刚登录的会话凭据（该接口未见 token 校验，字面量里只有裸 `/pull`）。
   - 另一层风险：**自动化过极验 + 短信登录**属于绕过平台人机校验，账号有被风控/封禁的可能，也不符合 B 站用户协议。
3. cookie 以明文 JSON（`cookies.json`）存在插件目录，无加密、无权限收紧。

**处置**：只在自家网络用短信登录，用完关掉；不要在有他人的热点下登录；能扫码登录就别用短信登录。

### 🟡 M1　texteditor：任意路径读写

`main.qml` 用 `XMLHttpRequest` 对 `file://` 做 GET/PUT（`stripFilePrefix`/`addFilePrefix`），可读写**进程权限内任意路径**（root 下遍及全盘）；书签/历史存 LocalStorage 且书签 url 可为任意路径。
这是"文本编辑器"的应有能力，不是漏洞，但它把"设备文件系统"变成用户可写对象——误操作可覆盖系统文件。

**处置**：编辑系统文件前先备份；不要用它打开来源不明的脚本再"另存为"到可执行路径。

### 🟡 M2　browser：可读取本机文件的文本浏览器

- 输入框支持把 `/`、`~`、盘符开头转成 `file://`，把 `localhost`/纯 IP 转成 `http://`，其余含 `.` 的补 `https://`；预设一言、必应、B 站；搜索模板 `https://cn.bing.com/search?q=%1`。
- 内容渲染走 `escapeHtml()`（转义 `& < >`）后放进 `<pre>` + `Text.RichText`，**页面里的 HTML/JS 不会被执行**，也没有 `<img>` 可加载 → 不存在"网页读本地文件再外传"或追踪像素链路。
- 残余风险：能通过 `file://` 显示本机文件内容（仅本地可见）、能访问 `127.0.0.1:8000` 等本机服务并把 JSON 显示出来（无 JS 则无法进一步利用）。

**处置**：低风险，正常使用即可。

### 🟢 L1　weather

- 定位：`https://api.live.bilibili.com/client/v1/Ip/getInfoNew`（把公网 IP 交给 B 站换城市）；城市天气 `https://wttr.in/<city>?format=j2`；预报 `https://api.open-meteo.com/v1/forecast`。
- 日志追加写 `file:///userdisk/PenMods/plugins/weather/weatherlog.txt`（GET 读旧 + PUT 覆盖，保留 `maxLogLines` 行）。
- 数据全在 LocalStorage（`WeatherDB`）。风险仅为"IP/城市透露给第三方"，属常规天气应用行为。

### 🟢 L2　calculator

`calculate()` 先做符号替换，再用 probe 白名单：

```js
.replace(/\d+(?:\.\d+)?[eE][-+]?\d+/g, "")
.replace(/Math\.(?:sqrt|cbrt|log10|log|sin|asin|cos|acos|PI|E)/g, "")
.replace(/fact\(/g, "(");
if (/[A-Za-z_$`'"\[\]{};:=<>!?&|~\\]/.test(probe)) { /* 不支持的输入 */ }
```

数字、运算符、白名单函数之外**不允许任何字母、引号、方括号、分号**，`Math.constructor` 之类也被拦。`eval` 可安全保留。（这正是 `chajian_fixed` 的加固项，实测有效。）

### 🟢 L3　2048 / minesweeper

纯 QML 本地游戏，状态存 `QtQuick.LocalStorage` 且用 `?` 参数化 `executeSql`，无网络、无文件系统访问。

---

## 三、跨插件共性问题

1. **无沙箱、同进程、root**：PenMods 插件与主程序共享地址空间和权限，插件之间没有隔离。**任意一个插件被替换成恶意版本 = 整机沦陷**。信任边界完全取决于"zip 从哪来"。
2. **插件包无签名/无校验**：zip 里没有签名文件，安装器不做完整性校验，作者字段纯属自述（`shell_plugin` 甚至写 "OpenAI"）。建议自行留存 sha256（附录）。
3. **本地服务无鉴权**：bili 的 8000/8666 都是"裸 HTTP + 无 token"，安全性依赖"只监听回环"这一假设。
4. **敏感数据明文落盘**：cookie（`cookies.json`）、书签、阅读记录均为明文，设备丢失即泄露。
5. **QML 里拼 SQL/HTML**：bili 的 `VideoDetailPage.qml`（2628 行）在 QML 内拼 SQL 与富文本，属"数据当代码"的老问题；本地库可被书名/视频标题里的特殊字符破坏，富文本若未转义还有注入面（当前未发现可利用点，但建议改为参数化 + 转义）。

---

## 四、处置建议

**如果你是设备使用者**

- 只装需要的：`shell_plugin` 除非你确实要敲命令，否则别装；装了就别把设备借人。
- `fanqie_plugin` 避免在公共 Wi-Fi 下阅读。
- `bili_plugin` 用扫码登录优先；用短信登录时确保同网段没有陌生人，用完即退出。
- `texteditor`/`browser` 不要打开来源不明的脚本/页面后另存到系统目录。
- 留存附录哈希，重装前比对，防止被替换。

**如果你是作者**

- fanqie：上 HTTPS + 域名 + 证书固定；至少校验响应来源。
- bili：`server` 与 `bili-sms` 显式绑定 `127.0.0.1`；`/pull` 加一次性 token 并限制请求 Origin；cookie 用 `0600` 权限并考虑加密；移除"自动过极验"逻辑，改走官方扫码/短信流程。
- 全部插件：富文本统一转义、SQL 全部参数化、日志不落敏感字段（`maskSensitive` 已有，保持）。

---

## 五、需在设备上复核的两项（静态无法定论）

在笔上（或同环境）执行：

```sh
ss -ltnp | grep -E ':(8000|8666)'      # 看绑定是 127.0.0.1 还是 0.0.0.0
ps -ef | grep -E 'server|bili-sms|mpv' # 看实际起的进程与参数
```

- 若 8000 显示 `0.0.0.0:8000` → bili 后端对局域网无鉴权开放，**升级为高危**，应立即限制。
- 若 8666 显示 `0.0.0.0:8666` → 短信登录期间同网段可 `/pull` 取凭据（与静态推断一致）。

---

## 六、方法与局限

- 环境无 binutils，用 Python 3.14 自行解析 ELF 段表、动态符号、字符串表；Go 二进制通过 `main.*` 符号与字符串表还原功能面。
- **未做动态分析**：aarch64 二进制无法在 x64 Windows 上运行，未做内存/网络抓包验证；`.so` 已 strip，理论上仍可能存在通过间接调用隐藏的行为（未发现证据）。
- 结论基于"代码能说明的意图"，对**服务端**（`101.35.133.34:5000`、bilibili 接口）的行为无法审计。
- 所有 zip 均通过 `unzip -t` 完整性校验；`chajian_fixed.zip` 内 5 个包与散装包 sha256 逐一相同。

---

## 附录：文件哈希（sha256）

插件包：

```
1268513170826ad36551cea38ed80227f687dd94dda806b7fee1b73aa9bf4e24  2048.zip
aefc0294a258432f920479aa53d102b19f90950e02d05b6c6de70fd71bc576b2  bili_plugin.zip
ce28b545a98424bf179b7e7f4b191d247f7d5d0bfdc41ed0a76602c75fcf5919  browser.zip
57e654639ff1a247b193867ef86a1df844dcd62b82b8ad95618a680e8d45097d  calculator.zip
7980750977e539b75990cdc5b9a820fd0553e6c192c67f07234672669e7f0479  chajian_fixed.zip
761cc274a859d1d09dc09b27fa40178b73ac40a2016a28e2de08e4afb649563a  fanqie_plugin.zip
d1200a45414c4d0c8869c90d42c3dbf4da6bb5d3ad9f507717d64182df660596  minesweeper.zip
234d0c219a72d7f653486c72ad1d1700da70732f67950141a3eca4fe94e14c09  shell_plugin.zip
8258034b2af0e0acc71c9b72fdf469df3c0b638cc7c2277dd0b8f7f58ae09dce  texteditor.zip
37efe7bd2bcede552647fc788ba27e0732e61dca788f909bca59161b8fcf07b7  weather.zip
```

原生二进制：

```
f3d38eeb40026b821c835c4b835d3c78c6565d41f0b4ec40d497e8993851318b  bili_plugin/server
2d9989828f78d78b25a981cf69525f8349914eab93fa4916fea4c3921d97fd51  bili_plugin/bili-sms
127b4ae106526fb8711110b1ca2bff559208fe9dfa565f854b6147431133e4a4  bili_plugin/libbili_plugin.so
0c81a21c83883d65c4d1befaef94d3b9a507ffefecdd7cf3fe34b1397a3b06f0  bili_plugin/qml/FFmpegPlayer/libffmpegplayerplugin.so
136713eef648efd8c7cb5c99c95ab5fc32ed96094cd7e62ab696a5c01c735f6b  fanqie_plugin/libfanqie_plugin.so
8d90da4208947bce19939a395777e6a4f3a70087cc6a2c530b890ae3cc3f718d  shell_plugin/libshell_plugin.so
```
