from pathlib import Path


def read(p): return Path(p).read_text(encoding='utf-8')
def write(p,t): Path(p).write_text(t.rstrip()+'\n',encoding='utf-8')
def replace_once(t,old,new,label):
    if old not in t: raise SystemExit(f'{label} anchor missing')
    return t.replace(old,new,1)

# 1) Repository: extract one canonical pending-capture path and preserve Browser Helper API.
p='src/app/Repository.php'; t=read(p)
t=replace_once(t,"$browserSource=in_array($source,['browser-extension','browser-gateway'],true);","$browserSource=in_array($source,['browser-extension','browser-gateway','mobile-quick-save'],true);",'capture source allowlist')
old=r'''    public function saveBrowserLink(array $data): array
    {
        $url = vf_validate_url((string)($data['url'] ?? ''));
        $duplicate = $this->db->prepare("SELECT id,title,url,category_id,is_pending FROM links WHERE url=? AND lifecycle_state='active' ORDER BY id LIMIT 1");
        $duplicate->execute([$url]);
        $existing = $duplicate->fetch(PDO::FETCH_ASSOC);
        if ($existing) {
            return [
                'id'=>(int)$existing['id'],
                'duplicate'=>true,
                'title'=>(string)$existing['title'],
                'url'=>(string)$existing['url'],
                'category_id'=>(int)$existing['category_id'],
                'pending'=>(int)($existing['is_pending']??0)===1,
            ];
        }
        $data['category_id'] = $this->browserInboxCategoryId();
        $data['url'] = $url;
        $data['url_type'] = 'normal';
        $data['url_protected'] = false;
        $data['is_private'] = true;
        $data['is_pending'] = true;
        $data['is_favorite'] = false;
        foreach (['affiliate_network','affiliate_merchant','affiliate_campaign','affiliate_tracking_id','affiliate_commission_note','affiliate_starts_at','affiliate_ends_at','affiliate_last_confirmed_at','affiliate_status','backup_affiliate_url','prevent_rewrite'] as $key) unset($data[$key]);
        return $this->saveLink(null, $data, 'browser-extension');
    }
'''
new=r'''    /**
     * Canonical fast-capture path. Browser Helper and mobile quick-save both land in
     * the same private Pending inbox; callers may not choose category, visibility or
     * favorite state. Existing URLs are never silently changed or re-pended.
     */
    public function savePendingCapture(array $data, string $source = 'browser-extension'): array
    {
        if (!in_array($source, ['browser-extension','browser-gateway','mobile-quick-save'], true)) {
            throw new InvalidArgumentException('快速收集来源无效。');
        }
        $url = vf_validate_url((string)($data['url'] ?? ''));
        $duplicate = $this->db->prepare("SELECT id,title,url,category_id,is_pending FROM links WHERE url=? AND lifecycle_state='active' ORDER BY id LIMIT 1");
        $duplicate->execute([$url]);
        $existing = $duplicate->fetch(PDO::FETCH_ASSOC);
        if ($existing) {
            return [
                'id'=>(int)$existing['id'],
                'duplicate'=>true,
                'title'=>(string)$existing['title'],
                'url'=>(string)$existing['url'],
                'category_id'=>(int)$existing['category_id'],
                'pending'=>(int)($existing['is_pending']??0)===1,
            ];
        }
        $data['category_id'] = $this->browserInboxCategoryId();
        $data['url'] = $url;
        $data['url_type'] = 'normal';
        $data['url_protected'] = false;
        $data['is_private'] = true;
        $data['is_pending'] = true;
        $data['is_favorite'] = false;
        foreach (['affiliate_network','affiliate_merchant','affiliate_campaign','affiliate_tracking_id','affiliate_commission_note','affiliate_starts_at','affiliate_ends_at','affiliate_last_confirmed_at','affiliate_status','backup_affiliate_url','prevent_rewrite','force_duplicate'] as $key) unset($data[$key]);
        return $this->saveLink(null, $data, $source);
    }

    public function saveBrowserLink(array $data): array
    {
        return $this->savePendingCapture($data, 'browser-extension');
    }
'''
t=replace_once(t,old,new,'saveBrowserLink refactor')
t=t.replace("l.source_type IN ('browser-extension','browser-gateway')","l.source_type IN ('browser-extension','browser-gateway','mobile-quick-save')",1)
write(p,t)

# 2) New authenticated quick-save page. GET only prefills; POST + CSRF performs mutation.
quick=r'''<?php
declare(strict_types=1);
require_once __DIR__ . '/app/bootstrap.php';
require_once __DIR__ . '/app/SurfaceRepository.php';
require_once __DIR__ . '/app/SurfaceShell.php';

if (!vf_is_installed()) { header('Location: setup.php'); exit; }
vf_security_headers(true);
header('X-Robots-Tag: noindex, nofollow, noarchive');
header('Cache-Control: no-store, private');
if (!vf_is_admin()) { header('Location: ./'); exit; }

function vf_quick_save_url_from_input(string $url, string $text = ''): string
{
    $candidate = trim($url);
    if ($candidate !== '') return $candidate;
    if (preg_match('#https?://[^\s<>"\']+#iu', $text, $match) === 1) {
        return rtrim((string)$match[0], ".,，。;；:：!！?？)]}）】》〉");
    }
    return '';
}

function vf_quick_save_title(string $title, string $url): string
{
    $title = vf_clean_text($title, 300);
    if ($title !== '') return $title;
    $validated = vf_validate_url($url);
    $host = strtolower(trim((string)(parse_url($validated, PHP_URL_HOST) ?: '')));
    $host = (string)preg_replace('/^www\./i', '', $host);
    return $host !== '' ? $host : $validated;
}

$db = vf_db();
$baseRepo = new VfRepository($db);
$surfaceRepo = new VfSurfaceRepository($db);
$csrf = vf_csrf_token();
$notice = '';$error = '';
$prefillUrl = vf_quick_save_url_from_input((string)($_GET['url'] ?? ''), (string)($_GET['text'] ?? ''));
$prefillTitle = trim((string)($_GET['title'] ?? ''));

if (strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET')) === 'POST') {
    $provided = (string)($_POST['csrf'] ?? '');
    if ($provided === '' || !hash_equals($csrf, $provided)) {
        $error = 'CSRF 校验失败，请刷新后重试。';
    } else {
        $prefillUrl = vf_quick_save_url_from_input((string)($_POST['url'] ?? ''), (string)($_POST['text'] ?? ''));
        $prefillTitle = trim((string)($_POST['title'] ?? ''));
        try {
            $url = vf_validate_url($prefillUrl);
            $title = vf_quick_save_title($prefillTitle, $url);
            $saved = $baseRepo->savePendingCapture(['url'=>$url,'title'=>$title], 'mobile-quick-save');
            if (!empty($saved['duplicate'])) {
                $notice = !empty($saved['pending']) ? '这个网址已经在待整理中。' : '这个网址已经收藏过，没有修改原记录。';
            } else {
                $notice = '已保存到私人待整理。';
                $prefillUrl = '';$prefillTitle = '';
            }
        } catch (Throwable $e) {
            $error = $e->getMessage();
        }
    }
}

$allAssets = $surfaceRepo->allAssets(true);
$counts = ['start'=>0,'channels'=>0,'watch'=>0,'topics'=>0,'total'=>0];
$pending = 0;
foreach ($allAssets as $asset) {
    $surface = (string)($asset['surface'] ?? 'start');
    if (isset($counts[$surface])) $counts[$surface]++;
    $counts['total']++;
    if ((int)($asset['is_pending'] ?? 0) === 1) $pending++;
}

vf_surface_shell_begin(['title'=>'快速收藏','active'=>'inbox','admin'=>true,'counts'=>$counts,'pending'=>$pending,'body_class'=>'vf-workspace-page vf-quick-save-page','allow_add'=>false]);
?>
<section class="vf-workspace-head">
  <div><h1>快速收藏</h1><p>粘贴一个网址即可。这里始终保存为私人待整理，不要求你现在决定分类。</p></div>
  <a class="vf-workspace-button" href="surface-manager.php">打开待整理</a>
</section>
<?php if($notice!==''): ?><div class="vf-inline-notice success" role="status"><?=htmlspecialchars($notice,ENT_QUOTES,'UTF-8')?></div><?php endif; ?>
<?php if($error!==''): ?><div class="vf-inline-notice danger" role="alert"><?=htmlspecialchars($error,ENT_QUOTES,'UTF-8')?></div><?php endif; ?>
<section class="vf-inbox-panel">
  <header><div><h2>保存到待整理</h2><p>从手机快捷方式、主屏入口或未来 Android Share Target 传来的网址也会先停在这里。</p></div></header>
  <form method="post" class="vf-workspace-form">
    <input type="hidden" name="csrf" value="<?=htmlspecialchars($csrf,ENT_QUOTES,'UTF-8')?>">
    <label class="vf-field vf-field-wide"><span>网址</span><input type="url" name="url" required inputmode="url" autocomplete="url" placeholder="https://" value="<?=htmlspecialchars($prefillUrl,ENT_QUOTES,'UTF-8')?>"></label>
    <label class="vf-field vf-field-wide"><span>标题 <small>可留空，自动使用网站域名</small></span><input name="title" maxlength="300" autocomplete="off" value="<?=htmlspecialchars($prefillTitle,ENT_QUOTES,'UTF-8')?>"></label>
    <footer><a class="vf-secondary-button" href="home.php">返回首页</a><button type="submit" class="vf-primary-button">保存到待整理</button></footer>
  </form>
</section>
<section class="vf-workspace-toolbar"><nav><span class="vf-toolbar-link">安全边界</span></nav><span>不公开 · 不自动分类 · 不自动收藏置顶 · 不修改已有重复记录</span></section>
<?php vf_surface_shell_end(); ?>
'''
Path('src/quick-save.php').write_text(quick.rstrip()+'\n',encoding='utf-8')

# 3) Home mobile primary capture goes to the dedicated private-pending quick path.
p='src/app/FunctionalHome.php'; t=read(p)
t=replace_once(t,'<button type="button" data-open-add>＋ 添加</button>','<a href="quick-save.php">＋ 快速收藏</a>','home mobile quick save')
write(p,t)

# 4) Preserve the existing compact mobile treatment for the anchor.
p='src/assets/workspace-home.css'; t=read(p)
old='.vf-home-mobile-command>button{height:38px;flex:0 0 auto;padding:0 10px;border:1px solid var(--ws-teal);border-radius:8px;background:var(--ws-teal);color:#fff;font-size:11.5px;font-weight:700}'
new='.vf-home-mobile-command>button,.vf-home-mobile-command>a{height:38px;flex:0 0 auto;padding:0 10px;border:1px solid var(--ws-teal);border-radius:8px;background:var(--ws-teal);color:#fff;font-size:11.5px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;text-decoration:none}'
t=replace_once(t,old,new,'home mobile action css')
write(p,t)

print('P01 MOBILE QUICK SAVE FOUNDATION PATCH APPLIED')
