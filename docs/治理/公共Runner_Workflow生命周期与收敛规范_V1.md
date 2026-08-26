# 公共 Runner Workflow 生命周期与收敛规范 V1

> 状态：`CURRENT CANDIDATE`  
> 适用仓库：`llhzx2018/core-free-runner-public`  
> 边界：不授权 Release、Tag 或 Production 写入

## 一、仓库定位

公共 Runner 是执行与验证基础设施，不是产品源码仓，也不是无限保存所有历史执行入口的仓库。

`.github/workflows/` 只保存仍需被 GitHub Actions 注册的入口。历史 Workflow 可以从该目录移出；真正无保留价值的材料，经过恢复性确认后可以删除。

## 二、五类对象

| 分类 | 定义 | 默认处置 |
| --- | --- | --- |
| 当前入口 | 当前项目或公共基础设施仍依赖的 Workflow | 保留在 `.github/workflows/` |
| 可复用 Harness | 不绑定单一历史版本，可被多个任务调用的脚本、Action 或测试逻辑 | 保留并由少量当前入口调用 |
| 历史版本 Workflow | 固定旧版本、旧 Commit 或已完成阶段的执行包装 | 移出注册目录并归档 |
| Evidence-only | 只用于证明过去发生过什么的记录 | 保留 Manifest、Hash 或 Git 历史，不保留可执行入口 |
| 删除候选 | 重复、无引用、无恢复价值，且已有替代物 | 通过 Candidate 删除 |

## 三、删除 Gate

同时满足以下条件才允许永久删除：

1. 不属于当前入口，也未被任何当前 Workflow、脚本或文档 Authority 引用；
2. 可复用逻辑已经存在于当前 Harness，或确认不存在可复用逻辑；
3. 删除后仍可通过 Git 历史或 Manifest 定位来源；
4. 独立 Candidate 测试证明当前触发、测试和恢复合同不受影响。

“这是测试仓”不能单独作为全删依据。测试仓中的 Gate 可能是产品发布前唯一机器验证入口；误删不会直接修改 Production，但会让后续改动失去验证能力。

## 四、第三阶段首批裁决

`core-agent` 族群采用“一当前入口 + 九历史版本”的结构：

- 保留：`core-agent-current-verify.yml`；
- 归档：`core-agent-v0.4` 至 `core-agent-v1.0` 共 9 个旧版本 Gate；
- 依据：9 个旧文件没有仓内调用方，只绑定自身路径和人工触发；
- 可复用能力：由 `core-agent` 当前源码中的验证与 Pilot 脚本承担，不依赖旧 YAML 保持注册；
- 结果：活跃 Workflow 从 386 降至 377，归档清单从 39 增至 48。

## 五、后续批次

按项目族群逐批处理 P01–P06、S01 和公共基础设施：

1. 每批先选出唯一 Current 入口；
2. 把重复内联逻辑提取为 Harness；
3. 归档被替代的版本化包装；
4. 稳定观察后，再删除确认无恢复价值的归档材料。

禁止一次性删除全部 Workflow；禁止把归档目录重新加入自动执行范围。
