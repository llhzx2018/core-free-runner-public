from pathlib import Path

BASE='e04529d80bd2f50eed617331441eb337a11f3e93'

def read(p): return Path(p).read_text(encoding='utf-8')
def write(p,t): Path(p).write_text(t.rstrip()+'\n',encoding='utf-8')
def replace_once(text, old, new, label):
    if old not in text: raise SystemExit(f'{label} anchor missing')
    return text.replace(old,new,1)

# 1) SurfaceRepository: add deterministic, suggest-only category recommendations.
p='src/app/SurfaceRepository.php'; t=read(p)
anchor='''    public function upsertProfile(int $linkId, array $data): void\n    {'''
method=r'''    /**
     * Suggest an existing Start category for real pending links only.
     * This is deliberately suggest-only: it never creates a category, moves a link,
     * changes visibility, or clears is_pending. The caller must obtain explicit Owner
     * confirmation and use the canonical Repository organize action to apply a choice.
     */
    public function categorySuggestions(array $assets, array $categories, int $limit = 160): array
    {
        $limit = max(1, min(500, $limit));
        $categoryMap = [];
        $categoryPaths = [];
        foreach ($categories as $category) {
            $id = (int)($category['id'] ?? 0);
            if ($id <= 0) continue;
            $categoryMap[$id] = $category;
        }
        foreach ($categoryMap as $id => $category) {
            $parts = [];$cursor = $id;$seen = [];$guard = 0;
            while ($cursor > 0 && isset($categoryMap[$cursor]) && !isset($seen[$cursor]) && $guard++ < 32) {
                $seen[$cursor] = true;
                array_unshift($parts, (string)($categoryMap[$cursor]['name'] ?? ''));
                $parent = $categoryMap[$cursor]['parent_id'] ?? null;
                $cursor = $parent === null ? 0 : (int)$parent;
            }
            $categoryPaths[$id] = implode(' / ', array_values(array_filter($parts, static fn(string $x): bool => trim($x) !== '')));
        }

        $hostFor = static function (string $url): string {
            $host = strtolower(trim((string)(parse_url($url, PHP_URL_HOST) ?? '')));
            $host = rtrim($host, '.');
            return str_starts_with($host, 'www.') ? substr($host, 4) : $host;
        };
        $history = [];
        foreach ($assets as $asset) {
            if ((string)($asset['surface'] ?? 'start') !== 'start' || (int)($asset['is_pending'] ?? 0) === 1) continue;
            $categoryId = (int)($asset['category_id'] ?? 0);
            if ($categoryId <= 0 || !isset($categoryMap[$categoryId])) continue;
            $host = $hostFor((string)($asset['url'] ?? ''));
            if ($host === '') continue;
            $history[$host][$categoryId] = ($history[$host][$categoryId] ?? 0) + 1;
        }

        $suggestions = [];
        foreach ($assets as $asset) {
            if ((string)($asset['surface'] ?? 'start') !== 'start' || (int)($asset['is_pending'] ?? 0) !== 1) continue;
            $currentCategory = (int)($asset['category_id'] ?? 0);
            $suggestedCategory = 0;$confidence = 0;$reason = '';
            $host = $hostFor((string)($asset['url'] ?? ''));

            if ($host !== '' && !empty($history[$host])) {
                $counts = $history[$host];
                arsort($counts, SORT_NUMERIC);
                $topCategory = (int)array_key_first($counts);
                $topCount = (int)($counts[$topCategory] ?? 0);
                $total = max(1, (int)array_sum($counts));
                $share = $topCount / $total;
                if ($topCategory !== $currentCategory && $topCount >= 2 && $share >= 0.60) {
                    $suggestedCategory = $topCategory;
                    $confidence = ($topCount >= 3 && $share >= 0.80) ? 97 : ($share >= 0.75 ? 94 : 90);
                    $reason = $share >= 0.999
                        ? '同一网站过去 '.$topCount.' 次都整理到这个分类'
                        : '同一网站过去 '.$topCount.' / '.$total.' 次整理到这个分类';
                }
            }

            if ($suggestedCategory <= 0) {
                $title = mb_strtolower(trim((string)($asset['title'] ?? '')), 'UTF-8');
                $description = mb_strtolower(trim((string)($asset['description'] ?? '')), 'UTF-8');
                $tags = array_values(array_filter(array_map(static fn($x): string => mb_strtolower(trim((string)$x), 'UTF-8'), (array)($asset['tags'] ?? []))));
                $best = null;
                foreach ($categoryMap as $categoryId => $category) {
                    if ($categoryId === $currentCategory) continue;
                    $name = trim((string)($category['name'] ?? ''));
                    $plain = trim((string)preg_replace('/^[\p{So}\p{Sk}\p{P}\s]+/u', '', $name));
                    if ($plain === '') continue;
                    $needle = mb_strtolower($plain, 'UTF-8');
                    $score = 0;$why = '';
                    if (in_array($needle, $tags, true)) { $score = 88;$why = '标签与现有分类名称一致'; }
                    elseif (mb_strlen($needle, 'UTF-8') >= 2 && ($title === $needle || str_starts_with($title, $needle))) { $score = 86;$why = '标题与现有分类名称高度匹配'; }
                    elseif (mb_strlen($needle, 'UTF-8') >= 2 && mb_strpos($title.' '.$description, $needle, 0, 'UTF-8') !== false) { $score = 82;$why = '标题/描述命中现有分类名称'; }
                    if ($score <= 0) continue;
                    $depth = max(0, (int)($category['depth'] ?? 0));
                    $rank = $score * 100 + min(20, $depth);
                    if ($best === null || $rank > $best['rank']) $best = ['category_id'=>$categoryId,'confidence'=>$score,'reason'=>$why,'rank'=>$rank];
                }
                if ($best !== null) {
                    $suggestedCategory = (int)$best['category_id'];
                    $confidence = (int)$best['confidence'];
                    $reason = (string)$best['reason'];
                }
            }

            if ($suggestedCategory <= 0 || !isset($categoryMap[$suggestedCategory])) continue;
            $suggestions[] = [
                'link_id'=>(int)($asset['id'] ?? 0),
                'title'=>(string)($asset['title'] ?? ''),
                'url'=>(string)($asset['url'] ?? ''),
                'current_category_id'=>$currentCategory,
                'current_category_name'=>(string)($asset['category_name'] ?? ''),
                'category_id'=>$suggestedCategory,
                'category_path'=>(string)($categoryPaths[$suggestedCategory] ?? ($categoryMap[$suggestedCategory]['name'] ?? '')),
                'confidence'=>$confidence,
                'reason'=>$reason,
            ];
        }
        usort($suggestions, static fn(array $a, array $b): int => ($b['confidence'] <=> $a['confidence']) ?: strnatcasecmp((string)$a['title'], (string)$b['title']));
        return array_slice($suggestions, 0, $limit);
    }

'''
t=replace_once(t,anchor,method+anchor,'SurfaceRepository upsertProfile')
write(p,t)

# 2) surface-manager: make Pending a real capture inbox; keep resource-domain suggestions as secondary workflow.
p='src/surface-manager.php'; t=read(p)
t=replace_once(t,"$categories=(array)$base['categories'];\n$csrf = vf_csrf_token();", "$categories=(array)$base['categories'];\n$categoryOptions=$baseRepo->pluginCategories();\n$categoryPathMap=[];foreach($categoryOptions as $categoryOption)$categoryPathMap[(int)$categoryOption['id']]=(string)$categoryOption['path'];\n$csrf = vf_csrf_token();",'manager category options')
old="""            if ($action === 'assign') {\n                $id = max(1,(int)($_POST['link_id'] ?? 0));$surface = (string)($_POST['surface'] ?? 'start');"""
new="""            if ($action === 'organize_category') {\n                $id=max(1,(int)($_POST['link_id']??0));$categoryId=max(1,(int)($_POST['category_id']??0));\n                $check=$db->prepare(\"SELECT id,is_pending FROM links WHERE id=? AND lifecycle_state='active'\");$check->execute([$id]);$row=$check->fetch(PDO::FETCH_ASSOC);\n                if(!$row||(int)($row['is_pending']??0)!==1)throw new RuntimeException('这个网址已经不在待整理中，请刷新后重试。');\n                $baseRepo->bulkLinks([$id],'organize',$categoryId);\n                $notice='已整理到 '.($categoryPathMap[$categoryId]??'所选分类').'。';\n            } elseif ($action === 'assign') {\n                $id = max(1,(int)($_POST['link_id'] ?? 0));$surface = (string)($_POST['surface'] ?? 'start');"""
t=replace_once(t,old,new,'manager organize action')
old="""$allAssets = $repo->allAssets(true);$assets=$allAssets;\nif ($surfaceFilter !== '' && in_array($surfaceFilter,VfSurfaceRepository::SURFACES,true)) $assets = array_values(array_filter($assets,static fn(array $a): bool => (string)$a['surface'] === $surfaceFilter));"""
new="""$allAssets = $repo->allAssets(true);$assets=$allAssets;\n$pendingAssets=array_values(array_filter($allAssets,static fn(array $a):bool=>(string)($a['surface']??'start')==='start'&&(int)($a['is_pending']??0)===1));\n$pendingCount=count($pendingAssets);\n$categorySuggestions=$repo->categorySuggestions($allAssets,$categories,300);\n$categorySuggestionMap=[];foreach($categorySuggestions as $categorySuggestion)$categorySuggestionMap[(int)$categorySuggestion['link_id']]=$categorySuggestion;\nif ($surfaceFilter !== '' && in_array($surfaceFilter,VfSurfaceRepository::SURFACES,true)) $assets = array_values(array_filter($assets,static fn(array $a): bool => (string)$a['surface'] === $surfaceFilter));"""
t=replace_once(t,old,new,'manager pending assets')
t=t.replace('$suggestions = $repo->suggestions(300);','$domainSuggestions = $repo->suggestions(300);',1)
t=t.replace("if($surfaceFilter!==''&&in_array($surfaceFilter,['channels','watch'],true))$suggestions=array_values(array_filter($suggestions,static fn(array $s):bool=>(string)$s['surface']===$surfaceFilter));","if($surfaceFilter!==''&&in_array($surfaceFilter,['channels','watch'],true))$domainSuggestions=array_values(array_filter($domainSuggestions,static fn(array $s):bool=>(string)$s['surface']===$surfaceFilter));",1)
t=t.replace("$highConfidence = count(array_filter($suggestions,static fn(array $s): bool => (int)$s['confidence'] >= 94));","$highConfidence = count(array_filter($domainSuggestions,static fn(array $s): bool => (int)$s['confidence'] >= 94));",1)
t=t.replace("$channelSuggestions = count(array_filter($suggestions,static fn(array $s): bool => (string)$s['surface'] === 'channels'));","$channelSuggestions = count(array_filter($domainSuggestions,static fn(array $s): bool => (string)$s['surface'] === 'channels'));",1)
t=t.replace("$watchSuggestions = count(array_filter($suggestions,static fn(array $s): bool => (string)$s['surface'] === 'watch'));","$watchSuggestions = count(array_filter($domainSuggestions,static fn(array $s): bool => (string)$s['surface'] === 'watch'));",1)
t=t.replace("'pending'=>$highConfidence","'pending'=>$pendingCount",1)
old="""<section class=\"vf-workspace-head\"><div><h1>待整理</h1><p><?=$highConfidence?> 条高置信度建议 · <?=$channelSuggestions?> Channels · <?=$watchSuggestions?> Watch</p></div><a class=\"vf-workspace-button\" href=\"surface-manager.php?advanced=1\">高级管理</a></section>"""
new="""<section class=\"vf-workspace-head\"><div><h1>待整理</h1><p><?=$pendingCount?> 条待整理 · <?=count($categorySuggestions)?> 条已有分类建议 · <?=$highConfidence?> 条资源域高置信度建议</p></div><a class=\"vf-workspace-button\" href=\"surface-manager.php?advanced=1\">高级管理</a></section>"""
t=replace_once(t,old,new,'manager head')
old="""<section class=\"vf-workspace-toolbar\"><nav><a class=\"<?=$surfaceFilter===''?'active':''?>\" href=\"surface-manager.php\">全部建议</a><a class=\"<?=$surfaceFilter==='channels'?'active':''?>\" href=\"surface-manager.php?surface=channels\">Channels</a><a class=\"<?=$surfaceFilter==='watch'?'active':''?>\" href=\"surface-manager.php?surface=watch\">Watch</a></nav><span class=\"vf-toolbar-link\">系统只提出建议，不会静默移动</span></section>\n\n<section class=\"vf-inbox-panel\">"""
new="""<section class=\"vf-workspace-toolbar\"><nav><span class=\"vf-toolbar-link\">先收进来，再慢慢整理；系统只建议，不会自动移动</span></nav><a class=\"vf-toolbar-link\" href=\"start.php\">打开导航 →</a></section>\n\n<section class=\"vf-inbox-panel\">\n  <header><div><h2>待整理网址</h2><p>确认一个现有分类后，这条网址才会离开待整理。</p></div><small><?=count($categorySuggestions)?> 条已有建议</small></header>\n  <?php if(!$pendingAssets): ?><div class=\"vf-workspace-empty\"><strong>待整理已经清空</strong><p>浏览器助手和快速收集的新网址会先回到这里。</p></div><?php else: ?><div class=\"vf-inbox-list\">\n    <?php foreach(array_slice($pendingAssets,0,120) as $pendingAsset): $categorySuggestion=$categorySuggestionMap[(int)$pendingAsset['id']]??null;$selectedCategory=(int)($categorySuggestion['category_id']??$pendingAsset['category_id']??0); ?>\n      <div class=\"vf-inbox-row vf-category-suggestion-row\">\n        <span class=\"vf-confidence<?=!$categorySuggestion?' is-neutral':''?>\"><?=$categorySuggestion?(int)$categorySuggestion['confidence'].'%':'待'?></span>\n        <span><strong><?=htmlspecialchars((string)$pendingAsset['title'],ENT_QUOTES,'UTF-8')?></strong><small><?=htmlspecialchars((string)($pendingAsset['category_name']??''),ENT_QUOTES,'UTF-8')?> · <?=htmlspecialchars((string)$pendingAsset['url'],ENT_QUOTES,'UTF-8')?></small></span>\n        <em><?=$categorySuggestion?htmlspecialchars((string)$categorySuggestion['reason'].' → '.(string)$categorySuggestion['category_path'],ENT_QUOTES,'UTF-8'):'暂时没有足够历史，手动选择一个现有分类即可'?></em>\n        <form method=\"post\" class=\"vf-suggestion-actions vf-inbox-category-form\"><input type=\"hidden\" name=\"csrf\" value=\"<?=htmlspecialchars($csrf,ENT_QUOTES,'UTF-8')?>\"><input type=\"hidden\" name=\"action\" value=\"organize_category\"><input type=\"hidden\" name=\"link_id\" value=\"<?=(int)$pendingAsset['id']?>\"><select name=\"category_id\" class=\"vf-inbox-category-select\" aria-label=\"选择分类\"><?php foreach($categoryOptions as $categoryOption): ?><option value=\"<?=(int)$categoryOption['id']?>\" <?=(int)$categoryOption['id']===$selectedCategory?'selected':''?>><?=htmlspecialchars((string)$categoryOption['path'],ENT_QUOTES,'UTF-8')?></option><?php endforeach; ?></select><button type=\"submit\">确认整理</button></form>\n      </div>\n    <?php endforeach; ?>\n  </div><?php endif; ?>\n</section>\n\n<section class=\"vf-workspace-toolbar\"><nav><span class=\"vf-toolbar-link\">资源域归属建议</span><a class=\"<?=$surfaceFilter===''?'active':''?>\" href=\"surface-manager.php\">全部</a><a class=\"<?=$surfaceFilter==='channels'?'active':''?>\" href=\"surface-manager.php?surface=channels\">频道</a><a class=\"<?=$surfaceFilter==='watch'?'active':''?>\" href=\"surface-manager.php?surface=watch\">影视</a></nav><span class=\"vf-toolbar-link\">独立于分类整理，仍需人工确认</span></section>\n\n<section class=\"vf-inbox-panel\">"""
t=replace_once(t,old,new,'manager toolbar and pending panel')
t=t.replace('<header><div><h2>需要你确认的归属</h2><p>逐条确认最可靠；高置信度内容也可以一次采用。</p></div>', '<header><div><h2>资源域归属建议</h2><p>这里仅判断网址是否更适合频道或影视，不等同于“待整理”。</p></div>',1)
t=t.replace('<?php if(!$suggestions): ?>','<?php if(!$domainSuggestions): ?>',1)
t=t.replace('foreach(array_slice($suggestions,0,100) as $s)','foreach(array_slice($domainSuggestions,0,100) as $s)',1)
write(p,t)

# 3) FunctionalWorkspace: sidebar badge is real is_pending count.
p='src/app/FunctionalWorkspace.php'; t=read(p)
old="$suggestions=$admin?$surfaceRepo->suggestions(300):[];$pending=count(array_filter($suggestions,static fn(array $s):bool=>(int)$s['confidence']>=94));"
new="$pending=$admin?count(array_filter($allAssets,static fn(array $asset):bool=>(int)($asset['is_pending']??0)===1)):0;"
t=replace_once(t,old,new,'workspace pending semantic')
write(p,t)

# 4) Home: same real pending count + human workflow language.
p='src/app/FunctionalHome.php'; t=read(p)
t=replace_once(t,"$suggestions = $surfaceRepo->suggestions(300);\n    $pending = count(array_filter($suggestions, static fn(array $suggestion): bool => (int)($suggestion['confidence'] ?? 0) >= 94));","$pending = count(array_filter($allAssets, static fn(array $asset): bool => (int)($asset['is_pending'] ?? 0) === 1));",'home pending count')
t=t.replace('网址健康与归属建议都处于安静状态。','网址健康、待整理与数据安全都处于安静状态。',1)
t=t.replace('<span class="vf-home-attention-copy"><b>归属建议</b><small>系统只给出建议，确认后再调整资源归属</small></span>','<span class="vf-home-attention-copy"><b>待整理</b><small>先收进来的网址还没有完成分类确认</small></span>',1)
t=t.replace('<i>确认 →</i>','<i>整理 →</i>',1)
write(p,t)

# 5) CSS: small progressive enhancement for category select; reuse inbox layout.
p='src/assets/surface-workspace.css'; t=read(p)
addition=r'''
/* L2 real Pending inbox: suggest an existing category, never auto-apply it. */
.vf-confidence.is-neutral{background:var(--ws-soft-2);color:var(--ws-muted)}
.vf-inbox-category-form{align-items:center;min-width:250px}
.vf-inbox-category-select{height:30px;max-width:220px;min-width:150px;padding:0 7px;border:1px solid var(--ws-line);border-radius:6px;background:var(--ws-panel);color:var(--ws-text);font-size:11.5px}
.vf-inbox-category-form button{white-space:nowrap}
@media(max-width:760px){.vf-inbox-category-form{width:100%;min-width:0}.vf-inbox-category-select{min-width:0;max-width:none;flex:1}}
'''
if '/* L2 real Pending inbox:' not in t: t=t.rstrip()+"\n"+addition
write(p,t)

print('P01 PENDING CATEGORY SUGGESTIONS PATCH APPLIED')
