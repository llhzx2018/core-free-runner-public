from pathlib import Path

workspace = Path('src/app/FunctionalWorkspace.php')
bundle = Path('src/assets/workspace-create-bundle.js')
css = Path('src/assets/workspace-rebaseline.css')

php = workspace.read_text(encoding='utf-8')
old = """    $emptyCopy=$domainEmpty?($admin?'从添加入口开始建立这个资源域。':'这个资源域暂时还没有可显示的内容。'):($q!==''?'换一个关键词，或调整可见范围、分类和筛选条件后再试。':'调整可见范围、分类或筛选条件继续查找。');
    $branding=['logoUrl'=>''];"""
new = """    $emptyCopy=$domainEmpty?($admin?'从添加入口开始建立这个资源域。':'这个资源域暂时还没有可显示的内容。'):($q!==''?'换一个关键词，或调整可见范围、分类和筛选条件后再试。':'调整可见范围、分类或筛选条件继续查找。');
    $searchUrlCandidate='';
    if($admin&&$q!==''&&$mode==='all'&&$total===0){try{$searchUrlCandidate=vf_validate_url($q);}catch(Throwable $ignored){}}
    $branding=['logoUrl'=>''];"""
if old not in php:
    raise SystemExit('search candidate anchor missing')
php = php.replace(old, new, 1)
old = """<?php if($q!==''&&$mode==='all'&&$total===0): ?><div class=\"vf-search-fallback\"><span>个人资源里没有找到。</span><a href=\"https://www.google.com/search?q=<?=rawurlencode($q)?>\" target=\"_blank\" rel=\"noopener noreferrer\">在 Google 搜索“<?=vf_fw_h($q)?>” →</a></div><?php endif; ?>"""
new = """<?php if($q!==''&&$mode==='all'&&$total===0): ?><div class=\"vf-search-fallback<?= $searchUrlCandidate!==''?' is-url-candidate':'' ?>\"><span>个人资源里没有找到。</span><?php if($searchUrlCandidate!==''): ?><span class=\"vf-search-fallback-actions\"><button type=\"button\" data-open-add data-prefill-url=\"<?=vf_fw_h($searchUrlCandidate)?>\">保存这个网址 →</button><a href=\"<?=vf_fw_h($searchUrlCandidate)?>\" target=\"_blank\" rel=\"noopener noreferrer\">直接打开 ↗</a></span><?php else: ?><a href=\"https://www.google.com/search?q=<?=rawurlencode($q)?>\" target=\"_blank\" rel=\"noopener noreferrer\">在 Google 搜索“<?=vf_fw_h($q)?>” →</a><?php endif; ?></div><?php endif; ?>"""
if old not in php:
    raise SystemExit('search fallback render anchor missing')
php = php.replace(old, new, 1)
workspace.write_text(php, encoding='utf-8')

js = bundle.read_text(encoding='utf-8')
anchor = """  setupUrlFirstAdd();"""
snippet = r'''
  document.addEventListener('click',event=>{
    const trigger=event.target.closest?.('[data-prefill-url]');
    if(!trigger||!addForm)return;
    const value=String(trigger.dataset.prefillUrl||'').trim();
    if(!/^https?:\/\//i.test(value))return;
    setTimeout(()=>{
      const surface=addForm.elements.namedItem('surface');
      const url=addForm.elements.namedItem('url');
      const title=addForm.elements.namedItem('title');
      if(surface){surface.value='start';surface.dispatchEvent(new Event('change',{bubbles:true}))}
      if(title)title.value='';
      if(url){url.value=value;url.focus();url.select()}
    },0);
  });'''
if anchor not in js:
    raise SystemExit('URL-first setup anchor missing')
js = js.replace(anchor, anchor + snippet, 1)
bundle.write_text(js, encoding='utf-8')

styles = css.read_text(encoding='utf-8').rstrip() + r'''

/* Search-to-save bridge: a pasted URL with zero local matches becomes a save action, not a dead end. */
.vf-search-fallback-actions{display:flex;align-items:center;justify-content:flex-end;gap:10px}
.vf-search-fallback-actions button{padding:0;border:0;background:transparent;color:var(--ws-teal);font:inherit;font-weight:780;cursor:pointer}
.vf-search-fallback-actions button:hover{text-decoration:underline}
.vf-search-fallback-actions button:focus-visible{outline:2px solid var(--ws-teal);outline-offset:3px;border-radius:3px}
.vf-search-fallback.is-url-candidate>a,.vf-search-fallback-actions a{font-weight:650}
@media(max-width:600px){.vf-search-fallback-actions{width:100%;justify-content:space-between;gap:12px}}
'''
css.write_text(styles.rstrip() + '\n', encoding='utf-8')
