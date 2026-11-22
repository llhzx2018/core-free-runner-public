#!/usr/bin/env python3
"""Ephemeral PHP test-only probe, never a product edit or PASS evidence.

Uses only numeric line locations in a transient private checkout. Never prints
or persists private source bytes. Emits only synthetic status, boolean, enum,
and approved Laravel session error keys to disposable PHPUnit stderr.
"""
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = path.read_text().splitlines(keepends=True)
if len(lines) < 360 or "$this->post(" not in lines[352] or "->assertSessionHasErrors(" not in lines[356]:
    raise SystemExit("P08_S3_TEMP_PROBE_SOURCE_DRIFT")

lines[352] = lines[352].replace("$this->post(", "$probeResponse=$this->post(", 1)
before, after = lines[356].split("->assertSessionHasErrors(", 1)
if not before.strip().endswith("])"):
    raise SystemExit("P08_S3_TEMP_PROBE_EXPECTED_ASSERTION_CHANGED")
lines[356] = before.rstrip() + ";\n" + """
        error_log('P08_S3_RESTORE_PROBE_STATUS='.$probeResponse->getStatusCode());
        error_log('P08_S3_RESTORE_PROBE_FAULT_UNCONSUMED='.($this->remote->timeoutAfterActivation ? 'YES' : 'NO'));
        error_log('P08_S3_RESTORE_PROBE_REMOTE_SWITCH_CALLED='.($this->remote->lastRollback!=='' ? 'YES' : 'NO'));
        $errorBag=$this->app['session.store']->get('errors');
        $errorKeys=$errorBag ? array_keys($errorBag->getBag('default')->getMessages()) : [];
        error_log('P08_S3_RESTORE_PROBE_SESSION_KEYS='.implode(',',array_intersect($errorKeys,['history_id','confirmation','vps'])));
        error_log('P08_S3_RESTORE_PROBE_LOCAL_STATE='.DB::table('static_vps_targets')->where('id',$target->id)->value('state'));
        $probeResponse->assertSessionHasErrors(""" + after
path.write_text("".join(lines))
print("P08_S3_TEMP_PROBE_PATCH=APPLIED_TO_PRIVATE_DISPOSABLE_TEST_ONLY")
