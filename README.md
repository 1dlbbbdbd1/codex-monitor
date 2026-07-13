# Codex Floating Companion

一个面向 Codex Desktop 的 Windows 混合式小助手：独立悬浮球负责常驻界面，Codex hooks 负责传递工作与审批状态，现有 CodexControl 数据层负责读取额度和刷新时间。

## v0.1 Demo 已实现

- 可拖动、置顶的 56px 悬浮球，支持左右贴边和 2 秒自动缩边。
- 展开面板显示 5 小时/7 天额度、下次刷新时间、连接健康和最近任务。
- 聚合显示“工作中、等待审批、已完成、失败、空闲”；等待审批优先级最高。
- 审批、完成、失败和额度刷新通知红点；审批未解决前不会被查看操作清除。
- 点击任务时优先使用安全导航能力；当前版本无法精确定位时只激活 Codex 窗口，不修改 Codex 私有状态。
- 多显示器位置恢复、设置持久化、系统托盘、开机启动、安装/升级/卸载脚本。
- 薄 Codex 插件骨架和全局 hooks 安装回退方案；事件桥不记录提示词、命令、工具输入或回复正文。

## 安装 Demo

解压 `CodexFloatingCompanion-windows-x64.zip`，在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -EnableStartup -Launch
```

安装器会把程序放到 `%LOCALAPPDATA%\Programs\CodexFloatingCompanion`，备份并合并 `%USERPROFILE%\.codex\hooks.json`，不会覆盖其他工具的 hooks。

卸载：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

保留本地设置和活动投影可加 `-KeepLocalData`。

## 本地开发

```powershell
$env:PYTHONPATH = (Resolve-Path .\windows)
.\.venv\Scripts\python.exe -m unittest discover .\windows\tests -v
.\.venv\Scripts\python.exe .\windows\tools\app_smoke.py --duration 5
powershell -ExecutionPolicy Bypass -File .\windows\package_release.ps1 -Clean -PythonExecutable .\.venv\Scripts\python.exe
```

关键接口：

- `ActivityEvent -> ActivityStore -> TaskProjection -> aggregate_tasks`
- `Codex hooks -> bridge_cli --emit-hook -> activity-events.jsonl`
- `AccountUsageSnapshot + ActivitySnapshot + NotificationState -> OverlayViewModel`
- `OverlayViewModel -> FloatingOverlay`

详细设计见 [设计规格](docs/superpowers/specs/2026-07-12-codex-floating-companion-design.md)，实施记录见 [开发计划](docs/superpowers/plans/2026-07-12-codex-floating-companion-v0.1.md)，限制见 [已知限制](docs/known-limitations.md)。

## 上游与许可

额度、账户和托盘基础来自 [ademisler/codexcontrol](https://github.com/ademisler/codexcontrol)，导入提交记录在 [UPSTREAM.md](UPSTREAM.md)。项目遵循 MIT License，并保留上游版权声明。

## 进度记录

- 2026-07-12：完成竞品与接口调研，选定 CodexControl Windows 为二开基线；用户确认混合架构、聚合规则、红点和贴边交互。
- 2026-07-12：完成设计规格和分阶段实施计划，导入固定上游提交。
- 2026-07-13：完成活动模型、JSONL 桥、通知状态机、Codex hooks 安装器与薄插件骨架。
- 2026-07-13：完成多屏定位、悬浮球、展开面板、额度/活动集成、托盘导航；70 项测试通过。
- 2026-07-13：完成 Windows x64 单文件 EXE、安装/卸载脚本、插件目录与 ZIP；修复 Tk 打包缺失并用发布 EXE 实机捕获悬浮球像素。
- 2026-07-13：v0.1.0 Demo 开发与本地发布验收完成。
- 2026-07-13：修复活动轮询无变化仍重绘导致的界面闪烁；右键隐藏悬浮球会同步托盘菜单和持久化设置；主窗口、托盘和额度文案改为中文，并补充回归测试。
