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
        elif method == 'PowerOff':
            for p in list(self.objects):
                if p == path or self.objects[p].get(h.BLOCK, {}).get('Drive') == path:
                    del self.objects[p]
        else: raise AssertionError('Unexpected removal method: ' + method)

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
            spawn.return_value.wait.return_value = 0
            self.assertEqual(h.main(), 0)
            spawn.return_value.wait.assert_called_once_with(timeout=10)
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
    def test_eject_preserves_other_drive(self):
        other, part = '/drives/other', '/blocks/other'
        self.o[other] = copy.deepcopy(self.o[D])
        self.o[part] = copy.deepcopy(self.o[P])
        self.o[part][h.BLOCK]['Drive'] = other
        before = copy.deepcopy({other: self.o[other], part: self.o[part]})
        bus = Fake(self.o)
        h.eject(bus, D, self.token(), identity)
        self.assertEqual(bus.calls, [(P, 'Unmount'), (D, 'PowerOff')])
        self.assertEqual(bus.objects, before)

    def test_later_partition_busy_preserves_remaining_mount(self):
        self.o[Q] = copy.deepcopy(self.o[P])
        class LaterBusy(Fake):
            def call(self, path, interface, method):
                if path == Q:
                    self.calls.append((path, method))
                    raise h.SafetyError('busy', 'Later partition busy')
                super().call(path, interface, method)
        bus = LaterBusy(self.o)
        with self.assertRaises(h.SafetyError): h.eject(bus, D, self.token(), identity)
        self.assertEqual(bus.calls, [(P, 'Unmount'), (Q, 'Unmount')])
        self.assertEqual(h.mounts(bus.objects[P]), [])
        self.assertTrue(h.mounts(bus.objects[Q]))
        self.assertIn(D, bus.objects)

    def test_poweroff_failure_leaves_drive_present_unmounted(self):
        class PowerFailure(Fake):
            def call(self, path, interface, method):
                if method == 'PowerOff':
                    self.calls.append((path, method))
                    raise RuntimeError('Power-off failed')
                super().call(path, interface, method)
        bus = PowerFailure(self.o)
        with self.assertRaises(RuntimeError): h.eject(bus, D, self.token(), identity)
        self.assertEqual(bus.calls, [(P, 'Unmount'), (D, 'PowerOff')])
        self.assertIn(D, bus.objects)
        self.assertEqual(h.mounts(bus.objects[P]), [])

    def test_sibling_appearing_between_operations_blocks_poweroff(self):
        self.o[D][h.DRIVE]['SiblingId'] = 'enclosure'
        class NewSibling(Fake):
            def call(self, *args):
                super().call(*args)
                self.objects['/drives/sibling'] = {h.DRIVE: {'SiblingId': 'enclosure'}}
        bus = NewSibling(self.o)
        with self.assertRaises(h.SafetyError) as error:
            h.eject(bus, D, self.token(), identity)
        self.assertEqual(error.exception.category, 'shared')
        self.assertEqual(bus.calls, [(P, 'Unmount')])
        self.assertIn(D, bus.objects)

    def test_repeated_click_lock(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, XDG_RUNTIME_DIR=tmp):
            with h.removal_lock():
                with self.assertRaises(ValueError):
                    with h.removal_lock(): pass

class LauncherTests(unittest.TestCase):
    def request(self, spawn):
        from io import StringIO
        import contextlib, json
        output = StringIO()
        with patch.object(h, 'Bus', return_value=Fake(fixture())), patch.object(h.sys, 'argv', ['helper', 'open', D, '', P]), patch.object(h.subprocess, 'Popen', spawn), contextlib.redirect_stdout(output):
            code = h.main()
        return code, json.loads(output.getvalue())

    def test_launcher_success_waits_for_exit(self):
        from unittest.mock import Mock
        spawn = Mock()
        spawn.return_value.wait.return_value = 0
        code, report = self.request(spawn)
        spawn.return_value.wait.assert_called_once_with(timeout=10)
        self.assertEqual(code, 0)
        self.assertTrue(report['success'])

    def test_launcher_nonzero_exit_is_error(self):
        from unittest.mock import Mock
        for status in (1, 3, 4, -15):
            spawn = Mock()
            spawn.return_value.wait.return_value = status
            code, report = self.request(spawn)
            self.assertEqual(code, 1)
            self.assertEqual(report['errorCode'], 'open_failed')
            self.assertNotIn('success', report)
            self.assertIn(str(status), report['details']['message'])

    def test_launcher_spawn_failure_is_open_error(self):
        from unittest.mock import Mock
        for error in (FileNotFoundError('xdg-open missing'), PermissionError('denied')):
            code, report = self.request(Mock(side_effect=error))
            self.assertEqual(code, 1)
            self.assertEqual(report['errorCode'], 'open_failed')
            self.assertNotIn('success', report)

    def test_launcher_timeout_is_bounded_without_killing_file_manager(self):
        from unittest.mock import Mock
        spawn = Mock()
        spawn.return_value.wait.side_effect = h.subprocess.TimeoutExpired('xdg-open', 10)
        code, report = self.request(spawn)
        self.assertEqual(code, 1)
        self.assertEqual(report['errorCode'], 'open_timeout')
        self.assertIn('may still open', report['error'])
        self.assertNotIn('success', report)
        spawn.return_value.wait.assert_called_once_with(timeout=10)
        spawn.return_value.kill.assert_not_called()
        spawn.return_value.terminate.assert_not_called()


class MetadataTests(unittest.TestCase):
    def test_volume_and_drive_sizes_remain_distinct(self):
        o = fixture()
        o[D][h.DRIVE]['Size'] = 64000000000
        o[P][h.BLOCK].update(Size=32000000000, IdType='ext4')
        o[P][h.FS]['Size'] = 31000000000
        o[Q] = copy.deepcopy(o[P])
        o[Q][h.BLOCK]['Size'] = 16000000000
        d = h.discover(o, identity)[0]
        self.assertEqual(d['capacityBytes'], 64000000000)
        self.assertEqual(d['volumes'][0]['filesystemBytes'], 31000000000)
        self.assertEqual(d['volumes'][1]['partitionBytes'], 16000000000)
        self.assertEqual(d['volumes'][0]['filesystem'], 'ext4')
        self.assertNotEqual(d['volumes'][0]['spaceKey'], d['volumes'][1]['spaceKey'])

    def test_missing_metadata_is_optional(self):
        d = h.discover(fixture(), identity)[0]
        self.assertEqual(d['capacityBytes'], 0)
        self.assertIsNone(d['usbSpeedMbps'])
        self.assertEqual(d['volumes'][0]['filesystem'], 'Unknown')
        self.assertEqual(d['volumes'][0]['filesystemBytes'], 0)

    def test_space_reports_available_not_reserved_free(self):
        from types import SimpleNamespace
        reports = []
        o = fixture(); o[Q] = copy.deepcopy(o[P])
        h.collect_space(Fake(o), query=lambda p: SimpleNamespace(f_blocks=100, f_frsize=4096, f_bavail=20, f_bfree=30), identity=identity, report=lambda **v: reports.append(v))
        self.assertEqual(len(reports), 2)
        self.assertTrue(all(v['totalBytes'] == 409600 and v['availableBytes'] == 81920 and v['usedBytes'] == 286720 for v in reports))
        self.assertNotEqual(reports[0]['spaceKey'], reports[1]['spaceKey'])

    def test_space_discards_changed_mount(self):
        from types import SimpleNamespace
        bus = Fake(fixture()); reports = []
        def query(path):
            bus.objects[P][h.FS]['MountPoints'] = [list(b'/mnt/replacement\0')]
            return SimpleNamespace(f_blocks=10, f_frsize=4096, f_bavail=1)
        h.collect_space(bus, query=query, identity=identity, report=lambda **v: reports.append(v))
        self.assertEqual(reports, [])
        self.assertEqual(bus.calls, [])

    def test_space_failure_and_impossible_counts_are_unavailable(self):
        from types import SimpleNamespace
        for value in (OSError('offline'), SimpleNamespace(f_blocks=10, f_frsize=4096, f_bavail=20)):
            reports = []
            def query(path):
                if isinstance(value, Exception): raise value
                return value
            h.collect_space(Fake(fixture()), query=query, identity=identity, report=lambda **v: reports.append(v))
            self.assertEqual(reports, [])

    def test_usage_empty_full_partial_and_invalid(self):
        from types import SimpleNamespace
        for free, available, expected in ((100,100,0),(0,0,100),(30,20,70),(-1,0,None),(101,100,None),(10,20,None)):
            reports = []
            h.collect_space(Fake(fixture()), query=lambda p: SimpleNamespace(f_blocks=100,f_frsize=1,f_bfree=free,f_bavail=available), identity=identity, report=lambda **v: reports.append(v))
            if expected is None: self.assertEqual(reports, [])
            else: self.assertEqual(reports[0]['usedBytes'], expected)

    def test_mount_paths_are_plain_display_data_without_truncation(self):
        o = fixture()
        path = '/run/media/testuser/' + '<b>$(not-a-command)</b>' * 20 + '\n'
        o[P][h.FS]['MountPoints'] = [list(path.encode()+b'\0'), list(b'/mnt/second\0')]
        volume = h.discover(o, identity)[0]['volumes'][0]
        self.assertEqual(volume['mountPaths'], [path[:-1]+'�','/mnt/second'])
        self.assertGreater(len(volume['mountPaths'][0]),160)

    def test_sysfs_negotiated_speed_and_missing_rate(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); usb = root/'devices/usb1/1-2'; block = usb/'host/block/sdz'
            block.mkdir(parents=True)
            links = root/'dev'; links.mkdir()
            (links/'8:0').symlink_to(block)
            for name, text in [('idVendor','1234'), ('idProduct','5678'), ('speed','5000')]: (usb/name).write_text(text)
            self.assertEqual(h.usb_speed({'DeviceNumber': os.makedev(8,0)}, links), 5000)
            (usb/'speed').write_text('unknown')
            self.assertIsNone(h.usb_speed({'DeviceNumber': os.makedev(8,0)}, links))
            (usb/'speed').unlink()
            self.assertIsNone(h.usb_speed({'DeviceNumber': os.makedev(8,0)}, links))


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
