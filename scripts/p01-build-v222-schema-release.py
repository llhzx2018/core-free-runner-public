#!/usr/bin/env python3
from __future__ import annotations
import hashlib, importlib.util, json
from pathlib import Path

ROOT=Path.cwd()
VERSION='2.22.0'; SOURCE_VERSION='2.21.25'; SCHEMA='2026082801'; SOURCE_SCHEMA='2026080902'
CANDIDATE='2c159b4b7ecfc03e79eff2e6103f7e2c768ded08'
CANDIDATE_TREE='9116fe6cfc24d9a5a0a7070fb6af3f31bb079392'
SOURCE='6bc09cd152210183972dcb3f2c361eb65a4cadab'
cand=ROOT/'candidate'/'src'; prod=ROOT/'production'/'src'; out=Path('/tmp/p01-v222-artifacts')

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise SystemExit(f'cannot load {path}')
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
base=load('p01_base',ROOT/'proven'/'scripts'/'p01-build-release.py')
v2=load('p01_v2',ROOT/'proven'/'scripts'/'p01-build-release-v2.py')
def sha(b): return hashlib.sha256(b).hexdigest()
gate_only={'.gitignore','CHANGELOG.md','DEPLOY-HERE.txt','FULL-PACKAGE-NOTES.txt','README.md','UPGRADE-V2.txt','robots.txt'}
def runtime(files): return {k:v for k,v in files.items() if k!='release-manifest.json' and k not in gate_only and k!='VF-Start-Browser-Extension.zip'}

target_delivery=base.collect(cand); source_delivery=base.collect(prod)
if target_delivery.get('VERSION.txt',b'').strip()!=VERSION.encode(): raise SystemExit('candidate VERSION mismatch')
if source_delivery.get('VERSION.txt',b'').strip()!=SOURCE_VERSION.encode(): raise SystemExit('source VERSION mismatch')
target=runtime(target_delivery); source=runtime(source_delivery)
added=sorted(set(target)-set(source)); removed=sorted(set(source)-set(target))
changed=sorted(k for k in target if k not in source or sha(target[k])!=sha(source[k]))
if not changed: raise SystemExit('empty runtime delta')
for required in ['app/CommonBaseline.php','system-info.php','system-baseline.php','system.php','update.php','data-safety.php','cli/baseline-verify.php','app/SurfaceRepository.php','cli/surface-verify.php','migrations/2026082801_v222_multi_surface.php','surfaces.php','channels.php','watch.php','surface-manager.php']:
    if required not in target: raise SystemExit(f'missing V2.22 runtime file {required}')
ext=json.loads(target_delivery['browser-extension/manifest.json'].decode('utf-8'))
if str(ext.get('version'))!='1.6.4': raise SystemExit('browser helper drift')
manifest={
 'project':'VF Start','project_id':'P01','project_slug':'vf-start','component_id':'APP',
 'version':VERSION,'source_version':SOURCE_VERSION,'schema_version':SCHEMA,'source_schema_version':SOURCE_SCHEMA,
 'release_type':'formal','stage':'FORMAL_ARTIFACT_GATE','deployable':True,'release_authorized':False,
 'source_commit':CANDIDATE,'source_tree':CANDIDATE_TREE,'production_source_commit':SOURCE,
 'schema_change':True,'schema_migrations':['2026082801_v222_multi_surface.php'],
 'runtime_data_included':False,'seed_user_business_data_included':False,
 'runtime_hashed_file_count':len(target),'runtime_files':{k:sha(v) for k,v in sorted(target.items())},
 'atomic_runtime_boundary':{'source_version':SOURCE_VERSION,'target_version':VERSION,'source_app_gate_count':len(source),'target_app_gate_count':len(target),'added_files':added,'removed_files':removed,'runtime_delta':changed},
 'browser_extension':{'version':'1.6.4','release_unit':'INDEPENDENT','released_this_round':False,'mechanical_version_bump':False},
 'update':{'project_id':'P01','component_id':'APP','manifest_truth':'llhzx2018/core-updates/projects/P01.json','release_truth':'GitHub Release','asset_name':f'VF-Start-V{VERSION}-UPDATE.zip','legacy_asset_name':f'VF_Start_V{VERSION}_UPDATE.zip','supported_from':[SOURCE_VERSION],'backup_required':True,'rollback_supported':True},
 'multi_surface':{'surfaces':['start','channels','watch'],'profile_table':'resource_surface_profiles','no_profile_semantics':'START','automatic_reclassification':False},
 'common_product_baseline':{'id':'VF-COMMON-PRODUCT-BASELINE@2.0','profile':'PERSONAL_SINGLE_ADMIN','current':True}
}
mb=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
full=dict(target_delivery); full['release-manifest.json']=mb
atomic=dict(target); atomic['release-manifest.json']=mb
repair=v2.build_repair(source,atomic,sha(target['app/UpdateManager.php']))

def one(old,new,label):
    global repair
    n=repair.count(old)
    if n!=1: raise SystemExit(f'{label} anchor mismatch: {n}')
    repair=repair.replace(old,new,1)

one("public const SOURCE_VERSION='2.21.14';\n    public const TARGET_VERSION='2.21.15';\n    public const TARGET_SCHEMA='2026080902';",
    "public const SOURCE_VERSION='2.21.25';\n    public const TARGET_VERSION='2.22.0';\n    public const SOURCE_SCHEMA='2026080902';\n    public const TARGET_SCHEMA='2026082801';",'version/schema constants')
one("private static function dbVerify(string $db): array {", "private static function dbVerify(string $db,string $expectedSchema=self::TARGET_SCHEMA): array {", 'dbVerify signature')
one("if($integrity!=='ok'||$fk||$head!==self::TARGET_SCHEMA)throw new RuntimeException('Database verification failed.');", "if($integrity!=='ok'||$fk||$head!==$expectedSchema)throw new RuntimeException('Database verification failed.');", 'dbVerify schema comparison')

migration_method="""private static function migrateDb(string $root,array $rt,string $db): void {
        require_once $root.'/app/bootstrap.php';
        $p=new PDO('sqlite:'.$db,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false]);
        $p->exec('PRAGMA foreign_keys=ON');$p->exec('PRAGMA busy_timeout=5000');
        (new VfMigrationRunner($p))->migrate(self::SOURCE_VERSION,self::TARGET_VERSION);
        $p=null;
    }
    """
one("private static function snapshotDb(string $db,string $dest): void {", migration_method+"private static function snapshotDb(string $db,string $dest): void {", 'migration method insertion')

one("$s=self::verifySource($root);if(!$s['ok'])throw new RuntimeException('Interrupted Atomic source recovery verification failed.');self::dbVerify((string)$rt['db_file']);@unlink($journal);",
    "$s=self::verifySource($root);if(!$s['ok'])throw new RuntimeException('Interrupted Atomic source recovery verification failed.');self::dbVerify((string)$rt['db_file'],self::SOURCE_SCHEMA);@unlink($journal);",'interrupted rollback schema')

one("$cfg['version']=self::TARGET_VERSION;$j=json_encode($cfg,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);if($j===false)throw new RuntimeException('Config serialize failed.');self::writeExact($config,$j.\"\\n\",0600);$target=self::verifyTarget($root);",
    "$cfg['version']=self::TARGET_VERSION;$j=json_encode($cfg,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);if($j===false)throw new RuntimeException('Config serialize failed.');self::writeExact($config,$j.\"\\n\",0600);self::migrateDb($root,$rt,$db);self::jsonWrite($journal,['target_version'=>self::TARGET_VERSION,'source_version'=>self::SOURCE_VERSION,'stage'=>$stage,'phase'=>'database_migrated','created_at'=>gmdate('c')]);$target=self::verifyTarget($root);",'migration call')

one("if($configBytes!=='')self::writeExact((string)$rt['config_file'],$configBytes,0600);$after=self::verifySource($root);if(!$after['ok'])throw new RuntimeException('Rollback source verification failed.');self::dbVerify((string)$rt['db_file']);if($journal!=='')@unlink($journal);",
    "if($configBytes!=='')self::writeExact((string)$rt['config_file'],$configBytes,0600);$after=self::verifySource($root);if(!$after['ok'])throw new RuntimeException('Rollback source verification failed.');self::dbVerify((string)$rt['db_file'],self::SOURCE_SCHEMA);if($journal!=='')@unlink($journal);",'catch rollback schema')

# Ensure the schema-aware repair contains exactly the intended migration hooks.
for needle in ["public const SOURCE_SCHEMA='2026080902';","public const TARGET_SCHEMA='2026082801';","self::migrateDb($root,$rt,$db);","phase'=>'database_migrated'","self::dbVerify((string)$rt['db_file'],self::SOURCE_SCHEMA)"]:
    if needle not in repair: raise SystemExit(f'missing schema-aware repair marker: {needle}')
if repair.count("self::dbVerify((string)$rt['db_file'],self::SOURCE_SCHEMA)")!=2:
    raise SystemExit('source-schema rollback verification count mismatch')

out.mkdir(parents=True,exist_ok=True)
rp=out/f'server-update-v{VERSION}-repair.php'; rp.write_text(repair,encoding='utf-8',newline='\n')
base.deterministic_zip(out/f'VF-Start-V{VERSION}-FULL.zip',full)
base.deterministic_zip(out/f'VF-Start-V{VERSION}-UPDATE.zip',{rp.name:rp.read_bytes()})
base.deterministic_zip(out/f'VF_Start_V{VERSION}_UPDATE.zip',{rp.name:rp.read_bytes()})
result={'project_id':'P01','version':VERSION,'source_version':SOURCE_VERSION,'candidate':CANDIDATE,'candidate_tree':CANDIDATE_TREE,'source_commit':SOURCE,'source_schema':SOURCE_SCHEMA,'schema':SCHEMA,'schema_migration':'2026082801_v222_multi_surface.php','runtime_source_files':len(source),'runtime_target_files':len(target),'runtime_added':added,'runtime_removed':removed,'runtime_delta':changed,'runtime_delta_count':len(changed),'schema_aware_atomic_update':True,'status':'BUILD_PASS'}
(out/'P01-V2.22.0-ARTIFACT-GATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
arts=[p for p in sorted(out.iterdir()) if p.is_file()]
(out/'SHA256SUMS.txt').write_text(''.join(f'{base.sha256_file(p)}  {p.name}\n' for p in arts),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
