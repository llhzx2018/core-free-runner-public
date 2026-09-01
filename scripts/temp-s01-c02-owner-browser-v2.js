const { chromium } = require('playwright');
const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const wpPath = process.env.WP_PATH;
const base = process.env.WP_URL;
const evidence = process.env.EVIDENCE_DIR;
const adminPass = fs.readFileSync(process.env.WP_ADMIN_PASSWORD_FILE, 'utf8').trim();
const wp = (...args) => execFileSync('wp', [...args, `--path=${wpPath}`], { encoding: 'utf8' }).trim();
const wpLogged = (name, ...args) => {
  const r = spawnSync('wp', [...args, `--path=${wpPath}`], { encoding: 'utf8' });
  const combined = `${r.stdout || ''}\n${r.stderr || ''}`;
  fs.writeFileSync(path.join(evidence, name), combined);
  if (r.status !== 0) throw new Error(`${name} failed with exit ${r.status}: ${combined}`);
  return combined;
};
const assert = (cond, message) => { if (!cond) throw new Error(message); };

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e)));

  await page.goto(`${base}/wp-login.php`, { waitUntil: 'domcontentloaded' });
  await page.locator('#user_login').fill(process.env.WP_ADMIN_USER);
  await page.locator('#user_pass').fill(adminPass);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    page.locator('#wp-submit').click(),
  ]);

  // A. Ops-only owner surface must fail closed when Provider is absent.
  let response = await page.goto(`${base}/wp-admin/admin.php?page=vf-toolsite-tools`, { waitUntil: 'networkidle' });
  assert(response && response.status() === 200, 'Ops OWNER tools page did not return HTTP 200');
  assert(await page.getByRole('heading', { name: '工具', exact: true }).count() === 1, 'OWNER 工具 heading missing');
  assert(await page.getByText('需要安装或启用 M3U8', { exact: true }).count() >= 1, 'Provider-missing state not rendered');
  assert(await page.getByRole('link', { name: '打开插件管理' }).count() === 1, 'Provider-missing next action missing');
  await page.screenshot({ path: path.join(evidence, '01-ops-provider-missing.png'), fullPage: true });

  // B. Activate exact Theme and the ephemeral namespace-patched M3U8 source.
  wpLogged('theme-activation.log', 'theme', 'activate', 'vf-tools-theme');
  const activationLog = wpLogged('m3u8-activation.log', 'plugin', 'activate', 'vf-tool-m3u8');
  const collisionPattern = /(Duplicate key name|Duplicate entry|Unknown column|doesn't exist|WordPress database error)/i;
  assert(!collisionPattern.test(activationLog), `M3U8 activation still shows schema/seed collision: ${activationLog}`);

  const identity = wp('eval', 'echo json_encode(["ops"=>defined("VF_OPS_VERSION")?VF_OPS_VERSION:"","m3u8"=>defined("VF_TOOL_M3U8_VERSION")?VF_TOOL_M3U8_VERSION:"","theme"=>wp_get_theme()->get("Version"),"tables"=>function_exists("vf_tools_m3u8_v6_table_names")?vf_tools_m3u8_v6_table_names():[],"readiness"=>function_exists("vf_m3u8_first_run_readiness")?vf_m3u8_first_run_readiness():[]],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);');
  fs.writeFileSync(path.join(evidence, 'fresh-three-component-readback.json'), identity + '\n');
  const fresh = JSON.parse(identity);
  assert(fresh.ops === '1.21.791', 'Ops runtime version mismatch');
  assert(fresh.m3u8 === '1.25.3', 'M3U8 runtime version mismatch');
  assert(fresh.theme === '1.35.8', 'Theme runtime version mismatch');
  assert(fresh.readiness && fresh.readiness.primaryPageId > 0, 'Fresh M3U8 activation did not produce a primary product page');
  for (const [key, table] of Object.entries(fresh.tables || {})) {
    if (['capabilities','capability_contracts','pipelines','pipeline_revisions','pipeline_steps','pipeline_edges','runtime_bundles','runtime_bundle_assets'].includes(key)) {
      assert(String(table).includes('vf_m3u8_'), `Overlapping Provider table was not isolated: ${key}=${table}`);
    }
  }

  // C. Runner-only reversible fault injection through the real settings envelope.
  const damaged = wp('eval', '$current=vf_m3u8_settings_readback();$snapshot=function_exists("vf_m3u8_settings_snapshot")?vf_m3u8_settings_snapshot($current):[];$data=(array)($current["data"]??[]);$data["enabledTools"]=array_values(array_filter((array)($data["enabledTools"]??[]),static fn($id)=>sanitize_key((string)$id)!=="downloader"));$validation=vf_m3u8_settings_validate($data);if(($validation["status"]??"FAIL")!=="PASS")throw new RuntimeException("FAULT_INJECTION_VALIDATION_FAILED");$next=vf_m3u8_settings_envelope((array)$validation["data"],max(1,(int)($current["revision"]??1)+1),"runner_fault_injection",["diagnosticOnly"=>true,"snapshotId"=>(string)($snapshot["snapshotId"]??"")]);update_option(vf_m3u8_settings_option_name(),$next,false);echo json_encode(["snapshot"=>$snapshot,"readiness"=>vf_m3u8_first_run_readiness()],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);');
  fs.writeFileSync(path.join(evidence, 'damaged-readiness.json'), damaged + '\n');
  const damagedState = JSON.parse(damaged);
  assert(damagedState.readiness.status === 'FAIL', 'Reversible Provider readiness gap did not fail readiness');
  assert((damagedState.readiness.enabledToolCount || 0) < 11, 'Downloader removal did not reduce enabled tool count');
  assert(damagedState.snapshot && damagedState.snapshot.snapshotId, 'Fault injection snapshot missing');

  // D. OWNER workbench must surface repair and delegate the repair to M3U8.
  response = await page.goto(`${base}/wp-admin/admin.php?page=vf-toolsite-tools`, { waitUntil: 'networkidle' });
  assert(response && response.status() === 200, 'OWNER workbench after Provider activation did not return 200');
  assert(await page.getByText('需要初始化', { exact: true }).count() >= 1, 'OWNER workbench did not expose initialization state');
  const repair = page.getByRole('button', { name: '初始化 / 修复' });
  assert(await repair.count() === 1, 'OWNER repair button missing');
  await page.screenshot({ path: path.join(evidence, '02-owner-repair-needed.png'), fullPage: true });
  await Promise.all([
    page.waitForURL(/vf_s01_action=pass/, { waitUntil: 'networkidle' }),
    repair.click(),
  ]);
  assert(await page.getByText('正常', { exact: true }).count() >= 1, 'OWNER repair did not return PASS state');
  assert(await page.getByText(/初始化\/修复已完成/).count() >= 1, 'OWNER repair success notice missing');

  const repaired = wp('eval', 'echo json_encode(vf_m3u8_first_run_readiness(),JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);');
  fs.writeFileSync(path.join(evidence, 'repaired-readiness.json'), repaired + '\n');
  const repairedState = JSON.parse(repaired);
  assert(repairedState.status === 'PASS', 'Provider readiness did not return PASS after OWNER repair');
  assert(repairedState.enabledToolCount === 11, 'OWNER repair did not restore all 11 tools');

  // E. Daily actions must resolve around one Downloader Flow Page object.
  const settingsHref = await page.getByRole('link', { name: '工具设置' }).getAttribute('href');
  const editHref = await page.getByRole('link', { name: '页面与内容' }).getAttribute('href');
  const seoHref = await page.getByRole('link', { name: 'SEO', exact: true }).getAttribute('href');
  const previewHref = await page.getByRole('link', { name: '预览工具' }).getAttribute('href');
  assert(settingsHref && settingsHref.includes('page=vf-tool-m3u8-tools') && settingsHref.includes('tab=settings'), 'Tool settings link is not Provider settings');
  assert(editHref && editHref.includes('/wp-admin/post.php?post='), 'Page/content link is not the WordPress flow page editor');
  const editUrl = new URL(editHref, base);
  const flowPageId = editUrl.searchParams.get('post');
  assert(flowPageId && /^\d+$/.test(flowPageId), 'Could not derive Downloader flow page id');
  assert(seoHref && seoHref.includes(`post_id=${flowPageId}`), 'SEO link is not bound to the same Downloader flow page');
  assert(previewHref, 'Preview link missing');
  const expectedPreviewHref = wp('eval', `echo get_permalink(${flowPageId});`);
  const resolvedPreviewHref = new URL(previewHref, base).href;
  const resolvedExpectedPreviewHref = new URL(expectedPreviewHref, base).href;
  assert(resolvedPreviewHref === resolvedExpectedPreviewHref, `Preview link is not the canonical Downloader flow-page permalink: ${resolvedPreviewHref} !== ${resolvedExpectedPreviewHref}`);
  fs.writeFileSync(path.join(evidence, 'owner-object-links.json'), JSON.stringify({ settingsHref, editHref, seoHref, previewHref, expectedPreviewHref, flowPageId }, null, 2) + '\n');

  response = await page.goto(settingsHref, { waitUntil: 'domcontentloaded' });
  assert(response && response.status() === 200, 'Provider settings destination failed');
  response = await page.goto(editHref, { waitUntil: 'domcontentloaded' });
  assert(response && response.status() === 200, 'Flow page editor destination failed');
  response = await page.goto(seoHref, { waitUntil: 'domcontentloaded' });
  assert(response && response.status() === 200, 'Ops SEO destination failed');

  // F. Public preview must execute the real unified Downloader shortcode.
  response = await page.goto(previewHref, { waitUntil: 'networkidle' });
  assert(response && response.status() === 200, 'Public Downloader preview failed');
  assert(await page.locator('[data-vf-product-flow="download-record"]').count() >= 1, 'Unified Downloader runtime root missing from public page');
  assert(await page.locator('[data-vf-entry-input]').count() >= 1, 'Downloader runtime input missing');
  const bodyText = await page.locator('body').innerText();
  assert(!bodyText.includes('[vf_m3u8_download_record_entry]'), 'Raw Downloader shortcode leaked instead of executing');
  await page.screenshot({ path: path.join(evidence, '03-public-downloader-preview.png'), fullPage: true });

  // G. Narrow admin usability.
  await page.setViewportSize({ width: 390, height: 844 });
  response = await page.goto(`${base}/wp-admin/admin.php?page=vf-toolsite-tools`, { waitUntil: 'networkidle' });
  assert(response && response.status() === 200, '390px OWNER workbench failed');
  assert(await page.getByRole('heading', { name: '工具', exact: true }).count() === 1, '390px OWNER heading missing');
  assert(await page.getByText('M3U8 Downloader', { exact: true }).count() >= 1, '390px Downloader product object missing');
  const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth);
  assert(overflow <= 40, `390px severe horizontal overflow: ${overflow}px`);
  await page.screenshot({ path: path.join(evidence, '04-owner-workbench-390.png'), fullPage: true });

  fs.writeFileSync(path.join(evidence, 'owner-browser-gate.json'), JSON.stringify({
    result: 'PASS',
    diagnosticMode: 'EPHEMERAL_M3U8_PROVIDER_TABLE_NAMESPACE',
    opsOnlyProviderMissing: 'PASS',
    m3u8ActivationSchemaCollision: 'ABSENT_WITH_EPHEMERAL_NAMESPACE_PATCH',
    reversibleProviderGap: 'PASS',
    ownerRepairPostRedirectReadback: 'PASS',
    sameProductObjectLinks: 'PASS',
    publicShortcodeRuntime: 'PASS',
    admin390Usability: 'PASS',
    flowPageId,
    pageErrors,
  }, null, 2) + '\n');
  await browser.close();
})().catch(err => {
  fs.mkdirSync(evidence, { recursive: true });
  fs.writeFileSync(path.join(evidence, 'owner-browser-gate-error.txt'), String(err && err.stack || err) + '\n');
  console.error(err);
  process.exit(1);
});
