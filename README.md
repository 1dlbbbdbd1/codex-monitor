# Codex 桌面悬浮状态与额度助手

## Upstream

The quota/account foundation is derived from [ademisler/codexcontrol](https://github.com/ademisler/codexcontrol) under the MIT License. The imported source commit is recorded in Git history and `UPSTREAM.md`.

## 项目目标

为 Codex 桌面端寻找或开发一个轻量常驻助手，优先满足：

- 显示额度余量及预计刷新时间。
- 显示当前工作状态，例如工作中、等待审批、已完成或异常。
- 以可拖动悬浮球呈现，可收起到屏幕侧边。
- 收起或隐藏时，遇到待处理事项或额度刷新可用红点提示。
- 优先复用成熟开源项目；没有合适成品时，再选择高星、架构接近的 GitHub 项目二次开发。

## 当前阶段

状态：整体设计已批准并固化为规格，正在生成实施计划，尚未开始实现代码。

设计规格：[`docs/superpowers/specs/2026-07-12-codex-floating-companion-design.md`](docs/superpowers/specs/2026-07-12-codex-floating-companion-design.md)

实施计划：[`docs/superpowers/plans/2026-07-12-codex-floating-companion-v0.1.md`](docs/superpowers/plans/2026-07-12-codex-floating-companion-v0.1.md)

按照项目约定，先核查接口、已有资料和社区项目。设计未经用户确认前不创建实现代码。

## 已有资料与环境

- 工作目录创建于 2026-07-12，目前只有 `work/`、`outputs/` 与本 README。
- 当前目录尚不是 Git 仓库，没有已有代码、提交历史或远程仓库。
- 用户允许在缺少成品时选择 GitHub 高星近似项目进行二次开发。
- GitHub fork、建仓、推送、提交 PR 等外部写操作需在目标确定后确认授权与账号。

## 待核查接口

- [已确认] Codex app-server 提供 `account/rateLimits/read`，字段包含已用百分比、窗口时长和下次刷新时间，并有 `account/rateLimits/updated` 更新事件。
- [已确认] app-server 提供 `thread/status/changed`、`turn/started`、`turn/completed`，可表达运行中、空闲、完成、失败与中断。
- [已确认] app-server 的审批流程会发出命令、文件修改、权限及 MCP elicitation 等服务端请求；客户端可以识别“等待处理”。
- [风险] Codex Desktop 自己启动的 app-server 与外部独立 app-server 目前不是共享实时事件总线；外部客户端不能假定能直接旁听桌面进程的所有活动。
- [风险] Codex 全局 hooks 已覆盖 SessionStart、UserPromptSubmit、Stop、PermissionRequest 等关键节点，但桌面端和插件内 hooks 仍有公开的兼容性/加载问题，需要实机验证并准备日志监听降级方案。
- 能否通过本地日志、进程、通知或窗口状态以稳定且合规的方式获得上述信息。
- Windows 桌面悬浮窗、贴边收起、开机启动和通知红点的实现边界。
- 候选开源项目的许可证是否允许 fork、修改和重新发布。

## 社区项目初筛

| 项目 | 平台/许可证 | 接近程度 | 结论 |
| --- | --- | --- | --- |
| [CodexBar](https://github.com/steipete/CodexBar) | macOS 主界面，MIT | 高星成熟项目；额度、刷新倒计时、状态徽标完善 | 数据层参考价值最高，但 Swift/macOS UI 不适合直接移植成 Windows 悬浮球 |
| [CodexControl](https://github.com/ademisler/codexcontrol) | macOS + Windows，MIT | Windows 托盘、实时 5h/7d 额度、精确刷新时间、本地优先 | 当前最适合的二开基座；缺悬浮球和 Codex 工作/审批状态 |
| [TokenPeep](https://www.tokenpeep.com/) | Windows，未公开仓库，预发布 | 托盘 + 常驻小窗、额度、刷新时间、阈值预警，视觉形态最接近 | 可试用/参考产品设计，但目前不满足“拉 GitHub 开源项目二开” |
| [Tokage](https://github.com/devdotmohit/tokage-app) | macOS，未见明确许可证 | 本地日志用量统计 | 统计的是 token 消耗，不是可靠的实时额度窗口；不选 |
| [Codex Buddy](https://github.com/openelab-commits/codex-buddy) | ESP32 外设 | 有 busy/idle/completed/attention 和宠物动画 | 状态模型值得借鉴，但硬件形态不合适 |

## 当前判断

- 没有一个现成开源项目同时满足 Windows、实时额度、Codex 工作状态、等待审批、可拖动贴边悬浮球和红点提醒。
- 推荐以 CodexControl 的 Windows 版本为二开基座，保留其额度/auth 实现，增加独立悬浮层与状态采集层。
- 成品应是 Windows 独立伴侣程序；可以附带 Codex 集成配置/薄插件，但不能把原生悬浮窗寄托在 Codex 插件 UI 上。
- 状态采集优先级：官方 app-server 事件（本程序管理的连接）→ 全局 hooks 事件桥 → 本地 session 日志/进程状态降级；任何不确定状态显示为“未知”。
- [用户决策] 采用混合方案：独立 Windows 小助手提供托盘/悬浮球/贴边/红点，Codex 薄插件或集成配置负责传递工作与审批事件。
- [用户决策] 悬浮球聚合全部 Codex 任务：任意任务等待审批时优先提示，否则显示工作中任务数；全部结束后显示最近完成状态，点击展开任务详情。
- [用户决策] 审批红点持续到审批完成；任务完成、失败和额度刷新红点在用户打开悬浮球查看后清除；普通工作中仅显示动画和数量，不显示红点。
- [用户决策] 拖到屏幕左右边缘后自动吸附，闲置约 2 秒收起，仅保留可点击把手；存在红点时把手和红点必须保持可见。
- [用户决策] 点击待审批任务时优先跳转到 Codex 对应任务；不支持精确跳转时激活 Codex 窗口，并显示项目名与任务标题用于定位。
- [用户决策] 采用路线 A：以 CodexControl Windows 版为基座，新增独立状态桥、悬浮层和提醒状态机；app-server 与 session 日志只作补充/降级。用户要求加快推进，后续设计合并为一次确认。

## 路线比较

- 路线 A（推荐）：CodexControl 二开 + Codex 状态桥。复用成熟额度与发布能力，开发量最小，状态采集可替换。
- 路线 B：独立 app-server 监听器。协议规范，但当前无法可靠旁听 Codex Desktop 自有进程的全部实时事件。
- 路线 C：全新 .NET 原生 Windows 应用。桌面体验潜力最佳，但需要重写额度、认证、账户和发布能力，首版成本最高。

## CodexControl Windows 二开尽调

- 许可证：MIT，允许 fork、修改、发布和销售衍生版本；发布时必须保留原版权及 MIT 许可证。
- 技术栈：Python、`tkinter`、`pystray`、Pillow、Requests；不是 Electron，常驻体量和改造门槛较低。
- 现有界面：系统托盘 + 438×616 主窗口，支持隐藏启动、5 分钟自动刷新、手动刷新和开机启动。
- 额度来源：读取本地 Codex `auth.json`，刷新 OAuth 后直接请求 `https://chatgpt.com/backend-api/wham/usage`；支持自定义 `chatgpt_base_url`。
- 数据可靠性：强制刷新时连续读取 2–3 次并比对，结果不一致则拒绝展示；短窗口和周窗口分别归一化。
- 工程化：Windows 代码已有 `unittest` 测试，使用 PyInstaller 生成单文件 GUI 程序，并提供安装、启动项和发布打包脚本。
- 改造点：新增独立 `ActivityState` 状态模型、事件采集器、透明无边框悬浮窗和通知状态机；不要把这些逻辑继续堆进现有体量较大的 `app.py`。
- Windows 风险：`tkinter` 可做无边框置顶窗口，但圆形透明点击区域、DPI、多显示器和贴边动画需要 Win32 API 辅助及实机回归。
- GitHub 状态：当前连接可读取该仓库但没有推送权限；本机也未安装 `gh`。设计确认后，fork/推送前需要安装 GitHub CLI 并完成用户授权，或由用户提供目标仓库权限。

## 初步验收方向

- 不要求用户频繁手动刷新。
- 额度或状态取不到时明确显示“未知”，不能伪造数据。
- 常驻资源占用低，悬浮球不抢焦点，拖动与贴边行为稳定。
- 待审批、任务完成或额度刷新能在收起状态下显示红点。
- 不收集或上传 Codex 会话内容；敏感凭据只保存在本地安全存储。

## 进度记录

- 2026-07-12：建立项目说明；完成空目录与 Git 状态检查；开始检索 Codex Skills、官方接口和 GitHub 候选项目。
- 2026-07-12：完成第一轮网络检索；确认 app-server 的额度、线程、回合和审批协议；确认暂无完全匹配的开源成品，CodexControl 是当前最佳二开候选。
- 2026-07-12：完成 CodexControl Windows 源码尽调；确认 MIT 许可、Python/tkinter/pystray 架构、实时额度请求、测试与 PyInstaller 发布流程均适合作为二开基座。
- 2026-07-12：用户确认采用“Windows 独立助手 + Codex 薄集成”的混合方案。
- 2026-07-12：用户确认悬浮球采用全任务聚合规则，审批状态具有最高展示优先级。
- 2026-07-12：用户确认提醒确认规则：审批持续提醒，完成/失败/额度刷新查看后清除。
- 2026-07-12：用户确认左右贴边吸附、2 秒自动收起及红点常显规则。
- 2026-07-12：用户确认待审批任务的精确跳转及激活 Codex 降级规则。
- 2026-07-12：根据用户“快一点”的要求，采用推荐路线 A，并将详细设计压缩为一次整体确认。
- 2026-07-12：用户批准完整设计并授权连续推进至第一版 Demo；设计规格已写入并进入实施计划阶段。

## 下一步

1. 逐项确认状态聚合、提醒和悬浮交互规则。
2. 给出 2–3 条路线和推荐。
3. 分段确认界面、状态规则、数据来源、异常处理和测试设计。
4. 写入并提交设计文档，用户复核后再形成实施计划。
5. 设计获批后安装 GitHub CLI、fork 候选仓库并开始二次开发。
