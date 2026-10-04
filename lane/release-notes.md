VF Tools Ops V1.21.1031 · 内容概览标题恢复

修正 V1.21.1030 隐藏整块页面标题区的回归：保留唯一正式标题“内容与 SEO 概览”，仅移除标题上方“VF 站点运营”重复身份。现有全宽布局、重新检查语言归一修复、冻结 Shell/Header/Header Menu 均保留。

本包为 WordPress Component 包，安装目录为 vf-ops/vf-ops.php，同时用于该组件安装与原生升级；不套用独立 APP 的 FULL/UPDATE 双包命名。已安装 1.21.1030 的升级及回退以隔离 WordPress 机器证据为准。内部 Schema 仍为 6.0.0，本版无 Schema/Data Migration；升级前沿用现有备份与恢复点机制。

正式 Asset、SHA256SUMS 和 SOURCE_MANIFEST 见本 Release。Exact Source、Candidate/Formal Run、Runtime fingerprint 由 SOURCE_MANIFEST.json 记录；同名正式包不会替换，Tag 不移动。

此 Release/Distribution 不代表 Production 已升级或 OWNER 产品验收通过。Production 当前由 OWNER 确认已安装 1.21.1030；1.21.1031 由 OWNER 手工升级并最终复验。OWNER_PRODUCT_PASS = NO。