# 公司盗版 Jira 能力文档

- [公司盗版 Jira 能力文档](#公司盗版-jira-能力文档)
  - [一、基本信息](#一基本信息)
  - [二、Issue Type 使用情况](#二issue-type-使用情况)
  - [三、工作流使用情况](#三工作流使用情况)
    - [Story 状态机（核心，完整走完）](#story-状态机核心完整走完)
    - [Bug 状态机（独立工作流）](#bug-状态机独立工作流)
    - [Publish 封版状态机](#publish-封版状态机)
  - [四、自定义字段使用情况](#四自定义字段使用情况)
    - [Story 核心字段](#story-核心字段)
    - [Bug 专属字段](#bug-专属字段)
  - [五、GitLab 自动化能力（jirascripts）](#五gitlab-自动化能力jirascripts)
  - [六、当前核心痛点](#六当前核心痛点)

> 基于实测数据（Jira REST API v8.13.5）+ 团队实际使用情况
> 项目：【TECH】技术中台前端（JSZTF）

---

## 一、基本信息

| 项目       | 值                                  |
| ---------- | ----------------------------------- |
| 部署版本   | Jira Software v8.13.5（盗版自托管） |
| 部署地址   | https://jira-yzwl.wisedu.com        |
| 项目名称   | 【TECH】技术中台前端（JSZTF）       |
| 项目负责人 | 桂东                                |
| 部署方式   | 私有服务器，无官方支持              |

---

## 二、Issue Type 使用情况

| Issue Type   | 使用频率 | 用途                                              |
| ------------ | -------- | ------------------------------------------------- |
| **Story**    | ⭐ 主力  | 核心开发单元，承载所有需求                        |
| **Sub-task** | ⭐ 经常  | 挂在 Story 下的子任务（如"创建分支"可触发自动化） |
| **Bug**      | ⭐ 经常  | 独立工作流，有专属状态机和字段集                  |
| **Sprint**   | 偶尔     | 迭代管理，按周期组织 Story                        |
| **Epic**     | 偶尔     | 大功能分组，组织多个 Story                        |
| MRD          | 极少     | 市场需求文档，基本不用                            |
| Live-Task    | 极少     | 线上任务                                          |
| Live-Bug     | 极少     | 线上缺陷                                          |
| Publish      | 特殊     | 封版/发版专属类型，驱动发版工作流                 |

---

## 三、工作流使用情况

### Story 状态机（核心，完整走完）

```
TODO → DEVELOPING → INTEGRATING → TESTING → TO_PUBLISH → DONE
                                                  ↓
                                           管理员统一发版
```

团队实际执行情况：**完整走完，不跳步**。开发人员按状态推进，管理员在 TO_PUBLISH 阶段统一触发封版发布。

| 状态转换                         | 操作人 | 触发效果                            |
| -------------------------------- | ------ | ----------------------------------- |
| TODO → DEVELOPING                | 开发者 | 手动，开始开发                      |
| DEVELOPING → INTEGRATING         | 开发者 | 自动：feature → dev 分支合并        |
| INTEGRATING/DEVELOPING → TESTING | 开发者 | 自动：feature → test 分支合并       |
| TESTING → TO_PUBLISH             | 测试   | 测试通过，等待发版                  |
| TO_PUBLISH → DONE                | 管理员 | 发版流程：test→release→main，打 Tag |

### Bug 状态机（独立工作流）

```
TODO → SUSPENDED（挂起）
     → REJECTED（拒绝）
     → READY FOR VERIFICATION（待验证）→ CLOSED
     → REOPENED → ...
```

### Publish 封版状态机

```
TODO → FREEZE_READY → REGRESSING → READY_TO_PUBLISH → DONE
                                 ↘ TODO（重新开版，支持多周期累积）
```

---

## 四、自定义字段使用情况

> 所有字段**都在认真填写**（驱动力：团队计划自建数据看板，依赖字段数据）

### Story 核心字段

| 字段名              | 类型   | 使用情况                |
| ------------------- | ------ | ----------------------- |
| Story Points        | number | 评估工作量              |
| Sprint              | array  | 分配到迭代              |
| Epic Link           | any    | 关联 Epic               |
| 业务域              | option | 业务领域分类            |
| 开始时间 / 结束时间 | date   | 计划时间管理            |
| 版本号              | string | 发版版本号（如 v1.6.0） |
| 是否联动Git发版     | option | 控制 release→main 合并  |
| 工时                | string | 工时记录                |

### Bug 专属字段

| 字段名                  | 类型          |
| ----------------------- | ------------- |
| 严重等级                | option        |
| Bug 来源 / Bug 类型     | option        |
| 责任定位 / 问题产生者   | option/user   |
| Reopen 次数             | option        |
| Bug 发现阶段            | option        |
| 问题定位时长            | number        |
| bug 产生原因 / 修改方案 | option/string |
| 是否命中测试用例        | option        |

---

## 五、GitLab 自动化能力（jirascripts）

通过 jirascripts（FastAPI 服务）监听 Jira Webhook，驱动 GitLab 操作：

| 自动化能力                                                     | 状态      |
| -------------------------------------------------------------- | --------- |
| Story 状态变更 → feature 分支自动合并（dev/test/release/main） | ✅ 运行中 |
| Sub-task 创建 → 在多个 GitLab 仓库自动建 feature 分支          | ✅ 运行中 |
| 封版流程 → test→release 合并 + Jpom CI 构建触发                | ✅ 运行中 |
| 发版 → release→main 合并 + 打 Tag + Changelog 生成             | ✅ 运行中 |
| 冲突通知 → Jira 评论回写                                       | ✅ 运行中 |
| AI 辅助 Changelog 分类                                         | ✅ 运行中 |

**实际体验**：流程本身逻辑没问题，但 **Jira 服务器卡顿频繁，页面经常死掉**，影响日常使用体验。

---

## 六、当前核心痛点

| 痛点                                                                                                                        | 严重程度 |
| --------------------------------------------------------------------------------------------------------------------------- | -------- |
| **盗版合规风险**——违反著作权法，商业合作尽职调查风险                                                                        | 🔴 高    |
| **无 AI 能力**——无 MCP/IDE 集成，无 AI 辅助任务管理                                                                         | 🔴 高    |
| **系统不稳定**——服务器卡顿、页面死掉，影响日常效率                                                                          | 🔴 高    |
| **无法扩展**——API 黑盒，高级功能无从实现，扩展天花板硬                                                                      | 🔴 高    |
| **无法升级维护**——盗版无补丁，无法可控，是否存在已知安全漏洞，死掉的工程                                                    | 🔴 高    |
| **jirascripts 明文认证**——Jira 账号密码明文写入配置文件，任何可访问服务器的人均可获取管理员凭证，一旦泄露影响整个 Jira 系统 | 🔴 高    |
| **无数据可视化**——无燃尽图/速度图，自建看板走到一半卡住                                                                     | 🟡 中    |
| **自建看板是死路**——依赖不透明的黑盒 API，数据源不可靠                                                                      | 🟡 中    |
