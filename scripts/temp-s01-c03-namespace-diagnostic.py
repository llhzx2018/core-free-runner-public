from pathlib import Path

path = Path('m3u8/src/includes/v6-provider-schema.php')
text = path.read_text(encoding='utf-8')
replacements = {
    "'capabilities' => $prefix . 'vf_capabilities'": "'capabilities' => $prefix . 'vf_m3u8_capabilities'",
    "'capability_contracts' => $prefix . 'vf_capability_contracts'": "'capability_contracts' => $prefix . 'vf_m3u8_capability_contracts'",
    "'pipelines' => $prefix . 'vf_pipelines'": "'pipelines' => $prefix . 'vf_m3u8_pipelines'",
    "'pipeline_revisions' => $prefix . 'vf_pipeline_revisions'": "'pipeline_revisions' => $prefix . 'vf_m3u8_pipeline_revisions'",
    "'pipeline_steps' => $prefix . 'vf_pipeline_steps'": "'pipeline_steps' => $prefix . 'vf_m3u8_pipeline_steps'",
    "'pipeline_edges' => $prefix . 'vf_pipeline_edges'": "'pipeline_edges' => $prefix . 'vf_m3u8_pipeline_edges'",
    "'runtime_bundles' => $prefix . 'vf_runtime_bundles'": "'runtime_bundles' => $prefix . 'vf_m3u8_runtime_bundles'",
    "'runtime_bundle_assets' => $prefix . 'vf_runtime_bundle_assets'": "'runtime_bundle_assets' => $prefix . 'vf_m3u8_runtime_bundle_assets'",
}
for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'expected exactly one mapping for {old!r}, found {count}')
    text = text.replace(old, new)
path.write_text(text, encoding='utf-8')

print('EPHEMERAL_M3U8_PROVIDER_TABLE_NAMESPACE_PATCH=PASS')
for key in (
    'vf_m3u8_capabilities',
    'vf_m3u8_capability_contracts',
    'vf_m3u8_pipelines',
    'vf_m3u8_pipeline_revisions',
    'vf_m3u8_pipeline_steps',
    'vf_m3u8_pipeline_edges',
    'vf_m3u8_runtime_bundles',
    'vf_m3u8_runtime_bundle_assets',
):
    if key not in text:
        raise SystemExit(f'missing patched table mapping {key}')
    print(key)
