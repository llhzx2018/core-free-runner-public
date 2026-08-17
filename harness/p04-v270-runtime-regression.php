<?php
declare(strict_types=1);
$root=$argv[1]??'';$cred=$argv[2]??'';$out=$argv[3]??'/tmp/p04-v270-regression-v3.json';
if($root===''||$cred===''||!is_file($root.'/bootstrap.php'))throw new RuntimeException('regression env missing');
chdir($root);require $root.'/bootstrap.php';
$g=[];function gate(string $n,bool $v):void{global $g;if(!$v)throw new RuntimeException('FAIL '.$n);$g[$n]='PASS';}
gate('VERSION',defined('VF_INFRA_VERSION')&&VF_INFRA_VERSION==='2.7.0');
gate('AUTH_PASSWORD',Auth::verifyPassword($cred));
$pdo=Database::connection();
gate('SCHEMA_14',(int)$pdo->query("SELECT COALESCE(MAX(version),0) FROM schema_migrations WHERE status='success'")->fetchColumn()===14);
$stmt=$pdo->query('PRAGMA integrity_check');$integrity=(string)$stmt->fetchColumn();$stmt->closeCursor();unset($stmt);gate('SQLITE_INTEGRITY',$integrity==='ok');
$stmt=$pdo->query('PRAGMA foreign_key_check');$fk=$stmt->fetchAll();$stmt->closeCursor();unset($stmt);gate('FOREIGN_KEYS',$fk===[]);
$tables=['domains','dns_zones','dns_records','compute_instances','assets','asset_relations','provider_accounts','provider_billing_snapshots','alerts','jobs','backups','restore_runs','update_history'];
foreach($tables as $t){$stmt=$pdo->prepare("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?");$stmt->execute([$t]);$exists=(int)$stmt->fetchColumn()===1;$stmt->closeCursor();unset($stmt);gate('TABLE_'.strtoupper($t),$exists);}
gate('PROVIDER_READ_LAYER',class_exists('VFInfra\\Core\\ProviderBillingQueryService'));
gate('SEARCH_LAYER',class_exists('VFInfra\\Core\\GlobalSearchService'));
gate('RELATION_LAYER',class_exists('VFInfra\\Core\\AssetQueryService'));
gate('JOB_ENGINE',class_exists('VFInfra\\Core\\JobEngine'));
gate('ONLINE_UPDATE',class_exists('VFInfra\\Core\\Update\\OnlineUpdateService'));
gate('UPDATE_HISTORY_CLASS',class_exists('VFInfra\\Core\\Update\\UpdateHistoryService'));
gate('ATOMIC_HANDOFF',class_exists('VFInfra\\Core\\Update\\OnlineUpdateHandoff'));
$experience=new VFInfra\Core\PersonalInfraExperienceService();
gate('TODAY_READ',is_array($experience->today()));
gate('BILLING_READ',is_array($experience->money()));
gate('INFRA_READ',is_array($experience->infrastructure()));
gate('SEARCH_READ',is_array($experience->search('nothing')));
unset($experience);
$history=new VFInfra\Core\Update\UpdateHistoryService();$op='v270-reg-'.Support::randomHex(6);$history->start($op,'2.6.0','2.7.0',str_repeat('a',64),str_repeat('b',64));$history->finish($op,'success');$rows=$history->list(20);gate('UPDATE_HISTORY',count(array_filter($rows,fn($r)=>($r['operation_id']??'')===$op&&($r['result']??'')==='success'))===1);unset($rows,$history);
gc_collect_cycles();
$marker='v270-regression-'.Support::randomHex(4);Settings::set('site_name',$marker);
$svc=new BackupService();$backup=$svc->create('manual','V2.7 regression restore smoke',true);$bid=(int)($backup['id']??0);gate('BACKUP_CREATED',$bid>0);
$verified=$svc->verify($bid);gate('BACKUP_INTEGRITY',($verified['metadata']['integrity_status']??'')==='ok');gate('BACKUP_FK',($verified['metadata']['foreign_key_status']??'')==='ok');unset($verified);
Settings::set('site_name','mutated-'.Support::randomHex(4));$restored=$svc->restore($bid,$cred);Settings::clearCache();gate('RESTORE_STATUS',($restored['status']??'')==='success');gate('RESTORE_DATA',Settings::get('site_name','')===$marker);gate('RESTORE_CREDENTIAL',Auth::verifyPassword($cred));
$pdo=Database::connection();$stmt=$pdo->query('PRAGMA integrity_check');$postIntegrity=(string)$stmt->fetchColumn();$stmt->closeCursor();unset($stmt);gate('POST_RESTORE_INTEGRITY',$postIntegrity==='ok');$stmt=$pdo->query('PRAGMA foreign_key_check');$postFk=$stmt->fetchAll();$stmt->closeCursor();unset($stmt);gate('POST_RESTORE_FK',$postFk===[]);
$online=file_get_contents($root.'/app/Core/Update/OnlineUpdateService.php');$p1=strpos($online,"create('pre_update'");$p2=strpos($online,'installRepairEntrypoint');gate('ONLINE_PREUPDATE_BACKUP_ORDER',$p1!==false&&$p2!==false&&$p1<$p2);gate('ATOMIC_SINGLE_FILE_CONTRACT',str_contains($online,'必须且只能包含声明的单文件 repair'));gate('HANDOFF_WRITE_CONTRACT',str_contains($online,'OnlineUpdateHandoff::writePlan'));
$result=['status'=>'PASS','version'=>'2.7.0','schema'=>14,'gates'=>$g,'gate_count'=>count($g)];file_put_contents($out,json_encode($result,JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT)."\n");echo 'P04_V270_RUNTIME_REGRESSION_V3_PASS gates='.count($g)."\n";
