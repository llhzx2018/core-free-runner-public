#!/usr/bin/env bash
set -Eeuo pipefail
OUT=/tmp/p01-four-sites-r2
mkdir -p "$OUT"
: >"$OUT/summary.txt"
analyze(){
  local name="$1" url="$2" html="$OUT/$1.html" cand="$OUT/$1.candidates.txt"
  printf '\n=== %s ===\nURL=%s\n' "$name" "$url" | tee -a "$OUT/summary.txt"
  if ! curl --fail --silent --show-error --location --max-time 25 -A 'VF-Start/2.37.0 CoverCache' -H 'Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.1' "$url" -o "$html"; then
    printf 'PAGE_FETCH=FAIL\n' | tee -a "$OUT/summary.txt"; return 0
  fi
  python3 - "$html" <<'PY' | tee -a "$OUT/summary.txt"
import re,sys
from pathlib import Path
s=Path(sys.argv[1]).read_text('utf-8','ignore')
def n(p): return len(re.findall(p,s,re.I|re.S))
print('BYTES='+str(len(s.encode())))
print('OG_IMAGE='+str(n(r'<meta[^>]+(?:og:image|twitter:image|image_src)[^>]*>')))
print('IMG_TAGS='+str(n(r'<img\b[^>]*>')))
print('DATA_ORIGINAL='+str(n(r'\bdata-original\s*=')))
print('DATA_SRC='+str(n(r'\bdata-src\s*=')))
print('JSON_LD='+str(n(r'application/ld\+json')))
for pat,label in [(r'injectJson\s*=\s*([^;]+)','INJECT_JSON'),(r'<script[^>]+src=["\']([^"\']+)','SCRIPT_SRC')]:
    vals=re.findall(pat,s,re.I|re.S)
    for v in vals[:8]: print(label+'='+re.sub(r'\s+',' ',v)[:300])
PY
  php -r "require 'product/src/app/ResourceCoverCache.php'; \$c=VfResourceCoverCache::extractCoverCandidates(file_get_contents('$html'),'$url'); echo 'CANDIDATES='.count(\$c).PHP_EOL; foreach(array_slice(\$c,0,12) as \$x) echo \$x,PHP_EOL;" | tee "$cand" | tee -a "$OUT/summary.txt"
  first="$(sed -n '2p' "$cand" || true)"
  if [[ "$first" =~ ^https?:// ]]; then
    if curl --fail --silent --show-error --location --max-time 25 -A 'VF-Start/2.37.0 CoverCache' -H 'Accept: image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.1' "$first" -o "$OUT/$name.bin"; then
      printf 'FIRST_FETCH=PASS\nFIRST_MIME=%s\nFIRST_BYTES=%s\n' "$(file --mime-type -b "$OUT/$name.bin")" "$(stat -c%s "$OUT/$name.bin")" | tee -a "$OUT/summary.txt"
    else printf 'FIRST_FETCH=FAIL\n' | tee -a "$OUT/summary.txt"; fi
  else printf 'FIRST_FETCH=SKIP_NO_CANDIDATE\n' | tee -a "$OUT/summary.txt"; fi
}
analyze iyf_desktop_play 'https://www.iyf.tv/play/dKzMjpczMIT'
analyze xiaoya_post 'https://xiaoyakankan.com/post/bc8df8d8c2.html'
printf '\nP01_FOUR_SITE_R2=COMPLETE\n' | tee -a "$OUT/summary.txt"
cat "$OUT/summary.txt"
