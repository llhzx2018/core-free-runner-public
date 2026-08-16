from pathlib import Path

css = Path('public/assets/v254-ui.css')
s = css.read_text(encoding='utf-8')
old = '.main-content{padding:22px 30px 48px}.view{max-width:var(--vf-page-max)}.section-stack{gap:16px}.app-footer{color:var(--vf-text-tertiary);padding-top:26px}'
new = '.main-content{padding:22px 30px 48px}.view{max-width:var(--vf-page-max)}.section-stack{gap:16px}.app-footer{color:var(--vf-text-secondary);padding-top:26px}'
if s.count(old) != 1:
    raise SystemExit(f'footer contrast sentinel mismatch: {s.count(old)}')
css.write_text(s.replace(old, new, 1), encoding='utf-8')

app = Path('public/assets/app.js')
s = app.read_text(encoding='utf-8')
repls = {
    "not_checked: '尚未检查', up_to_date: '已是最新版本', remote_older: '当前版本更新',": "not_checked: '尚未检查', up_to_date: '已是最新版本', remote_older: '当前版本较新',",
    "(update.status === 'update_available' ? '可更新到' : (update.status === 'up_to_date' ? '最新稳定版' : (updateLatest === '—' ? '最新稳定版' : '发现版本')));": "(update.status === 'update_available' ? '可更新到' : '最新稳定版');",
}
for old, new in repls.items():
    if s.count(old) != 1:
        raise SystemExit(f'app copy sentinel mismatch: {old[:60]} -> {s.count(old)}')
    s = s.replace(old, new, 1)
app.write_text(s, encoding='utf-8')
print('V254_FINAL_COPY_CONTRAST_PATCH=PASS')
