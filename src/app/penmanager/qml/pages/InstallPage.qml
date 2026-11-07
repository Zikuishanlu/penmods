import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Item {
    id: page

    property string serial: ""
    property bool busy: false
    property string task: ""
    property string message: ""
    property var release: ({})
    property var components: []
    property var events: []
    property string currentVersion: ""
    property var otaInfo: ({})
    property bool updateMode: false
    property var updateRows: []
    property var updateStatus: ({})
    property var migration: ({})
    property bool migrationBusy: false
    property string migrationStep: ""
    property bool pendingMigration: false

    function sizeMb(bytes) {
        if (!bytes) return "—"
        return (bytes / 1048576).toFixed(1) + " MB"
    }

    function toggle(id) {
        for (var i = 0; i < components.length; ++i) {
            var comp = components[i]
            if (comp.id === id && !comp.required) {
                comp.enabled = !comp.enabled
            }
        }
        var csv = []
        for (var j = 0; j < components.length; ++j) {
            if (!components[j].required && components[j].enabled) csv.push(components[j].id)
        }
        components = components  // force re-eval of delegates
        backend.planInstall(csv.join(","))
    }

    function begin(label) {
        busy = true
        task = label
        message = label + "…"
        events = []
    }

    function refresh() {
        if (page.busy) return
        page.begin("检查最新版")
        backend.checkRelease()
    }

    function pendingNames() {
        if (!page.updateStatus || !page.updateStatus.pending)
            return ""
        var pc = page.updateStatus.pending_components || {}
        var names = []
        for (var k in pc) names.push(k)
        return names.join(" / ")
    }

    function enableAndReboot() {
        if (!page.serial || page.busy) return
        page.begin("启用更新")
        backend.enablePendingUpdate(page.serial)
    }

    function cancelPending() {
        if (!page.serial || page.busy) return
        page.begin("撤销 pending")
        backend.cancelPendingUpdate(page.serial)
    }

    function loadUpdateComponents() {
        if (page.serial.length === 0) {
            page.updateMode = false
            page.updateRows = []
            return
        }
        page.message = "正在读取组件清单…"
        backend.updateComponents(page.serial)
    }

    function loadMigration() {
        if (Qt.application.arguments.indexOf("--fake-migration") >= 0)
            return
        if (page.serial.length === 0) {
            page.migration = ({})
            return
        }
        backend.migrationStatus(page.serial)
    }

    onSerialChanged: {
        page.loadUpdateComponents()
        page.loadMigration()
    }
    Component.onCompleted: {
        page.loadUpdateComponents()
        page.loadMigration()
        if (page.components.length === 0) refresh()
        // QA: render the migration banner without a device attached.
        if (Qt.application.arguments.indexOf("--fake-migration") >= 0) {
            page.migration = ({
                probe: {
                    ok: true,
                    needs_migration: true,
                    reasons: ["当前启动器为 2.7.0，存在冷启动缺陷", "设备上未出现 PenMods guarded launcher v3"],
                    launcher_ready: false,
                    launcher: { path: "/usr/bin/runDictPen", present: true, guarded: false, raw: "0" }
                },
                release: { tag: "V2.7.3", html_url: "https://github.com/Lyrecoul/PenMods/releases/tag/V2.7.3" },
                version: "2.7.3",
                asset: "update_v2.7.3.zip",
                size: 5693376
            })
            if (Qt.application.arguments.indexOf("--fake-migration-confirm") >= 0)
                page.pendingMigration = true
        }
    }

    Connections {
        target: backend

        function onProgress(id, message) {
            if (id === "migration-install")
                page.migrationStep = message
        }

        function onTaskFinished(id, result) {
            page.busy = false
            if (id === "release" || id === "plan") {
                if (result.ok) {
                    page.release = result.release || {}
                    page.components = result.components || []
                    page.message = "已连接 GitHub：最新版 " + (page.release.tag || "?")
                } else {
                    page.message = "获取版本失败：" + (result.error ? result.error.message : "未知错误")
                }
            } else if (id === "install") {
                page.events = result.events || []
                page.message = result.ok ? ("安装完成：" + (result.release || "")) : "安装中断，请查看步骤"
            } else if (id === "ota-check") {
                page.otaInfo = result
                page.message = result.ok
                    ? (result.up_to_date ? "已是最新版本" : ("发现新版本 " + result.available.version))
                    : ("OTA 检查失败：" + (result.error ? result.error.message : ""))
            } else if (id === "update-components") {
                if (result.ok) {
                    page.updateMode = true
                    page.updateRows = result.components || []
                    page.updateStatus = result.status || {}
                    if (page.message.indexOf("正在读取组件清单") >= 0)
                        page.message = "v2.7 update-system：组件以 stage 方式安装，重启后由守护进程校验并启用。"
                } else {
                    page.updateMode = false
                    page.updateRows = []
                }
            } else if (id === "update-cancel") {
                page.message = result.ok ? "已撤销待启用的更新" : ("撤销失败：" + (result.error ? result.error.message : ""))
                page.loadUpdateComponents()
            } else if (id === "update-enable") {
                if (result.ok) {
                    page.message = "已启用待生效更新，正在重启设备以校验新组件…"
                    backend.rebootDevice(page.serial)
                    win.toast("设备重启中，约 30 秒后可在「连接」页重新连接")
                } else {
                    page.message = "启用失败：" + (result.error ? result.error.message : "未知错误")
                }
                page.loadUpdateComponents()
            } else if (id === "update-status") {
                page.updateStatus = result.status || {}
            } else if (id === "migration-status") {
                if (result.ok) {
                    page.migration = result
                } else {
                    page.migration = ({})
                    page.message = "读取启动器状态失败：" + (result.error ? result.error.message : "未知错误")
                }
                page.migrationBusy = false
            } else if (id === "migration-install") {
                page.migrationBusy = false
                page.migrationStep = ""
                if (result.ok) {
                    var kept = result.probe || {}
                    page.migration = ({ probe: kept, version: result.version || "" })
                    page.message = "迁移完成（" + (result.version || "") + "）："
                                    + (kept.needs_migration ? "仍有待处理项，请点「校验启动器」" : "启动器已就绪，重启阅读应用后生效")
                    win.toast("迁移完成，重启阅读应用后生效")
                } else {
                    page.message = "迁移失败：" + (result.error ? result.error.message : "未知错误")
                    win.toast("迁移失败，请查看安装页提示和 doc/RECOVERY_2.7.3.md")
                }
                page.loadMigration()
            } else if (id === "launcher-verify") {
                var probe = result.probe || {}
                page.migration = ({ probe: probe })
                if (!result.ok) {
                    page.message = "校验失败：" + (result.error ? result.error.message : "未知错误")
                } else if (probe.needs_migration) {
                    page.message = "启动器检查：仍需迁移（" + ((probe.reasons || []).join("；")) + "）"
                } else {
                    page.message = "启动器检查：guarded v3 已就位"
                }
            } else if (id === "app-restart") {
                page.message = result.ok ? ("已发送重启命令：" + (result.message || "")) : "重启失败"
            } else if (id === "update-stage") {
                page.events = []
                page.message = result.ok
                    ? ("已 stage " + (result.component || "") + " " + (result.version || "") + "，重启后生效；可在下方取消。")
                    : ("stage 失败：" + (result.error ? result.error.message : "未知错误"))
                page.loadUpdateComponents()
            } else if (id === "ota-apply") {
                page.events = result.events || []
                page.message = result.ok ? ("OTA 更新完成：" + (result.version || "")) : "OTA 更新失败"
            }
        }
    }

    GlassCard {
        anchors.fill: parent

        ColumnLayout {
            anchors.fill: parent
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: "安装 PenMods"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: Theme.sizeDisplay
                    font.letterSpacing: -0.3
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    text: page.message.length > 0 ? page.message : "本体必装；可选组件按需勾选，安装前逐一校验 SHA256。"
                    color: Theme.textSecondary
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }

                GlassButton {
                    text: page.busy ? "处理中…" : "检查最新版"
                    width: 108
                    enabled: !page.busy
                    onClicked: page.refresh()
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

            // ---------------------------------------- launcher migration (v2.7.3)
            Rectangle {
                id: migrationBanner
                visible: !!(page.migration.probe && page.migration.probe.needs_migration)
                Layout.fillWidth: true
                implicitHeight: migRow.implicitHeight + 20
                radius: Theme.radiusControl
                color: Theme.dangerSoft
                border.width: 1
                border.color: Theme.alpha(Theme.danger, 0.32)

                RowLayout {
                    id: migRow
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: "启动器迁移（V2.7.3 完整迁移包）"
                            color: Theme.danger
                            font.family: Theme.fontText
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }

                        Text {
                            Layout.fillWidth: true
                            text: {
                                if (page.migrationStep.length > 0)
                                    return page.migrationStep
                                var probe = page.migration.probe || {}
                                var reasons = probe.reasons || []
                                var head = reasons.length > 0 ? reasons.join("；") : "检测到旧启动器"
                                return head + "。V2.7.0 / 2.7.1 的启动器有冷启动缺陷，"
                                             + "只能在更新中心之外跑一次完整迁移包（会重写启动脚本与入口）。"
                            }
                            color: Theme.textSecondary
                            font.pixelSize: 11
                            lineHeight: 1.4
                            wrapMode: Text.WordWrap
                        }
                    }

                    GlassButton {
                        text: page.migrationBusy ? "迁移中…" : "下载并迁移"
                        width: 108
                        primary: true
                        enabled: !page.migrationBusy && page.serial.length > 0
                        onClicked: {
                            if (!page.serial || page.migrationBusy)
                                return
                            page.pendingMigration = true
                        }
                    }

                    GlassButton {
                        text: "校验启动器"
                        width: 96
                        enabled: !page.migrationBusy && page.serial.length > 0
                        onClicked: backend.launcherVerify(page.serial)
                    }

                    GlassButton {
                        text: "重启应用"
                        width: 84
                        enabled: !page.migrationBusy && page.serial.length > 0
                        onClicked: backend.migrationRestart(page.serial)
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 16

                // -------------------------------------------------- component list
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 6

                    Text {
                        text: "组件选择"
                        color: Theme.textSecondary
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: page.components.length === 0
                        text: page.busy ? "正在读取组件清单…"
                                         : "点右上角「检查最新版」拉取 GitHub Release 组件清单。"
                        color: Theme.textDim
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }

                    ListView {
                        visible: !page.updateMode
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: page.components
                        spacing: 6

                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 62
                            radius: 12
                            color: modelData.enabled ? Theme.accentSoft : Theme.surface
                            border.width: 1
                            border.color: (modelData.enabled || modelData.required) ? Theme.accent : Theme.hairline

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 12

                                Rectangle {
                                    width: 18; height: 18; radius: 4
                                    color: modelData.enabled ? Theme.accent : Theme.surface
                                    border.width: 1
                                    border.color: modelData.enabled ? Theme.accent : Theme.hairlineStrong
                                    opacity: modelData.available ? 1.0 : 0.45
                                    Text {
                                        anchors.centerIn: parent
                                        visible: modelData.enabled
                                        text: "✓"
                                        color: Theme.textOnAccent
                                        font.pixelSize: 12
                                        font.weight: Font.Bold
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: (modelData.required || !modelData.available) ? Qt.ArrowCursor : Qt.PointingHandCursor
                                        onClicked: if (!modelData.required && modelData.available) page.toggle(modelData.id)
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: modelData.title + (modelData.required ? "（必装）" : "")
                                        color: Theme.text
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.desc
                                        color: Theme.textSecondary
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }
                                }

                                Text {
                                    text: page.sizeMb(modelData.size)
                                    color: Theme.textDim
                                    font.pixelSize: 11
                                }
                            }
                        }
                    }

                    ListView {
                        visible: page.updateMode
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: page.updateRows
                        spacing: 6

                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 62
                            radius: 12
                            color: Theme.panelHover
                            border.width: 1
                            border.color: modelData.required ? Theme.alpha(Theme.accent, 0.45) : Theme.hairlineStrong

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 12

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: modelData.name + (modelData.required ? "（本体）" : "")
                                        color: Theme.text
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: (modelData.installed.length > 0 ? ("已装 " + modelData.installed) : "未安装")
                                              + (modelData.up_to_date
                                                 ? ((modelData.installed.length > 0 && modelData.installed !== modelData.latest)
                                                    ? ("  ·  设备通道 " + modelData.latest + "，无需更新")
                                                    : "  ·  已是最新")
                                                 : ("  →  最新 " + modelData.latest))
                                              + (modelData.blocked ? ("  · " + modelData.blocked_reason) : "")
                                        color: modelData.blocked ? Theme.warn : Theme.textSecondary
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }
                                }

                                Text {
                                    text: page.sizeMb(modelData.size)
                                    color: Theme.textDim
                                    font.pixelSize: 11
                                }

                                Text {
                                    visible: modelData.pending
                                    text: "待启用"
                                    color: Theme.warn
                                    font.pixelSize: 11
                                }

                                GlassButton {
                                    visible: !modelData.pending
                                    width: 72
                                    text: modelData.blocked ? "先升级本体" : (modelData.up_to_date ? "已是最新" : "安装")
                                    enabled: !modelData.up_to_date && !page.busy && page.serial.length > 0
                                             && !modelData.blocked
                                    onClicked: {
                                        page.begin("安装 " + modelData.name)
                                        backend.stageComponent(modelData.id, page.serial)
                                    }
                                }
                            }
                        }
                    }

                    // ------------------------------------------- pending generation
                    Rectangle {
                        Layout.fillWidth: true
                        visible: page.pendingNames().length > 0
                        height: visible ? 52 : 0
                        radius: 12
                        color: Theme.warnSoft
                        border.width: 1
                        border.color: Theme.alpha(Theme.warn, 0.4)

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 10

                            Text {
                                Layout.fillWidth: true
                                text: "待启用：" + page.pendingNames() + "（重启后由守护进程校验，失败自动回滚）"
                                color: Theme.warn
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                            }

                            GlassButton {
                                text: "启用并重启"
                                width: 104
                                primary: true
                                enabled: page.serial.length > 0
                                onClicked: page.enableAndReboot()
                            }

                            GlassButton {
                                text: "取消"
                                width: 64
                                enabled: page.serial.length > 0
                                onClicked: page.cancelPending()
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "本体 libPenMods.so 必装且不可取消；其余组件按需勾选，确认后一次性写设备。"
                        color: Theme.textDim
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                }

                // ------------------------------------------------------ right side
                ColumnLayout {
                    Layout.preferredWidth: 316
                    Layout.fillHeight: true
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        GlassTextField {
                            Layout.fillWidth: true
                            placeholderText: "当前版本（OTA 检查用）"
                            text: page.currentVersion
                            onTextChanged: page.currentVersion = text
                        }

                        GlassButton {
                            text: "检查 OTA"
                            width: 84
                            enabled: !page.busy
                            onClicked: {
                                page.begin("检查 OTA")
                                backend.checkOta(page.currentVersion)
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: page.otaInfo && page.otaInfo.version !== undefined
                        text: page.otaInfo.up_to_date
                              ? "OTA：已是最新版本"
                              : ("OTA：" + (page.otaInfo.available ? page.otaInfo.available.version : "")
                                 + (page.otaInfo.available && page.otaInfo.available.note ? " · " + page.otaInfo.available.note : ""))
                        color: Theme.ok
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }

                    GlassButton {
                        Layout.fillWidth: true
                        text: page.busy ? "安装中…" : (page.updateMode ? "旧版注入安装" : "安装到设备")
                        primary: true
                        visible: !page.updateMode
                        enabled: !page.busy && page.serial.length > 0
                        onClicked: {
                            page.begin("安装 PenMods")
                            backend.runInstall(page.serial)
                        }
                    }

                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: "旧设备通道"
                            color: Theme.textDim
                            font.family: Theme.fontText
                            font.pixelSize: Theme.sizeMeta
                        }

                        Item { Layout.fillWidth: true }

                        GlassButton {
                            width: 96
                            text: page.busy ? "更新中…" : "应用 OTA"
                            enabled: !page.busy && page.serial.length > 0
                            onClicked: {
                                page.begin("应用 OTA")
                                backend.applyOta(page.serial)
                            }
                        }

                        GlassButton {
                            width: 68
                            text: "回滚"
                            enabled: !page.busy
                            onClicked: {
                                page.begin("回滚")
                                backend.rollback()
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: page.serial.length === 0
                        text: "先在「连接」页连接设备，这里的按钮才会启用。"
                        color: Theme.warn
                        font.family: Theme.fontText
                        font.pixelSize: Theme.sizeMeta
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        text: "步骤"
                        color: Theme.textSecondary
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: page.events
                        spacing: 4
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 36
                            radius: Theme.radiusControl
                            color: Theme.panel

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 8
                                Text {
                                    text: modelData.ok ? "✓" : "✕"
                                    color: modelData.ok ? Theme.ok : Theme.danger
                                    font.pixelSize: Theme.sizeSmall
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.title
                                        color: Theme.text
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.output || modelData.command || ""
                                        color: Theme.textDim
                                        font.pixelSize: Theme.sizeMeta
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    // ---------------------------------------------------- migration confirm
    Rectangle {
        id: migrationConfirm
        anchors.fill: parent
        visible: page.pendingMigration
        color: "#80111827"
        z: 60

        MouseArea { anchors.fill: parent; onClicked: page.pendingMigration = false }

        Rectangle {
            anchors.centerIn: parent
            width: 460
            height: 268
            radius: Theme.radiusPanel
            color: Theme.dialog
            border.width: 1
            border.color: Theme.hairline

            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 12

                Text {
                    text: "确认迁移启动器？"
                    color: Theme.text
                    font.family: Theme.fontDisplay
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }

                Text {
                    width: parent.width
                    text: "这一步会把 V2.7.3 完整迁移包推到笔上，重写启动脚本与开机入口，然后需要重启阅读应用才能生效。\n"
                          + "迁移期间不要拔线、不要连续杀进程（新版守护器有 16 秒冷却）。失败时按 doc/RECOVERY_2.7.3.md 恢复。"
                    color: Theme.textSecondary
                    font.family: Theme.fontText
                    font.pixelSize: Theme.sizeSmall
                    lineHeight: 1.45
                    wrapMode: Text.WordWrap
                }

                Item { width: 1; height: 4 }

                Row {
                    spacing: 8
                    anchors.right: parent.right

                    GlassButton { text: "取消"; width: 84; onClicked: page.pendingMigration = false }
                    GlassButton {
                        text: "我明白，开始迁移"
                        width: 148
                        primary: true
                        onClicked: {
                            page.pendingMigration = false
                            page.migrationBusy = true
                            page.migrationStep = "准备下载迁移包…"
                            backend.migrationInstall(page.serial)
                        }
                    }
                }
            }
        }
}
}
