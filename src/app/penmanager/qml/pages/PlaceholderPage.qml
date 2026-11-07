import QtQuick
import "../components"
import ".."

Item {
    id: page
    property string title: ""
    property string desc: ""

    GlassCard {
        anchors.fill: parent

        Column {
            anchors.fill: parent
            spacing: 12

            Text {
                text: page.title
                color: Theme.text
                font.family: Theme.fontDisplay
                font.pixelSize: Theme.sizeDisplay
                font.letterSpacing: -0.3
                font.weight: Font.DemiBold
            }

            Text {
                text: page.desc
                color: Theme.textDim
                font.pixelSize: 13
                wrapMode: Text.WordWrap
                width: parent.width
            }

            Rectangle {
                width: parent.width
                height: 1
                color: Theme.hairline
            }

            Text {
                text: "该页面会在后续里程碑接入（见 docs/PLAN.md）。"
                color: Theme.textDim
                font.pixelSize: 12
            }
        }
    }
}
