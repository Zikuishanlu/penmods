# PenMods 管理器（工作名）

面向 Windows 10/11 的有道词典笔管理工具：连接（ADB/SSH）、设备信息、安装 PenMods 与可选组件、
OTA 更新、插件与安装包管理、插件市场、文件/终端/配置编辑。
界面为 PySide6 + Qt Quick（QML）渲染的桌面程序（仪器感深色主题 + 左侧功能侧边栏），**不是本地网页**；设计系统见 [DESIGN.md](DESIGN.md)。

> 设计与里程碑见 [`docs/PLAN.md`](docs/PLAN.md)，C 核心与 GUI 之间的 JSON 协议见 [`docs/PROTOCOL.md`](docs/PROTOCOL.md)。

## 功能与界面

左侧边栏 8 个功能页（无边框窗口 + 亚克力背景 + 统一 token 主题）：

| 页面 | 能力 |
| --- | --- |
| 连接 | 两条通道：**ADB**（`adb devices` 扫描）与 **SSH 直连**（填 IP/端口，用本机 ed25519 密钥连；首次连接自动固定主机密钥，之后拒绝换钥）。SSH 连上后设备/安装/插件/市场/文件/终端/设置全部走 SSH，不再需要 USB |
| 设备 | 13 条探针：型号/系统/PenMods 版本、存储、运行时间、SSH 状态、ADB/SSH 自启等，附原始 JSON |
| 安装 | v2.7+ 组件式安装（core/player/mathjax/ppocr，stage → 待启用 → 启用并重启 / 取消）；≤2.6 走 patchelf 注入；OTA 检查 |
| 插件 | 已装插件列表、启用/禁用（`.disabled`）、卸载（备份可回滚）、zip 路径在线安装 |
| 市场 | 协议 v1 静态索引：内置示例 / 本地 index.json / HTTPS 索引 / GitHub 仓库链接直装 |
| 文件 | 设备目录浏览、进入目录、单文件下载到本机 |
| 终端 | 远端命令原样执行（ADB/SSH 通用），4 个常用快捷命令 |
| 设置 | 运行环境信息、安全约定、`PenModsconfig.json` 的 ADB/SSH 自启与跳过鉴权开关（写 `.penmanager-bak` 备份后 `mv -f` 生效）、SSH 身份卡片（私钥路径、known_hosts 状态、忘记主机密钥、断开 SSH） |

全局：任意页面把 `.zip` 拖进窗口即跳到插件页并安装。

### 用 SSH 连接点读笔

笔上要跑着 sshd（PenMods 的 `ssh_autorun` 打开即可），并且本机公钥已经在笔的 `/root/.ssh/authorized_keys` 里。两条路：

1. **已经能用 USB 连**：连接页 → 选中设备 → 「部署公钥（ADB）」，程序会生成/复用 `数据目录/ssh/penmods_ed25519` 并把公钥追加到笔上。
2. **只有 Wi-Fi**：先把上面生成的 `penmods_ed25519.pub` 手动加到笔上（USB 或别的办法），然后在连接页「SSH」那一行填 IP 和端口点连接。

连接成功后：
- 左侧状态从「ADB 已连接」变成「SSH 已连接 root@192.168.1.100」，所有页面自动改走 SSH；
- `ssh.exe` 参数固定 `BatchMode=yes`（不会弹密码）、`StrictHostKeyChecking=accept-new`、`UserKnownHostsFile=<数据目录>/ssh/known_hosts`；
- 换了笔或重刷系统后如果提示主机密钥不匹配，到「设置 → SSH 身份 → 忘记主机密钥」清掉再连；
- 设置页可以随时「断开 SSH」回到 ADB。

外观为液态玻璃：浅色/深色两套主题、7 种强调色、4 种动态背板（极光/朝霞/深海/夜空）、「纯色」底、6 张内置照片背板（峡湾/晚霞峡谷/雪山/晨雾森林/海浪/水母，Unsplash 照片，随安装包分发）或自定义图片，均在「设置 → 外观」里即时生效并记住（`ui-settings.json`）。窗口为圆角（Windows 10 用 `SetWindowRgn` 自绘，Windows 11 走 DWM），按钮为无阴影的扁平样式。

界面截图见 `shots/g3-settings-light.png`（浅色 + 壁纸画廊）、`shots/g3-settings-dark.png`（深色 + 晨雾森林背板）、`shots/g4-photo-fjord.png`（峡湾背板 + 连接页）、`shots/g2-light-connect.png`（浅色 + 极光）、`shots/g-light-device-ssh.png`、`shots/dist-glass.png`（冻结包运行效果），更早的 Preline 平铺版见 `shots/p-*.png`（连接/设备/安装/插件/市场/文件/终端/设置各一页）；SSH 相关见 `shots/v3-connect.png`、`shots/v3-device-ssh.png`、`shots/v3-settings.png`，`shots/dist.png` 为打包后运行效果；旧版玻璃风格截图保留在 `shots/ui*.png`、`shots/page*.png` 以作对比。

## 排障：ADB 连不上

先看应用「连接」页顶部那行状态，它会直说问题：

| 顶部状态 | 含义 | 处理 |
| --- | --- | --- |
| `adb 未找到 · 无法扫描 USB 设备` | 程序找不到 `adb.exe` | 打包版应把 `adb.exe` 放在 `PenModsManager.exe` 同目录；开发版应放在 `.toolchain/platform-tools/`；也可以设 `PENCTL_ADB` 指向 adb.exe |
| `adb 1.0.41 · 未发现设备` | adb 正常，但没枚举到设备 | 换数据线/接口、在笔上确认已开启 ADB 调试，然后点「再扫描一次」 |
| `adb 服务异常` | adb server 起不来（临时目录不可写 / 5037 被占用 / 安全软件拦截） | 程序已把 adb 的 `TMP/TEMP` 指到 `数据目录/tmp`，仍失败时命令行跑 `adb kill-server` 再 `adb devices -l` 看真实报错 |

命令行自查（设备正常时应能看到一行 `... device ...`）：

```bash
adb devices -l
```

程序侧逻辑：`penctl.py` 会把解析到的 adb 路径通过 `PENCTL_ADB` 传给 C 核心，并把 adb 目录前置到子进程 PATH，所以一般不需要手动设环境变量。

### 首次启动免责声明

第一次打开（或 `data_dir()/disclaimer.json` 里的版本号低于当前 `DISCLAIMER_VERSION`，当前为 **2**）会弹出「使用须知 & 免责声明」：

- 顶部是红色风险提示卡：本工具会替换启动脚本、注入/替换动态库、改动系统分区，可能导致变砖、数据丢失、保修失效；
- 正文分四节：**一、免责条款** / **二、使用须知** / **三、知识产权声明** / **四、开源协议与反馈**（条款内容参考了社区同类工具的惯例写法，并按本工具的实际行为改写）；
- 遮罩层拦下所有点击，弹窗不处理完无法操作主界面；
- 正文在可滚动区域里，**必须滑到最底部**，底部「我已阅读并同意」才会启用（正文不足一屏时直接可用）；
- 点「我已阅读并同意」后写入 `disclaimer.json`（含版本号与时间），之后不再弹出；版本号提升会重新提示；点「退出」直接关闭程序。

开发自检参数：`--show-disclaimer`（强制显示）、`--skip-disclaimer`（强制跳过）、`--disclaimer-at-end`（打开时自动滚到底，用于截图验证按钮可用态）。

### 外观（液态玻璃）

- 主题：浅色 / 深色（`Theme.mode`），切换后整个应用即时重绘。
- 强调色：blue / teal / indigo / violet / rose / amber / emerald，按钮、导航高亮、开关随色变化。
- 背板是一个图块画廊：动态渐变（极光/朝霞/深海/夜空）与「纯色」、以及随包分发的 6 张照片（`app/penmanager/data/wallpapers/photo-{fjord,canyon,snow,forest,wave,jelly}.jpg`，1600×1000 JPEG，来源 picsum.photos 的 Unsplash 照片），点一张立刻生效并记住；「图片…」可选一张本地图片（自动模糊 + 压暗）。
- 持久化：写到数据目录下 `ui-settings.json`；截图/自检可用 `--ui-theme light|dark`、`--ui-accent <name>`、`--ui-wallpaper <id>` 临时覆盖（不落盘）。
- 实现：`app/penmanager/qml/Theme.qml`（QML 单例，所有页面只引用 `Theme.*`），壁纸层在 `Main.qml` 内用 `MultiEffect` 模糊色团/图片，面板用半透明玻璃色 + 内高光；照片壁纸自动跳过彩色色团，只做模糊 + scrim。
- 圆角窗口：`app/penmanager/winfx_region.py` 用 `CreateRoundRectRgn` + `SetWindowRgn` 裁剪整窗（Windows 10 没有 DWM 圆角），窗口尺寸变化时由 `app.py` 里的 300ms 定时器重设。
- 交互线程：所有设备/网络操作都在 `bridge.py` 的后台线程里跑，结果通过 `taskFinished(id, result)` 回到 QML，点按钮不会再冻结窗口。

## 结构

```
core/          C 核心 penctl.exe：连接/安装/包处理，只吐 JSON
app/           PySide6 桌面壳：QML 界面 + 薄 Python 桥
scripts/       构建与开发脚本
tests/         冒烟测试
docs/          PLAN / PROTOCOL
```

## 开发环境

- Python 3.13+/3.14（默认 `python`）。PySide6 装到工作区而不是系统 site-packages：
  `python .toolchain/fetch_pyside.py`（装进 `.toolchain/site`，`scripts/run_app.py` 会自动加入 `sys.path`）
- C 编译器：优先 `.toolchain/zig/zig.exe`（`python .toolchain/fetch_zig.py` 自动下载便携版），也可用任意 `zig cc` / MSVC / MinGW
- adb：放到 PATH、`PENCTL_ADB` 环境变量、或 `penctl.exe` 同目录

## 快速开始

```powershell
python .toolchain\fetch_zig.py        # 一次性：下载便携 zig
python scripts\build_core.py          # 编译 build\penctl.exe
python tests\smoke_core.py            # 核心 JSON 协议冒烟测试（无需真机）
python scripts\run_app.py             # 启动 GUI
python scripts\run_app.py --screenshot shots\v2-connect.png   # 渲染主界面截图
```

## 安全红线

1. 绝不原地覆盖设备上正在映射的 `.so`：写 `*.new` → 同目录 `mv -f` → 重启应用。
2. 重启前必须 `sync`。
3. 安装失败必须回滚；兼容 `.original_bak` 与 `.bak` 两种历史备份命名。
4. 不重分发 GPL 二进制；运行时从官方 Release 下载并用 SHA256SUMS 校验。


## 安全边界（v0.2 加固）

- 索引与下载只接受 `https://`（`localhost`/`127.0.0.1` 例外用于本地索引）；明文 http 直接 `BAD_URL`；
- SSH 首次连接固定主机密钥到 `<数据目录>/ssh/known_hosts`（`StrictHostKeyChecking=accept-new`），之后拒绝变更，不再 `UserKnownHostsFile=NUL`；
- 所有拼进设备 shell 的值都过 `safe.shq()` 单引号转义；远端 JSON 里的版本号/资产名不再直接当路径（校验 + `safe_filename`）；
- 下载有上限（插件 128 MiB、release 资产 2×声明大小、update 8 MiB 起）；zip 新增压缩比检查（>200× 且 >4 MiB 判 `ZIP_BOMB`）；
- 插件目录原子交换失败会自动把备份 `mv` 回去；patchelf 注入不再「先移走启动器」，任何一步失败启动器都还在；
- 安装插件/仓库包前必须勾选「以 root 运行、可能 bootloop」的风险确认；拖拽 zip 会弹确认框；示例索引（sha256 全 0）标记为不可安装；
- SSH 私钥（无口令）只落在 `%LOCALAPPDATA%\PenModsManager\ssh` 或 exe 同目录 `data`，不再回退到共享临时目录。

## PenMods v2.7+（update-system）与旧版差异

真机实测（YDP02X / 系统 2.1.2 / 已装 PenMods 2.7.0）用的是新一代 update-system：

- `/userdata/PenMods/libPenMods.so` 是指向 `/userdisk/PenMods/update-system/active/core/` 的符号链接；
- 组件安装走设备端 helper `/userdata/PenMods/penmods-update stage DESCRIPTOR ZIP`，只写 pending generation，**不碰运行中的库**；
- 桌面端因此分两条路径：v2.7+ 走 `penmods-update stage`（`app/penmanager/update_system.py`），≤2.6 才走 `patchelf` 注入（`app/penmanager/installer.py`）；
- 组件：`core`（本体，必装）、`player`（FFmpegPlayer）、`mathjax`（公式渲染）、`ppocr`（离线 OCR），descriptor 字段见 `docs/PLAN.md`；
- stage 成功后点「启用」由设备端在下次启动做 trial + 健康校验；未通过的 generation 会被自动回滚。stage 阶段随时可用 `cancel` 撤销。

### V2.7.3 启动器迁移（重要）

上游在 V2.7.3 修掉了 **V2.7.0 / V2.7.1 更新启动器的冷启动缺陷**（可能进不去系统、反复整机重启、被固件切回原厂）。只在更新中心升级 core、或只换两份 `.so`，**都修不好**独立启动器与启动脚本；装过 2.7.0/2.7.1 的笔必须跑一次 V2.7.3 的 `update_v2.7.3.zip` 完整迁移包。

管理器把这套流程做成了「安装」页顶部的红色横幅（`app/penmanager/migration.py`）：

1. 「下载并迁移」：从最新 release 取 `update_v*.zip` → 用 `SHA256SUMS` 校验 → push 到 `/userdisk/PenMods/install-<ver>/` → 设备端 `unzip -o` + `sh _do_update.sh`；
2. 「校验启动器」：`grep -c "PenMods guarded launcher v3" /usr/bin/runDictPen`，并读 `penmods-update status` 的 `launcher_ready`；
3. 「重启应用」：`adb shell 'sync; killall -TERM YoudaoDictPen'`——新版守护器有 16 秒冷却，**不要连续杀进程**。

迁移成功的判据：`penmods-update status` 显示 core 2.7.3、`launcher_ready:true`、`pending:null`、`trial:null`，且 `/usr/bin/runDictPen` 里出现 `PenMods guarded launcher v3`。

- 播放器 1.0.5 要求 `core ≥ 2.7.3`：依赖不满足时该行会显示「先升级本体」并禁用安装按钮。
- 组件行会比较「已装版本」与设备更新通道里的最新版本：已装高于通道版本时显示「已是最新 / 设备通道 X，无需更新」并禁用按钮，避免误降级；V2.7.3 这类不在更新通道里的版本请用上面的迁移横幅。
- 迁移出事时按官方教程恢复：<https://github.com/Lyrecoul/PenMods/blob/main/doc/RECOVERY_2.7.3.md>（issue #32）。
- MathJax、PP-OCRv5 自 V2.7.0 未变，继续用旧附件；不要从旧发布页下 core / 迁移包 / 启动器。

## 安装包与插件

- 「插件」页可填 zip 路径在线安装，也可以**直接把 zip 拖进窗口**（拖拽会跳到插件页并上传安装）；
- 插件包校验：zip-slip、符号链接、单文件/总量上限、`metadata.json` 必填 `id/name/version`；
- 设备侧先解压到 staging，再做「旧目录 → 备份、staging → 目标」的原子交换，失败可回滚。

## 测试

```powershell
python tests\smoke_core.py      # C 核心 JSON 协议（用内置 fake adb）
python tests	est_offline.py    # 纯 Python 数据层（网络、OTA、插件包、update_system）
```

## 打包（M6）

```powershell
python .toolchain\pip_patch.py install -q --target .toolchain\site `
    -i https://mirrors.aliyun.com/pypi/simple/ pyinstaller
python scripts\build_dist.py
dist\PenModsManager\PenModsManager.exe     # 双击即用，无需装 Python
```

产物是 onedir 绿色包（约 168 MB）：`PenModsManager.exe` + `_internal/`（PySide6/QML）+ 同目录 `penctl.exe`。
用户数据默认写 `%LOCALAPPDATA%\PenModsManager`，不可写时回退到「exe 同目录 data」。

> 打包时 PyInstaller 的隔离子进程需要匿名管道；如果当前终端被沙箱限制出现 `WinError 5`，用完整权限跑一次 `build_dist.py` 即可。

## 尚未完成

- 插件市场还没有公开索引：默认加载内置示例 `app/penmanager/data/example_index.json`，可填自有 `index.json`（https 或本地路径），或用「GitHub 仓库链接」直接从 release 安装；
- 真正「启用」已 stage 的组件需要重启设备（安装页已提供「启用并重启」，由设备端 helper 做 trial + 健康校验，失败自动回滚）；
- 暂无自动化 UI 测试（目前靠 `--screenshot` 逐页目检）；
- 设备配置的保存只覆盖 `serv` 段的三个开关，其余字段原样保留。
