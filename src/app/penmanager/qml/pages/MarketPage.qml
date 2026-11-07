import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import ".."

Item {
    id: page

    property string serial: ""
    property bool busy: false
    property string message: ""
    property string indexUrl: ""
    property string repoUrl: ""
    property string filter: ""
    property var index: ({})
    property var plugins: []
    property bool riskAccepted: false

    function load(url) {
        busy = true
        message = "加载插件索引…"
        backend.marketLoad(url.length > 0 ? url : page.indexUrl)
    }

    function visiblePlugins() {
        var out = []
        var q = filter.toLowerCase()
        for (var i = 0; i < plugins.length; ++i) {
            var p = plugins[i]
            if (q.length === 0
                || (p.name || "").toLowerCase().indexOf(q) >= 0
                || (p.id || "").toLowerCase().indexOf(q) >= 0
                || (p.summary || "").toLowerCase().indexOf(q) >= 0) {
                out.push(p)
            }
        }
        return out
    }

    function latest(p) {
        return p.version || (p.versions && p.versions.length > 0 ? p.versions[0].version : "?")
    }

    Connections {
        target: backend

        function onTaskFinished(id, result) {
            if (id === "market-load") {
                page.busy = false
                if (result.ok) {
                    page.index = result.index || ({})
                    page.plugins = result.plugins || []
                    page.message = (page.plugins.length + " 个插件 · 索引 " + (page.index.name || "未命名"))
                } else {
                    page.plugins = []
                    page.message = "索引加载失败：" + (result.error ? result.error.message : "未知错误")
                }
            } else if (id === "market-install") {
                page.busy = false
                page.message = result.ok ? ("安装完成：" + (result.package ? result.package.id : "")) : "安装失败：请查看提示"
            } else if (id === "market-repo") {
                page.busy = false
                page.message = result.ok ? ("从仓库安装完成：" + (result.package ? result.package.id : "")) : "仓库安装失败"
            }
        }
    }

    FileDialog {
        id: indexPicker
        title: "选择插件索引 index.json"
        nameFilters: ["JSON (*.json)", "所有文件 (*.*)"]
        onAccepted: {
            var raw = indexPicker.selectedFile.toString()
            var path = decodeURIComponent(raw.replace(/^file:\/\/\//, ""))
            page.indexUrl = path
            page.load(path)
        }
    }

    GlassCard {
        anchors.fill: parent

        ColumnLayout {
            anchors.fill: parent
            spacing: 14

            // ---------- header ----------
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: "插件市场"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: Theme.sizeDisplay
                    font.letterSpacing: -0.3
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    text: page.message.length > 0 ? page.message
                                                   : "协议 v1：静态 index.json，每个版本带 SHA256；也可以直接填 GitHub 仓库地址安装。"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.sizeSmall
                    elide: Text.ElideRight
                }

                GlassButton {
                    text: page.busy ? "加载中…" : "加载索引"
                    width: 100
                    primary: true
                    enabled: !page.busy
                    onClicked: page.load(page.indexUrl)
                }
            }

            // ---------- index source ----------
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                GlassTextField {
                    Layout.fillWidth: true
                    placeholderText: "索引 URL（https://）或本地 index.json 路径，留空用内置示例"
                    text: page.indexUrl
                    onTextChanged: page.indexUrl = text
                }

                GlassButton {
                    text: "示例"
                    width: 68
                    enabled: !page.busy
                    onClicked: {
                        page.indexUrl = ""
                        page.load("")
                    }
                }

                GlassButton {
                    text: "本地文件…"
                    width: 96
                    enabled: !page.busy
                    onClicked: indexPicker.open()
                }
            }

            // ---------- direct GitHub install ----------
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                GlassTextField {
                    Layout.fillWidth: true
                    placeholderText: "GitHub 仓库链接（owner/repo 或完整 URL）—— 直接安装最新 release 的 zip"
                    text: page.repoUrl
                    onTextChanged: page.repoUrl = text
                }

                GlassButton {
                    text: "从仓库安装"
                    width: 108
                    enabled: !page.busy && page.repoUrl.length > 0 && page.serial.length > 0
                             && page.riskAccepted
                    onClicked: {
                        page.busy = true
                        page.message = "解析仓库 release…"
                        backend.marketFromRepo(page.repoUrl, page.serial)
                    }
                }
            }

            // ---------- search + risk ----------
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                GlassTextField {
                    Layout.fillWidth: true
                    placeholderText: "搜索插件名称 / id"
                    onTextChanged: page.filter = text
                }

                Rectangle {
                    width: targetLabel.implicitWidth + 16
                    height: 26
                    radius: Theme.radiusPill
                    color: page.serial.length > 0 ? Theme.okSoft : Theme.warnSoft
                    border.width: 1
                    border.color: page.serial.length > 0 ? Theme.alpha(Theme.ok, 0.35) : Theme.alpha(Theme.warn, 0.35)
                    Text {
                        id: targetLabel
                        anchors.centerIn: parent
                        text: page.serial.length > 0 ? "目标设备 " + page.serial : "未连接（仅浏览）"
                        color: page.serial.length > 0 ? Theme.ok : Theme.warn
                        font.pixelSize: Theme.sizeMeta
                    }
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

            // ---------- list ----------
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: page.visiblePlugins()
                spacing: 8

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 72
                    radius: Theme.radiusControl
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.hairline

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12

                        Rectangle {
                            width: 40; height: 40; radius: 10
                            color: Theme.accentSoft
                            Text {
                                anchors.centerIn: parent
                                text: (modelData.name || "?").substring(0, 1)
                                color: Theme.accent
                                font.pixelSize: 16
                                font.weight: Font.Bold
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: modelData.name + "  ·  v" + page.latest(modelData)
                                color: Theme.text
                                font.pixelSize: Theme.sizeBody
                                font.weight: Font.DemiBold
                            }
                            Text {
                                Layout.fillWidth: true
                                text: (modelData.summary || "") + (modelData.author ? "  ·  " + modelData.author : "")
                                color: Theme.textDim
                                font.pixelSize: Theme.sizeMeta
                                elide: Text.ElideRight
                            }
                        }

                        GlassButton {
                            text: modelData.installable === false ? "示例" : "安装"
                            width: 76
                            primary: modelData.installable !== false
                            enabled: !page.busy && page.serial.length > 0 && page.riskAccepted
                                     && modelData.installable !== false
                            onClicked: {
                                page.busy = true
                                page.message = "安装 " + modelData.id + "…"
                                backend.marketInstall(modelData.id, page.latest(modelData), page.serial)
                            }
                        }
                    }
                }
            }

            EmptyState {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: page.plugins.length === 0 && !page.busy
                glyph: "◉"
                title: "还没有插件列表"
                desc: "点「加载索引」拉取插件；默认加载内置示例，也可以填自有 index.json（https 或本地文件），或直接用 GitHub 仓库链接安装。"
                actionText: "加载内置示例"
                onActionClicked: {
                    page.indexUrl = ""
                    page.load("")
                }
            }
        }
    }
}
