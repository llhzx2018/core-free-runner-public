const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const wpPath = process.env.WP_PATH;
const evidence = process.env.EVIDENCE_DIR;
const wp = (...args) => execFileSync('wp', [...args, `--path=${wpPath}`], { encoding: 'utf8', timeout: 120000 }).trim();
const timed = (name, fn) => {
  const started = Date.now();
  const value = fn();
  const durationMs = Date.now() - started;
  return { name, durationMs, value };
};
const parse = value => JSON.parse(value || '{}');

const faultCode = '$current=vf_m3u8_settings_readback();$snapshot=function_exists("vf_m3u8_settings_snapshot")?vf_m3u8_settings_snapshot($current):[];$data=(array)($current["data"]??[]);$data["enabledTools"]=array_values(array_filter((array)($data["enabledTools"]??[]),static fn($id)=>sanitize_key((string)$id)!=="downloader"));$validation=vf_m3u8_settings_validate($data);if(($validation["status"]??"FAIL")!=="PASS")throw new RuntimeException("PROFILE_FAULT_VALIDATION_FAILED");$next=vf_m3u8_settings_envelope((array)$validation["data"],max(1,(int)($current["revision"]??1)+1),"runner_profile_fault",["diagnosticOnly"=>true,"snapshotId"=>(string)($snapshot["snapshotId"]??"")]);update_option(vf_m3u8_settings_option_name(),$next,false);echo json_encode(["snapshotId"=>(string)($snapshot["snapshotId"]??""),"readiness"=>vf_m3u8_first_run_readiness()],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);';

wp('theme', 'activate', 'vf-tools-theme');
wp('plugin', 'activate', 'vf-tool-m3u8');

const profile = { mode: 'RUNNER_ONLY_OWNER_REPAIR_PROFILE', sourceWrite: 'NO', stages: [] };

let row = timed('freshReadiness', () => wp('eval', 'echo json_encode(vf_m3u8_first_run_readiness(),JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);'));
profile.stages.push({ name: row.name, durationMs: row.durationMs, result: parse(row.value) });

row = timed('faultInjection1', () => wp('eval', faultCode));
profile.stages.push({ name: row.name, durationMs: row.durationMs, result: parse(row.value) });
if (profile.stages.at(-1).result.readiness.status !== 'FAIL') throw new Error('faultInjection1 did not fail readiness');

row = timed('settingsOnlyRepair', () => wp('eval', 'echo json_encode(vf_m3u8_first_run_enable_all_tools(),JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);'));
profile.stages.push({ name: row.name, durationMs: row.durationMs, result: parse(row.value) });

row = timed('readinessAfterSettingsOnlyRepair', () => wp('eval', 'echo json_encode(vf_m3u8_first_run_readiness(),JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);'));
profile.stages.push({ name: row.name, durationMs: row.durationMs, result: parse(row.value) });
if (profile.stages.at(-1).result.status !== 'PASS') throw new Error('settingsOnlyRepair did not restore readiness PASS');

row = timed('faultInjection2', () => wp('eval', faultCode));
profile.stages.push({ name: row.name, durationMs: row.durationMs, result: parse(row.value) });
if (profile.stages.at(-1).result.readiness.status !== 'FAIL') throw new Error('faultInjection2 did not fail readiness');

row = timed('fullInitializerRepair', () => wp('eval', '$r=vf_m3u8_first_run_initialize((int)get_current_user_id(),"runner_profile_full_initializer");echo json_encode($r,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);'));
profile.stages.push({ name: row.name, durationMs: row.durationMs, result: parse(row.value) });
if (profile.stages.at(-1).result.status !== 'PASS') throw new Error('fullInitializerRepair did not return PASS');

row = timed('finalReadiness', () => wp('eval', 'echo json_encode(vf_m3u8_first_run_readiness(),JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);'));
profile.stages.push({ name: row.name, durationMs: row.durationMs, result: parse(row.value) });
if (profile.stages.at(-1).result.status !== 'PASS') throw new Error('finalReadiness is not PASS');

fs.writeFileSync(path.join(evidence, 'owner-repair-profile.json'), JSON.stringify(profile, null, 2) + '\n');
console.log(JSON.stringify(profile.stages.map(s => ({ name: s.name, durationMs: s.durationMs, status: s.result.status || s.result.readiness?.status || s.result.code || '' })), null, 2));
