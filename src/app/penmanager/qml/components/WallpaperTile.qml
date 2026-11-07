import QtQuick
import ".."

// One cell of the wallpaper picker: a photo, a generated gradient or the
// plain background. Clicking the tile applies that wallpaper immediately.
Item {
    id: tile

    // "photo" | "gradient" | "plain"
    property string kind: "photo"
    property string source: ""
    property string label: ""
    property var tone: []
    property bool selected: false

    signal clicked()

    width: 100
    height: 88

    Rectangle {
        id: frame
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 64
        radius: Theme.radiusControl
        color: Theme.panel
        border.width: tile.selected ? 2 : 1
        border.color: tile.selected ? Theme.accent : Theme.hairline
        clip: true

        Image {
            anchors.fill: parent
            anchors.margins: 2
            visible: tile.kind === "photo"
            source: tile.kind === "photo" ? "file:///" + tile.source : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            smooth: true
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: Theme.radiusControl - 2
            visible: tile.kind === "gradient"
            gradient: Gradient {
                GradientStop {
                    position: 0.0
                    color: tile.tone.length > 0 ? tile.tone[0] : Theme.accent
                }
                GradientStop {
                    position: 1.0
                    color: tile.tone.length > 1 ? tile.tone[1] : Theme.panelHover
                }
            }

            Rectangle {
                width: parent.height * 0.8
                height: width
                radius: width / 2
                x: parent.width * 0.62
                y: parent.height * 0.42
                color: Theme.alpha("#FFFFFF", 0.28)
            }
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: Theme.radiusControl - 2
            visible: tile.kind === "plain"
            color: Theme.dark ? "#0B1220" : "#F2F5FC"

            Text {
                anchors.centerIn: parent
                text: "纯色"
                color: Theme.textDim
                font.pixelSize: 11
            }
        }

        Rectangle {
            visible: tile.selected
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 5
            width: 16
            height: 16
            radius: 8
            color: Theme.accent

            Text {
                anchors.centerIn: parent
                text: "✓"
                color: Theme.textOnAccent
                font.pixelSize: 10
                font.weight: Font.DemiBold
            }
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: tile.clicked()
        }
    }

    Text {
        anchors.top: frame.bottom
        anchors.topMargin: 5
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        text: tile.label
        color: tile.selected ? Theme.text : Theme.textDim
        font.pixelSize: 10
        elide: Text.ElideRight
    }
}
