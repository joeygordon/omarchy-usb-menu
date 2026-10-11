import copy
import os
import tempfile
import unittest
from unittest.mock import patch
import usb_helper as h

D = '/drives/usb'
P = '/blocks/part1'
Q = '/blocks/part2'
def fixture():
    return {D: {h.DRIVE: {'ConnectionBus': 'usb', 'CanPowerOff': True, 'Serial': 'a', 'TimeDetected': 1}},
            P: {h.BLOCK: {'Drive': D, 'HintSystem': False, 'IdUsage': 'filesystem', 'DeviceNumber': 1, 'IdLabel': 'one'}, h.FS: {'MountPoints': [list(b'/run/media/testuser/one\0')]}}}

def identity(b): return ['sys/device', '42']
class Fake:
    def __init__(self, objects): self.objects, self.calls, self.fail = objects, [], ''
    def snapshot(self): return copy.deepcopy(self.objects)
    def call(self, path, interface, method):
        self.calls.append((path, method))
        if self.fail: raise RuntimeError(self.fail)
        if method == 'Unmount': self.objects[path][h.FS]['MountPoints'] = []
        else: self.objects.clear()

class Tests(unittest.TestCase):
    def setUp(self): self.o = fixture()
    def token(self): return h.inspect(self.o, D, identity)[0]
    def test_no_drive(self): self.assertEqual(h.discover({}), [])
    def test_only_mounted_usb(self):
        self.o[D][h.DRIVE]['ConnectionBus'] = 'ata'
        self.assertEqual(h.discover(self.o, identity), [])
    def test_multiple_partitions_and_order(self):
        self.o[Q] = copy.deepcopy(self.o[P])
        self.assertEqual(len(h.discover(self.o, identity)[0]['volumes']), 2)
        bus = Fake(self.o)
        h.eject(bus, D, self.token(), identity)
        self.assertEqual(bus.calls, [(P, 'Unmount'), (Q, 'Unmount'), (D, 'PowerOff')])
    def test_malicious_label_is_data(self):
        label = '$(touch /tmp/USB_PWNED);<b>bad</b>\n'
        self.o[P][h.BLOCK]['IdLabel'] = label
        self.assertEqual(h.discover(self.o, identity)[0]['volumes'][0]['name'], label[:-1] + '�')
    def test_stale_identity(self):
        token = self.token(); self.o[D][h.DRIVE]['TimeDetected'] = 2
        bus = Fake(self.o)
        with self.assertRaises(ValueError): h.eject(bus, D, token, identity)
        self.assertEqual(bus.calls, [])
    def test_diskseq_change(self):
        bus = Fake(self.o)
        with self.assertRaises(ValueError): h.eject(bus, D, self.token(), lambda b: ['sys/device', '43'])
        self.assertEqual(bus.calls, [])
    def test_busy_and_error(self):
        for error in ('DeviceBusy', 'NotAuthorized'):
            bus = Fake(copy.deepcopy(self.o)); bus.fail = error
            with self.assertRaises(RuntimeError): h.eject(bus, D, self.token(), identity)
            self.assertEqual(bus.calls, [(P, 'Unmount')])
    def test_protected(self):
        for key, value in [('HintSystem', True), ('IdUsage', 'crypto'), ('IdUsage', 'raid'), ('IdUsage', 'other')]:
            o = copy.deepcopy(self.o); o[P][h.BLOCK][key] = value
            with self.assertRaises(ValueError): h.inspect(o, D, identity)
    def test_internal_mount(self):
        self.o[P][h.FS]['MountPoints'] = [list(b'/home\0')]
        with self.assertRaises(ValueError): self.token()
    def test_sibling(self):
        self.o[D][h.DRIVE]['SiblingId'] = 'enclosure'
        self.o['/drive2'] = {h.DRIVE: {'SiblingId': 'enclosure'}}
        with self.assertRaises(ValueError): self.token()
    def test_remount_blocks_poweroff(self):
        class Remount(Fake):
            def call(self, *args): self.calls.append(args)
        bus = Remount(self.o)
        with self.assertRaises(ValueError): h.eject(bus, D, self.token(), identity)
        self.assertEqual(len(bus.calls), 1)
    def test_success_reply_without_disappearance(self):
        class Remain(Fake):
            def call(self, p, i, m):
                if m == 'PowerOff': self.calls.append((p, m))
                else: super().call(p, i, m)
        with self.assertRaises(ValueError): h.eject(Remain(self.o), D, self.token(), identity)
    def test_change_between_operations(self):
        class Change(Fake):
            def call(self, *args):
                super().call(*args)
                self.objects[D][h.DRIVE]['Serial'] = 'replacement'
        bus = Change(self.o)
        with self.assertRaises(ValueError): h.eject(bus, D, self.token(), identity)
        self.assertEqual(bus.calls, [(P, 'Unmount')])
    def test_open_malicious_mount_uses_uri_argv(self):
        path = '/run/media/testuser/$(touch NEVER); space <tag>'
        self.o[P][h.FS]['MountPoints'] = [list(path.encode() + b'\0')]
        with patch.object(h, 'Bus', return_value=Fake(self.o)), patch.object(h.sys, 'argv', ['helper', 'open', D, '', P]), patch.object(h.subprocess, 'Popen') as spawn, patch.object(h, 'emit'):
            self.assertEqual(h.main(), 0)
            argv = spawn.call_args.args[0]
            self.assertEqual(argv[0], 'xdg-open')
            self.assertTrue(argv[1].startswith('file:///run/media/testuser/'))
            self.assertIn('%20', argv[1])
            self.assertNotIn('shell', spawn.call_args.kwargs)
    def test_open_stale_volume_does_not_launch(self):
        with patch.object(h, 'Bus', return_value=Fake({})), patch.object(h.sys, 'argv', ['helper', 'open', D, '', P]), patch.object(h.subprocess, 'Popen') as spawn, patch.object(h, 'emit'):
            self.assertEqual(h.main(), 1)
            spawn.assert_not_called()
    def test_topology_added(self):
        token = self.token()
        self.o[Q] = copy.deepcopy(self.o[P])
        bus = Fake(self.o)
        with self.assertRaises(ValueError): h.eject(bus, D, token, identity)
        self.assertEqual(bus.calls, [])
    def test_multiple_devices_independent(self):
        self.o['/drives/b'] = copy.deepcopy(self.o[D])
        self.o[Q] = copy.deepcopy(self.o[P])
        self.o[Q][h.BLOCK]['Drive'] = '/drives/b'
        self.assertEqual(len(h.discover(self.o, identity)), 2)
    def test_repeated_click_lock(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, XDG_RUNTIME_DIR=tmp):
            with h.removal_lock():
                with self.assertRaises(ValueError):
                    with h.removal_lock(): pass

class ErrorTests(unittest.TestCase):
    def remote(self, name, text='Technical backend detail'):
        from gi.repository import Gio
        return Gio.dbus_error_new_for_dbus_error(name, text)

    def test_structured_busy(self):
        result = h.error_payload(self.remote(h.PREFIX + 'Error.DeviceBusy'))
        self.assertEqual(result['error'], 'This drive is still in use. Close any files or terminal windows using it, then try ejecting again.')
        self.assertEqual(result['errorCode'], 'busy')
        self.assertEqual(result['details']['dbusError'], h.PREFIX + 'Error.DeviceBusy')

    def test_exact_structured_mappings(self):
        cases = {
            h.PREFIX+'Error.NotAuthorized': 'permission',
            h.PREFIX+'Error.NotAuthorizedCanObtain': 'permission',
            h.PREFIX+'Error.NotAuthorizedDismissed': 'permission',
            h.PREFIX+'Error.NotSupported': 'unsupported',
            h.PREFIX+'Error.NotMounted': 'stale',
            h.PREFIX+'Error.AlreadyUnmounting': 'pending',
            'org.freedesktop.DBus.Error.UnknownObject': 'stale',
        }
        for name, category in cases.items():
            with self.subTest(name=name):
                result = h.error_payload(self.remote(name))
                self.assertEqual(result['errorCode'], category)
                self.assertNotIn('Safe to unplug', result['error'])

    def test_unknown_and_misleading_message(self):
        for exc in [RuntimeError('DeviceBusy NotAuthorized'), self.remote(h.PREFIX+'Error.FutureError', 'DeviceBusy'), self.remote(h.PREFIX+'Error.Failed')]:
            result = h.error_payload(exc)
            self.assertEqual(result['errorCode'], 'failed')
            self.assertEqual(result['error'], "Couldn't eject this drive. Leave it connected and try again.")

    def test_long_multiline_details_are_bounded_and_separate(self):
        result = h.error_payload(RuntimeError('RAW DETAIL\n\x1b[31m' * 2000))
        self.assertNotIn('RAW', result['error'])
        self.assertNotIn('\n', result['error'])
        self.assertLess(len(result['error']), 150)
        self.assertEqual(len(result['details']['message']), 4096)
        self.assertNotIn('\x1b', result['details']['message'])

    def test_local_refusals(self):
        for exc, category in [(h.SafetyError('protected','raw details'),'protected'), (h.SafetyError('shared','raw details'),'shared'), (h.SafetyError('unconfirmed','raw details'),'unconfirmed'), (PermissionError('raw'),'permission'), (KeyError('gone'),'stale'), (FileNotFoundError('gone'),'stale')]:
            self.assertEqual(h.error_payload(exc)['errorCode'],category)

    def test_open_fallback_has_no_eject_success_claim(self):
        result = h.error_payload(RuntimeError('RAW'), 'open')
        self.assertEqual(result['error'], "Couldn't open this volume. Try opening it from your file manager.")
        self.assertNotIn('RAW', result['error'])

    def test_discovery_refusal_has_friendly_text_and_details(self):
        objects = fixture()
        objects[P][h.BLOCK]['IdUsage'] = 'crypto'
        result = h.discover(objects, identity)[0]
        self.assertEqual(result['token'], '')
        self.assertIn('protected storage', result['error'])
        self.assertIn('encrypted', result['errorDetails']['message'])

class CorrelationTests(unittest.TestCase):
    def test_duplicate_model_names_are_distinguished(self):
        o = fixture()
        o[D][h.DRIVE]['Model'] = 'Same USB'
        o['/drives/second'] = copy.deepcopy(o[D])
        o[Q] = copy.deepcopy(o[P])
        o[Q][h.BLOCK]['Drive'] = '/drives/second'
        drives = h.discover(o, identity)
        self.assertNotEqual(drives[0]['displayName'], drives[1]['displayName'])
        self.assertTrue(all(d['displayName'].startswith('[') for d in drives))

    def test_request_id_echo_without_storage_action(self):
        import io, json, contextlib
        out = io.StringIO()
        with patch.object(h, 'Bus', return_value=Fake({})), patch.object(h.sys, 'argv', ['helper','list','--request-id=opaque-42']), contextlib.redirect_stdout(out):
            self.assertEqual(h.main(), 0)
        self.assertEqual(json.loads(out.getvalue())['requestId'], 'opaque-42')
        h.REQUEST_ID = None

if __name__ == '__main__': unittest.main()
