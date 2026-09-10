from __future__ import annotations

import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import sys
ROOT = Path(__file__).resolve().parents[4] if len(Path(__file__).resolve().parents) > 4 else Path.cwd()
sys.path.insert(0, str(Path('/tmp/p07-restore-as-gate/lib')))
import restore_as
import site_lifecycle


class RestoreAsBehavior(unittest.TestCase):
    def package(self, base: Path, databases: int = 1) -> Path:
        p = base / 'backup'; (p/'files').mkdir(parents=True); (p/'mysql').mkdir()
        (p/'files/site.tar.gz').write_bytes(b'x')
        rows=[]
        for i in range(databases):
            name=f'source_db_{i+1}'; f=p/'mysql'/f'{name}.sql.gz'
            with gzip.open(f,'wt',encoding='utf-8') as h:
                h.write('CREATE TABLE demo(id INT);\nINSERT INTO demo VALUES (1);\n')
            rows.append({'database':name,'file':f'mysql/{name}.sql.gz'})
        manifest={
          'schema':'vf-server-ops.backup-package.v1','backup_id':'example.com_20260910T000000Z',
          'site':{'domain':'example.com','site_user':'alice','site_root':'/home/alice/htdocs/example.com',
                  'document_root':'/home/alice/htdocs/example.com/public',
                  'runtime':{'type':'php','version':'8.4','app_port':'UNKNOWN'}},
          'contents':{'files_archive':'files/site.tar.gz','mysql':rows,'sqlite':[],'metadata':{}}
        }
        (p/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        return p

    def target(self, base: Path) -> Path:
        t=base/'target'; t.mkdir();
        (t/restore_as.CONTROLLED_MARKER).write_text(restore_as.CONTROLLED_MARKER_VALUE+'\n',encoding='utf-8')
        return t

    def confirm(self,p:Path,d='restore.example.com') -> str:
        m=json.loads((p/'manifest.json').read_text(encoding='utf-8'))
        return restore_as.expected_confirm(m,d)

    def test_wordpress_config_remap(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'wp-config.php'; f.write_text("<?php\ndefine('DB_NAME','old');\ndefine('DB_USER','oldu');\ndefine('DB_PASSWORD','oldp');\n",encoding='utf-8')
            restore_as.rewrite_wordpress_config(f,'newdb','newuser','newsecret')
            s=f.read_text(encoding='utf-8')
            self.assertIn("define('DB_NAME', 'newdb');",s); self.assertIn("define('DB_USER', 'newuser');",s)
            self.assertIn("define('DB_PASSWORD', 'newsecret');",s)

    def test_dotenv_remap(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'.env'; f.write_text('DB_DATABASE=old\nDB_USERNAME=oldu\nDB_PASSWORD=oldp\nAPP_URL=https://example.com\n',encoding='utf-8')
            self.assertTrue(restore_as.rewrite_dotenv(f,'newdb','newu','newp','example.com','restore.example.com'))
            s=f.read_text(encoding='utf-8'); self.assertIn('DB_DATABASE=newdb',s); self.assertIn('DB_USERNAME=newu',s)
            self.assertIn('APP_URL=https://restore.example.com',s); self.assertNotIn('oldp',s)

    def test_imported_db_reexport_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); p=self.package(base); source=p/'mysql/source_db_1.sql.gz'
            def export(_db,out,**_kw): shutil.copy2(source,out); return Path(out)
            with mock.patch.object(restore_as.cloudpanel,'export_database',side_effect=export):
                restore_as.verify_imported_database(p,'source_db_1','target_db','clpctl')

    def test_wordpress_search_replace_is_serialization_safe(self):
        answers=['https://example.com','https://example.com','','https://restore.example.com','https://restore.example.com']; calls=[]
        def fake(_u,_r,args,**_kw): calls.append(args); return answers.pop(0)
        with mock.patch.object(restore_as,'_run_wp',side_effect=fake):
            out=restore_as.reconcile_wordpress_domain('u',Path('/tmp/site'),'example.com','restore.example.com')
        self.assertIn('restore.example.com',out['home'])
        search=next(c for c in calls if c[0]=='search-replace')
        self.assertIn('--all-tables-with-prefix',search); self.assertIn('--skip-columns=guid',search); self.assertIn('--precise',search)

    def test_existing_target_blocks_before_site_create(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); p=self.package(base); t=self.target(base)
            with mock.patch.object(restore_as.package_engine,'verify_package',return_value={'status':'PASS'}), \
                 mock.patch.object(restore_as.site_lifecycle,'ensure_domain_available',side_effect=site_lifecycle.SiteLifecycleError('exists')), \
                 mock.patch.object(restore_as.site_lifecycle,'create_site') as create:
                with self.assertRaises(site_lifecycle.SiteLifecycleError):
                    restore_as.restore_as(p,'restore.example.com',t,'clpctl',self.confirm(p))
            create.assert_not_called()

    def test_multi_db_blocks_before_site_create(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); p=self.package(base,2); t=self.target(base)
            with mock.patch.object(restore_as.package_engine,'verify_package',return_value={'status':'PASS'}), \
                 mock.patch.object(restore_as.site_lifecycle,'ensure_domain_available'), \
                 mock.patch.object(restore_as.restore_plan,'inspect_archive',return_value={'blockers':[]}), \
                 mock.patch.object(restore_as.site_lifecycle,'create_site') as create:
                with self.assertRaisesRegex(restore_as.RestoreAsError,'multi-database'):
                    restore_as.restore_as(p,'restore.example.com',t,'clpctl',self.confirm(p))
            create.assert_not_called()

    def test_orchestration_uses_new_identity_preserves_source_and_does_not_reuse_ssl(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); p=self.package(base); t=self.target(base)
            source=t/'home/alice/htdocs/example.com'; source.mkdir(parents=True); sentinel=source/'KEEP'; sentinel.write_text('keep',encoding='utf-8')
            identity=site_lifecycle.TargetSiteIdentity('restore.example.com','p07restore','sitepw','/home/p07restore/htdocs/restore.example.com')
            def create(_s,ident,**_kw): (t/ident.site_root.lstrip('/')).mkdir(parents=True)
            def extract(_a,staged):
                staged.mkdir(parents=True); (staged/'public').mkdir(); (staged/'public/index.php').write_text('<?php',encoding='utf-8')
                (staged/'wp-config.php').write_text("<?php\ndefine('DB_NAME','source_db_1');\ndefine('DB_USER','old');\ndefine('DB_PASSWORD','oldp');\n",encoding='utf-8')
            patches=[
              mock.patch.object(restore_as.package_engine,'verify_package',return_value={'status':'PASS'}),
              mock.patch.object(restore_as.site_lifecycle,'ensure_domain_available'),
              mock.patch.object(restore_as.site_lifecycle,'derive_target_identity',return_value=identity),
              mock.patch.object(restore_as,'source_vhost_template',return_value='Generic'),
              mock.patch.object(restore_as.site_lifecycle,'create_site',side_effect=create),
              mock.patch.object(restore_as.restore_plan,'inspect_archive',return_value={'blockers':[]}),
              mock.patch.object(restore_as.restore_apply,'extract_site_archive',side_effect=extract),
              mock.patch.object(restore_as.verify_engine,'verify_files',return_value={'status':'PASS'}),
              mock.patch.object(restore_as.verify_engine,'verify_sqlite',return_value={'status':'PASS'}),
              mock.patch.object(restore_as.cloudpanel,'add_database'), mock.patch.object(restore_as.cloudpanel,'import_database'),
              mock.patch.object(restore_as,'verify_imported_database'), mock.patch.object(restore_as.restore_new,'reconcile_site_ownership'),
              mock.patch.object(restore_as,'reconcile_wordpress_domain',return_value={'home':'https://restore.example.com','siteurl':'https://restore.example.com'}),
              mock.patch.object(restore_as.cloudpanel,'reset_permissions')]
            entered=[]
            try:
                for x in patches: entered.append(x.start())
                out=restore_as.restore_as(p,'restore.example.com',t,'clpctl',self.confirm(p))
            finally:
                for x in reversed(patches): x.stop()
            self.assertEqual(out['status'],'RESTORE_AS_VERIFIED'); self.assertNotEqual(out['target_site_user'],'alice')
            self.assertNotEqual(out['target_database'],'source_db_1'); self.assertFalse(out['source_ssl_reused'])
            self.assertFalse(out['dns_changed']); self.assertFalse(out['source_deleted']); self.assertEqual(sentinel.read_text(),'keep')


if __name__=='__main__': unittest.main()
