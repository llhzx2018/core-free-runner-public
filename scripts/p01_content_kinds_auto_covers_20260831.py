from pathlib import Path

ROOT = Path('product')

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

def write(path, content):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding='utf-8')

def replace_once(path, old, new):
    text = read(path)
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected exactly one match, got {text.count(old)} for {old[:90]!r}')
    write(path, text.replace(old, new, 1))

metadata = r'''<?php
declare(strict_types=1);

final class VfResourceMetadata
{
    public static function provider(string $url): array
    {
        $host = strtolower(trim((string)(parse_url($url, PHP_URL_HOST) ?: '')));
        $host = preg_replace('/^www\./', '', $host) ?: $host;
        $providers = [
            ['youtube.com', 'youtube', 'YouTube'],
            ['youtu.be', 'youtube', 'YouTube'],
            ['bilibili.com', 'bilibili', '哔哩哔哩'],
            ['b23.tv', 'bilibili', '哔哩哔哩'],
            ['twitch.tv', 'twitch', 'Twitch'],
            ['spotify.com', 'spotify', 'Spotify'],
            ['podcasts.apple.com', 'apple-podcasts', 'Apple Podcasts'],
            ['iqiyi.com', 'iqiyi', '爱奇艺'],
            ['v.qq.com', 'tencent-video', '腾讯视频'],
            ['youku.com', 'youku', '优酷'],
            ['mgtv.com', 'mgtv', '芒果TV'],
            ['netflix.com', 'netflix', 'Netflix'],
            ['iyf.tv', 'iyf', '爱一帆'],
        ];
        foreach ($providers as [$domain, $code, $label]) {
            if ($host === $domain || str_ends_with($host, '.' . $domain)) {
                return ['code'=>$code, 'label'=>$label, 'host'=>$host];
            }
        }
        if ($host === '') return ['code'=>'other', 'label'=>'其他来源', 'host'=>''];
        $code = preg_replace('/[^a-z0-9.-]+/', '-', $host) ?: 'other';
        return ['code'=>$code, 'label'=>$host, 'host'=>$host];
    }

    public static function normalizeKind(string $surface, string $kind, string $url = '', string $title = '', array $tags = []): string
    {
        $surface = strtolower(trim($surface));
        $raw = trim($kind);
        $key = mb_strtolower($raw, 'UTF-8');
        $haystack = mb_strtolower(trim($title . ' ' . implode(' ', array_map('strval', $tags))), 'UTF-8');

        if ($surface === 'channels') {
            if (preg_match('/播客|podcast/u', $key . ' ' . $haystack)) return '播客';
            $platformKinds = ['youtube','youtube频道','youtuber','bilibili','哔哩哔哩','b站','twitch','spotify'];
            if ($raw === '' || in_array($key, $platformKinds, true) || in_array($key, ['channel','creator','创作者'], true)) return '频道';
            return $raw;
        }
        if ($surface === 'watch') {
            $map = [
                'movie'=>'电影','film'=>'电影','电影'=>'电影','影视'=>'电影',
                'series'=>'剧集','tv'=>'剧集','电视剧'=>'剧集','剧集'=>'剧集',
                'documentary'=>'纪录片','纪录片'=>'纪录片',
                'variety'=>'综艺','综艺'=>'综艺',
                'anime'=>'动漫','animation'=>'动漫','动画'=>'动漫','动漫'=>'动漫',
            ];
            if (isset($map[$key])) return $map[$key];
            if ($raw === '') {
                if (preg_match('/纪录片/u', $haystack)) return '纪录片';
                if (preg_match('/电视剧|剧集/u', $haystack)) return '剧集';
                if (preg_match('/动画|动漫/u', $haystack)) return '动漫';
                if (preg_match('/综艺/u', $haystack)) return '综艺';
                return '电影';
            }
            return $raw;
        }
        return $raw;
    }
}
'''
write('src/app/ResourceMetadata.php', metadata)

cover_cache = r'''<?php
declare(strict_types=1);
require_once __DIR__ . '/ResourceMetadata.php';
require_once __DIR__ . '/ResourceAssetStore.php';

final class VfResourceCoverCache
{
    private PDO $db;
    private $fetcher;

    public function __construct(PDO $db, ?callable $fetcher = null)
    {
        $this->db = $db;
        $this->fetcher = $fetcher;
    }

    public function refreshIds(array $ids, int $limit = 2): array
    {
        $ids = array_values(array_unique(array_filter(array_map('intval', $ids), static fn(int $id): bool => $id > 0)));
        $ids = array_slice($ids, 0, max(1, min(4, $limit)));
        $results = [];
        foreach ($ids as $id) {
            try { $results[] = $this->refreshOne($id, false); }
            catch (Throwable $e) { $results[] = ['id'=>$id,'success'=>false,'error'=>$e->getMessage()]; }
        }
        return ['processed'=>count($results), 'results'=>$results];
    }

    public function refreshOne(int $linkId, bool $force = false): array
    {
        $stmt = $this->db->prepare("SELECT l.id,l.url,l.lifecycle_state,l.is_pending,l.sensitive_detected,l.url_protected,p.domain_key FROM links l JOIN resource_domain_profiles p ON p.link_id=l.id WHERE l.id=?");
        $stmt->execute([max(1, $linkId)]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        if (!$row || (string)$row['lifecycle_state'] !== 'active') throw new RuntimeException('资源不存在或已归档。');
        $surface = (string)$row['domain_key'];
        if (!in_array($surface, ['channels','watch'], true)) throw new RuntimeException('只有频道与影视资源需要自动封面。');
        if ((int)$row['is_pending'] === 1 || (int)$row['sensitive_detected'] === 1 || (int)$row['url_protected'] === 1) {
            throw new RuntimeException('待整理、敏感或受保护资源不会向远端请求封面。');
        }
        $url = vf_validate_url((string)$row['url']);
        $signature = substr(hash('sha256', $url), 0, 20);
        $provider = VfResourceMetadata::provider($url);
        $existing = $this->coverRow($linkId);
        if ($existing && $this->coverFileExists($existing)) {
            $original = (string)($existing['original_name'] ?? '');
            $automatic = str_starts_with($original, 'auto:');
            if (!$automatic && !$force) return $this->successFromRow($linkId, $existing, true, 'manual');
            if (!$force && str_starts_with($original, 'auto:' . $signature . ':')) return $this->successFromRow($linkId, $existing, true, 'auto');
        }

        $candidates = $this->directCandidates($url);
        try {
            $page = $this->fetchFollowing($url, 524288, 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.1');
            $type = strtolower((string)($page['contentType'] ?? ''));
            if ($type === '' || str_contains($type, 'html')) {
                foreach (self::extractCoverCandidates((string)$page['body'], (string)$page['url']) as $candidate) $candidates[] = $candidate;
            }
        } catch (Throwable $ignored) {}
        $candidates = array_values(array_unique(array_filter($candidates, static fn($x): bool => is_string($x) && $x !== '')));
        $errors = [];
        foreach (array_slice($candidates, 0, 6) as $candidate) {
            try {
                $response = $this->fetchFollowing($candidate, 2 * 1024 * 1024, 'image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.1');
                $image = $this->validateImage((string)$response['body'], (string)($response['contentType'] ?? ''));
                $saved = $this->saveImage($linkId, $signature, (string)$provider['code'], $image);
                return ['id'=>$linkId,'success'=>true,'cached'=>false,'source'=>(string)$response['url'],'provider'=>(string)$provider['code'],'providerLabel'=>(string)$provider['label'],'cover'=>$saved];
            } catch (Throwable $e) { $errors[] = $e->getMessage(); }
        }
        $message = $errors ? implode('；', array_slice(array_values(array_unique($errors)), 0, 3)) : '页面没有提供可用的封面图片。';
        return ['id'=>$linkId,'success'=>false,'provider'=>(string)$provider['code'],'providerLabel'=>(string)$provider['label'],'error'=>$message];
    }

    public static function extractCoverCandidates(string $html, string $baseUrl): array
    {
        $ranked = [];
        if (preg_match_all('/<(meta|link)\b[^>]*>/i', $html, $matches)) {
            foreach ($matches[0] as $tag) {
                $attrs = self::attributes($tag);
                $property = strtolower(trim((string)($attrs['property'] ?? $attrs['name'] ?? '')));
                $rel = strtolower(trim((string)($attrs['rel'] ?? '')));
                $value = trim((string)($attrs['content'] ?? $attrs['href'] ?? ''));
                if ($value === '') continue;
                $score = 0;
                if ($property === 'og:image:secure_url') $score = 1100;
                elseif ($property === 'og:image') $score = 1050;
                elseif ($property === 'twitter:image' || $property === 'twitter:image:src') $score = 950;
                elseif (str_contains($rel, 'image_src')) $score = 850;
                if ($score <= 0) continue;
                $resolved = self::resolveUrl($baseUrl, $value);
                if ($resolved !== '') $ranked[] = ['url'=>$resolved,'score'=>$score];
            }
        }
        usort($ranked, static fn(array $a, array $b): int => $b['score'] <=> $a['score']);
        return array_values(array_unique(array_map(static fn(array $x): string => (string)$x['url'], $ranked)));
    }

    private static function attributes(string $tag): array
    {
        $attrs = [];
        if (preg_match_all('/([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))/u', $tag, $pairs, PREG_SET_ORDER)) {
            foreach ($pairs as $pair) {
                $attrs[strtolower((string)$pair[1])] = html_entity_decode((string)($pair[2] !== '' ? $pair[2] : ($pair[3] !== '' ? $pair[3] : $pair[4])), ENT_QUOTES | ENT_HTML5, 'UTF-8');
            }
        }
        return $attrs;
    }

    private function directCandidates(string $url): array
    {
        $provider = VfResourceMetadata::provider($url);
        if ((string)$provider['code'] !== 'youtube') return [];
        $parts = parse_url($url);
        $host = strtolower((string)($parts['host'] ?? ''));
        $path = (string)($parts['path'] ?? '');
        $id = '';
        if ($host === 'youtu.be' || str_ends_with($host, '.youtu.be')) $id = trim($path, '/');
        if ($id === '' && preg_match('#^/(shorts|embed)/([A-Za-z0-9_-]{6,})#', $path, $m)) $id = $m[2];
        if ($id === '') {
            parse_str((string)($parts['query'] ?? ''), $query);
            $id = preg_match('/^[A-Za-z0-9_-]{6,}$/', (string)($query['v'] ?? '')) ? (string)$query['v'] : '';
        }
        return $id !== '' ? ['https://i.ytimg.com/vi/' . rawurlencode($id) . '/hqdefault.jpg'] : [];
    }

    public static function resolveUrl(string $base, string $relative): string
    {
        $relative = trim(html_entity_decode($relative, ENT_QUOTES | ENT_HTML5, 'UTF-8'));
        if ($relative === '' || str_starts_with(strtolower($relative), 'data:') || str_starts_with(strtolower($relative), 'javascript:')) return '';
        if (preg_match('#^https?://#i', $relative)) return $relative;
        $parts = parse_url($base);
        if (!is_array($parts) || empty($parts['scheme']) || empty($parts['host'])) return '';
        $origin = strtolower((string)$parts['scheme']) . '://' . (string)$parts['host'];
        if (isset($parts['port'])) $origin .= ':' . (int)$parts['port'];
        if (str_starts_with($relative, '//')) return strtolower((string)$parts['scheme']) . ':' . $relative;
        if (str_starts_with($relative, '/')) return $origin . self::normalizePath($relative);
        $path = (string)($parts['path'] ?? '/');
        $dir = str_ends_with($path, '/') ? $path : dirname($path) . '/';
        return $origin . self::normalizePath($dir . $relative);
    }

    private static function normalizePath(string $path): string
    {
        $suffix = '';
        $hash = strpos($path, '#'); if ($hash !== false) { $suffix = substr($path, $hash) . $suffix; $path = substr($path, 0, $hash); }
        $query = strpos($path, '?'); if ($query !== false) { $suffix = substr($path, $query) . $suffix; $path = substr($path, 0, $query); }
        $segments = [];
        foreach (explode('/', $path) as $segment) {
            if ($segment === '' || $segment === '.') continue;
            if ($segment === '..') { array_pop($segments); continue; }
            $segments[] = $segment;
        }
        return '/' . implode('/', $segments) . $suffix;
    }

    private function fetchFollowing(string $url, int $maxBytes, string $accept): array
    {
        $current = $url;
        for ($redirects = 0; $redirects <= 3; $redirects++) {
            if ($this->fetcher !== null) {
                $safeUrl = vf_validate_url($current);
                $response = ($this->fetcher)($safeUrl, $maxBytes, $accept);
                if (!is_array($response)) throw new RuntimeException('封面测试抓取器返回无效结果。');
                $body = (string)($response['body'] ?? '');
                if (strlen($body) > $maxBytes) throw new RuntimeException('远程响应体超过大小限制。');
                $response += ['status'=>200,'location'=>'','contentType'=>'','body'=>$body];
                $response['url'] = (string)($response['url'] ?? $safeUrl);
            } else {
                $safe = vf_safe_remote_url($current, '封面地址');
                if (!function_exists('curl_init')) throw new RuntimeException('服务器未启用 cURL，自动封面抓取已安全停止。');
                $response = $this->fetchCurl((string)$safe['url'], (string)$safe['resolve'], $maxBytes, $accept);
                $response['url'] = (string)$safe['url'];
            }
            $status = (int)($response['status'] ?? 0);
            if ($status >= 300 && $status < 400 && !empty($response['location'])) {
                if ($redirects >= 3) throw new RuntimeException('封面地址跳转次数过多。');
                $current = self::resolveUrl((string)$response['url'], (string)$response['location']);
                if ($current === '') throw new RuntimeException('封面跳转地址无效。');
                continue;
            }
            if ($status < 200 || $status >= 300) throw new RuntimeException('远程响应 HTTP ' . $status . '。');
            return $response;
        }
        throw new RuntimeException('封面地址跳转失败。');
    }

    private function fetchCurl(string $url, string $resolve, int $maxBytes, string $accept): array
    {
        $headers = [];
        $body = '';
        $overflow = false;
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 3);
        curl_setopt($ch, CURLOPT_TIMEOUT, 7);
        curl_setopt($ch, CURLOPT_USERAGENT, 'VF-Start/' . VF_VERSION . ' CoverCache');
        curl_setopt($ch, CURLOPT_HTTPHEADER, ['Accept: ' . $accept, 'Accept-Language: zh-CN,zh;q=0.8,en;q=0.5']);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 2);
        curl_setopt($ch, CURLOPT_ENCODING, '');
        if ($resolve !== '') curl_setopt($ch, CURLOPT_RESOLVE, [$resolve]);
        curl_setopt($ch, CURLOPT_HEADERFUNCTION, static function ($handle, string $line) use (&$headers): int {
            $trim = trim($line);
            if ($trim !== '' && str_contains($trim, ':')) {
                [$name,$value] = explode(':', $trim, 2);
                $headers[strtolower(trim($name))] = trim($value);
            }
            return strlen($line);
        });
        curl_setopt($ch, CURLOPT_WRITEFUNCTION, static function ($handle, string $chunk) use (&$body, &$overflow, $maxBytes): int {
            if (strlen($body) + strlen($chunk) > $maxBytes) { $overflow = true; return 0; }
            $body .= $chunk;
            return strlen($chunk);
        });
        $ok = curl_exec($ch);
        $status = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $error = curl_error($ch);
        curl_close($ch);
        if ($ok === false) {
            if ($overflow) throw new RuntimeException('远程响应体超过大小限制。');
            throw new RuntimeException('远程请求失败：' . ($error !== '' ? $error : '未知错误'));
        }
        return ['status'=>$status,'location'=>(string)($headers['location'] ?? ''),'contentType'=>(string)($headers['content-type'] ?? ''),'body'=>$body];
    }

    private function validateImage(string $bytes, string $reportedType): array
    {
        $length = strlen($bytes);
        if ($length < 64 || $length > 2 * 1024 * 1024) throw new RuntimeException('封面大小必须在 64 B–2 MB 之间。');
        $mime = '';
        if (class_exists('finfo')) { $finfo = new finfo(FILEINFO_MIME_TYPE); $mime = strtolower((string)$finfo->buffer($bytes)); }
        if ($mime === '' || $mime === 'application/octet-stream') $mime = strtolower(trim(explode(';', $reportedType)[0]));
        if (substr($bytes, 0, 8) === "\x89PNG\r\n\x1a\n") $mime = 'image/png';
        elseif (substr($bytes, 0, 3) === "\xff\xd8\xff") $mime = 'image/jpeg';
        elseif (substr($bytes, 0, 4) === 'RIFF' && substr($bytes, 8, 4) === 'WEBP') $mime = 'image/webp';
        $exts = ['image/png'=>'png','image/jpeg'=>'jpg','image/webp'=>'webp'];
        if (!isset($exts[$mime])) throw new RuntimeException('自动封面仅接受 PNG、JPG、WebP。');
        $info = @getimagesizefromstring($bytes);
        if (!is_array($info)) throw new RuntimeException('封面图片内容损坏。');
        $width=(int)$info[0];$height=(int)$info[1];
        if ($width < 32 || $height < 32 || $width > 4096 || $height > 4096) throw new RuntimeException('封面尺寸不在允许范围。');
        return ['bytes'=>$bytes,'mime'=>$mime,'ext'=>$exts[$mime],'width'=>$width,'height'=>$height];
    }

    private function saveImage(int $linkId, string $signature, string $provider, array $image): array
    {
        $dir = rtrim(VF_PRIVATE_ROOT, '/\\') . '/resource-assets/covers';
        if (!is_dir($dir) && !@mkdir($dir, 0750, true) && !is_dir($dir)) throw new RuntimeException('无法创建封面缓存目录。');
        @chmod($dir, 0750);
        if (function_exists('vf_write_storage_guards')) vf_write_storage_guards($dir);
        $hash = hash('sha256', (string)$image['bytes']);
        $file = 'cover-' . $linkId . '-' . substr($hash, 0, 20) . '.' . (string)$image['ext'];
        $target = $dir . '/' . $file;
        $stage = $target . '.auto-' . bin2hex(random_bytes(4));
        vf_write_exact_file($stage, (string)$image['bytes'], 0640);
        @chmod($stage, 0640);
        if (!@rename($stage, $target)) { @unlink($stage); throw new RuntimeException('自动封面启用失败。'); }
        $old = $this->coverRow($linkId);
        $now = gmdate('c');
        $stmt = $this->db->prepare("INSERT INTO resource_asset_files(link_id,asset_kind,file_name,original_name,mime_type,byte_size,width,height,file_hash,created_at,updated_at) VALUES(?,'cover',?,?,?,?,?,?,?,?,?) ON CONFLICT(link_id,asset_kind) DO UPDATE SET file_name=excluded.file_name,original_name=excluded.original_name,mime_type=excluded.mime_type,byte_size=excluded.byte_size,width=excluded.width,height=excluded.height,file_hash=excluded.file_hash,updated_at=excluded.updated_at");
        try {
            $stmt->execute([$linkId,$file,'auto:'.$signature.':'.$provider,(string)$image['mime'],strlen((string)$image['bytes']),(int)$image['width'],(int)$image['height'],$hash,$now,$now]);
        } catch (Throwable $e) { @unlink($target); throw $e; }
        if (is_array($old)) {
            $oldFile = basename((string)($old['file_name'] ?? ''));
            if ($oldFile !== '' && $oldFile !== $file) @unlink($dir . '/' . $oldFile);
        }
        return ['url'=>'/resource-cover.php?id='.$linkId.'&v='.rawurlencode(substr($hash,0,16)),'mime'=>(string)$image['mime'],'bytes'=>strlen((string)$image['bytes']),'width'=>(int)$image['width'],'height'=>(int)$image['height'],'hash'=>$hash,'automatic'=>true];
    }

    private function coverRow(int $linkId): ?array
    {
        $stmt=$this->db->prepare("SELECT * FROM resource_asset_files WHERE link_id=? AND asset_kind='cover'");
        $stmt->execute([$linkId]);
        $row=$stmt->fetch(PDO::FETCH_ASSOC);
        return $row ?: null;
    }

    private function coverFileExists(array $row): bool
    {
        $file=basename((string)($row['file_name']??''));
        return $file!=='' && is_file(rtrim(VF_PRIVATE_ROOT,'/\\').'/resource-assets/covers/'.$file);
    }

    private function successFromRow(int $linkId, array $row, bool $cached, string $source): array
    {
        $hash=(string)($row['file_hash']??'');
        return ['id'=>$linkId,'success'=>true,'cached'=>$cached,'source'=>$source,'cover'=>['url'=>'/resource-cover.php?id='.$linkId.'&v='.rawurlencode(substr($hash,0,16)),'mime'=>(string)($row['mime_type']??''),'bytes'=>(int)($row['byte_size']??0),'width'=>(int)($row['width']??0),'height'=>(int)($row['height']??0),'hash'=>$hash,'automatic'=>str_starts_with((string)($row['original_name']??''),'auto:')]];
    }
}
'''
write('src/app/ResourceCoverCache.php', cover_cache)

endpoint = r'''<?php
declare(strict_types=1);
require_once __DIR__ . '/app/bootstrap.php';
require_once __DIR__ . '/app/ResourceCoverCache.php';

if (!vf_is_installed()) { http_response_code(503); exit; }
vf_security_headers(true);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Robots-Tag: noindex, nofollow, noarchive');

function vf_cover_refresh_reply(array $payload, int $status = 200): never
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

if (!vf_is_admin()) vf_cover_refresh_reply(['ok'=>false,'error'=>'需要管理员登录。'], 403);
if (strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET')) !== 'POST') vf_cover_refresh_reply(['ok'=>false,'error'=>'仅支持 POST。'], 405);
$csrf = (string)($_POST['csrf'] ?? '');
if ($csrf === '' || !hash_equals(vf_csrf_token(), $csrf)) vf_cover_refresh_reply(['ok'=>false,'error'=>'CSRF 校验失败，请刷新后重试。'], 403);
$ids = json_decode((string)($_POST['ids'] ?? '[]'), true);
if (!is_array($ids)) $ids = [];
if (isset($_POST['id'])) $ids[] = (int)$_POST['id'];
$ids = array_values(array_unique(array_filter(array_map('intval', $ids), static fn(int $id): bool => $id > 0)));
if (!$ids) vf_cover_refresh_reply(['ok'=>true,'processed'=>0,'results'=>[]]);
$result = (new VfResourceCoverCache(vf_db()))->refreshIds($ids, 2);
vf_cover_refresh_reply(['ok'=>true] + $result);
'''
write('src/resource-cover-refresh.php', endpoint)

# SurfaceRepository: separate semantic kind from provider and normalize legacy platform-as-kind values.
replace_once('src/app/SurfaceRepository.php',
"require_once __DIR__ . '/ResourceAssetStore.php';",
"require_once __DIR__ . '/ResourceAssetStore.php';\nrequire_once __DIR__ . '/ResourceMetadata.php';")
replace_once('src/app/SurfaceRepository.php',
"            $link['resource_kind'] = $profile ? (string)$profile['resource_kind'] : '';",
"            $rawKind = $profile ? (string)$profile['resource_kind'] : '';\n            $link['resource_kind'] = VfResourceMetadata::normalizeKind($surface, $rawKind, (string)($link['url'] ?? ''), (string)($link['title'] ?? ''), (array)($link['tags'] ?? []));\n            $provider = $surface === 'start' ? ['code'=>'','label'=>''] : VfResourceMetadata::provider((string)($link['url'] ?? ''));\n            $link['provider'] = (string)$provider['code'];\n            $link['provider_label'] = (string)$provider['label'];")
replace_once('src/app/SurfaceRepository.php', "                    $kind = 'YouTube';", "                    $kind = '频道';")
replace_once('src/app/SurfaceRepository.php',
"        $check = $this->db->prepare(\"SELECT id FROM links WHERE id=? AND lifecycle_state='active'\");\n        $check->execute([$linkId]);\n        if (!$check->fetchColumn()) throw new RuntimeException('资源不存在或已归档。');",
"        $check = $this->db->prepare(\"SELECT id,url,title,tags FROM links WHERE id=? AND lifecycle_state='active'\");\n        $check->execute([$linkId]);\n        $link = $check->fetch(PDO::FETCH_ASSOC);\n        if (!$link) throw new RuntimeException('资源不存在或已归档。');")
replace_once('src/app/SurfaceRepository.php',
"        $kind = vf_clean_text((string)($data['resource_kind'] ?? ''), 80);",
"        $storedTags = json_decode((string)($link['tags'] ?? '[]'), true);\n        if (!is_array($storedTags)) $storedTags = [];\n        $kind = VfResourceMetadata::normalizeKind($surface, (string)($data['resource_kind'] ?? ''), (string)($link['url'] ?? ''), (string)($link['title'] ?? ''), $storedTags);\n        $kind = vf_clean_text($kind, 80);")

# Include provider in search so platform remains findable without becoming a classification.
replace_once('src/app/FunctionalWorkspace.php',
".(string)($asset['resource_kind']??'').' '.implode(' ',(array)($asset['tags']??[]))",
".(string)($asset['resource_kind']??'').' '.(string)($asset['provider_label']??'').' '.implode(' ',(array)($asset['tags']??[]))")

# SurfaceShell admin payload and copy: provider is metadata; cover is automatic-first.
replace_once('src/app/SurfaceShell.php',
"            'domain'=>$domain,\n            'description'=>(string)($asset['description'] ?? ''),",
"            'domain'=>$domain,\n            'provider'=>(string)($asset['provider'] ?? ''),\n            'provider_label'=>(string)($asset['provider_label'] ?? ''),\n            'description'=>(string)($asset['description'] ?? ''),")
replace_once('src/app/SurfaceShell.php',
"<span>封面 <small>可选 · 选择后自动压缩</small></span>",
"<span>封面 <small>自动获取 · 可手工覆盖</small></span>")
replace_once('src/app/SurfaceShell.php',
"<span>封面 <small>可上传新图替换</small></span>",
"<span>封面 <small>自动获取 · 可手工覆盖</small></span>")

# Functional rendering: platform is source metadata, not a kind/filter.
replace_once('src/app/FunctionalWorkspaceShell.php',
"    $surface=(string)($asset['surface']??'start');$domain=(string)(parse_url((string)$asset['url'],PHP_URL_HOST)?:'');$isFav=(int)($asset['is_favorite']??0)===1;$private=vf_fw_is_private($asset);$class=$surface==='start'?(string)($asset['category_name']??''):vf_fw_kind_display_label($surface,(string)($asset['resource_kind']??''));",
"    $surface=(string)($asset['surface']??'start');$domain=(string)(parse_url((string)$asset['url'],PHP_URL_HOST)?:'');$provider=trim((string)($asset['provider_label']??''));$source=$surface==='start'?$domain:($provider!==''?$provider:$domain);$isFav=(int)($asset['is_favorite']??0)===1;$private=vf_fw_is_private($asset);$class=$surface==='start'?(string)($asset['category_name']??''):vf_fw_kind_display_label($surface,(string)($asset['resource_kind']??''));")
replace_once('src/app/FunctionalWorkspaceShell.php',
"<small><?=vf_fw_h($domain)?><?php if($class!==''): ?> · <?=vf_fw_h($class)?><?php endif; ?></small>",
"<small><?=vf_fw_h($source)?><?php if($class!==''): ?> · <?=vf_fw_h($class)?><?php endif; ?></small>")
replace_once('src/app/FunctionalWorkspaceShell.php',
"    $isFav=(int)($asset['is_favorite']??0)===1;$private=vf_fw_is_private($asset);$mediaStatus=(string)($asset['media_status']??'');$labels=['want'=>'想看','watching'=>'在看','watched'=>'看过','favorite'=>'珍藏'];$visual=(string)($asset['cover_url']??'');if($visual==='')$visual=(string)($asset['icon_cache_url']??'');",
"    $isFav=(int)($asset['is_favorite']??0)===1;$private=vf_fw_is_private($asset);$mediaStatus=(string)($asset['media_status']??'');$provider=trim((string)($asset['provider_label']??''));$labels=['want'=>'想看','watching'=>'在看','watched'=>'看过','favorite'=>'珍藏'];$visual=(string)($asset['cover_url']??'');if($visual==='')$visual=(string)($asset['icon_cache_url']??'');")
replace_once('src/app/FunctionalWorkspaceShell.php',
"<?=vf_fw_h(vf_fw_kind_display_label('watch',(string)($asset['resource_kind']??'')) ?: '未分类')?></small>",
"<?=vf_fw_h(vf_fw_kind_display_label('watch',(string)($asset['resource_kind']??'')) ?: '电影')?><?php if($provider!==''): ?> · <?=vf_fw_h($provider)?><?php endif; ?></small>")

# workspace.js: clearer taxonomy and automatic visible-page cover hydration.
replace_once('src/assets/workspace.js',
"  const kindConfig=(surface)=>({channels:['频道分类','例如：旅行生活 / 科技 / 音乐'],watch:['内容类型','例如：电影 / 剧集 / 纪录片 / 综艺 / 动漫'],topics:['专题分类','例如：学习 / 赚钱 / AI / 工具']}[surface]||['主分类','输入主分类']);",
"  const kindConfig=(surface)=>({channels:['频道分类','例如：频道 / 播客；平台会自动识别'],watch:['内容类型','例如：电影 / 剧集 / 纪录片 / 综艺 / 动漫'],topics:['专题分类','例如：学习 / 赚钱 / AI / 工具']}[surface]||['主分类','输入主分类']);")
replace_once('src/assets/workspace.js',
"    const title=$('[data-detail-title]',drawer);if(title)title.textContent=a.title||'资源详情';const domain=$('[data-detail-domain]',drawer);if(domain)domain.textContent=a.source_kind==='hosted_html'?'托管 HTML':(a.domain||'');const open=$('[data-detail-open]',drawer);if(open)open.href=`surface-open.php?id=${a.id}`;",
"    const title=$('[data-detail-title]',drawer);if(title)title.textContent=a.title||'资源详情';const domain=$('[data-detail-domain]',drawer);if(domain)domain.textContent=a.source_kind==='hosted_html'?'托管 HTML':(a.provider_label||a.domain||'');const open=$('[data-detail-open]',drawer);if(open)open.href=`surface-open.php?id=${a.id}`;")
needle = "  const postMedia=async(body)=>{\n    body.set('csrf',state.csrf||'');\n    const r=await fetch('resource-media.php',{method:'POST',body,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}});\n    const json=await r.json().catch(()=>({ok:false,error:'资源附件服务返回了无效响应。'}));\n    if(!r.ok||!json.ok)throw new Error(json.error||'资源附件操作失败。');return json;\n  };"
auto = needle + r'''
  const coverRetryKey=(id)=>`vf-cover-retry:${id}`;
  const coverRetryBlocked=(id)=>{try{const t=Number(localStorage.getItem(coverRetryKey(id))||0);return t>0&&Date.now()-t<60*60*1000}catch(_){return false}};
  const markCoverRetry=(id,failed)=>{try{if(failed)localStorage.setItem(coverRetryKey(id),String(Date.now()));else localStorage.removeItem(coverRetryKey(id))}catch(_){}};
  const applyAutoCover=(id,url)=>{
    const a=state.assets[String(id)];if(a)a.cover_url=url||'';
    if(!url)return;
    document.querySelectorAll(`.vf-watch-poster[data-edit-id="${id}"],.vf-asset-icon[data-edit-id="${id}"]`).forEach(el=>{el.innerHTML=`<img src="${String(url).replace(/"/g,'&quot;')}" alt="" loading="lazy">`});
  };
  const refreshAutoCovers=async()=>{
    const ids=Object.values(state.assets||{}).filter(a=>['channels','watch'].includes(String(a.surface||''))&&!a.cover_url&&!coverRetryBlocked(a.id)).map(a=>Number(a.id)).filter(Boolean);
    for(let i=0;i<ids.length;i+=2){
      const batch=ids.slice(i,i+2),body=new FormData();body.set('csrf',state.csrf||'');body.set('ids',JSON.stringify(batch));
      try{
        const r=await fetch('resource-cover-refresh.php',{method:'POST',body,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}});const json=await r.json().catch(()=>({ok:false}));
        if(!r.ok||!json.ok)throw new Error(json.error||'自动封面抓取失败。');
        (json.results||[]).forEach(item=>{const id=Number(item.id||0),url=item?.cover?.url||'';markCoverRetry(id,!item.success);if(item.success&&url)applyAutoCover(id,url)});
      }catch(_){batch.forEach(id=>markCoverRetry(id,true))}
      await new Promise(resolve=>setTimeout(resolve,250));
    }
  };'''
replace_once('src/assets/workspace.js', needle, auto)
replace_once('src/assets/workspace.js',
"  updateBulk();\n})();",
"  updateBulk();\n  if(state.csrf)setTimeout(()=>{refreshAutoCovers().catch(()=>{})},700);\n})();")

print('P01 content-kind + automatic cover patch prepared')
