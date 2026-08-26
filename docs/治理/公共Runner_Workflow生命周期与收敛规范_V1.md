# 公共 Runner Workflow 生命周期与收敛规范 V1

> 状态：`CURRENT`
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

## 五、第三阶段 P02 裁决

P02 族群没有可继续注册的 Current Workflow：

- Current：0；
- 可复用且不绑定历史版本的 Harness：0；
- 历史 Workflow：83；
- 固定旧 Commit：81 / 83；
- 使用 `VF_RELEASE_WRITE_TOKEN`：27；
- 包含 `git push`：11；
- 包含 `gh release`：6。

其中包括 V2.4.23、V2.4.24、V2.4.25、V2.5.0、V2.5.10、V2.5.16、V2.5.17、V2.5.18、V2.5.20，以及 7 个表面通用但仍固定在 V2.4.x 的历史入口。

裁决：83 个 P02 Workflow 全部移出 `.github/workflows/`。P02 后续恢复开发时，应从 `vf-library` Current Source 建立新的任务级 Candidate Gate，不得复用历史 Release 包装。

本批完成后：活跃 Workflow 从 377 降至 294；归档清单从 48 增至 131。

## 六、第三阶段 P03 裁决

P03 族群没有可继续注册的 Current Workflow：

- Current：0；
- 可复用且不绑定历史版本的 Harness：0；
- 历史 Workflow：78；
- 固定旧 Commit：68 / 78；
- 使用 `VF_RELEASE_WRITE_TOKEN`：31；
- 包含 `git push`：21；
- 包含 `gh release`：16；
- 使用 `workflow_run` 串联历史流程：3。

P03 Workflow 最高只覆盖 V1.37.0，且所谓通用入口仍固定旧 Commit、执行一次性修复或检查发布令牌；它们不能代表当前运行基线。多个历史入口仍具备推送源码、创建 Tag/Release、写入 `core-updates` 或回写 Runner 的能力，继续注册会留下不必要的写入面。

裁决：78 个 P03 Workflow 全部移出 `.github/workflows/`。P03 处于 `DORMANT / MAINTENANCE` 时默认不注册项目级执行入口；未来明确恢复开发时，应从当时的 Current Source 新建任务级 Candidate Gate，不得复用历史 Release 包装或 `workflow_run` 链。

本批完成后：活跃 Workflow 从 294 降至 216；归档清单从 131 增至 209。

## 七、第三阶段 P04 裁决

P04 族群没有可继续注册的 Current Workflow：

- Current：0；
- 可复用且不绑定历史版本的 Harness：0；
- 历史 Workflow：67；
- 固定旧 Commit：62 / 67；
- 使用 `VF_RELEASE_WRITE_TOKEN`：45；
- 包含 `git push`：18；
- 包含 `gh release`：17；
- 涉及 Production 语义：37。

P04 Workflow 最高只覆盖 V2.7.8。名称包含 `current` 或 `harness` 的入口仍固定 V2.7.4、V2.5.8 和旧 Commit；两个无版本名入口也分别锁定 V2.5.2 Release Asset 与一次性 Production Secret Channel 探测，因此均不具备版本无关的复用合同。

裁决：67 个 P04 Workflow 全部移出 `.github/workflows/`。P04 后续开发应在 `vf-infra` Current Source 上建立任务级 Candidate Gate；Release、Rollback、Production Readback 与 Secret Probe 必须由当次明确授权重新生成，不得复用旧版本执行包装。

本批完成后：活跃 Workflow 从 216 降至 149；归档清单从 209 增至 276。

## 八、第三阶段 P05 裁决

P05 族群没有可继续注册的 Current Workflow：

- Current：0；
- 可复用且不绑定历史版本的 Harness：0；
- 历史 Workflow：17；
- 固定旧 Commit：14 / 17；
- 使用 `VF_RELEASE_WRITE_TOKEN`：1；
- 包含 `gh release`：1；
- 涉及 Production 语义：11。

P05 的 `database-deploy-current`、`database-deploy-gates` 与 `database-rebaseline` 均固定旧 Commit；First Boot、Production Readback 和 Reference-Locked 流程只在修改自身 YAML 时触发，是一次性诊断或阶段验证，不构成持续 Current Gate。仓内没有其他调用方。

裁决：17 个 P05 Workflow 全部移出 `.github/workflows/`。后续 P05 开发、数据库验证和 Production Readback 应从 `vf-seo` Current Source 建立任务级 Gate；不得把固定旧 Commit 的 `current` 名称视为当前 Authority。

本批完成后：活跃 Workflow 从 149 降至 132；归档清单从 276 增至 293。

## 九、第三阶段 P06 裁决

P06 族群没有可继续注册的 Current Workflow：

- Current：0；
- 可复用且不绑定历史版本的 Harness：0；
- 历史 Workflow：62；
- 固定旧 Commit：57 / 62；
- 使用 `VF_RELEASE_WRITE_TOKEN`：10；
- 包含 `git push`：33；
- 包含 `gh release`：12；
- 涉及 Production 语义：24。

P06 Workflow 覆盖旧 V0.1.2–V0.1.6、RC1 和 `VF Press` 身份。未固定 Commit 的5个入口也只是 Backup、Visual、Studio Auth 的一次性 Dispatch；仓内没有其他调用方，且旧项目身份不能代表当前 P06 Authority。

裁决：62 个 P06 Workflow 全部移出 `.github/workflows/`。当前 P06 后续开发必须从其正式 Source Identity 新建任务级 Gate，不得继承旧 `VF Press` Release、在线升级或私有 Secret 包装。

本批完成后：活跃 Workflow 从 132 降至 70；归档清单从 293 增至 355。

## 十、第三阶段 P01 裁决

P01 族群没有可继续注册的 Current Workflow：

- Current：0；
- 可复用且不绑定历史版本的 Harness：0；
- 历史 Workflow：58；
- 固定旧 Commit：54 / 58；
- 使用 `VF_RELEASE_WRITE_TOKEN`：42；
- 包含 `git push`：20；
- 包含 `gh release`：10；
- 涉及 Production 语义：47；
- 使用 `workflow_run` 串联历史流程：14。

P01 Workflow 覆盖 V2.21.17–V2.21.24 以及已完成的修复、发布、Production Closure 和 Token Probe。原隔离名单中的3个手工入口也固定 V2.21.21 旧分支或只执行 Runner Probe，不再承担当前恢复合同。

裁决：58 个 P01 Workflow 全部移出 `.github/workflows/`，并清空旧隔离名单。后续 P01 开发必须从 `vf-start` Current Source 建立任务级 Gate；已完成版本的 Artifact、Publish 与 Production 包装不得继续注册。

本批完成后：活跃 Workflow 从 70 降至 12；归档清单从 355 增至 413；历史触发隔离名单从3降至0。

## 十一、第三阶段 S01 裁决

S01 族群没有可继续注册的 Current Workflow：

- Current：0；
- 可复用且不绑定历史版本的 Harness：0；
- 历史 Workflow：6；
- 固定旧 Commit：6 / 6；
- 使用 `VF_RELEASE_WRITE_TOKEN`：3；
- 包含 `git push`：1；
- 包含 `gh release`：1；
- 涉及 Production 语义：4。

S01 Workflow 分别绑定 C01、C02、C03 的旧版本发布、Bootstrap 与 WordPress 在线更新候选，仓内没有其他调用方，不构成公共 Runner Current Harness。

裁决：6个 S01 Workflow 全部移出 `.github/workflows/`。各组件后续开发应从对应 Source Repository 建立任务级 Gate，不复用旧发布包装。

本批完成后：活跃 Workflow 从12降至6；归档清单从413增至419。

## 十二、后续批次

按项目族群逐批处理 P01–P06、S01 和公共基础设施：

1. 每批先选出唯一 Current 入口；
2. 把重复内联逻辑提取为 Harness；
3. 归档被替代的版本化包装；
4. 稳定观察后，再删除确认无恢复价值的归档材料。

禁止一次性删除全部 Workflow；禁止把归档目录重新加入自动执行范围。
