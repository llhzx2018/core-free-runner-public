# core-free-runner-public · CURRENT

> 唯一 Current Infrastructure Authority 入口

## Current Truth

```text
Role: Public-safe GitHub Hosted Runner + Evidence infrastructure
Canonical Branch: main
Private source persistence in public Git/Artifact: FORBIDDEN
Transient private checkout: ALLOWED under runtime secret + cleanup
One-off project PR/workflow: CLOSE WITHOUT MERGE by default
Runner activation: ON DEMAND ONLY
```

## Read Path

普通已路由到本 Runner 的 bounded task：

```text
CURRENT
→ task-relevant workflow / harness / script only
→ task-relevant Run / Job / Artifact / Evidence only
```

只有 Runner governance / authority change 才扩展读取：

```text
INFRASTRUCTURE_CONTRACT
→ SSOT
→ ACCEPTANCE_MATRIX
→ affected workflow surface
```

禁止为了“完整”机械读取整个 `.github/workflows/`、全部 Harness、全部历史 Evidence 或 README。

Active workflow 名称、数量、Run / Job / Artifact、临时 branch 与 trigger 都是动态 Git / Runner Truth，需要时 live-read，不复制为长期 Current 值。

Historical sandbox / request / trigger files are execution provenance, not Current Contract.
