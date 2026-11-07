import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Item {
    id: page

    signal connected(string serial)

    property var result: ({})
    property var device: null
    property string status: "尚未扫描"
    property string sshStatus: ""
    property string realModel: ""
    property bool busy: false
    property bool adbMissing: false
    property string adbHint: ""
    property bool sshBusy: false
    property bool showLog: false
    property bool sshConnected: false
    property string sshTarget: ""
    property string sshError: ""
    property var sshState: ({})
    property string sshHost: "192.168.1.100"
    property string sshUser: "root"
    property string sshPort: "22"

    function refresh() {
        if (busy) return
        busy = true
        result = ({})
        backend.detect()
    }

    function afterDetect(r) {
        busy = false
        result = r
        page.adbMissing = false
        page.adbHint = ""
        if (r && r.ok) {
            var list = r.devices || []
            device = list.length > 0 ? list[0] : null
            var adbVersion = r.adb && r.adb.version ? r.adb.version : "?"
            status = device ? ("adb " + adbVersion + " · 已发现 " + device.serial)
                            : ("adb " + adbVersion + " · 未发现设备")
            realModel = ""
            if (device && device.penctl_ok)
                backend.deviceInfo(device.serial)
        } else {
            device = null
            var code = (r && r.error && r.error.code) ? r.error.code : ""
            var msg = (r && r.error && r.error.message) ? r.error.message : "扫描失败"
            if (code === "ADB_MISSING") {
                page.adbMissing = true
                page.adbHint = "没有找到 adb.exe。开发环境请确认 .toolchain/platform-tools/adb.exe 存在；"
                             + "也可以设置 PENCTL_ADB 环境变量。打包版会把 adb.exe 放在程序目录里。"
                status = "adb 未找到 · 无法扫描 USB 设备"
            } else if (code === "ADB_FAILED" || code === "TIMEOUT") {
                page.adbMissing = true
                page.adbHint = "adb server 起不来：" + msg
                             + " （常见原因：系统临时目录不可写、5037 端口被占用，或安全软件拦截）"
                status = "adb 服务异常 · 无法扫描 USB 设备"
            } else {
                status = msg
            }
        }
    }

    function loadSshState() {
        var r = backend.sshState()
        page.sshState = r || {}
        page.sshConnected = !!(r && r.connected)
        if (page.sshConnected && r.transport) {
            page.sshTarget = (r.transport.user || "root") + "@" + (r.transport.host || "")
            page.sshHost = r.transport.host || page.sshHost
            page.sshUser = r.transport.user || page.sshUser
            page.sshPort = String(r.transport.port || 22)
        }
    }

    function connectSsh() {
        if (page.sshBusy) return
        page.sshBusy = true
        page.sshError = ""
        backend.sshConnect(page.sshHost, page.sshUser, page.sshPort)
    }

    function afterSshConnect(r) {
        page.sshBusy = false
        if (r && r.ok) {
            page.sshConnected = true
            page.sshTarget = r.target || (page.sshUser + "@" + page.sshHost)
            page.sshState = backend.sshState()
            page.status = "SSH 已连接 · " + page.sshTarget
            if (r.derived) page.realModel = r.derived.model || page.realModel
            page.connected("ssh:" + page.sshTarget)
        } else {
            page.sshConnected = false
            page.sshError = r && r.error ? (r.error.message || r.error.code) : "连接失败"
        }
    }

    function disconnectSsh() {
        backend.sshDisconnect()
        page.sshConnected = false
        page.sshTarget = ""
        page.sshError = ""
        page.loadSshState()
    }

    function onboard() {
        if (!device || sshBusy) return
        sshBusy = true
        sshStatus = "正在向设备部署公钥…"
        backend.sshOnboard(device.serial)
    }

    function afterOnboard(r) {
        sshBusy = false
        if (r && r.ok) {
            sshStatus = "SSH 就绪：" + r.host
        } else if (r && r.error) {
            sshStatus = "SSH 失败：" + r.error.message
        } else {
            sshStatus = "SSH 失败：" + (r && r.probe && r.probe.error ? r.probe.error.message : "未知错误")
        }
    }

    Connections {
        target: backend

        function onTaskFinished(id, result) {
            if (id === "detect") {
                page.afterDetect(result)
            } else if (id === "device-info") {
                if (result.ok && result.derived)
                    page.realModel = result.derived.model || ""
            } else if (id === "ssh-connect") {
                page.afterSshConnect(result)
            } else if (id === "ssh-onboard") {
                page.afterOnboard(result)
            }
        }
    }

    Component.onCompleted: {
        refresh()
        loadSshState()
    }

    GlassCard {
        anchors.fill: parent

        ColumnLayout {
            anchors.fill: parent
            spacing: 16

            // ------------------------------------------------------- header
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                ColumnLayout {
                    spacing: 3

                    Text {
                        text: "连接设备"
                        color: Theme.text
                        font.family: Theme.fontDisplay
                        font.pixelSize: Theme.sizeDisplay
                        font.weight: Font.DemiBold
                        font.letterSpacing: -0.3
                    }

                    Text {
                        text: page.status
                        color: Theme.textDim
                        font.family: Theme.fontText
                        font.pixelSize: Theme.sizeSmall
                    }
                }

                Item { Layout.fillWidth: true }

                GlassButton {
                    text: page.busy ? "扫描中…" : "扫描设备"
                    width: 108
                    enabled: !page.busy
                    onClicked: page.refresh()
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

            // ------------------------------------------------------ ssh (Wi-Fi)
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "SSH"
                    color: Theme.textSecondary
                    font.family: Theme.fontText
                    font.pixelSize: Theme.sizeSmall
                    font.weight: Font.DemiBold
                }

                GlassTextField {
                    id: sshUserField
                    Layout.preferredWidth: 74
                    placeholderText: "root"
                    text: page.sshUser
                    onTextChanged: page.sshUser = text
                }

                GlassTextField {
                    id: sshHostField
                    Layout.fillWidth: true
                    placeholderText: "点读笔 IP，如 192.168.1.100"
                    text: page.sshHost
                    onTextChanged: page.sshHost = text
                }

                GlassTextField {
                    id: sshPortField
                    Layout.preferredWidth: 64
                    placeholderText: "22"
                    text: page.sshPort
                    onTextChanged: page.sshPort = text
                }

                GlassButton {
                    width: page.sshConnected ? 72 : 96
                    primary: !page.sshConnected
                    text: page.sshBusy ? "连接中…" : (page.sshConnected ? "断开" : "SSH 连接")
                    enabled: !page.sshBusy
                    onClicked: page.sshConnected ? page.disconnectSsh() : page.connectSsh()
                }

                Text {
                    Layout.maximumWidth: 210
                    text: page.sshConnected
                          ? ("已连接 " + page.sshTarget)
                          : (page.sshError.length > 0 ? page.sshError : "Wi-Fi · 需先在笔上部署公钥")
                    color: page.sshConnected ? Theme.ok : (page.sshError.length > 0 ? Theme.danger : Theme.textDim)
                    font.family: Theme.fontText
                    font.pixelSize: Theme.sizeMeta
                    elide: Text.ElideRight
                }
            }

            // -------------------------------------------------- device / empty
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.radiusPanel
                color: Theme.panelHover
                border.width: 1
                border.color: page.device ? Theme.hairlineStrong : Theme.hairline

                // device card
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 18
                    visible: page.device !== null

                    Rectangle {
                        width: 56; height: 56; radius: 15
                        color: Theme.alpha(Theme.accent, 0.12)
                        border.width: 1
                        border.color: Theme.alpha(Theme.accent, 0.38)
                        Text {
                            anchors.centerIn: parent
                            text: "笔"
                            color: Theme.accent
                            font.family: Theme.fontText
                            font.pixelSize: 20
                            font.weight: Font.Bold
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5

                        RowLayout {
                            spacing: 8

                            Text {
                                text: page.realModel.length > 0 ? page.realModel : (page.device ? (page.device.model || "未知型号") : "")
                                color: Theme.text
                                font.family: Theme.fontDisplay
                                font.pixelSize: 19
                                font.weight: Font.DemiBold
                                font.letterSpacing: -0.2
                            }

                            Rectangle {
                                width: 1; height: 12
                                color: Theme.hairlineStrong
                            }

                            Text {
                                text: page.device && page.device.penctl_ok ? "通道正常" : "通道受限"
                                color: page.device && page.device.penctl_ok ? Theme.ok : Theme.warn
                                font.family: Theme.fontText
                                font.pixelSize: Theme.sizeSmall
                            }
                        }

                        Text {
                            text: page.device ? ("序列号 " + page.device.serial + " · adb 型号 " + (page.device.model || "?") + " · shell " + (page.device.shell || "?")) : ""
                            color: Theme.textDim
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.sizeMono
                        }

                        Text {
                            text: page.sshStatus.length > 0 ? page.sshStatus : "USB 用 ADB，日常读写用 Wi-Fi SSH；两种通道都可用时优先 SSH。"
                            color: page.sshStatus.length > 0
                                   ? (page.sshStatus.indexOf("就绪") >= 0 ? Theme.ok : Theme.warn)
                                   : Theme.textSecondary
                            font.family: Theme.fontText
                            font.pixelSize: Theme.sizeSmall
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                    }

                    ColumnLayout {
                        spacing: 8

                        GlassButton {
                            text: "连接"
                            width: 96
                            primary: true
                            enabled: page.device && page.device.penctl_ok
                            onClicked: page.connected(page.device.serial)
                        }

                        GlassButton {
                            text: page.sshBusy ? "部署中…" : "部署公钥（ADB）"
                            width: 96
                            enabled: !page.sshBusy && page.device && page.device.penctl_ok
                            onClicked: page.onboard()
                        }
                    }
                }

                // empty state
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 80, 430)
                    spacing: 12
                    visible: page.device === null

                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 54; height: 54; radius: 15
                        color: Theme.panelActive
                        border.width: 1
                        border.color: Theme.hairlineStrong
                        Text {
                            anchors.centerIn: parent
                            text: "⇄"
                            color: Theme.textSecondary
                            font.pixelSize: 22
                        }
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: page.busy ? "正在扫描…"
                                         : (page.sshConnected ? ("已通过 SSH 连接 " + page.sshTarget)
                                                              : (page.adbMissing ? "找不到 adb.exe" : "没有发现设备"))
                        color: Theme.text
                        font.family: Theme.fontDisplay
                        font.pixelSize: 17
                        font.weight: Font.DemiBold
                    }

                    Text {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        visible: !page.busy && !page.sshConnected
                        text: page.adbMissing
                              ? page.adbHint
                              : "把点读笔用 USB 连到电脑，并在笔上开启 ADB 调试；也可以直接在下面用 SSH 连接。"
                        color: Theme.textSecondary
                        font.family: Theme.fontText
                        font.pixelSize: Theme.sizeSmall
                        wrapMode: Text.WordWrap
                        lineHeight: 1.45
                    }

                    Text {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        visible: !page.busy && !page.sshConnected && !page.adbMissing
                        text: "扫描会列出 USB 设备；SSH 需要在笔上开启 Wi-Fi 后部署公钥。"
                        color: Theme.textDim
                        font.family: Theme.fontText
                        font.pixelSize: Theme.sizeMeta
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 6
                        spacing: 8

                        GlassButton {
                            text: page.sshConnected ? "查看设备" : "再扫描一次"
                            width: 112
                            primary: true
                            enabled: !page.busy
                            onClicked: {
                                if (page.sshConnected) page.connected("ssh:" + page.sshTarget)
                                else page.refresh()
                            }
                        }

                        GlassButton {
                            text: page.showLog ? "隐藏诊断" : "诊断输出"
                            width: 100
                            onClicked: page.showLog = !page.showLog
                        }
                    }
                }
            }

            // ------------------------------------------------------ diagnostics
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: page.showLog ? 168 : 0
                visible: page.showLog
                clip: true

                TextArea {
                    readOnly: true
                    color: Theme.textSecondary
                    selectionColor: Theme.accent
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.sizeMono
                    wrapMode: TextArea.WrapAnywhere
                    text: page.result && page.result.ok === true
                          ? JSON.stringify(page.result, null, 2)
                          : (page.result && page.result.error
                             ? "错误 " + page.result.error.code + "\n" + page.result.error.message
                             : "点击「扫描设备」开始。")

                    background: Rectangle {
                        color: Theme.panel
                        radius: Theme.radiusControl
                        border.width: 1
                        border.color: Theme.hairline
                    }
                }
            }
        }
    }
}
