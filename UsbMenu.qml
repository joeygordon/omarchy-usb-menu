import QtQuick
import qs.Ui as Ui
import qs.Commons

Column {
    id: menu
    readonly property string uiRevision: "native-compact-v16-secondary-contrast"
    readonly property color secondaryText: Util.alpha(Color.popups.text, 0.75)
    property var drives: []
    property var spaceStats: ({})
    property var expanded: ({})
    function detailKey(drive) { return drive.path + "|" + (drive.token || "") }
    function toggleDetails(drive) {
        var next = Object.assign({}, expanded)
        next[detailKey(drive)] = !next[detailKey(drive)]
        expanded = next
    }
    function collapseDetails() { expanded = ({}) }
    onDrivesChanged: {
        var next = ({})
        for (var i = 0; i < drives.length; i++) {
            var key = detailKey(drives[i])
            if (expanded[key]) next[key] = true
        }
        expanded = next
    }
    function bytesText(bytes) {
        var value = Number(bytes)
        if (!isFinite(value) || value <= 0) return "Unavailable"
        var units = ["B", "KB", "MB", "GB", "TB", "PB"]
        var index = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1000)))
        index = Math.max(0, index)
        return (value / Math.pow(1000, index)).toLocaleString(Qt.locale("en_US"), "f", index ? 1 : 0) + " " + units[index]
    }
    function validSpace(volume) {
        var stats = volume.spaceKey ? spaceStats[volume.spaceKey] : null
        return stats && isFinite(stats.totalBytes) && isFinite(stats.availableBytes) && stats.totalBytes > 0 && stats.availableBytes >= 0 && stats.availableBytes <= stats.totalBytes ? stats : null
    }
    function usageFraction(volume) {
        var stats = validSpace(volume)
        if (!stats || typeof stats.usedBytes !== "number" || !isFinite(stats.usedBytes) || stats.usedBytes < 0 || stats.usedBytes > stats.totalBytes - stats.availableBytes) return -1
        return stats.usedBytes / stats.totalBytes
    }
    function usageDescription(volume) {
        var fraction = usageFraction(volume)
        if (fraction < 0) return "Usage unavailable"
        var stats = validSpace(volume)
        return Math.round(fraction * 100) + "% used; " + (stats.usedBytes === 0 ? "0 B" : bytesText(stats.usedBytes)) + " used of " + bytesText(stats.totalBytes) + "; " + volumeSpace(volume)
    }
    function volumeSpace(volume) {
        var stats = validSpace(volume)
        if (stats) return (stats.availableBytes === 0 ? "0 B" : bytesText(stats.availableBytes)) + " free · " + bytesText(stats.totalBytes) + " total"
        if (volume.filesystemBytes > 0) return bytesText(volume.filesystemBytes) + " total · free unavailable"
        if (volume.partitionBytes > 0) return bytesText(volume.partitionBytes) + " partition · free unavailable"
        return "Space unavailable"
    }
    function connectionText(drive) {
        var rate = Number(drive.usbSpeedMbps)
        if (!isFinite(rate) || rate <= 0) return "USB · speed unavailable"
        return "USB · " + (rate >= 1000 ? rate / 1000 + " Gbps" : rate + " Mbps")
    }
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
            color: menu.secondaryText
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
            readonly property bool detailsOpen: !!menu.expanded[menu.detailKey(modelData)]
            readonly property bool ejecting: modelData.path === menu.ejectingPath && modelData.token === menu.ejectingToken
            width: menu.width
            spacing: Style.spacing.sm
            Ui.PanelSeparator { visible: driveRow.index > 0; foreground: Color.popups.text }
            Item {
                width: parent.width
                implicitHeight: Math.max(driveTitle.implicitHeight, ejectButton.implicitHeight)
                Item {
                    id: driveTitle
                    objectName: "usbDetailsToggle"
                    signal clicked()
                    anchors.left: parent.left
                    anchors.right: ejectButton.left
                    anchors.rightMargin: Style.spacing.sm
                    anchors.verticalCenter: parent.verticalCenter
                    implicitHeight: ejectButton.implicitHeight
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: driveRow.modelData.displayName || driveRow.modelData.name
                    Accessible.checkable: true
                    Accessible.checked: driveRow.detailsOpen
                    Accessible.description: (driveRow.detailsOpen ? "Expanded. " : "Collapsed. ") + "Toggle filesystem, capacity, connection, and mount details"
                    Accessible.onPressAction: clicked()
                    Accessible.onToggleAction: clicked()
                    Keys.onReturnPressed: clicked()
                    Keys.onEnterPressed: clicked()
                    Keys.onSpacePressed: clicked()
                    onClicked: menu.toggleDetails(driveRow.modelData)
                    Rectangle {
                        objectName: "usbTitleFocus"
                        anchors.fill: parent
                        radius: Style.space(3)
                        color: "transparent"
                        border.width: driveTitle.activeFocus ? 1 : 0
                        border.color: Color.accent
                    }
                    Text {
                        id: titleLabel
                        objectName: "usbDriveTitle"
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(0, Math.min(implicitWidth, parent.width - titleChevron.width - Style.spacing.sm))
                        text: driveRow.modelData.displayName || driveRow.modelData.name
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: Color.popups.text
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                        font.bold: true
                    }
                    Text {
                        id: titleChevron
                        objectName: "usbTitleChevron"
                        anchors.left: titleLabel.right
                        anchors.leftMargin: Style.spacing.sm
                        anchors.verticalCenter: parent.verticalCenter
                        text: driveRow.detailsOpen ? "⌃" : "⌄"
                        color: menu.secondaryText
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                        Accessible.ignored: true
                    }
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { driveTitle.forceActiveFocus(); driveTitle.clicked() }
                    }
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
                    implicitHeight: Math.max(volumeLabel.implicitHeight, openButton.implicitHeight) + spaceLabel.implicitHeight + Style.spacing.sm + Style.space(6)
                    Text {
                        id: folderIcon
                        anchors.left: parent.left
                        anchors.verticalCenter: volumeLabel.verticalCenter
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
                        anchors.verticalCenter: openButton.verticalCenter
                        text: volumeRow.modelData.name
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: Color.popups.text
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                    }
                    Text {
                        id: spaceLabel
                        objectName: "usbVolumeSpace"
                        anchors.left: volumeLabel.left
                        anchors.right: parent.right
                        anchors.bottom: usageTrack.top
                        anchors.bottomMargin: Style.space(3)
                        text: menu.volumeSpace(volumeRow.modelData)
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: menu.secondaryText
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                    }
                    Rectangle {
                        id: usageTrack
                        objectName: "usbUsageTrack"
                        readonly property real fraction: menu.usageFraction(volumeRow.modelData)
                        anchors.left: volumeLabel.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: Style.space(3)
                        radius: height / 2
                        visible: fraction >= 0
                        color: Qt.rgba(Color.muted.r, Color.muted.g, Color.muted.b, 0.16)
                        Accessible.role: Accessible.ProgressBar
                        Accessible.name: volumeRow.modelData.name + ": " + menu.usageDescription(volumeRow.modelData)
                        Rectangle {
                            objectName: "usbUsageFill"
                            height: parent.height
                            width: parent.width * Math.max(0, parent.fraction)
                            radius: parent.radius
                            color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.48)
                        }
                    }
                    Ui.Button {
                        id: openButton
                        objectName: "usbOpenAction"
                        anchors.right: parent.right
                        anchors.top: parent.top
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
            Column {
                objectName: "usbDriveDetails"
                topPadding: Style.spacing.lg
                width: parent.width
                visible: driveRow.detailsOpen
                spacing: Style.spacing.sm
                Text {
                    width: parent.width
                    text: "Drive capacity: " + menu.bytesText(driveRow.modelData.capacityBytes)
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: menu.secondaryText
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                }
                Text {
                    width: parent.width
                    text: "Connection: " + menu.connectionText(driveRow.modelData)
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: menu.secondaryText
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                }
                Repeater {
                    model: driveRow.modelData.volumes
                    Column {
                        id: volumeDetails
                        required property var modelData
                        width: driveRow.width
                        spacing: Style.spacing.sm
                        Text {
                            width: parent.width
                            text: volumeDetails.modelData.name + ": " + (volumeDetails.modelData.filesystem || "Unknown filesystem")
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: menu.secondaryText
                            font.family: Style.font.family
                            font.pixelSize: Style.font.caption
                        }
                        Text {
                            objectName: "usbMountLocation"
                            width: parent.width
                            text: "Mounted at: " + (volumeDetails.modelData.mountPaths && volumeDetails.modelData.mountPaths.length ? volumeDetails.modelData.mountPaths.join("\n") : "Unavailable")
                            textFormat: Text.PlainText
                            wrapMode: Text.WrapAnywhere
                            color: menu.secondaryText
                            font.family: Style.font.family
                            font.pixelSize: Style.font.caption
                            Accessible.role: Accessible.StaticText
                            Accessible.name: text
                        }
                    }
                }
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: driveRow.modelData.error
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: menu.secondaryText
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
        color: menu.statusError ? Color.urgent : menu.secondaryText
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
    }
}
