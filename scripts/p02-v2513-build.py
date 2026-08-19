#!/usr/bin/env python3
from pathlib import Path
import re, sys

root=Path(sys.argv[1] if len(sys.argv)>1 else 'product')

def read(path): return (root/path).read_text(encoding='utf-8')
def write(path,text): (root/path).write_text(text,encoding='utf-8')
def replace(path,old,new,count=1):
    text=read(path)
    actual=text.count(old)
    if actual < count: raise SystemExit(f'{path}: missing anchor; need {count}, have {actual}: {old[:100]!r}')
    write(path,text.replace(old,new,count))
def regex_replace(path,pattern,new,count=1):
    text=read(path); out,n=re.subn(pattern,new,text,count=count,flags=re.S)
    if n!=count: raise SystemExit(f'{path}: regex expected {count}, got {n}: {pattern[:100]}')
    write(path,out)

write('VERSION','2.5.13\n')

# Notebook: explicit category/scope navigation starts the title list from the top.
app='public/assets/app.js'
replace(app,
"function saveNotebookScroll(value){const map=notebookScrollMap();map[state.notebookScope]=Math.max(0,Math.round(Number(value)||0));const keys=Object.keys(map);while(keys.length>20){delete map[keys.shift()];}storage.set('vftb-notebook-scroll-map',JSON.stringify(map));}\n",
"function saveNotebookScroll(value){const map=notebookScrollMap();map[state.notebookScope]=Math.max(0,Math.round(Number(value)||0));const keys=Object.keys(map);while(keys.length>20){delete map[keys.shift()];}storage.set('vftb-notebook-scroll-map',JSON.stringify(map));}\nfunction resetNotebookListPosition(view){const key=notebookScopeKey(view||state),map=notebookScrollMap();if(Object.prototype.hasOwnProperty.call(map,key)){delete map[key];storage.set('vftb-notebook-scroll-map',JSON.stringify(map));}state.notebookListScroll=0;}\n")
replace(app,
"async function switchNotebookView(mode,status,categoryId){if(!await editorLeaveAllowed())return true;state.editorItem=null;state.editorDirty=false;state.mode=mode;state.status=status||'active';state.categoryId=Number(categoryId||0);state.query='';state.sort='auto';state.page=1;$('#globalSearch').value='';state.contentView='notebook';storage.set('vftb-content-view','notebook');persistView();closeSidebar();await loadList({render:false,scrollTop:0});return true;}",
"async function switchNotebookView(mode,status,categoryId){if(!await editorLeaveAllowed())return true;state.editorItem=null;state.editorDirty=false;state.mode=mode;state.status=status||'active';state.categoryId=Number(categoryId||0);state.query='';state.sort='auto';state.page=1;$('#globalSearch').value='';state.contentView='notebook';storage.set('vftb-content-view','notebook');resetNotebookListPosition(viewSnapshot());persistView();closeSidebar();await loadList({render:false,scrollTop:0});return true;}")
replace(app,
"async function setMode(mode,status){if(!await editorLeaveAllowed())return;state.selectionMode=false;state.selectedIds.clear();clearEditorState();state.readerItem=null;state.readerReturn=null;state.mode=mode;state.status=status||'active';state.categoryId=0;state.query='';state.sort='auto';state.page=1;$('#globalSearch').value='';if(!contentViewAllowed())state.contentView='list';persistView();closeSidebar();if(mode==='settings')renderSettings();else loadList({scrollTop:0});renderSidebar();}",
"async function setMode(mode,status){if(!await editorLeaveAllowed())return;state.selectionMode=false;state.selectedIds.clear();clearEditorState();state.readerItem=null;state.readerReturn=null;state.mode=mode;state.status=status||'active';state.categoryId=0;state.query='';state.sort='auto';state.page=1;$('#globalSearch').value='';if(!contentViewAllowed())state.contentView='list';if(state.contentView==='notebook')resetNotebookListPosition(viewSnapshot());persistView();closeSidebar();if(mode==='settings')renderSettings();else loadList({scrollTop:0});renderSidebar();}")
replace(app,
"async function selectCategory(id){if(!await editorLeaveAllowed())return;state.selectionMode=false;state.selectedIds.clear();const categoryId=Number(id);const rootId=categoryRootId(categoryId);state.expanded={};if(rootId)state.expanded[rootId]=true;persistCategoryExpansion();clearEditorState();state.readerItem=null;state.readerReturn=null;state.mode='category';state.status='active';state.categoryId=categoryId;state.query='';state.sort='auto';state.page=1;$('#globalSearch').value='';persistView();closeSidebar();loadList({scrollTop:0});renderSidebar();}",
"async function selectCategory(id){if(!await editorLeaveAllowed())return;state.selectionMode=false;state.selectedIds.clear();const categoryId=Number(id);const rootId=categoryRootId(categoryId);state.expanded={};if(rootId)state.expanded[rootId]=true;persistCategoryExpansion();clearEditorState();state.readerItem=null;state.readerReturn=null;state.mode='category';state.status='active';state.categoryId=categoryId;state.query='';state.sort='auto';state.page=1;$('#globalSearch').value='';if(state.contentView==='notebook')resetNotebookListPosition(viewSnapshot());persistView();closeSidebar();loadList({scrollTop:0});renderSidebar();}")

# Reader: keep open-at-top; remember progress only as an optional explicit resume action.
replace(app,
"function readerPreferenceSignature(){const p=readerPreferences();return [p.scale.toFixed(2),p.width,p.line].join('|');}\n",
"function readerPreferenceSignature(){const p=readerPreferences();return [p.scale.toFixed(2),p.width,p.line].join('|');}\nfunction readerPositionMap(){try{const value=JSON.parse(storage.get('vftb-reader-position-map','{}'));return value&&typeof value==='object'?value:{};}catch(error){return {};}}\nfunction savedReaderPosition(id){const row=readerPositionMap()[String(Number(id)||0)];if(!row||typeof row!=='object')return 0;const ratio=Number(row.ratio||0);return ratio>.04&&ratio<.985?Math.max(0,Math.min(1,ratio)):0;}\nfunction saveReaderPosition(id,ratio){id=Number(id)||0;if(!id)return;ratio=Math.max(0,Math.min(1,Number(ratio)||0));const map=readerPositionMap(),key=String(id);if(ratio<.035||ratio>.985)delete map[key];else map[key]={ratio:Math.round(ratio*10000)/10000,updated_at:Date.now()};const keys=Object.keys(map).sort((a,b)=>Number((map[a]||{}).updated_at||0)-Number((map[b]||{}).updated_at||0));while(keys.length>60){delete map[keys.shift()];}storage.set('vftb-reader-position-map',JSON.stringify(map));}\nfunction readerResumeMarkup(){return '<button type=\"button\" class=\"reader-resume-v2513 hidden\" data-reader-resume>继续上次阅读</button>';}\n")
old_wire="function wireMarkdown(root){$$('[data-copy-code]',root).forEach(button=>button.onclick=()=>{const code=$('code',button.closest('.code-block')).textContent;writeClipboard(code).then(()=>{const old=button.textContent;button.textContent='已复制';button.classList.add('copied');setTimeout(()=>{button.textContent=old;button.classList.remove('copied');},1400);});});$$('[data-copy-heading]',root).forEach(button=>button.onclick=()=>{const id=button.dataset.copyHeading;const url=currentOriginUrl(location.pathname)+'#'+id;writeClipboard(url).then(()=>toast('章节链接已复制'));});$$('[data-wiki]',root).forEach(button=>button.onclick=()=>{const target=button.dataset.wiki;closeTopModal();state.readerItem=null;state.readerReturn=null;state.mode='all';state.status='active';state.categoryId=0;state.query=target;state.page=1;$('#globalSearch').value=target;loadList({scrollTop:0});});}"
new_wire="""function wireReaderCollapsibles(root){if(!root||!root.closest('.notebook-article-reader,.reader-page'))return;
  Array.from(root.children).filter(node=>node.tagName==='H2'&&!node.dataset.readerFoldWired).forEach(heading=>{heading.dataset.readerFoldWired='1';heading.classList.add('reader-fold-heading-v2513');const body=document.createElement('div');body.className='reader-fold-body-v2513';let node=heading.nextSibling;while(node&&!(node.nodeType===1&&node.tagName==='H2')){const next=node.nextSibling;body.appendChild(node);node=next;}heading.after(body);const toggle=document.createElement('button');toggle.type='button';toggle.className='reader-fold-toggle-v2513';toggle.setAttribute('aria-label','折叠本节');toggle.setAttribute('aria-expanded','true');toggle.onclick=e=>{e.preventDefault();e.stopPropagation();const collapsed=!body.hidden;body.hidden=collapsed;heading.classList.toggle('is-collapsed',collapsed);toggle.setAttribute('aria-expanded',collapsed?'false':'true');toggle.setAttribute('aria-label',collapsed?'展开本节':'折叠本节');};heading.insertBefore(toggle,heading.firstChild);});
  $$('img',root).forEach(img=>{const parent=img.parentElement;if(!parent||parent.dataset.readerMediaWired==='1'||parent.tagName!=='P'||parent.children.length!==1||parent.textContent.trim()!=='')return;parent.dataset.readerMediaWired='1';parent.classList.add('reader-media-v2513');const toggle=document.createElement('button');toggle.type='button';toggle.className='reader-media-toggle-v2513';toggle.textContent='收起图片';toggle.setAttribute('aria-expanded','true');toggle.onclick=e=>{e.preventDefault();const collapsed=parent.classList.toggle('is-collapsed');toggle.textContent=collapsed?'展开图片':'收起图片';toggle.setAttribute('aria-expanded',collapsed?'false':'true');};parent.appendChild(toggle);});}
function wireMarkdown(root){$$('[data-copy-code]',root).forEach(button=>button.onclick=()=>{const code=$('code',button.closest('.code-block')).textContent;writeClipboard(code).then(()=>{const old=button.textContent;button.textContent='已复制';button.classList.add('copied');setTimeout(()=>{button.textContent=old;button.classList.remove('copied');},1400);});});$$('[data-copy-heading]',root).forEach(button=>button.onclick=()=>{const id=button.dataset.copyHeading;const url=currentOriginUrl(location.pathname)+'#'+id;writeClipboard(url).then(()=>toast('章节链接已复制'));});$$('[data-wiki]',root).forEach(button=>button.onclick=()=>{const target=button.dataset.wiki;closeTopModal();state.readerItem=null;state.readerReturn=null;state.mode='all';state.status='active';state.categoryId=0;state.query=target;state.page=1;$('#globalSearch').value=target;loadList({scrollTop:0});});wireReaderCollapsibles(root);}"""
replace(app,old_wire,new_wire)
replace(app,
"<div class=\"reader-meta\">'+metaMarkup(item,{hideCategory:true})+'<i>·</i><span>约 '+minutes+' 分钟</span></div><div class=\"markdown-body\" id=\"readerContent\">",
"<div class=\"reader-meta\">'+metaMarkup(item,{hideCategory:true})+'<i>·</i><span>约 '+minutes+' 分钟</span></div>'+readerResumeMarkup()+'<div class=\"markdown-body\" id=\"readerContent\">",
1)
regex_replace(app,r"function wireReadingState\(scrollRoot,content,tocLinks,progress\)\{.*?\}\nfunction sourceTypeLabel",
"""function wireReadingState(scrollRoot,content,tocLinks,progress,readerId){cleanupReaderScroll();const headings=$$('h2[data-reading-heading],h3[data-reading-heading]',content);const target=scrollRoot===window?window:scrollRoot;const topNow=()=>scrollRoot===window?window.scrollY:scrollRoot.scrollTop;const maxNow=()=>Math.max(0,scrollRoot===window?document.documentElement.scrollHeight-innerHeight:scrollRoot.scrollHeight-scrollRoot.clientHeight);const setTop=value=>{if(scrollRoot===window)window.scrollTo({top:value,behavior:'auto'});else scrollRoot.scrollTop=value;};let persistTimer=null,armed=false;setTimeout(()=>{armed=true;},600);const persist=()=>{if(!readerId||!armed)return;clearTimeout(persistTimer);persistTimer=setTimeout(()=>{const max=maxNow();saveReaderPosition(readerId,max>0?topNow()/max:0);},260);};const update=(shouldPersist=true)=>{const rootRect=scrollRoot===window?{top:0,height:innerHeight}:scrollRoot.getBoundingClientRect();const top=topNow(),max=maxNow();const ratio=max>0?Math.max(0,Math.min(1,top/max)):0;if(progress){progress.style.transform='scaleX('+ratio+')';progress.parentElement.setAttribute('aria-valuenow',String(Math.round(ratio*100)));}let current='';const threshold=rootRect.top+Math.min(150,rootRect.height*.22);headings.forEach(h=>{if(h.offsetParent!==null&&h.getBoundingClientRect().top<=threshold)current=h.id;});tocLinks.forEach(link=>link.classList.toggle('active',link.dataset.tocId===current));if(shouldPersist)persist();};target.addEventListener('scroll',update,{passive:true});const resume=content.closest('.notebook-article-reader,.reader-page')?.querySelector('[data-reader-resume]');const saved=readerId?savedReaderPosition(readerId):0;if(resume&&saved){resume.classList.remove('hidden');resume.textContent='继续上次阅读 · '+Math.round(saved*100)+'%';resume.onclick=()=>{armed=true;setTop(Math.round(maxNow()*saved));update(true);resume.classList.add('hidden');};}update(false);state.readerScrollCleanup=()=>{target.removeEventListener('scroll',update);clearTimeout(persistTimer);if(readerId&&armed){const max=maxNow();saveReaderPosition(readerId,max>0?topNow()/max:0);}};}
function sourceTypeLabel""")
replace(app,"wireReadingState(detail,content,tocLinks,$('#articleReadProgress',detail));","wireReadingState(detail,content,tocLinks,$('#articleReadProgress',detail),item.id);")

# Scratch: pin + reorder live in the existing JSON setting; no schema migration.
svc='src/app/ScratchTabsService.php'
replace(svc,"'is_open'=>!empty($tab['is_open']),\n                'sort_order'=>(int)($tab['sort_order']??0),","'is_open'=>!empty($tab['is_open']),\n                'is_pinned'=>!empty($tab['is_pinned']),\n                'sort_order'=>(int)($tab['sort_order']??0),")
replace(svc,"'id'=>(int)$tab['id'],'title'=>(string)$tab['title'],'is_open'=>(bool)$tab['is_open'],\n            'sort_order'=>(int)$tab['sort_order'],","'id'=>(int)$tab['id'],'title'=>(string)$tab['title'],'is_open'=>(bool)$tab['is_open'],'is_pinned'=>(bool)($tab['is_pinned']??false),\n            'sort_order'=>(int)$tab['sort_order'],")
replace(svc,"usort($open,fn($a,$b)=>($a['sort_order']<=>$b['sort_order'])?:($a['id']<=>$b['id']));","usort($open,fn($a,$b)=>(intval($b['is_pinned'])<=>intval($a['is_pinned']))?:($a['sort_order']<=>$b['sort_order'])?:($a['id']<=>$b['id']));")
replace(svc,"$tab=['id'=>$id,'title'=>'临时 '.$id,'content'=>'','is_open'=>true,'sort_order'=>$max+100,","$tab=['id'=>$id,'title'=>'临时 '.$id,'content'=>'','is_open'=>true,'is_pinned'=>false,'sort_order'=>$max+100,")
replace(svc,"    public function removeAfterOrganize(int $id): void{$this->discard($id,false);}\n}","""    public function pin(int $id,bool $pinned): array
    {
        $owned=$this->beginOwned();
        try{$state=$this->loadState();$i=$this->findIndex($state,$id);if(empty($state['tabs'][$i]['is_open']))throw new RuntimeException('已关闭页签不能固定。');$state['tabs'][$i]['is_pinned']=$pinned;$state['tabs'][$i]['updated_at']=gmdate('c');$this->writeState($state);$tab=$state['tabs'][$i];$this->commitOwned($owned);return $this->publicTab($tab,true);}catch(Throwable $e){$this->rollbackOwned($owned);throw $e;}
    }

    public function reorder(array $ids): void
    {
        $ids=array_values(array_map('intval',$ids));if(!$ids||count($ids)!==count(array_unique($ids)))throw new InvalidArgumentException('页签顺序参数无效。');
        $owned=$this->beginOwned();
        try{$state=$this->loadState();$open=[];foreach($state['tabs'] as $tab)if(!empty($tab['is_open']))$open[]=(int)$tab['id'];$expected=$open;$actual=$ids;sort($expected,SORT_NUMERIC);sort($actual,SORT_NUMERIC);if($expected!==$actual)throw new InvalidArgumentException('页签顺序必须包含全部已打开页签。');$order=100;foreach($ids as $id){$i=$this->findIndex($state,$id);$state['tabs'][$i]['sort_order']=$order;$order+=100;}$this->writeState($state);$this->commitOwned($owned);}catch(Throwable $e){$this->rollbackOwned($owned);throw $e;}
    }

    public function removeAfterOrganize(int $id): void{$this->discard($id,false);}
}
""")

action='public/scratch-action.php'
replace(action,"        case 'discard':\n            if($method!=='POST')vftb_json(['ok'=>false,'error'=>'Method Not Allowed'],405);\n            $body=vftb_request_json(16384);$id=(int)($body['id']??0);if($id<=0)throw new InvalidArgumentException('临时页签参数无效。');\n            $service->discard($id,true);vftb_json(['ok'=>true]);\n        case 'organize':","""        case 'discard':
            if($method!=='POST')vftb_json(['ok'=>false,'error'=>'Method Not Allowed'],405);
            $body=vftb_request_json(16384);$id=(int)($body['id']??0);if($id<=0)throw new InvalidArgumentException('临时页签参数无效。');
            $service->discard($id,true);vftb_json(['ok'=>true]);
        case 'pin':
            if($method!=='POST')vftb_json(['ok'=>false,'error'=>'Method Not Allowed'],405);
            $body=vftb_request_json(16384);$id=(int)($body['id']??0);if($id<=0)throw new InvalidArgumentException('临时页签参数无效。');
            vftb_json(['ok'=>true,'tab'=>$service->pin($id,!empty($body['pinned']))]);
        case 'reorder':
            if($method!=='POST')vftb_json(['ok'=>false,'error'=>'Method Not Allowed'],405);
            $body=vftb_request_json(32768);$ids=$body['ids']??null;if(!is_array($ids))throw new InvalidArgumentException('页签顺序参数无效。');
            $service->reorder($ids);vftb_json(['ok'=>true]);
        case 'organize':""")

scratch='public/assets/scratch-tabs.js'
replace(scratch,"  const LAST_OPEN_KEY='vftb-scratch-workspace-open-v1';\n","  const LAST_OPEN_KEY='vftb-scratch-workspace-open-v1';\n  const QUICK_OPEN=(new URLSearchParams(location.search)).get('scratch')==='1'||location.hash==='#scratch';\n")
old_tabs="""  function renderTabs(){
    if(!workspace)return;const root=workspace.querySelector('[data-scratch-tabs]');if(!root)return;
    root.innerHTML=snapshot.open.map(tab=>'<button type=\"button\" class=\"scratch-tab-v259 '+(Number(tab.id)===Number(activeId)?'active':'')+'\" data-scratch-tab=\"'+Number(tab.id)+'\" title=\"'+esc(tab.title)+'\"><span class=\"scratch-tab-title-v259\">'+esc(tab.title)+'</span><span class=\"scratch-tab-close-v259\" role=\"button\" aria-label=\"关闭临时页签\" title=\"关闭但不删除\" data-scratch-close=\"'+Number(tab.id)+'\">×</span></button>').join('');
    root.querySelectorAll('[data-scratch-tab]').forEach(btn=>btn.addEventListener('click',event=>{
      if(event.target.closest('[data-scratch-close]'))return;switchTab(Number(btn.dataset.scratchTab));
    }));
    root.querySelectorAll('[data-scratch-close]').forEach(btn=>btn.addEventListener('click',event=>{event.stopPropagation();closeTab(Number(btn.dataset.scratchClose));}));
    const active=root.querySelector('.scratch-tab-v259.active');if(active)requestAnimationFrame(()=>active.scrollIntoView({block:'nearest',inline:'nearest'}));
  }
"""
new_tabs="""  let draggedTabId=0;
  function sortSnapshotTabs(){snapshot.open.sort((a,b)=>(Number(!!b.is_pinned)-Number(!!a.is_pinned))||(Number(a.sort_order||0)-Number(b.sort_order||0))||(Number(a.id)-Number(b.id)));}
  async function persistTabOrder(){try{await request('reorder',{method:'POST',body:{ids:snapshot.open.map(tab=>Number(tab.id))}});}catch(error){showNotice(error.message||'页签顺序保存失败');await loadSnapshot();sortSnapshotTabs();renderTabs();}}
  async function moveTab(sourceId,targetId){const from=snapshot.open.findIndex(t=>Number(t.id)===Number(sourceId)),to=snapshot.open.findIndex(t=>Number(t.id)===Number(targetId));if(from<0||to<0||from===to)return;const source=snapshot.open[from],target=snapshot.open[to];if(!!source.is_pinned!==!!target.is_pinned){showNotice('固定页签会保持在最前面');return;}snapshot.open.splice(to,0,snapshot.open.splice(from,1)[0]);snapshot.open.forEach((tab,index)=>tab.sort_order=(index+1)*100);renderTabs();await persistTabOrder();}
  function closeTabMenu(){workspace?.querySelector('.scratch-tab-menu-v2513')?.remove();}
  async function togglePin(id){const tab=snapshot.open.find(t=>Number(t.id)===Number(id));if(!tab)return;try{const data=await request('pin',{method:'POST',body:{id,pinned:!tab.is_pinned}});Object.assign(tab,data.tab||{is_pinned:!tab.is_pinned});sortSnapshotTabs();closeTabMenu();renderTabs();showNotice(tab.is_pinned?'页签已固定':'已取消固定');}catch(error){showNotice(error.message||'固定页签失败');}}
  function openTabMenu(id,x,y){closeTabMenu();const tab=snapshot.open.find(t=>Number(t.id)===Number(id));if(!tab||!workspace)return;const menu=document.createElement('div');menu.className='scratch-tab-menu-v2513';menu.innerHTML='<button type=\"button\" data-tab-menu-pin>'+(tab.is_pinned?'取消固定':'固定页签')+'</button><button type=\"button\" data-tab-menu-close>关闭页签</button>';workspace.appendChild(menu);menu.style.left=Math.min(Math.max(8,x),innerWidth-150)+'px';menu.style.top=Math.min(Math.max(8,y),innerHeight-92)+'px';menu.querySelector('[data-tab-menu-pin]').onclick=()=>togglePin(id);menu.querySelector('[data-tab-menu-close]').onclick=()=>{closeTabMenu();closeTab(id);};}
  function renderTabs(){
    if(!workspace)return;sortSnapshotTabs();const root=workspace.querySelector('[data-scratch-tabs]');if(!root)return;
    root.innerHTML=snapshot.open.map(tab=>'<button type=\"button\" draggable=\"true\" class=\"scratch-tab-v259 '+(tab.is_pinned?'is-pinned ':'')+(Number(tab.id)===Number(activeId)?'active':'')+'\" data-scratch-tab=\"'+Number(tab.id)+'\" title=\"'+esc(tab.title)+(tab.is_pinned?' · 已固定':'')+'\"><span class=\"scratch-tab-title-v259\">'+esc(tab.title)+'</span><span class=\"scratch-tab-close-v259\" role=\"button\" aria-label=\"关闭临时页签\" title=\"关闭但不删除\" data-scratch-close=\"'+Number(tab.id)+'\">×</span></button>').join('');
    root.querySelectorAll('[data-scratch-tab]').forEach(btn=>{btn.addEventListener('click',event=>{if(event.target.closest('[data-scratch-close]'))return;switchTab(Number(btn.dataset.scratchTab));});btn.addEventListener('contextmenu',event=>{event.preventDefault();openTabMenu(Number(btn.dataset.scratchTab),event.clientX,event.clientY);});btn.addEventListener('dragstart',event=>{draggedTabId=Number(btn.dataset.scratchTab);btn.classList.add('is-dragging');if(event.dataTransfer){event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',String(draggedTabId));}});btn.addEventListener('dragend',()=>{draggedTabId=0;btn.classList.remove('is-dragging');});btn.addEventListener('dragover',event=>{if(!draggedTabId)return;event.preventDefault();if(event.dataTransfer)event.dataTransfer.dropEffect='move';});btn.addEventListener('drop',event=>{event.preventDefault();const source=draggedTabId||Number(event.dataTransfer?.getData('text/plain')||0);draggedTabId=0;moveTab(source,Number(btn.dataset.scratchTab));});});
    root.querySelectorAll('[data-scratch-close]').forEach(btn=>btn.addEventListener('click',event=>{event.stopPropagation();closeTab(Number(btn.dataset.scratchClose));}));
    const active=root.querySelector('.scratch-tab-v259.active');if(active)requestAnimationFrame(()=>active.scrollIntoView({block:'nearest',inline:'nearest'}));
  }
"""
replace(scratch,old_tabs,new_tabs)
replace(scratch,"    if(!autoOpened&&storage.get(LAST_OPEN_KEY)==='1'){\n","    if(!autoOpened&&(QUICK_OPEN||storage.get(LAST_OPEN_KEY)==='1')){\n")
replace(scratch,"data-scratch-add title=\"新建临时页签\" aria-label=\"新建临时页签\"","data-scratch-add title=\"新建临时页签 · Alt+N\" aria-label=\"新建临时页签\"")
replace(scratch,"data-scratch-recent title=\"最近关闭的临时页签\">最近关闭</button>","data-scratch-recent title=\"最近关闭 · Alt+R\">最近关闭</button>")
replace(scratch,"  async function reopenTab(id){try{","  async function reopenLatest(){const tab=(snapshot.closed||[])[0];if(tab)await reopenTab(Number(tab.id));else showNotice('最近没有关闭的页签');}\n\n  async function reopenTab(id){try{")
regex_replace(scratch,r"  document\.addEventListener\('keydown',event=>\{\n    if\(!workspace\)return;\n    if\(event\.altKey.*?\n  \}\);","""  document.addEventListener('keydown',event=>{
    const key=event.key.toLowerCase();
    if(!workspace){if(event.altKey&&!event.ctrlKey&&!event.metaKey&&key==='n'){event.preventDefault();openWorkspace(false);}return;}
    if(event.altKey&&!event.ctrlKey&&!event.metaKey&&key==='n'){event.preventDefault();createTab();return;}
    if(event.altKey&&!event.ctrlKey&&!event.metaKey&&key==='w'){event.preventDefault();if(activeId)closeTab(activeId);return;}
    if(event.altKey&&!event.ctrlKey&&!event.metaKey&&(key==='j'||key==='k')){event.preventDefault();if(snapshot.open.length<2)return;sortSnapshotTabs();const index=Math.max(0,snapshot.open.findIndex(t=>Number(t.id)===Number(activeId))),delta=key==='j'?1:-1,next=(index+delta+snapshot.open.length)%snapshot.open.length;switchTab(Number(snapshot.open[next].id));return;}
    if(event.altKey&&!event.ctrlKey&&!event.metaKey&&key==='r'){event.preventDefault();reopenLatest();return;}
    if(event.key==='Escape')closeTabMenu();
  });""")

# Visual details: no extra permanent toolbar noise.
css='public/assets/scratch-tabs.css'
write(css,read(css)+"""

/* V2.5.13 · personal scratch workflow */
.scratch-tab-v259.is-pinned{position:relative;padding-left:18px}
.scratch-tab-v259.is-pinned::before{content:"";position:absolute;left:8px;top:50%;width:5px;height:5px;border-radius:50%;transform:translateY(-50%);background:var(--primary,#0f766e)}
.scratch-tab-v259.is-dragging{opacity:.46}
.scratch-tab-menu-v2513{position:fixed;z-index:2147483200;width:138px;padding:5px;border:1px solid var(--border,#d9e1e1);border-radius:9px;background:var(--surface,#fff);box-shadow:0 16px 40px rgba(15,23,42,.16);display:grid;gap:2px}
.scratch-tab-menu-v2513 button{height:34px;padding:0 10px;border:0;border-radius:6px;background:transparent;color:var(--text,#243333);text-align:left;font:inherit;cursor:pointer}
.scratch-tab-menu-v2513 button:hover{background:var(--surface-soft,#f4f7f7)}
""")

appcss='public/assets/app.css'
write(appcss,read(appcss)+"""

/* V2.5.13 · personal reading workflow */
.reader-resume-v2513{display:inline-flex;align-items:center;min-height:30px;margin:0 0 22px;padding:0 10px;border:1px solid color-mix(in srgb,var(--primary) 24%,var(--border));border-radius:999px;background:color-mix(in srgb,var(--primary) 5%,var(--surface));color:var(--primary);font-size:11px;font-weight:700;cursor:pointer}
.reader-resume-v2513:hover{background:color-mix(in srgb,var(--primary) 9%,var(--surface))}.reader-resume-v2513.hidden{display:none!important}
.reader-fold-heading-v2513{position:relative;padding-left:24px!important}.reader-fold-toggle-v2513{position:absolute;left:0;top:.12em;width:20px;height:24px;padding:0;border:0;background:transparent;color:var(--muted2);cursor:pointer}.reader-fold-toggle-v2513::before{content:"▾";font-size:12px}.reader-fold-heading-v2513.is-collapsed .reader-fold-toggle-v2513::before{content:"▸"}.reader-fold-toggle-v2513:hover,.reader-fold-toggle-v2513:focus-visible{color:var(--primary)}.reader-fold-body-v2513[hidden]{display:none!important}
.reader-media-v2513{position:relative;display:block;min-height:28px}.reader-media-v2513>.reader-media-toggle-v2513{position:absolute;right:8px;top:8px;z-index:2;min-height:28px;padding:0 9px;border:1px solid color-mix(in srgb,var(--border) 75%,transparent);border-radius:7px;background:color-mix(in srgb,var(--surface) 90%,transparent);color:var(--muted);font-size:10.5px;opacity:.32;backdrop-filter:blur(8px);cursor:pointer}.reader-media-v2513:hover>.reader-media-toggle-v2513,.reader-media-v2513.is-collapsed>.reader-media-toggle-v2513,.reader-media-toggle-v2513:focus-visible{opacity:1}.reader-media-v2513.is-collapsed{height:42px;margin:12px 0;border:1px dashed var(--border);border-radius:8px;background:var(--surface-soft)}.reader-media-v2513.is-collapsed>img{display:none!important}.reader-media-v2513.is-collapsed>.reader-media-toggle-v2513{position:static;margin:6px 8px}
@media(max-width:640px){.reader-fold-heading-v2513{padding-left:22px!important}.reader-media-v2513>.reader-media-toggle-v2513{opacity:.7}}
""")

# Bookmarkable quick Scratch entry.
(root/'public/scratch').mkdir(parents=True,exist_ok=True)
write('public/scratch/index.php',"""<?php
declare(strict_types=1);
if(function_exists('header_remove'))@header_remove('X-Powered-By');
header('Cache-Control: no-store');
header('Location: /?scratch=1',true,302);
exit;
""")

# Changelog, no schema change.
change=read('CHANGELOG.md')
entry="""## 2.5.13 - 2026-08-19

- 修复笔记模式切换分类后标题列表恢复到旧滚动位置的问题：显式切换分类/范围统一从标题列表顶部开始。
- 临时页签增加低噪音固定与拖动排序；右键页签即可固定/取消固定，固定页签保持在最前。
- 临时工作台补齐网页内安全快捷键：Alt+N 新建、Alt+W 关闭、Alt+J/K 切换、Alt+R 恢复最近关闭；不占用浏览器 Ctrl+T / Ctrl+W / Ctrl+Tab。
- 新增 /scratch/ 快速入口，适合保存成浏览器书签直接进入临时工作台。
- 长文阅读默认仍从顶部打开；若存在上次阅读进度，显示“继续上次阅读”入口；H2 章节和独立图片支持按需折叠。
- 保持 Schema 2401，无数据库迁移。

"""
if '## 2.5.13 - 2026-08-19' not in change:
    pos=change.find('\n\n')
    change=(change[:pos+2]+entry+change[pos+2:]) if pos>=0 else entry+change
    write('CHANGELOG.md',change)

print('P02_V2513_PATCH_APPLIED=PASS')
