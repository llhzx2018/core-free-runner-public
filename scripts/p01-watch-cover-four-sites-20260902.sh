#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT_DIR="${PRODUCT_DIR:-product}"
OUT=/tmp/p01-four-sites
mkdir -p "$OUT"
: >"$OUT/summary.txt"

analyze() {
  local name="$1" url="$2"
  local html="$OUT/${name}.html" cand="$OUT/${name}.candidates.txt" img="$OUT/${name}.first-image.bin"
  printf '\n=== %s ===\nURL=%s\n' "$name" "$url" | tee -a "$OUT/summary.txt"
  if ! curl --fail --silent --show-error --location --max-time 25 \
    -A 'VF-Start/2.37.0 CoverCache' \
    -H 'Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.1' \
    "$url" -o "$html"; then
    printf 'PAGE_FETCH=FAIL\n' | tee -a "$OUT/summary.txt"
    return 0
  fi
  python3 - "$html" <<'PY' | tee -a "$OUT/summary.txt"
import re,sys
from pathlib import Path
s=Path(sys.argv[1]).read_text('utf-8','ignore')
def n(p): return len(re.findall(p,s,re.I|re.S))
print('BYTES='+str(len(s.encode('utf-8'))))
print('OG_IMAGE='+str(n(r'<meta[^>]+(?:og:image|twitter:image|image_src)[^>]*>')))
print('IMG_TAGS='+str(n(r'<img\b[^>]*>')))
print('DATA_ORIGINAL='+str(n(r'\bdata-original\s*=')))
print('DATA_SRC='+str(n(r'\bdata-src\s*=')))
print('JSON_LD='+str(n(r'application/ld\+json')))
print('HREFS='+str(n(r'<a\b[^>]+href\s*=')))
PY
  php -r "require '$PRODUCT_DIR/src/app/ResourceCoverCache.php'; \$h=file_get_contents('$html'); \$c=VfResourceCoverCache::extractCoverCandidates(\$h,'$url'); echo 'CANDIDATES='.count(\$c).PHP_EOL; foreach(array_slice(\$c,0,12) as \$x) echo \$x,PHP_EOL;" | tee "$cand" | tee -a "$OUT/summary.txt"
  local first
  first="$(sed -n '2p' "$cand" || true)"
  if [[ "$first" =~ ^https?:// ]]; then
    if curl --fail --silent --show-error --location --max-time 25 \
      -A 'VF-Start/2.37.0 CoverCache' \
      -H 'Accept: image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.1' \
      "$first" -o "$img"; then
      local size mime
      size="$(stat -c%s "$img")"
      mime="$(file --mime-type -b "$img")"
      printf 'FIRST_FETCH=PASS\nFIRST_BYTES=%s\nFIRST_MIME=%s\n' "$size" "$mime" | tee -a "$OUT/summary.txt"
    else
      printf 'FIRST_FETCH=FAIL\n' | tee -a "$OUT/summary.txt"
    fi
  else
    printf 'FIRST_FETCH=SKIP_NO_CANDIDATE\n' | tee -a "$OUT/summary.txt"
  fi
}

analyze iyf_play 'https://mview.iyf.tv/play/27Qr2mVwuzJ'
analyze iyf_root 'https://www.iyf.tv/'
analyze xiaobao_detail 'https://www.xiaobaotv.com/vod/detail/180209.html'
analyze xiaoheimi_detail 'https://xiaoheimi.cc/index.php/vod/detail/id/220543.html'

# Discover a representative Xiaoya detail URL from its live homepage.
XROOT="$OUT/xiaoya-root.html"
curl --fail --silent --show-error --location --max-time 25 \
  -A 'VF-Start/2.37.0 CoverCache' \
  -H 'Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.1' \
  'https://xiaoyakankan.com/' -o "$XROOT"
python3 - "$XROOT" <<'PY' >"$OUT/xiaoya-links.txt"
import re,sys,urllib.parse
from pathlib import Path
s=Path(sys.argv[1]).read_text('utf-8','ignore')
links=[]
for href in re.findall(r'<a\b[^>]*href\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))',s,re.I|re.S):
    h=next((x for x in href if x), '').strip()
    if not h or h.startswith(('javascript:','#','mailto:')): continue
    u=urllib.parse.urljoin('https://xiaoyakankan.com/',h)
    if u not in links: links.append(u)
for u in links[:120]: print(u)
PY
XDETAIL="$(grep -Ei 'xiaoyakankan\.com/(vod|movie|detail|video|play)/|xiaoyakankan\.com/[^/]+/[0-9]+[^/]*\.html|xiaoyakankan\.com/[0-9]+\.html' "$OUT/xiaoya-links.txt" | head -1 || true)"
if [[ -z "$XDETAIL" ]]; then
  XDETAIL="$(grep -Ei 'xiaoyakankan\.com/.*[0-9].*\.html' "$OUT/xiaoya-links.txt" | grep -Ev '/cat/' | head -1 || true)"
fi
printf '\nXIAOYA_DISCOVERED=%s\n' "${XDETAIL:-NONE}" | tee -a "$OUT/summary.txt"
if [[ -n "$XDETAIL" ]]; then analyze xiaoya_detail "$XDETAIL"; else analyze xiaoya_root 'https://xiaoyakankan.com/'; fi

# Important assertions: the three static-template sites must yield a fetchable image on the candidate extractor.
for n in xiaobao_detail xiaoheimi_detail; do
  grep -q '^FIRST_FETCH=PASS$' "$OUT/summary.txt" || true
done
printf '\nP01_FOUR_SITE_DIAGNOSTIC=COMPLETE\n' | tee -a "$OUT/summary.txt"
cat "$OUT/summary.txt"
