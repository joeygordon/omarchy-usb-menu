#!/usr/bin/python
"""Exercise compact details and a slow stats worker with fake storage only."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

source = Path(__file__).parent
module = ast.parse((source / 'qml_smoke.py').read_text())
base = ast.literal_eval(module.body[0].value)
shell = 'import qs.Commons as Commons\n' + base.split('    Timer {', 1)[0] + r'''
    Timer {
        interval: 50; running: true; repeat: true
        property int ticks: 0
        property int stage: 0
        property double started: 0
        property var menu: null
        function named(item, name, found) {
            if (item.objectName === name) found.push(item)
            if (item.children) for (var i=0; i<item.children.length; i++) named(item.children[i],name,found)
            return found
        }
        onTriggered: {
            if (++ticks > 160) throw new Error("Details test timed out")
            if (stage === 0 && widget.drives.length === 2) {
                widget.open()
                started = Date.now()
                var popup = null
                for (var i=0; i<widget.data.length; i++) if (widget.data[i].objectName === "usbPopup") popup=widget.data[i]
                menu = popup.contentItem[0].contentChildren[0]
                if (popup.contentWidth !== 320) throw new Error("Compact card width changed")
                if (menu.bytesText(32000000000) !== "32.0 GB" || menu.bytesText(undefined) !== "Unavailable") throw new Error("Capacity formatting")
                if (menu.connectionText({usbSpeedMbps:5000}) !== "USB · 5 Gbps" || menu.connectionText({}) !== "USB · speed unavailable") throw new Error("Connection fallback")
                widget.spaceStats = {a:{totalBytes:30000000000,availableBytes:12000000000,usedBytes:18000000000},b:{totalBytes:1000000000,availableBytes:0,usedBytes:1000000000}}
                if (menu.volumeSpace(widget.drives[0].volumes[0]) !== "12.0 GB free · 30.0 GB total") throw new Error("Volume space semantics")
                if (menu.volumeSpace(widget.drives[0].volumes[1]) !== "0 B free · 1.0 GB total") throw new Error("Full volume formatting")
                if (menu.volumeSpace({partitionBytes:32000000000}) !== "32.0 GB partition · free unavailable") throw new Error("Partition mislabeled as filesystem")
                if (menu.volumeSpace({}) !== "Space unavailable") throw new Error("Missing metadata")
                var tracks=named(menu,"usbUsageTrack",[])
                var fills=named(menu,"usbUsageFill",[])
                if (tracks.length!==3 || tracks[0].fraction!==0.6 || tracks[1].fraction!==1 || tracks[2].visible) throw new Error("Multi-volume usage bars")
                if (menu.usageDescription(widget.drives[0].volumes[0]).indexOf("60% used; 18.0 GB used")!==0) throw new Error("Missing textual usage equivalent")
                if (Math.abs(fills[0].width - tracks[0].width*0.6)>0.01 || Math.abs(fills[1].width-tracks[1].width)>0.01) throw new Error("Usage bar proportions")
                var themeAccent=Commons.Color.accent
                Commons.Color.accent="#5070a0"
                if (Math.abs(fills[0].color.r-80/255)>0.01 || Math.abs(fills[0].color.a-0.48)>0.01 || Math.abs(tracks[0].color.a-0.16)>0.01) throw new Error("Muted theme color")
                Commons.Color.accent=themeAccent
                var savedStats=widget.spaceStats
                widget.spaceStats={a:{totalBytes:100,availableBytes:100,usedBytes:0}}
                if (menu.usageFraction(widget.drives[0].volumes[0])!==0 || fills[0].width!==0 || !tracks[0].visible) throw new Error("Empty volume falsely filled")
                var bad=[{totalBytes:0,availableBytes:0,usedBytes:0},{totalBytes:100,availableBytes:50,usedBytes:70},{totalBytes:100,availableBytes:50,usedBytes:null},{totalBytes:100,availableBytes:50,usedBytes:-1},{totalBytes:Infinity,availableBytes:0,usedBytes:0}]
                for (var k=0;k<bad.length;k++) {
                    widget.spaceStats={a:bad[k]}
                    if (menu.usageFraction(widget.drives[0].volumes[0])!==-1 || tracks[0].visible || menu.usageDescription(widget.drives[0].volumes[0])!=="Usage unavailable") throw new Error("Invalid statistics made a misleading bar")
                }
                widget.spaceStats=savedStats
                var locations=named(menu,"usbMountLocation",[])
                if (locations.length!==3 || locations[0].text!=="Mounted at: "+widget.drives[0].volumes[0].mountPaths.join("\n") || locations[0].text.length<200 || locations[0].textFormat!==Text.PlainText || locations[2].text!=="Mounted at: Unavailable") throw new Error("Mount paths truncated, interpreted, or missing fallback")
                console.info("USB_USAGE_AND_MOUNT_DETAILS_PASS")
                var toggles=named(menu,"usbDetailsToggle",[])
                var details=named(menu,"usbDriveDetails",[])
                var rows=named(menu,"usbVolumeSpace",[])
                if (toggles.length!==2 || rows.length!==3 || details.some(d=>d.visible)) throw new Error("Not collapsed by default or wrong partition rows")
                for (var j=0; j<4; j++) {
                    toggles[0].clicked()
                    if (!details[0].visible || details[1].visible) throw new Error("Wrong drive expanded")
                    toggles[0].clicked()
                    if (details[0].visible) throw new Error("Collapse failed")
                }
                toggles[0].clicked()
                widget.drives=JSON.parse(JSON.stringify(widget.drives))
                if (!menu.expanded[menu.detailKey(widget.drives[0])]) throw new Error("Polling lost expansion")
                widget.close(); widget.open()
                if (Object.keys(menu.expanded).length) throw new Error("Reopen not collapsed")
                widget.spaceStats=({})
                widget.acceptSpace({spaceKey:"not-current",totalBytes:10,availableBytes:5},Date.now())
                if (Object.keys(widget.spaceStats).length) throw new Error("Stale mount accepted")
                console.info("USB_DETAILS_FORMAT_AND_EXPANSION_PASS")
                stage=1
            } else if (stage===1 && Date.now()-started>2300) {
                if (widget.busy || !widget.spaceExpired) throw new Error("Slow metadata blocked UI or missed deadline")
                widget.acceptSpace({spaceKey:"a",totalBytes:10,availableBytes:5},Date.now())
                if (Object.keys(widget.spaceStats).length) throw new Error("Late stats accepted")
                for (var n=0; n<5; n++) widget.refreshSpace()
                if (widget.busy) throw new Error("Metadata made actions busy")
                console.info("USB_SPACE_DEADLINE_PASS")
                stage=2
            } else if (stage===2 && Date.now()-started>3500) {
                if (Object.keys(widget.spaceStats).length) throw new Error("Expired worker reply revived statistics")
                console.info("USB_SPACE_SINGLE_WORKER_PASS")
                widget.close()
                Qt.quit()
            }
        }
    }
}
'''
drives = [
    dict(path='/mock/a', token='a', name='Long USB '*20, error='', capacityBytes=64000000000, usbSpeedMbps=5000,
         volumes=[dict(path='/mock/a1', name='<b>Long partition & data</b>'*20, spaceKey='a', filesystem='ext4', filesystemBytes=30000000000, mountPaths=['/run/media/testuser/'+ '<b>long & path</b>'*25, '/mnt/also-here']),
                  dict(path='/mock/a2', name='Second', spaceKey='b', filesystem='exfat', partitionBytes=1000000000, mountPaths=['/mnt/second'])]),
    dict(path='/mock/b', token='b', name='Unknown USB', error='', volumes=[dict(path='/mock/b1', name='Missing metadata')])]
helper = '''import json, os, sys, time
if sys.argv[1] == 'list':
    print(%r)
elif sys.argv[1] == 'space':
    with open(os.environ['USB_SPACE_CALLS'],'a') as f: f.write('space\\n')
    time.sleep(3)
    print(json.dumps(dict(spaceKey='a',totalBytes=30000000000,availableBytes=12000000000)),flush=True)
else:
    raise RuntimeError('Storage actions forbidden in details test')
''' % json.dumps({'drives': drives})
with tempfile.TemporaryDirectory(prefix='usb-details-') as tmp:
    root = Path(tmp)
    for name in ('Ui','Commons'): (root/name).symlink_to('/usr/share/omarchy/shell/'+name,target_is_directory=True)
    for name in ('Widget.qml','UsbMenu.qml'): shutil.copy2(source/name,root/name)
    (root/'shell.qml').write_text(shell)
    (root/'usb_helper.py').write_text(helper)
    runtime=root/'runtime'; runtime.mkdir(mode=0o700)
    env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),USB_SPACE_CALLS=str(root/'calls'),QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_CONTROLS_STYLE='Basic')
    result=subprocess.run(['quickshell','-p',str(root/'shell.qml'),'--no-color'],env=env,capture_output=True,text=True,timeout=10)
    output=result.stdout+result.stderr
    print(output)
    assert result.returncode==0
    for marker in ('USB_DETAILS_FORMAT_AND_EXPANSION_PASS','USB_SPACE_DEADLINE_PASS','USB_SPACE_SINGLE_WORKER_PASS','USB_USAGE_AND_MOUNT_DETAILS_PASS'): assert marker in output
    assert 'WARN scene:' not in output and 'ERROR qml:' not in output
    assert (root/'calls').read_text().splitlines()==['space'], 'Concurrent slow metadata workers'
