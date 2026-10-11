#!/usr/bin/python
"""Real mouse/key delivery to a standalone mocked menu; no helper or storage actions."""
from pathlib import Path
import os, shutil, subprocess, tempfile
source=Path(__file__).parent
qml=r'''
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
    {path:"/mock/a",token:"a",error:"",name:"A long USB name <b> & $(echo ignored) that must truncate",capacityBytes:64000000000,usbSpeedMbps:5000,volumes:[{name:"Work files",spaceKey:"a",filesystem:"ext4",mountPaths:["/run/media/test/Work files"]},{name:"Second partition",filesystem:"exfat",partitionBytes:1000000000}]},
    {path:"/mock/b",token:"b",error:"",name:"Backup USB",capacityBytes:32000000000,volumes:[{name:"Archive",spaceKey:"b",filesystem:"exfat",mountPaths:["/mnt/archive"]}]}]
   spaceStats: ({a:{totalBytes:60000000000,availableBytes:24000000000,usedBytes:36000000000},b:{totalBytes:32000000000,availableBytes:8000000000,usedBytes:24000000000}})
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
    var t=named(menu,"usbDetailsToggle",[]), d=named(menu,"usbDriveDetails",[]), e=named(menu,"usbEjectAction",[]), o=named(menu,"usbOpenAction",[]), l=named(menu,"usbDriveTitle",[]), c=named(menu,"usbTitleChevron",[])
    check(t.length===2 && d.length===2,"Drive controls")
    for(var i=0;i<4;i++) {
     input.mouseClick(t[0],10,t[0].height/2)
     check(d[0].visible && !d[1].visible && menu.actions.length===0,"Name click isolation")
     input.mouseClick(t[0],10,t[0].height/2)
     check(!d[0].visible,"Repeated collapse")
    }
    t[0].forceActiveFocus()
    check(t[0].activeFocus && named(menu,"usbTitleFocus",[])[0].border.width===1,"Keyboard focus indicator")
    input.keyClick(Qt.Key_Return); check(d[0].visible,"Return expand")
    check(t[0].Accessible.checked && t[0].Accessible.description.indexOf("Expanded.")===0,"Accessible expanded state")
    input.keyClick(Qt.Key_Space); check(!d[0].visible,"Space collapse")
    input.keyClick(Qt.Key_Enter); check(d[0].visible,"Enter expand")
    check(menu.actions.length===0,"Keyboard details triggered an action")
    input.keyClick(Qt.Key_Tab); check(e[0].activeFocus,"Tab focus skips to separate Eject")
    input.keyClick(Qt.Key_Return); check(menu.actions.join(',')==='eject' && d[0].visible,"Eject keyboard isolation")
    input.mouseClick(e[0],e[0].width/2,e[0].height/2)
    check(menu.actions.join(',')==='eject,eject' && d[0].visible,"Eject click isolation")
    input.mouseClick(o[0],o[0].width/2,o[0].height/2)
    check(menu.actions.join(',')==='eject,eject,open' && d[0].visible,"Open click isolation")
    input.mouseClick(t[1],10,t[1].height/2)
    check(d[0].visible && d[1].visible,"Independent expansion")
    check(l[0].truncated && l[0].textFormat===Text.PlainText,"Long name plain truncation")
    for(var j=0;j<2;j++) {
     check(t[j].x+t[j].width<e[j].x,"Title overlaps Eject")
     check(c[j].x+c[j].width<=t[j].width+0.1,"Chevron overflow")
     check(Math.abs(t[j].y+t[j].height/2-e[j].y-e[j].height/2)<0.1,"Title Eject alignment")
    }
    menu.collapseDetails(); t[0].forceActiveFocus()
    menu.grabToImage(function(r) { r.saveToFile('/tmp/usb-v14-title-preview.png'); console.info('USB_TITLE_INPUT_AND_LAYOUT_PASS'); Qt.quit() })
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
 assert r.returncode==0 and 'USB_TITLE_INPUT_AND_LAYOUT_PASS' in output
 assert 'WARN scene:' not in output and 'ERROR qml:' not in output
