import QtQuick
import ".."

// Preline switch: 36x20 track, 16px knob, neutral track when off, primary when on.
Item {
    id: root

    property bool checked: false
    property bool interactive: true
    signal toggled()

    width: 36
    height: 20

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.checked ? Theme.accent : (Theme.dark ? "#2EFFFFFF" : "#D1D5DB")
        Behavior on color { ColorAnimation { duration: 120 } }

        Rectangle {
            width: 16; height: 16; radius: 8
            y: 2
            x: root.checked ? parent.width - width - 2 : 2
            color: "#FFFFFF"
            border.width: 1
            border.color: root.checked ? Theme.accent : (Theme.dark ? "#3DFFFFFF" : "#C7CDD6")
            Behavior on x { NumberAnimation { duration: 120 } }
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.interactive
        cursorShape: root.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.toggled()
    }
}
