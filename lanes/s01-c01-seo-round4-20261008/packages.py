import pathlib,zipfile,hashlib,json,os,stat
rows=[]
for component,prefix,root in [('theme','THEME','vf-tools-theme'),('provider','PROVIDER','vf-tool-m3u8')]:
 version=os.environ['TARGET_VERSION' if component=='theme' else 'PROVIDER_VERSION']
 name=('vf-tools-theme' if component=='theme' else 'vf-tools-m3u8')+'_V'+version+'.zip'
 p=pathlib.Path('provider')/name;data=p.read_bytes();sha=hashlib.sha256(data).hexdigest()
 assert len(data)==int(os.environ[prefix+'_BYTES']) and sha==os.environ[prefix+'_SHA256']
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
  matched=0
  for i in z.infolist():
   path=pathlib.PurePosixPath(i.filename)
   assert not path.is_absolute() and '..' not in path.parts and '\\' not in i.filename and path.parts[0]==root
   assert not stat.S_ISLNK(i.external_attr>>16)
   if component=='theme' and not i.is_dir():
    source=pathlib.Path('target/src').joinpath(*path.parts[1:])
    assert source.is_file(),str(path)
    assert source.read_bytes()==z.read(i),str(path)
    matched+=1
 rows.append({'component':component,'version':version,'asset':name,'bytes':len(data),'sha256':sha,'crc':'PASS','safe_paths':'PASS','theme_exact_source_file_bytes':matched if component=='theme' else 'FORMAL_ASSET_IDENTITY'})
pathlib.Path('proof/package-identity.json').write_text(json.dumps({'status':'PASS','source_sha':os.environ['TARGET_SHA'],'source_tree':os.environ['TARGET_TREE'],'assets':rows},indent=2))
