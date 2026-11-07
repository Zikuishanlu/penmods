import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Effects
import "components"
import "pages"
import "."

// Preline "classic dashboard" shell: fixed navbar, sidebar below it, content
// canvas in gray-50 with white cards. Frameless window, custom chrome.
Window {
    id: win

    width: 1180
    height: 760
    minimumWidth: 1020
    minimumHeight: 680
    visible: true
    title: "PenMods 管理器"
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"

    property int pageIndex: 0
    property string activeSerial: ""
    property string toastText: ""
    property bool showDisclaimer: false
    property bool disclaimerReady: false
    property string pendingZip: ""
    property bool dropArmed: false

    // ---------------------------------------------------- first run disclaimer
    function disclaimerRisk() {
        return "本工具会修改词典笔的系统文件：替换启动脚本、注入或替换动态库、改动系统分区。"
             + "操作不当、意外断电或版本不匹配，可能导致设备变砖、功能异常、数据丢失、保修失效，且部分后果不可逆。"
    }

    function disclaimerSections() {
        return [
            {
                title: "一、免责条款",
                items: [
                    "本工具是社区第三方开源项目，构建在 PenMods 生态之上，仅供学习研究使用，严禁用于商业用途。",
                    "作者不对软件的完整性、适用性、可靠性做任何明示或暗示的保证。",
                    "因使用本工具造成的任何直接或间接损失（包括但不限于设备损坏、数据丢失、功能异常、保修失效），作者与贡献者不承担任何责任。",
                    "使用本工具即表示你已理解并接受上述全部风险，并自行承担一切后果。",
                    "本工具与网易有道及其关联公司无任何关联；如因使用本工具违反有道用户协议而导致账号或设备受限，作者不承担任何责任。"
                ]
            },
            {
                title: "二、使用须知",
                items: [
                    "操作前请确保设备电量充足（建议 50% 以上）；安装、更新过程中不要拔线、关机或强制退出程序。",
                    "安装前请备份重要数据（单词本、学习记录等），并记录设备当前的恢复方式。",
                    "已确认支持：YDP02x（2.0.7 / 2.0.8）、YDPG3（1.0.2 / 1.0.3）；YDP03x 为实验性支持，其余型号请勿尝试。",
                    "安装后若屏幕无响应，长按电源键强制关机再开机；连续启动失败会触发系统恢复，请按官方指引处理。",
                    "插件与安装包以 root 身份在笔上运行，只安装可信来源；安装前请检查包内文件与 metadata.json。",
                    "请从官方渠道获取软件包，谨防二次修改版；本工具校验 SHA256 只能证明文件未被篡改，不代表内容绝对安全。",
                    "禁止将本工具用于任何违法用途，或违反有道词典笔用户协议的行为。"
                ]
            },
            {
                title: "三、知识产权声明",
                items: [
                    "本工具是第三方独立开源项目，与网易有道公司（NetEase Youdao）及其关联公司无任何隶属关系，也未获其官方授权或认可。",
                    "「有道」「Youdao」「有道词典笔」等商标、品牌名称及设备固件版权归网易有道所有。",
                    "本工具仅提供安装与管理层面的辅助功能，不包含有道词典笔的专有固件代码、逆向工程产物或受版权保护的系统资源。",
                    "PenMods 本体、组件与插件版权归各自作者所有，使用时请遵守其开源许可。",
                    "如认为本项目内容侵犯了你的合法权益，请通过项目仓库与我们联系。"
                ]
            },
            {
                title: "四、开源协议与反馈",
                items: [
                    "本工具为学习研究用途的个人项目，上游 PenMods 生态以 GPL-3.0 许可发布；二次分发时请遵守上游许可与商标约定。",
                    "上游项目：Lyrecoul/PenMods（本体）、lyrecoul/penmods-ota（更新清单）、PenUniverse/PenMods（早期版本）。",
                    "发现问题欢迎提 Issue 或 PR；使用前请先读 README 的「安全边界」与「安装指南」。"
                ]
            }
        ];
    }

    function updateDisclaimerGate() {
        if (!win.showDisclaimer)
            return
        var flick = disclaimerFlick
        if (!flick)
            return
        // Short text (nothing to scroll) counts as fully read.
        if (flick.contentHeight <= flick.height + 6) {
            win.disclaimerReady = true
            return
        }
        var atEnd = flick.atYEnd
            || (flick.contentY + flick.height) >= (flick.contentHeight - 16)
        win.disclaimerReady = atEnd
    }

    function loadDisclaimer() {
        var args = Qt.application.arguments
        win.disclaimerReady = false
        if (args.indexOf("--skip-disclaimer") >= 0) {
            win.showDisclaimer = false
            return
        }
        if (args.indexOf("--show-disclaimer") >= 0) {
            win.showDisclaimer = true
            return
        }
        var st = backend.disclaimerState()
        win.showDisclaimer = !(st && st.accepted)
    }

    function acceptDisclaimerNow() {
        var r = backend.acceptDisclaimer()
        if (!r || !r.ok) {
            win.toast("写入同意记录失败，请检查数据目录权限")
            return
        }
        win.showDisclaimer = false
        win.toast("已记录：免责声明已同意")
    }

    function toast(msg) {
        win.toastText = msg
        toastTimer.restart()
    }

    // Wallpaper presets. "custom" means Theme.wallpaper holds an image path.
    function isPresetWallpaper() {
        var id = Theme.wallpaper
        return id === "aurora" || id === "sunset" || id === "ocean"
               || id === "midnight" || id === "none"
    }

    function wallpaperSource() {
        if (isPresetWallpaper())
            return ""
        if (Theme.wallpaper.indexOf("file:///") === 0)
            return Theme.wallpaper
        return "file:///" + Theme.wallpaper
    }

    function wallpaperColors() {
        if (!isPresetWallpaper())
            return []
        if (Theme.wallpaper === "sunset")
            return [Theme.accent, "#FB7185", "#FBBF24"]
        if (Theme.wallpaper === "ocean")
            return ["#22D3EE", Theme.accent, "#6366F1"]
        if (Theme.wallpaper === "midnight")
            return ["#1E3A8A", "#312E81", Theme.accent]
        if (Theme.wallpaper === "none")
            return []
        return ["#34D399", Theme.accent, "#A78BFA"]
    }

    function applyAppearance() {
        var res = backend.uiSettings()
        if (res && res.ok)
            Theme.apply(res.settings)
    }

    function persistAppearance() {
        backend.saveUiSettings(Theme.toJson())
    }

    // Screenshot / QA overrides, e.g. `--ui-theme dark --ui-accent rose`.
    function applyCommandLineOverrides() {
        var a = Qt.application.arguments
        for (var i = 0; i + 1 < a.length; ++i) {
            if (a[i] === "--ui-theme" && (a[i + 1] === "light" || a[i + 1] === "dark"))
                Theme.mode = a[i + 1]
            else if (a[i] === "--ui-accent")
                Theme.accentName = a[i + 1]
            else if (a[i] === "--ui-wallpaper")
                Theme.wallpaper = a[i + 1]
        }
    }

    Component.onCompleted: {
        win.applyAppearance()
        win.applyCommandLineOverrides()
        win.loadDisclaimer()
    }

    Timer {
        id: toastTimer
        interval: 4200
        onTriggered: win.toastText = ""
    }

    ListModel {
        id: navModel
        ListElement { label: "连接"; glyph: "⇄"; hint: "ADB / SSH 连接点读笔，扫描设备与鉴权" }
        ListElement { label: "设备"; glyph: "▤"; hint: "型号、系统版本、PenMods 版本、存储与运行状态" }
        ListElement { label: "安装"; glyph: "⇩"; hint: "安装 PenMods 本体与可选组件、OTA 更新与回滚" }
        ListElement { label: "插件"; glyph: "❖"; hint: "安装 / 启停 / 卸载插件与安装包（支持拖拽 zip）" }
        ListElement { label: "市场"; glyph: "◉"; hint: "从 GitHub 索引或仓库链接发现并安装插件" }
        ListElement { label: "文件"; glyph: "▦"; hint: "浏览、上传、下载设备文件" }
        ListElement { label: "终端"; glyph: "❯"; hint: "ADB / SSH 交互式 shell" }
        ListElement { label: "设置"; glyph: "⚙"; hint: "连接偏好、SSH 身份、日志与缓存" }
    }

    Component { id: connectComp; ConnectPage { onConnected: function (serial) { win.activeSerial = serial; win.pageIndex = 1 } } }
    Component { id: deviceComp; DevicePage { serial: win.activeSerial; onConnectRequested: win.pageIndex = 0 } }
    Component { id: installComp; InstallPage { serial: win.activeSerial } }
    Component { id: pluginsComp; PluginsPage { serial: win.activeSerial } }
    Component { id: marketComp; MarketPage { serial: win.activeSerial } }
    Component { id: filesComp; FilesPage { serial: win.activeSerial } }
    Component { id: terminalComp; TerminalPage { serial: win.activeSerial } }
    Component { id: settingsComp; SettingsPage { serial: win.activeSerial } }

    // ------------------------------------------------------------- canvas
    Rectangle {
        id: shell
        anchors.fill: parent
        radius: Theme.radiusWindow
        clip: true
        color: Theme.bgDeep
        border.width: win.dropArmed ? 2 : 1
        border.color: win.dropArmed ? Theme.accent : Theme.hairline

        // -------------------------------------------------------- wallpaper
        Item {
            id: wallpaper
            anchors.fill: parent
            clip: true

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Theme.dark ? "#0B1220" : "#F2F5FC" }
                    GradientStop { position: 1.0; color: Theme.dark ? Theme.bgDeep : "#E2E9F4" }
                }
            }

            // Custom photo wallpaper: blurred and scrimmed so glass stays readable.
            Image {
                anchors.fill: parent
                visible: !win.isPresetWallpaper()
                source: visible ? win.wallpaperSource() : ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                layer.enabled: visible
                layer.effect: MultiEffect {
                    blurEnabled: true
                    blur: Theme.dark ? 0.85 : 0.65
                    blurMax: 64
                    saturation: Theme.dark ? -0.25 : 0.15
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: Theme.wallpaper !== "none"
                color: win.isPresetWallpaper()
                       ? (Theme.dark ? "#66070A11" : "#40FFFFFF")
                       : (Theme.dark ? "#33070A11" : "#1FFFFFFF")
            }

            Repeater {
                model: win.wallpaperColors()

                Rectangle {
                    required property int index
                    required property var modelData

                    width: Math.max(shell.width, shell.height) * (index === 1 ? 0.68 : 0.58)
                    height: width
                    radius: width / 2
                    color: modelData
                    opacity: Theme.dark ? 0.60 : 0.46
                    x: index === 0 ? -width * 0.22 : index === 1 ? shell.width - width * 0.55 : shell.width * 0.3
                    y: index === 0 ? shell.height - height * 0.6 : index === 1 ? -height * 0.15 : shell.height * 0.35
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        blurEnabled: true
                        blur: 1.0
                        blurMax: 64
                    }

                    SequentialAnimation on x {
                        running: Theme.wallpaper !== "none"
                        loops: Animation.Infinite
                        NumberAnimation { to: shell.width - width * (index === 0 ? 0.02 : 0.62); duration: 26000 + index * 4000; easing.type: Easing.InOutSine }
                        NumberAnimation { to: -width * (index === 1 ? 0.35 : 0.12); duration: 26000 + index * 4000; easing.type: Easing.InOutSine }
                    }
                }
            }
        }

        // ---------------------------------------------------------- navbar
        Rectangle {
            id: navbar
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: Theme.titleBarHeight
            color: "transparent"
            border.width: 0

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Theme.sheen }
                    GradientStop { position: 1.0; color: Theme.navbar }
                }
            }

            MouseArea {
                anchors.fill: parent
                onPressed: win.startSystemMove()
            }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                // logo mark — Preline's square primary tile
                Rectangle {
                    width: 28; height: 28; radius: 8
                    color: Theme.accent
                    Text {
                        anchors.centerIn: parent
                        text: "P"
                        color: Theme.textOnAccent
                        font.family: Theme.fontDisplay
                        font.pixelSize: 15
                        font.weight: Font.Bold
                    }
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "PenMods"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                }

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 1; height: 18
                    color: Theme.hairline
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: navModel.get(win.pageIndex).label
                    color: Theme.textDim
                    font.family: Theme.fontText
                    font.pixelSize: Theme.sizeBody
                }
            }

            // window controls — flat 40x32 hit areas, close turns red
            Row {
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                spacing: 0

                Repeater {
                    model: ["—", "▢", "✕"]

                    Rectangle {
                        width: 40
                        height: 32
                        radius: 6
                        color: area.containsMouse
                               ? (index === 2 ? Theme.danger : Theme.panelHover)
                               : "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            color: index === 2 && area.containsMouse ? "#FFFFFF" : Theme.textSecondary
                            font.pixelSize: index === 2 ? 12 : 11
                        }

                        MouseArea {
                            id: area
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                if (index === 0) win.showMinimized()
                                else if (index === 1) win.visibility === Window.Maximized ? win.showNormal() : win.showMaximized()
                                else win.close()
                            }
                        }
                    }
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.hairline
            }
        }

        // --------------------------------------------------------- sidebar
        Rectangle {
            id: sidebar
            anchors.left: parent.left
            anchors.top: navbar.bottom
            anchors.bottom: parent.bottom
            width: Theme.sidebarWidth
            color: "transparent"

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Theme.sidebar }
                    GradientStop { position: 1.0; color: Theme.dark ? "#66101926" : "#70FFFFFF" }
                }
            }

            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 1
                color: Theme.hairline
            }

            Text {
                id: navSection
                anchors.left: parent.left
                anchors.leftMargin: 20
                anchors.top: parent.top
                anchors.topMargin: 18
                text: "工作区"
                color: Theme.textFaint
                font.family: Theme.fontText
                font.pixelSize: 11
                font.weight: Font.DemiBold
                font.letterSpacing: 0.6
            }

            Column {
                id: navColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: navSection.bottom
                anchors.topMargin: 10
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 2

                Repeater {
                    model: navModel

                    Rectangle {
                        width: navColumn.width
                        height: Theme.rowHeight
                        radius: Theme.radiusControl
                        color: win.pageIndex === index
                               ? Theme.panelActive
                               : (navArea.containsMouse ? Theme.panel : "transparent")

                        Row {
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 12

                            Item {
                                width: 18; height: 18
                                Text {
                                    anchors.centerIn: parent
                                    text: glyph
                                    color: win.pageIndex === index ? Theme.accent : Theme.textDim
                                    font.pixelSize: 14
                                }
                            }

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: label
                                color: win.pageIndex === index ? Theme.text : Theme.textSecondary
                                font.family: Theme.fontText
                                font.pixelSize: Theme.sizeBody
                                font.weight: win.pageIndex === index ? Font.DemiBold : Font.Medium
                            }
                        }

                        MouseArea {
                            id: navArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: win.pageIndex = index
                        }
                    }
                }
            }

            // ------------------------------------------------------- footer
            Item {
                id: footer
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 76

                Rectangle {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 1
                    color: Theme.hairline
                }

                Rectangle {
                    id: statusCard
                    anchors.fill: parent
                    anchors.topMargin: 13
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    anchors.bottomMargin: 12
                    radius: Theme.radiusControl
                    color: Theme.panel

                    Rectangle {
                        id: statusDot
                        width: 30; height: 30; radius: 15
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        color: win.activeSerial ? Theme.okSoft : Theme.warnSoft
                        Text {
                            anchors.centerIn: parent
                            text: win.activeSerial ? "✓" : "!"
                            color: win.activeSerial ? Theme.ok : Theme.warn
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                    }

                    Column {
                        anchors.left: statusDot.right
                        anchors.leftMargin: 9
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 1

                        Text {
                            text: win.activeSerial
                                  ? (win.activeSerial.indexOf("ssh:") === 0 ? "SSH 已连接" : "ADB 已连接")
                                  : "未连接"
                            color: Theme.text
                            font.family: Theme.fontText
                            font.pixelSize: Theme.sizeSmall
                            font.weight: Font.Medium
                        }

                        Text {
                            width: parent.width
                            text: win.activeSerial
                                  ? win.activeSerial.replace(/^ssh:/, "")
                                  : "等待设备"
                            color: Theme.textDim
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.sizeMeta - 1
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        // -------------------------------------------------------- content
        Item {
            id: content
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.top: navbar.bottom
            anchors.bottom: parent.bottom
            clip: true

            Loader {
                id: pageLoader
                anchors.fill: parent
                anchors.margins: 20
                sourceComponent: win.pageIndex === 0 ? connectComp
                               : win.pageIndex === 1 ? deviceComp
                               : win.pageIndex === 2 ? installComp
                               : win.pageIndex === 3 ? pluginsComp
                               : win.pageIndex === 4 ? marketComp
                               : win.pageIndex === 5 ? filesComp
                               : win.pageIndex === 6 ? terminalComp
                               : settingsComp
            }
        }

        // ---------------------------------------------------------- toast
        Rectangle {
            id: toastChip
            visible: win.toastText.length > 0
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 24
            width: Math.min(toastLabel.implicitWidth + 32, shell.width - 360)
            height: 40
            radius: Theme.radiusControl
            color: Theme.dark ? "#E5E7EB" : "#111827"
            border.width: 1
            border.color: Theme.dark ? "#33FFFFFF" : "#22000000"
            opacity: visible ? 1 : 0

            Behavior on opacity { NumberAnimation { duration: 140 } }

            Text {
                id: toastLabel
                anchors.centerIn: parent
                width: parent.width - 32
                text: win.toastText
                color: Theme.dark ? "#111827" : "#FFFFFF"
                font.family: Theme.fontText
                font.pixelSize: Theme.sizeSmall
                elide: Text.ElideMiddle
                horizontalAlignment: Text.AlignHCenter
            }
        }

        // ----------------------------------------------------- resize grips
        MouseArea { anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 4; cursorShape: Qt.SizeHorCursor; onPressed: win.startSystemResize(1) }
        MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 4; cursorShape: Qt.SizeHorCursor; onPressed: win.startSystemResize(4) }
        MouseArea { anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; height: 4; cursorShape: Qt.SizeVerCursor; onPressed: win.startSystemResize(2) }
        MouseArea { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 4; cursorShape: Qt.SizeVerCursor; onPressed: win.startSystemResize(8) }

        Component.onCompleted: {
            if (typeof backend !== "undefined") {
                var info = backend.appInfo()
                if (info && info.penctl) console.log("penctl:", info.penctl)
            }
        }
    }

    // ----------------------------------------------------- drop to install
    DropArea {
        id: dropArea
        anchors.fill: parent
        onEntered: { win.dropArmed = true; win.toastText = "" }
        onExited: win.dropArmed = false
        onDropped: {
            win.dropArmed = false
            if (win.showDisclaimer)
                return
            if (!drop.hasUrls || drop.urls.length === 0)
                return
            var raw = drop.urls[0].toString()
            var path = decodeURIComponent(raw.replace(/^file:\/\/\//, ""))
            if (path.toLowerCase().indexOf(".zip") < 0) {
                win.toast("只支持 .zip 插件包 / 安装包")
                return
            }
            if (!win.activeSerial) {
                win.toast("先连接设备，再拖入 zip")
                return
            }
            win.pageIndex = 3
            win.pendingZip = path
        }
    }

    // ------------------------------------------------- first run disclaimer UI
    Rectangle {
        id: disclaimerLayer
        anchors.fill: parent
        z: 100
        visible: win.showDisclaimer
        color: "#D90A0E15"

        // Swallow every click so the app is blocked until consent is given.
        MouseArea { anchors.fill: parent }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 160, 580)
            height: Math.min(parent.height - 110, 492)
            radius: Theme.radiusPanel
            color: Theme.dialog
            border.width: 1
            border.color: Theme.hairlineStrong

            Column {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 12

                Row {
                    spacing: 10

                    Rectangle {
                        width: 28; height: 28; radius: 8
                        color: Theme.warnSoft
                        Text {
                            anchors.centerIn: parent
                            text: "!"
                            color: Theme.warn
                            font.family: Theme.fontDisplay
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }
                    }

                    Column {
                        spacing: 1
                        Text {
                            text: "使用须知 & 免责声明"
                            color: Theme.text
                            font.family: Theme.fontDisplay
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: "请仔细阅读以下条款后再使用本工具"
                            color: Theme.textDim
                            font.family: Theme.fontText
                            font.pixelSize: Theme.sizeSmall
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    height: Math.max(180, parent.height - 172)
                    radius: Theme.radiusControl
                    color: Theme.panel
                    border.width: 1
                    border.color: Theme.hairline

                    Flickable {
                        id: disclaimerFlick
                        anchors.fill: parent
                        anchors.margins: 14
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        contentWidth: width
                        contentHeight: disclaimerColumn.height

                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                            width: 8
                        }

                        Column {
                            id: disclaimerColumn
                            width: disclaimerFlick.width - 10
                            spacing: 16

                            Rectangle {
                                width: parent.width
                                implicitHeight: riskText.implicitHeight + 24
                                radius: Theme.radiusControl
                                color: Theme.dangerSoft
                                border.width: 1
                                border.color: Theme.alpha(Theme.danger, 0.32)

                                Text {
                                    id: riskText
                                    x: 12
                                    y: 12
                                    width: parent.width - 24
                                    text: win.disclaimerRisk()
                                    color: Theme.danger
                                    font.family: Theme.fontText
                                    font.pixelSize: Theme.sizeSmall
                                    lineHeight: 1.5
                                    wrapMode: Text.WordWrap
                                }
                            }

                            Repeater {
                                model: win.disclaimerSections()

                                delegate: Column {
                                    width: disclaimerColumn.width
                                    spacing: 6

                                    Text {
                                        text: modelData.title
                                        color: Theme.text
                                        font.family: Theme.fontText
                                        font.pixelSize: Theme.sizeBody
                                        font.weight: Font.DemiBold
                                    }

                                    Column {
                                        width: parent.width
                                        spacing: 5

                                        Repeater {
                                            model: modelData.items

                                            delegate: Text {
                                                width: parent.width
                                                text: "· " + modelData
                                                color: Theme.textSecondary
                                                font.family: Theme.fontText
                                                font.pixelSize: Theme.sizeSmall
                                                lineHeight: 1.5
                                                wrapMode: Text.WordWrap
                                            }
                                        }
                                    }
                                }
                            }

                            onHeightChanged: win.updateDisclaimerGate()
                        }

                        onContentYChanged: win.updateDisclaimerGate()
                        onAtYEndChanged: win.updateDisclaimerGate()
                        onHeightChanged: win.updateDisclaimerGate()
                        onContentHeightChanged: win.updateDisclaimerGate()
                    }
                }

                Text {
                    width: parent.width
                    text: win.disclaimerReady
                          ? "已阅读到末尾，可以继续。"
                          : "把上面的内容滑到最后，底部的同意按钮才会亮起。"
                    color: win.disclaimerReady ? Theme.ok : Theme.warn
                    font.family: Theme.fontText
                    font.pixelSize: Theme.sizeMeta
                    wrapMode: Text.WordWrap
                }

                Item {
                    width: parent.width
                    height: 36

                    Row {
                        anchors.right: parent.right
                        spacing: 8

                        GlassButton {
                            width: 84
                            text: "退出"
                            onClicked: Qt.quit()
                        }

                        GlassButton {
                            width: 156
                            primary: true
                            enabled: win.disclaimerReady
                            text: win.disclaimerReady ? "我已阅读并同意" : "请先读到末尾"
                            onClicked: win.acceptDisclaimerNow()
                        }
                    }
                }
            }
        }

        Timer {
            id: disclaimerJump
            interval: 180
            repeat: true
            running: false
            onTriggered: {
                disclaimerFlick.contentY = Math.max(0, disclaimerFlick.contentHeight - disclaimerFlick.height)
                win.updateDisclaimerGate()
                if (disclaimerFlick.atYEnd)
                    running = false
            }
        }

        onVisibleChanged: {
            if (!visible)
                return
            disclaimerFlick.contentY = 0
            Qt.callLater(win.updateDisclaimerGate)
            // QA helper: jump to the end so screenshots can show the enabled state.
            if (Qt.application.arguments.indexOf("--disclaimer-at-end") >= 0)
                disclaimerJump.running = true
        }
    }

    // -------------------------------------------------- confirm dropped zip
    Rectangle {
        id: confirmLayer
        anchors.fill: parent
        visible: win.pendingZip.length > 0
        color: "#80111827"
        z: 50

        MouseArea { anchors.fill: parent; onClicked: win.pendingZip = "" }

        Rectangle {
            anchors.centerIn: parent
            width: 460
            height: 236
            radius: Theme.radiusPanel
            color: Theme.dialog
            border.width: 1
            border.color: Theme.hairline

            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 12

                Text {
                    text: "安装这个插件包？"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }

                Text {
                    width: parent.width
                    text: "插件以 root 身份在笔上运行，来源不明的插件可能让笔无法启动。只有确认来源可信时才继续。"
                    color: Theme.textSecondary
                    font.family: Theme.fontText
                    font.pixelSize: Theme.sizeSmall
                    lineHeight: 1.45
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    width: parent.width
                    height: 34
                    radius: Theme.radiusControl
                    color: Theme.panel
                    border.width: 1
                    border.color: Theme.hairline
                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        verticalAlignment: Text.AlignVCenter
                        text: win.pendingZip.split("/").pop()
                        color: Theme.textSecondary
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.sizeMono
                        elide: Text.ElideMiddle
                    }
                }

                Item { width: 1; height: 4 }

                Row {
                    spacing: 8
                    anchors.right: parent.right

                    GlassButton { text: "取消"; width: 84; onClicked: win.pendingZip = "" }
                    GlassButton {
                        text: "我明白，安装"
                        width: 124
                        primary: true
                        onClicked: {
                            var zip = win.pendingZip
                            win.pendingZip = ""
                            win.toast("正在安装 " + zip.split("/").pop() + " …")
                            backend.pluginInstall(zip, win.activeSerial)
                        }
                    }
                }
            }
        }
    }
}
