from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / 'src/assets/workspace-domain-nav.css'
s = p.read_text(encoding='utf-8')
marker = '/* P01 anonymous grid alignment: remove admin-only select column when logged out. */'
if marker in s:
    raise SystemExit('marker already present')
block = r'''

/* P01 anonymous grid alignment: remove admin-only select column when logged out. */
.vf-asset-row:not(:has(> .vf-asset-select)){grid-template-columns:36px minmax(0,1fr) auto}
.surface-start .vf-asset-row:not(:has(> .vf-asset-select)){grid-template-columns:32px minmax(0,1fr) auto}
.surface-channels .vf-asset-row:not(:has(> .vf-asset-select)){grid-template-columns:52px minmax(0,1fr) auto}
.vf-asset-card:not(:has(> .vf-asset-select)){grid-template-columns:38px minmax(0,1fr)}
.vf-asset-card:not(:has(> .vf-asset-select)) .vf-asset-meta{grid-column:1/-1}
@media(max-width:760px){
  .surface-start .vf-asset-row:not(:has(> .vf-asset-select)){grid-template-columns:32px minmax(0,1fr) auto}
  .surface-channels .vf-asset-row:not(:has(> .vf-asset-select)){grid-template-columns:46px minmax(0,1fr) auto}
}
'''
p.write_text(s.rstrip() + block + '\n', encoding='utf-8')
print('P01_ANONYMOUS_GRID_PREP=PASS')
