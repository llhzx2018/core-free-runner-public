#!/usr/bin/env python3
import base64
import json
import os
import urllib.parse
import urllib.request

REPO = 'llhzx2018/vf-seo'
BRANCH = 'l2/opportunity-explainability-contract-20260903'
BASE = 'a9c09033e846e7030cb460d0d2135c29090d07e0'
EXPECTED_HEAD = '8c754d5712e30f303a4135d301f2d76845a277bc'
PATH = 'src/server/product-optimization.ts'
EXPECTED_BLOB = '19c0fb229b8d7544f33518ba8d85103a5d12be1c'
TOKEN = os.environ['VF_RELEASE_WRITE_TOKEN']
EXPECTED_SCOPE = sorted([
    'src/server/product-optimization.ts',
    'php/src/ProductOptimizationService.php',
    'src/client/product-opportunity-evidence.ts',
    'tests/unit/product-opportunity-evidence-truth.test.ts',
])
HEADERS = {
    'Authorization': 'Bearer ' + TOKEN,
    'Accept': 'application/vnd.github+json',
    'Content-Type': 'application/json',
    'X-GitHub-Api-Version': '2022-11-28',
}


def api(method: str, url: str, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def get(url: str):
    return api('GET', url)


def exact_state_gate():
    main = get(f'https://api.github.com/repos/{REPO}/branches/main')['commit']['sha']
    head = get(f'https://api.github.com/repos/{REPO}/branches/{urllib.parse.quote(BRANCH, safe="")}')['commit']['sha']
    assert main == BASE, (main, BASE)
    assert head == EXPECTED_HEAD, (head, EXPECTED_HEAD)
    version = get(f'https://api.github.com/repos/{REPO}/contents/VERSION?ref={urllib.parse.quote(BRANCH, safe="")}')
    assert base64.b64decode(version['content']).decode().strip() == '1.2.4'
    row = get(f'https://api.github.com/repos/{REPO}/contents/{PATH}?ref={urllib.parse.quote(BRANCH, safe="")}')
    assert row['sha'] == EXPECTED_BLOB, (row['sha'], EXPECTED_BLOB)
    print('P05_NEXT_ACTIONS_CONTRACT_EXACT_STATE=PASS')
    return row


def transform(text: str) -> str:
    old1 = 'const nextActions: Json[] = explainedGrowthOpportunities.slice(0, 5).map(row => ({'
    new1 = 'const nextActions: Json[] = growthOpportunities.slice(0, 5).map(row => ({'
    old2 = '    explainability: row.explainability,'
    new2 = '    explainability: opportunityExplainability(row, site.business_value, searchSource),'
    assert text.count(old1) == 1, text.count(old1)
    assert text.count(old2) == 1, text.count(old2)
    text = text.replace(old1, new1, 1).replace(old2, new2, 1)
    assert old1 not in text
    assert old2 not in text
    assert new1 in text
    assert new2 in text
    print('P05_NEXT_ACTIONS_CONTRACT_CONSTRUCT=PASS')
    return text


def write(row):
    current = base64.b64decode(row['content']).decode()
    updated = transform(current)
    result = api('PUT', f'https://api.github.com/repos/{REPO}/contents/{PATH}', {
        'message': 'fix(product): preserve Overview next-actions source contract',
        'content': base64.b64encode(updated.encode()).decode(),
        'sha': row['sha'],
        'branch': BRANCH,
    })
    print('P05_NEXT_ACTIONS_CONTRACT_WRITE=' + result['commit']['sha'])


def readback():
    main = get(f'https://api.github.com/repos/{REPO}/branches/main')['commit']['sha']
    head = get(f'https://api.github.com/repos/{REPO}/branches/{urllib.parse.quote(BRANCH, safe="")}')['commit']['sha']
    assert main == BASE, (main, BASE)
    compare = get(f'https://api.github.com/repos/{REPO}/compare/{BASE}...{head}')
    assert compare['behind_by'] == 0, compare['behind_by']
    files = sorted(item['filename'] for item in compare['files'])
    assert files == EXPECTED_SCOPE, (files, EXPECTED_SCOPE)
    version = get(f'https://api.github.com/repos/{REPO}/contents/VERSION?ref={urllib.parse.quote(BRANCH, safe="")}')
    assert base64.b64decode(version['content']).decode().strip() == '1.2.4'
    tree = get(f'https://api.github.com/repos/{REPO}/git/commits/{head}')['tree']['sha']
    print('P05_NEXT_ACTIONS_CONTRACT_REMOTE_SCOPE=PASS')
    print('P05_NEXT_ACTIONS_CONTRACT_HEAD=' + head)
    print('P05_NEXT_ACTIONS_CONTRACT_TREE=' + tree)


if __name__ == '__main__':
    row = exact_state_gate()
    write(row)
    readback()
