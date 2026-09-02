from pathlib import Path

root = Path('product')
cover = root / 'src/app/ResourceCoverCache.php'
js = root / 'src/assets/workspace.js'

text = cover.read_text(encoding='utf-8')
old_fetch = """        try {\n            $page = $this->fetchFollowing($url, $pageMaxBytes, 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.1');\n            $type = strtolower((string)($page['contentType'] ?? ''));\n            if ($type === '' || str_contains($type, 'html')) {\n                foreach (self::extractCoverCandidates((string)$page['body'], (string)$page['url']) as $candidate) $candidates[] = $candidate;\n            }\n        } catch (Throwable $ignored) {}\n"""
new_fetch = """        foreach (self::metadataPageUrls($url, $provider) as $pageUrl) {\n            try {\n                $page = $this->fetchFollowing($pageUrl, $pageMaxBytes, 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.1');\n                $type = strtolower((string)($page['contentType'] ?? ''));\n                if ($type === '' || str_contains($type, 'html')) {\n                    foreach (self::extractCoverCandidates((string)$page['body'], (string)$page['url']) as $candidate) $candidates[] = $candidate;\n                }\n            } catch (Throwable $ignored) {}\n            if ($candidates !== []) break;\n        }\n"""
if old_fetch not in text:
    raise SystemExit('cover fetch block not found')
text = text.replace(old_fetch, new_fetch, 1)

anchor = """    private function directCandidates(string $url): array\n    {\n"""
helper = """    private static function metadataPageUrls(string $url, array $provider): array\n    {\n        $urls = [$url];\n        if ((string)($provider['code'] ?? '') !== 'iyf') return $urls;\n\n        $parts = parse_url($url);\n        if (!is_array($parts)) return $urls;\n        $host = strtolower((string)($parts['host'] ?? ''));\n        $path = (string)($parts['path'] ?? '');\n        if ($host !== 'mview.iyf.tv' || preg_match('#^/play/[A-Za-z0-9_-]+/?$#', $path) !== 1) return $urls;\n\n        $desktop = 'https://www.iyf.tv' . $path;\n        $query = (string)($parts['query'] ?? '');\n        if ($query !== '') $desktop .= '?' . $query;\n        array_unshift($urls, $desktop);\n        return array_values(array_unique($urls));\n    }\n\n"""
if anchor not in text:
    raise SystemExit('directCandidates anchor not found')
text = text.replace(anchor, helper + anchor, 1)
cover.write_text(text, encoding='utf-8')

jstext = js.read_text(encoding='utf-8')
old_key = "const coverRetryKey=(id)=>`vf-cover-retry:v2:${id}`;"
new_key = "const coverRetryKey=(id)=>`vf-cover-retry:v3:${id}`;"
if old_key not in jstext:
    raise SystemExit('cover retry v2 key not found')
js.write_text(jstext.replace(old_key, new_key, 1), encoding='utf-8')
