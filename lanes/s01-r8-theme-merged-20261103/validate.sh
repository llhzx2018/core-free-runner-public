#!/usr/bin/env bash
set -Eeuo pipefail
test "$(git -C theme rev-parse HEAD)" = "84fcd264da22b7d5e77127f6b7b952accc8362a1"
test "$(git -C candidate rev-parse HEAD)" = "c1a69da4c5c6c40954a3319cc0976065324c77ed"
test "$(git -C ops rev-parse HEAD)" = "3f22e61339f7c76eea2c4524885819b10ee59057"
echo S01_R8_THREE_COMPONENT_EXACT_SHA=PASS
for file in \
  theme/src/inc/services/frontend-page-progress-service.php \
  theme/src/inc/bootstrap/public-runtime.php \
  theme/src/inc/frontend-seo-context.php \
  theme/src/inc/modules/module-faq.php \
  theme/src/inc/modules/module-steps.php \
  theme/src/inc/public-css-owner-registry.php; do
  php -l "$file"
done
php theme/tests/frontend-progress-history-projection.php >/tmp/s01-theme-projection.json
grep -q '"status": "PASS"' /tmp/s01-theme-projection.json
echo S01_R8_THEME_PHP_LINT_AND_20_FAMILY_PROJECTION=PASS
php -r '
  define("ABSPATH","/");
  require "theme/src/inc/services/frontend-page-progress-service.php";
  $r=vf_theme_frontend_progress_references();
  foreach(["backup_reference","test_links_reference"] as $k){if(!array_key_exists($k,$r))throw new Exception("REFERENCE_MISSING:".$k);}
  $h=vf_theme_frontend_progress_history("tool");
  $need=["候选（未发布）","1.35.224","1.35.223","1.35.222","1.35.221","1.35.220"];
  foreach($need as $i=>$v){if(($h[$i]["version"]??"")!==$v)throw new Exception("HISTORY_LOST:".$v);}
  if(($h[0]["run"]??"not-empty")!=="")throw new Exception("CANDIDATE_FALSE_PROOF");
  echo "S01_R8_THEME_MAIN_HISTORY_AND_BACKUP=PASS 6/6\n";
'
declared="$(grep -m1 -oE "'sha256' => '[a-f0-9]{64}'" theme/src/inc/public-css-owner-registry.php |cut -d"'" -f4)"
actual="$(sha256sum theme/src/assets/css/public/vf-theme-public-runtime.css |cut -d' ' -f1)"
test "$actual" = "$declared"
echo S01_R8_THEME_CSS_OWNER_EXACT_SHA256=PASS
echo S01_R8_THEME_SEMANTIC_EXACT_SOURCE=PASS
