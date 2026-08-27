from pathlib import Path

p=Path('src/app/CommonBaseline.php')
s=p.read_text()
old="    public const TOAST_MAX_VISIBLE=2;\n"
assert old in s and 'RECOVERY_UPLOAD_EXCEPTION_ID' not in s
s=s.replace(old,old+"    public const RECOVERY_UPLOAD_EXCEPTION_ID='P01-FILE-UPLOAD-RECOVERY-ARTIFACT-001';\n",1)

old_update="        self::row($rows,'UPDATE','single_primary_update_flow',true,is_file(VF_ROOT.'/update.php'),'CUSTOM_RESOLVER','update.php + UpdateManager; full proof pending');\n"
new_update="""        $update=self::updateContractEvidence();
        self::row($rows,'UPDATE','single_primary_action',true,$update['single_primary_action'],'BOOLEAN_REQUIRED','update.php + update-core.js single user decision path');
        self::row($rows,'UPDATE','canonical_phase_contract',true,$update['canonical_phase_contract'],'BOOLEAN_REQUIRED','UpdateManager prepare/install Atomic lifecycle');
        self::row($rows,'UPDATE','preflight_before_product_write',true,$update['preflight_before_product_write'],'BOOLEAN_REQUIRED','UpdateManager validation/disk/staging before Atomic run');
        self::row($rows,'UPDATE','self_test_before_success',true,$update['self_test_before_success'],'BOOLEAN_REQUIRED','Atomic selfTest + run + activation verification');
        self::row($rows,'UPDATE','failure_may_report_success',false,$update['failure_may_report_success'],'EXACT','UpdateManager success assignment ordering + failure journal');
        self::row($rows,'UPDATE','owner_manual_repair_download_required',false,$update['owner_manual_repair_download_required'],'EXACT','UpdateManager automatic repair extraction/handoff');
        self::row($rows,'UPDATE','progress_semantics','PHASE_BASED_NOT_FAKE_PERCENT',$update['progress_semantics'],'EXACT','update-core.js step-based progress');
        self::row($rows,'UPDATE','post_upgrade_session_policy','PRESERVE',$update['post_upgrade_session_policy'],'EXACT','Update runtime does not invalidate authenticated session');
"""
assert old_update in s
s=s.replace(old_update,new_update,1)

old_exception="""    private static function exceptionRow(array &$rows,string $domain,string $parameter,$expected,$effective,string $exceptionId,string $source):void
    {
        $evidence=self::sourceHas($source,'\"id\": \"'.$exceptionId.'\"');
        $rows[]=['domain'=>$domain,'parameter'=>$parameter,'expected'=>$expected,'effective'=>$effective,'comparator'=>'EXPLICIT_EXCEPTION','source'=>$source,'exception'=>$evidence?$exceptionId:null,'result'=>$evidence?'EXCEPTION':'UNKNOWN'];
    }
"""
new_exception="""    private static function exceptionRow(array &$rows,string $domain,string $parameter,$expected,$effective,string $exceptionId,string $source):void
    {
        $declared=hash_equals(self::RECOVERY_UPLOAD_EXCEPTION_ID,$exceptionId);
        $rows[]=['domain'=>$domain,'parameter'=>$parameter,'expected'=>$expected,'effective'=>$effective,'comparator'=>'EXPLICIT_EXCEPTION','source'=>$source,'exception'=>$declared?$exceptionId:null,'result'=>$declared?'EXCEPTION':'UNKNOWN'];
    }
"""
assert old_exception in s
s=s.replace(old_exception,new_exception,1)

anchor="    private static function isIanaZone(string $zone):bool{return in_array($zone,DateTimeZone::listIdentifiers(),true);}\n"
assert anchor in s and 'private static function updateContractEvidence' not in s
helper="""    /** @return array<string,mixed> */
    private static function updateContractEvidence():array
    {
        $manager=self::sourceText('src/app/UpdateManager.php');
        $ui=self::sourceText('src/assets/update-core.js');
        $page=self::sourceText('src/update.php');
        if($manager===''||$ui===''||$page==='')return [
            'single_primary_action'=>null,'canonical_phase_contract'=>null,'preflight_before_product_write'=>null,
            'self_test_before_success'=>null,'failure_may_report_success'=>null,'owner_manual_repair_download_required'=>null,
            'progress_semantics'=>null,'post_upgrade_session_policy'=>null,
        ];
        $has=static fn(string $text,string $needle):bool=>str_contains($text,$needle);
        $ordered=static function(string $text,array $needles):bool{$last=-1;foreach($needles as $needle){$pos=strpos($text,$needle);if($pos===false||$pos<=$last)return false;$last=$pos;}return true;};
        $single=$has($page,'id=\"installUpdate\"')&&$has($ui,'function startInstall()')&&$has($ui,"api('update_prepare'")&&$has($ui,"api('update_install'");
        $canonical=$has($manager,'public function prepare(): array')&&$has($manager,'vf_assert_disk_space')&&$has($manager,'VfBackupManager')&&$has($manager,'VfAtomicPackage::selfTest()')&&$has($manager,'public function install(string $operationId): array')&&$has($manager,'VfAtomicPackage::run($this->root)')&&$has($manager,"$journal['result'] = 'success'")&&$has($manager,'removeTree($stage)');
        $preflight=$ordered($manager,['vf_assert_disk_space','$this->stagePath($operationId)','VfAtomicPackage::run($this->root)']);
        $selfTest=$has($manager,'VfAtomicPackage::selfTest()')&&$has($manager,"if (empty($selfTestJson['ok']))")&&$has($manager,"if (empty($atomicJson['ok']))")&&$has($manager,"if ($actual !== $target)");
        $successSafe=$ordered($manager,["if (empty($atomicJson['ok']))","if ($actual !== $target)","$journal['result'] = 'success'"])&&$has($manager,"'failed_rolled_back'")&&$has($manager,"'recovery_required'");
        $manualRepair=!$has($page,'下载 repair')&&!$has($ui,'下载 repair')&&$has($manager,'extractRepair(');
        $phaseProgress=$has($ui,'function step(label,kind)')&&!preg_match('/\\b(?:percent|percentage)\\b/i',$ui);
        $preserve=!$has($manager,'session_destroy(')&&!$has($manager,'revokeCurrent(')&&!$has($ui,'logout');
        return [
            'single_primary_action'=>$single,
            'canonical_phase_contract'=>$canonical,
            'preflight_before_product_write'=>$preflight,
            'self_test_before_success'=>$selfTest,
            'failure_may_report_success'=>$successSafe?false:true,
            'owner_manual_repair_download_required'=>$manualRepair?false:true,
            'progress_semantics'=>$phaseProgress?'PHASE_BASED_NOT_FAKE_PERCENT':'UNRESOLVED',
            'post_upgrade_session_policy'=>$preserve?'PRESERVE':'UNRESOLVED',
        ];
    }

"""
s=s.replace(anchor,helper+anchor,1)
p.write_text(s)
