from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'p')

p = root / 'src/index.php'
s = p.read_text(encoding='utf-8')
assert s.count('assets/reference-ui.js?v=22120') == 1
assert s.count('id="managementButton" class="sidebar-tool admin-only hidden" href="manage.php"') == 1
s = s.replace('assets/reference-ui.js?v=22120', 'assets/reference-ui.js?v=22121', 1)
s = s.replace(
    'id="managementButton" class="sidebar-tool admin-only hidden" href="manage.php"',
    'id="managementButton" class="sidebar-tool admin-only hidden" href="links-admin.php"',
    1,
)
p.write_text(s, encoding='utf-8')

p = root / 'src/links-admin.php'
s = p.read_text(encoding='utf-8')
marker = '?>\n<div class="vf-links-summary" id="linksSummary"></div>'
assert s.count(marker) == 1
notice = '''?>
<?php
$notice=(string)($_GET['notice']??'');
$noticeMap=[
  'tags-retired'=>'标签功能已退役。分类 + Public / Private + 待整理是当前网址整理方式。',
  'affiliate-retired'=>'推广链接独立管理已退役。已有网址仍保留原始 URL 与参数，不会因此删除数据。',
  'governance-retired'=>'历史治理已经封板退出日常产品。当前维护请使用网址、分类与待整理。',
];
if(isset($noticeMap[$notice])): ?>
<div class="notice" role="status"><?=htmlspecialchars($noticeMap[$notice],ENT_QUOTES,'UTF-8')?></div>
<?php endif; ?>
<div class="vf-links-summary" id="linksSummary"></div>'''
p.write_text(s.replace(marker, notice, 1), encoding='utf-8')

p = root / 'src/assets/links-admin.js'
s = p.read_text(encoding='utf-8')
s2, n = re.subn(
    r'<div class="vf-field full"><label>标签</label><input name="tags"[^>]*></div>',
    '',
    s,
    count=1,
)
assert n == 1, n
old = "description:f.get('description'),tags:f.get('tags')"
assert s2.count(old) == 1
p.write_text(s2.replace(old, "description:f.get('description')", 1), encoding='utf-8')

print('P01_22121_EXACT_PATCH_PASS')
