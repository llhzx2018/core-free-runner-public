# core-free-runner-public

VF 公共零付费测试执行壳。

```text
PUBLIC Repository
→ GitHub Hosted Runner
→ 临时只读取得指定 PRIVATE Repository Commit
→ 建立真实测试环境
→ 执行测试
→ 生成脱敏 Evidence
→ 自动清理
```

## 安全边界

- 私有源码不得进入本仓库 Git 历史；
- `PRIVATE_DATA`、数据库、Secret、Token、Cookie、Session 不得进入公开 Evidence；
- 私库读取统一使用 Repository Secret `VF_PRIVATE_READ_TOKEN`；
- Token 只授予指定 PRIVATE 仓库 `Contents: Read-only`；
- `persist-credentials: false`；
- 测试结束清理临时源码和运行数据；
- PASS 必须有可追踪 Evidence，不能只依据 Actions 绿灯；
- 用户个人电脑不是 Runner。

私有临时测试材料如确有必要，使用独立 PRIVATE 空间 `core-free-runner-private`，不进入本仓库。
