import pathlib,json,os,hashlib,zipfile,stat,base64,io
from PIL import Image
meta=json.loads(pathlib.Path('/tmp/meta.json').read_text());data=pathlib.Path('/tmp/archive.zip').read_bytes();job=json.loads(pathlib.Path('/tmp/job.json').read_text())
assert meta['id']==int(os.environ['ARTIFACT_ID']) and meta['size_in_bytes']==len(data)==int(os.environ['ARTIFACT_BYTES'])
assert meta['digest']=='sha256:'+hashlib.sha256(data).hexdigest()==os.environ['ARTIFACT_DIGEST']
assert not meta['expired'] and meta['workflow_run']['id']==int(os.environ['ORIGINAL_RUN']) and meta['workflow_run']['head_sha']==os.environ['ORIGINAL_HEAD']
assert job['id']==int(os.environ['ORIGINAL_JOB']) and job['run_id']==int(os.environ['ORIGINAL_RUN']) and job['conclusion']=='failure'
required=['Single spec preflight','Exact identity and existing SEO contracts','Exact delivered formal ZIPs','Browser dependencies','Real WordPress current formal controls Head XML language pairing','Public-safe proof']
assert all(next(s for s in job['steps'] if s['name']==name)['conclusion']=='success' for name in required)
assert [s['name'] for s in job['steps'] if s['conclusion']=='failure']==['Read back actual uploaded evidence ZIP']
with zipfile.ZipFile('/tmp/archive.zip') as z:
 assert z.testzip() is None
 names=z.namelist();assert len(names)==len(set(names))==52
 for i in z.infolist():
  p=pathlib.PurePosixPath(i.filename)
  assert not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename and not stat.S_ISLNK(i.external_attr>>16)
  assert p.suffix in ['.json','.png']
  if p.suffix=='.json':json.loads(z.read(i))
 assert 'FINAL_EVIDENCE.json' in names and 'proof/FINAL_EVIDENCE.json' not in names
 final=json.loads(z.read('FINAL_EVIDENCE.json'))
 assert final['status']=='PASS' and final['source_sha']==os.environ['TARGET_SHA'] and final['source_tree']==os.environ['TARGET_TREE']
 assert final['control_cases']==60 and final['public_cases']==13 and final['paired_cases']==6 and final['provider_version']==os.environ['PROVIDER_VERSION']
 assert final['widths']==[1920,1440,1319,1024,768,390]
 control=json.loads(z.read('live-browser.json'));assert len(control['tests'])==60 and len(control['checks'])==6 and not control['errors']
 records=[]
 for name in ['FINAL_EVIDENCE','package-identity','live-browser','public-output','paired-output','installed-versions','performance']:
  raw=z.read(name+'.json');json.loads(raw)
  records.append({'path':name+'.json','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
  print('VF_ARCHIVE_RECORD_BEGIN '+name);print(raw.decode());print('VF_ARCHIVE_RECORD_END '+name)
 images=[]
 for name in ['seo-clean-1440.png','seo-clean-390.png','seo-add-dialog-390.png']:
  raw=z.read(name);im=Image.open(io.BytesIO(raw)).convert('RGB');output=io.BytesIO();im.save(output,format='JPEG',quality=82,optimize=True);jpeg=output.getvalue()
  images.append({'path':name,'original_bytes':len(raw),'original_sha256':hashlib.sha256(raw).hexdigest(),'dimensions':im.size,'jpeg_bytes':len(jpeg),'jpeg_sha256':hashlib.sha256(jpeg).hexdigest()})
  print('VF_IMAGE_BEGIN '+name);print(base64.b64encode(jpeg).decode());print('VF_IMAGE_END '+name)
receipt={'status':'PASS_ACTUAL_ARCHIVE_REVERSE','artifact_id':meta['id'],'bytes':len(data),'digest':meta['digest'],'original_run':int(os.environ['ORIGINAL_RUN']),'original_job':job['id'],'original_head':os.environ['ORIGINAL_HEAD'],'original_run_conclusion':'failure','failure_classification':'EVIDENCE_READER_ARCHIVE_ROOT_PATH','product_step':'success','file_count':len(names),'crc':'PASS','safe_paths':'PASS','all_json':'PASS','source_sha':final['source_sha'],'source_tree':final['source_tree'],'records':records,'images':images,'reader_run':os.environ['GITHUB_RUN_ID'],'reader_head':os.environ['GITHUB_SHA'],'production':'NOT_EXECUTED'}
print('VF_READER_RECEIPT_BEGIN');print(json.dumps(receipt));print('VF_READER_RECEIPT_END')
