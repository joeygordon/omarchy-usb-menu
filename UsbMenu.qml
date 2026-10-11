import QtQuick
import qs.Ui as Ui
import qs.Commons

Column {
    id: menu
    readonly property string uiRevision: "native-compact-v10-feedback"
    property var drives: []
    property bool busy: false
    property string ejectingPath: ""
    property string ejectingToken: ""
    property string status: ""
    property bool statusError: false
    signal actionRequested(string verb, var drive, var volume)
    spacing: Style.spacing.md

    Item {
        width: parent.width
        implicitHeight: Math.max(headerIcon.implicitHeight, headerTitle.implicitHeight, headerCount.implicitHeight)
        Text {
            id: headerIcon
            anchors.left: parent.left
            anchors.verticalCenter: headerTitle.verticalCenter
            text: ""
            color: Color.popups.text
            font.family: Style.font.family
            font.pixelSize: Style.font.icon
        }
        Text {
            id: headerTitle
            objectName: "usbHeaderTitle"
            anchors.left: headerIcon.right
            anchors.leftMargin: Style.spacing.sm
            anchors.right: headerCount.left
            anchors.rightMargin: Style.spacing.md
            anchors.verticalCenter: parent.verticalCenter
            text: "USB storage"
            elide: Text.ElideRight
            color: Color.popups.text
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            font.bold: true
        }
        Text {
            id: headerCount
            objectName: "usbHeaderCount"
            anchors.right: parent.right
            anchors.baseline: headerTitle.baseline
            text: menu.drives.length.toString()
            color: Color.muted
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignRight
        }
    }
    Ui.PanelSeparator { foreground: Color.popups.text }
    Repeater {
        model: menu.drives
        Column {
            id: driveRow
            required property var modelData
            required property int index
            readonly property bool ejecting: modelData.path === menu.ejectingPath && modelData.token === menu.ejectingToken
            width: menu.width
            spacing: Style.spacing.sm
            Ui.PanelSeparator { visible: driveRow.index > 0; foreground: Color.popups.text }
            Item {
                width: parent.width
                implicitHeight: Math.max(driveTitle.implicitHeight, ejectButton.implicitHeight)
                Text {
                    id: driveTitle
                    anchors.left: parent.left
                    anchors.right: ejectButton.left
                    anchors.rightMargin: Style.spacing.sm
                    anchors.verticalCenter: parent.verticalCenter
                    text: driveRow.modelData.displayName || driveRow.modelData.name
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: Color.popups.text
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                }
                Ui.Button {
                    id: ejectButton
                    objectName: "usbEjectAction"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    text: driveRow.ejecting ? "Ejecting…" : "Eject"
                    iconText: "\uf052"
                    fontSize: Style.font.bodySmall
                    iconSize: Style.font.bodySmall
                    horizontalPadding: Style.spacing.sm
                    verticalPadding: Style.spacing.sm
                    foreground: Color.popups.text
                    focusable: true
                    enabled: !menu.busy && !!driveRow.modelData.token
                    opacity: enabled || driveRow.ejecting ? 1 : 0.45
                    Accessible.role: Accessible.Button
                    Accessible.name: "Eject " + (driveRow.modelData.displayName || driveRow.modelData.name)
                    Accessible.description: "Safely remove all volumes on this drive"
                    onClicked: menu.actionRequested("eject", driveRow.modelData, null)
                }
            }
            Repeater {
                model: driveRow.modelData.volumes
                Item {
                    id: volumeRow
                    required property var modelData
                    width: driveRow.width
                    implicitHeight: Math.max(volumeLabel.implicitHeight, openButton.implicitHeight)
                    Text {
                        id: folderIcon
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: ""
                        color: Color.muted
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                    }
                    Text {
                        id: volumeLabel
                        anchors.left: folderIcon.right
                        anchors.leftMargin: Style.spacing.sm
                        anchors.right: openButton.left
                        anchors.rightMargin: Style.spacing.sm
                        anchors.verticalCenter: parent.verticalCenter
                        text: volumeRow.modelData.name
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: Color.popups.text
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                    }
                    Ui.Button {
                        id: openButton
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Open"
                        fontSize: Style.font.bodySmall
                        horizontalPadding: Style.spacing.sm
                        verticalPadding: Style.spacing.sm
                        foreground: Color.popups.text
                        focusable: true
                        enabled: !menu.busy
                        opacity: enabled ? 1 : 0.45
                        Accessible.role: Accessible.Button
                        Accessible.name: "Open " + volumeRow.modelData.name
                        Accessible.description: "Open volume in file manager"
                        onClicked: menu.actionRequested("open", driveRow.modelData, volumeRow.modelData)
                    }
                }
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: driveRow.modelData.error
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
            }
        }
    }
    Ui.PanelSeparator { visible: menu.status !== ""; foreground: Color.popups.text }
    Text {
        width: parent.width
        text: (menu.busy ? "◌  " : "") + menu.status
        visible: menu.status !== ""
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        color: menu.statusError ? Color.urgent : Color.muted
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
    }
}
