#!/usr/bin/python
"""Exercise real QML processes with fake Open/notifications; no real device actions."""
import ast
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

source = Path(__file__).parent
module = ast.parse((source / 'qml_smoke.py').read_text())
constants = {n.targets[0].id: ast.literal_eval(n.value) for n in module.body[:2]}
shell = constants['SHELL'].replace('            Qt.quit()', '''            widget.drives = fixtures
            widget.status = ""
            widget.statusError = false
            openTests.start()''')
extra = '''
    Timer {
        id: openTests
        interval: 20; repeat: true
        property int stage: 0
        property int ticks: 0
        property var popup: null
        property var menu: null
        property real initialHeight: 0
        function startOpen(path) {
            widget.run("open", widget.drives[0], {path:path})
        }
        function checkQuiet() {
            if (widget.status !== "" || menu.implicitHeight !== initialHeight)
                throw new Error("Open footer flashed or layout changed")
        }
        onTriggered: {
            if (++ticks > 160) throw new Error("Open test timeout")
            if (stage === 0) {
                for (var i = 0; i < widget.data.length; i++)
                    if (widget.data[i].objectName === "usbPopup") popup = widget.data[i]
                menu = popup.contentItem[0].contentChildren[0]
                initialHeight = menu.implicitHeight
                startOpen("fast")
                checkQuiet()
                stage = 1
            } else if (stage === 1) {
                checkQuiet()
                if (!widget.busy) { console.info("USB_FAST_OPEN_NO_JUMP_PASS"); stage = 2 }
            } else if (stage === 2) {
                startOpen("slow")
                startOpen("duplicate")
                checkQuiet()
                stage = 3
            } else if (stage === 3) {
                checkQuiet()
                if (!widget.busy) { console.info("USB_SLOW_OPEN_NO_JUMP_PASS"); stage = 4 }
            } else if (stage === 4) {
                startOpen("error")
                checkQuiet()
                stage = 5
            } else if (stage === 5 && !widget.busy) {
                if (!widget.statusError || widget.status.indexOf("Mock Open failed") < 0)
                    throw new Error("Actual Open error was hidden")
                console.info("USB_OPEN_ERROR_VISIBLE_PASS")
                stage = 6
                ticks = 0
            } else if (stage === 6 && ticks > 8) Qt.quit()
        }
    }
'''
shell = shell.rstrip()[:-1] + extra + '}\n'
helper = '''import json, os, sys, time
args = sys.argv[1:]
request_id = args.pop().split('=', 1)[1] if args[-1].startswith('--request-id=') else None
if args[0] == 'list':
''' + '\n'.join('    ' + line for line in constants['HELPER'].splitlines()) + '''
else:
    assert args[0] == 'open', 'No ejection allowed in this test'
    with open(os.environ['USB_TEST_ACTIONS'], 'a') as log: log.write(args[-1] + chr(10))
    if args[-1] == 'slow': time.sleep(0.45)
    if args[-1] == 'error':
        print(json.dumps({'requestId':request_id,'error':'Mock Open failed'}), flush=True)
        sys.exit(1)
    print(json.dumps({'requestId':request_id,'success':True,'message':'Opened volume in file manager.'}), flush=True)
'''
with tempfile.TemporaryDirectory(prefix='usb-open-') as tmp:
    root = Path(tmp)
    for name in ('Ui', 'Commons'):
        (root/name).symlink_to('/usr/share/omarchy/shell/'+name, target_is_directory=True)
    for name in ('Widget.qml', 'UsbMenu.qml'):
        shutil.copy2(source/name, root/name)
    (root/'shell.qml').write_text(shell)
    (root/'usb_helper.py').write_text(helper)
    (root/'notify-send').write_text('#!/usr/bin/python\nimport os,sys\nwith open(os.environ["USB_TEST_NOTICES"],"a") as f: f.write(sys.argv[-1]+"\\n")\n')
    (root/'notify-send').chmod(0o700)
    runtime=root/'runtime'; runtime.mkdir(mode=0o700)
    env=dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'], USB_TEST_ACTIONS=str(root/'actions'), USB_TEST_NOTICES=str(root/'notices'), XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_CONTROLS_STYLE='Basic')
    try:
        result=subprocess.run(['quickshell','-p',str(root/'shell.qml'),'--no-color'],env=env,capture_output=True,text=True,timeout=8)
    except subprocess.TimeoutExpired as exc:
        print(exc.stdout, exc.stderr)
        raise
    output=result.stdout+result.stderr
    print(output)
    assert result.returncode == 0
    for marker in ('USB_FAST_OPEN_NO_JUMP_PASS','USB_SLOW_OPEN_NO_JUMP_PASS','USB_OPEN_ERROR_VISIBLE_PASS'):
        assert marker in output
    assert 'WARN scene:' not in output
    print('Recorded mocked actions:', repr((root/'actions').read_text()))
    assert (root/'actions').read_text().splitlines() == ['fast','slow','error'], 'Duplicate Open was not blocked'
    assert (root/'notices').read_text().splitlines() == ['Mock USB — &lt;b&gt;$(touch NEVER)&lt;/b&gt;: Mock Open failed'], 'Unexpected success notification'
    print('USB_OPEN_DUPLICATE_AND_NOTIFICATION_PASS')
