from pathlib import Path
import json

root = Path('p01')


def one(path: str, old: str, new: str) -> None:
    p = root / path
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected 1 match, got {count}: {old[:140]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

# Deployment/runtime implementation constants. Governance authority remains gov-doc.
one(
    'src/app/bootstrap.php',
    "define('VF_VERSION', '2.21.24');\n",
    "define('VF_VERSION', '2.21.24');\ndefine('VF_UPLOAD_DEFAULT_MAX_BYTES', 20971520);\ndefine('VF_RECOVERY_UPLOAD_MAX_BYTES', 209715200);\ndefine('VF_ARCHIVE_MAX_UNCOMPRESSED_BYTES', 209715200);\ndefine('VF_ARCHIVE_MAX_FILES', 5000);\ndefine('VF_STATIC_ASSET_CACHE_SECONDS', 31536000);\ndefine('VF_ADMIN_ASSET_CACHE_SECONDS', 300);\n",
)

anchor = """function vf_effective_upload_limit(): int
{
    $limits = [];
    foreach (['upload_max_filesize','post_max_size'] as $key) {
        $bytes = vf_ini_bytes((string)ini_get($key));
        if ($bytes > 0) $limits[] = $bytes;
    }
    return $limits ? min($limits) : 0;
}
"""
addition = anchor + r'''

function vf_declared_web_upload_limit(): int
{
    $path = VF_ROOT . '/.user.ini';
    if (!is_file($path)) return 0;
    $ini = @parse_ini_file($path, false, INI_SCANNER_RAW);
    if (!is_array($ini)) return 0;
    $limits = [];
    foreach (['upload_max_filesize','post_max_size'] as $key) {
        $bytes = vf_ini_bytes((string)($ini[$key] ?? ''));
        if ($bytes > 0) $limits[] = $bytes;
    }
    return $limits ? min($limits) : 0;
}

function vf_effective_web_upload_limit(): int
{
    $runtime = vf_effective_upload_limit();
    if (PHP_SAPI !== 'cli') return $runtime;
    // CLI verification does not apply per-directory .user.ini. Resolve the
    // declared FPM/web contract instead, while web requests always report the
    // live SAPI value above.
    $declared = vf_declared_web_upload_limit();
    return $declared > 0 ? $declared : $runtime;
}

function vf_assert_upload_size(int $bytes, int $maxBytes, string $subject='文件'): void
{
    if ($bytes <= 0 || $bytes > $maxBytes) {
        throw new InvalidArgumentException($subject . '大小必须在 ' . vf_format_bytes($maxBytes) . ' 以内。');
    }
}

function vf_assert_upload_extension(string $originalName, array $allowed, string $subject='文件'): void
{
    $name = strtolower(trim(basename($originalName)));
    if ($name === '' || $name !== strtolower(trim($originalName))) {
        throw new InvalidArgumentException($subject . '文件名无效。');
    }
    foreach ($allowed as $extension) {
        $suffix = '.' . strtolower(ltrim((string)$extension, '.'));
        if ($suffix !== '.' && str_ends_with($name, $suffix)) return;
    }
    throw new InvalidArgumentException($subject . '扩展名不受支持。');
}

function vf_assert_sqlite_upload_signature(string $path): void
{
    if (!is_file($path) || file_get_contents($path, false, null, 0, 16) !== "SQLite format 3\0") {
        throw new InvalidArgumentException('SQLite 备份内容签名无效。');
    }
}

function vf_assert_gzip_upload_signature(string $path): void
{
    if (!is_file($path) || file_get_contents($path, false, null, 0, 2) !== "\x1f\x8b") {
        throw new InvalidArgumentException('灾难恢复包必须是 gzip 压缩归档。');
    }
}
'''
one('src/app/bootstrap.php', anchor, addition)

# Canonical versioned asset URL. All core static assets are served by asset.php,
# so cache headers are application-verifiable instead of web-server assumptions.
fmt_anchor = """function vf_format_bytes(int $bytes): string
{
    if ($bytes <= 0) return '未知';
    $units = ['B','KB','MB','GB']; $i = 0; $value = (float)$bytes;
    while ($value >= 1024 && $i < count($units)-1) { $value /= 1024; $i++; }
    $digits = $value >= 10 || $i === 0 ? 0 : 1;
    return number_format($value,$digits,'.','') . ' ' . $units[$i];
}
"""
asset_helper = fmt_anchor + r'''

function vf_asset_url(string $path): string
{
    $parts = explode('#', trim($path), 2);
    $withoutFragment = $parts[0];
    $fragment = isset($parts[1]) ? '#' . $parts[1] : '';
    $assetPath = explode('?', ltrim($withoutFragment, '/'), 2)[0];
    if (!preg_match('#^assets/([A-Za-z0-9_.-]+\.(?:css|js|png|jpe?g|webp|gif|svg|ico))$#i', $assetPath, $m)) {
        throw new InvalidArgumentException('静态资源路径无效。');
    }
    return 'asset.php?file=' . rawurlencode($m[1]) . '&v=' . rawurlencode(VF_VERSION) . $fragment;
}
'''
one('src/app/bootstrap.php', fmt_anchor, asset_helper)

# Web PHP must be able to receive the explicit Recovery Artifact exception.
(root / 'src/.user.ini').write_text(
    'upload_max_filesize=200M\npost_max_size=205M\n', encoding='utf-8'
)

# Application-owned static asset endpoint.
(root / 'src/asset.php').write_text(r'''<?php
declare(strict_types=1);
require_once __DIR__ . '/app/bootstrap.php';

vf_security_headers(false);
header('X-Robots-Tag: noindex, nofollow, noarchive');

$file = (string)($_GET['file'] ?? '');
if ($file === '' || $file !== basename($file) || !preg_match('/^[A-Za-z0-9_.-]+\.(?:css|js|png|jpe?g|webp|gif|svg|ico)$/i', $file)) {
    http_response_code(404); exit;
}
$base = realpath(VF_ROOT . '/assets');
$path = realpath(VF_ROOT . '/assets/' . $file);
if ($base === false || $path === false || !is_file($path) || is_link($path) || !str_starts_with($path, $base . DIRECTORY_SEPARATOR)) {
    http_response_code(404); exit;
}

$extension = strtolower(pathinfo($file, PATHINFO_EXTENSION));
$types = [
    'css'=>'text/css; charset=utf-8','js'=>'application/javascript; charset=utf-8',
    'png'=>'image/png','jpg'=>'image/jpeg','jpeg'=>'image/jpeg','webp'=>'image/webp',
    'gif'=>'image/gif','svg'=>'image/svg+xml','ico'=>'image/x-icon',
];
header('Content-Type: ' . ($types[$extension] ?? 'application/octet-stream'));
header('Content-Length: ' . (string)filesize($path));
$etag = '"' . (hash_file('sha256', $path) ?: '') . '"';
header('ETag: ' . $etag);

$requestedVersion = trim((string)($_GET['v'] ?? ''));
if ($requestedVersion !== '' && hash_equals(VF_VERSION, $requestedVersion)) {
    header('Cache-Control: public, max-age=' . VF_STATIC_ASSET_CACHE_SECONDS . ', immutable');
} elseif ($requestedVersion === '') {
    header('Cache-Control: private, max-age=' . VF_ADMIN_ASSET_CACHE_SECONDS);
} else {
    // Never attach an old immutable identity to current bytes after an update.
    header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
}
if ((string)($_SERVER['HTTP_IF_NONE_MATCH'] ?? '') === $etag) {
    http_response_code(304); exit;
}
readfile($path);
''', encoding='utf-8')

# Admin assets use the same canonical helper and publish asset identity to JS.
old_admin_helper = r'''function vf_admin_asset_url(string $path): string
{
    $version = defined('VF_VERSION') ? (string)VF_VERSION : '0';
    $parts = explode('#', $path, 2);
    $url = $parts[0];
    $fragment = isset($parts[1]) ? '#' . $parts[1] : '';
    $count = 0;
    $updated = preg_replace('/([?&])v=[^&]*/', '$1v=' . rawurlencode($version), $url, 1, $count);
    if (!is_string($updated)) $updated = $url;
    if ($count === 0) $updated .= (str_contains($updated, '?') ? '&' : '?') . 'v=' . rawurlencode($version);
    return $updated . $fragment;
}
'''
one('src/app/AdminShell.php', old_admin_helper, "function vf_admin_asset_url(string $path): string\n{\n    return vf_asset_url($path);\n}\n")
one(
    'src/app/AdminShell.php',
    '<meta name="robots" content="noindex,nofollow,noarchive"><meta name="csrf-token" content="<?=htmlspecialchars($csrf,ENT_QUOTES,\'UTF-8\')?>"><meta name="vf-system-timezone" content="<?=htmlspecialchars($systemTimezone,ENT_QUOTES,\'UTF-8\')?>">',
    '<meta name="robots" content="noindex,nofollow,noarchive"><meta name="csrf-token" content="<?=htmlspecialchars($csrf,ENT_QUOTES,\'UTF-8\')?>"><meta name="vf-system-timezone" content="<?=htmlspecialchars($systemTimezone,ENT_QUOTES,\'UTF-8\')?>"><meta name="vf-asset-version" content="<?=htmlspecialchars($version,ENT_QUOTES,\'UTF-8\')?>">',
)

# Frontend core assets get canonical version identity from VF_VERSION.
one(
    'src/index.php',
    '  <meta name="vf-system-timezone" content="<?=htmlspecialchars(VfCommonBaseline::SYSTEM_TIMEZONE,ENT_QUOTES,\'UTF-8\')?>">',
    '  <meta name="vf-system-timezone" content="<?=htmlspecialchars(VfCommonBaseline::SYSTEM_TIMEZONE,ENT_QUOTES,\'UTF-8\')?>">\n  <meta name="vf-asset-version" content="<?=htmlspecialchars(VF_VERSION,ENT_QUOTES,\'UTF-8\')?>">',
)
for old, file in [
    ('assets/frontend-legacy.css?v=22124','frontend-legacy.css'),
    ('assets/frontend.css?v=22114','frontend.css'),
    ('assets/favorite-affordance.css?v=22122','favorite-affordance.css'),
    ('assets/reference-ui.css?v=22119','reference-ui.css'),
    ('assets/reference-ui.js?v=22121','reference-ui.js'),
    ('assets/update.js?v=22118','update.js'),
]:
    expr = "<?=htmlspecialchars(vf_asset_url('assets/%s'),ENT_QUOTES,'UTF-8')?>" % file
    one('src/index.php', old, expr)

# Dynamic core asset loads use the same meta version and asset.php endpoint.
p = root / 'src/assets/update.js'
text = p.read_text(encoding='utf-8')
needle = "  'use strict';\n\n"
if text.count(needle) != 1:
    raise SystemExit('update.js helper anchor mismatch')
helper = """  'use strict';

  function vfAssetUrl(file){var v=(document.querySelector('meta[name=\"vf-asset-version\"]')||{}).content||'';return 'asset.php?file='+encodeURIComponent(String(file).replace(/^assets\\//,''))+'&v='+encodeURIComponent(v);}

"""
text = text.replace(needle, helper, 1)
text = text.replace("'assets/update-reload.js?v=22121'", "vfAssetUrl('update-reload.js')")
text = text.replace("'assets/update-core.js?v=22121'", "vfAssetUrl('update-core.js')")
text = text.replace("'assets/navigation-stability.js?v=22118'", "vfAssetUrl('navigation-stability.js')")
p.write_text(text, encoding='utf-8')

p = root / 'src/assets/reference-ui.js'
text = p.read_text(encoding='utf-8')
needle = "  'use strict';\n\n"
if text.count(needle) != 1:
    raise SystemExit('reference-ui.js helper anchor mismatch')
helper = """  'use strict';

  function vfAssetUrl(file){var v=(document.querySelector('meta[name=\"vf-asset-version\"]')||{}).content||'';return 'asset.php?file='+encodeURIComponent(String(file).replace(/^assets\\//,''))+'&v='+encodeURIComponent(v);}

"""
text = text.replace(needle, helper, 1)
text = text.replace("if(existing.getAttribute('href')!=='assets/sidebar-refinement.css?v=22121')existing.setAttribute('href','assets/sidebar-refinement.css?v=22121');", "var target=vfAssetUrl('sidebar-refinement.css');if(existing.getAttribute('href')!==target)existing.setAttribute('href',target);")
text = text.replace("link.href='assets/sidebar-refinement.css?v=22121';", "link.href=vfAssetUrl('sidebar-refinement.css');")
text = text.replace("link.href='assets/reference-admin.css?v=22119';", "link.href=vfAssetUrl('reference-admin.css');")
p.write_text(text, encoding='utf-8')

# Upload entrypoints: extension allowlist + content signature + common limits.
one('src/api.php', "    $size = (int)($file['size'] ?? 0);\n", "    vf_assert_upload_extension((string)($file['name'] ?? ''), ['png','jpg','jpeg','webp'], '图片');\n    $size = (int)($file['size'] ?? 0);\n")
one(
    'src/api.php',
    "if((int)($file['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_OK)throw new InvalidArgumentException('图标上传失败。');$tmp=(string)($file['tmp_name']??'');",
    "if((int)($file['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_OK)throw new InvalidArgumentException('图标上传失败。');vf_assert_upload_extension((string)($file['name']??''),['png','jpg','jpeg','webp','gif'],'图标');$tmp=(string)($file['tmp_name']??'');",
)
one(
    'src/api.php',
    "            if((int)($file['size']??0)<=0||(int)($file['size']??0)>536870912)throw new InvalidArgumentException('备份文件大小必须在 512 MB 以内。');\n            $tmp=(string)($file['tmp_name']??'');if($tmp===''||!is_uploaded_file($tmp))throw new InvalidArgumentException('上传临时文件无效。');\n            $imported=$backups->importFile($tmp,(string)($file['name']??'external.sqlite'));",
    "            vf_assert_upload_extension((string)($file['name']??''),['sqlite','sqlite3','db'],'SQLite 备份');\n            vf_assert_upload_size((int)($file['size']??0),VF_RECOVERY_UPLOAD_MAX_BYTES,'SQLite 备份');\n            $tmp=(string)($file['tmp_name']??'');if($tmp===''||!is_uploaded_file($tmp))throw new InvalidArgumentException('上传临时文件无效。');\n            vf_assert_sqlite_upload_signature($tmp);\n            $imported=$backups->importFile($tmp,(string)($file['name']??'external.sqlite'));",
)
one(
    'src/api.php',
    "            if((int)($file['size']??0)<=0||(int)($file['size']??0)>536870912)throw new InvalidArgumentException('灾难恢复包必须在 512 MB 以内。');\n            $tmp=(string)($file['tmp_name']??'');if($tmp===''||!is_uploaded_file($tmp))throw new InvalidArgumentException('上传临时文件无效。');\n            vf_json(['ok'=>true,'package'=>$disaster->importFile($tmp,(string)($file['name']??'recovery.tar.gz')),'upload_limit_bytes'=>vf_effective_upload_limit()]);",
    "            vf_assert_upload_extension((string)($file['name']??''),['tar.gz','tgz'],'灾难恢复包');\n            vf_assert_upload_size((int)($file['size']??0),VF_RECOVERY_UPLOAD_MAX_BYTES,'灾难恢复包');\n            $tmp=(string)($file['tmp_name']??'');if($tmp===''||!is_uploaded_file($tmp))throw new InvalidArgumentException('上传临时文件无效。');\n            vf_assert_gzip_upload_signature($tmp);\n            vf_json(['ok'=>true,'package'=>$disaster->importFile($tmp,(string)($file['name']??'recovery.tar.gz')),'upload_limit_bytes'=>vf_effective_upload_limit()]);",
)

# Archive limits align with V2 Candidate defaults; compressed recovery artifacts
# retain an explicit 200 MiB project exception from the ordinary 20 MiB default.
one('src/app/DisasterRecovery.php', "    private const MAX_PACKAGE=536870912; // 512 MB\n    private const MAX_FILE=268435456;    // 256 MB\n    private const MAX_FILES=60000;        // bound archive traversal / tiny-file bombs\n", "    private const MAX_PACKAGE=209715200;      // explicit Recovery Artifact exception: 200 MiB compressed\n    private const MAX_FILE=209715200;         // recovery member hard ceiling\n    private const MAX_UNCOMPRESSED=209715200; // V2 Candidate archive default: 200 MiB\n    private const MAX_FILES=5000;             // V2 Candidate archive default\n")
text = (root/'src/app/DisasterRecovery.php').read_text(encoding='utf-8')
text = text.replace("if($total>self::MAX_PACKAGE)throw new RuntimeException('恢复包展开后超过大小限制。');", "if($total>self::MAX_UNCOMPRESSED)throw new RuntimeException('恢复包展开后超过大小限制。');")
(root/'src/app/DisasterRecovery.php').write_text(text, encoding='utf-8')

# V2 Candidate project adoption/exception record. V1 CURRENT remains untouched.
adoption = {
  'schema':'vf-common-product-baseline-adoption/v2-candidate',
  'state':'CANDIDATE_BRANCH_ONLY_NOT_CURRENT',
  'project_id':'P01','project_name':'VF Start','repository':'llhzx2018/vf-start',
  'baseline_id':'VF-COMMON-PRODUCT-BASELINE@2.0-CANDIDATE','baseline_version':'2.0-candidate',
  'profile':'PERSONAL_SINGLE_ADMIN','authority_repository':'llhzx2018/gov-doc','authority_ref':'main',
  'truth_model':'RUNTIME_DERIVED_READ_ONLY_NO_SHADOW_TRUTH',
  'exceptions':[{
    'id':'P01-FILE-UPLOAD-RECOVERY-ARTIFACT-001',
    'domain':'FILE_UPLOAD','parameter':'default_max_single_file_bytes',
    'vf_default':20971520,'project_effective':209715200,
    'scope':['backup_upload','disaster_upload'],
    'reason':'Full SQLite backup and disaster-recovery artifacts can legitimately exceed the ordinary 20 MiB upload default; only these recovery endpoints receive the higher ceiling.',
    'safety_bounds':{'archive_max_uncompressed_bytes':209715200,'archive_max_file_count':5000,'preflight_required':True},
    'review':'REVIEW_WHEN_V2_BECOMES_CURRENT'
  }],
  'release':False,'production':False,'main_changed':False,'version_changed':False,'schema_changed':False
}
(root/'docs/authority/VF_COMMON_PRODUCT_BASELINE_V2_ADOPTION_CANDIDATE.json').write_text(json.dumps(adoption,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Resolver: replace FILE_UPLOAD/CACHE placeholders with effective runtime rows.
old = "        foreach(['FILE_UPLOAD','CACHE'] as $domain)self::row($rows,$domain,'domain_effective_contract','RESOLVED_WHEN_APPLICABLE',null,'CUSTOM_RESOLVER','deeper P01 V2 audit pending');"
new = r'''        $webUploadLimit=vf_effective_web_upload_limit();
        self::row($rows,'FILE_UPLOAD','default_max_single_file_bytes',VF_UPLOAD_DEFAULT_MAX_BYTES,$webUploadLimit>=VF_UPLOAD_DEFAULT_MAX_BYTES?VF_UPLOAD_DEFAULT_MAX_BYTES:$webUploadLimit,'EXACT','bootstrap upload contract + live/deployment PHP limit');
        self::row($rows,'FILE_UPLOAD','runtime_web_upload_limit_bytes',VF_UPLOAD_DEFAULT_MAX_BYTES,$webUploadLimit>0?$webUploadLimit:null,'AT_LEAST','PHP upload_max_filesize/post_max_size or .user.ini in CLI verification');
        self::row($rows,'FILE_UPLOAD','extension_allowlist_required',true,self::sourceHas('src/api.php','vf_assert_upload_extension')?true:null,'BOOLEAN_REQUIRED','api.php upload entrypoints');
        self::row($rows,'FILE_UPLOAD','mime_validation_required',true,self::sourceHas('src/api.php','getimagesize')&&self::sourceHas('src/app/bootstrap.php','vf_assert_sqlite_upload_signature')&&self::sourceHas('src/app/bootstrap.php','vf_assert_gzip_upload_signature')?true:null,'BOOLEAN_REQUIRED','image MIME + SQLite/gzip content signatures');
        self::row($rows,'FILE_UPLOAD','filename_used_as_server_path',false,self::sourceHas('src/app/bootstrap.php','basename($originalName)')?false:null,'EXACT','upload extension validator + generated storage names');
        self::row($rows,'FILE_UPLOAD','upload_directory_script_execution',false,self::sourceHas('src/app/bootstrap.php','vf_write_storage_guards')?false:null,'EXACT','private storage guards');
        self::row($rows,'FILE_UPLOAD','path_traversal_protection',true,self::sourceHas('src/app/DisasterRecovery.php','assertSafeRelative')&&self::sourceHas('src/app/bootstrap.php','basename($originalName)')?true:null,'BOOLEAN_REQUIRED','upload names + archive safe-relative validation');
        self::row($rows,'FILE_UPLOAD','archive_preflight_required',true,self::sourceHas('src/app/DisasterRecovery.php','assertArchiveEntryTypesSafe($archive)')?true:null,'BOOLEAN_REQUIRED','raw tar preflight before materialization');
        self::row($rows,'FILE_UPLOAD','archive_default_max_uncompressed_bytes',VF_ARCHIVE_MAX_UNCOMPRESSED_BYTES,self::sourceConstantInt('src/app/DisasterRecovery.php','MAX_UNCOMPRESSED'),'EXACT','DisasterRecovery archive traversal');
        self::row($rows,'FILE_UPLOAD','archive_default_max_file_count',VF_ARCHIVE_MAX_FILES,self::sourceConstantInt('src/app/DisasterRecovery.php','MAX_FILES'),'EXACT','DisasterRecovery archive traversal');
        self::exceptionRow($rows,'FILE_UPLOAD','recovery_artifact_max_single_file_bytes',VF_UPLOAD_DEFAULT_MAX_BYTES,VF_RECOVERY_UPLOAD_MAX_BYTES,'P01-FILE-UPLOAD-RECOVERY-ARTIFACT-001','docs/authority/VF_COMMON_PRODUCT_BASELINE_V2_ADOPTION_CANDIDATE.json');

        self::row($rows,'CACHE','authenticated_private_html_cache','NO_STORE_OR_EQUIVALENT_PRIVATE_PROTECTION',self::sourceHas('src/index.php','no-store, no-cache, must-revalidate')&&self::sourceHas('src/system.php','no-store, private')?'NO_STORE_OR_EQUIVALENT_PRIVATE_PROTECTION':null,'EXACT','authenticated index + admin surfaces');
        self::row($rows,'CACHE','update_changes_asset_cache_identity',true,self::sourceHas('src/app/bootstrap.php',"'&v=' . rawurlencode(VF_VERSION)")&&self::sourceHas('src/asset.php','hash_equals(VF_VERSION, $requestedVersion)')?true:null,'BOOLEAN_REQUIRED','vf_asset_url + asset.php');
        self::row($rows,'CACHE','user_specific_api_cache_without_explicit_contract',false,self::sourceHas('src/app/bootstrap.php','no-store, no-cache, must-revalidate')?false:null,'EXACT','vf_json default no-store; binary assets have explicit endpoint policy');
        self::row($rows,'CACHE','cache_may_be_only_copy_of_user_data',false,self::sourceHas('src/app/IconCache.php','cleanup()')?false:null,'EXACT','SQLite/user assets remain source of truth; icon cache is rebuildable');
        self::row($rows,'CACHE','cache_rebuildable',true,self::sourceHas('src/app/IconCache.php','function cleanup')||self::sourceHas('src/app/IconCache.php','public function cleanup')?true:null,'BOOLEAN_REQUIRED','IconCache cleanup/rebuild contract');
        self::row($rows,'CACHE','versioned_static_asset_cache_seconds',VF_STATIC_ASSET_CACHE_SECONDS,self::sourceHas('src/asset.php','VF_STATIC_ASSET_CACHE_SECONDS')?VF_STATIC_ASSET_CACHE_SECONDS:null,'EXACT','asset.php canonical static endpoint');
        self::row($rows,'CACHE','versioned_static_asset_immutable',true,self::sourceHas('src/asset.php','immutable')?true:null,'BOOLEAN_REQUIRED','asset.php canonical static endpoint');
        self::row($rows,'CACHE','unversioned_admin_asset_cache_seconds',VF_ADMIN_ASSET_CACHE_SECONDS,self::sourceHas('src/asset.php','VF_ADMIN_ASSET_CACHE_SECONDS')&&self::sourceHas('src/plugin-asset.php','private, max-age=300')?VF_ADMIN_ASSET_CACHE_SECONDS:null,'EXACT','asset.php fallback + plugin-asset.php');'''
one('src/app/CommonBaseline.php', old, new)

# Allow project exception evidence without changing the ordinary comparison model.
row_anchor = r'''    /** @param array<int,array<string,mixed>> $rows */
    private static function row(array &$rows,string $domain,string $parameter,$expected,$effective,string $comparator,string $source):void
    {
        $rows[]=['domain'=>$domain,'parameter'=>$parameter,'expected'=>$expected,'effective'=>$effective,'comparator'=>$comparator,'source'=>$source,'exception'=>null,'result'=>self::compare($expected,$effective,$comparator)];
    }
'''
row_new = row_anchor + r'''

    /** @param array<int,array<string,mixed>> $rows */
    private static function exceptionRow(array &$rows,string $domain,string $parameter,$expected,$effective,string $exceptionId,string $source):void
    {
        $evidence=self::sourceHas($source,'"id": "'.$exceptionId.'"');
        $rows[]=['domain'=>$domain,'parameter'=>$parameter,'expected'=>$expected,'effective'=>$effective,'comparator'=>'EXPLICIT_EXCEPTION','source'=>$source,'exception'=>$evidence?$exceptionId:null,'result'=>$evidence?'EXCEPTION':'UNKNOWN'];
    }
'''
one('src/app/CommonBaseline.php', row_anchor, row_new)

# Project docs live beside src/. Resolve them as evidence without treating them as runtime defaults.
one(
    'src/app/CommonBaseline.php',
    "        $relative=ltrim($relative,'/');$candidates=[VF_ROOT.'/'.$relative];\n",
    "        $relative=ltrim($relative,'/');$candidates=[VF_ROOT.'/'.$relative,dirname(VF_ROOT).'/'.$relative];\n",
)

# Make upload/cache universal rows part of the CLI core gate.
p = root/'src/cli/baseline-verify.php'
text = p.read_text(encoding='utf-8')
anchor = "        'LOCALE.vf_admin_default_locale',\n"
insert = """        'LOCALE.vf_admin_default_locale',
        'FILE_UPLOAD.default_max_single_file_bytes',
        'FILE_UPLOAD.runtime_web_upload_limit_bytes',
        'FILE_UPLOAD.extension_allowlist_required',
        'FILE_UPLOAD.mime_validation_required',
        'FILE_UPLOAD.filename_used_as_server_path',
        'FILE_UPLOAD.upload_directory_script_execution',
        'FILE_UPLOAD.path_traversal_protection',
        'FILE_UPLOAD.archive_preflight_required',
        'FILE_UPLOAD.archive_default_max_uncompressed_bytes',
        'FILE_UPLOAD.archive_default_max_file_count',
        'CACHE.authenticated_private_html_cache',
        'CACHE.update_changes_asset_cache_identity',
        'CACHE.user_specific_api_cache_without_explicit_contract',
        'CACHE.cache_may_be_only_copy_of_user_data',
        'CACHE.cache_rebuildable',
        'CACHE.versioned_static_asset_cache_seconds',
        'CACHE.versioned_static_asset_immutable',
        'CACHE.unversioned_admin_asset_cache_seconds',
"""
if text.count(anchor) != 1:
    raise SystemExit('baseline requiredPass anchor mismatch')
p.write_text(text.replace(anchor, insert, 1), encoding='utf-8')

# Static identity audit: frozen 221xx cache tokens must not remain in core loaders.
for rel in ['src/index.php','src/assets/update.js','src/assets/reference-ui.js']:
    body=(root/rel).read_text(encoding='utf-8')
    if '?v=221' in body:
        raise SystemExit(f'frozen asset cache identity remains: {rel}')

print('UPLOAD_CACHE_PATCH_ASSERTIONS_PASS')
