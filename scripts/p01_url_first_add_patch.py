from pathlib import Path

create = Path('src/workspace-create.php')
bundle = Path('src/assets/workspace-create-bundle.js')
css = Path('src/assets/resource-actions.css')

php = create.read_text(encoding='utf-8')
anchor = """if (!vf_is_installed()) { http_response_code(503); exit; }"""
helper = r'''function vf_workspace_create_title(string $surface, string $title, string $url): string
{
    $title = trim($title);
    if ($title !== '' || $surface !== 'start') return $title;
    $validated = vf_validate_url($url);
    $host = strtolower(trim((string)(parse_url($validated, PHP_URL_HOST) ?: '')));
    $host = (string)preg_replace('/^www\./i', '', $host);
    return $host !== '' ? $host : $validated;
}

'''
if anchor not in php:
    raise SystemExit('workspace-create install anchor missing')
php = php.replace(anchor, helper + anchor, 1)
old = """    $categoryId = max(1, (int)($_POST['category_id'] ?? 0));
    $title = trim((string)($_POST['title'] ?? ''));
    $url = trim((string)($_POST['url'] ?? ''));"""
new = """    $categoryId = max(1, (int)($_POST['category_id'] ?? 0));
    $url = trim((string)($_POST['url'] ?? ''));
    $title = vf_workspace_create_title($surface, (string)($_POST['title'] ?? ''), $url);"""
if old not in php:
    raise SystemExit('workspace-create title/url anchor missing')
php = php.replace(old, new, 1)
create.write_text(php, encoding='utf-8')

js = bundle.read_text(encoding='utf-8')
anchor = """  applyContextualAddCopy();"""
snippet = r'''
  const setupUrlFirstAdd=()=>{
    if(!addForm)return;
    const title=addForm.elements.namedItem('title');
    const surface=addForm.elements.namedItem('surface');
    const footer=$('footer',addForm);
    if(!title||!surface||!footer)return;
    const advanced=[
      title.closest('.vf-field'),
      addForm.elements.namedItem('tags')?.closest('.vf-field'),
      addForm.elements.namedItem('description')?.closest('.vf-field'),
      addForm.elements.namedItem('is_private')?.closest('.vf-check'),
      addForm.elements.namedItem('is_favorite')?.closest('.vf-check')
    ].filter(Boolean);
    advanced.forEach(node=>node.dataset.urlFirstAdvanced='1');
    const bar=document.createElement('div');bar.className='vf-add-quickbar';bar.hidden=true;
    const copy=document.createElement('span');copy.textContent='导航网址可只填网址；标题留空时先用域名。';
    const toggle=document.createElement('button');toggle.type='button';toggle.className='vf-add-more-toggle';toggle.textContent='更多设置';toggle.setAttribute('aria-expanded','false');
    bar.append(copy,toggle);footer.before(bar);
    let expanded=false;
    const sync=()=>{
      const start=surface.value==='start';
      title.required=!start;
      title.placeholder=start?'可不填，系统先用域名作为标题':'资源标题';
      addForm.classList.toggle('is-url-first',start);
      bar.hidden=!start;
      if(start)advanced.forEach(node=>{node.hidden=!expanded});
      else advanced.forEach(node=>{node.hidden=false});
      toggle.textContent=expanded?'收起更多':'更多设置';
      toggle.setAttribute('aria-expanded',expanded?'true':'false');
    };
    toggle.addEventListener('click',()=>{expanded=!expanded;sync()});
    surface.addEventListener('change',()=>{if(surface.value!=='start')expanded=true;sync()});
    document.addEventListener('click',event=>{
      if(!event.target.closest?.('[data-open-add]'))return;
      setTimeout(()=>{if(surface.value==='start')expanded=false;sync()},0);
    });
    sync();
  };
  setupUrlFirstAdd();'''
if anchor not in js:
    raise SystemExit('bundle contextual add anchor missing')
js = js.replace(anchor, anchor + snippet, 1)
bundle.write_text(js, encoding='utf-8')

styles = css.read_text(encoding='utf-8').rstrip() + r'''

/* URL-first navigation add: progressive enhancement only; full form remains the no-JS fallback. */
.vf-functional-workspace .vf-add-quickbar{
  grid-column:1/-1;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  min-height:38px;
  padding:8px 10px;
  border:1px solid color-mix(in srgb,var(--ws-teal) 18%,var(--ws-line));
  border-radius:8px;
  background:color-mix(in srgb,var(--ws-teal-soft) 18%,var(--ws-panel));
}
.vf-functional-workspace .vf-add-quickbar[hidden]{display:none}
.vf-functional-workspace .vf-add-quickbar>span{color:var(--ws-muted-2);font-size:11px;line-height:1.45}
.vf-functional-workspace .vf-add-more-toggle{
  flex:0 0 auto;
  min-height:30px;
  padding:0 9px;
  border:1px solid var(--ws-line);
  border-radius:7px;
  background:var(--ws-panel);
  color:var(--ws-teal);
  font:inherit;
  font-size:11px;
  font-weight:750;
  cursor:pointer;
}
.vf-functional-workspace .vf-add-more-toggle:hover{border-color:var(--ws-line-strong);background:var(--ws-soft)}
.vf-functional-workspace .vf-add-more-toggle:focus-visible{outline:2px solid var(--ws-teal);outline-offset:2px}
@media(max-width:520px){
  .vf-functional-workspace .vf-add-quickbar{align-items:flex-start;flex-direction:column;gap:7px}
}
'''
css.write_text(styles.rstrip() + '\n', encoding='utf-8')
