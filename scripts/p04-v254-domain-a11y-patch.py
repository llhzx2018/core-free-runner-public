from pathlib import Path

css = Path('public/assets/v254-ui.css')
s = css.read_text(encoding='utf-8')
old = "--vf-success:#237a58;--vf-warning:#a96513;--vf-danger:#bb342d;--vf-info:#346b81;"
new = "--vf-success:#237a58;--vf-warning:#8a520c;--vf-danger:#bb342d;--vf-info:#346b81;"
if s.count(old) != 1:
    raise SystemExit(f'warning color sentinel mismatch: {s.count(old)}')
s = s.replace(old, new, 1)
marker = ".action-menu-panel{border-color:var(--vf-border);border-radius:11px;box-shadow:var(--vf-shadow-float)}.menu-action{font-size:12px}.menu-action:hover{background:#f5f8f7}\n"
addition = marker + ".tag-line span{font-size:10px!important;color:#53645d!important}.badge.warning{color:var(--vf-warning)}\n"
if s.count(marker) != 1:
    raise SystemExit(f'tag-line marker mismatch: {s.count(marker)}')
s = s.replace(marker, addition, 1)
css.write_text(s, encoding='utf-8')

js = Path('public/assets/v254-ui.js')
s = js.read_text(encoding='utf-8')
marker = """  function statusSemantics(root = document) {
    qsa('.badge', root).forEach((badge) => {
      const text = badge.textContent.trim();
      if (!text) return;
      const label = `状态：${text}`;
      if (badge.getAttribute('aria-label') !== label) badge.setAttribute('aria-label', label);
    });
  }

"""
addition = marker + """  function controlNames(root = document) {
    const fixedSelectNames = {
      'domain-status-filter': '域名状态筛选',
      'domain-renewal-filter': '域名续费方式筛选',
      'domain-sort': '域名排序方式',
      'domain-page-size': '域名每页显示数量',
    };
    Object.entries(fixedSelectNames).forEach(([id, label]) => {
      const control = document.getElementById(id);
      if (control && !control.getAttribute('aria-label') && !control.getAttribute('aria-labelledby')) {
        control.setAttribute('aria-label', label);
      }
    });

    const selectAll = document.getElementById('select-all-domains');
    if (selectAll && !selectAll.getAttribute('aria-label')) selectAll.setAttribute('aria-label', '选择全部当前页域名');

    qsa('.domain-select', root).forEach((checkbox) => {
      if (checkbox.getAttribute('aria-label') || checkbox.getAttribute('aria-labelledby')) return;
      const row = checkbox.closest('tr');
      const domain = row?.querySelector('.domain-name, .domain-link')?.textContent?.trim() || '';
      checkbox.setAttribute('aria-label', domain ? `选择域名 ${domain}` : '选择该域名');
    });
  }

"""
if s.count(marker) != 1:
    raise SystemExit(f'controlNames insertion marker mismatch: {s.count(marker)}')
s = s.replace(marker, addition, 1)
old_call = """      disabledReasons(root);
      statusSemantics(root);
      tableSemantics(root);"""
new_call = """      disabledReasons(root);
      statusSemantics(root);
      controlNames(root);
      tableSemantics(root);"""
if s.count(old_call) != 1:
    raise SystemExit(f'controlNames call marker mismatch: {s.count(old_call)}')
s = s.replace(old_call, new_call, 1)
js.write_text(s, encoding='utf-8')
print('P04_V254_DOMAIN_A11Y_PATCH=PASS')
