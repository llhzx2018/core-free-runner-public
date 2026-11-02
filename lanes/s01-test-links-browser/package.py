import pathlib, zipfile, hashlib, json
p=pathlib.Path
with zipfile.ZipFile('provider/vf-tools-m3u8_V1.25.98.zip') as old, zipfile.ZipFile('proof/vf-tools-m3u8_V1.25.99.zip','w') as out:
    changed=[]
    for info in old.infolist():
        assert info.filename.startswith('vf-tool-m3u8/')
        data=old.read(info.filename)
        rel=info.filename.removeprefix('vf-tool-m3u8/')
        src=p('plugin-source/src')/rel
        if not info.is_dir():
            assert src.is_file()
            new=src.read_bytes()
            if new!=data: changed.append(rel)
            data=new
        out.writestr(info,data)
    expected={'vf-tool-m3u8.php','plugin-manifest.json','includes/v510-copy.php','public/js/modules/test-links.js','public/dist/test-links.js','config/v6/runtime-bundle.json','config/performance-bundles.json','config/performance-bundles.php'}
    assert set(changed)==expected, changed
with zipfile.ZipFile('proof/vf-tools-theme_V1.35.224.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as out:
    files=sorted(x for x in p('target/src').rglob('*') if x.is_file())
    for f in files:
        info=zipfile.ZipInfo('vf-tools-theme/'+str(f.relative_to('target/src')),(2020,1,1,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o100644 << 16
        out.writestr(info,f.read_bytes())
report={}
for name in ['vf-tools-theme_V1.35.224.zip','vf-tools-m3u8_V1.25.99.zip']:
    data=(p('proof')/name).read_bytes()
    with zipfile.ZipFile(p('proof')/name) as z: 
        assert z.testzip() is None
        count=sum(not x.is_dir() for x in z.infolist())
    report[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'files':count}
assert report['vf-tools-theme_V1.35.224.zip']['files']==476
assert report['vf-tools-m3u8_V1.25.99.zip']['files']==570
p('proof/candidate-package-proof.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
