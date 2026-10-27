import re
pattern=re.compile(r'([^{}]+)\{([^{}]*)\}')
pagination=re.compile(r'\.(?:vf-theme-pagination|vf-data-pagination|page-numbers|pagination)\b')
def selectors(s):
 depth=0;start=0
 for i,c in enumerate(s):
  if c=='(':depth+=1
  elif c==')':depth-=1
  elif c==',' and depth==0:yield s[start:i];start=i+1
 yield s[start:]
def strip_pagination(s):
 def replace(m):
  selector=re.sub(r'/\*.*?\*/','',m[1],flags=re.S)
  if not pagination.search(selector):return m[0]
  # Keep comments/whitespace before a removed rule; all removed selectors
  # must exclusively target pagination, never an unrelated combined rule.
  assert all(pagination.search(x) for x in selectors(selector)),selector
  comments=''.join(re.findall(r'/\*.*?\*/',m[1],flags=re.S))
  return '\n'+comments+'\n'
 return pattern.sub(replace,s)

