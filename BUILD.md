# 从源码构建

需要 **Windows 10/11 x64** + **Python 3.10+**。整条链路不依赖 MSVC / CMake / Visual Studio。

## 目录约定

仓库里的 `.toolchain/` 是**本机工具链缓存**（已被 `.gitignore` 忽略），构建脚本会往里放：

| 路径 | 内容 | 由谁准备 |
| --- | --- | --- |
| `.toolchain/zig/zig.exe` | 便携 Zig（提供 `zig cc` 编译 C 核心） | `python src/tools/fetch_zig.py` |
| `.toolchain/platform-tools/adb.exe` | Android platform-tools | `python src/tools/fetch_adb.py` |
| `.toolchain/site/` | `pip install --target` 的 PySide6 / PyInstaller | `python src/tools/pip_patch.py install --target .toolchain/site PySide6-Essentials==6.12.0 pyinstaller` |

> `pip_patch.py` 是本项目的 pip 包装：它绕开“系统 site-packages 只读”的限制，把依赖装进仓库内目录，
> `run_app.py` 与 `build_dist.py` 会自动把 `.toolchain/site` 加进 `sys.path`。

## 1. 编译 C 核心（`penctl.exe`）

```powershell
python src/tools/fetch_zig.py
python src/scripts/build_core.py      # -> build/penctl.exe
```

`penctl` 是纯 C11、只链接 Win32 的 CLI，输出统一 JSON 信封（`core/src/README` 无，见 `docs/PROTOCOL.md`）。
建议设置：

```powershell
$env:ZIG_GLOBAL_CACHE_DIR = "$PWD\.toolchain\zig-cache"
$env:ZIG_LOCAL_CACHE_DIR  = "$PWD\.toolchain\zig-cache\local"
```

## 2. 运行开发版

```powershell
python src/scripts/run_app.py
```

常用自检参数：`--page N`、`--ui-theme light|dark`、`--ui-accent NAME`、`--ui-wallpaper ID`、
`--screenshot out.png`、`--screenshot-delay MS`、`--serial <sn>`、`--skip-disclaimer`。

## 3. 跑测试

```powershell
python src/tests/test_offline.py     # 纯函数/协议/安全助手，不需要设备
python src/tests/smoke_core.py       # 用 fake adb / fake ssh 跑 C 核心
```

## 4. 冻结打包

```powershell
python src/scripts/build_dist.py     # -> dist/PenModsManager/PenModsManager.exe（约 168 MB onedir）
```

打包前请先关掉正在运行的 `PenModsManager.exe`（Windows 会锁住 `qwindows.dll`）。
产物是 **onedir** 结构，分发时整目录一起给，或压成 zip 作为 GitHub Release 附件。

## 已知环境坑

- 本机禁用了匿名管道：程序内部一律用临时文件重定向，而不是 `CreatePipe`。
- 子进程必须用 `DETACHED_PROCESS`，否则在某些沙箱里会以 `0xC0000142` 退出。
- PyInstaller 需要在可写的 `TMP/TEMP` 下运行，否则隔离子进程起不来。
- adb server 的 `adb.log` 若落到不可写的临时目录会启动失败；管理器会把 adb 的 `TMP/TEMP` 指到数据目录下的 `tmp`。
