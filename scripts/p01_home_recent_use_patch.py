from pathlib import Path


def read(p): return Path(p).read_text(encoding='utf-8')
def write(p,t): Path(p).write_text(t.rstrip()+'\n',encoding='utf-8')
def replace_once(t,old,new,label):
    if old not in t: raise SystemExit(f'{label} anchor missing')
    return t.replace(old,new,1)

p='src/app/FunctionalHome.php'; t=read(p)
# Context + copy.
t=replace_once(t,"    $backupStatus = (array)($context['backup_status'] ?? []);","    $backupStatus = (array)($context['backup_status'] ?? []);\n    $recentAssets = (array)($context['recent_assets'] ?? []);",'home recent context')
t=t.replace('这里只放需要处理的事项和最近操作。资源浏览、收藏与最近使用继续由现有导航承担。','这里只放需要处理的事项、最近使用和最近操作。完整资源浏览继续由现有导航承担。',1)
# Insert recent use between focus and activity.
anchor='''    <section class="vf-home-activity-section" aria-labelledby="vfHomeActivityTitle">'''
recent=r'''    <?php if($recentAssets): ?>
    <section class="vf-home-recent-section" aria-labelledby="vfHomeRecentTitle">
      <header class="vf-home-block-head">
        <div><span>最近</span><h2 id="vfHomeRecentTitle">最近使用</h2></div>
        <a class="vf-home-block-link" href="surfaces.php?view=recent">查看全部 →</a>
      </header>
      <div class="vf-home-recent-grid">
        <?php foreach($recentAssets as $asset):
          $recentId=(int)($asset['id']??0);$recentTitle=trim((string)($asset['title']??''));
          $recentHost=(string)(parse_url((string)($asset['url']??''),PHP_URL_HOST)?:'');
          $recentMeta=trim((string)($asset['category_name']??''));if($recentMeta==='')$recentMeta=$recentHost;
          $recentAge=vf_home_relative_age((string)($asset['last_surface_opened_at']??''));
        ?>
          <a class="vf-home-recent-item" href="surface-open.php?id=<?=$recentId?>" target="_blank" rel="noopener noreferrer">
            <span class="vf-home-recent-icon"><?=vf_fw_icon($asset)?></span>
            <span class="vf-home-recent-copy"><b><?=vf_fw_h($recentTitle!==''?$recentTitle:'未命名资源')?></b><small><?=vf_fw_h($recentMeta)?></small></span>
            <i><?=vf_fw_h($recentAge)?></i>
          </a>
        <?php endforeach; ?>
      </div>
    </section>
    <?php endif; ?>

'''
t=replace_once(t,anchor,recent+anchor,'home activity anchor')
# Build recent list from existing last-opened authority.
old="""    $operations = [];\n    try { $operations = (new VfOperationHistory($db))->recent(8, 0); } catch (Throwable $ignored) {}"""
new="""    $recentAssets = array_values(array_filter($allAssets, static fn(array $asset): bool => trim((string)($asset['last_surface_opened_at'] ?? '')) !== ''));\n    usort($recentAssets, static fn(array $a,array $b): int => strcmp((string)($b['last_surface_opened_at'] ?? ''),(string)($a['last_surface_opened_at'] ?? '')));\n    $recentAssets = array_slice($recentAssets,0,6);\n    $operations = [];\n    try { $operations = (new VfOperationHistory($db))->recent(8, 0); } catch (Throwable $ignored) {}"""
t=replace_once(t,old,new,'home recent data')
old="""<?php vf_render_home_command_center(['pending'=>$pending,'operations'=>$operations,'operation_asset_titles'=>$operationAssetTitles,'operation_category_titles'=>$operationCategoryTitles,'health_status'=>$healthStatus,'backup_status'=>$backupStatus,'first_use'=>count($allAssets)===0]); ?>"""
new="""<?php vf_render_home_command_center(['pending'=>$pending,'operations'=>$operations,'operation_asset_titles'=>$operationAssetTitles,'operation_category_titles'=>$operationCategoryTitles,'health_status'=>$healthStatus,'backup_status'=>$backupStatus,'recent_assets'=>$recentAssets,'first_use'=>count($allAssets)===0]); ?>"""
t=replace_once(t,old,new,'home render call')
write(p,t)

p='src/assets/workspace-home.css'; t=read(p)
addition=r'''
/* L2 Home: a compact recent-use rail, not a second navigation wall. */
.vf-home-recent-section{padding:17px 18px;border-bottom:1px solid var(--ws-line)}
.vf-home-block-link{padding-top:3px;color:var(--ws-teal);font-size:10px;font-weight:750;text-decoration:none;white-space:nowrap}
.vf-home-recent-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
.vf-home-recent-item{min-width:0;min-height:52px;padding:8px;display:grid;grid-template-columns:30px minmax(0,1fr) auto;align-items:center;gap:8px;border:1px solid var(--ws-line);border-radius:8px;background:var(--ws-panel);color:inherit;text-decoration:none}
.vf-home-recent-item:hover{border-color:color-mix(in srgb,var(--ws-teal) 32%,var(--ws-line));background:var(--ws-soft)}
.vf-home-recent-icon{width:30px;height:30px;display:grid;place-items:center;border:1px solid var(--ws-line);border-radius:7px;background:var(--ws-soft);overflow:hidden;color:var(--ws-teal);font-size:11px;font-weight:800}
.vf-home-recent-icon img{width:100%;height:100%;object-fit:cover}
.vf-home-recent-copy{min-width:0}.vf-home-recent-copy b,.vf-home-recent-copy small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.vf-home-recent-copy b{color:var(--ws-text);font-size:11px}.vf-home-recent-copy small{margin-top:2px;color:var(--ws-muted-2);font-size:9.5px}
.vf-home-recent-item>i{color:var(--ws-muted-2);font-style:normal;font-size:9px;white-space:nowrap}
@media(max-width:760px){.vf-home-recent-section{padding:14px 12px}.vf-home-recent-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.vf-home-block-link{font-size:9.5px}.vf-home-recent-item{grid-template-columns:28px minmax(0,1fr);min-height:50px}.vf-home-recent-icon{width:28px;height:28px}.vf-home-recent-item>i{grid-column:2}}
@media(max-width:430px){.vf-home-recent-grid{grid-template-columns:1fr}.vf-home-recent-item>i{grid-column:auto}}
'''
if '/* L2 Home: a compact recent-use rail' not in t: t=t.rstrip()+"\n"+addition
write(p,t)
print('P01 HOME RECENT USE PATCH APPLIED')
