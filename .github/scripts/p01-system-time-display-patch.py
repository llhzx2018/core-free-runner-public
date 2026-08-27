from pathlib import Path

root = Path('p01')


def one(path: str, old: str, new: str) -> None:
    p = root / path
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected 1 match, got {count}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


# Admin Shell publishes the PHP authority timezone into the DOM.
one(
    'src/app/AdminShell.php',
    "    $version = defined('VF_VERSION') ? VF_VERSION : '0';\n    ?><!doctype html>",
    "    $version = defined('VF_VERSION') ? VF_VERSION : '0';\n    $systemTimezone = class_exists('VfCommonBaseline') ? VfCommonBaseline::SYSTEM_TIMEZONE : 'Asia/Shanghai';\n    ?><!doctype html>",
)
one(
    'src/app/AdminShell.php',
    '<meta name="robots" content="noindex,nofollow,noarchive"><meta name="csrf-token" content="<?=htmlspecialchars($csrf,ENT_QUOTES,\'UTF-8\')?>">',
    '<meta name="robots" content="noindex,nofollow,noarchive"><meta name="csrf-token" content="<?=htmlspecialchars($csrf,ENT_QUOTES,\'UTF-8\')?>"><meta name="vf-system-timezone" content="<?=htmlspecialchars($systemTimezone,ENT_QUOTES,\'UTF-8\')?>">',
)

# Shared admin formatter: explicit IANA timezone and stable display shape.
p = root / 'src/assets/admin-shell.js'
text = p.read_text(encoding='utf-8')
needle = "  var TOAST_DURATION={success:2500,info:4000,warning:6000,error:6000},TOAST_MAX_VISIBLE=2;\n"
if text.count(needle) != 1:
    raise SystemExit('admin-shell.js insertion anchor mismatch')
helper = """  var TOAST_DURATION={success:2500,info:4000,warning:6000,error:6000},TOAST_MAX_VISIBLE=2;
  var SYSTEM_TIMEZONE=(document.querySelector('meta[name=\"vf-system-timezone\"]')||{}).content||'';
  function systemTimeParts(value){
    if(!value||!SYSTEM_TIMEZONE)return null;var d=new Date(value);if(isNaN(d.getTime()))return null;
    try{var parts=new Intl.DateTimeFormat('zh-CN',{timeZone:SYSTEM_TIMEZONE,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(d),out={};parts.forEach(function(part){if(part.type!=='literal')out[part.type]=part.value;});return out;}catch(e){return null;}
  }
  function formatSystemInstant(value,compact){var p=systemTimeParts(value);if(!p)return value?String(value):'—';return compact?(p.month+'-'+p.day+' '+p.hour+':'+p.minute):(p.year+'-'+p.month+'-'+p.day+' '+p.hour+':'+p.minute+':'+p.second);}
  window.vfSystemTime={timeZone:SYSTEM_TIMEZONE,format:function(value){return formatSystemInstant(value,false);},formatCompact:function(value){return formatSystemInstant(value,true);}};
"""
p.write_text(text.replace(needle, helper, 1), encoding='utf-8')

# Admin pages use the shared formatter instead of browser-local timezone.
one('src/assets/system.js', "function dt(v){if(!v)return'—';var d=new Date(v);return isNaN(d)?esc(v):d.toLocaleString();}", "function dt(v){if(!v)return'—';return window.vfSystemTime?window.vfSystemTime.format(v):esc(v);}")
one('src/assets/update-core.js', "function fmtTime(value){if(!value)return '尚未检查';var d=new Date(value);return isNaN(d.getTime())?String(value):d.toLocaleString();}", "function fmtTime(value){if(!value)return '尚未检查';return window.vfSystemTime?window.vfSystemTime.format(value):String(value);}")
one('src/assets/jobs.js', "const fmt=x=>x?new Date(x).toLocaleString():'—';", "const fmt=x=>x?(window.vfSystemTime?window.vfSystemTime.format(x):String(x)):'—';")
one('src/assets/data-recovery.js', "const fmt=v=>v?new Date(v).toLocaleString():'—';", "const fmt=v=>v?(window.vfSystemTime?window.vfSystemTime.format(v):String(v)):'—';")
one('src/assets/security.js', "function dt(v){if(!v)return'—';var d=new Date(v);return isNaN(d)?esc(v):d.toLocaleString();}", "function dt(v){if(!v)return'—';return window.vfSystemTime?window.vfSystemTime.format(v):esc(v);}")
one('src/assets/data-safety.js', "const fmt=v=>v?new Date(v).toLocaleString():'—';", "const fmt=v=>v?(window.vfSystemTime?window.vfSystemTime.format(v):String(v)):'—';")
one('src/assets/health.js', "const fmt=x=>x?new Date(x).toLocaleString('zh-CN'):'—';", "const fmt=x=>x?(window.vfSystemTime?window.vfSystemTime.format(x):String(x)):'—';")
one('src/plugins/rss/assets/workspace.js', "function dt(v){if(!v)return '从未';var d=new Date(v);return isNaN(d)?text(v):d.toLocaleString([], {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});}", "function dt(v){if(!v)return '从未';return window.vfSystemTime?window.vfSystemTime.formatCompact(v):text(v);}")

# Main page does not load AdminShell; publish the same authority meta and use a local explicit formatter.
one(
    'src/index.php',
    '  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
    '  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n  <meta name="vf-system-timezone" content="<?=htmlspecialchars(VfCommonBaseline::SYSTEM_TIMEZONE,ENT_QUOTES,\'UTF-8\')?>">',
)
one(
    'src/index.php',
    "function formatDateTime(value){if(!value)return '尚未检查';try{return new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});}catch(e){return String(value);}}",
    "function formatDateTime(value){if(!value)return '尚未检查';var zone=(document.querySelector('meta[name=\"vf-system-timezone\"]')||{}).content||'';var d=new Date(value);if(!zone||isNaN(d.getTime()))return String(value);try{var parts=new Intl.DateTimeFormat('zh-CN',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(d),out={};parts.forEach(function(part){if(part.type!=='literal')out[part.type]=part.value;});return out.year+'-'+out.month+'-'+out.day+' '+out.hour+':'+out.minute+':'+out.second;}catch(e){return String(value);}}",
)
one('src/index.php', "<span>最后 '+esc(item.lastAttemptAt||'—')+'</span>", "<span>最后 '+formatDateTime(item.lastAttemptAt)+'</span>")

# Resolver reflects the runtime/display contract only after source changes are present.
one(
    'src/app/CommonBaseline.php',
    "        self::row($rows,'TIME','user_visible_instant_timezone_source','SYSTEM_TIMEZONE_OR_EXPLICIT_USER_TIMEZONE',null,'CUSTOM_RESOLVER','legacy display audit pending');",
    "        self::row($rows,'TIME','user_visible_instant_timezone_source','SYSTEM_TIMEZONE_OR_EXPLICIT_USER_TIMEZONE','SYSTEM_TIMEZONE_OR_EXPLICIT_USER_TIMEZONE','EXACT','AdminShell/index System Timezone formatter + machine display audit');",
)

# No browser-local date rendering may remain in the audited UI surfaces.
candidates = list((root / 'src/assets').glob('*.js')) + list((root / 'src/plugins').rglob('*.js')) + [root / 'src/index.php']
offenders = []
for file in candidates:
    body = file.read_text(encoding='utf-8')
    if 'toLocaleString(' in body or 'toLocaleDateString(' in body or 'toLocaleTimeString(' in body:
        offenders.append(str(file))
if offenders:
    raise SystemExit('browser-local display remains: ' + ', '.join(offenders))

print('SYSTEM_TIME_DISPLAY_PATCH_ASSERTIONS_PASS')
