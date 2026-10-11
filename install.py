#!/usr/bin/python
"""Install personal files, back up config, then use supported shell IPC."""
from datetime import datetime, timezone
from pathlib import Path
import shutil
import json
import time
import subprocess

source = Path(__file__).resolve().parent
home = Path.home()
target = home / '.config/omarchy/plugins/joey.usb-storage'
config = home / '.config/omarchy/shell.json'
backup = home / '.local/state/omarchy-usb-storage' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
subprocess.run(['omarchy', 'plugin', 'validate', str(source)], check=True)
backup.mkdir(parents=True)
if config.exists():
    shutil.copy2(config, backup / 'shell.json')
if target.exists():
    shutil.copytree(target, backup / 'joey.usb-storage')
    raise SystemExit(f'Existing plugin preserved at {backup}; disable and remove it before reinstalling.')
target.mkdir(parents=True)
for name in ('manifest.json', 'Widget.qml', 'UsbMenu.qml', 'usb_helper.py'):
    shutil.copy2(source / name, target / name)
subprocess.run(['omarchy-shell', 'shell', 'rescanPlugins'], check=True)
# Discovery is asynchronous; do not race enable against the rescan process.
for attempt in range(40):
    catalog = json.loads(subprocess.check_output(['omarchy', 'plugin', 'list', '--json']))
    if any(p.get('id') == 'joey.usb-storage' for p in catalog):
        break
    time.sleep(0.25)
else:
    raise SystemExit('Plugin discovery did not finish; files and backup retained, not enabled.')
subprocess.run(['omarchy', 'plugin', 'enable', 'joey.usb-storage'], check=True)
print(f'Installed: {target}\nBackup: {backup}')
