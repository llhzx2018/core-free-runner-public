<?php
if (!defined('ABSPATH')) { exit; }
$overall=is_array($workbench['overall']??null)?(array)$workbench['overall']:[];
$configuration=is_array($workbench['configuration']??null)?(array)$workbench['configuration']:[];
$acceptance=is_array($workbench['acceptance']??null)?(array)$workbench['acceptance']:[];
$maintenance=is_array($workbench['maintenance']??null)?(array)$workbench['maintenance']:[];
$rows=is_array($workbench['rows']??null)?array_values(array_filter((array)$workbench['rows'],'is_array')):[];
$notices=is_array($workbench['notices']??null)?array_values(array_filter((array)$workbench['notices'],'is_array')):[];
$nextStep=is_array($workbench['nextStep']??null)?(array)$workbench['nextStep']:[];
$status=(string)($overall['status']??'blocked');
$configReady=(int)($configuration['readyCount']??0);
$configTotal=max(1,(int)($configuration['totalCount']??6));
$configPercent=min(100,max(0,(int)round(($configReady/$configTotal)*100)));
$baseReady=!empty($configuration['complete']);
$acceptanceReady=!empty($acceptance['ready']);
$nextStatus=(string)($nextStep['status']??($baseReady?'warning':'blocked'));
$nextUrl=(string)($nextStep['url']??vf_theme_dashboard_url('preview'));
$workspaces=array_values(array_filter($rows,static function(array $row):bool{
    return in_array((string)($row['id']??''),['brand','layout','render','navigation','seo'],true);
}));
$workspaceReadyCount=count(array_filter($workspaces,static fn(array $row):bool=>(string)($row['status']??'warning')==='ready'));
$statusLabel=static function(string $tone):string{
    return $tone==='ready'?'已接通':($tone==='blocked'?'需处理':'待确认');
};
$summaryText=!$baseReady
    ?'基础配置仍有阻断。先完成下方这一项，再继续其它设置。'
    :(!$acceptanceReady?'基础配置已经接通。现在只差一次真实前台验收。':'基础配置和最近一次真实验收都已接通。');
$statusTitle=$status==='ready'?'主题当前可正常使用':($status==='blocked'?'主题还有阻断项需要处理':'主题还有事项需要确认');
?>
<section class="vf-startup vf-workbench-v5141 vf-workbench-v4" data-vf-dashboard-root data-vf-page-id="THM-DASH-001" data-vf-dashboard-revision="<?php echo esc_attr((string)($workbench['revision']??'')); ?>" data-vf-page-state="<?php echo esc_attr($status); ?>">
  <section class="vf-workbench-v5141__status" aria-label="主题当前状态">
    <div class="vf-workbench-v5141__status-main">
      <div class="vf-workbench-v4__status-heading">
        <span class="vf-workbench-v5141__state is-<?php echo esc_attr($status); ?>" data-vf-dashboard-status><?php echo esc_html((string)($overall['label']??'需要处理')); ?></span>
        <h2><?php echo esc_html($statusTitle); ?></h2>
      </div>
      <p data-vf-dashboard-summary><?php echo esc_html($summaryText); ?></p>
    </div>
    <dl class="vf-workbench-v5141__readiness" aria-label="主题就绪度">
      <div class="vf-workbench-v4__metric">
        <dt>基础配置</dt>
        <dd><b data-vf-dashboard-config-ready><?php echo esc_html((string)$configReady); ?></b><span> / <?php echo esc_html((string)$configTotal); ?> 项</span></dd>
        <span class="vf-workbench-v4__meter" aria-hidden="true"><i style="width:<?php echo esc_attr((string)$configPercent); ?>%"></i></span>
      </div>
      <div class="vf-workbench-v4__metric">
        <dt>真实验收</dt>
        <dd data-vf-dashboard-acceptance><?php echo esc_html((string)($acceptance['label']??'待完成')); ?></dd>
        <small><?php echo $acceptanceReady?'最近证据有效':'完成配置后再进行'; ?></small>
      </div>
    </dl>
    <div class="vf-workbench-v5141__refresh">
      <button type="button" class="button" data-vf-dashboard-refresh>刷新状态</button>
      <span data-vf-dashboard-feedback aria-live="polite">只重新读取真实配置和验收状态，不会修改站点。</span>
    </div>
  </section>

  <div class="vf-workbench-v5141__main">
    <section class="vf-workbench-v5141__next is-<?php echo esc_attr($nextStatus); ?>" data-vf-dashboard-next aria-label="推荐下一步">
      <div class="vf-workbench-v4__next-copy">
        <span class="vf-workbench-v5141__eyebrow">现在先做这一项</span>
        <h2 data-vf-dashboard-next-title><?php echo esc_html((string)($nextStep['title']??'刷新当前状态')); ?></h2>
        <p data-vf-dashboard-next-problem><?php echo esc_html((string)($nextStep['problem']??'重新读取主题配置和验收状态。')); ?></p>
      </div>
      <div class="vf-workbench-v5141__next-standard">
        <span>做到什么算完成</span>
        <strong data-vf-dashboard-next-expected><?php echo esc_html((string)($nextStep['expected']??'形成可回读证据')); ?></strong>
      </div>
      <a class="button button-primary vf-workbench-v5141__action" href="<?php echo esc_url($nextUrl); ?>" data-vf-dashboard-next-link><?php echo esc_html((string)($nextStep['action']??'进入处理')); ?></a>
    </section>

    <section class="vf-workbench-v5141__workspaces" aria-label="主题配置工作区">
      <header>
        <div>
          <span class="vf-workbench-v5141__eyebrow">配置工作区</span>
          <h2>按你要改的内容直接进入</h2>
          <p>品牌、布局、导航、工具页和技术 SEO 分开管理，不需要按顺序全部打开。</p>
        </div>
        <strong data-vf-dashboard-workspace-count><?php echo esc_html((string)$workspaceReadyCount); ?> / <?php echo esc_html((string)count($workspaces)); ?> 已接通</strong>
      </header>
      <div class="vf-workbench-v5141__workspace-list" data-vf-dashboard-workspaces>
        <?php foreach($workspaces as $row):$rowStatus=(string)($row['status']??'warning'); ?>
          <a class="vf-workbench-v5141__workspace is-<?php echo esc_attr($rowStatus); ?>" href="<?php echo esc_url((string)($row['url']??'#')); ?>" data-workspace-id="<?php echo esc_attr((string)($row['id']??'')); ?>">
            <div class="vf-workbench-v4__workspace-title"><strong><?php echo esc_html((string)($row['label']??'配置')); ?></strong><span><?php echo esc_html($statusLabel($rowStatus)); ?></span></div>
            <p><?php echo esc_html((string)($row['summary']??'')); ?></p>
            <footer><small><?php echo esc_html((string)($row['value']??'')); ?></small><i aria-hidden="true">进入 →</i></footer>
          </a>
        <?php endforeach; ?>
      </div>
    </section>
  </div>

  <section class="vf-workbench-v5141__attention" data-vf-dashboard-notices<?php echo $notices?'':' hidden'; ?> aria-label="需要关注">
    <header><div><span class="vf-workbench-v5141__eyebrow">需要关注</span><strong>这些事项不会自动修改站点</strong></div><b data-vf-dashboard-notice-count><?php echo esc_html((string)count($notices)); ?> 项</b></header>
    <div data-vf-dashboard-notice-list>
      <?php foreach($notices as $notice): ?>
        <a href="<?php echo esc_url((string)($notice['url']??'#')); ?>"><strong><?php echo esc_html((string)($notice['label']??'注意事项')); ?></strong><span><?php echo esc_html((string)($notice['summary']??'')); ?></span><i aria-hidden="true">查看 →</i></a>
      <?php endforeach; ?>
    </div>
  </section>

  <section class="vf-workbench-v5141__maintenance" aria-label="备份与恢复">
    <div><span class="vf-workbench-v5141__eyebrow">安全维护</span><strong data-vf-dashboard-maintenance-title><?php echo esc_html(!empty($maintenance['ready'])?'恢复策略已接通':'恢复策略待处理'); ?></strong><small data-vf-dashboard-maintenance-meta><?php echo esc_html((int)($maintenance['revisionCount']??0).' 个恢复点 · 最多保留 '.(int)($maintenance['retention']??10).' 个'); ?></small></div>
    <a class="button" href="<?php echo esc_url((string)($maintenance['url']??vf_theme_dashboard_url('recovery'))); ?>" data-vf-dashboard-maintenance-link>备份与恢复</a>
  </section>
</section>
