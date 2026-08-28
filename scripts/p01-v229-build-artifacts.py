#!/usr/bin/env python3
from pathlib import Path
import hashlib, importlib.util, json

ROOT=Path.cwd()
VERSION='2.29.0'
SOURCE_VERSION='2.28.0'
SOURCE_SCHEMA='2026082801'
TARGET_SCHEMA='2026082901'
MIGRATION='migrations/2026082901_v229_resource_domains.php'
FORMAL='28fc399d2d0ccc30531d6421d180db079ec571d9'
TREE='9545d334b626fce3968cdee92f09d13c58b2ae8e'
SOURCE='e010d484c8879737503a02612d0ba8cff1d2fd7d'


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    if s is None or s.loader is None: raise SystemExit('cannot load '+str(path))
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

base=load('base',ROOT/'proven/scripts/p01-build-release.py')
v2=load('v2',ROOT/'proven/scripts/p01-build-release-v2.py')
sha=lambda b: hashlib.sha256(b).hexdigest()
gate_only={'.gitignore','CHANGELOG.md','DEPLOY-HERE.txt','FULL-PACKAGE-NOTES.txt','README.md','UPGRADE-V2.txt','robots.txt'}
def runtime(files): return {k:v for k,v in files.items() if k!='release-manifest.json' and k not in gate_only and k!='VF-Start-Browser-Extension.zip'}

target_delivery=base.collect(ROOT/'candidate/src')
source_delivery=base.collect(ROOT/'production/src')
if target_delivery.get('VERSION.txt',b'').strip()!=VERSION.encode(): raise SystemExit('formal version mismatch')
if source_delivery.get('VERSION.txt',b'').strip()!=SOURCE_VERSION.encode(): raise SystemExit('source version mismatch')
target=runtime(target_delivery); source=runtime(source_delivery)
changed=sorted(k for k in target if k not in source or sha(target[k])!=sha(source[k]))
added=sorted(set(target)-set(source)); removed=sorted(set(source)-set(target))
if not changed: raise SystemExit('empty runtime delta')
required=[
 'app/FunctionalWorkspace.php','app/FunctionalWorkspaceCore.php','app/FunctionalWorkspaceShell.php',
 'app/ResourceAssetStore.php','app/SurfaceRepository.php','assets/workspace-create-bundle.js',
 'assets/workspace-rebaseline.css','assets/workspace-rebaseline.js','workspace-create.php','workspace-save.php',
 'workspace-visibility-action.php','resource-cover.php','resource-html.php','resource-media.php','topics.php',MIGRATION
]
for r in required:
    if r not in target: raise SystemExit('missing target runtime '+r)

manifest={
 'project':'VF Start','project_id':'P01','project_slug':'vf-start','component_id':'APP',
 'version':VERSION,'source_version':SOURCE_VERSION,'schema_version':TARGET_SCHEMA,'source_schema_version':SOURCE_SCHEMA,
 'release_type':'formal','stage':'FORMAL_ARTIFACT_GATE','deployable':True,'release_authorized':True,
 'source_commit':FORMAL,'source_tree':TREE,'production_source_commit':SOURCE,
 'schema_change':True,'schema_migrations':[MIGRATION],'runtime_data_included':False,'seed_user_business_data_included':False,
 'runtime_hashed_file_count':len(target),'runtime_files':{k:sha(v) for k,v in sorted(target.items())},
 'atomic_runtime_boundary':{'source_version':SOURCE_VERSION,'target_version':VERSION,'source_schema':SOURCE_SCHEMA,'target_schema':TARGET_SCHEMA,'source_app_gate_count':len(source),'target_app_gate_count':len(target),'added_files':added,'removed_files':removed,'runtime_delta':changed},
 'browser_extension':{'release_unit':'INDEPENDENT','released_this_round':False},
 'update':{'project_id':'P01','component_id':'APP','publication':'GATE_PROVEN_NOT_PUBLISHED','asset_name':'VF_Start_V2.29.0_UPDATE.zip','supported_from':[SOURCE_VERSION],'backup_required':True,'rollback_supported':True,'schema_migration_atomic':True},
 'resource_domains':{'domains':['start','channels','watch','topics'],'labels':['导航','频道','影视','专题'],'profile_table':'resource_domain_profiles','asset_file_table':'resource_asset_files','legacy_profile_table':'resource_surface_profiles','navigation_category_table':'categories','non_navigation_taxonomy':'resource_kind+tags'},
 'workspace_productization':{'public_private_scope':True,'large_library_navigation':True,'atomic_add':True,'atomic_edit':True,'attachment_delete_transactional':True,'legacy_split_mutation_fail_closed':True,'hosted_html_sandbox':True,'anonymous_public_isolated':True},
 'presentation_authority':{'interaction':'SINGLE_WORKSPACE','visual':'VF_ADMIN_SHELL_TEAL','presentation_flexible':True},
 'common_product_baseline':{'id':'VF-COMMON-PRODUCT-BASELINE@2.0','profile':'PERSONAL_SINGLE_ADMIN','current':True}
}
mb=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
full=dict(target_delivery); full['release-manifest.json']=mb
atomic=dict(target); atomic['release-manifest.json']=mb
repair=v2.build_repair(source,atomic,sha(target['app/UpdateManager.php']))
old="public const SOURCE_VERSION='2.21.14';\n    public const TARGET_VERSION='2.21.15';\n    public const TARGET_SCHEMA='2026080902';"
new="public const SOURCE_VERSION='2.28.0';\n    public const TARGET_VERSION='2.29.0';\n    public const SOURCE_SCHEMA='2026082801';\n    public const TARGET_SCHEMA='2026082901';\n    public const TARGET_MIGRATION='migrations/2026082901_v229_resource_domains.php';"
if repair.count(old)!=1: raise SystemExit('repair constant anchor mismatch')
repair=repair.replace(old,new,1)

old_db="private static function dbVerify(string $db): array {if(!extension_loaded('pdo_sqlite'))throw new RuntimeException('PDO_SQLITE is required.');$p=new PDO('sqlite:'.$db,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);$p->exec('PRAGMA foreign_keys=ON');$p->exec('PRAGMA busy_timeout=5000');$integrity=strtolower((string)$p->query('PRAGMA integrity_check')->fetchColumn());$fk=$p->query('PRAGMA foreign_key_check')->fetchAll();$head=(string)$p->query(\"SELECT COALESCE(MAX(version),'') FROM schema_migrations WHERE status='success'\")->fetchColumn();if($integrity!=='ok'||$fk||$head!==self::TARGET_SCHEMA)throw new RuntimeException('Database verification failed.');return ['integrity'=>$integrity,'foreign_key_errors'=>count($fk),'schema'=>$head];}"
new_db="private static function dbVerify(string $db,string $expectedSchema=self::TARGET_SCHEMA): array {if(!extension_loaded('pdo_sqlite'))throw new RuntimeException('PDO_SQLITE is required.');$p=new PDO('sqlite:'.$db,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);$p->exec('PRAGMA foreign_keys=ON');$p->exec('PRAGMA busy_timeout=5000');$integrity=strtolower((string)$p->query('PRAGMA integrity_check')->fetchColumn());$fk=$p->query('PRAGMA foreign_key_check')->fetchAll();$head=(string)$p->query(\"SELECT COALESCE(MAX(version),'') FROM schema_migrations WHERE status='success'\")->fetchColumn();if($integrity!=='ok'||$fk||$head!==$expectedSchema)throw new RuntimeException('Database verification failed for schema '.$expectedSchema.'; got '.$head);return ['integrity'=>$integrity,'foreign_key_errors'=>count($fk),'schema'=>$head];}"
if repair.count(old_db)!=1: raise SystemExit('dbVerify anchor mismatch')
repair=repair.replace(old_db,new_db,1)

migrate_method=r'''    private static function migrateDb(string $root,string $db): array {
        $path=rtrim($root,'/').'/'.self::TARGET_MIGRATION;if(!is_file($path)||is_link($path))throw new RuntimeException('Target migration file missing.');
        $def=require $path;if(!is_array($def)||($def['version']??'')!==self::TARGET_SCHEMA||!is_callable($def['up']??null))throw new RuntimeException('Target migration definition invalid.');
        $hash=hash_file('sha256',$path)?:'';if($hash==='')throw new RuntimeException('Target migration hash failed.');
        $p=new PDO('sqlite:'.$db,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);$p->exec('PRAGMA foreign_keys=ON');$p->exec('PRAGMA busy_timeout=5000');
        $p->exec("CREATE TABLE IF NOT EXISTS schema_migrations(id INTEGER PRIMARY KEY AUTOINCREMENT,version TEXT NOT NULL UNIQUE,migration_name TEXT NOT NULL,migration_sha256 TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,error_message TEXT NOT NULL DEFAULT '',source_version TEXT NOT NULL DEFAULT '',target_version TEXT NOT NULL DEFAULT '')");
        $q=$p->prepare('SELECT * FROM schema_migrations WHERE version=?');$q->execute([self::TARGET_SCHEMA]);$existing=$q->fetch(PDO::FETCH_ASSOC);
        if($existing&&($existing['status']??'')==='success'){if(!hash_equals((string)$existing['migration_sha256'],$hash))throw new RuntimeException('Target migration SHA changed.');return ['applied'=>false,'already_current'=>true,'schema'=>self::TARGET_SCHEMA,'sha256'=>$hash];}
        $started=gmdate('c');$name=(string)($def['name']??'V2.29 resource domains');
        $write=$p->prepare("INSERT INTO schema_migrations(version,migration_name,migration_sha256,started_at,finished_at,status,error_message,source_version,target_version) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(version) DO UPDATE SET migration_name=excluded.migration_name,migration_sha256=excluded.migration_sha256,started_at=excluded.started_at,finished_at=excluded.finished_at,status=excluded.status,error_message=excluded.error_message,source_version=excluded.source_version,target_version=excluded.target_version");
        $write->execute([self::TARGET_SCHEMA,$name,$hash,$started,'','running','',self::SOURCE_VERSION,self::TARGET_VERSION]);
        try{$p->beginTransaction();($def['up'])($p);$integrity=strtolower((string)$p->query('PRAGMA integrity_check')->fetchColumn());$fk=$p->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC);if($integrity!=='ok'||$fk)throw new RuntimeException('Migration integrity verification failed.');$write->execute([self::TARGET_SCHEMA,$name,$hash,$started,gmdate('c'),'success','',self::SOURCE_VERSION,self::TARGET_VERSION]);$p->commit();return ['applied'=>true,'already_current'=>false,'schema'=>self::TARGET_SCHEMA,'sha256'=>$hash];}catch(Throwable $e){if($p->inTransaction())$p->rollBack();throw $e;}
    }
'''
anchor="    public static function selfTest(): array"
if repair.count(anchor)!=1: raise SystemExit('selfTest anchor mismatch')
repair=repair.replace(anchor,migrate_method+anchor,1)

recover_old="self::dbVerify((string)$rt['db_file']);@unlink($journal);self::removeTree($stage);return true;"
recover_new="self::dbVerify((string)$rt['db_file'],self::SOURCE_SCHEMA);@unlink($journal);self::removeTree($stage);return true;"
if repair.count(recover_old)!=1: raise SystemExit('recover dbVerify anchor mismatch')
repair=repair.replace(recover_old,recover_new,1)

target_old="$target=self::verifyTarget($root);if(!$target['ok'])throw new RuntimeException('Target verification failed: '.implode(',',$target['errors']));$dbv=self::dbVerify($db);self::jsonWrite($journal,['target_version'=>self::TARGET_VERSION,'source_version'=>self::SOURCE_VERSION,'stage'=>$stage,'phase'=>'commit_ready','created_at'=>gmdate('c')]);"
target_new="$target=self::verifyTarget($root);if(!$target['ok'])throw new RuntimeException('Target verification failed: '.implode(',',$target['errors']));$migration=self::migrateDb($root,$db);self::jsonWrite($journal,['target_version'=>self::TARGET_VERSION,'source_version'=>self::SOURCE_VERSION,'stage'=>$stage,'phase'=>'migration_applied','created_at'=>gmdate('c')]);if(getenv('VF_ATOMIC_TEST_HARD_EXIT_AFTER_MIGRATION')==='1'){fwrite(STDERR,\"Injected hard interruption after migration.\\n\");exit(98);}if(getenv('VF_ATOMIC_TEST_FAIL_AFTER_MIGRATION')==='1')throw new RuntimeException('Injected failure after migration.');$dbv=self::dbVerify($db);self::jsonWrite($journal,['target_version'=>self::TARGET_VERSION,'source_version'=>self::SOURCE_VERSION,'stage'=>$stage,'phase'=>'commit_ready','created_at'=>gmdate('c')]);"
if repair.count(target_old)!=1: raise SystemExit('target migration insertion anchor mismatch')
repair=repair.replace(target_old,target_new,1)

catch_old="self::dbVerify((string)$rt['db_file']);if($journal!=='')@unlink($journal);"
catch_new="self::dbVerify((string)$rt['db_file'],self::SOURCE_SCHEMA);if($journal!=='')@unlink($journal);"
if repair.count(catch_old)!=1: raise SystemExit('rollback dbVerify anchor mismatch')
repair=repair.replace(catch_old,catch_new,1)

out=Path('/tmp/p01-v229-artifacts'); out.mkdir(parents=True,exist_ok=True)
rp=out/'repair-v2.29.0.php'; rp.write_text(repair,encoding='utf-8',newline='\n')
base.deterministic_zip(out/'VF-Start-V2.29.0-FULL.zip',full)
base.deterministic_zip(out/'VF_Start_V2.29.0_UPDATE.zip',{rp.name:rp.read_bytes()})
result={
 'project_id':'P01','version':VERSION,'source_version':SOURCE_VERSION,'formal_source':FORMAL,'formal_tree':TREE,'source_commit':SOURCE,
 'source_schema':SOURCE_SCHEMA,'schema':TARGET_SCHEMA,'schema_change':True,'schema_migrations':[MIGRATION],
 'runtime_source_files':len(source),'runtime_target_files':len(target),'runtime_added':added,'runtime_removed':removed,'runtime_delta':changed,'runtime_delta_count':len(changed),
 'atomic_update':True,'atomic_schema_migration':True,'release_published':False,'status':'FORMAL_ARTIFACT_BUILD_PASS'
}
(out/'P01-V2.29.0-FORMAL-GATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
arts=[p for p in sorted(out.iterdir()) if p.is_file()]
(out/'SHA256SUMS.txt').write_text(''.join(f'{base.sha256_file(p)}  {p.name}\n' for p in arts),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
