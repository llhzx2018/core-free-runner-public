import re
def split_selectors(s):
 depth=0;start=0
 for i,c in enumerate(s):
  if c in '([':depth+=1
  elif c in ')]':depth-=1
  elif c==',' and depth==0:yield s[start:i];start=i+1
 yield s[start:]
def search_selector(x):return re.search(r'\.vf-theme-search-|\.vf-directory-card--search\b|\.vf-search-type-badge\b',x) is not None
def strip_search(css):
 def edit(m):
  comments=''.join(re.findall(r'/\*.*?\*/',m[1],re.S));selectors=re.sub(r'/\*.*?\*/','',m[1],flags=re.S)
  parts=list(split_selectors(selectors));keep=[x for x in parts if not search_selector(x)]
  if len(parts)==len(keep):return m[0]
  return '\n'+comments+'\n'+(','.join(keep)+'{'+m[2]+'}' if keep else '')
 return re.sub(r'([^{}]+)\{([^{}]*)\}',edit,css)
