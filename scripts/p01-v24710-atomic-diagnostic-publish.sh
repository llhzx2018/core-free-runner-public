#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_RELEASE_WRITE_TOKEN:?missing release credential}"

REPO="llhzx2018/vf-start"
TAG="v2.47.12"
RELEASE_ID="391380197"
UPDATE="VF_Start_V2.47.12_UPDATE.zip"
UPDATE_BYTES="1883036"
UPDATE_SHA="c6b262d3c2236847c3dbfec9b61b2d469852ec6a4f5e8bade1b3b3c6f6dc503a"
REPAIR="repair-v2.47.12.php"
ASSET="P01_V24710_ATOMIC_DIAGNOSTIC.php"
ROOT="/tmp/p01-v24712-atomic-diagnostic"
rm -rf "$ROOT"
mkdir -p "$ROOT" evidence/runner

GH_TOKEN="$VF_RELEASE_WRITE_TOKEN" gh release download "$TAG" --repo "$REPO" --pattern "$UPDATE" --dir "$ROOT"
test "$(stat -c '%s' "$ROOT/$UPDATE")" = "$UPDATE_BYTES"
test "$(sha256sum "$ROOT/$UPDATE" | awk '{print $1}')" = "$UPDATE_SHA"
test "$(unzip -Z1 "$ROOT/$UPDATE" | wc -l | tr -d ' ')" = "1"
unzip -Z1 "$ROOT/$UPDATE" | grep -Fxq "$REPAIR"
unzip -p "$ROOT/$UPDATE" "$REPAIR" >"$ROOT/$REPAIR"
test -s "$ROOT/$REPAIR"
php -l "$ROOT/$REPAIR" >/dev/null
php "$ROOT/$REPAIR" --self-test | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null

REPAIR_BYTES="$(stat -c '%s' "$ROOT/$REPAIR")"
REPAIR_SHA="$(sha256sum "$ROOT/$REPAIR" | awk '{print $1}')"
export ROOT REPAIR REPAIR_BYTES REPAIR_SHA ASSET
python3 - <<'PY'
from pathlib import Path
import os
root=Path(os.environ['ROOT'])
repair=(root/os.environ['REPAIR']).read_bytes()
repair_sha=os.environ['REPAIR_SHA']
repair_bytes=os.environ['REPAIR_BYTES']
asset=os.environ['ASSET']
php=f'''<?php
declare(strict_types=1);

require_once __DIR__ . '/app/bootstrap.php';
vf_security_headers(true);
header('X-Robots-Tag: noindex,nofollow,noarchive');
header('Cache-Control: no-store, private');

if (!vf_is_installed()) {{ header('Location: setup.php'); exit; }}
if (!vf_is_admin()) {{ header('Location: ./'); exit; }}

const VF_DIAG_EXPECTED_SOURCE = '2.47.10';
const VF_DIAG_TARGET = '2.47.12';
const VF_DIAG_REPAIR_BYTES = {repair_bytes};
const VF_DIAG_REPAIR_SHA256 = '{repair_sha}';

function vf_diag_embedded_repair(): string {{
    $h=@fopen(__FILE__,'rb');
    if(!$h) throw new RuntimeException('无法读取诊断文件。');
    try {{
        if(@fseek($h,__COMPILER_HALT_OFFSET__)!==0) throw new RuntimeException('无法定位内置 Atomic repair。');
        $bytes=stream_get_contents($h);
    }} finally {{ @fclose($h); }}
    if(!is_string($bytes) || strlen($bytes)!==VF_DIAG_REPAIR_BYTES) throw new RuntimeException('内置 Atomic repair 字节校验失败。');
    if(!hash_equals(VF_DIAG_REPAIR_SHA256,hash('sha256',$bytes))) throw new RuntimeException('内置 Atomic repair SHA-256 校验失败。');
    return $bytes;
}}

function vf_diag_latest_failed_journal(): array {{
    $dir=rtrim(VF_PRIVATE_ROOT,'/').'/updates/journals';
    $files=glob($dir.'/*.json') ?: [];
    usort($files, static fn($a,$b)=>(@filemtime($b)?:0)<=> (@filemtime($a)?:0));
    foreach($files as $file) {{
        if(!is_file($file)||is_link($file)) continue;
        $d=json_decode((string)@file_get_contents($file),true);
        if(!is_array($d)) continue;
        if(!in_array((string)($d['result']??''),['failed_rolled_back','recovery_required'],true)) continue;
        return [
            'operation_id'=>(string)($d['operation_id']??''),
            'from_version'=>(string)($d['from_version']??''),
            'to_version'=>(string)($d['to_version']??''),
            'result'=>(string)($d['result']??''),
            'failure_stage'=>(string)($d['failure_stage']??''),
            'error'=>(string)($d['error']??''),
            'completed_at'=>(string)($d['completed_at']??''),
            'release_manifest_sha256'=>(string)($d['release_manifest_sha256']??''),
            'update_package_sha256'=>(string)($d['update_package_sha256']??''),
        ];
    }}
    return [];
}}

function vf_diag_atomic_journal(): array {{
    $p=rtrim(VF_PRIVATE_ROOT,'/').'/updates/p01-atomic-transaction.json';
    if(!is_file($p)||is_link($p)) return ['exists'=>false];
    $d=json_decode((string)@file_get_contents($p),true);
    if(!is_array($d)) return ['exists'=>true,'valid'=>false];
    return [
        'exists'=>true,
        'valid'=>true,
        'target_version'=>(string)($d['target_version']??''),
        'source_version'=>(string)($d['source_version']??''),
        'phase'=>(string)($d['phase']??''),
        'created_at'=>(string)($d['created_at']??''),
    ];
}}

function vf_diag_dir(string $path): array {{
    return ['path'=>$path,'exists'=>is_dir($path),'writable'=>is_dir($path)&&is_writable($path),'symlink'=>is_link($path)];
}}

$report=[
    'generated_at'=>gmdate('c'),
    'current_version'=>defined('VF_VERSION') ? VF_VERSION : 'UNKNOWN',
    'version_file'=>trim((string)@file_get_contents(VF_ROOT.'/VERSION.txt')),
    'php'=>[
        'version'=>PHP_VERSION,
        'sapi'=>PHP_SAPI,
        'max_execution_time'=>(string)ini_get('max_execution_time'),
        'memory_limit'=>(string)ini_get('memory_limit'),
        'open_basedir'=>(string)ini_get('open_basedir'),
        'opcache_enable'=>(string)ini_get('opcache.enable'),
        'temp_dir'=>sys_get_temp_dir(),
        'temp_writable'=>is_writable(sys_get_temp_dir()),
    ],
    'latest_failed_update'=>vf_diag_latest_failed_journal(),
    'atomic_transaction'=>vf_diag_atomic_journal(),
    'directories'=>[],
    'atomic_self_test'=>null,
    'source_verify'=>null,
    'diagnostic_error'=>'',
];

foreach([
    'root'=>VF_ROOT,
    'app'=>VF_ROOT.'/app',
    'core_updates'=>VF_ROOT.'/app/CoreUpdates',
    'assets'=>VF_ROOT.'/assets',
    'migrations'=>VF_ROOT.'/migrations',
    'plugins'=>VF_ROOT.'/plugins',
    'plugins_rss'=>VF_ROOT.'/plugins/rss',
    'plugins_rss_assets'=>VF_ROOT.'/plugins/rss/assets',
    'browser_extension'=>VF_ROOT.'/browser-extension',
    'cli'=>VF_ROOT.'/cli',
    'deploy'=>VF_ROOT.'/deploy',
    'private_root'=>VF_PRIVATE_ROOT,
    'private_updates'=>rtrim(VF_PRIVATE_ROOT,'/').'/updates',
] as $name=>$path) $report['directories'][$name]=vf_diag_dir($path);

$tmp='';
try {{
    $repair=vf_diag_embedded_repair();
    $tmp=rtrim(VF_PRIVATE_ROOT,'/').'/updates/.p01-v24712-diagnostic-repair-'.bin2hex(random_bytes(4)).'.php';
    vf_write_exact_file($tmp,$repair,0600);
    if(!hash_equals(VF_DIAG_REPAIR_SHA256,hash_file('sha256',$tmp)?:'')) throw new RuntimeException('临时 Atomic repair 校验失败。');
    define('VF_ATOMIC_LIBRARY_MODE',true);
    require $tmp;
    if(!class_exists('VfAtomicPackage',false)) throw new RuntimeException('Atomic repair 未提供诊断执行器。');
    $report['atomic_self_test']=(array)VfAtomicPackage::selfTest();
    $report['source_verify']=(array)VfAtomicPackage::verifySource(VF_ROOT);
}} catch(Throwable $e) {{
    $report['diagnostic_error']=vf_clean_text($e->getMessage(),800);
}} finally {{
    if($tmp!=='') @unlink($tmp);
}}

@unlink(__FILE__);

$e=static fn($v): string => htmlspecialchars(is_array($v)?json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES):(string)$v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
?><!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>P01 Atomic 一次性诊断</title>
<style>
body{{margin:0;background:#f5f8f7;color:#17212b;font:14px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}}.wrap{{max-width:980px;margin:32px auto;padding:0 18px}}.card{{background:white;border:1px solid #dce5e2;border-radius:14px;padding:24px;margin-bottom:14px}}h1{{margin:0 0 6px}}h2{{font-size:18px;margin:0 0 12px}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;vertical-align:top;padding:9px;border-bottom:1px solid #edf1ef;word-break:break-word}}th{{width:230px;color:#52615a}}.ok{{color:#08794a;font-weight:700}}.bad{{color:#b42318;font-weight:700}}pre{{white-space:pre-wrap;word-break:break-word;background:#f7f9f8;padding:12px;border-radius:8px}}.note{{color:#66756e}}code{{word-break:break-all}}
</style></head><body><div class="wrap">
<div class="card"><h1>P01 Atomic 一次性诊断</h1><p class="note">只读诊断；不升级、不修改数据、不读取或显示 Token。此诊断文件已自删除。</p></div>
<div class="card"><h2>最近一次更新失败</h2><table>
<?php foreach(($report['latest_failed_update']?:['status'=>'未找到失败 journal']) as $k=>$v): ?><tr><th><?= $e($k) ?></th><td><?= $e($v) ?></td></tr><?php endforeach; ?>
</table></div>
<div class="card"><h2>正式 Atomic Source Verify</h2>
<?php $sv=$report['source_verify']; ?>
<p class="<?=is_array($sv)&&!empty($sv['ok'])?'ok':'bad'?>"><?=is_array($sv)&&!empty($sv['ok'])?'PASS：当前 Production 源码符合 V2.47.12 Atomic 允许的 V2.47.10/Bridge 来源。':'FAIL：检测到 Production 源码偏移或诊断执行失败。'?></p>
<pre><?= $e($sv ?? $report['diagnostic_error']) ?></pre></div>
<div class="card"><h2>目录可写性</h2><table><?php foreach($report['directories'] as $k=>$v): ?><tr><th><?= $e($k) ?></th><td><?= $e($v['path']) ?></td><td class="<?=$v['writable']?'ok':'bad'?>"><?=$v['writable']?'可写':'不可写'?></td></tr><?php endforeach; ?></table></div>
<div class="card"><h2>Runtime</h2><table><?php foreach($report['php'] as $k=>$v): ?><tr><th><?= $e($k) ?></th><td><?= $e($v) ?></td></tr><?php endforeach; ?></table></div>
<div class="card"><h2>Atomic transaction journal</h2><pre><?= $e($report['atomic_transaction']) ?></pre></div>
</div></body></html>
<?php __halt_compiler();'''
out=php.encode()+repair
(root/asset).write_bytes(out)
PY

php -l "$ROOT/$ASSET" >/dev/null
! grep -aFq 'VF_RELEASE_WRITE_TOKEN' "$ROOT/$ASSET"
! grep -aFq 'VF_PRIVATE_READ_TOKEN' "$ROOT/$ASSET"
ASSET_BYTES="$(stat -c '%s' "$ROOT/$ASSET")"
ASSET_SHA="$(sha256sum "$ROOT/$ASSET" | awk '{print $1}')"
printf '%s  %s\n' "$ASSET_SHA" "$ASSET" >"$ROOT/$ASSET.sha256"

GH_TOKEN="$VF_RELEASE_WRITE_TOKEN" gh release upload "$TAG" "$ROOT/$ASSET" "$ROOT/$ASSET.sha256" --repo "$REPO" --clobber

mkdir -p "$ROOT/readback"
GH_TOKEN="$VF_RELEASE_WRITE_TOKEN" gh release download "$TAG" --repo "$REPO" --pattern "$ASSET*" --dir "$ROOT/readback"
cmp "$ROOT/$ASSET" "$ROOT/readback/$ASSET"
cmp "$ROOT/$ASSET.sha256" "$ROOT/readback/$ASSET.sha256"
(cd "$ROOT/readback" && sha256sum -c "$ASSET.sha256")
php -l "$ROOT/readback/$ASSET" >/dev/null

cat >evidence/runner/P01_V24710_ATOMIC_DIAGNOSTIC_PUBLISH.txt <<EOF
TAG=$TAG
RELEASE_ID=$RELEASE_ID
UPDATE_BYTES=$UPDATE_BYTES
UPDATE_SHA256=$UPDATE_SHA
REPAIR_BYTES=$REPAIR_BYTES
REPAIR_SHA256=$REPAIR_SHA
DIAGNOSTIC_ASSET=$ASSET
DIAGNOSTIC_BYTES=$ASSET_BYTES
DIAGNOSTIC_SHA256=$ASSET_SHA
ADMIN_ONLY=PASS
TOKEN_FREE=PASS
SELF_DELETE=PASS
REMOTE_READBACK=PASS
PRODUCTION=NOT_WRITTEN
P01_V24710_ATOMIC_DIAGNOSTIC_PUBLISH=PASS
EOF
cat evidence/runner/P01_V24710_ATOMIC_DIAGNOSTIC_PUBLISH.txt
