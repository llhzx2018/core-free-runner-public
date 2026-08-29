#!/usr/bin/env bash
set -Eeuo pipefail
: "${EXPECTED_SOURCE:?}"
: "${PRODUCT_BRANCH:?}"
test "$(git -C product rev-parse HEAD)" = "$EXPECTED_SOURCE"
python3 - <<'PY'
from pathlib import Path
p=Path('product/src/app/FunctionalHome.php')
s=p.read_text(encoding='utf-8')
anchor="function vf_home_operation_view(array $entry, array $assetTitles, array $categoryTitles): array\n{\n"
helper="""function vf_home_relative_age(string $createdAt, ?int $now = null): string
{
    $createdAt = trim($createdAt);
    if ($createdAt === '') return '时间未知';
    try { $created = (new DateTimeImmutable($createdAt))->getTimestamp(); }
    catch (Throwable $ignored) { return '时间未知'; }
    $current = $now ?? time();
    $seconds = max(0, $current - $created);
    if ($seconds < 60) return '刚刚';
    if ($seconds < 3600) return (int)floor($seconds / 60) . ' 分钟前';
    if ($seconds < 86400) return (int)floor($seconds / 3600) . ' 小时前';
    return (int)floor($seconds / 86400) . ' 天前';
}

"""
if s.count(anchor)!=1: raise SystemExit('activity time helper anchor drift')
s=s.replace(anchor,helper+anchor,1)
old="""    return [
        'action' => $actionLabel,
        'object' => $object,
        'success' => $result === '' || $result === 'success',
    ];
"""
new="""    return [
        'action' => $actionLabel,
        'object' => $object,
        'success' => $result === '' || $result === 'success',
        'age' => vf_home_relative_age((string)($entry['created_at'] ?? '')),
    ];
"""
if s.count(old)!=1: raise SystemExit('activity time view anchor drift')
s=s.replace(old,new,1)
old_markup="              <i><?= $view['success'] ? '完成' : '失败' ?></i>"
new_markup="              <i><?=vf_fw_h($view['success'] ? (string)$view['age'] : ('失败 · ' . (string)$view['age']))?></i>"
if s.count(old_markup)!=1: raise SystemExit('activity time markup anchor drift')
s=s.replace(old_markup,new_markup,1)
p.write_text(s,encoding='utf-8')
PY
php -l product/src/app/FunctionalHome.php
test "$(git -C product diff --name-only | tr '\n' ' ')" = "src/app/FunctionalHome.php "
git -C product diff --check
test "$(tr -d '\r\n' < product/src/VERSION.txt)" = "2.31.0"
git -C product config user.name VictorForge
git -C product config user.email llhzx2018@gmail.com
git -C product add src/app/FunctionalHome.php
git -C product commit -m "refine(P01): show relative time for Home activity"
git -C product push origin "HEAD:${PRODUCT_BRANCH}"
echo "NEW_SOURCE=$(git -C product rev-parse HEAD)"
echo "NEW_TREE=$(git -C product rev-parse HEAD^{tree})"
echo "VERSION=$(tr -d '\r\n' < product/src/VERSION.txt)"
echo "OWNER_PRODUCTION_WRITE=NO"
echo "RELEASE=NO"
