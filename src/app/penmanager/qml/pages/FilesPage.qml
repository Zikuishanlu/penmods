import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Item {
    id: page

    property string serial: ""
    property bool busy: false
    property string message: ""
    property string path: "/userdata/PenMods"
    property var rows: []
    property int selected: -1
    property string localDir: ""

    function open(p) {
        busy = true
        message = "读取 " + p
        path = p
        selected = -1
        backend.listDir(p, page.serial)
    }

    function goUp() {
        var p = path
        if (p.length <= 1) return
        if (p.endsWith("/")) p = p.substring(0, p.length - 1)
        var i = p.lastIndexOf("/")
        open(i <= 0 ? "/" : p.substring(0, i))
    }

    function isDir(row) {
        return row.mode.length > 0 && row.mode.charAt(0) === "d"
    }

    Connections {
        target: backend

        function onTaskFinished(id, result) {
            if (id === "files") {
                page.busy = false
                if (result.ok) {
                    page.rows = result.rows || []
                    page.path = result.path || page.path
                    page.message = page.rows.length + " 项"
                } else {
                    page.rows = []
                    page.message = "读取失败：" + (result.error ? result.error.message : "未知错误")
                }
            } else if (id === "pull") {
                page.busy = false
                page.message = result.ok ? ("已下载到 " + page.localDir) : "下载失败"
            }
        }
    }

    onSerialChanged: if (page.serial.length > 0) open(page.path)

    Component.onCompleted: if (page.serial.length > 0) open(page.path)

    GlassCard {
        anchors.fill: parent

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: "文件"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: Theme.sizeDisplay
                    font.letterSpacing: -0.3
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    text: page.message
                    color: Theme.textSecondary
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }

                GlassButton {
                    text: page.busy ? "读取中…" : "刷新"
                    width: 84
                    enabled: !page.busy && page.serial.length > 0
                    onClicked: page.open(page.path)
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                GlassButton {
                    text: "上级"
                    width: 64
                    enabled: !page.busy
                    onClicked: page.goUp()
                }

                GlassTextField {
                    Layout.fillWidth: true
                    text: page.path
                    onTextChanged: page.path = text
                    onAccepted: page.open(page.path)
                }

                GlassTextField {
                    Layout.preferredWidth: 260
                    placeholderText: "下载保存到本机目录"
                    text: page.localDir
                    onTextChanged: page.localDir = text
                }

                GlassButton {
                    text: "下载所选"
                    width: 92
                    enabled: !page.busy && page.selected >= 0 && page.localDir.length > 0 && page.serial.length > 0
                    onClicked: {
                        var row = page.rows[page.selected]
                        page.busy = true
                        page.message = "下载 " + row.name + "…"
                        backend.pullFile(page.path.replace(new RegExp("/$"), "") + "/" + row.name,
                                         page.localDir + "/" + row.name, page.serial)
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

            ListView {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: page.rows
                spacing: 3

                Keys.onUpPressed: page.selected = Math.max(0, page.selected - 1)
                Keys.onDownPressed: page.selected = Math.min(page.rows.length - 1, page.selected + 1)

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 32
                    radius: 6
                    color: page.selected === index ? Theme.panelActive : "transparent"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 10

                        Text {
                            text: page.isDir(modelData) ? "▸" : "·"
                            color: page.isDir(modelData) ? Theme.accent : Theme.textFaint
                            font.pixelSize: 12
                            width: 14
                        }
                        Text {
                            Layout.fillWidth: true
                            text: modelData.name
                            color: page.isDir(modelData) ? Theme.text : Theme.textSecondary
                            font.pixelSize: Theme.sizeSmall
                            font.weight: page.isDir(modelData) ? Font.DemiBold : Font.Normal
                            elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.size
                            color: Theme.textDim
                            font.pixelSize: Theme.sizeMeta
                            width: 70
                            horizontalAlignment: Text.AlignRight
                        }
                        Text {
                            text: modelData.mode
                            color: Theme.textFaint
                            font.pixelSize: Theme.sizeMeta
                            font.family: Theme.fontMono
                            width: 90
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: page.selected = index
                        onDoubleClicked: {
                            if (page.isDir(modelData)) {
                                page.open((page.path.replace(new RegExp("/$"), "")) + "/" + modelData.name)
                            }
                        }
                    }
                }
            }

            EmptyState {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: page.rows.length === 0 && !page.busy
                glyph: "▦"
                title: page.serial.length > 0 ? "这个目录是空的" : "还没有连接设备"
                desc: page.serial.length > 0
                      ? "路径栏里可以输入任意设备目录，双击文件夹进入，选中文件后点「下载所选」。"
                      : "连接点读笔后可以浏览 /userdata、/userdisk 等目录并下载文件。"
            }
        }
    }
}
