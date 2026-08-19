from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'p')

p = root / 'src/index.php'
s = p.read_text(encoding='utf-8')
old_js = 'assets/reference-ui.js?v=22120'
new_js = 'assets/reference-ui.js?v=22121'
old_manage = 'id="managementButton" class="sidebar-tool admin-only hidden" href="manage.php"'
new_manage = 'id="managementButton" class="sidebar-tool admin-only hidden" href="links-admin.php"'
if s.count(old_js) == 1:
    s = s.replace(old_js, new_js, 1)
else:
    assert s.count(old_js) == 0 and s.count(new_js) == 1
if s.count(old_manage) == 1:
    s = s.replace(old_manage, new_manage, 1)
else:
    assert s.count(old_manage) == 0 and s.count(new_manage) == 1
p.write_text(s, encoding='utf-8')

p = root / 'src/links-admin.php'
s = p.read_text(encoding='utf-8')
marker = '?>\n<div class="vf-links-summary" id="linksSummary"></div>'
notice_token = '标签功能已退役。分类 + Public / Private + 待整理是当前网址整理方式。'
if notice_token not in s:
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
    s = s.replace(marker, notice, 1)
else:
    assert s.count(notice_token) == 1
p.write_text(s, encoding='utf-8')

p = root / 'src/assets/links-admin.js'
s = p.read_text(encoding='utf-8')
pattern = r'<div class="vf-field full"><label>标签</label><input name="tags"[^>]*></div>'
s2, n = re.subn(pattern, '', s, count=1)
assert n in (0, 1)
old = "description:f.get('description'),tags:f.get('tags')"
if s2.count(old) == 1:
    s2 = s2.replace(old, "description:f.get('description')", 1)
else:
    assert s2.count(old) == 0 and "description:f.get('description')" in s2
p.write_text(s2, encoding='utf-8')

print('P01_22121_EXACT_PATCH_PASS')
