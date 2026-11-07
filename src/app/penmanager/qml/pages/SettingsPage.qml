import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import ".."

Item {
    id: page

    property string serial: ""
    property var info: ({})
    property var config: ({})
    property string configMessage: ""
    property var sshState: ({})
    property string sshTarget: ""

    function loadSsh() {
        var st = backend.sshState()
        page.sshState = st || {}
        page.sshTarget = (st && st.transport && st.transport.host)
                       ? ((st.transport.user || "root") + "@" + st.transport.host) : ""
    }

    function forgetHost() {
        backend.sshForgetHost()
        page.loadSsh()
    }

    function disconnectSsh() {
        backend.sshDisconnect()
        page.loadSsh()
    }

    property bool adbAuto: false
    property bool sshAuto: false
    property bool skipAuth: false

    function applyConfig(cfg) {
        page.config = cfg || ({})
        page.adbAuto = cfg ? cfg.adb_autorun === true : false
        page.sshAuto = cfg ? cfg.ssh_autorun === true : false
        page.skipAuth = cfg ? cfg.adb_skip_verification === true : false
    }

    function loadConfig() {
        if (page.serial.length === 0) {
            page.configMessage = "先连接设备才能读取 PenMods 配置"
            return
        }
        page.configMessage = "正在读取设备配置…"
        backend.readConfig(page.serial)
    }

    function saveConfig() {
        if (page.serial.length === 0) return
        var next = JSON.parse(JSON.stringify(page.config || {}))
        next.adb_autorun = page.adbAuto
        next.ssh_autorun = page.sshAuto
        next.adb_skip_verification = page.skipAuth
        page.configMessage = "正在写入设备配置…"
        backend.writeConfig(page.serial, JSON.stringify(next))
    }

    Connections {
        target: backend

        function onTaskFinished(id, result) {
            if (id === "config-read") {
                if (result.ok) {
                    page.applyConfig(result.config)
                    page.configMessage = "已读取 /userdata/PenModsconfig.json"
                } else {
                    page.configMessage = "读取失败：" + (result.error ? result.error.message : "未知错误")
                }
            } else if (id === "config-write") {
                if (result.ok) {
                    page.applyConfig(result.config)
                    page.configMessage = result.message
                } else {
                    page.configMessage = "保存失败：" + (result.error ? result.error.message : "未知错误")
                }
            }
        }
    }

    property var accentChoices: Theme.accentChoices
    property var dynamicWallpapers: [
        { id: "aurora", label: "极光", tone: ["#34D399", "#2563EB"] },
        { id: "sunset", label: "朝霞", tone: ["#FB7185", "#FBBF24"] },
        { id: "ocean", label: "深海", tone: ["#22D3EE", "#6366F1"] },
        { id: "midnight", label: "夜空", tone: ["#1E3A8A", "#312E81"] }
    ]
    property var photoWallpapers: []

    function setMode(next) {
        Theme.mode = next
        win.persistAppearance()
    }

    function setAccent(name) {
        Theme.accentName = name
        win.persistAppearance()
    }

    function setWallpaper(id) {
        Theme.wallpaper = id
        win.persistAppearance()
    }

    function baseName(value) {
        var text = String(value)
        var slash = text.lastIndexOf("/")
        var backslash = text.lastIndexOf("\\")
        var cut = Math.max(slash, backslash)
        return cut >= 0 ? text.substring(cut + 1) : text
    }

    function isWallpaperSelected(path) {
        if (!path)
            return false
        return page.baseName(Theme.wallpaper).toLowerCase() === page.baseName(path).toLowerCase()
    }

    function pickWallpaper() {
        wallpaperPicker.open()
    }

    onSerialChanged: page.loadConfig()
    Component.onCompleted: {
        page.info = backend.appInfo()
        var walls = backend.wallpapers()
        page.photoWallpapers = (walls && walls.items) ? walls.items : []
        page.loadSsh()
        page.loadConfig()
        // QA: --settings-at-end scrolls the card to the bottom for screenshots.
        if (Qt.application.arguments.indexOf("--settings-at-end") >= 0)
            settingsJump.start()
    }

    Timer {
        id: settingsJump
        interval: 450
        repeat: false
        onTriggered: settingsFlick.contentY = Math.max(0, settingsFlick.contentHeight - settingsFlick.height)
    }

    FileDialog {
        id: wallpaperPicker
        title: "选择背板壁纸"
        nameFilters: ["图片 (*.png *.jpg *.jpeg *.webp *.bmp)", "所有文件 (*.*)"]
        onAccepted: {
            var raw = wallpaperPicker.selectedFile.toString()
            var decoded = decodeURIComponent(raw.replace(/^file:\/\/\//, ""))
            page.setWallpaper(decoded)
        }
    }

    GlassCard {
        anchors.fill: parent

        Flickable {
            id: settingsFlick
            anchors.fill: parent
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            contentWidth: width
            contentHeight: settingsColumn.implicitHeight

            ScrollBar.vertical: ScrollBar {
                id: settingsBar
                width: 6
                policy: settingsFlick.contentHeight > settingsFlick.height
                        ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff

                contentItem: Rectangle {
                    implicitWidth: 6
                    radius: 3
                    color: Theme.hairlineStrong
                    opacity: settingsBar.pressed ? 1.0 : 0.8
                }
            }

            ColumnLayout {
                id: settingsColumn
                width: settingsFlick.width - 10
                spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Text {
                    text: "设置"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: Theme.sizeDisplay
                    font.letterSpacing: -0.3
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    text: "运行环境、设备配置与安全选项"
                    color: Theme.textSecondary
                    font.pixelSize: 12
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 16
                rowSpacing: 10

                Text { text: "版本"; color: Theme.textSecondary; font.pixelSize: 12 }
                Text { text: page.info.appVersion || "—"; color: Theme.textSecondary; font.pixelSize: 12 }

                Text { text: "penctl 核心"; color: Theme.textSecondary; font.pixelSize: 12 }
                Text {
                    Layout.fillWidth: true
                    text: page.info.penctl || "未找到（请先 python scripts/build_core.py）"
                    color: page.info.penctl ? Theme.textSecondary : Theme.warn
                    font.pixelSize: 12
                    elide: Text.ElideMiddle
                }

                Text { text: "数据目录"; color: Theme.textSecondary; font.pixelSize: 12 }
                Text { Layout.fillWidth: true; text: page.info.data || "—"; color: Theme.textSecondary; font.pixelSize: 12; elide: Text.ElideMiddle }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

            // -------------------------------------------------- appearance
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Text { text: "外观"; color: Theme.textSecondary; font.pixelSize: Theme.sizeMeta; font.weight: Font.DemiBold }
                Text {
                    Layout.fillWidth: true
                    text: "液态玻璃：浅色 / 深色、强调色与背板壁纸"
                    color: Theme.textDim
                    font.pixelSize: Theme.sizeMeta
                    elide: Text.ElideRight
                }

                Rectangle {
                    width: 168; height: 32; radius: Theme.radiusControl
                    color: Theme.panel
                    border.width: 1
                    border.color: Theme.hairline

                    Row {
                        anchors.fill: parent
                        anchors.margins: 3
                        spacing: 3

                        Repeater {
                            model: [{ id: "light", label: "浅色" }, { id: "dark", label: "深色" }]

                            Rectangle {
                                required property var modelData
                                width: (parent.width - 3) / 2
                                height: parent.height
                                radius: Theme.radiusControl - 2
                                color: Theme.mode === modelData.id ? Theme.surfaceRaised : "transparent"
                                border.width: Theme.mode === modelData.id ? 1 : 0
                                border.color: Theme.hairline

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    color: Theme.mode === modelData.id ? Theme.text : Theme.textDim
                                    font.pixelSize: Theme.sizeMeta
                                    font.weight: Theme.mode === modelData.id ? Font.DemiBold : Font.Normal
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: page.setMode(modelData.id)
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text { text: "主题色"; color: Theme.textDim; font.pixelSize: Theme.sizeMeta; width: 48 }

                Row {
                    spacing: 8

                    Repeater {
                        model: Object.keys(page.accentChoices)

                        Item {
                            required property var modelData
                            width: 26; height: 26

                            Rectangle {
                                anchors.centerIn: parent
                                width: Theme.accentName === modelData ? 20 : 16
                                height: width
                                radius: width / 2
                                color: page.accentChoices[modelData]
                            }

                            Rectangle {
                                anchors.fill: parent
                                radius: width / 2
                                color: "transparent"
                                border.width: 2
                                border.color: Theme.accentName === modelData ? page.accentChoices[modelData] : "transparent"
                                opacity: Theme.accentName === modelData ? 1.0 : 0.0
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: page.setAccent(modelData)
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "背板壁纸"
                        color: Theme.textSecondary
                        font.pixelSize: Theme.sizeMeta
                        font.weight: Font.DemiBold
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "点一张立刻生效，选择会被记住；也可以用本机图片。"
                        color: Theme.textDim
                        font.pixelSize: Theme.sizeMeta
                        elide: Text.ElideRight
                    }

                    GlassButton {
                        text: "图片…"
                        width: 78
                        onClicked: page.pickWallpaper()
                    }
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 12

                    Repeater {
                        model: page.dynamicWallpapers

                        WallpaperTile {
                            required property var modelData
                            kind: "gradient"
                            tone: modelData.tone
                            label: modelData.label
                            selected: Theme.wallpaper === modelData.id
                            onClicked: page.setWallpaper(modelData.id)
                        }
                    }

                    WallpaperTile {
                        kind: "plain"
                        label: "纯色"
                        selected: Theme.wallpaper === "none"
                        onClicked: page.setWallpaper("none")
                    }

                    Repeater {
                        model: page.photoWallpapers

                        WallpaperTile {
                            required property var modelData
                            kind: "photo"
                            source: modelData.path
                            label: modelData.label
                            selected: page.isWallpaperSelected(modelData.path)
                            onClicked: page.setWallpaper(modelData.path)
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Text { text: "设备配置"; color: Theme.textSecondary; font.pixelSize: Theme.sizeMeta; font.weight: Font.DemiBold }
                Text {
                    Layout.fillWidth: true
                    text: page.configMessage.length > 0 ? page.configMessage
                          : "PenModsconfig.json（ADB/SSH 自启、跳过 ADB 鉴权），写入后重启 PenMods 生效"
                    color: Theme.textDim
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
                GlassButton {
                    text: "读取"
                    width: 64
                    enabled: page.serial.length > 0
                    onClicked: page.loadConfig()
                }
                GlassButton {
                    text: "保存"
                    width: 64
                    primary: true
                    enabled: page.serial.length > 0
                    onClicked: page.saveConfig()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    width: 168
                    height: 56
                    radius: 12
                    color: Theme.surface
                    border.width: 1
                    border.color: page.adbAuto ? Theme.accent : Theme.hairline
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8
                        Text { Layout.fillWidth: true; text: "开机自启 ADB"; color: Theme.textSecondary; font.pixelSize: 12; elide: Text.ElideRight }
                        GlassSwitch {
                            checked: page.adbAuto
                            onToggled: page.adbAuto = !page.adbAuto
                        }
                    }
                }

                Rectangle {
                    width: 168
                    height: 56
                    radius: 12
                    color: Theme.surface
                    border.width: 1
                    border.color: page.sshAuto ? Theme.accent : Theme.hairline
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8
                        Text { Layout.fillWidth: true; text: "开机自启 SSH"; color: Theme.textSecondary; font.pixelSize: 12; elide: Text.ElideRight }
                        GlassSwitch {
                            checked: page.sshAuto
                            onToggled: page.sshAuto = !page.sshAuto
                        }
                    }
                }

                Rectangle {
                    width: 168
                    height: 56
                    radius: 12
                    color: Theme.surface
                    border.width: 1
                    border.color: page.skipAuth ? Theme.accent : Theme.hairline
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8
                        Text { Layout.fillWidth: true; text: "跳过 ADB 鉴权"; color: Theme.textSecondary; font.pixelSize: 12; elide: Text.ElideRight }
                        GlassSwitch {
                            checked: page.skipAuth
                            onToggled: page.skipAuth = !page.skipAuth
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

            Text { text: "SSH 身份"; color: Theme.textSecondary; font.pixelSize: 12; font.weight: Font.DemiBold }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: 3

                    Text {
                        text: page.sshState.connected ? ("当前已连接 " + page.sshTarget) : "当前未使用 SSH"
                        color: page.sshState.connected ? Theme.ok : Theme.text
                        font.family: Theme.fontText
                        font.pixelSize: Theme.sizeSmall
                    }

                    Text {
                        text: page.sshState.key || "—"
                        color: Theme.textDim
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.sizeMeta
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "known_hosts：" + (page.sshState.knownHosts || "—")
                                + (page.sshState.knownHostsExists ? "（已固定主机密钥）" : "（还没有固定任何主机）")
                        color: Theme.textDim
                        font.family: Theme.fontText
                        font.pixelSize: Theme.sizeMeta
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                }

                Item { Layout.fillWidth: true }

                GlassButton {
                    width: 96
                    text: "忘记主机密钥"
                    enabled: page.sshState.knownHostsExists === true
                    onClicked: page.forgetHost()
                }

                GlassButton {
                    width: 82
                    text: "断开 SSH"
                    enabled: page.sshState.connected === true
                    onClicked: page.disconnectSsh()
                }
            }

            Text { text: "安全约定"; color: Theme.textSecondary; font.pixelSize: 12; font.weight: Font.DemiBold }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Repeater {
                    model: [
                        "写设备只覆盖 .tmp/.new 再同目录 mv -f，绝不原地覆盖正在运行的 .so",
                        "安装结束统一 killall YoudaoDictPen 让新库生效，不自动重启设备",
                        "所有下载先做 SHA256/MD5 校验再落盘，市场包同样走 zip-slip 与符号链接校验",
                        "SSH 只部署本机 ed25519 公钥，不写入密码、不改 sshd_config"
                    ]
                    Text {
                        Layout.fillWidth: true
                        text: "· " + modelData
                        color: Theme.textSecondary
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                }
            }

                Item { Layout.fillWidth: true; height: 6 }
            }
        }
    }
}
