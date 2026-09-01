from pathlib import Path
import re

page = Path('src/transfer.php')
js_path = Path('src/assets/transfer.js')
css_path = Path('src/assets/admin-pages.css')

php = page.read_text(encoding='utf-8')
php = php.replace("'description'=>'浏览器书签 HTML 和 CSV 都先只读预览；正式写入前自动创建 SQLite 恢复点。',", "'description'=>'第一次使用先把浏览器书签带进来；系统先预览，确认后才写入，并在导入前自动创建恢复点。',", 1)
start = php.find('<div class="grid">')
end_marker = "<?php vf_admin_shell_end(['assets/transfer.js?v=2182']); ?>"
end = php.find(end_marker)
if start < 0 or end < 0 or end <= start:
    raise SystemExit('transfer body anchors missing')
body = r'''<div class="grid vf-transfer-grid">
<section class="panel vf-transfer-import-primary">
  <div class="vf-transfer-kicker">第一次使用 · 从这里开始</div>
  <h2>导入浏览器书签</h2>
  <p>Chrome、Edge、Firefox 都可以从书签管理器导出 HTML。把那个 <strong>.html</strong> 文件选进来即可；预览阶段不会修改任何数据。</p>
  <div class="vf-transfer-steps" aria-label="导入步骤">
    <span><b>1</b><strong>浏览器导出</strong><small>在书签管理器里导出书签 HTML</small></span>
    <span><b>2</b><strong>VF Start 预览</strong><small>先看分类、网址、重复和无效项</small></span>
    <span><b>3</b><strong>确认导入</strong><small>写入前自动创建 SQLite 恢复点</small></span>
  </div>
  <label class="field"><span>导入来源</span><select id="format"><option value="bookmarks">浏览器书签 HTML（推荐）</option><option value="csv">VF Start 维护 CSV</option></select></label>
  <label class="field"><span>选择文件</span><input id="file" type="file" accept=".html,.htm,.csv,text/html,text/csv"></label>
  <label class="switch"><input id="private" type="checkbox" checked><span><strong>默认按私人导入</strong><small>浏览器书签建议保持开启；CSV 有明确可见性字段时以 CSV 为准。</small></span></label>
  <details class="vf-transfer-advanced">
    <summary>高级设置</summary>
    <label class="field"><span>重复网址处理</span><select id="policy"><option value="skip">跳过已有网址（推荐）</option><option value="update">用导入字段更新已有网址</option><option value="create">仍然创建新记录</option></select></label>
  </details>
  <div class="row"><button class="btn primary" id="preview" disabled>预览这份书签</button></div>
  <div class="preview" id="result">先选择浏览器导出的书签 HTML。</div>
</section>

<section class="panel vf-transfer-export-secondary">
  <div class="vf-transfer-kicker">以后迁移或留档时再用</div>
  <h2>导出 / 迁移</h2>
  <p>书签 HTML 适合回到浏览器；维护 CSV 用于完整保留 VF Start 的分类、可见性和原始网址字段。</p>
  <div class="export-grid">
    <a class="export" href="api.php?action=transfer_export&format=bookmarks&scope=all"><strong>全部书签 HTML</strong><span>当前正常使用的全部网址。</span></a>
    <a class="export" href="api.php?action=transfer_export&format=bookmarks&scope=public"><strong>公开书签 HTML</strong><span>仅公开网址。</span></a>
    <a class="export" href="api.php?action=transfer_export&format=bookmarks&scope=private"><strong>私人书签 HTML</strong><span>仅管理员会话可下载。</span></a>
    <a class="export" href="api.php?action=transfer_export&format=csv&scope=all"><strong>完整维护 CSV</strong><span>保留分类、可见性、原始 URL 与历史兼容字段。</span></a>
    <a class="export" href="api.php?action=transfer_export&format=csv&scope=public"><strong>公开 CSV</strong><span>只含公开分类与公开网址。</span></a>
    <a class="export" href="api.php?action=transfer_export&format=csv&scope=private"><strong>私人 CSV</strong><span>私人网址只在管理员会话下载。</span></a>
  </div>
  <div class="notice">书签 HTML 没有“私密”字段；重新导入 VF Start 时可以统一选择默认可见性。维护 CSV 会保留 VF Start 自己的可见性和兼容字段。</div>
  <div class="field"><span>按指定分类导出</span><select id="exportCategory"><option value="">选择分类</option></select></div>
  <div class="row"><a class="btn" id="exportCategoryBookmarks" aria-disabled="true">导出该分类书签 HTML</a><a class="btn" id="exportCategoryCsv" aria-disabled="true">导出该分类 CSV</a></div>
</section>
</div>
'''
php = php[:start] + body + php[end:]
page.write_text(php, encoding='utf-8')

js = js_path.read_text(encoding='utf-8')
old = """$('#result').innerHTML='<strong>导入完成</strong><div class=\"metrics\"><div class=\"metric\"><strong>'+Number(r.createdCategories||0)+'</strong><span>新增分类</span></div><div class=\"metric\"><strong>'+Number(r.createdLinks||0)+'</strong><span>新增网址</span></div><div class=\"metric\"><strong>'+Number(r.updatedLinks||0)+'</strong><span>更新网址</span></div><div class=\"metric\"><strong>'+Number(r.skippedLinks||0)+'</strong><span>跳过</span></div></div><div class=\"notice\">恢复点：'+esc(r.backup||'已创建')+'</div>';"""
new = """$('#result').innerHTML='<strong>导入完成</strong><div class=\"metrics\"><div class=\"metric\"><strong>'+Number(r.createdCategories||0)+'</strong><span>新增分类</span></div><div class=\"metric\"><strong>'+Number(r.createdLinks||0)+'</strong><span>新增网址</span></div><div class=\"metric\"><strong>'+Number(r.updatedLinks||0)+'</strong><span>更新网址</span></div><div class=\"metric\"><strong>'+Number(r.skippedLinks||0)+'</strong><span>跳过</span></div></div><div class=\"notice\">恢复点：'+esc(r.backup||'已创建')+'</div><div class=\"row vf-transfer-complete-actions\"><a class=\"btn primary\" href=\"start.php\">打开我的导航</a><a class=\"btn\" href=\"links-admin.php\">继续整理网址</a></div>';$('#result').scrollIntoView({behavior:'smooth',block:'nearest'});"""
if old not in js:
    raise SystemExit('transfer completion anchor missing')
js = js.replace(old, new, 1)
js_path.write_text(js.rstrip() + '\n', encoding='utf-8')

styles = css_path.read_text(encoding='utf-8').rstrip() + r'''

/* transfer.php — onboarding-first import flow; export remains available as the secondary task. */
body[data-vf-page="transfer"] .vf-transfer-grid{grid-template-columns:1fr;gap:12px}
body[data-vf-page="transfer"] .vf-transfer-import-primary{border-color:color-mix(in srgb,var(--vf-admin-primary) 30%,var(--vf-admin-border))}
body[data-vf-page="transfer"] .vf-transfer-kicker{margin-bottom:4px;color:var(--vf-admin-primary);font-size:10.5px;font-weight:780;letter-spacing:.02em}
body[data-vf-page="transfer"] .vf-transfer-steps{margin:13px 0 14px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
body[data-vf-page="transfer"] .vf-transfer-steps>span{min-width:0;padding:10px;display:grid;grid-template-columns:24px minmax(0,1fr);column-gap:8px;row-gap:2px;border:1px solid var(--vf-admin-border);border-radius:9px;background:var(--vf-admin-surface-soft)}
body[data-vf-page="transfer"] .vf-transfer-steps b{grid-row:1/3;width:24px;height:24px;display:grid;place-items:center;border-radius:999px;background:var(--vf-admin-primary);color:#fff;font-size:10px}
body[data-vf-page="transfer"] .vf-transfer-steps strong{font-size:11.5px;color:var(--vf-admin-strong)}
body[data-vf-page="transfer"] .vf-transfer-steps small{color:var(--vf-admin-muted);font-size:10.5px;line-height:1.4}
body[data-vf-page="transfer"] .vf-transfer-advanced{margin:8px 0 10px;padding:0;border:1px solid var(--vf-admin-border);border-radius:9px;background:var(--vf-admin-surface-soft)}
body[data-vf-page="transfer"] .vf-transfer-advanced summary{padding:9px 11px;cursor:pointer;color:var(--vf-admin-muted);font-size:11px;font-weight:700}
body[data-vf-page="transfer"] .vf-transfer-advanced[open] summary{border-bottom:1px solid var(--vf-admin-border)}
body[data-vf-page="transfer"] .vf-transfer-advanced .field{margin:10px}
body[data-vf-page="transfer"] .vf-transfer-complete-actions{margin-top:12px}
body[data-vf-page="transfer"] .vf-transfer-export-secondary{margin-top:2px}
@media(max-width:760px){body[data-vf-page="transfer"] .vf-transfer-steps{grid-template-columns:1fr}body[data-vf-page="transfer"] .vf-transfer-complete-actions>*{flex:1 1 100%;text-align:center}}
'''
css_path.write_text(styles.rstrip() + '\n', encoding='utf-8')
