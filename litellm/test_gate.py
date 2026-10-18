import importlib.util
import json
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gate', __file__.replace('test_gate.py', 'gate.py'))
try:
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
except FileNotFoundError:
    gate = None

class GateTests(unittest.TestCase):
    def test_restrict_request(self):
        self.assertIsNotNone(gate, 'fixed-purpose gate not implemented')
        body = {'name':'litellm-litellm-1','result':{'hook':{'phase':'pre','parentTrigger':'litellm'}}}
        self.assertTrue(gate.allowed('172.26.0.3','/backup','Bearer test',b'test',body))
        for ip,path,auth,data in [('192.168.1.3','/backup','Bearer test',body),('172.26.0.3','/exec','Bearer test',body),('172.26.0.3','/backup?cmd=id','Bearer test',body),('172.26.0.3','/backup','Bearer wrong',body),('172.26.0.3','/backup','Bearer test',{'name':'litellm-db-1'}),('172.26.0.3','/backup','Bearer test',{'name':'litellm-litellm-1','command':'id'})]:
            self.assertFalse(gate.allowed(ip,path,auth,b'test',data))
    def test_failure_never_returns_success(self):
        self.assertIsNotNone(gate, 'fixed-purpose gate not implemented')
        import subprocess
        with patch.object(gate.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['fixed'])):
            with self.assertRaises(subprocess.CalledProcessError):
                gate.backup()
    def test_fixed_backup_command(self):
        self.assertIsNotNone(gate, 'fixed-purpose gate not implemented')
        from types import SimpleNamespace
        with patch.object(gate.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps({'restore_verified':True}).encode())) as run:
            self.assertTrue(gate.backup()['restore_verified'])
            args,kw=run.call_args
            self.assertEqual(args[0],['/usr/bin/python3','-I','/usr/local/lib/litellm-backup/backup.py'])
            self.assertTrue(kw['check'])
            self.assertEqual(kw['timeout'],480)
    def test_unverified_restore_rejected(self):
        self.assertIsNotNone(gate, 'fixed-purpose gate not implemented')
        from types import SimpleNamespace
        with patch.object(gate.subprocess,'run',return_value=SimpleNamespace(stdout=b'{"restore_verified":false}')):
            with self.assertRaises(RuntimeError):
                gate.backup()

if __name__ == '__main__':
    unittest.main()
