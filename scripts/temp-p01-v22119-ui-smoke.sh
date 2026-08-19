#!/usr/bin/env bash
set -Eeuo pipefail

test -n "${VF_PRIVATE_READ_TOKEN:-}"
git clone -q --depth 1 --branch maintenance/reference-driven-ui-2.21.19-20260819 "https://x-access-token:${VF_PRIVATE_READ_TOKEN}@github.com/llhzx2018/vf-start.git" product
git -C product rev-parse HEAD >/tmp/p01-source-sha

sudo apt-get update -qq
sudo apt-get install -y -qq php-cli php-sqlite3 php-curl php-zip php-xml php-mbstring sqlite3 >/dev/null
command -v google-chrome >/dev/null
mkdir -p "$RUNNER_TEMP/p01-node"; cd "$RUNNER_TEMP/p01-node"; npm init -y >/dev/null 2>&1
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm i --no-audit --no-fund playwright-core@1.57.0 >/dev/null 2>&1
cd "$GITHUB_WORKSPACE"
php -l product/src/index.php >/dev/null
php -l product/src/app/AdminShell.php >/dev/null
node --check product/src/assets/reference-ui.js

cp -a product/src /tmp/p01-ui
php -S 127.0.0.1:18119 -t /tmp/p01-ui >/tmp/p01-server.log 2>&1 & echo $! >/tmp/p01-ui.pid
for i in $(seq 1 30); do curl -fsS -c /tmp/p01-ui.cookies http://127.0.0.1:18119/setup.php -o /tmp/setup.html && break || sleep 1; done
csrf=$(python3 - <<'PY'
import re
s=open('/tmp/setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsSL -b /tmp/p01-ui.cookies -c /tmp/p01-ui.cookies -X POST http://127.0.0.1:18119/setup.php \
  --data-urlencode "setup_csrf=$csrf" --data-urlencode 'site_title=VF Start Reference Preview' \
  --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null

php -r '
require "/tmp/p01-ui/app/bootstrap.php";
$r=new VfRepository(vf_db());$cats=[];
foreach([["工作工具","每天高频打开的工作入口"],["AI 与开发","AI、代码与部署服务"],["内容与资料","阅读、出版与知识资料"],["运营服务","域名、支付与运营平台"]] as $i=>$row){$cats[]=$r->createCategory(["name"=>$row[0],"description"=>$row[1],"is_private"=>0,"sort_order"=>400-$i*10]);}
$links=[[$cats[0],"GitHub","https://github.com/",1],[$cats[0],"Cloudflare","https://www.cloudflare.com/",0],[$cats[0],"CloudPanel","https://www.cloudpanel.io/",0],[$cats[1],"OpenAI","https://openai.com/",1],[$cats[1],"Vercel","https://vercel.com/",0],[$cats[1],"MDN","https://developer.mozilla.org/",0],[$cats[2],"Leanpub","https://leanpub.com/",0],[$cats[2],"Wikipedia","https://www.wikipedia.org/",0],[$cats[2],"Internet Archive","https://archive.org/",0],[$cats[3],"Dynadot","https://www.dynadot.com/",0],[$cats[3],"PayPal","https://www.paypal.com/",0],[$cats[3],"Stripe","https://stripe.com/",0]];
foreach($links as $i=>$x){$r->saveLink(null,["category_id"=>$x[0],"title"=>$x[1],"url"=>$x[2],"description"=>"Synthetic reference fixture","is_private"=>0,"is_favorite"=>$x[3],"sort_order"=>400-$i],"manual");}
echo "FIXTURE_PASS\n";'
php /tmp/p01-ui/cli/verify.php | grep -q 'VERIFY_PASS=YES'
sqlite3 /tmp/p01-ui/private_data/vf.sqlite 'PRAGMA integrity_check;' | grep -qx ok

ADMIN_PASS="$ADMIN_PASS" node "$GITHUB_WORKSPACE/scripts/temp-p01-v22119-ui-smoke.mjs"
