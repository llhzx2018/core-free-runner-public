<?php
declare(strict_types=1);

/**
 * Presentation-only views over existing canonical resources.
 *
 * These modes never create a storage domain and never own mutations:
 * - courses aliases the canonical books domain;
 * - tools/software derive read models from canonical Start links.
 */
final class VfWorkspaceViewCatalog
{
    public const PRIMARY_MODES = ['home', 'start', 'channels', 'watch', 'topics', 'courses', 'projects', 'tools', 'software'];

    private const TOOL_SCENES = [
        '做网站' => ['建站','cms','域名','whois','dns','开发工具','api','调试','测试','技术栈','网站分析','网页工具'],
        '上线 / 服务器' => ['部署','上线','服务器','主机','vps','ssh','cdn','nginx','运维','云主机'],
        'SEO / 竞品' => ['seo','关键词','竞品','外链','流量分析','search console','站长工具'],
        '图片 / 页面素材' => ['图片','图像','素材','截图','压缩图片','logo','icon','svg','png','webp','配色'],
        '视频下载 / M3U8' => ['视频下载','下载视频','m3u8','录屏','音视频下载','媒体下载'],
        '联盟投流 / 追踪' => ['联盟','offer','投流','追踪','tracker','spy','广告流量','广告与流量'],
        '代理 / 账号环境' => ['代理','账号环境','浏览器环境','指纹','住宅 ip','住宅ip','vpn','节点','网络与路由'],
        '内容生产' => ['内容生产','内容创作','写作工具','翻译工具','转录工具','文案工具','markdown 编辑','内容工具'],
    ];

    private const SOFTWARE_GROUPS = [
        '系统基础' => ['解压','压缩包','文件搜索','输入法','密码库','系统基础','windows 文件','启动器'],
        '浏览器扩展' => ['浏览器扩展','浏览器与扩展','chrome 扩展','firefox 扩展','插件'],
        '开发 / 编程' => ['代码编辑器','开发环境','ide','编程','api 调试','日志'],
        '服务器 / SSH' => ['ssh 客户端','服务器管理','远程终端','sftp','运维客户端','部署与运维','ssh','终端'],
        '文件 / 办公 / 知识' => ['办公','知识库','笔记','邮件客户端','本地 markdown','文件传输','云盘客户端'],
        '下载 / 影音' => ['下载器','播放器','录屏','音频编辑','视频编辑','影音软件'],
        '网络' => ['代理客户端','网络与路由','网络客户端','分流','测速客户端'],
        '远程 / 设备' => ['远程桌面','远程与设备','手机管理','设备管理','虚拟声卡'],
        '装机 / 救援' => ['装机','重装','启动盘','系统镜像','救援','pe 系统','iso 启动'],
    ];

    private const DERIVED_VIEW_EXCLUSIONS = [
        '影视网站','成人','课程与资料','学习与社区','社区与学习','频道','专题','电影','剧集',
        '教程','指南','学习路线','回放','直播','节目','插件推荐',
    ];

    private const SOFTWARE_SIGNALS = [
        'windows','macos','linux','客户端','桌面','安装','装机','软件','编辑器','播放器',
        '下载器','输入法','密码库','远程桌面','启动器','本地','浏览器扩展','系统镜像',
        '录屏','文件管理','邮件客户端','知识库','虚拟声卡','扩展',
    ];

    /** @return array<int,array{mode:string,label:string,route:string,icon:string}> */
    public static function entries(bool $admin): array
    {
        $entries = [
            ['mode'=>'home','label'=>'首页','route'=>'home.php','icon'=>'⌂'],
            ['mode'=>'start','label'=>'导航','route'=>'start.php','icon'=>'◎'],
            ['mode'=>'channels','label'=>'频道','route'=>'channels.php','icon'=>'▶'],
            ['mode'=>'watch','label'=>'影视','route'=>'watch.php','icon'=>'▦'],
            ['mode'=>'topics','label'=>'专题','route'=>'topics.php','icon'=>'◇'],
            ['mode'=>'courses','label'=>'课程','route'=>'courses.php','icon'=>'▥'],
            ['mode'=>'projects','label'=>'项目','route'=>'projects.php','icon'=>'▤'],
            ['mode'=>'tools','label'=>'工具','route'=>'tools.php','icon'=>'⌁'],
            ['mode'=>'software','label'=>'软件','route'=>'software.php','icon'=>'⬡'],
        ];
        if ($admin) return $entries;
        return array_values(array_filter($entries, static fn(array $entry): bool => $entry['mode'] !== 'home'));
    }

    public static function normalizeMode(string $mode): string
    {
        $mode = strtolower(trim($mode));
        if ($mode === 'books') return 'courses';
        return in_array($mode, array_merge(['all'], self::PRIMARY_MODES), true) ? $mode : 'all';
    }

    public static function storageDomain(string $mode): ?string
    {
        $mode = self::normalizeMode($mode);
        return match ($mode) {
            'courses' => 'books',
            'start', 'channels', 'watch', 'topics', 'projects' => $mode,
            default => null,
        };
    }

    /** @return array<int,array<string,mixed>> */
    public static function assets(array $allAssets, string $mode): array
    {
        $mode = self::normalizeMode($mode);
        if ($mode === 'all') return array_values($allAssets);

        $domain = self::storageDomain($mode);
        if ($domain !== null) {
            return array_values(array_filter(
                $allAssets,
                static fn(array $asset): bool => (string)($asset['surface'] ?? 'start') === $domain
            ));
        }

        if ($mode !== 'tools' && $mode !== 'software') return [];
        $out = [];
        foreach ($allAssets as $asset) {
            if ((string)($asset['surface'] ?? 'start') !== 'start') continue;
            $kind = $mode === 'tools' ? self::toolScene($asset) : self::softwareGroup($asset);
            if ($kind === null) continue;
            $asset['_vf_view_mode'] = $mode;
            $asset['_vf_view_kind'] = $kind;
            $out[] = $asset;
        }
        return $out;
    }

    /** @return array<string,int> */
    public static function counts(array $allAssets): array
    {
        $counts = ['total'=>count($allAssets),'start'=>0,'channels'=>0,'watch'=>0,'topics'=>0,'books'=>0,'courses'=>0,'projects'=>0,'tools'=>0,'software'=>0];
        foreach ($allAssets as $asset) {
            $surface = (string)($asset['surface'] ?? 'start');
            if (isset($counts[$surface])) $counts[$surface]++;
            else $counts['start']++;
        }
        $counts['courses'] = $counts['books'];
        $counts['tools'] = count(self::assets($allAssets, 'tools'));
        $counts['software'] = count(self::assets($allAssets, 'software'));
        return $counts;
    }

    public static function viewKind(array $asset, string $mode): string
    {
        $derived = trim((string)($asset['_vf_view_kind'] ?? ''));
        if ($derived !== '') return $derived;
        return trim((string)($asset['resource_kind'] ?? ''));
    }

    public static function toolScene(array $asset): ?string
    {
        if (self::excludedByPrimarySemantics($asset)) return null;
        $explicit = self::explicitTagLabel((array)($asset['tags'] ?? []), ['场景','tool','tools'], array_keys(self::TOOL_SCENES));
        if ($explicit !== null) return $explicit;
        return self::bestLabel($asset, self::TOOL_SCENES, 2);
    }

    public static function softwareGroup(array $asset): ?string
    {
        if (self::excludedByPrimarySemantics($asset)) return null;
        $explicit = self::explicitTagLabel((array)($asset['tags'] ?? []), ['软件','software'], array_keys(self::SOFTWARE_GROUPS));
        if ($explicit !== null) return $explicit;
        $text = self::semanticText($asset);
        if (!self::containsAny($text, self::SOFTWARE_SIGNALS)) return null;
        return self::bestLabel($asset, self::SOFTWARE_GROUPS, 1);
    }

    private static function excludedByPrimarySemantics(array $asset): bool
    {
        $primary = mb_strtolower(implode(' ', [
            (string)($asset['title'] ?? ''),
            (string)($asset['category_name'] ?? ''),
            (string)($asset['resource_kind'] ?? ''),
            implode(' ', array_map('strval', (array)($asset['tags'] ?? []))),
        ]), 'UTF-8');
        return self::containsAny($primary, self::DERIVED_VIEW_EXCLUSIONS);
    }

    private static function bestLabel(array $asset, array $groups, int $minimumScore): ?string
    {
        $primary = mb_strtolower(implode(' ', [
            (string)($asset['title'] ?? ''),
            (string)($asset['category_name'] ?? ''),
            (string)($asset['resource_kind'] ?? ''),
            implode(' ', array_map('strval', (array)($asset['tags'] ?? []))),
        ]), 'UTF-8');
        $description = mb_strtolower((string)($asset['description'] ?? ''), 'UTF-8');
        $best = null;
        $bestScore = 0;
        foreach ($groups as $label => $keywords) {
            $score = 0;
            foreach ($keywords as $keyword) {
                $keyword = mb_strtolower(trim((string)$keyword), 'UTF-8');
                if ($keyword === '') continue;
                if (mb_strpos($primary, $keyword, 0, 'UTF-8') !== false) $score += 3;
                elseif (mb_strpos($description, $keyword, 0, 'UTF-8') !== false) $score++;
            }
            if ($score > $bestScore) {
                $best = (string)$label;
                $bestScore = $score;
            }
        }
        return $bestScore >= $minimumScore ? $best : null;
    }

    private static function semanticText(array $asset): string
    {
        return mb_strtolower(implode(' ', [
            (string)($asset['title'] ?? ''),
            (string)($asset['url'] ?? ''),
            (string)($asset['description'] ?? ''),
            (string)($asset['category_name'] ?? ''),
            (string)($asset['resource_kind'] ?? ''),
            implode(' ', array_map('strval', (array)($asset['tags'] ?? []))),
        ]), 'UTF-8');
    }

    private static function containsAny(string $text, array $keywords): bool
    {
        foreach ($keywords as $keyword) {
            $needle = mb_strtolower(trim((string)$keyword), 'UTF-8');
            if ($needle !== '' && mb_strpos($text, $needle, 0, 'UTF-8') !== false) return true;
        }
        return false;
    }

    private static function explicitTagLabel(array $tags, array $prefixes, array $labels): ?string
    {
        $labelMap = [];
        foreach ($labels as $label) $labelMap[mb_strtolower($label, 'UTF-8')] = $label;
        foreach ($tags as $tag) {
            $tag = trim((string)$tag);
            if ($tag === '') continue;
            $normalized = str_replace('：', ':', $tag);
            $parts = explode(':', $normalized, 2);
            if (count($parts) !== 2) continue;
            $prefix = mb_strtolower(trim($parts[0]), 'UTF-8');
            if (!in_array($prefix, $prefixes, true)) continue;
            $value = mb_strtolower(trim($parts[1]), 'UTF-8');
            if (isset($labelMap[$value])) return $labelMap[$value];
        }
        return null;
    }
}
