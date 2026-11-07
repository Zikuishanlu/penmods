import QtQuick
import QtQuick.Controls
import ".."

// Glass input: translucent white/dark pane, 1px edge that turns accent on
// focus, and a 3px accent halo while typing.
TextField {
    id: field

    implicitHeight: Theme.controlHeight
    color: Theme.text
    placeholderTextColor: Theme.textFaint
    selectionColor: Theme.accentSoft
    selectedTextColor: Theme.text
    font.family: Theme.fontText
    font.pixelSize: Theme.sizeBody
    leftPadding: 12
    rightPadding: 12
    verticalAlignment: TextInput.AlignVCenter
    background: Rectangle {
        radius: Theme.radiusControl
        color: Theme.panel
        border.width: field.activeFocus ? 2 : 1
        border.color: field.activeFocus ? Theme.accent : Theme.hairlineStrong

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Theme.dark ? "#0AFFFFFF" : "#59FFFFFF"
            visible: !field.activeFocus
        }
    }
}
