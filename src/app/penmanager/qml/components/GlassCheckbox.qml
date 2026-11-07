import QtQuick
import ".."

// Preline checkbox: 4px radius, 1px neutral border, primary fill when checked.
Item {
    id: root

    property bool checked: false
    property bool interactive: true
    signal toggled()

    width: 18
    height: 18

    Rectangle {
        anchors.fill: parent
        radius: 4
        color: root.checked ? Theme.accent : Theme.surface
        border.width: 1
        border.color: root.checked ? Theme.accent : Theme.hairlineStrong

        Text {
            anchors.centerIn: parent
            visible: root.checked
            text: "✓"
            color: Theme.textOnAccent
            font.pixelSize: 12
            font.weight: Font.Bold
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.interactive
        cursorShape: root.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.toggled()
    }
}
