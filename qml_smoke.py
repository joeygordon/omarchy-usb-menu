# Constants contain only mocked devices.
SHELL = 'import QtQuick\nimport Quickshell\nShellRoot {\n    QtObject {\n        id: fakeBar\n        property bool vertical: false\n        property bool foregroundAnimationEnabled: false\n        property int barSize: 26\n        property color barForeground: "white"\n        property color foreground: "white"\n        property color urgent: "red"\n        property string fontFamily: "monospace"\n        property string position: "top"\n        property var activePopout: null\n        function registerClickTarget(t) {}\n        function unregisterClickTarget(t) {}\n        function showTooltip(t, text) {}\n        function hideTooltip(t) {}\n        function requestPopout(t) {}\n        function releasePopout(t) {}\n    }\n    FloatingWindow { visible: true; implicitWidth: 32; implicitHeight: 26; Widget { id: widget; bar: fakeBar } }\n    Timer {\n        interval: 1500; running: true\n        onTriggered: {\n            if (widget.drives.length !== 2 || widget.implicitWidth <= 0) throw new Error("Fixture not loaded")\n            if (widget.shouldNotify({success:true}, "open")) throw new Error("Open success must be quiet")\n            if (!widget.shouldNotify({error:"failure"}, "open")) throw new Error("Open errors must notify")\n            if (!widget.shouldNotify({success:true}, "eject")) throw new Error("Eject success must notify")\n            console.info("USB_NOTIFICATION_POLICY_PASS")\n            console.info("USB_QML_MOCK_POPULATED_PASS")\n            var fixtures = widget.drives\n            widget.open()\n            widget.drives = [fixtures[1]]\n            if (!widget.opened) throw new Error("Nonfinal removal closed popup")\n            widget.status = "Device busy; close the app using this drive"\n            widget.statusError = true\n            widget.drives = [fixtures[1]]\n            if (!widget.opened || !widget.statusError) throw new Error("Busy error lost")\n            widget.status = "Safe to unplug the USB drive."\n            widget.statusError = false\n            widget.drives = []\n            if (widget.opened || widget.status !== "Safe to unplug the USB drive.") throw new Error("Final removal lifecycle failed")\n            widget.open()\n            if (widget.opened) throw new Error("Opened with no drive")\n            widget.drives = fixtures\n            widget.open()\n            widget.status = ""\n            widget.drives = []\n            if (widget.opened || widget.status !== "") throw new Error("Unplug must close without claiming safe removal")\n            widget.drives = fixtures\n            var escape = null\n            var popup = null\n            for (var i = 0; i < widget.data.length; i++) {\n                if (widget.data[i].objectName === "usbEscape") escape = widget.data[i]\n                if (widget.data[i].objectName === "usbPopup") popup = widget.data[i]\n            }\n            if (!escape || !popup) throw new Error("Dismiss handlers missing")\n            for (var n = 0; n < 3; n++) {\n                widget.open()\n                escape.activated()\n                if (widget.opened) throw new Error("Escape dismissal failed")\n                widget.open()\n                popup.close()\n                if (widget.opened) throw new Error("Outside close owner routing failed")\n            }\n            console.info("USB_POPUP_LIFECYCLE_PASS")\n            widget.drives = []\n            if (widget.visible || widget.implicitWidth !== 0 || widget.implicitHeight !== 0) throw new Error("No-drive visibility failed")\n            console.info("USB_QML_NO_DRIVE_PASS")\n            Qt.quit()\n        }\n    }\n}\n'
HELPER = "import json\nprint(json.dumps({'drives': [{'path':'/mock/a','token':'mock','name':'Mock USB','error':'','volumes':[{'path':'/mock/a1','name':'<b>$(touch NEVER)</b>'},{'path':'/mock/a2','name':'Second partition'}]}, {'path':'/mock/b','token':'','name':'Protected USB','error':'Protected test device','volumes':[{'path':'/mock/b1','name':'Third volume'}]}]}))\n"
#!/usr/bin/python
"""Headless QML smoke test. Uses a fake helper; no real storage operations."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

with tempfile.TemporaryDirectory(prefix='joey-usb-qml-') as tmp:
    root = Path(tmp)
    for name in ('Ui', 'Commons'):
        (root / name).symlink_to('/usr/share/omarchy/shell/' + name, target_is_directory=True)
    for name in ('Widget.qml', 'UsbMenu.qml'):
        shutil.copy2(Path(__file__).with_name(name), root / name)
    (root / 'shell.qml').write_text(SHELL)
    (root / 'usb_helper.py').write_text(HELPER)
    runtime = root / 'runtime'
    runtime.mkdir(mode=0o700)
    env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_CONTROLS_STYLE='Basic')
    result = subprocess.run(['quickshell', '-p', str(root / 'shell.qml'), '--no-color'], env=env, capture_output=True, text=True, timeout=8)
    output = result.stdout + result.stderr
    print(output)
    assert result.returncode == 0
    assert 'USB_POPUP_LIFECYCLE_PASS' in output
    assert 'USB_NOTIFICATION_POLICY_PASS' in output
    assert 'USB_QML_MOCK_POPULATED_PASS' in output and 'USB_QML_NO_DRIVE_PASS' in output
    assert 'WARN scene:' not in output and 'ERROR qml:' not in output
