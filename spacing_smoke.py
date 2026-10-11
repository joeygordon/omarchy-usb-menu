#!/usr/bin/python
"""Check expanded-details spacing with mocked volumes and long mount paths."""
from pathlib import Path
import os, shutil, subprocess, tempfile
source=Path(__file__).parent
qml = r'''
import QtQuick
import Quickshell
import QtTest
import qs.Commons
ShellRoot {
 FloatingWindow {
  id: win; visible: true; implicitWidth: 352; implicitHeight: 580; color: Color.background
  UsbMenu {
   id: menu; x:16; y:16; width:320
   property var actions: []
   onActionRequested: (verb,drive,volume) => { actions.push(verb) }
   drives: [
    {path:"/mock/a",token:"a",error:"",name:"A long USB name <b> & $(echo ignored) that must truncate",capacityBytes:64000000000,usbSpeedMbps:5000,volumes:[{name:"Work files",spaceKey:"a",filesystem:"ext4",mountPaths:["/run/media/test/Work files"]},{name:"Second partition",spaceKey:"second",filesystem:"exfat",partitionBytes:1000000000}]},
    {path:"/mock/b",token:"b",error:"",name:"Backup USB",capacityBytes:32000000000,volumes:[{name:"Archive",spaceKey:"b",filesystem:"exfat",mountPaths:["/run/media/test/"+"long-folder-name/".repeat(12)]}]}]
   spaceStats: ({second:{totalBytes:1000000000,availableBytes:400000000,usedBytes:600000000},a:{totalBytes:60000000000,availableBytes:24000000000,usedBytes:36000000000},b:{totalBytes:32000000000,availableBytes:8000000000,usedBytes:24000000000}})
  }
  TestCase { id: input; when: false }
  Timer {
   interval:500; running:true
   function named(item,name,out) {
    if(item.objectName===name) out.push(item)
    if(item.children) for(var i=0;i<item.children.length;i++) named(item.children[i],name,out)
    return out
   }
   function check(v,s) { if(!v) throw new Error(s) }
   onTriggered: {
    var d=named(menu,"usbDriveDetails",[]), tracks=named(menu,"usbUsageTrack",[])
    check(named(menu,"usbMountLocation",[])[2].text.length>200,"Long path fixture"); var collapsed=menu.height
    menu.drives[1].volumes[0].mountPaths=["/run/media/test/"+"long-folder-name/".repeat(12)]
    menu.toggleDetails(menu.drives[0]); menu.toggleDetails(menu.drives[1])
    for(var i=0;i<d.length;i++) { d[i].forceLayout(); d[i].parent.forceLayout() }
    menu.forceLayout()
    for(var j=0;j<d.length;j++) {
     var track=tracks[j===0?1:2], bottom=track.mapToItem(menu,0,track.height).y
     var top=d[j].children[0].mapToItem(menu,0,0).y
     check(Math.abs(top-bottom-Style.spacing.sm-Style.spacing.lg)<0.1,"Expanded gap wrong")
    }
    check(menu.width===320 && menu.height>collapsed,"Expanded geometry")
    menu.grabToImage(function(r) {
     r.saveToFile('/tmp/usb-v15-expanded.png')
     menu.collapseDetails()
     for(var k=0;k<d.length;k++) d[k].parent.forceLayout()
     menu.forceLayout()
     check(menu.height===collapsed,"Collapsed height changed")
     menu.grabToImage(function(c) { c.saveToFile('/tmp/usb-v15-collapsed.png'); console.info('USB_DETAILS_SPACING_PASS'); Qt.quit() })
    })

   }
  }
 }
}
'''
with tempfile.TemporaryDirectory(prefix='usb-title-') as tmp:
 root=Path(tmp)
 for name in ('Ui','Commons'): (root/name).symlink_to('/usr/share/omarchy/shell/'+name,target_is_directory=True)
 shutil.copy2(source/'UsbMenu.qml',root/'UsbMenu.qml')
 (root/'shell.qml').write_text(qml)
 runtime=root/'runtime'; runtime.mkdir(mode=0o700)
 env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_CONTROLS_STYLE='Basic')
 r=subprocess.run(['quickshell','-p',str(root/'shell.qml'),'--no-color'],env=env,capture_output=True,text=True,timeout=8)
 output=r.stdout+r.stderr; print(output)
 assert r.returncode==0 and 'USB_DETAILS_SPACING_PASS' in output
 assert 'WARN scene:' not in output and 'ERROR qml:' not in output
