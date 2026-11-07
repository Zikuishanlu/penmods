# 插件包与市场索引

`plugins/` 放 8 个可直接安装的插件包（`shell_plugin.zip` 按发布决定排除）（`.zip`）、`SHA256SUMS`，以及市场索引 `index.json`（已随仓库提供，换包后重新生成）。

## 结构与校验

- 每个 zip 的包根（或唯一一级目录）里必须有 `metadata.json`，字段 `id / name / version / author / description` 齐全。
- 安装器会拒绝符号链接、路径穿越、超限文件；声明了 `main_so` 却没有 `.so` 会报 `MISSING_SO`。
- 每个包的 sha256 见 `SHA256SUMS`，逐包细节见 `SECURITY-AUDIT.md`（第三方静态审计，不构成安全保证）。

## 生成市场索引

索引里的下载地址必须是**绝对 HTTPS URL**，所以先给这些包一个公开位置（GitHub 仓库 raw 地址、CDN、对象存储都可以），再生成：

```powershell
# 在仓库根目录执行；--base-url 指向 plugins/ 的公开前缀（不要带结尾斜杠）
python src/scripts/make_market_index.py --base-url https://raw.githubusercontent.com/<owner>/<repo>/main/plugins
```

产物：

- `plugins/index.json`：协议 v1，`schema_version: 1`，每个插件含 `versions[].url`、`sha256`、`devices`、`min_penmods`、`native`；
- `plugins/SHA256SUMS`：`sha256sum` 格式，随包分发。

管理器内置的默认索引地址（`app/penmanager/market.py` 的 `DEFAULT_INDEX_URL`）已指向本仓库；
如果你把仓库放在别处，改这个常量与下面的地址即可：

```
https://raw.githubusercontent.com/<owner>/<repo>/main/plugins/index.json
```

> 生成脚本会重新计算每个包的 sha256；**替换包之后必须重新生成**，否则安装会因校验失败被拒绝。

## 已知限制

- 8 个包都没有声明依赖（`requires` / `dependencies` / `min_penmods` 全缺），索引里统一填 `min_penmods: 2.0.0`。
- `fanqie_plugin` 走明文 HTTP、`bili_plugin` 拉起本地无鉴权服务——风险说明见审计报告，市场条目的 `summary` 保留作者原文，未做风险标注。
- `shell_plugin.zip` 是 root 终端，**不在本仓库发布**（仍在本地 `plugin/` 里，需要时用「插件 → 本地 zip」侧载）。
- 旧包 `chajian_fixed.zip`（5 个 zip 的整合包，没有 `metadata.json`）**不是插件包**，不收录。
