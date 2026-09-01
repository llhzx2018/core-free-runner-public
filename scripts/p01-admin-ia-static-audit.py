#!/usr/bin/env python3
from pathlib import Path
import json,re,sys

root=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
out.parent.mkdir(parents=True,exist_ok=True)
canonical=[
 'links-admin.php','health.php','duplicates.php','transfer.php','browser-helper.php',
 'data-safety.php','settings.php','workbench.php','system.php','update.php'
]
low=[
 'affiliate.php','tags.php','plugins.php','governance.php','jobs.php','icons.php',
 'security.php','diagnose.php','system-info.php','system-baseline.php','surface-manager.php','manage.php'
]
scan_roots=[root,root/'app',root/'assets',root/'plugins']
files=[]
for base in scan_roots:
    if not base.exists(): continue
    for p in base.rglob('*'):
        if p.is_file() and p.suffix.lower() in {'.php','.js','.css','.json'}:
            files.append(p)
files=sorted(set(files))

shell_pages=[]
for p in sorted(root.glob('*.php')):
    txt=p.read_text(encoding='utf-8',errors='ignore')
    if 'vf_admin_shell_begin' in txt:
        shell_pages.append(p.name)

refs={}
for target in low:
    rows=[]
    pat=re.compile(re.escape(target))
    for p in files:
        if p.resolve()==(root/target).resolve():
            continue
        txt=p.read_text(encoding='utf-8',errors='ignore')
        n=len(pat.findall(txt))
        if n:
            rows.append({'file':str(p.relative_to(root)),'count':n})
    refs[target]={'total':sum(x['count'] for x in rows),'files':rows}

admin=(root/'app/AdminShell.php').read_text(encoding='utf-8',errors='ignore')
admin_hrefs=re.findall(r"'href'=>'([^']+)'",admin)
admin_labels=re.findall(r"'label'=>'([^']+)'",admin)
modules=[]
for m in re.finditer(r"\['key'=>'([^']+)','label'=>'([^']+)','href'=>'([^']+)'",admin):
    modules.append({'key':m.group(1),'label':m.group(2),'href':m.group(3)})

root_pages=[]
for p in sorted(root.glob('*.php')):
    txt=p.read_text(encoding='utf-8',errors='ignore')
    root_pages.append({
        'page':p.name,
        'bytes':p.stat().st_size,
        'admin_shell':p.name in shell_pages,
        'requires_admin':('vf_is_admin()' in txt or 'vf_require_admin' in txt),
        'redirects':re.findall(r"header\(['\"]Location:\s*([^'\"]+)",txt)[:8],
    })

result={
 'canonical':canonical,
 'low_frequency':low,
 'admin_modules':modules,
 'admin_literal_hrefs':admin_hrefs,
 'admin_literal_labels':admin_labels,
 'admin_shell_root_pages':shell_pages,
 'reference_graph':refs,
 'root_pages':root_pages,
}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('P01_ADMIN_IA_STATIC_AUDIT=PASS')
print('ADMIN_MODULES='+json.dumps(modules,ensure_ascii=False))
print('SHELL_PAGES='+','.join(shell_pages))
for k,v in refs.items(): print(f'REF {k} total={v["total"]}')
