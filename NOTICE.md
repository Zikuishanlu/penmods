# 第三方组件与许可

本仓库自身代码以 MIT 发布（见 [LICENSE](LICENSE)）。以下内容来自第三方，随发布物一起分发时需要保留其许可信息。

| 组件 | 位置 | 许可 / 来源 | 说明 |
| --- | --- | --- | --- |
| Qt for Python（PySide6-Essentials 6.12.0） | 运行时依赖，不随源码分发；冻结包内嵌 | LGPL-3.0 / Qt 商业许可 | 冻结包以动态库形式携带 Qt，符合 LGPL 的动态链接要求；如需再分发请保留 Qt 许可文本 |
| Android platform-tools（`adb.exe`、`AdbWinApi.dll`、`AdbWinUsbApi.dll`） | 随冻结包分发 | Apache-2.0（Android SDK） | 来自 <https://dl.google.com/android/repository/platform-tools-latest-windows.zip> |
| 内置照片背板（峡湾 / 晚霞峡谷 / 雪山 / 晨雾森林 / 海浪 / 水母） | `src/app/penmanager/data/wallpapers/` | [Unsplash License](https://unsplash.com/license)（经 picsum.photos 获取） | 允许免费使用与再分发，不要求署名；此处仍标注来源 |
| 插件包（`plugins/*.zip`） | `plugins/` | 各插件作者自定（未随包声明） | 这是第三方作品，不是本项目的代码；作者字段以各包 `metadata.json` 为准。安装前请阅读 [plugins/SECURITY-AUDIT.md](plugins/SECURITY-AUDIT.md) |
| PenMods（上游设备端项目） | 不包含在本仓库 | GPL-3.0 | 本管理器只是调用设备上的 `penmods-update` / `libPenMods.so`，不链接其代码 |

## 资料来源

- PenMods 上游：<https://github.com/Lyrecoul/PenMods>（设备端运行时、发布说明与恢复教程）
- 插件市场协议 v1 的字段约定沿用 PenManager 的 `docs/plugin-market-v1.md`
