# 变更记录

## 0.1.0 — 首个可发布版本

**连接**

- ADB（`adb devices` 扫描 + `penctl` C 核心）与 SSH（ed25519 密钥、`accept-new` 首次固定主机密钥、known_hosts 随数据目录保存）双通道。
- 修掉 adb 冷启动失败：把解析到的 adb 路径经 `PENCTL_ADB` 传给子进程，并把 adb 的 `TMP/TEMP` 指向可写目录。

**安装与更新**

- v2.7+ 组件式安装：core / player / mathjax / ppocr，`stage → 待启用 → 启用并重启`，可取消；≤2.6 走 patchelf 注入。
- 组件依赖校验（`requires.min` / `max_exclusive`）：不满足时行内提示「先升级本体」并禁用按钮。
- 设备通道版本低于已装版本时显示「已是最新 / 设备通道 X，无需更新」，避免误降级。
- **PenMods V2.7.3 启动器迁移**：探测 `/usr/bin/runDictPen` 是否带 `PenMods guarded launcher v3` + `penmods-update status` 的 `launcher_ready`，提供完整迁移包下载（SHA256 校验）、执行、重启应用与校验入口。

**插件与市场**

- 插件 zip 安装：拒绝符号链接与路径穿越、校验 `metadata.json` 必填字段与 `id`、检测 `.so` 与 `main_so` 一致性。
- 市场协议 v1：HTTPS 索引、SHA256 强校验、本地 index.json、GitHub 仓库链接直装。
- 附带 9 个插件包、`SHA256SUMS` 与第三方静态审计报告。

**界面**

- PySide6 + QML 液态玻璃：浅/深色主题、7 种强调色、4 种动态背板 + 6 张照片背板 + 自定义图片、扁平按钮、圆角窗口（Win10 `SetWindowRgn`，Win11 DWM）。
- 全部设备/网络操作走后台线程（`taskFinished` 信号），点按钮不再卡界面。
- 首次启动「使用须知 & 免责声明」，滑到底才能同意。

**安全**

- 下载强制 HTTPS、大小上限、zip 压缩炸弹与路径穿越防护、SSH 主机密钥固定、写设备先 `*.tmp` 再 `mv -f`。
