# Omarchy USB Menu

A small USB storage menu for the Omarchy bar. See mounted USB drives, open a
volume in your file manager, or safely eject a physical drive without opening a
separate disk-management app.

The bar icon appears only when USB storage has mounted volumes. The menu uses
Omarchy's theme, typography, and controls. Its count is the number of drives with
mounted volumes, not the number of partitions or files.

Display name: **USB Storage** · Plugin ID: **`joey.usb-storage`**

## Requirements

**Experimental personal plugin.** Tested on **Omarchy 4.0.4-1** with its Quickshell shell and official manifest-based
bar plugin API. Other versions have not been verified.

The plugin uses existing system components:

- `/usr/bin/python` and PyGObject/Gio (`python-gobject` on Arch)
- UDisks2 (`udisks2`) and normal desktop authorization
- `xdg-open` (`xdg-utils`) for the explicit Open action
- `notify-send` (`libnotify`) for completion and otherwise hidden errors
- Omarchy's bundled QML UI components and Nerd Font icons

It does not install packages or change system services, security settings, or
Omarchy's packaged source files. Plugins run as your user inside the desktop
shell; review the code before enabling one.

## Install

This repository is private; cloning requires access. From your normal desktop
session:

```sh
git clone https://github.com/joeygordon/omarchy-usb-menu.git
cd omarchy-usb-menu
/usr/bin/python install.py
```

The installer validates the manifest, backs up `~/.config/omarchy/shell.json` to
`~/.local/state/omarchy-usb-storage/<UTC timestamp>/shell.json`, and copies four
runtime files into `~/.config/omarchy/plugins/joey.usb-storage/`. It waits for plugin
discovery, then uses `omarchy plugin enable joey.usb-storage`.

The widget is added to the bar's **right section**. This does not change which
screen edge holds the bar. Existing layout and settings are preserved. If the
plugin directory already exists, the installer backs it up and refuses to
overwrite it.

For fresh installations, Omarchy's standard Git-based installer is another option:

```sh
omarchy plugin add https://github.com/joeygordon/omarchy-usb-menu.git --enable --yes
```

Use one installation method. The project copy and installed copy are separate
when using `install.py`; editing the project alone does not update the desktop.

## Use

- Click the USB icon to open the menu. Escape or an outside click dismisses it.
- **Open** opens that mounted volume. There is no progress footer or success
  notification; launch errors remain visible. The launcher has a ten-second
  deadline; if it does not finish, an uncertainty message appears. The file
  manager is not killed and may still open. A successful launcher exit confirms
  acceptance, not that a particular window is visible. Open does not mount an
  unmounted drive.
- **Eject** applies to the entire physical drive, including all its partitions.
  Close files and terminal working directories using the drive first.
- The target row shows **Ejecting…** while removal and list confirmation are
  pending. Duplicate actions are blocked.
- Success requires a matching successful helper response and a fresh discovery
  result confirming the target row is gone. The popup then closes and a desktop
  notification names the drive that is safe to unplug. Other drives are not
  covered by that confirmation; reopen the menu to manage them.

Errors are shown inline when the menu can display the target. Otherwise, one
named error notification provides feedback. There is no duplicate toast for an
inline error. A disappearing icon by itself is **not** a safe-removal confirmation.

Names are captured when an action starts; matching model names receive a device
identifier for distinction. Stale and duplicate helper replies are ignored.
Discovery runs every four seconds normally and every half-second during eject.
After helper success, list reconciliation has an eight-second deadline; timeout
reports uncertainty rather than claiming the drive is safe.

## Disable, remove, and update

```sh
omarchy plugin disable joey.usb-storage
omarchy plugin remove joey.usb-storage --yes
```

Disabling removes this widget from the layout and stops its helper polling.
Removing deletes its installed directory. Neither removes files from your drives.
Keep a project clone if you want to reinstall.

For an installation made with `install.py`, pull reviewed changes in your source
clone, then disable/remove the installed copy and run the installer again. For an
installation made with `omarchy plugin add`, use the supported
`omarchy plugin update joey.usb-storage` workflow and review its diff.

**QML reload caveat:** on the tested Omarchy version, plugin reload messages did
not reliably mean changed QML had reached the live widget. After installing an
update, close desktop panels and, when no USB action is running, use:

```sh
omarchy restart shell
omarchy-shell shell ping
omarchy-shell joey.usb-storage diagnostics
```

This source revision reports `native-compact-v11-release-fixes`; the initial
published version reports `native-compact-v10-feedback`. Diagnostics
are read-only and include the live UI revision, mounted-drive count, popup state,
and operation/reconciliation state. Restarting the shell briefly reloads desktop
shell UI; it is not required after each drive operation.

Prefer disabling this plugin over restoring an entire old `shell.json`. A full
snapshot also restores unrelated layout changes made since the backup. If you
need to restore one, copy the chosen backup over `~/.config/omarchy/shell.json`
and run `omarchy-shell shell reloadConfig`.

## Safety and limitations

The helper uses UDisks2 D-Bus properties and methods, not human-formatted command
output. Removal requires a USB drive that supports power-off, non-system block
devices, ordinary filesystems, and mounted paths beneath `/run/media/`, `/media/`,
or `/mnt/`.

It refuses shared-enclosure siblings, active storage mappings/holders, encrypted,
swap, RAID, protected/system storage, and unsupported power-off. Such mounted
volumes may still be displayed and opened. There is no force-unmount or
unmount-only fallback, formatting, file deletion, privilege escalation, or
internal-disk removal operation.

Drive identity includes detection time, block topology, and Linux disk sequence
numbers. The helper revalidates identity before every unmount and power-off.
A per-user lock blocks concurrent removals. All unmounts must succeed before
power-off, and the helper checks that the drive and its block objects disappear
before reporting success. Busy, permission, identity, remount, or confirmation
failures stop the sequence.

If a later partition fails, earlier partitions may remain unmounted. If all
partitions unmount but power-off fails, the icon can disappear; read the error
and use the system disk utility rather than assuming success. No software can
eliminate hardware failure or every race between validation and an operation.
Keep backups and wait for the named successful confirmation before unplugging.

Labels are plain text in the menu and escaped for notification markup. Open
passes a file URI in an argument array; no labels,
mount paths, or identifiers are interpolated into shell commands. Errors use
exact structured D-Bus names, with bounded technical details kept out of normal
UI. Inspect details when needed:

```sh
quickshell log -p /usr/share/omarchy/shell -t 100
/usr/bin/python usb_helper.py list
```

The second command is read-only and includes details for discovery refusals.
The menu is an Omarchy popup; unrelated notifications can be covered while it is
open. Successful eject closes it before notifying. No global notification
settings are changed.

## Tests

Run these from the project directory on an Omarchy system:

```sh
/usr/bin/python -m unittest -v
/usr/bin/python qml_smoke.py
/usr/bin/python open_smoke.py
/usr/bin/python target_smoke.py
omarchy plugin validate .
```

The 35 Python tests cover discovery, multiple devices/partitions, malicious names,
identity changes, protected storage, busy/authorization errors, removal ordering,
request IDs, launcher exit/timeout failures, and error mapping. Removal tests
also verify that another drive remains unchanged, later-partition and power-off
failures stop safely, and a newly appearing sibling blocks power-off. QML suites
use fake helpers and notification
commands to check empty/populated UI, dismissal routing, quiet fast/slow Open,
duplicate clicks, target-specific feedback, delayed discovery, both result/list
orderings, stale replies, timeout, and final/nonfinal removal.

Tests never open a real volume or eject a real drive. Offscreen Qt may warn about
unavailable Wayland focus grabs or masks; it cannot verify physical hardware,
actual pointer/keyboard delivery, or every multi-monitor configuration. Those
remain manual tests. The plugin has been exercised interactively, but that does
not establish compatibility with every USB device or enclosure.

## Files

- `manifest.json` — official Omarchy plugin declaration
- `Widget.qml` — bar integration, lifecycle, processes, and reconciliation
- `UsbMenu.qml` — themed menu presentation
- `usb_helper.py` — UDisks2 discovery, identity validation, and removal
- `install.py` — local installer with config backup
- `test_usb_helper.py`, `qml_smoke.py`, `open_smoke.py`, `target_smoke.py` — mocked tests

API references: [Omarchy shell](https://github.com/omacom/omarchy/blob/v4.0.4/shell/README.md)
and [bar plugins](https://github.com/omacom/omarchy/blob/v4.0.4/shell/plugins/bar/README.md).

## License

[MIT](LICENSE), copyright 2026 Joey Gordon. Omarchy, Quickshell, and other
system dependencies retain their own licenses. This is an independent plugin,
not an official Omarchy release.
