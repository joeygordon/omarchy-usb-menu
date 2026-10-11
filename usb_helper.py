#!/usr/bin/python
"""Conservative UDisks2 USB discovery and explicitly requested removal."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PREFIX = 'org.freedesktop.UDisks2.'
REQUEST_ID = None
BLOCK, DRIVE, FS = (PREFIX + n for n in ('Block', 'Drive', 'Filesystem'))


def emit(**data):
    if REQUEST_ID is not None:
        data['requestId'] = REQUEST_ID
    print(json.dumps(data, ensure_ascii=True), flush=True)


def mounts(obj):
    return [os.fsdecode(bytes(m).rstrip(b'\0')) for m in obj.get(FS, {}).get('MountPoints', [])]


def clean(text):
    return ''.join(c if c.isprintable() else '�' for c in str(text))[:160]



class SafetyError(ValueError):
    def __init__(self, category, detail):
        super().__init__(detail)
        self.category = category


def error_payload(exc, action='eject'):
    """Classify exact D-Bus names/types, never text extracted from error messages."""
    remote = ''
    try:
        from gi.repository import Gio, GLib
        if isinstance(exc, GLib.Error):
            remote = Gio.dbus_error_get_remote_error(exc) or ''
    except ImportError:
        pass
    names = {
        'busy': ['org.freedesktop.UDisks2.Error.DeviceBusy'],
        'permission': ['org.freedesktop.UDisks2.Error.NotAuthorized',
                       'org.freedesktop.UDisks2.Error.NotAuthorizedCanObtain',
                       'org.freedesktop.UDisks2.Error.NotAuthorizedDismissed',
                       'org.freedesktop.UDisks2.Error.OptionNotPermitted',
                       'org.freedesktop.UDisks2.Error.MountedByOtherUser',
                       'org.freedesktop.DBus.Error.AccessDenied',
                       'org.freedesktop.DBus.Error.AuthFailed'],
        'stale': ['org.freedesktop.UDisks2.Error.NotMounted',
                  'org.freedesktop.DBus.Error.UnknownObject'],
        'unsupported': ['org.freedesktop.UDisks2.Error.NotSupported',
                        'org.freedesktop.DBus.Error.UnknownMethod'],
        'pending': ['org.freedesktop.UDisks2.Error.AlreadyUnmounting'],
    }
    category = next((key for key, values in names.items() if remote in values), 'failed')
    if isinstance(exc, SafetyError):
        category = exc.category
    elif isinstance(exc, PermissionError):
        category = 'permission'
    elif isinstance(exc, (FileNotFoundError, KeyError)):
        category = 'stale'
    messages = {
        'open_failed': "Couldn't open this volume. Try opening it from your file manager.",
        'open_timeout': "The file manager hasn't confirmed the Open request. It may still open; check before trying again.",
        'busy': 'This drive is still in use. Close any files or terminal windows using it, then try ejecting again.',
        'permission': "You don't have permission to manage this drive here. Try the system disk utility.",
        'stale': 'This drive changed or is no longer available. Close this menu and try again.',
        'unsupported': "This drive can't be safely ejected here. Use the system disk utility.",
        'protected': 'This drive uses protected storage. Use the system disk utility to manage it.',
        'shared': 'This device shares its connection with another drive. Use the system disk utility to manage it.',
        'pending': 'Another drive operation is already running. Wait for it to finish, then try again.',
        'unconfirmed': 'Removal could not be confirmed. Leave the drive connected and try the system disk utility.',
    }
    fallback = ("Couldn't open this volume. Try opening it from your file manager." if action == 'open'
                else 'USB storage is temporarily unavailable. Try again shortly.' if action == 'list'
                else "Couldn't eject this drive. Leave it connected and try again.")
    detail = ''.join(c if c.isprintable() or c in '\n\t' else '�' for c in str(exc))[:4096]
    return {'error': messages.get(category, fallback), 'errorCode': category,
            'details': {'type': type(exc).__name__, 'dbusError': remote, 'message': detail}}


class Bus:
    def __init__(self):
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def snapshot(self):
        return self.bus.call_sync('org.freedesktop.UDisks2', '/org/freedesktop/UDisks2',
            'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects', None,
            self.GLib.VariantType.new('(a{oa{sa{sv}}})'), self.Gio.DBusCallFlags.NONE,
            10000, None).unpack()[0]

    def call(self, path, interface, method):
        self.bus.call_sync('org.freedesktop.UDisks2', path, interface, method,
            self.GLib.Variant('(a{sv})', ({'auth.no_user_interaction': self.GLib.Variant('b', True)},)),
            None, self.Gio.DBusCallFlags.NONE, 120000, None)


def kernel_identity(block):
    """diskseq detects unplug/replug even if UDisks reuses its object path."""
    dev = block['DeviceNumber']
    path = Path('/sys/dev/block') / f'{os.major(dev)}:{os.minor(dev)}'
    real = path.resolve(strict=True)
    disk = real.parent if (real / 'partition').exists() else real
    if list((real / 'holders').iterdir()):
        raise SafetyError('protected', 'Device has active storage mappings; use the system disk utility.')
    return [str(real), (disk / 'diskseq').read_text().strip()]


def inspect(objects, path, identity=kernel_identity):
    drive = objects[path][DRIVE]
    if drive.get('ConnectionBus') != 'usb':
        raise SafetyError('protected', 'Not a USB storage drive.')
    blocks = {p: o for p, o in objects.items() if o.get(BLOCK, {}).get('Drive') == path}
    if not blocks:
        raise SafetyError('stale', 'Drive has no physical block devices.')
    sibling = drive.get('SiblingId', '')
    if sibling and any(p != path and o.get(DRIVE, {}).get('SiblingId') == sibling for p, o in objects.items()):
        raise SafetyError('shared', 'Shared USB enclosure affects another drive; use the system disk utility.')
    if not drive.get('CanPowerOff', False):
        raise SafetyError('unsupported', 'Safe power-off is not supported by this drive.')
    fingerprint = [path, {k: drive.get(k) for k in ('Id', 'Serial', 'WWN', 'TimeDetected', 'SiblingId', 'ConnectionBus')}]
    for p, obj in sorted(blocks.items()):
        b = obj[BLOCK]
        if b.get('HintSystem', True) or b.get('IdUsage', '') not in ('', 'filesystem'):
            raise SafetyError('protected', 'System, encrypted, swap or layered storage is protected.')
        for mount in mounts(obj):
            if not any(mount.startswith(base) for base in ('/run/media/', '/media/', '/mnt/')):
                raise SafetyError('protected', 'Mount outside removable-storage locations is protected.')
        fingerprint.append([p, b.get('DeviceNumber'), b.get('IdUUID'), b.get('Size'), identity(b)])
    token = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    return token, blocks


def discover(objects, identity=kernel_identity):
    result = []
    for path, obj in sorted(objects.items()):
        d = obj.get(DRIVE, {})
        if d.get('ConnectionBus') != 'usb':
            continue
        volumes = []
        for p, o in sorted(objects.items()):
            if o.get(BLOCK, {}).get('Drive') == path and mounts(o):
                volumes.append({'path': p, 'name': clean(o[BLOCK].get('IdLabel') or o[BLOCK].get('IdUUID') or p.rsplit('/', 1)[-1])})
        if not volumes:
            continue
        details = None
        try:
            token, _ = inspect(objects, path, identity)
            error = ''
        except (ValueError, OSError, KeyError) as exc:
            report = error_payload(exc)
            token, error, details = '', report['error'], report['details']
        physical = next((o[BLOCK] for o in objects.values() if o.get(BLOCK, {}).get('Drive') == path and PREFIX + 'Partition' not in o), {})
        raw_device = physical.get('Device', [])
        device = os.fsdecode(bytes(raw_device).rstrip(b'\0')) if raw_device else path.rsplit('/', 1)[-1]
        result.append({'device': clean(device), 'path': path, 'token': token, 'name': clean(d.get('Model') or 'USB storage'), 'volumes': volumes, 'error': error, 'errorDetails': details})
    for drive in result:
        ambiguous = sum(d['name'] == drive['name'] for d in result) > 1
        drive['displayName'] = ('[' + drive['device'].rsplit('/', 1)[-1] + '] ' if ambiguous else '') + drive['name']
    return result


def checked(bus, path, token, identity):
    objects = bus.snapshot()
    actual, blocks = inspect(objects, path, identity)
    if not token or actual != token:
        raise SafetyError('stale', 'Drive changed or was reconnected. Refresh and try again.')
    return blocks


def eject(bus, path, token, identity=kernel_identity, progress=lambda x: None):
    blocks = checked(bus, path, token, identity)
    for p in sorted(blocks):
        # Revalidate complete topology and diskseq before EVERY removal operation.
        current = checked(bus, path, token, identity)
        if mounts(current[p]):
            progress('Unmounting ' + clean(current[p][BLOCK].get('IdLabel') or p.rsplit('/', 1)[-1]) + '…')
            bus.call(p, FS, 'Unmount')  # no force flag; busy files abort here
    current = checked(bus, path, token, identity)
    if any(mounts(o) for o in current.values()):
        raise SafetyError('busy', 'A volume is still mounted or was remounted; power-off cancelled.')
    progress('Powering off USB drive…')
    bus.call(path, DRIVE, 'PowerOff')
    # A successful reply alone is insufficient for our safe-to-unplug claim.
    after = bus.snapshot()
    if path in after or any(o.get(BLOCK, {}).get('Drive') == path for o in after.values()):
        raise SafetyError('unconfirmed', 'Power-off returned but the drive remains present; safe removal is not confirmed.')


@contextlib.contextmanager
def removal_lock():
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    with (runtime / 'joey-usb-storage.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafetyError('pending', 'Another USB removal is already in progress.')
        yield


def launch_file_manager(uri, timeout=10):
    """Wait for the launcher, without killing an existing/file-manager process."""
    try:
        process = subprocess.Popen(['xdg-open', uri], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise SafetyError('open_failed', f'Could not start xdg-open: {exc}') from exc
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # Some handlers stay attached to their window. Bound our wait but do not
        # terminate a launcher that may have exec'd the actual file manager.
        raise SafetyError('open_timeout', 'xdg-open did not finish within the launch deadline.') from exc
    if code != 0:
        raise SafetyError('open_failed', f'xdg-open exited with status {code}.')


def main():
    global REQUEST_ID
    args = sys.argv[1:]
    REQUEST_ID = args.pop().split('=', 1)[1] if args and args[-1].startswith('--request-id=') else None
    action = args[0] if args else ''
    try:
        bus = Bus()
        if action == 'list':
            emit(drives=discover(bus.snapshot()))
        elif action == 'eject' and len(args) == 3:
            with removal_lock():
                eject(bus, args[1], args[2], progress=lambda message: emit(progress=message))
            emit(success=True, message='Safe to unplug the USB drive.')
        elif action == 'open' and len(args) == 4:
            # Open is read-only and also available for drives we refuse to eject.
            objects = bus.snapshot()
            drive, volume = args[1], args[3]
            if objects.get(drive, {}).get(DRIVE, {}).get('ConnectionBus') != 'usb':
                raise SafetyError('stale', 'USB drive is no longer present.')
            obj = objects.get(volume, {})
            if obj.get(BLOCK, {}).get('Drive') != drive or not mounts(obj):
                raise SafetyError('stale', 'Volume is no longer mounted.')
            from gi.repository import Gio
            launch_file_manager(Gio.File.new_for_path(mounts(obj)[0]).get_uri())
            emit(success=True, message='File manager accepted the Open request.')
        else:
            raise ValueError('Unknown request.')
    except Exception as exc:
        emit(**error_payload(exc, action))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
