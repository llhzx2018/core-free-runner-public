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
    'src/server/product-optimization.ts': 'a5fea829582282d14cf1ea4bc414f7e735c0fb3a',
    'php/src/ProductOptimizationService.php': '77b3d103236372d058a7d7f2383838b43bc446fb',
    'tests/unit/product-opportunity-evidence-truth.test.ts': '21c9d11851732a91a076f9d15ef6eb6e7adfa1c1',
}
EXPECTED_SCOPE = sorted([
    'src/server/product-optimization.ts',
    'php/src/ProductOptimizationService.php',
    'src/client/product-opportunity-evidence.ts',
    'tests/unit/product-opportunity-evidence-truth.test.ts',
])


def api(method: str, url: str, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def get(url: str):
    return api('GET', url)


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, (label, count)
    return text.replace(old, new, 1)


def exact_state_gate():
    main = get(f'https://api.github.com/repos/{REPO}/branches/main')['commit']['sha']
    candidate = get(f'https://api.github.com/repos/{REPO}/branches/{urllib.parse.quote(BRANCH, safe="")}')['commit']['sha']
    assert main == BASE, (main, BASE)
    assert candidate == EXPECTED_HEAD, (candidate, EXPECTED_HEAD)
    version = get(f'https://api.github.com/repos/{REPO}/contents/VERSION?ref={urllib.parse.quote(BRANCH, safe="")}')
    assert base64.b64decode(version['content']).decode().strip() == '1.2.4'
    for path, sha in EXPECTED_BLOBS.items():
        row = get(f'https://api.github.com/repos/{REPO}/contents/{path}?ref={urllib.parse.quote(BRANCH, safe="")}')
        assert row['sha'] == sha, (path, row['sha'], sha)
    print('P05_OPPORTUNITY_EXPLAINABILITY_SEMANTICS_EXACT_STATE=PASS')


def transform_node(text: str) -> str:
    # Preserve the actual Query identity in derived evidence. Landing page remains a separate target fact.
    old1 = "evidence: { impressions, ctr, position, previousPosition: row.previousPosition ?? null, landingPageId: row.landingPageId ?? null, landingPage: row.landingPage ?? null },"
    new1 = "evidence: { query: row.query, impressions, ctr, position, previousPosition: row.previousPosition ?? null, landingPageId: row.landingPageId ?? null, landingPage: row.landingPage ?? null },"
    assert text.count(old1) == 2, text.count(old1)
    text = text.replace(old1, new1, 2)
    text = once(
        text,
        "evidence: { impressions, ctr, position, previousPosition: row.previousPosition ?? null, movement, landingPageId: row.landingPageId ?? null, landingPage: row.landingPage ?? null },",
        "evidence: { query: row.query, impressions, ctr, position, previousPosition: row.previousPosition ?? null, movement, landingPageId: row.landingPageId ?? null, landingPage: row.landingPage ?? null },",
        'node recovery query evidence',
    )

    old = """  const subjectType = String(item.subjectType ?? '').toUpperCase();
  const target = typeof item.target === 'string' && item.target.trim() ? ` · ${item.target.trim()}` : '';
  const subject = subjectType === 'QUERY' ? `关键词${target}` : subjectType === 'PAGE' ? `页面${target}` : '网站';
  const provider = scalarEvidence(evidence.provider) ?? scalarEvidence(evidence.source);
  const source = provider ?? (item.kind === 'SEARCH' ? 'Google Search Console' : '已记录机会');
  const freshness = item.kind === 'SEARCH' ? searchSource.freshness : item.lastSeenAt ?? null;
  const confidence = scalarEvidence(evidence.confidence) ?? '未声明（不推测）';
"""
    new = """  const subjectType = String(item.subjectType ?? '').toUpperCase();
  const query = scalarEvidence(evidence.query);
  const target = typeof item.target === 'string' && item.target.trim() ? item.target.trim() : null;
  const subject = subjectType === 'QUERY'
    ? (query ? `关键词：${query}` : '关键词（名称未声明）')
    : subjectType === 'PAGE'
      ? (target ? `页面：${target}` : '页面')
      : '网站';
  const provider = scalarEvidence(evidence.provider) ?? scalarEvidence(evidence.source);
  const source = provider ?? (item.kind === 'SEARCH' ? 'Google Search Console' : '未声明（不推测）');
  const recordedFreshness = scalarEvidence(evidence.sourceFreshness) ?? scalarEvidence(evidence.freshness);
  const freshness = item.kind === 'SEARCH'
    ? (searchSource.freshness ?? '未声明（不推测）')
    : (recordedFreshness ?? '未声明（不推测）');
  const confidence = scalarEvidence(evidence.confidence) ?? '未声明（不推测）';
"""
    text = once(text, old, new, 'node truthful subject and freshness')
    assert 'item.lastSeenAt ?? null' not in text[text.index('function opportunityExplainability'):text.index('export function deriveSearchOpportunities')]
    return text


def transform_php(text: str) -> str:
    old = "'evidence' => ['impressions' => (int) ($row['impressions'] ?? 0), 'ctr' => $row['ctr'] ?? null, 'position' => $row['position'] ?? null, 'previousPosition' => $row['previousPosition'] ?? null, 'movement' => $row['movement'] ?? null, 'landingPageId' => $row['landingPageId'] ?? null, 'landingPage' => $row['landingPage'] ?? null]"
    new = "'evidence' => ['query' => $row['query'] ?? null, 'impressions' => (int) ($row['impressions'] ?? 0), 'ctr' => $row['ctr'] ?? null, 'position' => $row['position'] ?? null, 'previousPosition' => $row['previousPosition'] ?? null, 'movement' => $row['movement'] ?? null, 'landingPageId' => $row['landingPageId'] ?? null, 'landingPage' => $row['landingPage'] ?? null]"
    text = once(text, old, new, 'php derived query evidence')

    old2 = """        $subjectType = strtoupper((string) ($item['subjectType'] ?? ''));
        $target = is_string($item['target'] ?? null) && trim((string) $item['target']) !== '' ? ' · ' . trim((string) $item['target']) : '';
        $subject = $subjectType === 'QUERY' ? '关键词' . $target : ($subjectType === 'PAGE' ? '页面' . $target : '网站');
        $provider = self::scalarEvidence($evidence['provider'] ?? null) ?? self::scalarEvidence($evidence['source'] ?? null);
        $source = $provider ?? (($item['kind'] ?? '') === 'SEARCH' ? 'Google Search Console' : '已记录机会');
        $freshness = ($item['kind'] ?? '') === 'SEARCH' ? ($searchSource['freshness'] ?? null) : ($item['lastSeenAt'] ?? null);
        $confidence = self::scalarEvidence($evidence['confidence'] ?? null) ?? '未声明（不推测）';
"""
    new2 = """        $subjectType = strtoupper((string) ($item['subjectType'] ?? ''));
        $query = self::scalarEvidence($evidence['query'] ?? null);
        $target = is_string($item['target'] ?? null) && trim((string) $item['target']) !== '' ? trim((string) $item['target']) : null;
        $subject = $subjectType === 'QUERY'
            ? ($query !== null ? '关键词：' . $query : '关键词（名称未声明）')
            : ($subjectType === 'PAGE' ? ($target !== null ? '页面：' . $target : '页面') : '网站');
        $provider = self::scalarEvidence($evidence['provider'] ?? null) ?? self::scalarEvidence($evidence['source'] ?? null);
        $source = $provider ?? (($item['kind'] ?? '') === 'SEARCH' ? 'Google Search Console' : '未声明（不推测）');
        $recordedFreshness = self::scalarEvidence($evidence['sourceFreshness'] ?? null) ?? self::scalarEvidence($evidence['freshness'] ?? null);
        $freshness = ($item['kind'] ?? '') === 'SEARCH'
            ? ($searchSource['freshness'] ?? '未声明（不推测）')
            : ($recordedFreshness ?? '未声明（不推测）');
        $confidence = self::scalarEvidence($evidence['confidence'] ?? null) ?? '未声明（不推测）';
"""
    text = once(text, old2, new2, 'php truthful subject and freshness')
    helper = text[text.index('private static function opportunityExplainability'):text.index('private static function portfolioStatus')]
    assert "$item['lastSeenAt'] ?? null" not in helper
    return text


def transform_test(text: str) -> str:
    text = text.replace("evidence: { impressions: 420, position: 6.4 },", "evidence: { query: 'example query', impressions: 420, position: 6.4 },", 1)
    text = text.replace("subject: '关键词 · https://example.com/landing',", "subject: '关键词：example query',", 1)
    text = text.replace("{ key: 'subject', label: '作用对象', value: '关键词 · https://example.com/landing' },", "{ key: 'subject', label: '作用对象', value: '关键词：example query' },", 1)

    marker = "  assert.match(phpService, /'firstSeenAt' => isset\\(\\$row\\['first_seen_at'\\]\\)/);\n});"
    addition = """  assert.match(nodeService, /evidence: \{ query: row\.query,/);
  assert.match(phpService, /'evidence' => \['query' => \$row\['query'\]/);
  assert.match(nodeService, /query \? `关键词：\$\{query\}` : '关键词（名称未声明）'/);
  assert.match(phpService, /'关键词：' \. \$query/);
  const nodeExplain = nodeService.slice(nodeService.indexOf('function opportunityExplainability'), nodeService.indexOf('export function deriveSearchOpportunities'));
  const phpExplain = phpService.slice(phpService.indexOf('private static function opportunityExplainability'), phpService.indexOf('private static function portfolioStatus'));
  for (const source of [nodeExplain, phpExplain]) {
    assert.ok(source.includes('未声明（不推测）'));
    assert.equal(source.includes('lastSeenAt ?? null'), false);
  }
"""
    assert marker in text
    text = text.replace(marker, addition + marker, 1)
    return text


def write_files():
    transforms = {
        'src/server/product-optimization.ts': transform_node,
        'php/src/ProductOptimizationService.php': transform_php,
        'tests/unit/product-opportunity-evidence-truth.test.ts': transform_test,
    }
    q = urllib.parse.quote(BRANCH, safe='')
    transformed = {}
    for path, fn in transforms.items():
        transformed[path] = fn(Path(path).read_text())
    print('P05_OPPORTUNITY_EXPLAINABILITY_SEMANTICS_CONSTRUCT=PASS')

    for path in transforms:
        current = get(f'https://api.github.com/repos/{REPO}/contents/{path}?ref={q}')
        assert current['sha'] == EXPECTED_BLOBS[path], (path, current['sha'], EXPECTED_BLOBS[path])
        result = api('PUT', f'https://api.github.com/repos/{REPO}/contents/{path}', {
            'message': 'fix(product): correct Opportunity explainability semantics' if not path.startswith('tests/') else 'test(product): lock Opportunity explainability semantics',
            'content': base64.b64encode(transformed[path].encode()).decode(),
            'sha': current['sha'],
            'branch': BRANCH,
        })
        print('WRITE', path, result['commit']['sha'])


def readback():
    main = get(f'https://api.github.com/repos/{REPO}/branches/main')['commit']['sha']
    head = get(f'https://api.github.com/repos/{REPO}/branches/{urllib.parse.quote(BRANCH, safe="")}')['commit']['sha']
    assert main == BASE, (main, BASE)
    compare = get(f'https://api.github.com/repos/{REPO}/compare/{BASE}...{head}')
    assert compare['behind_by'] == 0, compare['behind_by']
    files = sorted(row['filename'] for row in compare['files'])
    assert files == EXPECTED_SCOPE, (files, EXPECTED_SCOPE)
    version = get(f'https://api.github.com/repos/{REPO}/contents/VERSION?ref={urllib.parse.quote(BRANCH, safe="")}')
    assert base64.b64decode(version['content']).decode().strip() == '1.2.4'
    tree = get(f'https://api.github.com/repos/{REPO}/git/commits/{head}')['tree']['sha']
    print('P05_OPPORTUNITY_EXPLAINABILITY_SEMANTICS_REMOTE_SCOPE=PASS')
    print('P05_OPPORTUNITY_EXPLAINABILITY_HEAD=' + head)
    print('P05_OPPORTUNITY_EXPLAINABILITY_TREE=' + tree)


if __name__ == '__main__':
    exact_state_gate()
    write_files()
    readback()
