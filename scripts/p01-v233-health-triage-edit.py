from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one anchor, found {count}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


root = Path('.')

link_health = root / 'src/app/LinkHealth.php'
old_status = '''    public function status(): array
    {
        $total=(int)$this->db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn();
        $counts=['healthy'=>0,'redirected'=>0,'restricted'=>0,'temporary'=>0,'suspected'=>0,'confirmed'=>0,'unchecked'=>0];
        $rows=$this->db->query("SELECT lh.status,COUNT(*) total FROM link_health lh JOIN links l ON l.id=lh.link_id WHERE l.lifecycle_state='active' AND lh.last_checked_at<>'' GROUP BY lh.status")->fetchAll(PDO::FETCH_ASSOC);
        $checked=0;foreach($rows as $row){$s=(string)$row['status'];$c=(int)$row['total'];if(isset($counts[$s]))$counts[$s]=$c;$checked+=$c;}
        $counts['unchecked']=max(0,$total-$checked);
        $last=(string)($this->db->query("SELECT COALESCE(MAX(lh.last_checked_at),'') FROM link_health lh JOIN links l ON l.id=lh.link_id WHERE l.lifecycle_state='active'")->fetchColumn()?:'');
        $ignored=(int)$this->db->query("SELECT COUNT(*) FROM link_health lh JOIN links l ON l.id=lh.link_id WHERE l.lifecycle_state='active' AND lh.ignore_auto=1")->fetchColumn();
        return ['total'=>$total,'checked'=>$checked,'unchecked'=>$counts['unchecked'],'healthy'=>$counts['healthy'],'redirected'=>$counts['redirected'],'restricted'=>$counts['restricted'],'temporary'=>$counts['temporary'],'suspected'=>$counts['suspected'],'confirmed'=>$counts['confirmed'],'ignored'=>$ignored,'problems'=>$counts['restricted']+$counts['temporary']+$counts['suspected']+$counts['confirmed'],'lastCheckedAt'=>$last,'curl'=>function_exists('curl_init')];
    }
'''
new_status = '''    public function status(): array
    {
        $total=(int)$this->db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn();
        $counts=['healthy'=>0,'redirected'=>0,'restricted'=>0,'temporary'=>0,'suspected'=>0,'confirmed'=>0,'unchecked'=>0];
        $rows=$this->db->query("SELECT lh.status,COUNT(*) total FROM link_health lh JOIN links l ON l.id=lh.link_id WHERE l.lifecycle_state='active' AND lh.last_checked_at<>'' GROUP BY lh.status")->fetchAll(PDO::FETCH_ASSOC);
        $checked=0;foreach($rows as $row){$s=(string)$row['status'];$c=(int)$row['total'];if(isset($counts[$s]))$counts[$s]=$c;$checked+=$c;}
        $counts['unchecked']=max(0,$total-$checked);
        $last=(string)($this->db->query("SELECT COALESCE(MAX(lh.last_checked_at),'') FROM link_health lh JOIN links l ON l.id=lh.link_id WHERE l.lifecycle_state='active'")->fetchColumn()?:'');
        $ignored=(int)$this->db->query("SELECT COUNT(*) FROM link_health lh JOIN links l ON l.id=lh.link_id WHERE l.lifecycle_state='active' AND lh.ignore_auto=1")->fetchColumn();
        $review=['restricted'=>0,'temporary'=>0,'suspected'=>0,'confirmed'=>0];
        $reviewRows=$this->db->query("SELECT lh.status,COUNT(*) total FROM link_health lh JOIN links l ON l.id=lh.link_id WHERE l.lifecycle_state='active' AND lh.last_checked_at<>'' AND COALESCE(lh.ignore_auto,0)=0 AND lh.status IN ('restricted','temporary','suspected','confirmed') GROUP BY lh.status")->fetchAll(PDO::FETCH_ASSOC);
        foreach($reviewRows as $row){$s=(string)$row['status'];if(isset($review[$s]))$review[$s]=(int)$row['total'];}
        $attention=$review['confirmed']+$review['suspected'];
        $needsAction=$attention+$review['temporary'];
        return [
            'total'=>$total,'checked'=>$checked,'unchecked'=>$counts['unchecked'],'healthy'=>$counts['healthy'],'redirected'=>$counts['redirected'],
            'restricted'=>$counts['restricted'],'temporary'=>$counts['temporary'],'suspected'=>$counts['suspected'],'confirmed'=>$counts['confirmed'],'ignored'=>$ignored,
            'problems'=>$counts['restricted']+$counts['temporary']+$counts['suspected']+$counts['confirmed'],
            'confirmedReview'=>$review['confirmed'],'suspectedReview'=>$review['suspected'],'temporaryReview'=>$review['temporary'],'restrictedReview'=>$review['restricted'],
            'attention'=>$attention,'needsAction'=>$needsAction,
            'lastCheckedAt'=>$last,'curl'=>function_exists('curl_init')
        ];
    }
'''
replace_once(link_health, old_status, new_status, 'LinkHealth status')

home = root / 'src/app/FunctionalHome.php'
replace_once(
    home,
    "    $healthProblems = max(0, (int)($healthStatus['problems'] ?? 0));\n",
    "    $healthConfirmed = max(0, (int)($healthStatus['confirmedReview'] ?? $healthStatus['confirmed'] ?? 0));\n"
    "    $healthSuspected = max(0, (int)($healthStatus['suspectedReview'] ?? $healthStatus['suspected'] ?? 0));\n"
    "    $healthTemporary = max(0, (int)($healthStatus['temporaryReview'] ?? $healthStatus['temporary'] ?? 0));\n"
    "    $healthRestricted = max(0, (int)($healthStatus['restrictedReview'] ?? $healthStatus['restricted'] ?? 0));\n"
    "    $healthNeedsAction = max(0, (int)($healthStatus['needsAction'] ?? ($healthConfirmed + $healthSuspected + $healthTemporary)));\n",
    'Home health counters'
)
old_home = '''      <?php if($healthProblems>0): ?>
      <section class="vf-home-section vf-home-health-section">
        <header><div><span>异常</span><h2>有 <?=number_format($healthProblems)?> 个网址需要检查</h2><p>只统计已检查后进入异常状态的网址；未检查与已跳转不算异常。</p></div></header>
        <div class="vf-home-health-breakdown" aria-label="网址异常状态">
          <?php foreach([['confirmed','确认失效'],['suspected','疑似失效'],['temporary','暂时异常'],['restricted','访问受限']] as [$key,$label]): $count=max(0,(int)($healthStatus[$key]??0)); if($count<=0)continue; ?>
            <span><b><?=number_format($count)?></b><small><?=vf_fw_h($label)?></small></span>
          <?php endforeach; ?>
        </div>
        <a class="vf-home-health-link" href="health.php">查看网址健康 →</a>
      </section>
      <?php endif; ?>
'''
new_home = '''      <?php if($healthNeedsAction>0 || $healthRestricted>0): ?>
      <section class="vf-home-section vf-home-health-section">
        <header><div><span>健康</span><h2><?php if($healthNeedsAction>0): ?>有 <?=number_format($healthNeedsAction)?> 个网址需要处理<?php else: ?>有 <?=number_format($healthRestricted)?> 个访问受限网址建议人工确认<?php endif; ?></h2><p>疑似/确认失效优先处理，暂时异常建议复查；访问受限常见于登录墙、防爬或限流，不直接等于失效。</p></div></header>
        <div class="vf-home-health-breakdown" aria-label="网址健康待处理状态">
          <?php foreach([[$healthConfirmed,'确认失效'],[$healthSuspected,'疑似失效'],[$healthTemporary,'暂时异常'],[$healthRestricted,'访问受限（人工确认）']] as [$count,$label]): if($count<=0)continue; ?>
            <span><b><?=number_format($count)?></b><small><?=vf_fw_h($label)?></small></span>
          <?php endforeach; ?>
        </div>
        <a class="vf-home-health-link" href="health.php">进入网址健康治理 →</a>
      </section>
      <?php endif; ?>
'''
replace_once(home, old_home, new_home, 'Home health section')

health_php = root / 'src/health.php'
replace_once(
    health_php,
    "    'description'=>'检测 DNS、HTTPS/HTTP、SSL、状态码、跳转、最终地址和响应时间。一次失败不会自动删除或改写网址。',\n",
    "    'description'=>'检测 DNS、HTTPS/HTTP、SSL、状态码、跳转、最终地址和响应时间。访问受限常见于登录墙、防爬或限流，不直接等于失效；一次失败不会自动删除或改写网址。',\n",
    'Health page description'
)
replace_once(
    health_php,
    '<option value="restricted">访问受限</option>',
    '<option value="restricted">访问受限（需人工确认）</option>',
    'Health restricted filter copy'
)

health_js = root / 'src/assets/health.js'
text = health_js.read_text(encoding='utf-8')
old = "function badge(s){return '<span class=\"status '+esc(s)+'\">'+esc(labels[s]||s||'未检查')+'</span>'}function renderSummary(){let s=state.summary||{},items=[['确认失效',s.confirmed],['疑似失效',s.suspected],['暂时异常',s.temporary],['访问受限',s.restricted],['已跳转',s.redirected],['未检查',s.unchecked],['忽略自动',s.ignored]].filter(x=>Number(x[1]||0)>0);if(!items.length&&Number(s.healthy||0)>0)items=[['正常',s.healthy]];$('#summary').innerHTML=items.length?items.map(x=>'<div class=\"metric\"><strong>'+Number(x[1]||0)+'</strong><span>'+x[0]+'</span></div>').join(''):'<div class=\"vf-quiet-state\">当前没有需要处理的网址状态。</div>'}"
new = "function badge(s){return '<span class=\"status '+esc(s)+'\">'+esc(labels[s]||s||'未检查')+'</span>'}function guidance(i){if(i.ignoreAuto)return '已忽略自动检查，不计入首页待处理；需要时可人工打开确认。';if(i.status==='confirmed')return '已人工确认失效；可移到待整理或回收站。';if(i.status==='suspected')return '优先人工打开确认，再决定是否确认失效。';if(i.status==='temporary')return '建议稍后复查；单次超时或网络错误不代表网址失效。';if(i.status==='restricted')return '可能是登录墙、防爬或限流；请先人工打开，不要直接判定失效。';if(i.status==='redirected')return '可人工确认最终地址后，再决定是否采用跳转地址。';return ''}function renderSummary(){let s=state.summary||{},items=[['确认失效',s.confirmedReview??s.confirmed],['疑似失效',s.suspectedReview??s.suspected],['暂时异常',s.temporaryReview??s.temporary],['访问受限（需人工确认）',s.restrictedReview??s.restricted],['已跳转',s.redirected],['未检查',s.unchecked],['已忽略自动',s.ignored]].filter(x=>Number(x[1]||0)>0);if(!items.length&&Number(s.healthy||0)>0)items=[['正常',s.healthy]];$('#summary').innerHTML=items.length?items.map(x=>'<div class=\"metric\"><strong>'+Number(x[1]||0)+'</strong><span>'+x[0]+'</span></div>').join(''):'<div class=\"vf-quiet-state\">当前没有需要处理的网址状态。</div>'}"
if text.count(old) != 1:
    raise SystemExit(f'health.js summary anchor drift: {text.count(old)}')
text = text.replace(old, new, 1)
old = "+(i.lastError?'<div class=\"meta\">'+esc(i.lastError)+'</div>':'')+(i.finalUrl&&i.finalUrl!==i.url?"
new = "+(i.lastError?'<div class=\"meta\">'+esc(i.lastError)+'</div>':'')+(guidance(i)?'<div class=\"meta health-guidance\">'+esc(guidance(i))+'</div>':'')+(i.finalUrl&&i.finalUrl!==i.url?"
if text.count(old) != 1:
    raise SystemExit(f'health.js guidance anchor drift: {text.count(old)}')
text = text.replace(old, new, 1)
old = "<td><div class=\"row-actions\"><button class=\"btn\" data-action=\"retry\""
new = "<td><div class=\"row-actions\"><a class=\"btn primary\" href=\"'+esc(i.url)+'\" target=\"_blank\" rel=\"noopener noreferrer\">打开网址</a><button class=\"btn\" data-action=\"retry\""
if text.count(old) != 1:
    raise SystemExit(f'health.js open action anchor drift: {text.count(old)}')
text = text.replace(old, new, 1)
health_js.write_text(text, encoding='utf-8')

print('P01_V233_HEALTH_TRIAGE_EDIT=PASS')
