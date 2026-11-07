# penctl 协议（v0.1）

`penctl.exe` 是所有设备操作的唯一执行者；GUI 只负责拼参数、展示 JSON。
约定：一行 JSON 写到 stdout（UTF-8、无 BOM），诊断信息写 stderr。

## 调用形式

```
penctl [--json] [-s SERIAL] <command> [args...]
penctl --version
penctl --help
```

- `--json`：GUI 始终传它；不带时为人类可读模式（M1 起补）。
- `-s SERIAL`：只对单台设备执行；多设备且未指定时应返回 `MULTI_DEVICE`。
- 退出码：`0` 成功；`1` 业务失败（JSON 里 `ok=false`）；`2` 用法错误。

## 成功信封

```json
{
  "ok": true,
  "cmd": "detect",
  "version": "0.1.0",
  ... 命令载荷
}
```

## 失败信封

```json
{
  "ok": false,
  "cmd": "detect",
  "error": { "code": "ADB_MISSING", "message": "adb not found ..." }
}
```

| code | 含义 |
| --- | --- |
| `BAD_ARG` | 参数缺失或非法 |
| `UNKNOWN_COMMAND` | 未知子命令 |
| `ADB_MISSING` | 找不到 adb（`PENCTL_ADB` → exe 同目录 → PATH） |
| `ADB_FAILED` | adb 进程启动失败或非零退出 |
| `TIMEOUT` | 设备操作超时 |
| `NO_DEVICE` | 需要设备但未发现（或未用 `-s` 指定） |
| `MULTI_DEVICE` | 多台在线且未 `-s` 指定 |
| `DEVICE_OFFLINE` | 设备处于 offline / unauthorized / recovery |
| `AUTH_REQUIRED` | 需要执行 `adb shell auth`（密码 CherryYoudao） |
| `NOT_IMPLEMENTED` | 里程碑未落地的命令 |
| `INTERNAL` | 兜底 |

## 命令

### `version`

```json
{"ok": true, "cmd": "version", "version": "0.1.0", "platform": "windows"}
```

`--version` 走同一实现。

### `detect`

扫描 ADB 设备并报告每台设备能否执行 shell：

```json
{
  "ok": true, "cmd": "detect", "version": "0.1.0",
  "adb": { "path": "C:\\...\\adb.exe", "version": "Android Debug Bridge version 1.0.41" },
  "devices": [
    { "serial": "abcd1234", "state": "device", "model": "YDP02X",
      "shell": "ok", "auth_hint": false, "penctl_ok": true }
  ]
}
```

- `shell`：`ok` / `auth_required` / `unavailable` / `error`。
- `auth_required`：shell 回声里出现 `adb shell auth` 提示（设备端鉴权未过）。
- `penctl_ok`：`echo penctl-ok` 往返成功，说明可以下发命令。

多台在线且未 `-s` 时 `detect` 仍列出全部设备（不报 `MULTI_DEVICE`）；`--serial/ -s` 只约束后续命令。

### `device-info -s SERIAL`

返回设备探针聚合（型号、系统版本、PenMods 安装状态、存储、运行状态）。字段随 M1 稳定；
当前返回 `{"ok":true,"cmd":"device-info","info":{...}}`，键缺失表示探针失败。

`derived` 由 `info` 推导（GUI 直接用它做属性行）：

```json
{"ok": true, "cmd": "device-info", "serial": "R58MFAKEDEV",
 "info": { "version_raw": "...", "pcba": "YDP02X", "..." : "..." },
 "derived": { "model": "YDP02X", "model_supported": true,
              "system_version": "2.0.8", "penmods_installed": true }}
```

`model_supported`：`YDP02X` / `YDPG3` / `YDP03X` 为 true；空 model 为 false。

### `shell <command...>`

终端页用的原样透传：`penctl -s SERIAL shell ls /userdata` 把 adb 的 stdout 原样输出（不包 JSON），退出码 0/1。
未给 `-s` → `NO_DEVICE`；无命令 → `BAD_ARG`。

### `pkg-inspect <zip>`

M3：校验插件/安装包结构（zip-slip、大小、metadata.json），输出归一化清单。M0 起返回 `NOT_IMPLEMENTED`（退出码 1）。

## 安全红线（对实现的约束）

1. 绝不原地覆盖设备上正在映射的 `.so`：先写 `*.new`/`*.tmp`，再同目录 `mv -f`。
2. 任何会重启应用/设备的操作都要显式 `sync`。
3. 安装事务失败必须回滚到备份（`.original_bak` 与 `.bak` 两种历史命名都要认）。
4. 下载产物必须校验官方 `SHA256SUMS`（OTA zip 用 releases.json 的 md5）。
