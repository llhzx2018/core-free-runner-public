#!/usr/bin/env python3
import base64
import json
import os
import urllib.parse
import urllib.request

REPO = 'llhzx2018/vf-seo'
BRANCH = 'release/p05-v1.2.5-takeover-20260903'
BASE = '30238c394d0537b74e17f8a08e46c8cd0e11c125'
BASE_TREE = '0de2c223e1adaaa62b0b6b4f8b42dc0dcd0016d4'
EXPECTED_HEAD = 'd2c0e2c1673be22e7e28abfd8f90327a3d0aa65d'
PROJECT_PATH = 'VF_PROJECT.json'
PROJECT_BLOB = '1bcd33b81a75fe02b3a78a2e357c12e9e6f1d04a'
APP_PATH = 'src/client/ProductApp.tsx'
APP_BLOB = 'bc49b0ee8f333bdb16fe5d5d99d0254ac0159242'
TOKEN = os.environ['VF_RELEASE_WRITE_TOKEN']
EXPECTED_SCOPE = sorted([
    'VERSION',
    'package.json',
    'VF_PROJECT.json',
    'src/client/ProductApp.tsx',
    'docs/authority/RELEASE_V1.2.5_CANDIDATE.md',
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


def branch_url(branch: str) -> str:
    return f'https://api.github.com/repos/{REPO}/branches/{urllib.parse.quote(branch, safe="")}'


def content(path: str, branch: str):
    ref = urllib.parse.quote(branch, safe='')
    return get(f'https://api.github.com/repos/{REPO}/contents/{path}?ref={ref}')


def decode(row) -> str:
    return base64.b64decode(row['content']).decode('utf-8')


def write(path: str, row, updated: str, message: str):
    result = api('PUT', f'https://api.github.com/repos/{REPO}/contents/{path}', {
        'message': message,
        'content': base64.b64encode(updated.encode('utf-8')).decode('ascii'),
        'sha': row['sha'],
        'branch': BRANCH,
    })
    print(f'P05_V125_WRITE_{path}=' + result['commit']['sha'])
    return result['commit']['sha']


def exact_state_gate():
    main = get(branch_url('main'))['commit']['sha']
    head = get(branch_url(BRANCH))['commit']['sha']
    assert main == BASE, (main, BASE)
    assert head == EXPECTED_HEAD, (head, EXPECTED_HEAD)

    git_commit = get(f'https://api.github.com/repos/{REPO}/git/commits/{BASE}')
    assert git_commit['tree']['sha'] == BASE_TREE, (git_commit['tree']['sha'], BASE_TREE)

    version = content('VERSION', BRANCH)
    package = content('package.json', BRANCH)
    project = content(PROJECT_PATH, BRANCH)
    app = content(APP_PATH, BRANCH)

    assert decode(version).strip() == '1.2.5'
    assert json.loads(decode(package))['version'] == '1.2.5'
    assert project['sha'] == PROJECT_BLOB, (project['sha'], PROJECT_BLOB)
    assert app['sha'] == APP_BLOB, (app['sha'], APP_BLOB)

    compare = get(f'https://api.github.com/repos/{REPO}/compare/{BASE}...{head}')
    assert compare['behind_by'] == 0, compare['behind_by']
    assert sorted(item['filename'] for item in compare['files']) == sorted([
        'VERSION', 'package.json', 'docs/authority/RELEASE_V1.2.5_CANDIDATE.md'
    ])
    print('P05_V125_EXACT_STATE=PASS')
    return project, app


def transform_project(text: str) -> str:
    project = json.loads(text)
    assert project['project_id'] == 'P05'
    assert project['version'] == '1.2.4'
    assert project['production_version'] == '1.2.4'
    assert project['formal_release'] == 'v1.2.4'

    project['status'] = 'V1.2.5_RELEASE_CANDIDATE / MAIN_PROMOTION_APPROVAL_PENDING / PRODUCTION_V1.2.4_CLOSED'
    project['version'] = '1.2.5'
    project['target_version'] = '1.2.5'
    project['working_version'] = '1.2.5'
    project['version_change'] = True
    project['working_branch'] = BRANCH
    project['candidate_authorization'] = 'P05_PUBLICATION_TAKEOVER_RECONSTRUCTED / MAIN_PROMOTION_APPROVAL_PENDING'
    project['release_authorization'] = 'PENDING_EXPLICIT_V1.2.5_MAIN_PROMOTION_APPROVAL'
    project['production_deployment_authorization'] = 'NO_NEW_PRODUCTION_WRITE_AUTHORIZED / PRODUCTION_V1.2.4_CLOSED'
    project['next_action'] = 'V1.2.5 FINAL EXACT GATES → EXPLICIT MAIN PROMOTION APPROVAL → FORMAL FULL/TAG/RELEASE → ATOMIC UPDATE CHANNEL → PRODUCTION READBACK'
    project['authority']['release_candidate'] = 'docs/authority/RELEASE_V1.2.5_CANDIDATE.md'
    project['deployment_readiness'] = 'V1.2.5_RELEASE_CANDIDATE / PRODUCTION_BASELINE_V1.2.4_CLOSED / MAIN_PROMOTION_APPROVAL_PENDING'
    project['current_engineering_main'] = BASE
    project['current_engineering_tree'] = BASE_TREE
    project['current_engineering_state'] = 'V1.2.5_OWNER_WORKFLOW_ENGINEERING_FROZEN_FOR_RELEASE_CANDIDATE'
    project['v1_2_5_release_candidate'] = {
        'state': 'TAKEOVER_RECONSTRUCTED_MAIN_PROMOTION_APPROVAL_PENDING',
        'production_baseline': 'v1.2.4',
        'frozen_engineering_main': BASE,
        'frozen_engineering_tree': BASE_TREE,
        'candidate_branch': BRANCH,
        'scope_prs': [211, 214, 215, 216, 217, 218, 219, 220],
        'schema': 'VF-SEO-SCHEMA@1 / 1',
        'database_format_changed': False,
        'production_write': 0,
        'formal_release_remains_until_publication': 'v1.2.4',
    }

    assert project['production_version'] == '1.2.4'
    assert project['formal_release'] == 'v1.2.4'
    assert project['release_publication']['tag'] == 'v1.2.4'
    assert project['v1_2_4_production_closure']['state'] == 'PASS_CLOSED'
    print('P05_V125_PROJECT_TRANSFORM=PASS')
    return json.dumps(project, ensure_ascii=False, indent=2) + '\n'


def transform_app(text: str) -> str:
    old = 'P05 · VF SEO · v1.2.4'
    new = 'P05 · VF SEO · v1.2.5'
    assert text.count(old) == 1, text.count(old)
    assert text.count(new) == 0, text.count(new)
    updated = text.replace(old, new, 1)
    assert updated.count(new) == 1
    print('P05_V125_APP_TRANSFORM=PASS')
    return updated


def readback():
    main = get(branch_url('main'))['commit']['sha']
    head = get(branch_url(BRANCH))['commit']['sha']
    assert main == BASE, (main, BASE)
    assert head != EXPECTED_HEAD, head

    compare = get(f'https://api.github.com/repos/{REPO}/compare/{BASE}...{head}')
    assert compare['behind_by'] == 0, compare['behind_by']
    files = sorted(item['filename'] for item in compare['files'])
    assert files == EXPECTED_SCOPE, (files, EXPECTED_SCOPE)

    version = decode(content('VERSION', BRANCH)).strip()
    package = json.loads(decode(content('package.json', BRANCH)))
    project = json.loads(decode(content(PROJECT_PATH, BRANCH)))
    app = decode(content(APP_PATH, BRANCH))

    assert version == '1.2.5'
    assert package['version'] == version
    assert project['version'] == version
    assert project['target_version'] == version
    assert project['working_version'] == version
    assert project['production_version'] == '1.2.4'
    assert project['formal_release'] == 'v1.2.4'
    assert project['release_publication']['tag'] == 'v1.2.4'
    assert app.count('P05 · VF SEO · v1.2.5') == 1
    assert 'P05 · VF SEO · v1.2.4' not in app

    tree = get(f'https://api.github.com/repos/{REPO}/git/commits/{head}')['tree']['sha']
    print('P05_V125_REMOTE_SCOPE=PASS')
    print('P05_V125_PRODUCTION_HISTORY_PRESERVED=PASS')
    print('P05_V125_CANDIDATE_HEAD=' + head)
    print('P05_V125_CANDIDATE_TREE=' + tree)


if __name__ == '__main__':
    project_row, app_row = exact_state_gate()
    write(PROJECT_PATH, project_row, transform_project(decode(project_row)), 'release(P05): synchronize v1.2.5 candidate authority')
    write(APP_PATH, app_row, transform_app(decode(app_row)), 'release(P05): show v1.2.5 product identity')
    readback()
