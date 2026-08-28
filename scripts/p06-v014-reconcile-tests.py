from pathlib import Path

p = Path('bin/admin-shell-book-overview-self-test.php')
s = p.read_text()

old = "$operations = (string) file_get_contents($basePath . '/src/Http/Studio/OperationsController.php');\n"
new = "$backoffice = (string) file_get_contents($basePath . '/src/Http/Studio/BackofficeShell.php');\n"
if old not in s:
    raise SystemExit('missing historical operations source anchor')
s = s.replace(old, new, 1)

old_claims = """    [$operations, \"private readonly AdminShell \\$shell\", 'Operations shared shell dependency'],
    [$operations, \"'/studio/books#import-markdown'\", 'Home Markdown route'],
    [$operations, \"'/studio/books/' . rawurlencode\", 'Home search Book Overview route'],
"""
new_claims = """    [$front, 'BackofficeShell::wrap', 'Operations canonical BackofficeShell wrapper'],
    [$front, \"\\$runStudioModule(\\$c,'operations')\", 'Operations canonical wrapped route'],
    [$backoffice, \"'operations' => ['运维总览'\", 'Professional operations shell identity'],
"""
if old_claims not in s:
    raise SystemExit('missing superseded AdminShell claims')
s = s.replace(old_claims, new_claims, 1)

# The V0.1.13 Book/AdminShell capability remains fully gated below. Only the
# superseded assertion that the global Operations controller itself must depend
# on AdminShell is replaced by the later CURRENT BackofficeShell contract.
p.write_text(s)
