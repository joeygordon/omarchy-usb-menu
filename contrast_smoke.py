#!/usr/bin/python
"""Render mocked USB details against current and bundled theme palettes."""
import ast,json,os,subprocess,tempfile,shutil,tomllib
from pathlib import Path
source=Path(__file__).parent
module=ast.parse((source/'spacing_smoke.py').read_text())
base=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='qml' for t in n.targets))
def rgb(h):return [int(h[i:i+2],16)/255 for i in (1,3,5)]
def lum(c):return sum(w*(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4) for w,v in zip((.2126,.7152,.0722),c))
themes=[('current',Path.home()/'.local/state/omarchy/current/theme')]+[(n,Path('/usr/share/omarchy/themes')/n) for n in ('nord','flexoki-light','white')]
for name,theme in themes:
 colors=(theme/'colors.toml').read_text();palette=tomllib.loads(colors)
 shell=(theme/'shell.toml').read_text() if (theme/'shell.toml').exists() else ''
 surface=tomllib.loads(shell).get('popups',{})
 fg=rgb(surface.get('text',palette['foreground']));bg=rgb(surface.get('background',palette['background']))
 blend=[v*.75+b*.25 for v,b in zip(fg,bg)];ratio=(max(lum(blend),lum(bg))+.05)/(min(lum(blend),lum(bg))+.05)
 with tempfile.TemporaryDirectory(prefix='usb-contrast-') as tmp:
  root=Path(tmp)
  for n in ('Ui','Commons'):(root/n).symlink_to('/usr/share/omarchy/shell/'+n,target_is_directory=True)
  shutil.copy2(source/'UsbMenu.qml',root/'UsbMenu.qml')
  q=base.replace('implicitHeight: 580','implicitHeight: 650').replace('  UsbMenu {','  Rectangle { anchors.fill: parent; color: Color.popups.background }\n  UsbMenu {',1)
  start=q.index('   onTriggered: {');end=q.index('\n   }\n  }\n }\n}',start)
  q=q[:start]+'''   onTriggered: {
    Color.loadColors(COLORS); Color.loadShell(SHELL); Color.loadUserShell("")
    var labels=named(menu,"usbVolumeSpace",[]).concat(named(menu,"usbMountLocation",[]),named(menu,"usbTitleChevron",[]))
    for(var i=0;i<labels.length;i++) {
     check(labels[i].opacity===1,"Compounded item opacity")
     check(Math.abs(labels[i].color.a-.75)<.002,"Wrong secondary alpha")
     check(Math.abs(labels[i].color.r-Color.popups.text.r)<.002,"Wrong theme token")
    }
    menu.toggleDetails(menu.drives[0]); menu.toggleDetails(menu.drives[1])
    var details=named(menu,"usbDriveDetails",[]); for(var j=0;j<details.length;j++) { details[j].forceLayout(); details[j].parent.forceLayout() }; menu.forceLayout()
    console.info("USB_CONTRAST_TOKEN_PASS "+menu.secondaryText)
    Qt.callLater(function() {
     menu.grabToImage(function(r) { r.saveToFile(OUTPUT); Qt.quit() }, Qt.size(menu.width*3,menu.height*3))
    })
'''.replace('COLORS',json.dumps(colors)).replace('SHELL',json.dumps(shell)).replace('OUTPUT',json.dumps('/tmp/usb-v16-'+name+'.png'))+q[end:]
  (root/'shell.qml').write_text(q);runtime=root/'runtime';runtime.mkdir(mode=0o700)
  try: r=subprocess.run(['quickshell','-p',str(root/'shell.qml'),'--no-color'],env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_CONTROLS_STYLE='Basic'),capture_output=True,text=True,timeout=6)
  except subprocess.TimeoutExpired as e:
   print(e.stdout,e.stderr); raise
  output=r.stdout+r.stderr
  assert r.returncode==0 and 'USB_CONTRAST_TOKEN_PASS' in output and 'ERROR qml:' not in output and 'WARN scene:' not in output,output
  # Check actual rendered RGB pixels in the expanded-details area, not just source values.
  pixels=subprocess.check_output(['magick','/tmp/usb-v16-'+name+'.png','-background',surface.get('background',palette['background']),'-alpha','remove','-crop','900x285+0+510','+repage','-depth','8','rgb:-'])
  expected=[round(x*255) for x in blend]
  nearest=min(max(abs(pixels[i+j]-expected[j]) for j in range(3)) for i in range(0,len(pixels),3))
  assert nearest<=3,(name,expected,nearest)
  print(name,'effective','#'+''.join(f'{v:02x}' for v in expected),'contrast',round(ratio,3),'render delta',nearest,'PASS')
