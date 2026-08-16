#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()
p=root/'scripts/build-v251-maintenance-release.py'
s=p.read_text(encoding='utf-8')

# Escape PHP braces inserted into the Python f-string Atomic template.
a="if(class_exists('Web')){Web::headers($cspNonce);}else{"
b="if(class_exists('Web')){{Web::headers($cspNonce);}}else{{"
if s.count(a)!=1: raise SystemExit(f'Atomic CSP open-brace sentinel count={s.count(a)}')
s=s.replace(a,b,1)
a="header('Cache-Control: no-store, private');}$cls='state-'.$state;"
b="header('Cache-Control: no-store, private');}}$cls='state-'.$state;"
if s.count(a)!=1: raise SystemExit(f'Atomic CSP close-brace sentinel count={s.count(a)}')
s=s.replace(a,b,1)

# Atomic source replacement must invalidate runtime code/stat caches before the next
# authenticated request. The transaction API is replace(array $targetFiles).
old="$tx->replace($targetFiles);"
new=old+"clearstatcache();if(function_exists('opcache_reset'))@opcache_reset();"
if s.count(old)!=1: raise SystemExit(f'Atomic replace sentinel count={s.count(old)}')
s=s.replace(old,new,1)

# VF Atomic contract: after successful commit, remove current/old repair artifacts and
# the exact one-time P04 bridge. Protected DB recovery points remain untouched.
old="$tx->commit();$journal->clear();$success=true;"
cleanup=(
    "$tx->commit();$journal->clear();"
    "$cleanupCandidates=glob(__DIR__.'/repair-v*.php')?:[];"
    "$legacyBridge=__DIR__.'/P04_V2.5.1_TO_UNIFIED_UPDATE_BRIDGE.php';"
    "if(is_file($legacyBridge)&&!is_link($legacyBridge))$cleanupCandidates[]=$legacyBridge;"
    "foreach(array_unique($cleanupCandidates) as $garbage){{"
    "if(!is_string($garbage)||!is_file($garbage)||is_link($garbage))continue;"
    "$base=basename($garbage);"
    "if($base==='P04_V2.5.1_TO_UNIFIED_UPDATE_BRIDGE.php'||preg_match('/^repair-v\\d+\\.\\d+\\.\\d+\\.php$/',$base))@unlink($garbage);"
    "}}"
    "$success=true;"
)
if s.count(old)!=1: raise SystemExit(f'Atomic success cleanup sentinel count={s.count(old)}')
s=s.replace(old,cleanup,1)

p.write_text(s,encoding='utf-8')
print('ATOMIC_TEMPLATE_POSTPATCH=PASS')
