# PenMods 管理器 · 设计方案（v0.1）

Windows 桌面工具，用于管理「已支持 PenMods 的有道词典笔」。UI 为**液态玻璃**风格，左侧功能侧边栏，右侧内容区。
技术栈按你的选择：**Python(PySide6 + Qt Quick/QML) GUI + C 核心 CLI（`penctl.exe`）**，两者用 JSON 协议解耦。
QML 是 Qt 原生 GPU 渲染，**不是网页、不启动本地 HTTP 服务**。

---

## 1. 需求 → 落点

| 你提出的功能 | 实现位置 | 里程碑 |
|---|---|---|
| ADB / SSH 两种连接，设备信息 | 连接页 + 设备页；`penctl detect / device-info`，SSH 传输层 | M1 |
| 给支持的型号安装 PenMods；本体必装、可选组件勾选 | 安装页；`penctl install-penmods` 事务 | M2 |
| OTA 更新（点读笔内外一致） | 安装页「更新」；读 jsDelivr manifest + 校验 | M2 |
| 安装包 / 插件安装（zip 拖拽） | 插件页；`penctl pkg inspect/install`，原子目录交换 | M3 |
| 插件市场（GitHub 索引 / 仓库链接） | 市场页；市场协议 v1 + 仓库直装 | M4 |
| 文件管理 / 终端 / 配置编辑 | 对应三个页面；ADB、SFTP、pty | M5 |

## 2. 架构

```
┌─────────────────────────┐      JSON（stdout/一键一 JSON）      ┌──────────────────────┐
│ PySide6 GUI (QML 液态玻璃) │ ─────────────────────────────────▶ │ penctl.exe (C, 无依赖) │
│ 侧边栏导航 · 页面 · 状态     │ ◀───────────────────────────────── │ 设备事务 / 包 / ELF    │
└─────────────────────────┘                                     └──────────┬───────────┘
   网络：市场索引 / Release 下载 / SHA256 校验（Python）                      │ 进程 + stdio
                                                        ┌───────────────────┴───────────────┐
                                                        │ adb.exe（随包/环境）               │
                                                        │ ssh（libssh2，后续里程碑）          │
                                                        └───────────────────┬───────────────┘
                                                                    有道词典笔 (aarch64)
```

为什么这样切：
- **C 核心**：进程/超时/管道、zip 解包校验、ELF `.so` 依赖处理、sha256，全部稳定可测、可被脚本复用，GUI 崩溃不影响设备操作。
- **Python GUI**：界面、网络、业务编排迭代快；QML 才做得出真正的分层透明/模糊/动效。
- 协议单向、无共享内存：`penctl ... --json` 每个命令恰好输出一个 JSON 对象，进度用行分隔事件。

## 3. 目录结构

```
D:\penmods\
├─ core\                 C 核心（zig cc 编译，产物 build\penctl.exe）
│  ├─ src\util.c         字符串缓冲 / UTF-16↔UTF-8 / 子进程（超时、临时文件捕获）
│  ├─ src\adb.c          adb 定位、shell/push/pull、鉴权探测
│  ├─ src\commands.c     detect / device-info / install / pkg ...
│  └─ src\main.c         命令行入口
├─ app\                  Python 应用（pip install -e .）
│  └─ penmanager\  app.py bridge.py penctl.py winfx.py qml\...
├─ scripts\build_core.py 用 zig cc 编译 core
├─ docs\PLAN.md  PROTOCOL.md
├─ tests\                离线单测（假 adb 脚本驱动）
└─ .toolchain\           便携 zig / 临时工具（不进 git）
```

## 4. penctl 协议（详见 docs/PROTOCOL.md）

```
penctl --version
penctl --json detect                        # adb 路径/版本、设备列表、是否需要 auth
penctl --json device-info [-s SERIAL]       # /Version、pcba、系统版本、PenMods 状态、ssh/adb 服务
penctl --json install-penmods [-s S] [--version V] [--components a,b] [--pkg ZIP] [--dry-run]
penctl --json update-penmods  [-s S] [--version V] [--check-only]
penctl --json pkg inspect ZIP | pkg install ZIP [-s S]
penctl --json plugin list|enable|disable|remove [-s S] ID
penctl --json file ls|push|pull|rm  ...
penctl --json recover [-s S]                # 救砖：清插件、恢复 known_good、修 misc
```

错误统一 `{"ok":false,"error":{"code":"...","message":"..."}}`；码表：`ADB_MISSING`、`NO_DEVICE`、`MULTI_DEVICE`、`AUTH_REQUIRED`、`UNSUPPORTED_MODEL`、`CHECKSUM_MISMATCH`、`REMOTE_IO`、`TIMEOUT`。

## 5. 安装事务（最关键、最危险的部分）

设备红线：**绝不能原地覆盖正在被映射的 .so / 可执行文件**（会让页表失效 → 段错误 → 守护重启 → 固件进 `misc` boot-recovery）。
所有替换一律「写 `.new`/`.tmp` → 同目录 `mv -f` 原子改名」。

状态机（每步失败可回滚，全程日志落 `%LOCALAPPDATA%\penmods-manager\logs\`）：

1. **preflight**：adb 可用 → 单设备 → auth（`CherryYoudao`）→ `cat /Version`、`get_pcba_version` 判定型号/系统是否在支持矩阵；已装则提示走「更新」。
2. **stage**：按所选版本从 GitHub Releases 取 `libPenMods.so`（+可选 `libPenModsResources.so`），对 `SHA256SUMS` 校验；校验失败直接中止。
3. **remount**：`touch /test_write_permission` 探针，失败才 `mount -o remount,rw /`。
4. **push**：`/userdata/PenMods/` 建目录 → push 主库、资源库、`misc/patchelf`（aarch64 静态，musl 构建，不依赖设备 glibc）、`patch.sh`、备份原程序。
5. **patch**：设备侧 `patchelf --add-needed /userdata/PenMods/libPenMods.so` 作用于副本 → `mv` 原子替换，原程序留存 `YoudaoDictPen.original_bak`（兼容旧名 `.bak` 回滚）。不依赖我们重写 ELF。
6. **components**（可选，勾选才装）：
   - `ffmpegplayer-plugin.zip` → 解压到 `/userdata/PenMods/qml/`（布局 `FFmpegPlayer/{*.so,qmldir}`）
   - `mathjax-server.zip` → 落点以 `AGENTS.md`/真机为准（待确认项）
   - `penmods-ppocr.sh` → push 后 `sh penmods-ppocr.sh install`
7. **verify**：`patchelf --print-needed` 含 libPenMods.so、文件存在、`LD_LIBRARY_PATH=/oem/YoudaoDictPen/output/aarch64_libs` 启动主程序 10s 不崩。
8. **commit**：`sync; sleep 2; sync; reboot`；重连后 postcheck（进程在、日志无 panic、PenMods 菜单可见）。
9. **rollback**：还原 `YoudaoDictPen.original_bak` → 删 `/userdata/PenMods` → `rm -f /usr/bin/patchelf` → reboot。

风险控制：整个流程「写前备份、写后校验、失败回滚」，并在安装前用对话框列出将执行的全部命令（可导出日志）。

## 6. OTA 更新
读 `https://cdn.jsdelivr.net/gh/lyrecoul/penmods-ota@main/updates.json`（可配镜像），按当前版本选升级路径，校验 zip 的 md5/size，
**由我们解包并 `.tmp.so + mv` 部署**（不执行设备端 `_do_update.sh`，避免不可控脚本）；可选组件按版本差异提示重装。

## 7. 插件与安装包
- 包校验：条目数/单文件体积上限、zip-slip、符号链接、`metadata.json` 必填字段与 id 合法性。
- 安装：解压到 `/userdisk/PenMods/.penctl-staging/<uuid>` → 原子目录交换 → 备份到 `.penctl-backups/<ts>` → 失败反向回滚。
- 支持：单插件、多插件归档（`roots` 选择）、纯目录、`.disabled` 启停、`.loading` 崩溃标记保护（删除需二次确认）。

## 8. 插件市场
- 协议 v1（兼容 PenManager）：`index.json` 静态清单，每个版本必须带 64 位 hex `sha256`。
- 默认索引指向我们自建的 `penmods-registry` 仓（GitHub Pages / raw 均可），用户可改 URL、可粘贴**任意 GitHub 仓库链接**直装（解析 owner/repo → Latest Release 资产）。
- 下载缓存 + 命中校验；离线时回退本地缓存。不打包任何第三方二进制，运行时下载。

## 9. UI：液态玻璃 + 侧边栏

- 窗口：无边框、18px 圆角、暗色亚克力底（Win11 `DWMWA_SYSTEMBACKDROP_TYPE=acrylic`，Win10 `ACCENT_ENABLE_ACRYLICBLURBEHIND` 兜底），失败时纯半透明渐变兜底，不影响功能。
- **侧边栏（212px）**：玻璃面板 = 8% 白 + 1px 高光描边 + 顶部高光渐变；每个功能一项（图标 + 文本），选中项为药丸高亮 + 柔光；底部设备状态（未连接/已连接 + 型号）。
- 内容区：玻璃卡片（12px 圆角、分层透明、hover 高光），卡片头 = 标题 + 右侧操作按钮。
- 背景：深蓝黑渐变 + 2~3 个模糊柔光椭圆，营造"液态"纵深。
- 动效：120–180ms ease-out；页面切换淡入 + 8px 位移。
- 字体：Segoe UI Variable Text / 微软雅黑；图标先 Unicode 后换 SVG。
- 无边框拖动/缩放：`startSystemMove()` / `startSystemResize()`，8px 边缘热区。

## 10. 里程碑

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M0 骨架 | 目录、C 核心 `--version`/`detect`、GUI 空壳（液态玻璃侧边栏 + 8 页占位）、协议文档 | `penctl --json detect` 输出合法 JSON；GUI 可启动并截图 |
| M1 连接/设备 | ADB 检测+鉴权、SSH 配置、服务启停/自启/改密码、设备信息面板 | 真机插拔后信息正确刷新 |
| M2 安装/更新 | 安装向导（组件勾选）、OTA、回滚、日志 | 真机全新安装成功；拔线中断可回滚 |
| M3 包/插件 | 拖拽 zip、校验、原子安装、启停卸载、备份 | 装官方插件包 + 自制包均成功 |
| M4 市场 | 索引浏览/搜索/安装、仓库链接直装、缓存 | 无网缓存安装成功 |
| M5 文件/终端/配置 | 文件浏览传输、终端、配置 JSON 编辑备份 | 截图/传输/编辑回读一致 |
| M6 打包 | PyInstaller onedir（内嵌 adb.exe/penctl.exe）、图标、安装包、日志与救援页 | 干净 Windows 机器直接运行 |

## 11. 待确认 / 风险
1. **真机信息**：型号（YDP02x/YDPG3/YDP03x）、系统版本、是否已装 PenMods —— 决定 M2 实测路径。
2. **patchelf aarch64 静态二进制**：用 zig 交叉编译 musl 静态版本；若失败，退化为「主机侧 patchelf 改 ELF → push 副本 → mv」。
3. **mathjax-server 设备端落点**：文档只写了打包来源，未写安装位置，需真机 `find` 确认。
4. **ADB 鉴权**：`adb shell auth` + 密码 `CherryYoudao` 的喂入方式（stdin vs `cmd /c echo|`）需实测。
5. **许可**：工具自身开源（MIT）；不重分发 PenMods 二进制，安装时从官方 Release 下载并校验。
