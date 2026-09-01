from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    p.write_text(s.replace(old, new, 1))

# One product-facing health entry in the admin rail.
replace_once(
    'src/app/AdminShell.php',
    "            ['href'=>'health.php','label'=>'网址健康'],\n            ['href'=>'duplicates.php','label'=>'重复网址'],\n",
    "            ['href'=>'health.php','label'=>'网址健康'],\n",
    'admin health submenu',
)

# Shared center tabs: health status and duplicate cleanup remain separate technical pages.
p = Path('src/health.php')
s = p.read_text()
s = s.replace("'description'=>'检测 DNS、HTTPS/HTTP、SSL、状态码、跳转、最终地址和响应时间。访问受限常见于登录墙、防爬或限流，不直接等于失效；一次失败不会自动删除或改写网址。',", "'description'=>'集中处理网址是否还能访问、是否发生跳转，以及重复收藏。检测不会因为一次失败自动删除或改写网址。',", 1)
anchor = "?>\n<div class=\"summary\" id=\"summary\"></div>"
insert = '''?>
<nav class="vf-health-center-tabs" aria-label="网址健康中心">
  <a class="active" href="health.php" aria-current="page"><strong>连接与失效</strong><span>DNS、HTTPS、状态码、跳转与响应</span></a>
  <a href="duplicates.php"><strong>重复清理</strong><span>识别重复网址，人工确认后处理</span></a>
</nav>
<div class="summary" id="summary"></div>'''
if s.count(anchor) != 1:
    raise SystemExit('health tab anchor drift')
p.write_text(s.replace(anchor, insert, 1))

p = Path('src/duplicates.php')
s = p.read_text()
s = s.replace("'title'=>'重复网址',", "'title'=>'网址健康',", 1)
s = s.replace("'description'=>'只识别和提示，不自动合并。推广、签名和受保护网址保持原始 URL，普通网址规范化必须先预览。',", "'description'=>'集中处理网址是否还能访问、是否发生跳转，以及重复收藏。重复项只识别和提示，不自动合并。',", 1)
anchor = "?><div class=\"summary\" id=\"summary\">正在扫描…</div>"
insert = '''?><nav class="vf-health-center-tabs" aria-label="网址健康中心"><a href="health.php"><strong>连接与失效</strong><span>DNS、HTTPS、状态码、跳转与响应</span></a><a class="active" href="duplicates.php" aria-current="page"><strong>重复清理</strong><span>识别重复网址，人工确认后处理</span></a></nav><section class="vf-health-center-note"><strong>重复网址</strong><span>系统只帮你找出来，不会自动合并、删除或改写原始网址。</span></section><div class="summary" id="summary">正在扫描…</div>'''
if s.count(anchor) != 1:
    raise SystemExit('duplicates tab anchor drift')
p.write_text(s.replace(anchor, insert, 1))

p = Path('src/assets/admin-pages.css')
css = p.read_text()
addition = '''
/* health.php + duplicates.php: one user-facing Link Health Center, two reused engines. */
.vf-health-center-tabs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:14px}
.vf-health-center-tabs>a{display:grid;gap:3px;padding:12px 14px;border:1px solid var(--vf-admin-border);border-radius:10px;background:var(--vf-admin-surface);color:var(--vf-admin-text);text-decoration:none;transition:border-color .15s ease,background .15s ease}
.vf-health-center-tabs>a:hover{border-color:var(--vf-admin-line-strong)}
.vf-health-center-tabs>a.active{border-color:var(--vf-admin-primary);background:var(--vf-admin-primary-soft)}
.vf-health-center-tabs strong{font-size:12.5px;color:var(--vf-admin-strong)}
.vf-health-center-tabs span{font-size:10.5px;line-height:1.45;color:var(--vf-admin-muted)}
.vf-health-center-note{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;padding:9px 11px;border:1px solid var(--vf-admin-line);border-radius:8px;background:var(--vf-admin-surface-soft)}
.vf-health-center-note strong{font-size:11.5px;color:var(--vf-admin-strong)}
.vf-health-center-note span{font-size:10.5px;color:var(--vf-admin-muted);text-align:right}
@media(max-width:640px){.vf-health-center-tabs{grid-template-columns:1fr}.vf-health-center-note{align-items:flex-start;flex-direction:column}.vf-health-center-note span{text-align:left}}
'''
if 'one user-facing Link Health Center' in css:
    raise SystemExit('health center css duplicate')
p.write_text(css.rstrip() + addition.rstrip() + '\n')
