name: TEMP P07 M03 D04 two genuine CloudPanels and actual static PULL
on:
  pull_request:
    branches: [main]
    paths:
      - '.github/workflows/temp-p07-m03-two-cloudpanel-static-pull-20261124.yml'
permissions:
  contents: read
jobs:
  two-vm-readiness:
    if: >-
      github.repository == 'llhzx2018/core-free-runner-public' &&
      github.event.pull_request.user.login == 'llhzx2018' &&
      github.event.pull_request.head.repo.full_name == github.repository &&
      github.head_ref == 'test/p07-m03-web-first-run-20261124'
    runs-on: ubuntu-24.04
    timeout-minutes: 48
    env:
      TARGET_REPO: '{{REPOSITORY}}'
      TARGET_VERSION: '{{TARGET_VERSION}}'
      TARGET_SHA: '{{TARGET_SHA}}'
      TARGET_TREE: '{{TARGET_TREE}}'
      NO_COLOR: '1'
      DEBIAN_FRONTEND: noninteractive
    steps:
      - name: Checkout public registered runner
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
      - name: Exact source lane preflight before virtual machine boot
        shell: bash
        run: |
          set -Eeuo pipefail
          python3 -B scripts/ephemeral_lane_spec.py validate --spec '.github/ephemeral/p07-m03-two-cloudpanel-static-pull-20261124.json' > "$RUNNER_TEMP/p07-vm-spec.json"
          python3 -B scripts/ephemeral_lane_spec.py audit-rendered --spec '.github/ephemeral/p07-m03-two-cloudpanel-static-pull-20261124.json' --input '.github/workflows/temp-p07-m03-two-cloudpanel-static-pull-20261124.yml' > "$RUNNER_TEMP/p07-vm-audit.json"
          python3 -B - "$RUNNER_TEMP/p07-vm-audit.json" "$TARGET_SHA" <<'PY'
          import json,sys
          p=json.load(open(sys.argv[1]))
          assert p["status"]=="PASS" and p["target_sha"]==sys.argv[2]
          print("P07_D04_DEBIAN13_VM_SOURCE_IDENTITY_AUDIT=PASS")
          PY
      - name: Transient exact P07 private candidate source
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: llhzx2018/vf-server-ops
          ref: ${{ env.TARGET_SHA }}
          token: ${{ secrets.VF_PRIVATE_READ_TOKEN }}
          fetch-depth: 1
          persist-credentials: false
          path: .p07-private
      - name: Verify exact P07 source tree before VM transfer
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          P="$GITHUB_WORKSPACE/.p07-private"
          test "$(git -C "$P" rev-parse HEAD)" = "$TARGET_SHA"
          test "$(git -C "$P" rev-parse HEAD^{tree})" = "$TARGET_TREE"
          for p in BUILD_ID VERSION lib/server_migration_pull.py lib/cloudpanel.py bin/vfops-migrate-ui; do
            test -f "$P/$p"
          done
          echo P07_D04_EXACT_PRIVATE_PRODUCT_RUNTIME=PASS
      - name: Validate official CloudPanel VM-only boundary and free KVM requirements
        shell: bash
        run: |
          set -Eeuo pipefail
          test "$(uname -m)" = x86_64
          test -c /dev/kvm || { echo 'P07_D04_FREE_RUNNER_KVM_UNAVAILABLE'; exit 30; }
          test -r /dev/kvm && test -w /dev/kvm || sudo chmod 666 /dev/kvm
          test -r /dev/kvm && test -w /dev/kvm || { echo 'P07_D04_FREE_RUNNER_KVM_PERMISSION_BLOCK'; exit 31; }
          awk '/MemAvailable:/{if ($2 < 8000000) exit 32}' /proc/meminfo || { echo 'P07_D04_VM_RAM_INSUFFICIENT'; exit 32; }
          avail="$(df --output=avail -k "$RUNNER_TEMP" | tail -1)"
          test "$avail" -ge 8500000 || { echo 'P07_D04_VM_DISK_INSUFFICIENT'; exit 33; }
          sudo apt-get -qq update >/dev/null
          sudo apt-get -y -qq install --no-install-recommends qemu-system-x86 qemu-utils cloud-image-utils openssh-client > "$RUNNER_TEMP/p07-vm-apt.log" 2>&1 || {
            echo 'P07_D04_FREE_RUNNER_VM_PACKAGES_UNAVAILABLE'; exit 34;
          }
          command -v qemu-system-x86_64
          command -v cloud-localds
          qemu-system-x86_64 -accel help | grep -Fq kvm || { echo 'P07_D04_VM_KVM_ACCEL_NOT_SUPPORTED'; exit 35; }
          echo P07_D04_TWO_INDEPENDENT_VM_FREE_HOSTED_RUNNER_READY=PASS
      - name: Boot two real Debian13 QEMU KVM guests and verify SSH separation
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          umask 077
          T="$(mktemp -d "$RUNNER_TEMP/p07-d04-two-vm.XXXXXXXX")"
          echo "$T" > "$RUNNER_TEMP/p07-vm-directory"
          cd "$T"
          image_url='https://cdimage.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2'
          sums_url='https://cdimage.debian.org/images/cloud/trixie/latest/SHA512SUMS'
          curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error --retry 2 --max-time 420 "$image_url" -o debian13.qcow2
          curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error --retry 2 --max-time 90 "$sums_url" -o SHA512SUMS
          ln -s debian13.qcow2 debian-13-genericcloud-amd64.qcow2
          grep -E '^[0-9a-f]{128}  (\./)?debian-13-genericcloud-amd64.qcow2$' SHA512SUMS | sed 's@  \./@  @' | sha512sum -c - >/dev/null || {
            echo P07_D04_OFFICIAL_DEBIAN_IMAGE_HASH_UNVERIFIED; exit 36;
          }
          ssh-keygen -q -t ed25519 -N '' -f "$T/key"
          pub="$(cat "$T/key.pub")"
          cat > userdata <<EOF
          #cloud-config
          disable_root: false
          ssh_pwauth: false
          users:
            - name: root
              lock_passwd: true
              ssh_authorized_keys:
                - "$pub"
          EOF
          for side in source target; do
            cp debian13.qcow2 "$side.qcow2"
            qemu-img resize "$side.qcow2" 16G >/dev/null
            cp userdata "$side-userdata"
            printf 'instance-id: p07-%s\nlocal-hostname: p07-%s\n' "$side" "$side" > "$side-meta"
            cloud-localds "$side-seed.iso" "$side-userdata" "$side-meta"
          done
          qemu-system-x86_64 -enable-kvm -m 2600 -smp 2 \
            -drive file="$T/source.qcow2",format=qcow2,if=virtio \
            -drive file="$T/source-seed.iso",format=raw,if=virtio \
            -netdev user,id=net0,hostfwd=tcp:127.0.0.1:22021-:22 \
            -device virtio-net-pci,netdev=net0 \
            -netdev socket,id=lan,listen=127.0.0.1:24242 \
            -device virtio-net-pci,netdev=lan -display none -monitor none \
            -serial file:"$T/source-serial.log" -daemonize -pidfile "$T/source.pid"
          qemu-system-x86_64 -enable-kvm -m 2600 -smp 2 \
            -drive file="$T/target.qcow2",format=qcow2,if=virtio \
            -drive file="$T/target-seed.iso",format=raw,if=virtio \
            -netdev user,id=net0,hostfwd=tcp:127.0.0.1:22022-:22 \
            -device virtio-net-pci,netdev=net0 \
            -netdev socket,id=lan,connect=127.0.0.1:24242 \
            -device virtio-net-pci,netdev=lan -display none -monitor none \
            -serial file:"$T/target-serial.log" -daemonize -pidfile "$T/target.pid"
          for side in source target; do
            port=22021
            test "$side" = target && port=22022
            ready=0
            for trial in $(seq 1 70); do
              if ssh -q -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$T/known_hosts" \
                -o ConnectTimeout=5 -o BatchMode=yes -i "$T/key" -p "$port" root@127.0.0.1 \
                'test "$(cat /etc/os-release | grep VERSION_ID)" = "VERSION_ID=\"13\"" && test "$(uname -m)" = x86_64' >/dev/null 2>&1; then
                ready=1
                break
              fi
              sleep 5
            done
            test "$ready" = 1 || { echo "P07_D04_DEBIAN13_${side}_VM_SSH_NOT_READY"; exit 38; }
            echo "P07_D04_DEBIAN13_${side}_VM_SEPARATE_SSH=PASS"
          done
          srcid="$(ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22021 root@127.0.0.1 cat /etc/machine-id)"
          dstid="$(ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22022 root@127.0.0.1 cat /etc/machine-id)"
          test -n "$srcid" && test -n "$dstid" && test "$srcid" != "$dstid" || {
            echo P07_D04_TWO_VM_INDEPENDENT_MACHINE_ID_UNPROVEN; exit 39;
          }
          echo P07_D04_TWO_INDEPENDENT_DEBIAN13_VM_BOOT_SSH_KVM=PASS
          echo P07_D04_CLOUDPANEL_INSTALLED=NOT_RUN
          echo P07_D04_SOURCE_TARGET_P07_PULL=NOT_RUN
          echo P07_D04_PRODUCTION_AND_DNS=UNTOUCHED
      - name: Install hash-pinned genuine CloudPanel on both Debian13 KVM guests
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          test -s "$RUNNER_TEMP/p07-vm-directory"
          T="$(cat "$RUNNER_TEMP/p07-vm-directory")"
          case "$T" in "$RUNNER_TEMP"/p07-d04-two-vm.*) ;; *) echo P07_D04_ISOLATION_DIRECTORY_UNVERIFIED; exit 51 ;; esac
          test -r "$T/key" && test -r "$T/known_hosts"
          # Two separate source/target QEMU disks; installer checks pinned
          # upstream SHA before execution. All installer logs stay private.
          pids=()
          for side in source target; do
            port=22021
            test "$side" = target && port=22022
            (
              ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" \
                -o BatchMode=yes -o ConnectTimeout=7 -i "$T/key" -p "$port" root@127.0.0.1 bash -se <<'GUEST'
          set -Eeuo pipefail
          export DEBIAN_FRONTEND=noninteractive
          test "$( . /etc/os-release; echo "$VERSION_ID")" = '13'
          test "$(awk '/MemTotal:/{print $2}' /proc/meminfo)" -ge 1900000
          test "$(df -k / | awk 'NR==2{print $4}')" -ge 9000000
          timeout 160 apt-get -qq update
          timeout 160 apt-get -y -qq install --no-install-recommends curl wget sudo ca-certificates
          cd /root
          curl --proto '=https' --tlsv1.2 -fLsS --retry 2 --max-time 100 https://installer.cloudpanel.io/ce/v2/install.sh -o install.sh
          echo '8146dbe0a488e7088b04071b0c34d59aa0ab1fe9dcec382d395fd155c9e6c476  install.sh' | sha256sum -c -
          timeout 1140 env DB_ENGINE=MYSQL_8.4 bash install.sh < /dev/null
          command -v clpctl >/dev/null
          test -f /home/clp/htdocs/app/data/db.sq3
          systemctl is-active --quiet nginx
          systemctl is-active --quiet mysql
          ss -lnt | grep -Eq ':8443[[:space:]]'
          echo P07_D04_GENUINE_CLOUDPANEL_MYSQL84_VM=PASS
          GUEST
            ) > "$T/$side-cloudpanel-install.log" 2>&1 &
            pids+=("$!")
          done
          # Fail closed, no retry or restart/cleanup of an unknown guest.
          status=0
          wait "${pids[0]}" || { echo P07_D04_SOURCE_CLOUDPANEL_INSTALL_FAILED; status=52; }
          wait "${pids[1]}" || { echo P07_D04_TARGET_CLOUDPANEL_INSTALL_FAILED; status=53; }
          if test "$status" -ne 0; then
            echo P07_D04_GENUINE_DUAL_CLOUDPANEL_E2E=BLOCKED
            exit "$status"
          fi
          grep -Fxq P07_D04_GENUINE_CLOUDPANEL_MYSQL84_VM=PASS "$T/source-cloudpanel-install.log"
          grep -Fxq P07_D04_GENUINE_CLOUDPANEL_MYSQL84_VM=PASS "$T/target-cloudpanel-install.log"
          echo P07_D04_TWO_REAL_DEBIAN13_CLOUDPANEL_MYSQL84_VMS=PASS
          echo P07_D04_REAL_P07_PULL_AND_SITE_DATA_PARITY=NOT_RUN
          echo P07_D04_FORMAL_RELEASE=NOT_AUTHORIZED
      - name: Verify two actual databases and create one source-only CloudPanel static site
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          T="$(cat "$RUNNER_TEMP/p07-vm-directory")"
          case "$T" in "$RUNNER_TEMP"/p07-d04-two-vm.*) ;; *) exit 61 ;; esac
          P="$GITHUB_WORKSPACE/.p07-private"
          test "$(git -C "$P" rev-parse HEAD)" = "$TARGET_SHA"
          test "$(git -C "$P" rev-parse HEAD^{tree})" = "$TARGET_TREE"
          for side in source target; do
            port=22021
            test "$side" = target && port=22022
            tar -C "$P" --exclude='.git' -cf - bin lib components VERSION BUILD_ID |
              ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" \
                -i "$T/key" -p "$port" root@127.0.0.1 \
                'install -d -m 0700 /root/p07exact && tar -C /root/p07exact -xf -'
            if ! ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p "$port" root@127.0.0.1 bash -se <<'GUEST' > "$T/engine-$side.log" 2>&1; then
          set -Eeuo pipefail
          test -f /home/clp/htdocs/app/data/db.sq3 || { echo P07_D04_GUEST_PANEL_DB_MISSING; exit 71; }
          if ! command -v rsync >/dev/null || ! command -v crontab >/dev/null; then
            timeout 150 apt-get -qq update >/dev/null 2>&1
            timeout 150 apt-get -y -qq install --no-install-recommends rsync cron >/dev/null 2>&1 || {
              echo P07_D04_GUEST_MIGRATION_DEPS_MISSING;exit 72;
            }
          fi
          # Exercise genuine CloudPanel first-run HTTPS (local guest loopback only).
          # CLI user:add does NOT prove the first-run Web lifecycle completed.
          # Fail closed if the installed upstream form differs; never forge DB rows.
          python3 -B - <<'WEB'
          import http.cookiejar, re, secrets, sqlite3, ssl, urllib.parse, urllib.request
          from html.parser import HTMLParser
          from pathlib import Path

          base='https://127.0.0.1:8443'
          db=Path('/home/clp/htdocs/app/data/db.sq3')
          def count_users():
              try:
                  con=sqlite3.connect(f'file:{db}?mode=ro',uri=True,timeout=4)
                  try:
                      return int(con.execute('SELECT count(*) FROM "user"').fetchone()[0])
                  finally:
                      con.close()
              except (OSError,sqlite3.Error,TypeError,ValueError):
                  return None
          if count_users()!=0:
              print('P07_D04_GUEST_WEB_ADMIN_INITIAL_STATE_UNVERIFIED')
              raise SystemExit(78)
          class Forms(HTMLParser):
              def __init__(self):
                  super().__init__();self.forms=[];self.cur=None;self.select=None
              def handle_starttag(self,tag,attrs):
                  a=dict(attrs)
                  if tag=='form':
                      if self.cur is None:
                          self.cur={'action':a.get('action',''),'method':a.get('method','get').lower(),'fields':{},'options':{}}
                  elif self.cur is not None and tag=='input':
                      name=a.get('name')
                      if name and a.get('type','text').lower() not in ('submit','button','reset','file','image'):
                          self.cur['fields'][name]=a.get('value','')
                  elif self.cur is not None and tag=='select':
                      self.select=a.get('name')
                      if self.select:self.cur['fields'][self.select]=''
                  elif self.cur is not None and tag=='option' and self.select:
                      self.cur['options'].setdefault(self.select,[]).append(a.get('value',''))
                  elif self.cur is not None and tag=='button' and a.get('type')=='submit' and a.get('name'):
                      self.cur['fields'][a['name']]=a.get('value','')
              def handle_endtag(self,tag):
                  if tag=='select':self.select=None
                  if tag=='form' and self.cur is not None:
                      self.forms.append(self.cur);self.cur=None;self.select=None
          def kind(name):
              k=re.sub('[^a-z0-9]','',name.lower())
              if 'csrf' in k or 'token' in k:return 'hidden'
              if 'password' in k or 'passwd' in k:return 'password'
              if 'username' in k:return 'username'
              if 'firstname' in k:return 'first'
              if 'lastname' in k:return 'last'
              if 'email' in k:return 'email'
              if 'timezone' in k:return 'timezone'
              if 'role' in k:return 'role'
              return 'other'
          class LocalRedirect(urllib.request.HTTPRedirectHandler):
              def redirect_request(self,request,fp,code,msg,headers,url):
                  u=urllib.parse.urlsplit(url)
                  if (u.scheme,u.netloc)!=('https','127.0.0.1:8443'):
                      raise ValueError('Nonlocal first-run redirect rejected')
                  return super().redirect_request(request,fp,code,msg,headers,url)
          ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
          ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
          op=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),LocalRedirect())
          try:
              with op.open(base+'/',timeout=18) as res:
                  page=res.read(160000).decode('utf-8','replace');page_url=res.url
          except Exception:
              print('P07_D04_GUEST_WEB_ADMIN_FIRST_PAGE_UNAVAILABLE')
              raise SystemExit(79)
          if urllib.parse.urlsplit(page_url).netloc!='127.0.0.1:8443':
              print('P07_D04_GUEST_WEB_ADMIN_PAGE_ORIGIN_REJECTED')
              raise SystemExit(80)
          forms=Forms();forms.feed(page)
          candidates=[f for f in forms.forms if f['method']=='post' and {'username','password','email'}.issubset({kind(x) for x in f['fields']})]
          if len(candidates)!=1:
              print('P07_D04_GUEST_WEB_ADMIN_FIRST_FORM_UNRECOGNIZED')
              raise SystemExit(81)
          form=candidates[0]
          dest=urllib.parse.urljoin(page_url,form['action'] or '')
          u=urllib.parse.urlsplit(dest)
          if (u.scheme,u.netloc)!=('https','127.0.0.1:8443'):
              print('P07_D04_GUEST_WEB_ADMIN_SUBMIT_ORIGIN_REJECTED')
              raise SystemExit(82)
          password=secrets.token_urlsafe(36)
          fields=dict(form['fields'])
          for name in fields:
              t=kind(name)
              if t=='username':fields[name]='p07-ci-admin'
              elif t=='email':fields[name]='p07-ci-admin@example.invalid'
              elif t=='first':fields[name]='Synthetic'
              elif t=='last':fields[name]='Admin'
              elif t=='password':fields[name]=password
              elif t in ('timezone','role'):
                  candidates=form['options'].get(name,[])
                  allowed=['UTC','Etc/UTC'] if t=='timezone' else ['admin']
                  value=next((x for x in allowed if not candidates or x in candidates),None)
                  if value is None:
                      print('P07_D04_GUEST_WEB_ADMIN_OPTIONS_UNSUPPORTED')
                      raise SystemExit(83)
                  fields[name]=value
          req=urllib.request.Request(dest,urllib.parse.urlencode(fields).encode(),headers={'Content-Type':'application/x-www-form-urlencoded','Referer':page_url},method='POST')
          try:
              with op.open(req,timeout=30) as res:
                  if urllib.parse.urlsplit(res.url).netloc!='127.0.0.1:8443':
                      raise ValueError('Nonlocal redirect')
                  res.read(10000)
          except Exception:
              print('P07_D04_GUEST_WEB_ADMIN_FIRST_POST_FAILED')
              raise SystemExit(84)
          if count_users()!=1:
              print('P07_D04_GUEST_WEB_ADMIN_CREATION_NOT_CONFIRMED')
              raise SystemExit(85)
          print('P07_D04_GUEST_WEB_ADMIN_FIRST_RUN_CONFIRMED=PASS')
          WEB
          python3 -B - <<'PY'
          import sys
          sys.path.insert(0,'/root/p07exact/lib')
          import server_migration_pull as p
          import migration_target_cloudpanel_environment as cp
          # Classify both independent failures before exiting. Never log SQL,
          # credentials, raw DB metadata or arbitrary guest exception text.
          registration_ok=cp.cloudpanel_database_server_ready()
          engine=p.local_target_active_db_engine_version()
          engine_ok=engine in ('MYSQL_8.4','MYSQL_8.4_PERCONA')
          if not registration_ok:
              print('P07_D04_GUEST_CLOUDPANEL_DB_REGISTRATION_INCOMPLETE')
          if not engine_ok:
              print('P07_D04_GUEST_ACTIVE_DATABASE_ENGINE_UNPROVEN')
          if not registration_ok or not engine_ok:
              raise SystemExit(73 if not registration_ok else 74)
          with open('/root/p07-db-release','w') as out:
              out.write(engine+'\n')
          print('P07_D04_PRODUCT_NATIVE_ACTIVE_ENGINE_PROOF=PASS')
          PY
          GUEST
              # Only fixed whitelist codes leave the discarded, root-only guest log.
              # Preserve fail-closed behavior even if no known marker is present.
              for marker in \
                P07_D04_GUEST_WEB_ADMIN_INITIAL_STATE_UNVERIFIED \
                P07_D04_GUEST_WEB_ADMIN_FIRST_PAGE_UNAVAILABLE \
                P07_D04_GUEST_WEB_ADMIN_PAGE_ORIGIN_REJECTED \
                P07_D04_GUEST_WEB_ADMIN_FIRST_FORM_UNRECOGNIZED \
                P07_D04_GUEST_WEB_ADMIN_SUBMIT_ORIGIN_REJECTED \
                P07_D04_GUEST_WEB_ADMIN_OPTIONS_UNSUPPORTED \
                P07_D04_GUEST_WEB_ADMIN_FIRST_POST_FAILED \
                P07_D04_GUEST_WEB_ADMIN_CREATION_NOT_CONFIRMED \
                P07_D04_GUEST_PANEL_DB_MISSING \
                P07_D04_GUEST_MIGRATION_DEPS_MISSING \
                P07_D04_GUEST_PANEL_USER_LIST_UNVERIFIED \
                P07_D04_GUEST_PANEL_ADMIN_PREFLIGHT_FAILED \
                P07_D04_GUEST_OFFICIAL_INITIAL_ADMIN_CLI_FAILED \
                P07_D04_GUEST_INITIAL_ADMIN_NOT_REGISTERED \
                P07_D04_GUEST_CLOUDPANEL_DB_REGISTRATION_INCOMPLETE \
                P07_D04_GUEST_ACTIVE_DATABASE_ENGINE_UNPROVEN; do
                if grep -Fxq "$marker" "$T/engine-$side.log"; then
                  printf 'P07_D04_DIAG_%s_%s\n' "$side" "${marker#P07_D04_GUEST_}"
                fi
              done
              echo P07_D04_GUEST_ENGINE_PRECHECK_FAILED
              exit 62
            fi
            grep -Fxq P07_D04_PRODUCT_NATIVE_ACTIVE_ENGINE_PROOF=PASS "$T/engine-$side.log"
          done
          a="$(ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22021 root@127.0.0.1 'cat /root/p07-db-release')"
          b="$(ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22022 root@127.0.0.1 'cat /root/p07-db-release')"
          test "$a" = "$b" || { echo P07_D04_ACTUAL_DB_ENGINE_FLAVOR_MISMATCH; exit 63; }
          case "$a" in MYSQL_8.4|MYSQL_8.4_PERCONA) ;; *) echo P07_D04_ACTUAL_DB_NOT_MYSQL84;exit 64 ;; esac
          echo P07_D04_TWO_CLOUDPANEL_REAL_ACTIVE_DB_ENGINE_MATCH=PASS
          ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22021 root@127.0.0.1 bash -se <<'SOURCE' > "$T/source-site.log" 2>&1
          set -Eeuo pipefail
          clpctl site:add:static --domainName=static-p07.example.test --siteUser=p07static --siteUserPassword=Synthetic2026SiteOnlySecure123
          root=/home/p07static/htdocs/static-p07.example.test
          test -d "$root"
          printf 'P07_TEST_STATIC_SITE_REAL_CLOUDPANEL_SHA_TARGET_2026\n' > "$root/index.html"
          chown p07static:p07static "$root/index.html"
          test "$(cat "$root/index.html")" = "P07_TEST_STATIC_SITE_REAL_CLOUDPANEL_SHA_TARGET_2026"
          echo P07_D04_REAL_CLOUDPANEL_SOURCE_STATIC_SITE=PASS
          SOURCE
          grep -Fxq P07_D04_REAL_CLOUDPANEL_SOURCE_STATIC_SITE=PASS "$T/source-site.log" || {
            echo P07_D04_SOURCE_STATIC_SITE_PROVISION_FAILED; exit 65;
          }
          echo P07_D04_SOURCE_SITE_FROM_REAL_CLOUDPANEL=PASS
      - name: Establish isolated target-to-source SSH LAN with pinned host identity
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          T="$(cat "$RUNNER_TEMP/p07-vm-directory")"
          for side in source target; do
            port=22021
            ip=172.28.77.1
            if test "$side" = target; then port=22022;ip=172.28.77.2; fi
            ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p "$port" root@127.0.0.1 bash -se -- "$ip" <<'GUEST' > "$T/lan-$side.log" 2>&1
          set -Eeuo pipefail
          addr="$1"
          primary="$(ip -o -4 route show default | awk '{print $5;exit}')"
          test -n "$primary"
          iface=""
          for candidate in /sys/class/net/*; do
            name="$(basename "$candidate")"
            case "$name" in lo) continue ;; esac
            test "$name" != "$primary" || continue
            if test -z "$iface"; then iface="$name"; else echo EXTRA_NETWORK_DEVICE;exit 14;fi
          done
          test -n "$iface"
          ip link set dev "$iface" up
          ip addr add "$addr/30" dev "$iface"
          ip -o -4 addr show dev "$iface" | grep -Fq "$addr/30"
          echo P07_D04_GUEST_PRIVATE_CROSS_LAN_READY=PASS
          GUEST
            grep -Fxq P07_D04_GUEST_PRIVATE_CROSS_LAN_READY=PASS "$T/lan-$side.log" || {
              echo P07_D04_PRIVATE_LAN_CONFIGURATION_FAILED;exit 66;
            }
          done
          ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22021 root@127.0.0.1 'cat /etc/ssh/ssh_host_ed25519_key.pub' > "$T/source-host.pub"
          pub="$(cut -d' ' -f1,2 "$T/source-host.pub")"
          printf '172.28.77.1 %s\n' "$pub" > "$T/lan-known-hosts"
          scp -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -P 22022 "$T/key" "$T/lan-known-hosts" root@127.0.0.1:/root/
          ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22022 root@127.0.0.1 bash -se <<'TARGET'
          set -Eeuo pipefail
          install -m 0700 -d /root/.ssh
          chmod 0600 /root/key
          chmod 0600 /root/lan-known-hosts
          ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/lan-known-hosts -o BatchMode=yes -i /root/key -p 22 root@172.28.77.1 'test -f /home/p07static/htdocs/static-p07.example.test/index.html'
          TARGET
          echo P07_D04_REAL_TARGET_TO_SOURCE_PRIVATE_SSH=PASS
      - name: Run exact P07 M03 D04 PULL PLAN and PREPARE on real target CloudPanel
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          T="$(cat "$RUNNER_TEMP/p07-vm-directory")"
          P="$GITHUB_WORKSPACE/.p07-private"
          test "$(git -C "$P" rev-parse HEAD)" = "$TARGET_SHA"
          test "$(git -C "$P" rev-parse HEAD^{tree})" = "$TARGET_TREE"
          tar -C "$P" --exclude='.git' -cf - bin lib components VERSION BUILD_ID |
            ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" \
              -i "$T/key" -p 22022 root@127.0.0.1 \
              'install -d -m 0700 /root/p07exact && tar -C /root/p07exact -xf -'
          ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22022 root@127.0.0.1 bash -se <<'TARGET' > "$T/p07-full-pull.log" 2>&1 || {
            grep -Eo '(BATCH_[A-Z_]+|D04_[A-Z_]+|CURRENT_SERVER_[A-Z_]+|SOURCE_[A-Z_]+|CLOUDPANEL_[A-Z_]+|TARGET_[A-Z_]+)' "$T/p07-full-pull.log" | sort -u | head -n 25 || true
            echo P07_D04_REAL_CLOUDPANEL_STATIC_P07_PULL_BLOCKED
            exit 67
          }
          set -Eeuo pipefail
          set +x
          export PYTHONDONTWRITEBYTECODE=1 NO_COLOR=1
          install -m 0700 -d /var/lib/vf-server-ops
          command -v rsync >/dev/null
          command -v crontab >/dev/null
          test -f /root/p07exact/lib/server_migration_pull.py
          test -r /root/key
          test -r /root/lan-known-hosts
          args=(--source-ip 172.28.77.1 --identity-file /root/key --site static-p07.example.test)
          python3 -B /root/p07exact/lib/server_migration_pull.py plan "${args[@]}" \
            --confirm-source-helper-staging ALLOW_SOURCE_HELPER_STAGING \
            > /root/p07-plan.json 2> /root/p07-plan.log
          python3 - <<'PY'
          import json
          plan=json.load(open('/root/p07-plan.json'))
          assert plan['operation']=='PLAN' and plan['status']=='READY'
          assert plan['site_count']==1 and plan['mysql_database_count']==0
          assert plan['automatic_dns_change'] is False
          print('P07_D04_REAL_CLOUDPANEL_SOURCE_P07_PLAN=PASS')
          PY
          python3 -B /root/p07exact/lib/server_migration_pull.py prepare "${args[@]}" \
            --confirm PREPARE_PULL_MIGRATION \
            > /root/p07-prepare.json 2> /root/p07-prepare.log
          python3 - <<'PY'
          import json
          receipt=json.load(open('/root/p07-prepare.json'))
          assert receipt['status']=='PREPARED'
          assert receipt['site_count']==1
          assert receipt['dns_changed_by_p07'] is False
          assert receipt['source_delete_allowed'] is False
          assert receipt['existing_target_overwrite_allowed'] is False
          print('P07_D04_REAL_CLOUDPANEL_STATIC_P07_PREPARED=PASS')
          PY
          target=/home/p07static/htdocs/static-p07.example.test/index.html
          test -f "$target"
          test "$(cat "$target")" = P07_TEST_STATIC_SITE_REAL_CLOUDPANEL_SHA_TARGET_2026
          test "$(ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/lan-known-hosts -i /root/key root@172.28.77.1 cat "$target")" = "$(cat "$target")"
          echo P07_D04_REAL_SOURCE_TO_TARGET_FILE_CONTENT_PARITY=PASS
          if python3 -B /root/p07exact/lib/server_migration_pull.py prepare "${args[@]}" \
            --confirm PREPARE_PULL_MIGRATION > /root/p07-replay.json 2> /root/p07-replay.log; then
            echo P07_D04_UNSAFE_REPLAY_ACCEPTED
            exit 68
          fi
          test "$(cat "$target")" = P07_TEST_STATIC_SITE_REAL_CLOUDPANEL_SHA_TARGET_2026
          echo P07_D04_REAL_SECOND_PREPARE_REPLAY_BLOCK=PASS
          echo P07_D04_CUTOVER_AND_DNS=NOT_RUN
          TARGET
          for marker in P07_D04_REAL_CLOUDPANEL_SOURCE_P07_PLAN=PASS \
            P07_D04_REAL_CLOUDPANEL_STATIC_P07_PREPARED=PASS \
            P07_D04_REAL_SOURCE_TO_TARGET_FILE_CONTENT_PARITY=PASS \
            P07_D04_REAL_SECOND_PREPARE_REPLAY_BLOCK=PASS; do
            grep -Fxq "$marker" "$T/p07-full-pull.log" || exit 69
            echo "$marker"
          done
          echo P07_D04_FULL_VPS_MULTI_SITE_MIGRATION=NOT_RUN
          echo P07_D04_MYSQL_SQLITE_APP_E2E=NOT_RUN
          echo P07_D04_FORMAL_RELEASE=NOT_AUTHORIZED
      - name: Always stop QEMU guests, erase keys, qcow2 and ephemeral files
        if: always()
        shell: bash
        run: |
          set +e
          if test -s "$RUNNER_TEMP/p07-vm-directory"; then
            T="$(cat "$RUNNER_TEMP/p07-vm-directory")"
            case "$T" in "$RUNNER_TEMP"/p07-d04-two-vm.*)
              for side in source target; do
                if test -f "$T/$side.pid"; then
                  pid="$(cat "$T/$side.pid")"
                  if test -n "$pid" && test "$pid" -eq "$pid" 2>/dev/null; then
                    kill "$pid" 2>/dev/null || true
                  fi
                fi
              done
              rm -rf -- "$T"
            ;; esac
          fi
          rm -rf -- "$GITHUB_WORKSPACE/.p07-private"
          rm -f -- "$RUNNER_TEMP/p07-vm-directory" "$RUNNER_TEMP/p07-vm-spec.json" "$RUNNER_TEMP/p07-vm-audit.json" "$RUNNER_TEMP/p07-vm-apt.log"
          echo P07_D04_TRANSIENT_TWO_VM_PRIVATE_KEYS_AND_DISKS_CLEANUP=PASS
