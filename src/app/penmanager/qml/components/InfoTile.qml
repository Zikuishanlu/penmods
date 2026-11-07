import QtQuick
import ".."

// Preline stat card: white layer, hairline border, rounded-xl, label in
// text-xs/medium muted-foreground, value in text-xl semibold foreground.
Rectangle {
    id: tile

    property string label: ""
    property string value: ""
    property string hint: ""
    property string accent: Theme.text
    property string labelColor: Theme.textDim

    implicitHeight: 96
    radius: Theme.radiusPanel
    color: Theme.surface
    border.width: 1
    border.color: Theme.hairline

    Column {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 6

        Text {
            text: tile.label
            color: tile.labelColor
            font.family: Theme.fontText
            font.pixelSize: Theme.sizeSmall
            font.weight: Font.Medium
        }

        Text {
            width: parent.width
            text: tile.value
            color: tile.accent
            font.family: Theme.fontDisplay
            font.pixelSize: Theme.sizeDisplay
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }

        Text {
            width: parent.width
            visible: tile.hint.length > 0
            text: tile.hint
            color: Theme.textDim
            font.family: Theme.fontText
            font.pixelSize: Theme.sizeMeta
            elide: Text.ElideRight
        }
    }
}
