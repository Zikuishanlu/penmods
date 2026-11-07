import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Item {
    id: page

    property string serial: ""
    property bool busy: false
    property string output: ""
    property var history: []

    function runCommand(cmd) {
        if (cmd.length === 0 || page.busy) return
        busy = true
        var next = history.slice()
        next.push(cmd)
        history = next
        output = output + "\n$ " + cmd + "\n"
        backend.terminalRun(cmd, page.serial)
    }

    Connections {
        target: backend

        function onTaskFinished(id, result) {
            if (id !== "terminal") return
            page.busy = false
            if (result.ok) {
                page.output = page.output + (result.output || "") + (result.output && result.output.endsWith("\n") ? "" : "\n")
            } else {
                page.output = page.output + "[" + (result.error ? result.error.code : "ERROR") + "] "
                              + (result.error ? result.error.message : "") + "\n"
            }
        }
    }

    GlassCard {
        anchors.fill: parent

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: "终端"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: Theme.sizeDisplay
                    font.letterSpacing: -0.3
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    text: page.serial.length > 0
                          ? ("通过 " + page.serial + " 执行设备命令（ADB/SSH）")
                          : "未连接设备"
                    color: Theme.textSecondary
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }

                GlassButton {
                    text: "清空"
                    width: 72
                    onClicked: page.output = ""
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 12
                color: "#111827"
                border.width: 1
                border.color: Theme.hairlineStrong

                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 10
                    clip: true

                    TextArea {
                        id: consoleArea
                        readOnly: true
                        text: page.output
                        color: "#D1FAE5"
                        font.family: "Consolas"
                        font.pixelSize: 12
                        wrapMode: TextArea.WrapAnywhere
                        background: Item {}
                        Component.onCompleted: cursorPosition = length
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                GlassTextField {
                    id: prompt
                    Layout.fillWidth: true
                    placeholderText: page.serial.length > 0 ? "输入命令，回车执行（如 ls -la /userdata）" : "先连接设备"
                    enabled: page.serial.length > 0 && !page.busy
                    onAccepted: {
                        page.runCommand(text)
                        text = ""
                    }
                }

                GlassButton {
                    text: page.busy ? "执行中…" : "执行"
                    width: 84
                    primary: true
                    enabled: page.serial.length > 0 && !page.busy && prompt.text.length > 0
                    onClicked: {
                        page.runCommand(prompt.text)
                        prompt.text = ""
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Repeater {
                    model: ["ls -la /userdata", "df -h /userdata", "cat /userdata/PenModsconfig.json", "ps | grep -i penmods"]
                    GlassButton {
                        text: modelData
                        width: Math.min(240, modelData.length * 7 + 24)
                        enabled: page.serial.length > 0 && !page.busy
                        onClicked: page.runCommand(modelData)
                    }
                }

                Item { Layout.fillWidth: true }
            }
        }
    }
}
