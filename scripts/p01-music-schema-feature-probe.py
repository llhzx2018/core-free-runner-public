#!/usr/bin/env python3
"""One-off P01 Music schema-changing Atomic artifact PROBE; never publishes."""
import argparse
import base64
import importlib.util
import json
import re
from pathlib import Path

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("p01_pkg_base",here/"p01-maintenance-release.py")
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def must(ok,message):
    if not ok:
        raise SystemExit(message)

def main():
    parser=argparse.ArgumentParser()
    for name in ("candidate","baseline-full","baseline-repair","out","version","source-version","target-sha","target-tree"):
        parser.add_argument("--"+name,required=True)
    a=parser.parse_args()
    new_schema="2026102201"
    migration="migrations/2026102201_vf_music.php"
    cand=m.collect(Path(a.candidate))
    baseline=m.collect(Path(a.baseline_full))
    must(re.fullmatch(r"\d+\.\d+\.\d+",a.version) is not None,"invalid candidate version")
    must(cand.get("VERSION.txt",b"").strip()==a.version.encode(),"candidate version mismatch")
    must(baseline.get("VERSION.txt",b"").strip()==a.source_version.encode(),"baseline version mismatch")
    must(re.fullmatch(r"[a-f0-9]{40}",a.target_sha) is not None,"SHA invalid")
    must(re.fullmatch(r"[a-f0-9]{40}",a.target_tree) is not None,"tree invalid")
    old=Path(a.baseline_repair).read_text(encoding="utf-8")
    must(m.parse_public(old,"TARGET_VERSION")==a.source_version,"base repair does not match formal release")
    old_schema=m.parse_public(old,"TARGET_SCHEMA")
    must(old_schema=="2026090401","unapproved source schema")
    old_targets=m.decode_private(old,"TARGET_MANIFEST")
    must(isinstance(old_targets,dict) and bool(old_targets),"missing old target manifest")
    for path,digest in old_targets.items():
        must(path in baseline and m.sha(baseline[path])==digest,"old FULL/repair mismatch: "+path)
    source={key:baseline[key] for key in sorted(old_targets)}
    pack_only=set(baseline)-set(source)
    target={k:v for k,v in cand.items() if k not in pack_only}
    src_migs=m.subset(source,"migrations/")
    dst_migs=m.subset(target,"migrations/")
    must(set(dst_migs)-set(src_migs)=={migration},"expected one isolated Music migration")
    must(set(src_migs)-set(dst_migs)==set(),"existing migrations removed")
    for path in src_migs:
        must(src_migs[path]==dst_migs[path],"existing migration rewritten: "+path)
    for path in m.UPDATER_PATHS:
        must(source.get(path)==target.get(path),"updater mechanism changed: "+path)
    must(b"'version' => '2026102201'" in target[migration],"Music schema id mismatch")
    must(("define('VF_VERSION', '"+a.version+"');").encode() in cand["app/bootstrap.php"],"bootstrap version identity mismatch")
    old_manifest=json.loads(baseline["release-manifest.json"])
    must(str(old_manifest.get("schema_version"))==old_schema,"prior formal schema identity mismatch")
    manifest=dict(old_manifest)
    manifest.pop("maintenance_release",None)
    manifest.update({
        "project":"VF Start","project_id":"P01","project_slug":"vf-start",
        "version":a.version,"source_version":a.source_version,
        "release_type":"schema-feature-candidate-probe","stage":"FORMAL_CANDIDATE_PROBE",
        "source_commit":a.target_sha,"source_tree":a.target_tree,
        "schema_version":new_schema,"schema_change":True,
        "schema_migrations":[migration],"runtime_data_included":False,
        "seed_user_business_data_included":False,
        "release_not_performed":True,
    })
    runtime=dict(target)
    runtime.pop("release-manifest.json",None)
    manifest["runtime_hashed_file_count"]=len(runtime)
    manifest["runtime_files"]={k:m.sha(v) for k,v in sorted(runtime.items())}
    payload_manifest=(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode()
    target["release-manifest.json"]=payload_manifest
    source_manifest={k:m.sha(v) for k,v in sorted(source.items())}
    target_manifest={k:m.sha(v) for k,v in sorted(target.items())}
    encoded={k:base64.b64encode(v).decode() for k,v in sorted(target.items())}
    repair=old
    repair=m.replace_public(repair,"SOURCE_VERSION",a.source_version)
    repair=m.replace_public(repair,"TARGET_VERSION",a.version)
    repair=m.replace_public(repair,"TARGET_SCHEMA",new_schema)
    # The inherited maintenance template cannot apply new migrations. Its
    # rollback verifier also assumes the TARGET schema, which is wrong after
    # original SOURCE files + SQLite have been restored. Keep verification
    # STRICT, choosing the expected schema from the actual on-disk version.
    def transform_once(needle, replacement):
        nonlocal repair
        count=repair.count(needle)
        must(count==1,"unexpected P01 repair template shape: "+needle[:70]+f" (found {count})")
        repair=repair.replace(needle,replacement,1)
    transform_once(
        "public const TARGET_SCHEMA='"+new_schema+"';",
        "public const TARGET_SCHEMA='"+new_schema+"'; public const SOURCE_SCHEMA='"+old_schema+"';"
    )
    transform_once(
        "$head!==self::TARGET_SCHEMA",
        """$head!==(
            defined('VF_ROOT') &&
            trim((string)@file_get_contents(VF_ROOT.'/VERSION.txt'))===self::SOURCE_VERSION
            ? self::SOURCE_SCHEMA : self::TARGET_SCHEMA
        )"""
    )
    transform_once(
        "$dbv=self::dbVerify($db);",
        """require_once $root.'/app/bootstrap.php';
            $p=new PDO('sqlite:'.$db,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
            $p->exec('PRAGMA foreign_keys=ON');
            $migrator=new VfMigrationRunner($p);
            $migrator->migrate(self::SOURCE_VERSION,self::TARGET_VERSION);
            $p=null;
            $dbv=self::dbVerify($db);"""
    )

    for name,obj in (("SOURCE_MANIFEST",source_manifest),("TARGET_MANIFEST",target_manifest),
                     ("PAYLOAD",encoded),("REMOVED",sorted(set(source_manifest)-set(target_manifest))),
                     ("SOURCE_ALTERNATES",{})):
        repair=m.replace_private(repair,name,obj)
    out=Path(a.out)
    out.mkdir(parents=True,exist_ok=True)
    full=dict(cand)
    full["release-manifest.json"]=payload_manifest
    full["FULL-PACKAGE-NOTES.txt"]=(f"VF Start {a.version} schema feature candidate - test only\n").encode()
    full_path=out/f"VF-Start-V{a.version}-FULL.zip"
    atomic_path=out/f"VF_Start_V{a.version}_UPDATE.zip"
    m.zip_deterministic(full_path,full)
    m.zip_deterministic(atomic_path,{f"repair-v{a.version}.php":repair.encode()})
    receipt={"project_id":"P01","mode":"schema-feature-ephemeral-proof",
             "version":a.version,"source_version":a.source_version,"from_schema":old_schema,
             "to_schema":new_schema,"new_migrations":[migration],"source_sha":a.target_sha,
             "source_tree":a.target_tree,"full_sha256":m.sha(full_path.read_bytes()),
             "atomic_sha256":m.sha(atomic_path.read_bytes()),
             "full_bytes":full_path.stat().st_size,"atomic_bytes":atomic_path.stat().st_size,
             "published":False}
    (out/"P01_MUSIC_SCHEMA_ARTIFACT_PROBE.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print("P01_MUSIC_SCHEMA_ARTIFACT_PROBE_BUILD=PASS")

if __name__=="__main__":
    main()
