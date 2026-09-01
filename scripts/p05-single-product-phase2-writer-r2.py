from pathlib import Path

source = Path('scripts/p05-single-product-phase2-writer.py').read_text(encoding='utf-8')
old = "text = re.sub(r\"\\n  const applyUpdate = async \\(\\) => \\{.*?\\n  \\};\\n  const exportData\", \"\\n  const exportData\", text, count=1, flags=re.S)"
new = "text = re.sub(r\"\\n  const applyUpdate = async \\(\\) => \\{.*?\\n  \\};\\n  const createBackup\", \"\\n  const createBackup\", text, count=1, flags=re.S)"
if old not in source:
    raise SystemExit('phase2 applyUpdate anchor not found')
source = source.replace(old, new, 1)
write_anchor = "common.write_text(text, encoding='utf-8')"
write_replacement = "text = text.replace('<small>系统信息、基线、升级、备份与运行健康</small>', '<small>系统信息、基线、备份、运行健康与维护设置</small>')\ncommon.write_text(text, encoding='utf-8')"
if write_anchor not in source:
    raise SystemExit('phase2 common write anchor not found')
source = source.replace(write_anchor, write_replacement, 1)
exec(compile(source, 'p05-single-product-phase2-writer-r2', 'exec'))
