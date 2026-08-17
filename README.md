# core-free-runner-public

VF 公共测试 / Evidence 基础设施，用于只包含可公开测试输入和可公开 Evidence 的 Runner 工作负载。

## 正式命名层

本仓属于 `core-*` 公共基础设施层，Current 人读命名统一继承 `llhzx2018/gov-doc` 的 `VF 正式命名层 V1.0`。

```text
vf-*      = 软件产品 / 软件组件
skill-*   = AI Skill
core-*    = 跨项目公共基础设施
gov-*     = 治理、规范与长期文档 Authority
```

## 边界

- 只允许 Synthetic Fixture；
- 只允许可公开 Evidence；
- 禁止私人源码、凭据、Production DB、PRIVATE_DATA；
- 受控验证时允许创建并清理项目专用的一次性 Workflow；
- Secret / Token 不作为普通文件长期存储。
