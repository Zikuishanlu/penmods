import QtQuick
import ".."

// Flat button: solid accent for the primary action, quiet glass for the rest.
// No gradients, no inner shadow - the shape itself carries the affordance.
Rectangle {
    id: btn

    property alias text: label.text
    property bool primary: false
    property bool hovered: area.containsMouse && btn.enabled

    signal clicked()

    implicitHeight: Theme.controlHeight
    implicitWidth: Math.max(label.implicitWidth + 32, 88)
    radius: Theme.radiusControl

    color: !btn.enabled
             ? (Theme.dark ? "#12FFFFFF" : "#EEF1F5")
             : btn.primary
               ? (area.pressed ? Theme.accentPressed : (btn.hovered ? Theme.accentHover : Theme.accent))
               : (btn.hovered ? Theme.panelHover : Theme.panel)
    border.width: btn.primary ? 0 : 1
    border.color: btn.enabled ? Theme.hairline : (Theme.dark ? "#14FFFFFF" : "#E2E6EC")

    Behavior on color { ColorAnimation { duration: 90 } }

    Text {
        id: label
        anchors.centerIn: parent
        color: !btn.enabled ? Theme.textFaint : (btn.primary ? Theme.textOnAccent : Theme.text)
        font.family: Theme.fontText
        font.pixelSize: Theme.sizeBody
        font.weight: Font.Medium
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: if (btn.enabled) btn.clicked()
    }
}
