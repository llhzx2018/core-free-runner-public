<?php
declare(strict_types=1);

/**
 * P05 · VF SEO v1.1.12 Demo Dataset Bridge
 *
 * Production-safe rules:
 * - requires the current live vf_session; no password prompt;
 * - POST requires same-site origin + session-derived CSRF;
 * - writes deterministic demo IDs only;
 * - never touches admins, sessions, oauth_credentials, backups, runtime.env or real credentials;
 * - can be re-run idempotently and demo rows can be removed independently.
 */

use VfSeo\PhpRuntime\Config;
use VfSeo\PhpRuntime\Database;
use VfSeo\PhpRuntime\Security;

const P05_DEMO_VERSION = 'P05-DEMO-DATASET@1';
const P05_REQUIRED_VERSION = '1.1.12';

$root = __DIR__;
require_once $root . '/php/src/RuntimePaths.php';
require_once $root . '/php/src/Config.php';
require_once $root . '/php/src/Database.php';
require_once $root . '/php/src/Security.php';

function h(string $v): string { return htmlspecialchars($v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function demoId(string $key): string {
    $hex = hash('sha256', 'P05-DEMO:' . $key);
    return substr($hex,0,8).'-'.substr($hex,8,4).'-4'.substr($hex,13,3).'-8'.substr($hex,17,3).'-'.substr($hex,20,12);
}
function utc(int $daysAgo = 0, int $hoursAgo = 0): string { return gmdate('Y-m-d\TH:i:s.000\Z', time() - ($daysAgo * 86400) - ($hoursAgo * 3600)); }
function day(int $daysAgo = 0): string { return gmdate('Y-m-d', time() - $daysAgo * 86400); }
function jsonText(mixed $v): string { return json_encode($v, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR); }

function upsert(PDO $pdo, string $table, array $row): void {
    $cols = array_keys($row);
    $names = implode(',', array_map(static fn($x) => '"'.$x.'"', $cols));
    $params = implode(',', array_map(static fn($x) => ':'.$x, $cols));
    $updates = implode(',', array_map(static fn($x) => '"'.$x.'"=excluded."'.$x.'"', array_values(array_filter($cols, static fn($x) => $x !== 'id'))));
    $sql = 'INSERT INTO "'.$table.'"('.$names.') VALUES('.$params.') ON CONFLICT(id) DO UPDATE SET '.$updates;
    $st = $pdo->prepare($sql);
    foreach ($row as $k => $v) $st->bindValue(':'.$k, $v, is_int($v) ? PDO::PARAM_INT : ($v === null ? PDO::PARAM_NULL : PDO::PARAM_STR));
    $st->execute();
}
function insertIgnore(PDO $pdo, string $sql, array $params): void {
    $st=$pdo->prepare($sql);
    foreach($params as $k=>$v) $st->bindValue(is_int($k)?$k+1:':'.ltrim((string)$k,':'),$v,is_int($v)?PDO::PARAM_INT:($v===null?PDO::PARAM_NULL:PDO::PARAM_STR));
    $st->execute();
}
function tableExists(PDO $pdo, string $name): bool {
    $st=$pdo->prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"); $st->execute([':n'=>$name]); return (bool)$st->fetchColumn();
}
function currentSession(Database $db, Config $config): ?array {
    $token = $_COOKIE['vf_session'] ?? null;
    if (!is_string($token) || $token === '') return null;
    $row = $db->one("SELECT a.id admin_id,a.username,s.id session_id,s.csrf_token,s.expires_at,s.absolute_expires_at,s.last_seen_at FROM sessions s JOIN admins a ON a.id=s.admin_id WHERE s.token_hash=:hash AND s.revoked_at IS NULL LIMIT 1", ['hash'=>Security::sha256($token)]);
    if ($row === null) return null;
    $now=time(); $e=strtotime((string)$row['expires_at']); $a=strtotime((string)$row['absolute_expires_at']); $l=strtotime((string)$row['last_seen_at']);
    if ($e===false||$a===false||$l===false||$e<=$now||$a<=$now||$l<=$now-$config->sessionIdleSeconds) return null;
    return $row;
}
function originAllowed(): bool {
    if (strtolower(trim((string)($_SERVER['HTTP_SEC_FETCH_SITE'] ?? ''))) === 'cross-site') return false;
    $origin=trim((string)($_SERVER['HTTP_ORIGIN'] ?? '')); if($origin==='') return true;
    $parts=parse_url($origin); if(!is_array($parts)||!isset($parts['scheme'],$parts['host'])) return false;
    if(!in_array(strtolower((string)$parts['scheme']),['http','https'],true)) return false;
    $host=strtolower(trim((string)($_SERVER['HTTP_HOST'] ?? '')));
    $oh=strtolower((string)$parts['host']).(isset($parts['port'])?':'.(int)$parts['port']:'');
    return $host!=='' && hash_equals($host,$oh);
}

function demoProjectIds(): array { return array_map(static fn($i)=>demoId('project-'.$i), range(1,5)); }
function demoSiteIds(): array { return array_map(static fn($i)=>demoId('site-'.$i), range(1,8)); }

function clearDemo(PDO $pdo): array {
    $siteIds=demoSiteIds(); $projectIds=demoProjectIds();
    $pdo->beginTransaction();
    try {
        if (tableExists($pdo,'user_decisions')) {
            foreach(range(1,16) as $i) $pdo->prepare('DELETE FROM user_decisions WHERE id=?')->execute([demoId('decision-'.$i)]);
        }
        if (tableExists($pdo,'notes')) {
            foreach(range(1,16) as $i) $pdo->prepare('DELETE FROM notes WHERE id=?')->execute([demoId('note-'.$i)]);
        }
        foreach($siteIds as $id) $pdo->prepare('DELETE FROM websites WHERE id=?')->execute([$id]);
        foreach($projectIds as $id) $pdo->prepare('DELETE FROM projects WHERE id=?')->execute([$id]);
        foreach(['GSC','GA4'] as $p) $pdo->prepare('DELETE FROM provider_accounts WHERE id=?')->execute([demoId('provider-account-'.$p)]);
        $pdo->commit();
        return ['projects'=>0,'websites'=>0,'queries'=>0,'pages'=>0,'searchFacts'=>0,'analyticsFacts'=>0];
    } catch(Throwable $e) { if($pdo->inTransaction())$pdo->rollBack(); throw $e; }
}

function ensureAuditRule(PDO $pdo, string $key, string $name, string $type, string $severity, string $recommendation): string {
    $st=$pdo->prepare('SELECT id FROM audit_rules WHERE rule_key=? LIMIT 1'); $st->execute([$key]); $rid=$st->fetchColumn();
    if(!$rid){ $rid=demoId('audit-rule-'.$key); upsert($pdo,'audit_rules',['id'=>$rid,'rule_key'=>$key,'display_name_zh'=>$name,'category'=>'SEO','rule_type'=>$type,'enabled'=>1,'created_at'=>utc(30)]); }
    $st=$pdo->prepare('SELECT id FROM audit_rule_versions WHERE rule_id=? AND version=1 LIMIT 1'); $st->execute([$rid]); $vid=$st->fetchColumn();
    if(!$vid){ $vid=demoId('audit-rule-version-'.$key); upsert($pdo,'audit_rule_versions',['id'=>$vid,'rule_id'=>$rid,'version'=>1,'severity_default'=>$severity,'authority'=>'VF-SEO@1.1','authority_version'=>'1.1','description'=>$name,'check_contract'=>jsonText(['ruleKey'=>$key]),'recommendation'=>$recommendation,'introduced_at'=>utc(30),'deprecated_at'=>null]); }
    return (string)$vid;
}

function seedDemo(PDO $pdo): array {
    clearDemo($pdo);
    $projects=[
      ['[演示] Kewaro 工具矩阵','工具站、导航与效率产品的 SEO 增长组合。'],
      ['[演示] 内容增长实验室','中文内容站、教程与专题的搜索增长实验。'],
      ['[演示] Micro SaaS 出海','英文 SaaS 与 AI 产品的海外获客样本。'],
      ['[演示] 电商转化项目','商品页、类目页与转化型内容的 SEO 样本。'],
      ['[演示] 本地服务增长','本地业务、品牌词与长尾词样本。'],
    ];
    $pids=demoProjectIds();
    foreach($projects as $i=>$p) upsert($pdo,'projects',['id'=>$pids[$i],'name'=>$p[0],'description'=>$p[1],'created_at'=>utc(120-$i*7),'updated_at'=>utc($i),'archived_at'=>null]);

    $sites=[
      [0,'[演示] ToolBox Pro','https://toolbox.example/','HIGH','zh-CN','CN','TOOL'],
      [0,'[演示] Start Hub','https://start-hub.example/','NORMAL','zh-CN','CN','DIRECTORY'],
      [1,'[演示] SEO 学习站','https://seo-lab.example/','HIGH','zh-CN','CN','CONTENT'],
      [1,'[演示] AI 搜索专题','https://ai-search.example/','NORMAL','zh-CN','CN','CONTENT'],
      [2,'[演示] Indie Metrics','https://indie-metrics.example/','HIGH','en-US','US','SAAS'],
      [2,'[演示] Prompt Ops','https://prompt-ops.example/','NORMAL','en-US','US','SAAS'],
      [3,'[演示] North Shop','https://north-shop.example/','HIGH','en-US','US','ECOMMERCE'],
      [4,'[演示] City Repair','https://city-repair.example/','NORMAL','en-US','US','LOCAL'],
    ];
    $sids=demoSiteIds();
    foreach($sites as $i=>$s) upsert($pdo,'websites',['id'=>$sids[$i],'project_id'=>$pids[$s[0]],'name'=>$s[1],'url'=>$s[2],'business_value'=>$s[3],'language'=>$s[4],'country_code'=>$s[5],'site_type'=>$s[6],'created_at'=>utc(90-$i*3),'updated_at'=>utc($i),'archived_at'=>null]);

    foreach(['GSC','GA4'] as $provider) upsert($pdo,'provider_accounts',['id'=>demoId('provider-account-'.$provider),'provider'=>$provider,'external_account_id'=>'demo-'.$provider.'-readonly','display_name'=>'[演示] '.$provider.' 只读数据源','state'=>'ACTIVE','reconnect_required'=>0,'created_at'=>utc(80)]);
    $states=['FRESH','FRESH','STALE','AUTH_ERROR','FRESH','PARTIAL','FAILED','RATE_LIMITED'];
    $sourceIds=[];
    foreach($sites as $i=>$s){
      foreach(['GSC','GA4'] as $provider){
        $prop=demoId('property-'.$provider.'-'.$i); $account=demoId('provider-account-'.$provider);
        upsert($pdo,'provider_properties',['id'=>$prop,'provider_account_id'=>$account,'external_property_id'=>'demo:'.$provider.':'.$i,'display_name'=>$s[1].' · '.$provider,'metadata'=>jsonText(['demo'=>true,'property'=>$s[2]]),'created_at'=>utc(75)]);
        $sid=demoId('source-'.$provider.'-'.$i); $sourceIds[$provider][$i]=$sid;
        $state=$provider==='GSC'?$states[$i]:($i%3===0?'STALE':'FRESH');
        upsert($pdo,'data_sources',['id'=>$sid,'website_id'=>$sids[$i],'provider_property_id'=>$prop,'provider'=>$provider,'state'=>$state,'last_good_at'=>utc($state==='FRESH'?0:2),'last_sync_at'=>utc($state==='FRESH'?0:2),'next_sync_at'=>utc(0,-1),'next_retry_at'=>in_array($state,['FAILED','AUTH_ERROR','RATE_LIMITED'],true)?utc(0,-2):null,'last_error_code'=>$state==='AUTH_ERROR'?'DEMO_AUTH_EXPIRED':($state==='FAILED'?'DEMO_UPSTREAM_503':($state==='RATE_LIMITED'?'DEMO_RATE_LIMITED':null)),'requires_action'=>in_array($state,['FAILED','AUTH_ERROR'],true)?1:0,'created_at'=>utc(75),'updated_at'=>utc(0)]);
        $run=demoId('sync-run-'.$provider.'-'.$i); upsert($pdo,'sync_runs',['id'=>$run,'data_source_id'=>$sid,'grain'=>'DAILY','state'=>'COMPLETE','finality'=>'FINAL','freshness'=>$state==='FRESH'?'FRESH':'STALE','started_at'=>utc(0,2),'finished_at'=>utc(0,1),'checkpoint'=>jsonText(['demo'=>true,'days'=>90]),'error_code'=>null,'correlation_id'=>demoId('sync-correlation-'.$provider.'-'.$i)]);
      }
    }

    $queryTemplates=['seo 工具','关键词研究','google seo','网站收录','seo 检查','ai seo','独立站 seo','搜索流量','内容优化','technical seo'];
    $pagePaths=['/','/pricing','/features','/blog/seo-guide','/blog/ai-search','/tools/keyword','/case-study','/about'];
    $queryIds=[]; $pageIds=[]; $searchFacts=0; $analyticsFacts=0;
    foreach($sites as $i=>$s){
      foreach($pagePaths as $pi=>$path){ $pid=demoId('page-'.$i.'-'.$pi); $pageIds[$i][$pi]=$pid; $url=rtrim($s[2],'/').$path; upsert($pdo,'pages',['id'=>$pid,'website_id'=>$sids[$i],'url'=>$url,'canonical_url'=>$url,'created_at'=>utc(70-$pi),'updated_at'=>utc($pi)]); }
      foreach($queryTemplates as $qi=>$q){
        $qid=demoId('query-'.$i.'-'.$qi); $queryIds[$i][$qi]=$qid; $label=($i>=4?['seo tools','keyword research','google ranking','site audit','search traffic','ai seo','saas seo','content optimization','technical seo','organic growth'][$qi]:$q);
        upsert($pdo,'queries',['id'=>$qid,'website_id'=>$sids[$i],'observed_query'=>$label,'first_observed_on'=>day(89-$qi),'created_at'=>utc(89-$qi)]);
        insertIgnore($pdo,'INSERT OR IGNORE INTO query_page_relations(query_id,page_id,first_observed_on,last_observed_on) VALUES(?,?,?,?)',[$qid,$pageIds[$i][$qi%count($pagePaths)],day(89-$qi),day(0)]);
      }
      for($d=89;$d>=0;$d--){
        foreach($queryTemplates as $qi=>$unused){
          $impr=160+($i*70)+($qi*43)+(89-$d)*4; $season=(($d+$qi)%7)-3; $pos=max(1.4,22-($qi*1.35)-((89-$d)*0.035)+$i*.25); if($qi===4 && $d<30)$pos+=4;
          $ctr=max(.002,min(.24,.22/($pos+1)+$qi*.001)); $clicks=max(0,(int)round($impr*$ctr+$season));
          $id=demoId('search-'.$i.'-'.$qi.'-'.$d); upsert($pdo,'search_observation_daily',['id'=>$id,'observed_on'=>day($d),'website_id'=>$sids[$i],'query_id'=>$queryIds[$i][$qi],'page_id'=>$pageIds[$i][$qi%count($pagePaths)],'dimension_grain'=>'QUERY_PAGE','dimension_value'=>jsonText(['device'=>$qi%3===0?'MOBILE':'DESKTOP','country'=>$s[5]]),'clicks'=>$clicks,'impressions'=>$impr,'ctr'=>$impr>0?$clicks/$impr:0,'position'=>$pos,'sync_run_id'=>demoId('sync-run-GSC-'.$i),'finality'=>$d<2?'PRELIMINARY':'FINAL','freshness'=>$states[$i]==='FRESH'?'FRESH':'STALE','source_key'=>'demo:gsc:'.$i.':'.$qi.':'.day($d)]); $searchFacts++;
        }
        foreach(array_slice($pagePaths,0,6) as $pi=>$unused){
          $sessions=25+$i*8+$pi*5+(89-$d); $users=max(1,$sessions-(3+$pi)); $views=$sessions+(5+$pi*2); $eng=min(.86,.48+$pi*.035); $events=(int)round($sessions*(.03+$pi*.008));
          upsert($pdo,'analytics_observation_daily',['id'=>demoId('analytics-'.$i.'-'.$pi.'-'.$d),'observed_on'=>day($d),'website_id'=>$sids[$i],'page_id'=>$pageIds[$i][$pi],'users'=>$users,'sessions'=>$sessions,'views'=>$views,'engagement_rate'=>$eng,'key_events'=>$events,'sync_run_id'=>demoId('sync-run-GA4-'.$i),'finality'=>$d<2?'PRELIMINARY':'FINAL','freshness'=>'FRESH','source_key'=>'demo:ga4:'.$i.':'.$pi.':'.day($d)]); $analyticsFacts++;
        }
      }
    }

    $oppTypes=['POSITION_4_10','POSITION_11_20','HIGH_IMPRESSION_LOW_CTR','RISING_KEYWORD','DECLINING_KEYWORD','RISING_PAGE','DECLINING_PAGE','NEW_OBSERVED_EFFECTIVE_KEYWORD','HIGH_IMPRESSION_NO_CLICK','MULTI_PAGE_COMPETITION_CANDIDATE'];
    foreach($sites as $i=>$s) foreach($oppTypes as $oi=>$type){ $subjectType=$oi>=5&&$oi<=6?'PAGE':'QUERY'; $subject=$subjectType==='PAGE'?$pageIds[$i][$oi%6]:$queryIds[$i][$oi%10]; upsert($pdo,'opportunities',['id'=>demoId('opp-'.$i.'-'.$oi),'website_id'=>$sids[$i],'subject_type'=>$subjectType,'subject_id'=>$subject,'opportunity_type'=>$type,'lifecycle_state'=>$oi%4===0?'ACKNOWLEDGED':'NEW','priority_band'=>$oi%5===0?'P1':($oi%3===0?'P2':'P3'),'evidence'=>jsonText(['demo'=>true,'impressions'=>500+$oi*120,'position'=>3+$oi,'changePercent'=>$oi%2===0?38:-31]),'source_state'=>$states[$i],'first_seen_at'=>utc(18-$oi),'last_seen_at'=>utc($oi%3),'identity_key'=>'demo:'.$i.':'.$type]); }

    $alertTypes=['TRAFFIC_DROP','DATA_SOURCE_DISCONNECT','LONG_STALE_SYNC','P1_OPPORTUNITY','CRITICAL_AUDIT'];
    foreach($sites as $i=>$s) foreach($alertTypes as $ai=>$type){ if(($i+$ai)%2!==0)continue; upsert($pdo,'alerts',['id'=>demoId('alert-'.$i.'-'.$ai),'website_id'=>$sids[$i],'alert_type'=>$type,'severity'=>$type==='CRITICAL_AUDIT'?'CRITICAL':($type==='LONG_STALE_SYNC'?'MEDIUM':'HIGH'),'state'=>$ai===4&&$i%3===0?'RESOLVED':'OPEN','evidence'=>jsonText(['demo'=>true,'summary'=>'用于产品评审的演示告警','value'=>20+$i*7+$ai]),'dedupe_key'=>'demo:alert:'.$i.':'.$type,'created_at'=>utc(10-$ai),'resolved_at'=>$ai===4&&$i%3===0?utc(1):null]); }

    foreach($sites as $i=>$s){
      foreach(['流量上涨','标题改版','Canonical 调整','内容更新'] as $ci=>$desc){ upsert($pdo,'seo_change_events',['id'=>demoId('change-'.$i.'-'.$ci),'website_id'=>$sids[$i],'page_id'=>$pageIds[$i][$ci%6],'segment_id'=>null,'change_type'=>['CONTENT_UPDATE','TITLE_CHANGE','CANONICAL_CHANGE','CONTENT_REFRESH'][$ci],'changed_at'=>utc(20-$ci*4),'source'=>'DEMO','description'=>'[演示] '.$desc,'observation_state'=>['POSITIVE_SIGNAL','OBSERVING','NEUTRAL','NEGATIVE_SIGNAL'][$ci],'before_snapshot'=>jsonText(['demo'=>true,'value'=>100+$ci]),'after_snapshot'=>jsonText(['demo'=>true,'value'=>130+$ci]),'created_at'=>utc(20-$ci*4)]); }
      foreach(['商业页','内容页','工具页'] as $gi=>$name){ $seg=demoId('segment-'.$i.'-'.$gi); upsert($pdo,'site_segments',['id'=>$seg,'website_id'=>$sids[$i],'name'=>'[演示] '.$name,'created_at'=>utc(40),'archived_at'=>null]); insertIgnore($pdo,'INSERT OR IGNORE INTO site_segment_rules(id,segment_id,rule_type,rule_value,created_at) VALUES(?,?,?,?,?)',[demoId('segment-rule-'.$i.'-'.$gi),$seg,'PATH_PREFIX',['/pricing','/blog','/tools'][$gi],utc(40)]); }
    }

    $rules=[
      ['SERVER_ERROR','服务器错误','HARD_ERROR','CRITICAL','修复 5xx 页面。'],['TITLE_MISSING','缺少标题','HARD_ERROR','HIGH','提供唯一、描述性 title。'],['TITLE_DUPLICATE','重复标题','BEST_PRACTICE','MEDIUM','为重要页面提供可区分 title。'],['CANONICAL_BROKEN','Canonical 目标异常','HARD_ERROR','HIGH','canonical 应指向可访问目标。'],['BROKEN_INTERNAL_LINK','内部死链','HARD_ERROR','MEDIUM','修复内部死链。'],['JSONLD_INVALID','JSON-LD 无效','HARD_ERROR','MEDIUM','修复结构化数据 JSON。'],['IMAGE_ALT_MISSING','图片缺少 alt','BEST_PRACTICE','LOW','补充替代文本。'],['CRAWL_PARTIAL','抓取不完整','INFORMATIONAL','INFO','继续或恢复抓取。']
    ];
    $ruleVersions=[]; foreach($rules as $r)$ruleVersions[$r[0]]=ensureAuditRule($pdo,$r[0],$r[1],$r[2],$r[3],$r[4]);
    foreach($sites as $i=>$s){
      $run=demoId('audit-run-'.$i); upsert($pdo,'audit_runs',['id'=>$run,'website_id'=>$sids[$i],'state'=>$i===5?'PARTIAL':'COMPLETE','scope'=>'SITE','rule_catalog_version'=>'VF-SEO-AUDIT@1','started_at'=>utc(3,2),'finished_at'=>utc(3,1),'partial_reason'=>$i===5?'DEMO_PARTIAL_CRAWL':null,'correlation_id'=>demoId('audit-correlation-'.$i)]);
      $findingIds=[];
      foreach($rules as $ri=>$r){ $page=$pageIds[$i][$ri%count($pagePaths)]; $url=rtrim($s[2],'/').$pagePaths[$ri%count($pagePaths)]; $au=demoId('audit-url-'.$i.'-'.$ri); upsert($pdo,'audit_urls',['id'=>$au,'audit_run_id'=>$run,'page_id'=>$page,'url'=>$url,'fetch_state'=>'FETCHED','http_status'=>$r[0]==='SERVER_ERROR'?500:200]); $fid=demoId('finding-'.$i.'-'.$ri); $findingIds[]=$fid; upsert($pdo,'audit_findings',['id'=>$fid,'audit_run_id'=>$run,'audit_url_id'=>$au,'rule_version_id'=>$ruleVersions[$r[0]],'severity'=>$r[3],'lifecycle_state'=>['NEW','OPEN','REGRESSION','FIXED'][$ri%4],'actual'=>jsonText(['demo'=>true,'problem'=>$r[0]]),'expected'=>jsonText(['healthy'=>true]),'first_seen_at'=>utc(12-$ri),'last_seen_at'=>utc(2)]); upsert($pdo,'audit_evidence',['id'=>demoId('evidence-'.$i.'-'.$ri),'finding_id'=>$fid,'evidence_type'=>'RULE_EVIDENCE','content'=>jsonText(['demo'=>true,'url'=>$url,'rule'=>$r[0]]),'content_hash'=>hash('sha256','demo:'.$i.':'.$ri),'created_at'=>utc(2)]); }
      $rc=demoId('root-cause-'.$i); upsert($pdo,'root_cause_candidates',['id'=>$rc,'website_id'=>$sids[$i],'state'=>'CANDIDATE','rule_version_id'=>$ruleVersions['TITLE_MISSING'],'evidence_signature'=>hash('sha256','demo-template-'.$i),'affected_count'=>3+$i,'confidence'=>0.72+($i%3)*0.08,'created_at'=>utc(2),'updated_at'=>utc(0)]); foreach(array_slice($findingIds,0,3) as $fid) insertIgnore($pdo,'INSERT OR IGNORE INTO root_cause_members(root_cause_id,finding_id) VALUES(?,?)',[$rc,$fid]);
      upsert($pdo,'notes',['id'=>demoId('note-'.($i*2+1)),'object_type'=>'WEBSITE','object_id'=>$sids[$i],'body'=>'[演示] 本周优先处理 P1 机会和技术审计高危项。','created_at'=>utc(5),'updated_at'=>utc(1)]);
      upsert($pdo,'notes',['id'=>demoId('note-'.($i*2+2)),'object_type'=>'PAGE','object_id'=>$pageIds[$i][3],'body'=>'[演示] 观察改版后 14 天自然流量和 CTR。','created_at'=>utc(4),'updated_at'=>utc(0)]);
      upsert($pdo,'user_decisions',['id'=>demoId('decision-'.($i*2+1)),'object_type'=>'OPPORTUNITY','object_id'=>demoId('opp-'.$i.'-0'),'decision'=>'ACCEPTED','note'=>'[演示] 纳入本周优化','created_at'=>utc(3)]);
      upsert($pdo,'user_decisions',['id'=>demoId('decision-'.($i*2+2)),'object_type'=>'ALERT','object_id'=>demoId('alert-'.$i.'-0'),'decision'=>'ACKNOWLEDGED','note'=>'[演示] 已知悉，继续观察','created_at'=>utc(2)]);
    }

    $check=$pdo->query('PRAGMA integrity_check')->fetchColumn(); if($check!=='ok')throw new RuntimeException('DEMO_SQLITE_INTEGRITY_FAILED');
    return ['projects'=>5,'websites'=>8,'queries'=>80,'pages'=>64,'days'=>90,'searchFacts'=>$searchFacts,'analyticsFacts'=>$analyticsFacts,'opportunities'=>80,'dataset'=>P05_DEMO_VERSION];
}

try {
    $version=trim((string)@file_get_contents($root.'/VERSION'));
    if($version!==P05_REQUIRED_VERSION) throw new RuntimeException('DEMO_BRIDGE_VERSION_MISMATCH: expected '.P05_REQUIRED_VERSION.', got '.$version);
    $config=Config::load($root); $db=new Database($config->sqlitePath,$config->sqliteBusyTimeoutMs); $session=currentSession($db,$config);
    if($session===null){ http_response_code(401); echo '<!doctype html><meta charset="utf-8"><title>需要登录</title><p>请先登录 VF SEO 后台，再在同一浏览器打开此文件。</p>'; exit; }
    $csrf=hash_hmac('sha256','p05-demo-dataset-v1',(string)$session['csrf_token']);
    $message=''; $summary=null;
    if(($_SERVER['REQUEST_METHOD']??'GET')==='POST'){
      if(!originAllowed())throw new RuntimeException('ORIGIN_REJECTED');
      if(!isset($_POST['csrf'])||!is_string($_POST['csrf'])||!hash_equals($csrf,$_POST['csrf']))throw new RuntimeException('CSRF_REJECTED');
      $action=(string)($_POST['action']??'load');
      $summary=$action==='clear'?clearDemo($db->pdo()):$db->transaction(fn() => seedDemo($db->pdo()));
      $message=$action==='clear'?'演示数据已清除；管理员、登录会话和真实数据未修改。':'完整演示数据已载入。刷新后台即可查看所有主要页面。';
    }
    header('Content-Type: text/html; charset=utf-8'); header('Cache-Control: no-store'); header('X-Robots-Tag: noindex, nofollow, noarchive');
    echo '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VF SEO 演示数据</title><style>body{font:15px/1.6 system-ui;margin:0;background:#f3f8f8;color:#12343b}.w{max-width:760px;margin:7vh auto;padding:28px;background:#fff;border:1px solid #cfe3e3;border-radius:18px}.ok{padding:12px 14px;background:#e8f8f4;border-radius:10px;margin:14px 0}.warn{padding:12px 14px;background:#fff8e7;border-radius:10px}button{border:0;border-radius:10px;padding:12px 18px;margin-right:10px;font-weight:700;cursor:pointer}.go{background:#0e9aaa;color:#fff}.clear{background:#eef3f4;color:#31555c}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}.k{padding:12px;background:#f6fafa;border-radius:10px}.n{font-size:22px;font-weight:800}@media(max-width:640px){.w{margin:0;border-radius:0}.grid{grid-template-columns:1fr 1fr}}</style><div class="w"><div style="font-size:12px;font-weight:800;color:#078899">P05 · VF SEO · V'.h($version).'</div><h1>完整演示数据</h1><p>当前管理员：<b>'.h((string)$session['username']).'</b>。本工具只认当前登录会话，不要求再次输入密码。</p>';
    if($message!=='') echo '<div class="ok">'.h($message).'</div>';
    echo '<div class="warn">演示数据使用固定 ID 和 <b>[演示]</b> 标记；可重复载入、可单独清除。不会修改管理员、Session、OAuth 凭据、备份文件或 Runtime Pointer。</div><div class="grid"><div class="k"><div class="n">8</div>演示网站</div><div class="k"><div class="n">90 天</div>趋势数据</div><div class="k"><div class="n">10 类</div>SEO 机会</div><div class="k"><div class="n">80</div>关键词</div><div class="k"><div class="n">64</div>页面</div><div class="k"><div class="n">完整</div>审计/告警/根因</div></div><form method="post"><input type="hidden" name="csrf" value="'.h($csrf).'"><button class="go" name="action" value="load">载入全部演示数据</button><button class="clear" name="action" value="clear" onclick="return confirm(\'只清除带固定 Demo ID 的演示数据，继续？\')">清除演示数据</button></form><p style="margin-top:20px;color:#648087">载入完成后删除此 PHP 文件即可；演示数据会继续保存在当前 pointer-bound SQLite 中。</p></div>';
} catch(Throwable $e){ http_response_code(500); header('Content-Type:text/html; charset=utf-8'); echo '<!doctype html><meta charset="utf-8"><h1>演示数据操作未执行</h1><pre>'.h($e->getMessage()).'</pre>'; }
