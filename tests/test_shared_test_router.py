import importlib.util
import json
import tempfile
import sys
import time
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'scripts/shared_test_router.py'
spec = importlib.util.spec_from_file_location('shared_test_router', p)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


def req(task_id='p01-fast', tier='light', privacy='public_safe', key='p01'):
    return dict(task_id=task_id, repository='llhzx2018/vf-start', commit_sha='a'*40,
                tree_sha='b'*40, test_id='synthetic', tier=tier, privacy=privacy,
                resource_key=key, timeout_seconds=2)


class RouterTest(unittest.TestCase):
    def test_lane_contract(self):
        self.assertEqual(router.route(req()), 'PUBLIC_HOSTED')
        self.assertEqual(router.route(req(tier='integration', privacy='private_source')), 'PUBLIC_TRANSIENT_PRIVATE_SOURCE')
        self.assertEqual(router.route(req(tier='integration', privacy='private_evidence')), 'PRIVATE_SANDBOX')
        self.assertEqual(router.route(req(tier='heavy')), 'EXISTING_HYPERV')

    def test_replay_and_secret_injection(self):
        with self.assertRaisesRegex(ValueError, 'TASK_ID_REPLAY'):
            router.plan([req(), req()])
        for field, value in [('token', 'SENSITIVE'), ('command', ['/bin/sh'])]:
            tampered = {**req(), field: value}
            with self.assertRaisesRegex(ValueError, 'REQUEST_FIELDS_INVALID'):
                router.plan([tampered])
        for wrong in ('../../tmp', 'P01/../../foo', 'file:///tmp'):
            with self.assertRaises(ValueError):
                router.plan([{**req(), 'resource_key': wrong}])

    def test_source_pin_timeout_bool_and_lane_tamper(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_SHA_INVALID'):
            router.plan([{**req(), 'commit_sha': 'main'}])
        with self.assertRaisesRegex(ValueError, 'TIMEOUT_INVALID'):
            router.plan([{**req(), 'timeout_seconds': True}])
        p = router.plan([req()])
        p['tasks'][0]['lane'] = 'PRIVATE_SANDBOX'
        with self.assertRaisesRegex(ValueError, 'LANE_TAMPERED'):
            router.execute_public(p, {}, workers=2)

    def test_independent_projects_really_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            first = req('p01-light')
            second = {**req('p08-light'), 'repository': 'llhzx2018/vf-adops', 'resource_key': 'p08', 'test_id': 'synthetic2'}
            first['timeout_seconds'] = 8
            second['timeout_seconds'] = 8
            batch = router.plan([first, second, req('p07-heavy', tier='heavy')])
            catalog = {}
            for key in ('synthetic', 'synthetic2'):
                marker = str(Path(directory)/(key + '.json'))
                code = ('import json,time,pathlib; a=time.monotonic();time.sleep(1.2);'
                        'pathlib.Path(%r).write_text(json.dumps([a,time.monotonic()]))' % marker)
                catalog[key] = [sys.executable, '-c', code]
            result = router.execute_public(batch, catalog, workers=2)
            self.assertEqual([r['result'] for r in result['receipts']], ['PASS', 'PASS', 'DEFERRED_ROUTE'])
            self.assertTrue(all(r.get('sandbox_cleaned') for r in result['receipts'][:2]))
            a, b = [json.loads((Path(directory)/(x+'.json')).read_text()) for x in ('synthetic','synthetic2')]
            self.assertLess(max(a[0], b[0]), min(a[1], b[1]), 'The two independent real processes must overlap')

    def test_private_source_not_falsely_executed(self):
        item = req(privacy='private_source')
        result = router.execute_public(router.plan([item]), {'synthetic': ['/bin/true']})
        self.assertEqual(result['receipts'][0]['result'], 'BLOCKED_PRIVATE_CHECKOUT_NOT_ATTESTED')

    def test_timeout_and_no_secret_echo(self):
        catalog = {'synthetic': [sys.executable, '-c', 'import time;print("TOKEN=SHOULD_NEVER_APPEAR");time.sleep(5)']}
        r = req()
        r['timeout_seconds'] = 1
        result = router.execute_public(router.plan([r]), catalog)['receipts'][0]
        self.assertEqual(result['result'], 'TIMEOUT')
        self.assertNotIn('SHOULD_NEVER_APPEAR', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
