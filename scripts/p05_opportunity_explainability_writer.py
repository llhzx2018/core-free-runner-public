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
TOKEN = os.environ['VF_RELEASE_WRITE_TOKEN']
HEADERS = {
    'Authorization': 'Bearer ' + TOKEN,
    'Accept': 'application/vnd.github+json',
    'Content-Type': 'application/json',
    'X-GitHub-Api-Version': '2022-11-28',
}

EXPECTED_FILES = [
    'src/server/product-optimization.ts',
    'php/src/ProductOptimizationService.php',
    'src/client/product-opportunity-evidence.ts',
    'tests/unit/product-opportunity-evidence-truth.test.ts',
]
EXPECTED_SHA = {
    'src/server/product-optimization.ts': 'b569ae84172e7f0747dbc9fc332e4dad352b98a7',
    'php/src/ProductOptimizationService.php': '4b0e8415c9546894721d6329bb06a0f9b7756e29',
    'src/client/product-opportunity-evidence.ts': '7749166c000711bc8774bfc0e8e393d56c7f9334',
    'tests/unit/product-opportunity-evidence-truth.test.ts': 'a74fd374a2fea5c207dc8ed5a58e9abb75be6d32',
}


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
    assert new not in text, (label, 'new already present')
    return text.replace(old, new, 1)


def assert_exact_base():
    main = get(f'https://api.github.com/repos/{REPO}/branches/main')['commit']['sha']
    candidate = get(f'https://api.github.com/repos/{REPO}/branches/{urllib.parse.quote(BRANCH, safe="")}')['commit']['sha']
    assert main == BASE, (main, BASE)
    assert candidate == BASE, (candidate, BASE)
    print('P05_OPPORTUNITY_EXPLAINABILITY_EXACT_BASE=PASS')


def transform_node(text: str) -> str:
    text = once(text,
        "  movement?: number | null;\n};",
        "  movement?: number | null;\n  observedOn?: string | null;\n  previousObservedOn?: string | null;\n};",
        'node search observation fields')
    text = once(text,
        "  sourceState: string;\n  lifecycleState: string;\n};",
        "  sourceState: string;\n  lifecycleState: string;\n  firstSeenAt?: string | null;\n  lastSeenAt?: string | null;\n};",
        'node opportunity observation fields')

    old = """function opportunitySort(a: ProductOpportunity, b: ProductOpportunity): number {
  return priorityRank(a.priority) - priorityRank(b.priority)
    || number(b.evidence?.impressions) - number(a.evidence?.impressions)
    || a.title.localeCompare(b.title);
}
"""
    new = old + """
function scalarEvidence(value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null;
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : null;
}

function businessValueLabel(value: unknown): string {
  const raw = String(value ?? 'NORMAL').trim().toUpperCase();
  return raw === 'HIGH' ? '高' : raw === 'LOW' ? '低' : '普通';
}

function opportunityExplainability(item: ProductOpportunity, businessValue: unknown, searchSource: SourceSummary): Json {
  const evidence = item.evidence && typeof item.evidence === 'object' ? item.evidence : {};
  const type = String(item.opportunityType ?? '').toUpperCase();
  const impressions = number(evidence.impressions);
  const movement = productNullableNumber(evidence.movement);
  const previousPosition = productNullableNumber(evidence.previousPosition);
  let trigger = scalarEvidence(evidence.trigger) ?? item.reason;
  let baseline = scalarEvidence(evidence.baseline) ?? '当前记录未提供可验证的基线或规则阈值。';
  const current = scalarEvidence(evidence.current) ?? item.reason;
  let whyPriority = scalarEvidence(evidence.priorityReason) ?? `已记录为 ${item.priority}；当前记录未提供更细的优先级依据。`;

  if (type === 'CTR_OPPORTUNITY') {
    trigger = '排名 ≤ 10、展示 ≥ 100 且 CTR < 4%。';
    baseline = '规则阈值：排名 ≤ 10、展示 ≥ 100、CTR < 4%。';
    whyPriority = item.priority === 'P1'
      ? `P1：当前展示量 ${impressions} ≥ 300。`
      : `P2：当前展示量 ${impressions} < 300，但已满足基础触发阈值。`;
  } else if (type === 'STRIKING_DISTANCE') {
    trigger = '排名 4–20 且展示 ≥ 50。';
    baseline = '规则阈值：排名 4–20、展示 ≥ 50。';
    whyPriority = item.priority === 'P1'
      ? `P1：当前展示量 ${impressions} ≥ 200。`
      : `P2：当前展示量 ${impressions} < 200，但已满足基础触发阈值。`;
  } else if (type === 'RANKING_RECOVERY') {
    trigger = '较前一观察日下降 ≥ 1 位且展示 ≥ 50。';
    baseline = previousPosition == null
      ? '规则阈值：下降 ≥ 1 位且展示 ≥ 50。'
      : `上一观察位置 ${previousPosition.toFixed(1)}；规则阈值：下降 ≥ 1 位且展示 ≥ 50。`;
    whyPriority = item.priority === 'P1'
      ? `P1：排名回落至少 2 位或展示量 ≥ 200；当前变化 ${movement == null ? '—' : movement.toFixed(1)} 位，展示 ${impressions}。`
      : 'P2：已满足回落触发阈值，但未达到 P1 的回落幅度 / 展示量条件。';
  }

  const subjectType = String(item.subjectType ?? '').toUpperCase();
  const target = typeof item.target === 'string' && item.target.trim() ? ` · ${item.target.trim()}` : '';
  const subject = subjectType === 'QUERY' ? `关键词${target}` : subjectType === 'PAGE' ? `页面${target}` : '网站';
  const provider = scalarEvidence(evidence.provider) ?? scalarEvidence(evidence.source);
  const source = provider ?? (item.kind === 'SEARCH' ? 'Google Search Console' : '已记录机会');
  const freshness = item.kind === 'SEARCH' ? searchSource.freshness : item.lastSeenAt ?? null;
  const confidence = scalarEvidence(evidence.confidence) ?? '未声明（不推测）';
  return {
    trigger,
    baseline,
    current,
    firstSeenAt: item.firstSeenAt ?? null,
    lastSeenAt: item.lastSeenAt ?? null,
    source,
    freshness,
    subject,
    confidence,
    whyPriority,
    businessValueInfluence: `网站业务价值：${businessValueLabel(businessValue)}；影响跨站运营排序，本网站内机会仍按 ${item.priority} 与证据排序；不改原始指标。`,
  };
}
"""
    text = once(text, old, new, 'node explainability helper')

    old_derived = "        sourceState: 'FRESH',\n        lifecycleState: 'DERIVED',"
    new_derived = "        sourceState: 'FRESH',\n        lifecycleState: 'DERIVED',\n        firstSeenAt: row.previousObservedOn ?? row.observedOn ?? null,\n        lastSeenAt: row.observedOn ?? null,"
    assert text.count(old_derived) == 3, text.count(old_derived)
    text = text.replace(old_derived, new_derived, 3)

    old_no_movement = "evidence: { impressions, ctr, position, landingPageId: row.landingPageId ?? null, landingPage: row.landingPage ?? null },"
    assert text.count(old_no_movement) == 2, text.count(old_no_movement)
    text = text.replace(old_no_movement,
        "evidence: { impressions, ctr, position, previousPosition: row.previousPosition ?? null, landingPageId: row.landingPageId ?? null, landingPage: row.landingPage ?? null },")
    text = once(text,
        "evidence: { impressions, ctr, position, movement, landingPageId: row.landingPageId ?? null, landingPage: row.landingPage ?? null },",
        "evidence: { impressions, ctr, position, previousPosition: row.previousPosition ?? null, movement, landingPageId: row.landingPageId ?? null, landingPage: row.landingPage ?? null },",
        'node recovery previous position')

    text = once(text,
        "    sourceState: String(row.source_state ?? 'UNKNOWN'),\n    lifecycleState: String(row.lifecycle_state ?? 'OPEN'),\n  };",
        "    sourceState: String(row.source_state ?? 'UNKNOWN'),\n    lifecycleState: String(row.lifecycle_state ?? 'OPEN'),\n    firstSeenAt: row.first_seen_at == null ? null : String(row.first_seen_at),\n    lastSeenAt: row.last_seen_at == null ? null : String(row.last_seen_at),\n  };",
        'node persisted observation preservation')
    text = once(text,
        "      movement: position != null && previousPosition != null ? previousPosition - position : null,\n    });",
        "      movement: position != null && previousPosition != null ? previousPosition - position : null,\n      observedOn: latest.observed_on == null ? null : String(latest.observed_on),\n      previousObservedOn: previous?.observed_on == null ? null : String(previous.observed_on),\n    });",
        'node keyword observation window')
    text = once(text,
        "  const growthOpportunities = [...persisted, ...derived].sort(opportunitySort).slice(0, 12);\n  const status = portfolioStatus({ source, issues, delta, opportunities: growthOpportunities });",
        "  const growthOpportunities = [...persisted, ...derived].sort(opportunitySort).slice(0, 12);\n  const explainedGrowthOpportunities = growthOpportunities.map(row => ({ ...row, explainability: opportunityExplainability(row, site.business_value, searchSource) }));\n  const status = portfolioStatus({ source, issues, delta, opportunities: growthOpportunities });",
        'node explained growth')
    text = once(text,
        "  const nextActions: Json[] = growthOpportunities.slice(0, 5).map(row => ({",
        "  const nextActions: Json[] = explainedGrowthOpportunities.slice(0, 5).map(row => ({",
        'node next actions explained source')
    text = once(text,
        "    evidence: row.evidence,\n  }));",
        "    evidence: row.evidence,\n    explainability: row.explainability,\n  }));",
        'node next action explainability')
    text = once(text,
        "    growthOpportunities,\n    changes,",
        "    growthOpportunities: explainedGrowthOpportunities,\n    changes,",
        'node response explained growth')
    return text


def transform_php(text: str) -> str:
    text = once(text,
        "            $out[] = ['id' => (string) $latest['id'], 'query' => (string) $latest['observed_query'], 'landingPageId' => isset($latest['landing_page_id']) ? (string) $latest['landing_page_id'] : null, 'landingPage' => $latest['landing_page'] ?? null, 'clicks' => (int) ($latest['clicks'] ?? 0), 'impressions' => (int) ($latest['impressions'] ?? 0), 'ctr' => self::nullableNumber($latest['ctr'] ?? null), 'position' => $position, 'previousPosition' => $previousPosition, 'movement' => $position !== null && $previousPosition !== null ? $previousPosition - $position : null];",
        "            $out[] = ['id' => (string) $latest['id'], 'query' => (string) $latest['observed_query'], 'landingPageId' => isset($latest['landing_page_id']) ? (string) $latest['landing_page_id'] : null, 'landingPage' => $latest['landing_page'] ?? null, 'clicks' => (int) ($latest['clicks'] ?? 0), 'impressions' => (int) ($latest['impressions'] ?? 0), 'ctr' => self::nullableNumber($latest['ctr'] ?? null), 'position' => $position, 'previousPosition' => $previousPosition, 'movement' => $position !== null && $previousPosition !== null ? $previousPosition - $position : null, 'observedOn' => isset($latest['observed_on']) ? (string) $latest['observed_on'] : null, 'previousObservedOn' => isset($previous['observed_on']) ? (string) $previous['observed_on'] : null];",
        'php keyword observation window')
    text = once(text,
        "    private static function derivedOpportunity(array $row, string $type, string $priority, string $title, string $reason, string $action): array { return ['id' => 'derived:' . strtolower($type) . ':' . $row['id'], 'kind' => 'SEARCH', 'opportunityType' => $type, 'priority' => $priority, 'title' => $title, 'reason' => $reason, 'action' => $action, 'subjectType' => 'QUERY', 'subjectId' => $row['id'], 'target' => $row['landingPage'] ?? null, 'evidence' => ['impressions' => (int) ($row['impressions'] ?? 0), 'ctr' => $row['ctr'] ?? null, 'position' => $row['position'] ?? null, 'movement' => $row['movement'] ?? null, 'landingPageId' => $row['landingPageId'] ?? null, 'landingPage' => $row['landingPage'] ?? null], 'sourceState' => 'FRESH', 'lifecycleState' => 'DERIVED']; }",
        "    private static function derivedOpportunity(array $row, string $type, string $priority, string $title, string $reason, string $action): array { return ['id' => 'derived:' . strtolower($type) . ':' . $row['id'], 'kind' => 'SEARCH', 'opportunityType' => $type, 'priority' => $priority, 'title' => $title, 'reason' => $reason, 'action' => $action, 'subjectType' => 'QUERY', 'subjectId' => $row['id'], 'target' => $row['landingPage'] ?? null, 'evidence' => ['impressions' => (int) ($row['impressions'] ?? 0), 'ctr' => $row['ctr'] ?? null, 'position' => $row['position'] ?? null, 'previousPosition' => $row['previousPosition'] ?? null, 'movement' => $row['movement'] ?? null, 'landingPageId' => $row['landingPageId'] ?? null, 'landingPage' => $row['landingPage'] ?? null], 'sourceState' => 'FRESH', 'lifecycleState' => 'DERIVED', 'firstSeenAt' => $row['previousObservedOn'] ?? $row['observedOn'] ?? null, 'lastSeenAt' => $row['observedOn'] ?? null]; }",
        'php derived observation preservation')
    text = once(text,
        "'sourceState' => (string) ($row['source_state'] ?? 'UNKNOWN'), 'lifecycleState' => (string) ($row['lifecycle_state'] ?? 'OPEN')];",
        "'sourceState' => (string) ($row['source_state'] ?? 'UNKNOWN'), 'lifecycleState' => (string) ($row['lifecycle_state'] ?? 'OPEN'), 'firstSeenAt' => isset($row['first_seen_at']) ? (string) $row['first_seen_at'] : null, 'lastSeenAt' => isset($row['last_seen_at']) ? (string) $row['last_seen_at'] : null];",
        'php persisted observation preservation')

    anchor = "    private static function opportunityCompare(array $a, array $b): int { $rank = self::priorityRank($a['priority'] ?? null) <=> self::priorityRank($b['priority'] ?? null); if ($rank !== 0) return $rank; $impressions = ((int) ($b['evidence']['impressions'] ?? 0)) <=> ((int) ($a['evidence']['impressions'] ?? 0)); return $impressions !== 0 ? $impressions : strcmp((string) ($a['title'] ?? ''), (string) ($b['title'] ?? '')); }\n"
    helper = anchor + """

    private static function scalarEvidence(mixed $value): ?string
    {
        if ($value === null || $value === '') return null;
        return is_string($value) || is_int($value) || is_float($value) || is_bool($value) ? (string) $value : null;
    }

    private static function businessValueLabel(mixed $value): string
    {
        return match (strtoupper(trim((string) ($value ?? 'NORMAL')))) { 'HIGH' => '高', 'LOW' => '低', default => '普通' };
    }

    /** @param array<string,mixed> $item @param array<string,mixed> $searchSource @return array<string,mixed> */
    private static function opportunityExplainability(array $item, mixed $businessValue, array $searchSource): array
    {
        $evidence = is_array($item['evidence'] ?? null) ? $item['evidence'] : [];
        $type = strtoupper((string) ($item['opportunityType'] ?? ''));
        $impressions = (int) ($evidence['impressions'] ?? 0);
        $movement = self::nullableNumber($evidence['movement'] ?? null);
        $previousPosition = self::nullableNumber($evidence['previousPosition'] ?? null);
        $trigger = self::scalarEvidence($evidence['trigger'] ?? null) ?? (string) ($item['reason'] ?? '');
        $baseline = self::scalarEvidence($evidence['baseline'] ?? null) ?? '当前记录未提供可验证的基线或规则阈值。';
        $current = self::scalarEvidence($evidence['current'] ?? null) ?? (string) ($item['reason'] ?? '');
        $whyPriority = self::scalarEvidence($evidence['priorityReason'] ?? null) ?? ('已记录为 ' . ($item['priority'] ?? 'P3') . '；当前记录未提供更细的优先级依据。');
        if ($type === 'CTR_OPPORTUNITY') {
            $trigger = '排名 ≤ 10、展示 ≥ 100 且 CTR < 4%。';
            $baseline = '规则阈值：排名 ≤ 10、展示 ≥ 100、CTR < 4%。';
            $whyPriority = ($item['priority'] ?? '') === 'P1' ? 'P1：当前展示量 ' . $impressions . ' ≥ 300。' : 'P2：当前展示量 ' . $impressions . ' < 300，但已满足基础触发阈值。';
        } elseif ($type === 'STRIKING_DISTANCE') {
            $trigger = '排名 4–20 且展示 ≥ 50。';
            $baseline = '规则阈值：排名 4–20、展示 ≥ 50。';
            $whyPriority = ($item['priority'] ?? '') === 'P1' ? 'P1：当前展示量 ' . $impressions . ' ≥ 200。' : 'P2：当前展示量 ' . $impressions . ' < 200，但已满足基础触发阈值。';
        } elseif ($type === 'RANKING_RECOVERY') {
            $trigger = '较前一观察日下降 ≥ 1 位且展示 ≥ 50。';
            $baseline = $previousPosition === null ? '规则阈值：下降 ≥ 1 位且展示 ≥ 50。' : '上一观察位置 ' . number_format($previousPosition, 1) . '；规则阈值：下降 ≥ 1 位且展示 ≥ 50。';
            $whyPriority = ($item['priority'] ?? '') === 'P1' ? 'P1：排名回落至少 2 位或展示量 ≥ 200；当前变化 ' . ($movement === null ? '—' : number_format($movement, 1)) . ' 位，展示 ' . $impressions . '。' : 'P2：已满足回落触发阈值，但未达到 P1 的回落幅度 / 展示量条件。';
        }
        $subjectType = strtoupper((string) ($item['subjectType'] ?? ''));
        $target = is_string($item['target'] ?? null) && trim((string) $item['target']) !== '' ? ' · ' . trim((string) $item['target']) : '';
        $subject = $subjectType === 'QUERY' ? '关键词' . $target : ($subjectType === 'PAGE' ? '页面' . $target : '网站');
        $provider = self::scalarEvidence($evidence['provider'] ?? null) ?? self::scalarEvidence($evidence['source'] ?? null);
        $source = $provider ?? (($item['kind'] ?? '') === 'SEARCH' ? 'Google Search Console' : '已记录机会');
        $freshness = ($item['kind'] ?? '') === 'SEARCH' ? ($searchSource['freshness'] ?? null) : ($item['lastSeenAt'] ?? null);
        $confidence = self::scalarEvidence($evidence['confidence'] ?? null) ?? '未声明（不推测）';
        return [
            'trigger' => $trigger, 'baseline' => $baseline, 'current' => $current,
            'firstSeenAt' => $item['firstSeenAt'] ?? null, 'lastSeenAt' => $item['lastSeenAt'] ?? null,
            'source' => $source, 'freshness' => $freshness, 'subject' => $subject, 'confidence' => $confidence,
            'whyPriority' => $whyPriority,
            'businessValueInfluence' => '网站业务价值：' . self::businessValueLabel($businessValue) . '；影响跨站运营排序，本网站内机会仍按 ' . ($item['priority'] ?? 'P3') . ' 与证据排序；不改原始指标。',
        ];
    }
"""
    text = once(text, anchor, helper, 'php explainability helper')
    text = once(text,
        "        $growth = array_slice($growth, 0, 12);\n        $status = self::portfolioStatus($source, $issues, $delta, $growth);",
        "        $growth = array_slice($growth, 0, 12);\n        $explainedGrowth = array_map(static fn(array $row): array => array_merge($row, ['explainability' => self::opportunityExplainability($row, $site['business_value'] ?? 'NORMAL', $searchSource)]), $growth);\n        $status = self::portfolioStatus($source, $issues, $delta, $growth);",
        'php explained growth')
    text = once(text,
        "        foreach (array_slice($growth, 0, 5) as $row) $nextActions[] = ['id' => $row['id'], 'kind' => $row['opportunityType'], 'opportunityKind' => $row['kind'], 'priority' => $row['priority'], 'title' => $row['title'], 'reason' => $row['reason'], 'action' => $row['action'], 'subjectType' => $row['subjectType'], 'subjectId' => $row['subjectId'], 'target' => $row['target'] ?? null, 'evidence' => $row['evidence'] ?? []];",
        "        foreach (array_slice($explainedGrowth, 0, 5) as $row) $nextActions[] = ['id' => $row['id'], 'kind' => $row['opportunityType'], 'opportunityKind' => $row['kind'], 'priority' => $row['priority'], 'title' => $row['title'], 'reason' => $row['reason'], 'action' => $row['action'], 'subjectType' => $row['subjectType'], 'subjectId' => $row['subjectId'], 'target' => $row['target'] ?? null, 'evidence' => $row['evidence'] ?? [], 'explainability' => $row['explainability'] ?? []];",
        'php next action explainability')
    text = once(text,
        "'opportunities' => $persistedRows, 'growthOpportunities' => $growth, 'changes' => $changes,",
        "'opportunities' => $persistedRows, 'growthOpportunities' => $explainedGrowth, 'changes' => $changes,",
        'php response explained growth')
    return text


def transform_ui(text: str) -> str:
    helper = """function text(value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null;
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : null;
}
"""
    helper_new = helper + """
function observedDay(value: unknown): string | null {
  const raw = text(value)?.trim();
  if (!raw) return null;
  const iso = raw.match(/^(\\d{4})-(\\d{2})-(\\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? raw : new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(parsed);
}

function observedRange(first: unknown, last: unknown): string | null {
  const start = observedDay(first);
  const end = observedDay(last);
  if (!start && !end) return null;
  if (!start || start === end) return end ?? start;
  if (!end) return start;
  return `${start} → ${end}`;
}
"""
    text = once(text, helper, helper_new, 'ui observed date helpers')
    text = once(text,
        "  const rows: ProductOpportunityEvidenceRow[] = [];\n  const add = (key: string, label: string, value: string | null) => { if (value != null) rows.push({ key, label, value }); };\n\n  add('impressions', '展示量', count(evidence.impressions));",
        "  const explainability = item?.explainability && typeof item.explainability === 'object' && !Array.isArray(item.explainability) ? item.explainability as Json : {};\n  const rows: ProductOpportunityEvidenceRow[] = [];\n  const add = (key: string, label: string, value: string | null) => { if (value != null) rows.push({ key, label, value }); };\n\n  add('trigger', '触发条件', text(explainability.trigger));\n  add('baseline', '基线 / 阈值', text(explainability.baseline));\n  add('current', '当前观察', text(explainability.current));\n  add('timeRange', '观察时间', observedRange(explainability.firstSeenAt, explainability.lastSeenAt));\n  add('source', '数据来源', text(explainability.source));\n  add('freshness', '数据新鲜度', observedDay(explainability.freshness));\n  add('subject', '作用对象', text(explainability.subject));\n  add('confidence', '置信度', text(explainability.confidence));\n  add('whyPriority', '为什么这个优先级', text(explainability.whyPriority));\n  add('businessValueInfluence', '业务价值影响', text(explainability.businessValueInfluence));\n\n  add('impressions', '展示量', count(evidence.impressions));",
        'ui explainability rows')
    return text


def transform_test(text: str) -> str:
    text = once(text,
        "const opportunitySurface = readFileSync(new URL('../../src/client/ProductSiteViews.tsx', import.meta.url), 'utf8');",
        "const opportunitySurface = readFileSync(new URL('../../src/client/ProductSiteViews.tsx', import.meta.url), 'utf8');\nconst nodeService = readFileSync(new URL('../../src/server/product-optimization.ts', import.meta.url), 'utf8');\nconst phpService = readFileSync(new URL('../../php/src/ProductOptimizationService.php', import.meta.url), 'utf8');",
        'test source imports')
    addition = r'''

test('Opportunity explainability exposes the RPD minimum without inventing confidence or score', () => {
  const rows = productOpportunityEvidenceRows({
    target: 'https://example.com/landing',
    evidence: { impressions: 420, position: 6.4 },
    explainability: {
      trigger: '排名 4–20 且展示 ≥ 50。',
      baseline: '规则阈值：排名 4–20、展示 ≥ 50。',
      current: '当前位置 6.4，已有 420 次展示。',
      firstSeenAt: '2026-08-29T03:00:00.000Z',
      lastSeenAt: '2026-08-30T03:00:00.000Z',
      source: 'Google Search Console',
      freshness: '2026-08-30T03:00:00.000Z',
      subject: '关键词 · https://example.com/landing',
      confidence: '未声明（不推测）',
      whyPriority: 'P1：当前展示量 420 ≥ 200。',
      businessValueInfluence: '网站业务价值：高；影响跨站运营排序，本网站内机会仍按 P1 与证据排序；不改原始指标。',
    },
  });
  assert.deepEqual(rows.slice(0, 10), [
    { key: 'trigger', label: '触发条件', value: '排名 4–20 且展示 ≥ 50。' },
    { key: 'baseline', label: '基线 / 阈值', value: '规则阈值：排名 4–20、展示 ≥ 50。' },
    { key: 'current', label: '当前观察', value: '当前位置 6.4，已有 420 次展示。' },
    { key: 'timeRange', label: '观察时间', value: '2026-08-29 → 2026-08-30' },
    { key: 'source', label: '数据来源', value: 'Google Search Console' },
    { key: 'freshness', label: '数据新鲜度', value: '2026-08-30' },
    { key: 'subject', label: '作用对象', value: '关键词 · https://example.com/landing' },
    { key: 'confidence', label: '置信度', value: '未声明（不推测）' },
    { key: 'whyPriority', label: '为什么这个优先级', value: 'P1：当前展示量 420 ≥ 200。' },
    { key: 'businessValueInfluence', label: '业务价值影响', value: '网站业务价值：高；影响跨站运营排序，本网站内机会仍按 P1 与证据排序；不改原始指标。' },
  ]);
  assert.equal(rows.some(row => /\d+(?:\.\d+)?\s*分/.test(row.value)), false);
});

test('Node and PHP Opportunity contracts preserve real observation windows and humanized explainability in parity', () => {
  for (const source of [nodeService, phpService]) {
    for (const key of ['firstSeenAt', 'lastSeenAt', 'trigger', 'baseline', 'current', 'source', 'freshness', 'subject', 'confidence', 'whyPriority', 'businessValueInfluence']) {
      assert.ok(source.includes(key), `missing explainability key ${key}`);
    }
    assert.ok(source.includes('未声明（不推测）'));
    assert.ok(source.includes('影响跨站运营排序'));
    assert.ok(source.includes('不改原始指标'));
  }
  assert.match(nodeService, /observedOn: latest\.observed_on/);
  assert.match(nodeService, /previousObservedOn: previous\?\.observed_on/);
  assert.match(nodeService, /row\.first_seen_at == null \? null : String\(row\.first_seen_at\)/);
  assert.match(phpService, /'observedOn' => isset\(\$latest\['observed_on'\]\)/);
  assert.match(phpService, /'firstSeenAt' => isset\(\$row\['first_seen_at'\]\)/);
});
'''
    marker = "\ntest('Opportunity surface renders the formatter through a collapsed evidence drawer with an explicit no-evidence state', () => {"
    assert marker in text
    assert 'Opportunity explainability exposes the RPD minimum' not in text
    return text.replace(marker, addition + marker, 1)


def write_product_files():
    transforms = {
        'src/server/product-optimization.ts': transform_node,
        'php/src/ProductOptimizationService.php': transform_php,
        'src/client/product-opportunity-evidence.ts': transform_ui,
        'tests/unit/product-opportunity-evidence-truth.test.ts': transform_test,
    }
    local = {}
    for path in EXPECTED_FILES:
        text = Path(path).read_text()
        local[path] = transforms[path](text)
    assert '未声明（不推测）' in local['src/server/product-optimization.ts']
    assert '影响跨站运营排序' in local['php/src/ProductOptimizationService.php']
    assert "add('whyPriority', '为什么这个优先级'" in local['src/client/product-opportunity-evidence.ts']
    print('P05_OPPORTUNITY_EXPLAINABILITY_CONSTRUCT=PASS')

    q = urllib.parse.quote(BRANCH, safe='')
    for path in EXPECTED_FILES:
        current = get(f'https://api.github.com/repos/{REPO}/contents/{path}?ref={q}')
        assert current['sha'] == EXPECTED_SHA[path], (path, current['sha'], EXPECTED_SHA[path])
        result = api('PUT', f'https://api.github.com/repos/{REPO}/contents/{path}', {
            'message': 'test(product): lock opportunity explainability contract' if path.startswith('tests/') else 'feat(product): add opportunity explainability contract',
            'content': base64.b64encode(local[path].encode()).decode(),
            'sha': current['sha'],
            'branch': BRANCH,
        })
        print('WRITE', path, result['commit']['sha'])


def remote_scope_readback():
    main = get(f'https://api.github.com/repos/{REPO}/branches/main')['commit']['sha']
    head = get(f'https://api.github.com/repos/{REPO}/branches/{urllib.parse.quote(BRANCH, safe="")}')['commit']['sha']
    assert main == BASE, (main, BASE)
    compare = get(f'https://api.github.com/repos/{REPO}/compare/{BASE}...{head}')
    assert compare['behind_by'] == 0, compare['behind_by']
    files = sorted(x['filename'] for x in compare['files'])
    assert files == sorted(EXPECTED_FILES), (files, EXPECTED_FILES)
    version = get(f'https://api.github.com/repos/{REPO}/contents/VERSION?ref={urllib.parse.quote(BRANCH, safe="")}')
    assert base64.b64decode(version['content']).decode().strip() == '1.2.4'
    tree = get(f'https://api.github.com/repos/{REPO}/git/commits/{head}')['tree']['sha']
    print('P05_OPPORTUNITY_EXPLAINABILITY_REMOTE_SCOPE=PASS')
    print('P05_OPPORTUNITY_EXPLAINABILITY_HEAD=' + head)
    print('P05_OPPORTUNITY_EXPLAINABILITY_TREE=' + tree)


if __name__ == '__main__':
    assert_exact_base()
    write_product_files()
    remote_scope_readback()
