import QtQuick
import QtQuick.Layouts
import ".."

// Preline-style dashed placeholder used whenever a page has nothing to show.
Item {
    id: root

    property string glyph: "·"
    property string title: ""
    property string desc: ""
    property string actionText: ""
    signal actionClicked()

    implicitHeight: 240

    // Preline keeps empty placeholders on the page background with a light
    // neutral outline, so the placeholder never competes with real content.
    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusPanel
        color: Theme.bg
        border.width: 1
        border.color: Theme.hairline
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 420)
        spacing: 10

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 48; height: 48; radius: 24
            color: Theme.panel

            Text {
                anchors.centerIn: parent
                text: root.glyph
                color: Theme.textFaint
                font.pixelSize: 18
            }
        }

        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: root.title
            color: Theme.text
            font.family: Theme.fontText
            font.pixelSize: Theme.sizeBody
            font.weight: Font.DemiBold
        }

        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            visible: root.desc.length > 0
            text: root.desc
            color: Theme.textDim
            font.family: Theme.fontText
            font.pixelSize: Theme.sizeSmall
            wrapMode: Text.WordWrap
            lineHeight: 1.45
        }

        GlassButton {
            Layout.alignment: Qt.AlignHCenter
            visible: root.actionText.length > 0
            text: root.actionText
            primary: true
            onClicked: root.actionClicked()
        }
    }
}
