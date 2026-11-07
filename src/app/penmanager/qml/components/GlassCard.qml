import QtQuick
import QtQuick.Effects
import ".."

// Liquid-glass panel: a translucent pane sitting on the wallpaper, with a
// bright top sheen, a 1px glass edge and a soft drop shadow. Nothing here
// samples what is behind it (that would need a per-panel shader source), so
// the illusion comes from a strongly blurred wallpaper plus generous
// translucency - cheap, and it keeps every control responsive.
Rectangle {
    id: card
    radius: Theme.radiusPanel
    color: Theme.surface
    border.width: 1
    border.color: Theme.hairline
    antialiasing: true

    property int padding: 20

    default property alias content: contentItem.data

    // Diagonal highlight: brighter at the top-left like a pane of glass.
    Rectangle {
        anchors.fill: parent
        radius: card.radius
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Theme.dark ? "#14FFFFFF" : "#B3FFFFFF" }
            GradientStop { position: 0.55; color: "transparent" }
            GradientStop { position: 1.0; color: Theme.dark ? "#0AFFFFFF" : "#4DFFFFFF" }
        }
        opacity: 0.8
    }

    // Top sheen line: the "wet" edge that reads as glass thickness.
    Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: 1
        anchors.leftMargin: 1
        anchors.rightMargin: 1
        height: 1
        radius: 1
        color: Theme.sheen
        opacity: 0.75
    }

    Item {
        id: contentItem
        anchors.fill: parent
        anchors.margins: card.padding
    }
}
