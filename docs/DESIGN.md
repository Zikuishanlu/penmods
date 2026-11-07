# DESIGN.md — PenMods 管理器

> 设计系统文档。改界面先改这里，再改 `app/penmanager/qml/theme.js`，最后才动页面。
> 参照 [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) 的做法：一份可执行的 DESIGN.md 比一堆截图更耐用；反 slop 规则来自 [impeccable](https://github.com/pbakaus/impeccable)。

## 1. 这是什么

Windows 上的桌面工具，管理一台插着 USB 或连着 Wi-Fi 的有道点读笔：装 PenMods、更新组件、装插件、翻文件、开终端。

使用者是同一类人：愿意为了多几个功能去折腾设备、看得懂 shell、但不想每次都手打命令。界面要让他们**一眼确认设备状态**，并且**在危险操作前知道自己在做什么**。

## 2. 设计立场

三条，按优先级：

1. **仪器感，不是展示页。** 这是一个控制面板，不是产品落地页。信息密度优先、装饰次要。数字用等宽字，状态用颜色，动效只在解释状态变化时出现。
2. **诚实材质。** 桌面窗口就该像桌面窗口：实心面板、1px 分隔线、无模糊玻璃叠层、无渐变光斑。半透明只用在真正的层级关系上（浮层、选中态），不用来制造"高级感"。
3. **一个强调色。** 全站只有一种强调色（珊瑚橙 `#E8654C`），它只代表"可以点"和"当前选中"。状态色（成功/警告/危险）是另外一套语义色，不做装饰。

## 3. 反 slop 清单（来自 impeccable，逐条对照过）

现有界面曾经踩过的坑，别再踩回去：

| 不要 | 原因 | 现在怎么做 |
| --- | --- | --- |
| 紫→蓝渐变背景 + 模糊光斑 | AI 生成界面的第一特征，与工具无关 | 纯色 `#0B0E13` + 一处 accent 用于"主按钮/选中"，其余交给留白 |
| 玻璃拟态卡片套卡片 | 层级靠模糊表达，信息密度一高就糊 | 实心 `surface` + 1px `hairline`；嵌套只允许一层 |
| 每个标题左上一个圆角方块图标 | 装饰性图标不承载信息 | 图标只出现在导航栏与空状态，且必须表达"这是什么功能" |
| Inter 一把梭 | 默认感 | Display 用 Segoe UI Variable Display / Text 用 Segoe UI Variable Text / 代码用 Cascadia Mono |
| 彩色底 + 灰字 | 对比度不足 | 强调色底上只用 `textOnAccent`（近黑） |
| 大段 JSON 直接铺满页面 | 调试信息不是主信息 | 原始输出默认折叠，需要时展开 |
| 满屏胶囊按钮 | 层级消失 | 主操作最多一个实心按钮，其余描边或纯文字 |

## 4. Token（唯一来源：`app/penmanager/qml/theme.js`）

色板：

| token | 值 | 用在哪 |
| --- | --- | --- |
| `bg` | `#0B0E13` | 窗口底 |
| `bgDeep` | `#080A0E` | 标题栏、侧栏底 |
| `surface` | `#12161D` | 内容卡片 |
| `surfaceRaised` | `#161B23` | toast、浮层 |
| `panel` | `#0FFFFFFF` | 输入框、代码块 |
| `panelHover` | `#14FFFFFF` | 列表 hover、空状态容器 |
| `panelActive` | `#1FFFFFFF` | 选中行、chip |
| `hairline` | `#12FFFFFF` | 分隔线、卡片内衬 |
| `hairlineStrong` | `#1FFFFFFF` | 卡片描边、强分隔 |
| `outline` | `#2A3542` | 控件描边 |
| `text` | `#E9EEF5` | 主文本 |
| `textSecondary` | `#98A4B3` | 说明 |
| `textDim` | `#69737F` | 元信息、标签 |
| `textOnAccent` | `#14171D` | 主按钮文字 |
| `accent` | `#E8654C` | 主按钮、选中 |
| `accentHover` | `#F07A62` | hover |
| `accentPressed` | `#D2553D` | 按下 |
| `accentSoft` | `#33E8654C` | 图标底、弱提示 |
| `ok` | `#48C9A0` | 运行中、受支持 |
| `warn` | `#E9B44C` | 未安装、待启用 |
| `danger` | `#E4666B` | 失败、危险操作 |
| `info` | `#6FA8FF` | 下载、外部链接来源 |

字体：

| token | 值 |
| --- | --- |
| `fontDisplay` | `Segoe UI Variable Display` |
| `fontText` | `Segoe UI Variable Text` |
| `fontMono` | `Cascadia Mono` |

字号（QML `font.pixelSize` 只收整数）：

| token | px | 用途 |
| --- | --- | --- |
| `sizeDisplay` | 21 | 页面标题 |
| `sizeTitle` | 15 | 区块标题 |
| `sizeBody` | 13 | 正文 |
| `sizeSmall` | 12 | 说明、列表副行 |
| `sizeMeta` | 11 | 标签、时间戳、元信息 |
| `sizeMono` | 11 | 序列号、路径、JSON |

间距（4 的倍数）：`4 / 8 / 12 / 16 / 24 / 32`。只有这三处偏离：标题栏高 48、侧栏宽 212、控件高 34。

圆角：窗口 16（Windows 11 下由 DWM 处理，QML 侧仍按 16 画）、面板 14、控件 9、胶囊 999。

## 5. 布局

```
┌─────────────────────────────────────────────────────┐
│ 标题栏 48  [品牌] [名称] │ [当前页]        [− □ ×]  │
├──────────┬──────────────────────────────────────────┤
│ 侧栏 212 │ 内容区（padding 14）                     │
│ 工作区   │  ┌─ GlassCard ────────────────────────┐  │
│ · 连接   │  │ 标题 21 + 状态副行        [动作]   │  │
│ · 设备   │  │ ─────────────────────────────────  │  │
│ · 安装   │  │ 内容                               │  │
│ · 插件   │  └────────────────────────────────────┘  │
│ · 市场   │                                          │
│ · 文件   │                                          │
│ · 终端   │                                          │
│ · 设置   │                                          │
│ ──────── │                                          │
│ 连接状态 │                                          │
└──────────┴──────────────────────────────────────────┘
```

- 一个窗口只有一个主卡片（内容区填满），页面内部再用区块分隔，不做多层卡片嵌套。
- 导航项高 38，选中态 = `panelActive` 底 + 左侧 2×16 accent 竖条 + 图标转 accent。
- 页面头部统一：标题 21 DemiBold + 一行状态（`textDim` 12）+ 右侧至多一个主按钮。

## 6. 组件

| 组件 | 规则 |
| --- | --- |
| `GlassCard` | 实心 `surface`、1px `hairline` 描边、顶部 1px 内衬线；`padding: 18` |
| `GlassButton` | 主按钮 = accent 填充 + `textOnAccent` 文字；次按钮 = 透明 + `hairline` 描边 + `textSecondary`；禁用 = `#08FFFFFF` 底 + `textDim` 文字，不用暗红 |
| `GlassTextField` | `panelHover` 底、`hairline` 边；聚焦时 1px accent 边 |
| `InfoTile` | 88 高；label 11 DemiBold + 0.4 字距；value 20 Display；hint 11 dim |
| chip | 26 高胶囊，`panelActive` 底；`键 值` 两段，值用语义色 |
| 开关 | 44×24 轨道，选中 accent，圆点 16 |
| toast | 底部居中 36 高 `surfaceRaised`，2.4s 自动消失 |

## 7. 文案语气

- 说人话，说后果。不写"操作成功"，写"已重启，PenMods 2.7.0 生效"。
- 危险操作必须写清楚代价：「插件以 root 身份运行，来源不明可能让笔无法启动（bootloop）」。
- 空状态给下一步，不给解释：「还没有选择设备 → 去连接」。
- 英文只用于专有名词（ADB、SSH、PenMods、YDP02X）与单位。

## 8. 动效

- 只用于状态解释：面板切换 120ms、toast 160ms 淡入、按钮 hover 90ms。
- 不做背景视差、不做模糊光斑漂移、不做滚动视差。
- 窗口拖拽时外框变 `alpha(accent, 0.55)`，松手即恢复——这是唯一的"环境反馈"。

## 9. 无障碍与操作

- 正文对比度 ≥ 7:1（`text` on `bg` 约 13:1），说明文字 ≥ 4.5:1。
- 所有可点区域至少 28×28；主按钮 34 高。
- 键盘：`Esc` 关闭确认层，`Enter` 提交当前输入。
- 破坏性操作（卸载插件、回滚、写入配置）都要二次确认。

## 10. 改界面时的工作流

1. 改 `theme.js` 的 token —— 不要在任何页面里写新的十六进制颜色。
2. 改 `DESIGN.md` 对应小节（如果规则变了）。
3. 改组件，再改页面。
4. `python scripts/run_app.py --page N --screenshot shots/v2-N.png` 截图自检，确认没有回退成玻璃/渐变。


---

## 长页面滚动（设置/安装等）

- 卡片内容超过可视高度时，用 `Flickable` 包一层 `ColumnLayout`：`contentWidth: width`、`contentHeight: settingsColumn.implicitHeight`、`ColumnLayout.width: flick.width - 10`。
- `ScrollBar.vertical` 必须显式给可见样式（6px 宽、`Theme.hairlineStrong`），`policy` 在溢出时用 `AlwaysOn`——默认 Basic 样式在浅色玻璃上几乎看不见，用户会以为页面被截断。
- 不要给列表行里的文本写死 `Layout.preferredWidth`（如 620/460）：RowLayout 会被撑得比卡片宽，右侧按钮被裁掉、点不到。改为 `Layout.fillWidth: true` + `elide`。

## 危险操作横幅与依赖阻断（安装页）

- **风险提示用横幅，不用弹窗**：启动器迁移这类「影响开机」的操作，在安装页顶部放一条 `Theme.dangerSoft` 底的横幅，列出触发原因（`probe.reasons`）和后果，再给动作按钮；点一次就写设备，所以文案必须写清「会重启应用」「不要连续杀进程」。
- **依赖不满足就禁用，并说明原因**：组件行显示 `blocked_reason`（橙色）与文案「先升级本体」，按钮 `enabled` 排除 blocked；不要只把按钮变灰而不解释。
- **状态要可复核**：横幅同时提供「校验启动器」和「重启应用」，让用户能自己确认 `launcher_ready` 与 `runDictPen` 标记，而不是只相信一次成功提示。

## 弹窗（modal）

- **不透明底**：弹窗卡用 `Theme.dialog`（浅 `#FFFFFF` / 深 `#141A24`），不要用玻璃 `Theme.surface`——半透明会让底下的页面透出来，正文发灰、对比度掉到不可读。
- **遮罩**：`#D90A0E15` 全屏矩形 + 填充整个遮罩的 `MouseArea`，先吞掉点击再放内容，避免误触背后界面。
- **结构**：风险提示用 `Theme.dangerSoft` 底 + `Theme.danger` 字的 callout（圆角 `Theme.radiusControl`，内边距 12）；条款分节，每节一个 DemiBold 小节标题 + 圆点条目列表，条目之间 5px 间距，跨节 16px。
- **必须读完才可确认**：需要「阅读并同意」的弹窗（滚动区用 `Column` + `Repeater` 渲染分节内容，`contentHeight` 绑定 Column 高度），正文放在 `Flickable` 里，`atYEnd` 为真（或内容不足一屏）才启用主按钮；提示文案随状态变（未读橙 `Theme.warn` / 已读绿 `Theme.ok`）。
- **尺寸**：`width: min(parent.width - 160, 580)`、`height: min(parent.height - 110, 492)`，圆角 `Theme.radiusPanel`，1px `Theme.hairlineStrong` 边框，内边距 24。
- **按钮**：「取消/退出」在左，主动作在右；禁用时文案要说明为什么不可用（例：`请先读到末尾`）。

## 液态玻璃主题（v0.3，当前生效）

早期 Preline 平铺主题已被替换为「液态玻璃」：同一套版式骨架，但材质是半透明玻璃叠在动态背板上。

### 材质层次（从下到上）

1. **背板壁纸**（`Main.qml` 的 `wallpaper`）：基础渐变 + 3 个模糊色团（`MultiEffect` blur，`blurMax: 64`，不要再调大，160 会渲染空白），或用用户图片（`fillMode: PreserveAspectCrop` + blur + 深色下压暗）。
2. **scrim**：深浅两档，保证面板与文字对比度。
3. **导航/面板**：`Theme.navbar` / `Theme.sidebar` / `Theme.surface`（60–70% 白或深蓝黑），加一条顶部 1px `Theme.sheen` 内高光。
4. **控件**：按钮与输入框同样半透明；按钮是扁平样式——主按钮纯强调色实心、无边框、无内高光、无投影，次按钮半透明面板 + 1px 描边，hover/按下只换颜色（90ms）。按钮上不要再叠反光条或阴影，形状与颜色本身表达层级。

### 主题 token（`app/penmanager/qml/Theme.qml`）

- `mode`: `"light" | "dark"`；`accentName`: 7 种；`wallpaper`: `aurora|sunset|ocean|midnight|none|<图片绝对路径>`。
- 强调色系：`accent / accentHover / accentPressed / accentSoft / accentGlow / textOnAccent`。
- 表面：`bg / bgDeep / surface / surfaceRaised / sidebar / navbar / panel / panelHover / panelActive`。
- 描边：`hairline / hairlineStrong / outline / shadow / sheen`。
- 文本：`text / textSecondary / textDim / textFaint`；状态：`ok / okSoft / warn / warnSoft / danger / dangerSoft`。
- 常量：`fontDisplay/fontText/fontMono`、`sizeDisplay/title/body/small/meta/mono`、`radiusWindow/Panel/Control/Pill`、`gutter/cardPadding`、`sidebarWidth 260`、`titleBarHeight 56`、`controlHeight 36`。
- 禁止在页面里写死十六进制颜色；需要透明色用 `Theme.alpha(hex, a)`。

### 规则

- 深色模式下不改变信息层级，只换 token；任何新页面上线前必须在浅色与深色各截一张图检查对比度。
- 玻璃只做一层：内容卡片本身不透明到看不清背板，也不在半透明卡片里再放半透明卡片。
- 动效只用 90–160ms 的颜色/位置过渡，背板色团缓慢平移（26–34s）制造“流动”，不做高频动画。
- 照片背板：`app/penmanager/data/wallpapers/` 内置 6 张（峡湾/晚霞峡谷/雪山/晨雾森林/海浪/水母，1600×1000 JPEG，来源 Unsplash 经 picsum），加载时统一 `blurMax: 64` + 深色压暗；照片模式不叠加彩色色团。
- 壁纸选择是一个图块画廊（`components/WallpaperTile.qml`，108×72 预览 + 标签），动态渐变、纯色、内置照片、自定义图片都在同一处选中即生效。
- 窗口圆角 14：Windows 10 无 DWM 圆角，由 `winfx_region.apply_round_region()` 裁剪；Windows 11 也会应用，效果一致。
- 任何会阻塞超过 100ms 的工作（adb/ssh/下载）必须放进 `bridge._async()`，禁止在 GUI 线程里同步调用 `penctl`。
