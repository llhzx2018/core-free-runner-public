from pathlib import Path


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise SystemExit(f'missing test-contract anchor: {label}')
    return source.replace(old, new, 1)


# V0.1.13 Book/AdminShell capability stays gated. Only its historical claim that
# Operations itself must use AdminShell is superseded by the later CURRENT
# professional BackofficeShell authority.
p = Path('bin/admin-shell-book-overview-self-test.php')
s = p.read_text()
s = replace_once(
    s,
    "$operations = (string) file_get_contents($basePath . '/src/Http/Studio/OperationsController.php');\n",
    "$backoffice = (string) file_get_contents($basePath . '/src/Http/Studio/BackofficeShell.php');\n",
    'book-overview operations source',
)
s = replace_once(
    s,
    """    [$operations, \"private readonly AdminShell \\$shell\", 'Operations shared shell dependency'],
    [$operations, \"'/studio/books#import-markdown'\", 'Home Markdown route'],
    [$operations, \"'/studio/books/' . rawurlencode\", 'Home search Book Overview route'],
""",
    """    [$front, 'BackofficeShell::wrap', 'Operations canonical BackofficeShell wrapper'],
    [$front, \"\\$runStudioModule(\\$c,'operations')\", 'Operations canonical wrapped route'],
    [$backoffice, \"'operations' => ['运维总览'\", 'Professional operations shell identity'],
""",
    'book-overview superseded AdminShell claims',
)
p.write_text(s)


# The old AdminShell-unification test also treated Operations/System and the
# cross-book quality queue as one AdminShell site. Current authority splits the
# professional global BackofficeShell/SystemBaseline surfaces from focused
# AdminShell book workflows. Preserve every business/data assertion, but bind
# each shell assertion to its current canonical owner.
p = Path('bin/admin-shell-unification-self-test.php')
s = p.read_text()
s = replace_once(
    s,
    "$quality = (string)file_get_contents($basePath . '/src/Http/Studio/QualityController.php');\n",
    "$quality = (string)file_get_contents($basePath . '/src/Http/Studio/QualityQueueController.php');\n"
    "$system = (string)file_get_contents($basePath . '/src/Http/Studio/SystemBaselineController.php');\n"
    "$backoffice = (string)file_get_contents($basePath . '/src/Http/Studio/BackofficeShell.php');\n",
    'unification current sources',
)
s = replace_once(
    s,
    "    [$quality, 'final class QualityController', 'Quality center controller'],\n",
    "    [$quality, 'final class QualityQueueController', 'Quality queue controller'],\n",
    'quality controller class',
)
s = replace_once(
    s,
    """    [$operations, \"if (\\$path === '/studio/system' && \\$method === 'GET')\", 'System canonical route'],
    [$operations, \"'settings',\", 'Settings active destination'],
    [$operations, \"\\$this->shell->start(\", 'System shared shell start'],
    [$operations, \"\\$this->shell->end();\", 'System shared shell end'],
""",
    """    [$system, \"if (\\$path === '/studio/system')\", 'System canonical route'],
    [$system, \"if (\\$path === '/studio/system/baseline')\", 'System baseline route'],
    [$system, \"if (\\$path === '/studio/system/health')\", 'System health route'],
    [$backoffice, \"'system' => ['系统信息'\", 'System BackofficeShell identity'],
""",
    'system superseded AdminShell claims',
)
s = replace_once(
    s,
    "    [$front, \"str_starts_with(\\$path,'/studio/system')\", 'System front route family'],\n",
    "    [$front, \"\\$systemActive = match (\\$path)\", 'Explicit System V2 route map'],\n",
    'system front route family',
)
s = replace_once(
    s,
    "if (str_contains($operations, '<!doctype html>')) {\n    throw new RuntimeException('System center still duplicates the full HTML shell.');\n}\n",
    "if (str_contains($operations, 'class=\"ops-sidebar\"')) {\n    throw new RuntimeException('Operations controller duplicates canonical Backoffice chrome.');\n}\n",
    'legacy full-html assertion',
)
p.write_text(s)


# V0.1.11's Whole-Site Refoundation introduced Library/Book continuity. The
# later CURRENT backoffice authority supersedes only the global login-home shape:
# Operations is now a professional operational overview, not a Library Continue
# hero. Keep Book Workspace, Reader continuity, publishing demotion, and the
# cross-book quality queue capability under their current owners.
p = Path('bin/whole-site-refoundation-self-test.php')
s = p.read_text()
s = replace_once(
    s,
    "$home = (string)file_get_contents($basePath . '/src/Http/Studio/OperationsController.php');\n",
    "$home = (string)file_get_contents($basePath . '/src/Http/Studio/OperationsController.php');\n"
    "$backoffice = (string)file_get_contents($basePath . '/src/Http/Studio/BackofficeShell.php');\n",
    'whole-site backoffice source',
)
s = replace_once(
    s,
    "$quality = (string)file_get_contents($basePath . '/src/Http/Studio/QualityController.php');\n",
    "$quality = (string)file_get_contents($basePath . '/src/Http/Studio/QualityQueueController.php');\n",
    'whole-site quality queue source',
)
s = replace_once(
    s,
    "    [$home, 'class=\"library-continue\"', 'Continue latest book surface'],\n",
    "    [$backoffice, \"'operations' => ['运维总览'\", 'Professional Operations default surface'],\n"
    "    [$home, '今日待处理', 'Operations action-first overview'],\n",
    'whole-site superseded Continue hero',
)
p.write_text(s)
