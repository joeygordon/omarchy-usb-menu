# Omarchy USB Menu

A small menu for checking and ejecting USB drives from the Omarchy bar, without
opening your file manager. If you want to browse a volume, there's an **Open**
button too.

The USB icon appears when a USB drive has mounted volumes and disappears when
there aren't any. The menu follows your Omarchy theme and handles multiple drives
and partitions. Each volume has a quiet free-space/capacity line and a thin usage
bar. Click a drive name to see filesystem types, full mount locations, drive
capacity, and USB connection speed. The number in the header counts drives,
not partitions.

Still experimental. Tested on **Omarchy 4.0.4-1** with the Quickshell shell.
Other versions haven't been checked, and hardware coverage is still limited.

## Requirements

This uses components already included with standard Omarchy. It's tested on
**Omarchy 4.0.4**—no extra Python packages, pip installs, or virtual environment
needed.

<details>
<summary>Technical dependencies for customized installs</summary>

If you've trimmed or replaced parts of Omarchy, the plugin uses its Quickshell
shell, built-in controls, and Nerd Font icons, plus these system packages:

- Python at `/usr/bin/python` and `python-gobject` for Gio
- `udisks2` for drive information and removal
- `xdg-utils` for opening volumes in your file manager
- `libnotify` for desktop notifications

The installer checks the plugin and sets it up; it doesn't install missing
packages. On a customized system, those need to be available first.

</details>

Like other Omarchy plugins, it runs as your user inside the shell, so review the
code before enabling it.

## Install

The repository is currently private, so you'll need access to clone it. Run this
from your normal desktop session:

```sh
omarchy plugin add https://github.com/joeygordon/omarchy-usb-menu.git --enable
```

It appears as **USB Storage**, with plugin ID `joey.usb-storage`. It goes in the
bar's right section without changing which edge of the screen your bar uses.

### Install from a local clone

If you'd rather use the included installer:

```sh
git clone https://github.com/joeygordon/omarchy-usb-menu.git
cd omarchy-usb-menu
/usr/bin/python install.py
```

This backs up `~/.config/omarchy/shell.json` under
`~/.local/state/omarchy-usb-storage/<UTC timestamp>/`, copies the plugin into
`~/.config/omarchy/plugins/joey.usb-storage/`, and enables it. If an installed copy
already exists, it backs that up and stops instead of overwriting it.

Choose one install method. With the local installer, editing your clone doesn't
update the installed copy.

## Using it

Click the USB icon to see your mounted volumes. Click outside the menu or press
Escape to close it.

- **Drive name** expands or collapses details. The small chevron shows the state;
  you can also focus the name and press Enter or Space. Each drive expands
  independently, and closing the menu collapses the details.
- **Open** opens a mounted volume in your file manager. It stays quiet on success
  and shows an error if the launcher fails. It doesn't mount unmounted volumes.
- **Eject** removes the whole physical drive, including all its partitions. Close
  any files or terminal windows using the drive first.

Wait for the notification naming the drive that's safe to unplug. The menu closes
before showing it. **A disappearing icon alone doesn't mean removal succeeded.**
Errors appear in the menu, or in a notification if the menu can't show them.

Space figures are per mounted volume, not the whole drive. Available space is
what your user can use, excluding reserved space. The bar shows actual used space;
reserved-but-unused space is not counted as used. Its accessible text gives the
used amount and percentage. Unknown or invalid usage hides the bar rather than
showing a misleading empty or full drive. Sizes use decimal units. When
filesystem figures aren't available, the line says so; a partition size is labeled
as a partition size. Connection speed is the negotiated USB link rate, not a
measurement of file-transfer speed.

Secondary text uses the native popup foreground at 75% opacity. It stays subdued
without using the much darker muted palette color. Sizes and spacing follow
Omarchy tokens; contrast still depends on your theme.

## A few limits

The plugin uses normal UDisks2 unmount and power-off operations. It never forces
an unmount, formats a drive, or deletes files. Busy drives stop the operation.
It checks the drive's identity before each removal step and only reports success
after power-off succeeds and the drive disappears.

Some setups are deliberately left to a disk utility: system or protected storage,
encrypted volumes, swap, RAID, active storage mappings, shared enclosures, and
drives that don't support power-off. Removal is limited to USB drives with
ordinary filesystems mounted under `/run/media/`, `/media/`, or `/mnt/`.

If one partition fails to unmount, earlier partitions may already be unmounted.
If power-off fails after everything unmounts, the icon may disappear anyway.
Read the error and use your disk utility if needed. Keep backups: these checks
can't rule out hardware failures or every timing issue during removal.

## Disable or remove

```sh
omarchy plugin disable joey.usb-storage
omarchy plugin remove joey.usb-storage --yes
```

Disable stops the widget and its background checks. Remove deletes the installed
plugin, not anything on your USB drives.

## Updates and troubleshooting

For a Git-based install, run this and review the proposed changes:

```sh
omarchy plugin update joey.usb-storage
```

For a local install, pull the changes in your clone, disable and remove the
installed copy, then run `install.py` again.

**Updates not showing up:** On the tested Omarchy version, changed QML
sometimes needed a shell restart even after a reload message. Close desktop
panels and wait until no USB action is running, then run:

```sh
omarchy restart shell
omarchy-shell shell ping
omarchy-shell joey.usb-storage diagnostics
```

The restart briefly reloads the desktop shell. `ping` should return `ok`, and this
version's diagnostics should show `native-compact-v16-secondary-contrast`.

**Open seems stuck:** After ten seconds, the plugin reports that it couldn't
confirm the launch. It doesn't kill your file manager, which may still open.
Check before trying again. A successful launcher exit also can't guarantee that
a window is visible.

**Space or connection details unavailable:** Metadata is optional. Free-space
reads run separately while the menu is open, with a two-second display deadline
and refreshes every 15 seconds. A slow read can't block discovery or removal
controls, and no second stats worker starts while the first is still running.
An unresponsive mount may leave space unavailable until that worker returns.
Unknown USB speed is shown as unavailable rather than guessed.

**Error details:** These commands only read information. Run the
second from your project clone or installed plugin directory:

```sh
quickshell log -p /usr/share/omarchy/shell -t 100
/usr/bin/python usb_helper.py list
```

The open menu can cover unrelated desktop notifications. Successful eject closes
it before showing its own notification.

To undo an installation, disabling or removing the plugin is usually enough.
Restoring an old `shell.json` also rolls back unrelated layout changes made since
that backup. If you choose to restore it, run `omarchy-shell shell reloadConfig`
after copying it back.

## Development

Run the checks from the project directory on an Omarchy system. The input tests
need QtTest (on Arch, `qt6-declarative`), and the rendered contrast check needs
ImageMagick (`magick`). These are test dependencies, not plugin requirements:

```sh
/usr/bin/python -m unittest -v
/usr/bin/python qml_smoke.py
/usr/bin/python open_smoke.py
/usr/bin/python target_smoke.py
/usr/bin/python details_smoke.py
/usr/bin/python title_smoke.py
/usr/bin/python spacing_smoke.py
/usr/bin/python contrast_smoke.py
omarchy plugin validate .
```

There are 43 Python tests and seven QML suites. They use fake devices, launchers,
and notifications; they never open or eject a real volume. Coverage includes
multiple drives and partitions, busy and partial failures, changed devices,
malicious labels, repeated clicks, delayed results, per-volume space, missing
metadata, empty/full/partial usage, theme colors, long mount paths, repeated
expansion, keyboard and mouse action isolation, and a slow stats worker. The
contrast suite renders the current palette plus bundled Nord, Flexoki Light, and
White palettes; those results are not a guarantee for every custom theme.
Offscreen tests may warn
about Wayland focus or window masks. They don't replace hands-on checks of
hardware, keyboard and mouse behavior, or multi-monitor setups.

`Widget.qml` handles bar integration and feedback, `UsbMenu.qml` draws the menu,
and `usb_helper.py` talks to UDisks2. The helper uses argument arrays for launches
and treats drive labels as text. The UI ignores stale replies and waits for both
a successful removal result and a refreshed device list before notifying.

See the [Omarchy shell docs](https://github.com/omacom/omarchy/blob/v4.0.4/shell/README.md)
and [bar plugin docs](https://github.com/omacom/omarchy/blob/v4.0.4/shell/plugins/bar/README.md)
for the plugin API.

## License

[MIT](LICENSE), copyright 2026 Joey Gordon. Dependencies keep their own licenses.
This is an independent plugin, not an official Omarchy release.
