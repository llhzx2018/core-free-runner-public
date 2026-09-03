#!/usr/bin/env python3
import base64
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

REPO = os.environ['P05_REPO']
BRANCH = os.environ['P05_BRANCH']
BASE = os.environ['P05_BASE_SHA']
EXPECTED_HEAD = os.environ['P05_EXPECTED_HEAD']
TOKEN = os.environ['VF_RELEASE_WRITE_TOKEN']
HEADERS = {
    'Authorization': 'Bearer ' + TOKEN,
    'Accept': 'application/vnd.github+json',
    'Content-Type': 'application/json',
    'X-GitHub-Api-Version': '2022-11-28',
}
EXPECTED_BLOBS = {
    'src/server/product-optimization.ts': 'bff794c34f2bfacdd7e08506a8513cbd339bc73f',
    'php/src/ProductOptimizationService.php': 'dcfa1e2d687d238d2c31aadb74b1d39d2ab3e660',
    'tests/unit/product-opportunity-evidence-truth.test.ts': 'd098583930c55ce4c3c40155ef234c10722eafba',
}
EXPECTED_SCOPE = sorted([
    'src/server/product-optimization.ts',
    'php/src/ProductOptimizationService.php',
    'src/client/product-opportunity-evidence.ts',
    'tests/unit/product-opportunity-evidence-truth.test.ts',
])


def api(method, url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def get(url):
    return api('GET', url)


def once(text, old, new, label):
    count = text.count(old)
    assert count == 1, (label, count)
    return text.replace(old, new, 1)


def gate():
    main = get(f'https://api.github.com/repos/{REPO}/branches/main')['commit']['sha']
    head = get(f'https://api.github.com/repos/{REPO}/branches/{urllib.parse.quote(BRANCH, safe="")}')['commit']['sha']
    assert main == BASE, (main, BASE)
    assert head == EXPECTED_HEAD, (head, EXPECTED_HEAD)
    q = urllib.parse.quote(BRANCH, safe='')
    version = get(f'https://api.github.com/repos/{REPO}/contents/VERSION?ref={q}')
    assert base64.b64decode(version['content']).decode().strip() == '1.2.4'
    for path, sha in EXPECTED_BLOBS.items():
        row = get(f'https://api.github.com/repos/{REPO}/contents/{path}?ref={q}')
        assert row['sha'] == sha, (path, row['sha'], sha)
    print('P05_OPPORTUNITY_EXPLAINABILITY_TRUTH_BOUNDARY_EXACT_STATE=PASS')


def transform_node(text):
    text = once(
        text,
        "  let trigger = scalarEvidence(evidence.trigger) ?? item.reason;",
        "  let trigger = scalarEvidence(evidence.trigger) ?? (item.kind === 'SEARCH' ? item.reason : '未声明（不推测）');",
        'node persisted trigger fallback',
    )
    text = once(
        text,
        "  const current = scalarEvidence(evidence.current) ?? item.reason;",
        "  const current = scalarEvidence(evidence.current) ?? (item.kind === 'SEARCH' ? item.reason : '未声明（不推测）');",
        'node persisted current fallback',
    )
    return text


def transform_php(text):
    text = once(
        text,
        "        $trigger = self::scalarEvidence($evidence['trigger'] ?? null) ?? (string) ($item['reason'] ?? '');",
        "        $trigger = self::scalarEvidence($evidence['trigger'] ?? null) ?? (($item['kind'] ?? '') === 'SEARCH' ? (string) ($item['reason'] ?? '') : '未声明（不推测）');",
        'php persisted trigger fallback',
    )
    text = once(
        text,
        "        $current = self::scalarEvidence($evidence['current'] ?? null) ?? (string) ($item['reason'] ?? '');",
        "        $current = self::scalarEvidence($evidence['current'] ?? null) ?? (($item['kind'] ?? '') === 'SEARCH' ? (string) ($item['reason'] ?? '') : '未声明（不推测）');",
        'php persisted current fallback',
    )
    return text


def transform_test(text):
    marker = "  assert.equal(phpExplain.includes(\"$freshness = ($item['kind'] ?? '') === 'SEARCH' ? ($searchSource['freshness'] ?? null) : ($item['lastSeenAt'] ?? null);\"), false);\n"
    addition = """  assert.ok(nodeExplain.includes("let trigger = scalarEvidence(evidence.trigger) ?? (item.kind === 'SEARCH' ? item.reason : '未声明（不推测）');"));
  assert.ok(nodeExplain.includes("const current = scalarEvidence(evidence.current) ?? (item.kind === 'SEARCH' ? item.reason : '未声明（不推测）');"));
  assert.ok(phpExplain.includes("$trigger = self::scalarEvidence($evidence['trigger'] ?? null) ?? (($item['kind'] ?? '') === 'SEARCH' ? (string) ($item['reason'] ?? '') : '未声明（不推测）');"));
  assert.ok(phpExplain.includes("$current = self::scalarEvidence($evidence['current'] ?? null) ?? (($item['kind'] ?? '') === 'SEARCH' ? (string) ($item['reason'] ?? '') : '未声明（不推测）');"));
"""
    assert marker in text
    return text.replace(marker, marker + addition, 1)


def write():
    transforms = {
        'src/server/product-optimization.ts': transform_node,
        'php/src/ProductOptimizationService.php': transform_php,
        'tests/unit/product-opportunity-evidence-truth.test.ts': transform_test,
    }
    changed = {path: fn(Path(path).read_text()) for path, fn in transforms.items()}
    print('P05_OPPORTUNITY_EXPLAINABILITY_TRUTH_BOUNDARY_CONSTRUCT=PASS')
    q = urllib.parse.quote(BRANCH, safe='')
    for path in transforms:
        current = get(f'https://api.github.com/repos/{REPO}/contents/{path}?ref={q}')
        assert current['sha'] == EXPECTED_BLOBS[path]
        result = api('PUT', f'https://api.github.com/repos/{REPO}/contents/{path}', {
            'message': 'fix(product): keep persisted Opportunity explainability truthful' if not path.startswith('tests/') else 'test(product): lock persisted Opportunity truth boundary',
            'content': base64.b64encode(changed[path].encode()).decode(),
            'sha': current['sha'],
            'branch': BRANCH,
        })
        print('WRITE', path, result['commit']['sha'])


def readback():
    main = get(f'https://api.github.com/repos/{REPO}/branches/main')['commit']['sha']
    head = get(f'https://api.github.com/repos/{REPO}/branches/{urllib.parse.quote(BRANCH, safe="")}')['commit']['sha']
    assert main == BASE
    compare = get(f'https://api.github.com/repos/{REPO}/compare/{BASE}...{head}')
    assert compare['behind_by'] == 0
    files = sorted(row['filename'] for row in compare['files'])
    assert files == EXPECTED_SCOPE, files
    q = urllib.parse.quote(BRANCH, safe='')
    version = get(f'https://api.github.com/repos/{REPO}/contents/VERSION?ref={q}')
    assert base64.b64decode(version['content']).decode().strip() == '1.2.4'
    tree = get(f'https://api.github.com/repos/{REPO}/git/commits/{head}')['tree']['sha']
    print('P05_OPPORTUNITY_EXPLAINABILITY_TRUTH_BOUNDARY_REMOTE_SCOPE=PASS')
    print('P05_OPPORTUNITY_EXPLAINABILITY_HEAD=' + head)
    print('P05_OPPORTUNITY_EXPLAINABILITY_TREE=' + tree)


if __name__ == '__main__':
    gate()
    write()
    readback()
