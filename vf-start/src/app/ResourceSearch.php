<?php
declare(strict_types=1);

final class VfResourceSearch
{
    private const SURFACE_LABELS = [
        'start' => '导航',
        'channels' => '频道',
        'watch' => '影视',
        'topics' => '专题',
        'books' => '课程',
        'projects' => '项目',
    ];

    public static function isPrivate(array $asset): bool
    {
        if (array_key_exists('effective_private', $asset)) return (int)$asset['effective_private'] === 1;
        if (array_key_exists('category_private', $asset) && (int)$asset['category_private'] === 1) return true;
        return (int)($asset['is_private'] ?? 0) === 1;
    }

    public static function matches(array $asset, string $needle): bool
    {
        if ($needle === '') return false;
        $haystack = mb_strtolower(
            (string)($asset['title'] ?? '') . ' ' .
            (string)($asset['url'] ?? '') . ' ' .
            (string)($asset['description'] ?? '') . ' ' .
            (string)($asset['category_name'] ?? '') . ' ' .
            (string)($asset['resource_kind'] ?? '') . ' ' .
            (string)($asset['provider_label'] ?? '') . ' ' .
            implode(' ', array_map('strval', (array)($asset['tags'] ?? []))),
            'UTF-8'
        );
        return mb_strpos($haystack, $needle, 0, 'UTF-8') !== false;
    }

    public static function score(array $asset, string $needle): int
    {
        $title = mb_strtolower(trim((string)($asset['title'] ?? '')), 'UTF-8');
        $url = mb_strtolower((string)($asset['url'] ?? ''), 'UTF-8');
        $category = mb_strtolower((string)($asset['category_name'] ?? ''), 'UTF-8');
        $description = mb_strtolower((string)($asset['description'] ?? ''), 'UTF-8');
        $provider = mb_strtolower((string)($asset['provider_label'] ?? ''), 'UTF-8');
        $kind = mb_strtolower((string)($asset['resource_kind'] ?? ''), 'UTF-8');
        $tags = array_map(static fn($tag): string => mb_strtolower(trim((string)$tag), 'UTF-8'), (array)($asset['tags'] ?? []));

        // Quick-open is an intent launcher, not a full-text report. Title intent
        // therefore defines the ranking tier; secondary fields only refine ties.
        $points = 0;
        if ($title === $needle) $points += 10000;
        elseif (str_starts_with($title, $needle)) $points += 8000;
        elseif (mb_strpos($title, $needle, 0, 'UTF-8') !== false) $points += 6000;
        if (in_array($needle, $tags, true)) $points += 500;
        elseif ($tags && mb_strpos(implode(' ', $tags), $needle, 0, 'UTF-8') !== false) $points += 220;
        if (mb_strpos($url, $needle, 0, 'UTF-8') !== false) $points += 300;
        if (mb_strpos($category, $needle, 0, 'UTF-8') !== false) $points += 240;
        if (mb_strpos($provider, $needle, 0, 'UTF-8') !== false) $points += 160;
        if (mb_strpos($kind, $needle, 0, 'UTF-8') !== false) $points += 140;
        if (mb_strpos($description, $needle, 0, 'UTF-8') !== false) $points += 80;
        return $points;
    }

    /** @return array<int,array<string,mixed>> */
    public static function search(array $assets, string $query, int $limit = 8): array
    {
        $needle = mb_strtolower(trim($query), 'UTF-8');
        if ($needle === '') return [];
        $ranked = [];
        foreach ($assets as $asset) {
            if (!is_array($asset) || !self::matches($asset, $needle)) continue;
            $asset['_vf_search_score'] = self::score($asset, $needle);
            $ranked[] = $asset;
        }
        usort($ranked, static function(array $a, array $b): int {
            $score = (int)($b['_vf_search_score'] ?? 0) <=> (int)($a['_vf_search_score'] ?? 0);
            if ($score !== 0) return $score;
            $order = (int)($a['sort_order'] ?? 0) <=> (int)($b['sort_order'] ?? 0);
            if ($order !== 0) return $order;
            return strnatcasecmp((string)($a['title'] ?? ''), (string)($b['title'] ?? ''));
        });
        if ($limit > 0) $ranked = array_slice($ranked, 0, $limit);
        foreach ($ranked as &$asset) unset($asset['_vf_search_score']);
        unset($asset);
        return array_values($ranked);
    }

    public static function present(array $asset, bool $admin): ?array
    {
        $id = (int)($asset['id'] ?? 0);
        if ($id <= 0) return null;
        $surface = strtolower(trim((string)($asset['surface'] ?? 'start')));
        if (!isset(self::SURFACE_LABELS[$surface])) $surface = 'start';
        $hosted = $surface === 'topics'
            && (string)($asset['source_kind'] ?? '') === 'hosted_html'
            && trim((string)($asset['html_url'] ?? '')) !== '';
        $direct = $hosted ? trim((string)$asset['html_url']) : trim((string)($asset['url'] ?? ''));
        if ($direct === '') return null;

        $context = $surface === 'start'
            ? trim((string)($asset['category_name'] ?? ''))
            : trim((string)($asset['resource_kind'] ?? ''));
        $provider = trim((string)($asset['provider_label'] ?? ''));
        if ($context === '' && $provider !== '') $context = $provider;

        return [
            'id' => $id,
            'title' => trim((string)($asset['title'] ?? '')) ?: $direct,
            'surface' => $surface,
            'surface_label' => self::SURFACE_LABELS[$surface],
            'context' => $context,
            'private' => self::isPrivate($asset),
            'open_url' => $admin ? 'surface-open.php?id=' . $id : $direct,
        ];
    }
}
