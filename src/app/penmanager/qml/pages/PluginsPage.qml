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
    property var plugins: []
    property string zipPath: ""
    property bool riskAccepted: false

    function reload() {
        console.log("reload, serial=", page.serial)
        busy = true
        message = "读取已安装插件…"
        backend.pluginList(page.serial)
    }

    function installPath(path) {
        if (!path) return
        if (!riskAccepted) {
            message = "请先勾选下面的风险确认，再安装插件"
            return
        }
        busy = true
        message = "校验并安装 " + path
        backend.pluginInstall(path, page.serial)
    }

    Connections {
        target: backend

        function onTaskFinished(id, result) {
            if (id === "plugin-list") {
                console.log("plugin-list result size:", (result.plugins || []).length)
                page.busy = false
                page.plugins = result.plugins || []
                page.message = "已安装 " + page.plugins.length + " 个插件"
            } else if (id === "plugin-install" || id === "market-install") {
                page.busy = false
                if (result.ok) {
                    page.message = "安装完成：" + (result.package ? result.package.id : "")
                    page.reload()
                } else {
                    page.message = "安装失败：" + (result.error ? result.error.message : (result.device ? "设备返回失败" : "未知错误"))
                }
            } else if (id === "plugin-toggle" || id === "plugin-remove") {
                page.busy = false
                page.message = result.ok ? "操作完成" : "操作失败"
                page.reload()
            }
        }
    }

    onSerialChanged: if (page.serial.length > 0) reload()

    Component.onCompleted: if (page.serial.length > 0) reload()

    GlassCard {
        anchors.fill: parent

        ColumnLayout {
            anchors.fill: parent
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: "插件"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: Theme.sizeDisplay
                    font.letterSpacing: -0.3
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    text: page.message.length > 0 ? page.message : "插件放在 /userdisk/PenMods/plugins/<id>/，本体 .so 必装、其余可选。"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.sizeSmall
                    elide: Text.ElideRight
                }

                GlassButton {
                    text: page.busy ? "读取中…" : "刷新"
                    width: 84
                    enabled: !page.busy && page.serial.length > 0
                    onClicked: page.reload()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                GlassTextField {
                    Layout.fillWidth: true
                    placeholderText: "插件 zip / 安装包路径（可把文件拖进来）"
                    text: page.zipPath
                    onTextChanged: page.zipPath = text
                }

                GlassButton {
                    text: "在线安装"
                    width: 96
                    primary: true
                    enabled: !page.busy && page.zipPath.length > 0 && page.serial.length > 0
                            && page.riskAccepted
                    onClicked: page.installPath(page.zipPath)
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                GlassCheckbox {
                    checked: page.riskAccepted
                    onToggled: page.riskAccepted = !page.riskAccepted
                }

                Text {
                    Layout.fillWidth: true
                    text: "我了解：插件以 root 身份在笔上运行，来源不明的插件可能让笔无法启动（bootloop）。"
                    color: Theme.textDim
                    font.pixelSize: Theme.sizeMeta
                    wrapMode: Text.WordWrap
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: page.plugins
                spacing: 6

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 68
                    radius: Theme.radiusControl
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.hairline

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12

                        Rectangle {
                            width: 36; height: 36; radius: 10
                            color: Theme.accentSoft
                            Text {
                                anchors.centerIn: parent
                                text: (modelData.name ? modelData.name.substring(0, 1) : "?")
                                color: Theme.accent
                                font.pixelSize: 15
                                font.weight: Font.Bold
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: (modelData.name || modelData.id)
                                      + (modelData.enabled === false ? "  ·  已禁用" : "")
                                color: Theme.text
                                font.pixelSize: Theme.sizeBody
                                font.weight: Font.DemiBold
                            }
                            Text {
                                Layout.fillWidth: true
                                text: modelData.id + (modelData.version ? " · v" + modelData.version : "")
                                      + (modelData.description ? " · " + modelData.description : "")
                                color: Theme.textDim
                                font.pixelSize: Theme.sizeMeta
                                elide: Text.ElideRight
                            }
                        }

                        GlassButton {
                            text: modelData.enabled === false ? "启用" : "禁用"
                            width: 68
                            enabled: !page.busy && page.serial.length > 0
                            onClicked: {
                                page.busy = true
                                page.message = (modelData.enabled === false ? "启用 " : "禁用 ") + modelData.id
                                backend.pluginToggle(modelData.id, modelData.enabled === false, page.serial)
                            }
                        }

                        GlassButton {
                            text: "卸载"
                            width: 64
                            enabled: !page.busy && page.serial.length > 0
                            onClicked: {
                                page.busy = true
                                page.message = "卸载 " + modelData.id
                                backend.pluginUninstall(modelData.id, page.serial)
                            }
                        }
                    }
                }
            }

            EmptyState {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: page.plugins.length === 0 && !page.busy
                glyph: "❖"
                title: page.serial.length > 0 ? "还没有安装插件" : "还没有连接设备"
                desc: page.serial.length > 0
                      ? "把插件 zip 的路径填到上面的输入框，或去「市场」页浏览插件。"
                      : "连接点读笔后可以查看已安装插件、禁用或卸载它们。"
            }
        }
    }
}
