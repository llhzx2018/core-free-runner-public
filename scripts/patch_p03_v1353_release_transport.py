from pathlib import Path

p = Path('harness/scripts/p03_v1353_formal_release.sh')
s = p.read_text(encoding='utf-8')
marker = '# Preflight: tag/release must not already exist.\n'
if marker not in s:
    raise SystemExit('release transport marker missing')
head = s.split(marker, 1)[0]
tail = r'''# Transport phase: exact tag via native git push, then draft release, verify all assets, publish once.
TAG_CODE=$(curl -sS -o "$ROOT/tag-pre.json" -w '%{http_code}' "${AUTH[@]}" "$API/git/ref/tags/$TAG")
if [ "$TAG_CODE" = '200' ]; then
  EXISTING_TAG_SHA=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["object"]["sha"])' "$ROOT/tag-pre.json")
  test "$EXISTING_TAG_SHA" = "$CANDIDATE_COMMIT"
  echo FORMAL_TAG_ALREADY_EXACT=PASS
elif [ "$TAG_CODE" = '404' ]; then
  REPO_DIR="$GITHUB_WORKSPACE/p03"
  git -C "$REPO_DIR" tag "$TAG" "$CANDIDATE_COMMIT"
  AUTH64=$(printf 'x-access-token:%s' "$VF_RELEASE_TOKEN" | base64 -w0)
  git -C "$REPO_DIR" -c "http.extraHeader=Authorization: Basic $AUTH64" push https://github.com/llhzx2018/vf-forge.git "refs/tags/$TAG:refs/tags/$TAG" >/dev/null
  unset AUTH64
  echo FORMAL_TAG_NATIVE_PUSH=PASS
else
  echo "Unexpected tag preflight HTTP $TAG_CODE" >&2
  cat "$ROOT/tag-pre.json" >&2 || true
  exit 83
fi
curl -fsS "${AUTH[@]}" "$API/git/ref/tags/$TAG" >"$ROOT/tag-readback.json"
TAG_SHA=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["object"]["sha"])' "$ROOT/tag-readback.json")
test "$TAG_SHA" = "$CANDIDATE_COMMIT"
echo FORMAL_TAG_EXACT_READBACK=PASS

REL_CODE=$(curl -sS -o "$ROOT/release-pre.json" -w '%{http_code}' "${AUTH[@]}" "$API/releases/tags/$TAG")
if [ "$REL_CODE" = '200' ]; then
  echo 'Published release already exists before this transport attempt; refusing overwrite.' >&2
  exit 84
elif [ "$REL_CODE" != '404' ]; then
  echo "Unexpected release preflight HTTP $REL_CODE" >&2
  cat "$ROOT/release-pre.json" >&2 || true
  exit 85
fi

python3 - "$ROOT/release-create.json" "$OUT/VF_Forge_V1.35.3_RELEASE_NOTES.md" "$CANDIDATE_COMMIT" <<'PY'
import json,sys
body=open(sys.argv[2],encoding='utf-8').read()
d={'tag_name':'v1.35.3','target_commitish':sys.argv[3],'name':'VF Forge V1.35.3','body':body,'draft':True,'prerelease':False}
open(sys.argv[1],'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,separators=(',',':')))
PY
REL_CREATE_CODE=$(curl -sS -o "$ROOT/release-created.json" -w '%{http_code}' -X POST "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary @"$ROOT/release-create.json" "$API/releases")
if [ "$REL_CREATE_CODE" != '201' ]; then
  echo "Draft release create failed HTTP $REL_CREATE_CODE" >&2
  cat "$ROOT/release-created.json" >&2 || true
  exit 86
fi
RID=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["draft"] is True; print(d["id"])' "$ROOT/release-created.json")
test -n "$RID"
echo "FORMAL_DRAFT_RELEASE_ID=$RID"

cleanup_draft_on_error(){
  rc=$?
  if [ "$rc" -ne 0 ] && [ -n "${RID:-}" ]; then
    curl -sS -X DELETE "${AUTH[@]}" "$API/releases/$RID" >/dev/null 2>&1 || true
    echo FORMAL_DRAFT_RELEASE_CLEANUP=ATTEMPTED >&2
  fi
  exit "$rc"
}
trap cleanup_draft_on_error ERR

upload(){
  local f="$1" ct="$2" n code
  n=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$f")
  code=$(curl -sS -o "$ROOT/upload-$(basename "$f").json" -w '%{http_code}' -X POST "${AUTH[@]}" -H "Content-Type: $ct" --data-binary @"$f" "https://uploads.github.com/repos/llhzx2018/vf-forge/releases/$RID/assets?name=$n")
  test "$code" = '201'
}
upload VF_Forge_V1.35.3_FULL.zip application/zip
upload VF_Forge_V1.35.3_UPDATE.zip application/zip
upload VF_Forge_V1.35.3_Atomic_Upgrade.zip application/zip
upload repair-v1.35.3.php application/x-php
upload VF_Forge_V1.35.3_RELEASE_MANIFEST.json application/json
upload VF_Forge_V1.35.3_SOURCE_MANIFEST.txt text/plain
upload VF_Forge_V1.35.3_RELEASE_NOTES.md text/markdown
upload SHA256SUMS.txt text/plain

curl -fsS "${AUTH[@]}" "$API/releases/$RID" >"$ROOT/draft-readback.json"
python3 - "$ROOT/draft-readback.json" "$OUT" <<'PY'
import hashlib,json,os,sys
r=json.load(open(sys.argv[1])); root=sys.argv[2]
assert r['tag_name']=='v1.35.3' and r['name']=='VF Forge V1.35.3' and r['draft'] is True and not r['prerelease']
expected=['VF_Forge_V1.35.3_FULL.zip','VF_Forge_V1.35.3_UPDATE.zip','VF_Forge_V1.35.3_Atomic_Upgrade.zip','repair-v1.35.3.php','VF_Forge_V1.35.3_RELEASE_MANIFEST.json','VF_Forge_V1.35.3_SOURCE_MANIFEST.txt','VF_Forge_V1.35.3_RELEASE_NOTES.md','SHA256SUMS.txt']
a={x['name']:x for x in r['assets']}
assert sorted(a)==sorted(expected),(sorted(a),expected)
for n in expected:
    p=os.path.join(root,n); b=os.path.getsize(p); h=hashlib.sha256(open(p,'rb').read()).hexdigest(); x=a[n]
    assert x['size']==b,(n,x['size'],b)
    digest=x.get('digest')
    if digest is not None: assert digest=='sha256:'+h,(n,digest,h)
    print('DRAFT_ASSET_VERIFIED',x['id'],n,b,h)
print('FORMAL_DRAFT_ASSETS_EXACT=PASS')
PY

cat >"$ROOT/release-publish.json" <<'JSON'
{"draft":false,"prerelease":false,"make_latest":"true"}
JSON
PUBLISH_CODE=$(curl -sS -o "$ROOT/release-published.json" -w '%{http_code}' -X PATCH "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary @"$ROOT/release-publish.json" "$API/releases/$RID")
test "$PUBLISH_CODE" = '200'
trap - ERR

curl -fsS "${AUTH[@]}" "$API/releases/tags/$TAG" >"$ROOT/release-readback.json"
python3 - "$ROOT/release-readback.json" "$OUT" <<'PY'
import hashlib,json,os,sys
r=json.load(open(sys.argv[1])); root=sys.argv[2]
assert r['tag_name']=='v1.35.3' and r['name']=='VF Forge V1.35.3' and not r['draft'] and not r['prerelease']
expected=['VF_Forge_V1.35.3_FULL.zip','VF_Forge_V1.35.3_UPDATE.zip','VF_Forge_V1.35.3_Atomic_Upgrade.zip','repair-v1.35.3.php','VF_Forge_V1.35.3_RELEASE_MANIFEST.json','VF_Forge_V1.35.3_SOURCE_MANIFEST.txt','VF_Forge_V1.35.3_RELEASE_NOTES.md','SHA256SUMS.txt']
a={x['name']:x for x in r['assets']}
assert sorted(a)==sorted(expected)
for n in expected:
    p=os.path.join(root,n); b=os.path.getsize(p); h=hashlib.sha256(open(p,'rb').read()).hexdigest(); x=a[n]
    assert x['size']==b
    digest=x.get('digest')
    if digest is not None: assert digest=='sha256:'+h
    print('FORMAL_ASSET',x['id'],n,b,h)
print('FORMAL_RELEASE_ID',r['id'])
print('FORMAL_RELEASE_PUBLISHED_AT',r['published_at'])
print('FORMAL_RELEASE_REMOTE_READBACK=PASS')
PY

echo "FORMAL_RELEASE_ID=$RID"
echo "FORMAL_FULL_SHA=$FULL_SHA FORMAL_FULL_BYTES=$FULL_BYTES"
echo "FORMAL_UPDATE_SHA=$UPDATE_SHA FORMAL_UPDATE_BYTES=$UPDATE_BYTES"
echo "FORMAL_ATOMIC_SHA=$ATOMIC_SHA FORMAL_ATOMIC_BYTES=$ATOMIC_BYTES"
echo "FORMAL_SOURCE_MANIFEST_SHA=$SRC_SHA"
echo FORMAL_RELEASE=PASS
'''
p.write_text(head + tail, encoding='utf-8', newline='\n')
print('P03_RELEASE_TRANSPORT_PATCH=PASS')
