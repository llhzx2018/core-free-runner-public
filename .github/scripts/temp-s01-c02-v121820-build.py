from pathlib import Path
import re

# Run from the checked-out vf-tools-ops repository root.

p = Path('VERSION')
p.write_text('1.21.820\n', encoding='utf-8')

p = Path('vf-ops.php')
s = p.read_text(encoding='utf-8')
s, n1 = re.subn(r'(?m)^\s*\*\s*Version:\s*1\.21\.819\s*$', ' * Version: 1.21.820', s, count=1)
s, n2 = re.subn(r"define\('VF_OPS_VERSION',\s*'1\.21\.819'\);", "define('VF_OPS_VERSION', '1.21.820');", s, count=1)
s, n3 = re.subn(r"define\('VF_OPS_ROUND',\s*'[^']+'\);", "define('VF_OPS_ROUND', 'CANDIDATE-PREFLIGHT-AUTHORITY-V1');", s, count=1)
assert n1 == n2 == n3 == 1, (n1, n2, n3)
p.write_text(s, encoding='utf-8')

p = Path('includes/publish-o10/publish-preflight-product.php')
s = p.read_text(encoding='utf-8')
anchor = "function vf_ops_publish_preflight_gate_v121422(): array {"
assert anchor in s
helper = r'''/**
 * V1.21.820 Candidate authority: consume the persisted Preflight snapshot using
 * the product's saved_snapshot_lightweight_batch_identity contract. Candidate
 * preparation must not silently rerun context-sensitive SEO/language/component
 * scans after an explicit saved snapshot has already been read back intact.
 * P1 remains visible and non-blocking here; P0 still blocks. Final online freeze
 * continues to require its stricter P0/P1 policy and does not use this helper.
 */
function vf_ops_publish_preflight_candidate_gate_v121820(array $batch=[]): array {
    $contract=(array)vf_ops_publish_preflight_contract_v121422();
    $saved=get_option((string)($contract['snapshotOption']??''),[]);$saved=is_array($saved)?$saved:[];
    if(!$batch&&function_exists('vf_ops_o10_current_batch_v121399')){$batch=(array)vf_ops_o10_current_batch_v121399();}
    if(!$batch&&function_exists('vf_ops_release_batch_active_id_v121363')&&function_exists('vf_ops_release_batch_find_v121363')){
        $id=(string)vf_ops_release_batch_active_id_v121363();$batch=$id!==''?(array)vf_ops_release_batch_find_v121363($id):[];
    }
    $status=sanitize_key((string)($batch['status']??''));
    $eligible=$batch&&in_array($status,['locked','package_attached','deployed_pending_acceptance'],true);
    $state=($saved&&$eligible&&function_exists('vf_ops_publish_preflight_saved_view_state_v121708'))
        ?(array)vf_ops_publish_preflight_saved_view_state_v121708($saved,$batch):[];
    $savedStatus=vf_ops_publish_preflight_clean_status_v121422((string)($saved['status']??'NOT_VERIFIED'));
    $p0=max(0,(int)($saved['gateSummary']['P0']??0));$p1=max(0,(int)($saved['gateSummary']['P1']??0));
    $pass=$eligible&&!empty($state['snapshotCurrent'])&&!empty($state['gateReady'])&&$p0===0&&in_array($savedStatus,['PASS','PARTIAL'],true);
    $blocking=[];
    if(!$saved){$blocking[]='尚未保存发布前检查快照。';}
    if(!$eligible){$blocking[]='当前发布批次状态不允许生成候选包。';}
    if($saved&&!empty($state)&&empty($state['snapshotCurrent'])){$blocking=array_merge($blocking,(array)($state['reasons']??[]));}
    if($p0>0){$blocking[]='已保存发布前检查仍有 P0 阻断。';}
    if($saved&&!in_array($savedStatus,['PASS','PARTIAL'],true)){$blocking[]='已保存发布前检查没有达到候选包准入状态。';}
    $blocking=array_values(array_unique(array_filter($blocking)));
    return [
        'status'=>$pass?'PASS':'FAIL','source_site_pass'=>$pass?'YES':'NO','theme_acceptance_gate_pass'=>$pass?'YES':'NO','o10_preflight_pass'=>$pass?'YES':'NO',
        'message'=>$pass?($p1>0?'发布前快照有效；P0=0，P1 提醒保留并允许进入候选包。':'发布前快照有效，可以进入候选包。'):implode(' ',$blocking),
        'checked_at'=>(string)($saved['generatedAt']??''),'expires_at'=>(string)($saved['expiresAtGmt']??''),'snapshot_fresh'=>!empty($state['snapshotCurrent'])?'YES':'NO',
        'blocking_count'=>count($blocking),'blocking_examples'=>array_slice($blocking,0,5),'batch_id'=>(string)($batch['id']??''),'snapshot_status'=>$savedStatus,'current_status'=>(string)($state['status']??'NOT_VERIFIED'),
        'p0_count'=>$p0,'p1_count'=>$p1,'checks'=>(array)($saved['checks']??[]),'savedState'=>$state,'scopeHash'=>(string)($saved['scopeHash']??''),'evidenceHash'=>(string)($saved['evidenceHash']??''),
        'authorityBasis'=>'saved_snapshot_lightweight_batch_identity','warningsMayProceedButRemainVisible'=>true,'finalOnlinePass'=>'NO',
    ];
}

'''
s = s.replace(anchor, helper + anchor, 1)
p.write_text(s, encoding='utf-8')

p = Path('includes/publish-o10/publish-zip-product.php')
s = p.read_text(encoding='utf-8')
old = "$gate=function_exists('vf_ops_publish_preflight_gate_v121422')?(array)vf_ops_publish_preflight_gate_v121422():(function_exists('vf_ops_o10_preflight_gate_v121399')?(array)vf_ops_o10_preflight_gate_v121399():['status'=>'FAIL','message'=>'发布前门禁服务不可用。']);"
new = "$gate=function_exists('vf_ops_publish_preflight_candidate_gate_v121820')?(array)vf_ops_publish_preflight_candidate_gate_v121820($batch):(function_exists('vf_ops_publish_preflight_gate_v121422')?(array)vf_ops_publish_preflight_gate_v121422():(function_exists('vf_ops_o10_preflight_gate_v121399')?(array)vf_ops_o10_preflight_gate_v121399():['status'=>'FAIL','message'=>'发布前门禁服务不可用。']));"
assert s.count(old) == 1
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

p = Path('includes/publish-o10/publish-release-orchestrator.php')
s = p.read_text(encoding='utf-8')
old = "$gate=function_exists('vf_ops_publish_preflight_gate_v121422')?(array)vf_ops_publish_preflight_gate_v121422():[];"
new = "$batch=function_exists('vf_ops_o10_current_batch_v121399')?(array)vf_ops_o10_current_batch_v121399():[];$gate=function_exists('vf_ops_publish_preflight_candidate_gate_v121820')?(array)vf_ops_publish_preflight_candidate_gate_v121820($batch):(function_exists('vf_ops_publish_preflight_gate_v121422')?(array)vf_ops_publish_preflight_gate_v121422():[]);"
assert s.count(old) == 1
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

Path('.github/phase3/v121820-candidate-preflight-authority.php').write_text(r'''<?php
$pre=file_get_contents(__DIR__.'/../../includes/publish-o10/publish-preflight-product.php');
$zip=file_get_contents(__DIR__.'/../../includes/publish-o10/publish-zip-product.php');
$orch=file_get_contents(__DIR__.'/../../includes/publish-o10/publish-release-orchestrator.php');
$main=file_get_contents(__DIR__.'/../../vf-ops.php');
$assert=function($ok,$msg){if(!$ok){fwrite(STDERR,"FAIL: $msg\n");exit(1);}};
$assert(str_contains($pre,'function vf_ops_publish_preflight_candidate_gate_v121820'),'candidate helper missing');
$assert(str_contains($pre,"['PASS','PARTIAL']"),'PARTIAL/P1 candidate contract missing');
$assert(str_contains($pre,'$p0===0'),'P0 fail-closed contract missing');
$assert(str_contains($pre,'vf_ops_publish_preflight_saved_view_state_v121708'),'saved lightweight identity state missing');
$assert(str_contains($pre,"warningsMayProceedButRemainVisible'=>true"),'P1 visibility contract missing');
$assert(str_contains($pre,"finalOnlinePass'=>'NO"),'online boundary missing');
$assert(str_contains($zip,'vf_ops_publish_preflight_candidate_gate_v121820($batch)'),'ZIP model not aligned');
$assert(str_contains($orch,'vf_ops_publish_preflight_candidate_gate_v121820($batch)'),'orchestrator capture not aligned');
$assert(str_contains($pre,'function vf_ops_publish_preflight_gate_v121422'),'legacy strict gate must remain');
$assert(str_contains($main,'CANDIDATE-PREFLIGHT-AUTHORITY-V1'),'round identity missing');
echo "PASS_V121820_CANDIDATE_PREFLIGHT_AUTHORITY\n";
''', encoding='utf-8')
