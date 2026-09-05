from pathlib import Path
for rel in [
    'includes/site-release/s01-static-zero-write-batch-retry-v121834.php',
    '.github/phase3/v121834-zero-write-batch-closure.php',
]:
    p = Path('ops') / rel
    s = p.read_text()
    if not s.startswith('\\\n<?php'):
        raise SystemExit(f'unexpected leading bytes: {rel}: {s[:12]!r}')
    p.write_text(s[2:])
