import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

// Device overview. Everything is anchored explicitly: Qt Quick Layouts
// distributes leftover height in ways that kept pushing the tiles around.
Item {
    id: page

    signal connectRequested()

    property string serial: ""
    property var info: ({})
    property var derived: ({})
    property string status: "连接设备后自动读取。"
    property bool busy: false
    property bool showRaw: false

    property bool hasDevice: false

    function refresh() {
        if (!page.hasDevice) {
            info = {}
            derived = {}
            status = "连接设备后自动读取。"
            return
        }
        busy = true
        page.info = {}
        page.derived = {}
        page.status = "正在读取设备信息…"
        backend.deviceInfo(page.serial)
    }

    Connections {
        target: backend

        function onTaskFinished(id, result) {
            if (id !== "device-info") return
            page.busy = false
            if (result.ok) {
                page.info = result.info || {}
                page.derived = result.derived || {}
                page.status = "读取 " + Object.keys(page.info).length + " 项探针"
            } else {
                page.info = {}
                page.derived = {}
                page.status = (result.error && result.error.message) ? result.error.message : "读取失败"
            }
        }
    }

    function flag(v) { return v === true ? "开" : "关" }

    function chipModel() {
        var d = page.derived
        return [
            { k: "ADB 自启", v: page.flag(d.adb_autostart) },
            { k: "SSH 自启", v: page.flag(d.ssh_autostart) },
            { k: "跳过 ADB 鉴权", v: page.flag(d.adb_skip_auth) },
            { k: "启动器", v: page.info.app_binary ? "在 /oem" : "未知" }
        ]
    }

    onSerialChanged: {
        page.hasDevice = page.serial.length > 0
        page.refresh()
    }

    Component.onCompleted: {
        page.hasDevice = page.serial.length > 0
        page.refresh()
    }

    GlassCard {
        anchors.fill: parent

        Item {
            anchors.fill: parent

            RowLayout {
                id: header
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                spacing: 12

                ColumnLayout {
                    spacing: 3

                    Text {
                        text: "设备信息"
                        color: Theme.text
                        font.family: Theme.fontDisplay
                        font.pixelSize: Theme.sizeDisplay
                        font.weight: Font.DemiBold
                        font.letterSpacing: -0.3
                    }

                    Text {
                        text: page.hasDevice
                              ? ((page.serial.indexOf("ssh:") === 0
                                  ? ("SSH · " + page.serial.slice(4))
                                  : page.serial) + " · " + page.status)
                              : page.status
                        color: Theme.textDim
                        font.family: Theme.fontText
                        font.pixelSize: Theme.sizeSmall
                    }
                }

                Item { Layout.fillWidth: true }

                GlassButton {
                    text: page.busy ? "读取中…" : "刷新"
                    width: 84
                    enabled: !page.busy && page.hasDevice
                    onClicked: page.refresh()
                }
            }

            Rectangle {
                id: rule
                anchors.top: header.bottom
                anchors.topMargin: 12
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.hairline
            }

            // -------------------------------------------------- empty state
            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width - 80, 420)
                spacing: 12
                visible: !page.hasDevice

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 54; height: 54; radius: 15
                    color: Theme.panelActive
                    border.width: 1
                    border.color: Theme.hairlineStrong
                    Text {
                        anchors.centerIn: parent
                        text: "▤"
                        color: Theme.textSecondary
                        font.pixelSize: 22
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "还没有选择设备"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: "先到「连接」页扫描 USB 设备，或在那边用 SSH 直连点读笔。"
                    color: Theme.textSecondary
                    font.family: Theme.fontText
                    font.pixelSize: Theme.sizeSmall
                    wrapMode: Text.WordWrap
                    lineHeight: 1.45
                }

                GlassButton {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 4
                    text: "去连接"
                    width: 104
                    primary: true
                    onClicked: page.connectRequested()
                }
            }

            // ------------------------------------------------------- tiles
            GridLayout {
                id: tiles
                anchors.top: rule.bottom
                anchors.topMargin: 16
                anchors.left: parent.left
                anchors.right: parent.right
                columns: 3
                columnSpacing: 12
                rowSpacing: 12
                visible: page.hasDevice

                InfoTile {
                    Layout.fillWidth: true
                    label: "型号"
                    value: page.derived.model || "未知"
                    hint: page.derived.model_supported ? "受支持" : "未在支持列表"
                    accent: page.derived.model_supported ? Theme.ok : Theme.warn
                }
                InfoTile {
                    Layout.fillWidth: true
                    label: "系统版本"
                    value: page.derived.system_version || "—"
                    hint: page.info.kernel ? ("内核 " + page.info.kernel) : ""
                }
                InfoTile {
                    Layout.fillWidth: true
                    label: "PenMods"
                    value: page.derived.penmods_installed ? "已安装" : "未安装"
                    hint: page.derived.penmods_installed ? "运行中" : "可到「安装」页部署"
                    accent: page.derived.penmods_installed ? Theme.ok : Theme.warn
                }
                InfoTile {
                    Layout.fillWidth: true
                    label: "存储 /userdata"
                    value: page.info.storage || "—"
                }
                InfoTile {
                    Layout.fillWidth: true
                    label: "运行时间"
                    value: page.info.uptime || "—"
                }
                InfoTile {
                    Layout.fillWidth: true
                    label: "SSH 服务"
                    value: (page.info.sshd || "").indexOf("sshd") >= 0 ? "运行中" : "未运行"
                    accent: (page.info.sshd || "").indexOf("sshd") >= 0 ? Theme.ok : Theme.textDim
                }
            }

            // ------------------------------------------------------ config
            ColumnLayout {
                id: config
                anchors.top: tiles.bottom
                anchors.topMargin: 18
                anchors.left: parent.left
                anchors.right: parent.right
                spacing: 10
                visible: page.hasDevice

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "启动配置"
                        color: Theme.textSecondary
                        font.family: Theme.fontText
                        font.pixelSize: Theme.sizeSmall
                        font.weight: Font.DemiBold
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: page.showRaw ? "隐藏原始探针" : "原始探针"
                        color: Theme.textDim
                        font.family: Theme.fontText
                        font.pixelSize: Theme.sizeMeta
                    }

                    Rectangle {
                        width: 30; height: 18; radius: 9
                        color: page.showRaw ? Theme.accentSoft : Theme.panelActive
                        border.width: 1
                        border.color: page.showRaw ? Theme.alpha(Theme.accent, 0.6) : Theme.outline

                        Rectangle {
                            width: 12; height: 12; radius: 6
                            y: 3
                            x: page.showRaw ? 15 : 3
                            color: page.showRaw ? Theme.accent : Theme.textSecondary
                            Behavior on x { NumberAnimation { duration: 90 } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: page.showRaw = !page.showRaw
                        }
                    }
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: page.hasDevice ? page.chipModel() : []

                        Rectangle {
                            height: 26
                            radius: 7
                            width: chipText.implicitWidth + 20
                            color: Theme.panelHover
                            border.width: 1
                            border.color: Theme.hairline

                            Text {
                                id: chipText
                                anchors.centerIn: parent
                                text: modelData.k + " " + modelData.v
                                color: modelData.v === "开" ? Theme.text : Theme.textSecondary
                                font.family: Theme.fontText
                                font.pixelSize: Theme.sizeMeta
                            }
                        }
                    }
                }
            }

            // --------------------------------------------------- raw probes
            ScrollView {
                id: rawBox
                anchors.top: config.bottom
                anchors.topMargin: 12
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                visible: page.showRaw && page.hasDevice
                clip: true

                TextArea {
                    readOnly: true
                    color: Theme.textSecondary
                    selectionColor: Theme.accent
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.sizeMono
                    wrapMode: TextArea.WrapAnywhere
                    background: null
                    text: JSON.stringify({ info: page.info, derived: page.derived }, null, 2)
                }
            }
        }
    }
}
