"""Isolated tests for a clean-target PREPARE entry; no host or DB effects."""
from __future__ import annotations
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest import mock

LIB=pathlib.Path(__file__).resolve().parents[1]/'lib'
fixture=types.ModuleType('server_migration_pull')
fixture.SCHEMA='vf-server-ops.server-migration.target-pull.v1'
fixture.PullMigrationError=type('PullMigrationError',(RuntimeError,),{})
fixture.sql_diff_probe=types.SimpleNamespace(AdvisoryDiagnosticUnavailable=type('AdvisoryDiagnosticUnavailable',(RuntimeError,),{}))
fixture.verify_engine=types.SimpleNamespace(RestoreVerifyError=type('RestoreVerifyError',(RuntimeError,),{}))
fixture.STATE_ROOT=pathlib.Path('/definitely-not-real-p07-target')
fixture.shlex=__import__('shlex')
fixture.inventory=types.SimpleNamespace(build_manifest=lambda *_: {'sites':[]})
for _f in ('source_probe','target_preflight_local','prepare_migration','stage_source_runtime','source_export_database','pull_path','cleanup_probe_runtime','source_remote','source_from_args'):
    setattr(fixture,_f,lambda *args,**kwargs: None)
previous=sys.modules.get('server_migration_pull')
sys.modules['server_migration_pull']=fixture
spec=importlib.util.spec_from_file_location('migration_fresh_cp2',LIB/'migration_fresh_cp2.py')
assert spec and spec.loader
fresh=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fresh)
if previous is None:
    sys.modules.pop('server_migration_pull',None)
else:
    sys.modules['server_migration_pull']=previous

def source_plan():
    names=[f'site{i}.example.test' for i in range(14)]+sorted(fresh.DATABASE_SITES)
    return {'schema':fixture.SCHEMA,'status':'READY','source_server_identity':'sha256:old-source',
        'sites':[{'domain':x,'site_user':f'u{i}','site_root':f'/home/u{i}/htdocs/{x}',
                  'mysql_databases':[f'db{i}'] if x in fresh.DATABASE_SITES else []}
                 for i,x in enumerate(names)],
        'external_assets':[],'sqlite_assets':[],'runtime_assets':{'system_cron':[], 'user_cron':[], 'pm2':[]}}

class FreshTests(unittest.TestCase):
    def test_valid_inventory_is_17_3(self):
        n,d=fresh.inventory_scope(source_plan())
        self.assertEqual(len(n),17)
        self.assertEqual({x for x,_ in d},fresh.DATABASE_SITES)
    def test_duplicate_site_refused(self):
        p=source_plan();p['sites'][0]['domain']=p['sites'][1]['domain']
        with self.assertRaisesRegex(fresh.FreshBlocked,'FRESH_SOURCE_SITE_SCOPE_CHANGED'):
            fresh.inventory_scope(p)
    def test_extra_missing_db_refused(self):
        p=source_plan();p['sites'][-1]['mysql_databases']=[]
        with self.assertRaisesRegex(fresh.FreshBlocked,'FRESH_THREE_DATABASE_OWNERS_CHANGED'):
            fresh.inventory_scope(p)
    def test_old_cp2_state_refused_before_target_preflight(self):
        with __import__('tempfile').TemporaryDirectory() as path:
            root=pathlib.Path(path);(root/'pull-old').mkdir()
            with mock.patch.object(fresh.pull,'STATE_ROOT',root),mock.patch.object(fresh.os,'geteuid',return_value=0),mock.patch.object(fresh.pull,'target_preflight_local') as called:
                with self.assertRaisesRegex(fresh.FreshBlocked,'FRESH_CP2_OLD_MIGRATION_STATE_PRESENT'):
                    fresh.clean_target(source_plan())
                called.assert_not_called()
    def test_target_sites_refused(self):
        with __import__('tempfile').TemporaryDirectory() as path:
            with mock.patch.object(fresh.pull,'STATE_ROOT',pathlib.Path(path)),\
                 mock.patch.object(fresh.os,'geteuid',return_value=0),\
                 mock.patch.object(fresh.pull,'target_preflight_local',return_value={'status':'READY','target_identity':'sha256:new'}),\
                 mock.patch.object(fresh.pull.inventory,'build_manifest',return_value={'sites':[{'domain':'existing'}]}):
                with self.assertRaisesRegex(fresh.FreshBlocked,'FRESH_CP2_EXISTING_SITES_PRESENT'):
                    fresh.clean_target(source_plan())
    def test_preview_never_prepares(self):
        with mock.patch.object(fresh.os,'geteuid',return_value=0),\
             mock.patch.object(fresh.pull,'source_probe',return_value=source_plan()),\
             mock.patch.object(fresh,'clean_target',return_value={'status':'READY'}),\
             mock.patch.object(fresh,'screen_source_databases',return_value=3),\
             mock.patch.object(fresh.pull,'prepare_migration') as prepare:
            result=fresh.run('preview',{'ip':'example'},fresh.CONFIRM_PREVIEW)
            self.assertEqual(result['status'],'PREFLIGHT_PASS_NOT_CUTOVER_READY')
            prepare.assert_not_called()
    def test_failed_sql_preflight_blocks_prepare(self):
        with mock.patch.object(fresh.os,'geteuid',return_value=0),\
             mock.patch.object(fresh.pull,'source_probe',return_value=source_plan()),\
             mock.patch.object(fresh,'clean_target',return_value={'status':'READY'}),\
             mock.patch.object(fresh,'screen_source_databases',side_effect=fresh.FreshBlocked('FRESH_SOURCE_SQL_UNPROVEN_SIDE_EFFECTS')),\
             mock.patch.object(fresh.pull,'prepare_migration') as prepare:
            with self.assertRaisesRegex(fresh.FreshBlocked,'FRESH_SOURCE_SQL_UNPROVEN_SIDE_EFFECTS'):
                fresh.run('prepare',{},fresh.CONFIRM_PREPARE)
            prepare.assert_not_called()
    def test_wrong_token_refuses_before_source_probe(self):
        with mock.patch.object(fresh.pull,'source_probe') as probe:
            with self.assertRaisesRegex(fresh.FreshBlocked,'FRESH_EXPLICIT_CONFIRMATION_REQUIRED'):
                fresh.run('prepare',{},'NOT_AUTHORIZED')
            probe.assert_not_called()
    def test_prepare_uses_exact_full_inventory(self):
        with mock.patch.object(fresh.os,'geteuid',return_value=0),\
             mock.patch.object(fresh.pull,'source_probe',return_value=source_plan()),\
             mock.patch.object(fresh,'clean_target',return_value={'status':'READY'}),\
             mock.patch.object(fresh,'screen_source_databases',return_value=3),\
             mock.patch.object(fresh.pull,'prepare_migration',return_value={'status':'PREPARED','sites':[{}]*17}) as prepare:
            result=fresh.run('prepare',{'host':'old'},fresh.CONFIRM_PREPARE)
            self.assertEqual(result['status'],'FRESH_FIRST_COPY_COMPLETED_NOT_CUTOVER_READY')
            self.assertEqual(len(prepare.call_args.args[1]),17)
    def test_source_sql_dynamic_guard_blocks_without_import(self):
        def local_copy(_src,_remote,p):
            pathlib.Path(p).write_bytes(b"fake bytes for isolated guard test")
        with mock.patch.object(fresh.pull,'stage_source_runtime'),\
             mock.patch.object(fresh.pull,'source_export_database'),\
             mock.patch.object(fresh.pull,'pull_path',side_effect=local_copy),\
             mock.patch.object(fresh.pull,'cleanup_probe_runtime'),\
             mock.patch.object(fresh.pull,'source_remote',return_value=types.SimpleNamespace(returncode=0)),\
             mock.patch.object(fresh.pull.sql_diff_probe,'require_nonempty_source_schema',create=True),\
             mock.patch.object(fresh.pull.sql_diff_probe,'require_source_import_utf8_integrity',create=True),\
             mock.patch.object(fresh.pull.sql_diff_probe,'dynamic_guard_syntax_counts',return_value={'recognized_unsafe':1},create=True),\
             mock.patch.object(fresh.pull.verify_engine,'sql_unproven_side_effects',return_value=False,create=True):
            with self.assertRaisesRegex(fresh.FreshBlocked,'FRESH_SOURCE_SQL_UNPROVEN_SIDE_EFFECTS'):
                fresh.screen_source_databases({},[('www3.m3u8.one','db')])
    def test_safe_sql_preflight_is_not_final_parity(self):
        def local_copy(_src,_remote,p):
            pathlib.Path(p).write_bytes(b"synthetic SQL content")
        with mock.patch.object(fresh.pull,'stage_source_runtime'),\
             mock.patch.object(fresh.pull,'source_export_database'),\
             mock.patch.object(fresh.pull,'pull_path',side_effect=local_copy),\
             mock.patch.object(fresh.pull,'cleanup_probe_runtime'),\
             mock.patch.object(fresh.pull,'source_remote',return_value=types.SimpleNamespace(returncode=0)),\
             mock.patch.object(fresh.pull.sql_diff_probe,'require_nonempty_source_schema',create=True),\
             mock.patch.object(fresh.pull.sql_diff_probe,'require_source_import_utf8_integrity',create=True),\
             mock.patch.object(fresh.pull.sql_diff_probe,'dynamic_guard_syntax_counts',return_value={},create=True),\
             mock.patch.object(fresh.pull.verify_engine,'sql_unproven_side_effects',return_value=False,create=True):
            self.assertEqual(fresh.screen_source_databases({},[('www3.m3u8.one','db')]),1)
    def test_sql_cleanup_unverified_fails(self):
        with mock.patch.object(fresh.pull,'stage_source_runtime'),\
             mock.patch.object(fresh.pull,'source_export_database'),\
             mock.patch.object(fresh.pull,'pull_path'),\
             mock.patch.object(fresh.pull,'cleanup_probe_runtime'),\
             mock.patch.object(fresh.pull,'source_remote',return_value=types.SimpleNamespace(returncode=1)),\
             mock.patch.object(fresh.pull.sql_diff_probe,'require_nonempty_source_schema',create=True),\
             mock.patch.object(fresh.pull.sql_diff_probe,'require_source_import_utf8_integrity',create=True),\
             mock.patch.object(fresh.pull.sql_diff_probe,'dynamic_guard_syntax_counts',return_value={},create=True),\
             mock.patch.object(fresh.pull.verify_engine,'sql_unproven_side_effects',return_value=False,create=True):
            with self.assertRaisesRegex(fresh.FreshBlocked,'FRESH_SOURCE_TEMP_CLEANUP_UNVERIFIED'):
                fresh.screen_source_databases({},[('www3.m3u8.one','db')])

if __name__=='__main__':unittest.main()
