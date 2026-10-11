import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Ui as Ui
import qs.Commons

Ui.BarWidget {
    id: root
    property var drives: []
    property string status: ""
    property bool statusError: false
    property string activeVerb: ""
    property var operation: null
    property int requestSequence: 0
    property int discoveryEpoch: 0
    property bool scanPending: false
    signal notificationRequested(string message)
    onNotificationRequested: message => {
        notify.command = ["notify-send", "USB Storage", notificationText(message)]
        notify.running = true
    }
    function notificationText(message) {
        // Notification bodies are StyledText; labels and errors must remain data.
        return String(message).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    }
    function targetPresent() {
        return operation && drives.some(d => d.path === operation.path && d.token === operation.token)
    }
    function operationLabel(drive) {
        var label = drive.displayName || drive.name
        if (drive.volumes && drive.volumes.length) label += " — " + drive.volumes[0].name
        return label
    }
    function failOperation(message) {
        if (!operation || operation.complete) return
        operation = Object.assign({}, operation, {complete:true})
        statusError = true
        var failure = operation.label + ": " + message
        status = targetPresent() ? failure : ""
        // Avoid duplicating an error already shown in the open dropdown.
        if (!opened || !targetPresent()) notificationRequested(failure)
    }
    function reconcileOperation() {
        if (!operation || operation.complete || !operation.successReceived || !operation.discoverySeen) return
        var replaced = drives.some(d => (d.path === operation.path || (operation.device && d.device === operation.device)) && d.token !== operation.token)
        if (replaced) {
            failOperation("the drive connection changed. Check it again before unplugging.")
            return
        }
        if (targetPresent()) return
        var completionLabel = operation.label
        if (drives.some(d => d.path !== operation.path && operationLabel(d) === operation.label))
            completionLabel += " (" + (operation.device || operation.path.split("/").pop()) + ")"
        operation = Object.assign({}, operation, {complete:true})
        status = ""
        statusError = false
        // The xdg-popup can cover notifications; dismiss only after confirmed removal.
        close()
        notificationRequested(completionLabel + ": safe to unplug.")
    }
    function acceptDiscovery(data, epoch) {
        // A scan started before this operation must never restore an old row.
        if (epoch !== discoveryEpoch) return
        if (data.drives !== undefined) {
            drives = data.drives
            if (operation && !operation.complete && operation.verb === "eject") {
                operation = Object.assign({}, operation, {discoverySeen:true})
                reconcileOperation()
            }
        }
        if (data.error) console.warn("joey.usb-storage discovery: " + data.error + (data.details ? " " + JSON.stringify(data.details) : ""))
    }
    function checkReconciliationDeadline(now) {
        if (operation && !operation.complete && operation.successReceived && now >= operation.deadline)
            failOperation("couldn't confirm removal in the device list. Leave it connected and try again.")
    }
    function handleResult(result) {
        if (!operation || result.requestId !== operation.id || operation.complete) return
        if (result.details) console.warn("USB operation details: " + JSON.stringify({target:operation.label, requestId:operation.id, code:result.errorCode, details:result.details}))
        if (result.error || result.success) {
            action.receivedResult = true
            if (result.error) {
                failOperation(result.error)
            } else if (operation.verb === "eject") {
                if (!operation.successReceived) {
                    operation = Object.assign({}, operation, {successReceived:true, deadline:Date.now()+8000})
                    statusError = false
                    status = targetPresent() ? operation.label + ": confirming removal…" : ""
                }
                reconcileOperation()
                refresh()
            } else {
                operation = Object.assign({}, operation, {complete:true})
                status = ""
                statusError = false
            }
        } else if (result.progress && !operation.successReceived) {
            statusError = false
            status = targetPresent() ? operation.label + ": " + result.progress : ""
        }
    }
    property bool actionPending: false
    readonly property bool busy: actionPending || action.running || (operation !== null && operation.verb === "eject" && !operation.complete)
    property bool opened: false
    property string helper: Qt.resolvedUrl("usb_helper.py").toString().replace(/^file:\/\//, "")
    implicitWidth: drives.length ? button.implicitWidth : 0
    implicitHeight: drives.length ? button.implicitHeight : 0
    visible: drives.length > 0
    // A popup is a separate window; hiding its bar Item does not dismiss it.
    onDrivesChanged: {
        if (drives.length === 0) close()
        if (operation && !targetPresent()) { status = ""; statusError = false }
    }
    function open() { if (drives.length > 0) opened = true }
    function close() { opened = false }
    Shortcut {
        objectName: "usbEscape"
        sequence: "Escape"
        context: Qt.ApplicationShortcut
        enabled: root.opened
        onActivated: root.close()
    }
    function refresh() {
        if (!scan.running && !scanPending) {
            scanPending = true
            scan.epoch = discoveryEpoch
            scan.running = true
        }
    }
    function run(verb, drive, volume) {
        if (busy) return
        actionPending = true
        activeVerb = verb
        discoveryEpoch++
        operation = {id:Date.now().toString() + "-" + (++requestSequence), verb:verb,
            path:drive.path, token:drive.token, device:drive.device || "", label:operationLabel(drive), complete:false, successReceived:false, discoverySeen:false, deadline:0}
        statusError = false
        status = verb === "eject" ? operation.label + ": preparing safe removal…" : ""
        action.command = ["/usr/bin/python", helper, verb, drive.path, drive.token]
            .concat(volume ? [volume.path] : []).concat(["--request-id=" + operation.id])
        action.running = true
    }
    function shouldNotify(result, verb) {
        return !!result.error || (!!result.success && verb !== "open")
    }
    Component.onCompleted: {
        Qt.callLater(function() { console.info("joey.usb-storage loaded UI=" + contents.uiRevision + " cardWidth=" + popup.contentWidth) })
        refresh()
    }
    // Read-only runtime verification; never opens or removes storage.
    IpcHandler {
        target: "joey.usb-storage"
        function diagnostics(): string {
            return JSON.stringify({uiRevision: contents.uiRevision,
                cardWidth: popup.contentWidth, icon: button.text,
                drives: root.drives.length, popupOpen: root.opened, busy: root.busy, reconciling:!!(root.operation && root.operation.successReceived && !root.operation.complete)})
        }
    }
    // A failed process launch must not leave controls permanently disabled.
    Timer {
        interval: 5000
        running: root.actionPending
        onTriggered: {
            if (!action.running) {
                root.actionPending = false
                root.failOperation(root.activeVerb === "open"
                    ? "couldn't open this volume. Try again."
                    : "couldn't start safe removal. Leave the drive connected and try again.")
            }
        }
    }
    Timer { interval: root.operation && !root.operation.complete && root.operation.verb === "eject" ? 500 : 4000; running: true; repeat: true; onTriggered: root.refresh() }
    Timer { interval: 200; running: root.operation !== null && root.operation.successReceived === true && !root.operation.complete; repeat: true; onTriggered: root.checkReconciliationDeadline(Date.now()) }
    Process {
        id: scan
        property int epoch: 0
        onStarted: root.scanPending = false
        onExited: root.scanPending = false
        command: ["/usr/bin/python", root.helper, "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var data = JSON.parse(text)
                    root.acceptDiscovery(data, scan.epoch)
                } catch (e) { console.warn("joey.usb-storage discovery failed: " + e) }
            }
        }
    }
    Process {
        id: action
        property bool receivedResult: false
        onStarted: { receivedResult = false; root.actionPending = false }
        stdout: SplitParser {
            onRead: data => {
                try {
                    var result = JSON.parse(data)
                    root.handleResult(result)
                } catch (e) { root.statusError = true; root.status = "Invalid helper response; removal is not confirmed." }
            }
        }
        onExited: (exitCode, exitStatus) => {
            root.actionPending = false
            if (!receivedResult)
                root.failOperation("the action stopped. Removal is not confirmed.")
            root.refresh()
        }
    }
    Process { id: notify }
    Ui.BarIconButton {
        id: button
        bar: root.bar
        text: ""
        active: root.opened
        activeColor: Color.accent
        Accessible.role: Accessible.Button
        Accessible.name: "USB storage"
        Accessible.description: "Show mounted USB drives"
        onPressed: mouseButton => {
            if (mouseButton === Qt.LeftButton) { if (root.opened) root.close(); else root.open(); root.refresh() }
        }
    }
    Ui.PopupCard {
        id: popup
        objectName: "usbPopup"
        anchorItem: button
        bar: root.bar
        owner: root
        open: root.opened
        contentWidth: fittedContentWidth(Style.space(320))
        contentHeight: fittedContentHeight(contents.implicitHeight, Style.space(500))
        ScrollView {
            id: scroll
            anchors.fill: parent
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            UsbMenu {
                id: contents
                width: scroll.availableWidth
                drives: root.drives
                busy: root.busy
                ejectingPath: root.operation && root.operation.verb === "eject" && !root.operation.complete ? root.operation.path : ""
                ejectingToken: root.operation ? root.operation.token : ""
                status: root.status
                statusError: root.statusError
                onActionRequested: (verb, drive, volume) => root.run(verb, drive, volume)
            }
        }
    }
}
