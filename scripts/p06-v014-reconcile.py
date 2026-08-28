from pathlib import Path


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise SystemExit(f"missing patch anchor: {label}")
    return source.replace(old, new, 1)


# Reconcile public/index.php around current professional backoffice + Baseline V2,
# while restoring V0.1.13 Book/Reader controller signatures and routes.
p = Path("public/index.php")
s = p.read_text()
s = replace_once(
    s,
    "use VF\\Press\\Application\\Operations\\CommonBaselineV2;\n",
    "use VF\\Press\\Application\\Demo\\DemoDataService;\n"
    "use VF\\Press\\Application\\Operations\\CommonBaselineV2;\n"
    "use VF\\Press\\Application\\Publication\\BookGenerationService;\n",
    "imports-app",
)
s = replace_once(
    s,
    "use VF\\Press\\Http\\Studio\\BackofficeCatalogController;\n",
    "use VF\\Press\\Http\\Studio\\AdminShell;\n"
    "use VF\\Press\\Http\\Studio\\BackofficeCatalogController;\n"
    "use VF\\Press\\Http\\Studio\\BookController;\n",
    "imports-studio",
)
s = replace_once(
    s,
    "use VF\\Press\\Http\\Studio\\QualityController;\n",
    "use VF\\Press\\Http\\Studio\\QualityController;\n"
    "use VF\\Press\\Http\\Studio\\QualityQueueController;\n",
    "imports-quality-queue",
)
s = replace_once(
    s,
    "use VF\\Press\\Infrastructure\\Database\\ConnectionFactory;\n",
    "use VF\\Press\\Infrastructure\\Database\\ConnectionFactory;\n"
    "use VF\\Press\\Infrastructure\\Jobs\\JobQueue;\n",
    "imports-jobs",
)

init_line = (
    "try{$pdo=ConnectionFactory::create($config);$guard=new StoragePathGuard($config->storagePath);"
    "if(!$guard->storageIsOutsidePublicRoot($basePath.'/public'))throw new RuntimeException('私人数据目录与公开网站目录发生重叠。');"
    "$session=new SessionManager();$session->start(($_SERVER['HTTPS']??'')==='on',$config->sessionIdleSeconds,$config->sessionAbsoluteSeconds,$config->sessionCookieSeconds,$config->serverSessionFloorSeconds);"
    "$csrf=new CsrfTokenManager($session);$audit=new AuditLogger($pdo);$rate=new LoginRateLimiter($pdo);"
    "$auth=new OwnerAuthService($pdo,$session,$rate,$audit);$manuscripts=new ManuscriptStore($config->storagePath);"
    "$markdown=new SafeMarkdownRenderer();$settings=new SettingsService($pdo,$audit,$config->storagePath);}"
    "catch(Throwable){http_response_code(503);header('Content-Type: text/plain; charset=utf-8');"
    "echo \"VF Press 暂时无法运行，请先完成数据库升级与环境检查。\\n\";exit;}"
)
s = replace_once(
    s,
    init_line,
    init_line + "\n$adminShell=new AdminShell($settings,$csrf,$runtimeVersion);",
    "admin-shell-init",
)

old_ops = (
    "if(str_starts_with($path,'/studio/operations')){$recovery=new RecoveryService($pdo,$audit,$config->storagePath,$config->databasePath);"
    "$adapter=new VFPressUpdateAdapter($pdo,$config,$audit,$recovery);$updates=new OnlineUpdateService($pdo,$config,$audit,$adapter);"
    "$c=new OperationsController($pdo,$config,$audit,$settings,$recovery,$updates,$csrf,$session);"
    "if($method==='GET'&&$path==='/studio/operations'){if($runStudioModule($c,'operations'))exit;}elseif($c->handle($method,$path))exit;}"
)
new_ops = (
    "if(str_starts_with($path,'/studio/operations')||str_starts_with($path,'/studio/system/demo/')){"
    "$recovery=new RecoveryService($pdo,$audit,$config->storagePath,$config->databasePath);"
    "$adapter=new VFPressUpdateAdapter($pdo,$config,$audit,$recovery);$updates=new OnlineUpdateService($pdo,$config,$audit,$adapter);"
    "$demo=new DemoDataService($pdo,$audit,$manuscripts);"
    "$c=new OperationsController($pdo,$config,$audit,$settings,$recovery,$updates,$csrf,$session,$demo);"
    "if($method==='GET'&&$path==='/studio/operations'){if($runStudioModule($c,'operations'))exit;}elseif($c->handle($method,$path))exit;}"
)
s = replace_once(s, old_ops, new_ops, "operations-route")

book_route = (
    "if(str_starts_with($path,'/studio/books')){$publicationService=new PublicationService($pdo,$audit,$manuscripts);"
    "$outlineProvider=OpenAIResponsesProvider::fromEnvironment();"
    "$c=new BookController($publicationService,new BookGenerationService($pdo,$publicationService,new JobQueue($pdo),$audit,$manuscripts),"
    "$adminShell,$csrf,$outlineProvider!==null);if($c->handle($method,$path))exit;}\n"
)
research_anchor = (
    "if(str_starts_with($path,'/studio/research')){$c=new ResearchController(new ResearchService($pdo,$audit),$csrf);"
    "if($runStudioModule($c,'research'))exit;}"
)
s = replace_once(
    s,
    research_anchor,
    book_route
    + "if(str_starts_with($path,'/studio/research')){$c=new ResearchController(new ResearchService($pdo,$audit),$adminShell,$csrf);"
      "if($c->handle($method,$path))exit;}",
    "book-research-routes",
)
s = replace_once(
    s,
    "if(str_starts_with($path,'/studio/publications')){$c=new PublicationController(new PublicationService($pdo,$audit,$manuscripts),$csrf);if($runStudioModule($c,'publications'))exit;}",
    "if(str_starts_with($path,'/studio/publications')){$c=new PublicationController(new PublicationService($pdo,$audit,$manuscripts),$csrf,$runtimeVersion);if($runStudioModule($c,'publications'))exit;}",
    "publication-signature",
)
s = replace_once(
    s,
    "if(str_starts_with($path,'/studio/publishing')){$ai=OpenAIResponsesProvider::fromEnvironment();$c=new PublishingController(new PublicationService($pdo,$audit,$manuscripts),new EditionService($pdo,$audit,$manuscripts),new ExportService($pdo,$audit,$manuscripts,$markdown,$config->storagePath),new DistributionService($pdo,$audit),$ai===null?null:new AIEditorialService($pdo,$audit,$ai),$csrf);if($runStudioModule($c,'publishing'))exit;}",
    "if(str_starts_with($path,'/studio/publishing')){$ai=OpenAIResponsesProvider::fromEnvironment();$c=new PublishingController(new PublicationService($pdo,$audit,$manuscripts),new EditionService($pdo,$audit,$manuscripts),new ExportService($pdo,$audit,$manuscripts,$markdown,$config->storagePath),new DistributionService($pdo,$audit),$ai===null?null:new AIEditorialService($pdo,$audit,$ai),$adminShell,$csrf);if($c->handle($method,$path))exit;}",
    "publishing-signature",
)
s = replace_once(
    s,
    "if(str_starts_with($path,'/preview')){$c=new PublisherReaderPreviewController(new ReaderService($pdo,$manuscripts,$markdown));if($c->handle($method,$path))exit;}",
    "if(str_starts_with($path,'/preview')){$c=new PublisherReaderPreviewController(new ReaderService($pdo,$manuscripts,$markdown),$runtimeVersion);if($c->handle($method,$path))exit;}",
    "preview-signature",
)
quality_anchor = "if(str_starts_with($path,'/studio/books'))"
s = replace_once(
    s,
    quality_anchor,
    "if($path==='/studio/quality'){$c=new QualityQueueController($pdo,$adminShell);if($c->handle($method,$path))exit;}\n"
    + quality_anchor,
    "quality-queue-route",
)
p.write_text(s)


# Current operations UI remains authoritative, but Demo V2 actions remain callable
# through their historical controlled POST routes.
p = Path("src/Http/Studio/OperationsController.php")
s = p.read_text()
if "use VF\\Press\\Application\\Demo\\DemoDataService;" not in s:
    s = replace_once(
        s,
        "use VF\\Press\\Application\\Operations\\OnlineUpdateService;\n",
        "use VF\\Press\\Application\\Demo\\DemoDataService;\n"
        "use VF\\Press\\Application\\Operations\\OnlineUpdateService;\n",
        "operations-demo-import",
    )
s = replace_once(
    s,
    "        private readonly SessionManager $session,\n    ) {}",
    "        private readonly SessionManager $session,\n        private readonly DemoDataService $demo,\n    ) {}",
    "operations-constructor",
)
marker = "        return false;\n    }\n\n    private function renderIndex(): void"
demo_routes = """        if ($path === '/studio/system/demo/install' && $method === 'POST') {
            $this->requireCsrf();
            try {
                $result = $this->demo->install();
                $this->maintenanceFlash('success', sprintf('完整演示资料已安装：%d 本书、%d 项研究、%d 个章节。', $result['books'], $result['research'], $result['sections']));
            } catch (Throwable $exception) {
                $this->maintenanceFlash('error', '演示资料安装失败：' . $exception->getMessage());
            }
            $this->redirect('/studio/settings');
        }

        if ($path === '/studio/system/demo/refresh' && $method === 'POST') {
            $this->requireCsrf();
            try {
                $result = $this->demo->refresh();
                $this->maintenanceFlash('success', sprintf('演示资料已更新：%d 本书、%d 项研究、%d 个长文章节；真实资料未改变。', $result['books'], $result['research'], $result['sections']));
            } catch (Throwable $exception) {
                $this->maintenanceFlash('error', '演示资料更新失败：' . $exception->getMessage());
            }
            $this->redirect('/studio/settings');
        }

        if ($path === '/studio/system/demo/remove' && $method === 'POST') {
            $this->requireCsrf();
            if ($this->post('confirm') !== '清除演示资料') {
                $this->maintenanceFlash('error', '请输入“清除演示资料”后再执行。');
                $this->redirect('/studio/settings');
            }
            try {
                $this->demo->remove();
                $this->maintenanceFlash('success', '演示资料已整体清除；真实书籍、研究与 Canonical Markdown 未改变。');
            } catch (Throwable $exception) {
                $this->maintenanceFlash('error', '演示资料清除失败：' . $exception->getMessage());
            }
            $this->redirect('/studio/settings');
        }

"""
s = replace_once(s, marker, demo_routes + marker, "operations-demo-routes")
p.write_text(s)
