# Windows Compatibility Implementation Plan

## 背景

当前 BBagent 的核心 Python 库、FastAPI 后端和 React 前端大部分代码使用 `pathlib`、`os.path`、Vite、npm 等跨平台能力，理论上可以在 Windows 上安装和运行一部分功能。

但项目里仍有几处明确偏 Unix 的运行时假设：

1. `run.py` 使用 `lsof` 查端口，并使用 Unix signal 终止进程。
2. 内置 `bash` 工具在 Windows 上实际会落到 `cmd.exe` 语义，和工具名称、提示词、用户预期不一致。
3. 前端文件夹选择器手动用 `/` 拼接路径，没有使用后端返回的路径分隔符。
4. README 没有 Windows 原生 PowerShell / CMD / Git Bash / WSL 的支持边界说明。
5. 当前测试主要覆盖功能行为，没有针对平台分支、Windows 路径、shell 语义做明确回归保护。

本文档整理完整 Windows 兼容实现方案。目标不是要求 Windows 用户必须使用 WSL，而是在 Windows 原生环境下提供可预测的基础体验，同时继续保持 macOS / Linux 行为稳定。

## 兼容目标

### 基础兼容

- Windows 原生 PowerShell / CMD 环境可以安装 Python 包。
- 可以构建前端。
- 可以通过 `python run.py` 或 `py run.py` 启动后端。
- Web UI 可以加载。
- 文件树、目录选择、文件读写、目录创建/重命名/删除基本可用。
- `GET /health` 返回 `{"status": "ok"}`。

### Agent 工具兼容

- 内置命令执行工具在 Windows 上有明确 shell 语义。
- Windows 默认命令执行不再伪装成 bash。
- Agent 配置和 UI 能表达当前使用的是 Bash、PowerShell 还是 CMD。
- 旧配置中引用 `bash` 工具的 Agent 不被破坏。

### 文档和测试兼容

- README 给出 Windows 原生安装和启动命令。
- 文档说明 PowerShell、CMD、Git Bash、WSL 的差异。
- 单测覆盖平台分支和 Windows 路径处理。
- 后续可接入 `windows-latest` CI。

## 非目标

- 不保证所有用户输入的 Unix shell 命令在 Windows 原生环境自动等价转换。
- 不把 Windows 原生环境强行包装成 WSL。
- 不在本方案中重构整个工具系统。
- 不改变现有 session、team message、template 等持久化格式，除非后续实现发现确有必要。
- 不要求默认测试访问真实 LLM、MCP server 或外部 API。

## 当前风险点

### 1. 启动脚本偏 Unix

位置：

- `run.py`

问题：

- `find_processes_on_port()` 使用 `lsof -ti :<port>`，Windows 默认不存在 `lsof`。
- `stop_processes()` 使用 `signal.SIGTERM` / `signal.SIGKILL`，Windows 上语义不稳定。
- Windows 下端口被占用时，当前逻辑通常检测不到 PID，只能等 uvicorn 自己报错。
- `--kill-existing` 在 Windows 上不能稳定工作。

影响：

- Windows 用户第一次启动时如果 8000 端口被占用，错误体验差。
- README 中的一键启动承诺在 Windows 上不完整。

### 2. `bash` 工具语义不跨平台

位置：

- `bbagent/built_in_tool/bash.py`
- `bbagent/built_in_tool/policy.py`
- `frontend/src/components/agents/AgentConfigDialog.tsx`
- `frontend/src/types/index.ts`

问题：

- `asyncio.create_subprocess_shell(command)` 在 Windows 上默认使用 `cmd.exe`，不是 bash。
- 工具名称、描述和输入 schema 都写的是 Bash。
- Agent 或用户输入 `ls`, `grep`, `rm`, `export`, `VAR=value cmd` 等命令时，Windows 原生环境可能失败。
- PowerShell 与 CMD 的管道、引号、环境变量、退出码习惯也不同。

影响：

- Coding agent 在 Windows 上最核心的命令执行能力不可靠。
- 用户难以理解失败原因，因为 UI 和工具描述仍宣称是 bash。

### 3. 前端路径拼接使用 `/`

位置：

- `frontend/src/components/FolderPicker.tsx`
- `frontend/src/components/FolderPickerModal.tsx`
- 其他文件浏览/模板选择相关组件需要同步检查

问题：

- 后端 `/api/files/dirs` 已返回 `separator`，但前端没有使用。
- Windows 路径可能出现 `C:\Users\name/Desktop` 这种混合风格。
- 大多数 Windows API 可以容忍混合分隔符，但盘符根目录、UNC 路径、网络盘、根目录导航等边界风险更高。

影响：

- UI 路径展示不一致。
- 文件夹创建、重命名、删除在复杂路径下可能失败。

### 4. 文档缺少 Windows 支持边界

位置：

- `README.md`
- `doc/testing-baseline.md`

问题：

- Quickstart 只有 Unix 风格代码块，没有 PowerShell / CMD 命令说明。
- 没有说明 `bash` 工具在 Windows 原生环境下的行为。
- 没有说明推荐 shell、Git Bash、WSL、Ollama / ChromaDB 等可选能力的 Windows 注意事项。

影响：

- 用户可能按 Unix 心智在 Windows 上操作，遇到问题后难以定位。

## 实施方案

## 方案一：启动脚本跨平台

### 目标

- `python run.py` 在 Windows、macOS、Linux 上都能启动。
- `--kill-existing` 在 Windows 上可用。
- 端口占用时给出清楚诊断。

### 推荐实现

优先引入 `psutil` 作为跨平台进程和端口检测依赖：

```toml
web = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "python-multipart>=0.0.9",
    "websockets>=12",
    "psutil>=5.9",
]
```

实现思路：

```python
def find_processes_on_port(port: int) -> list[int]:
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
            if conn.pid:
                yield conn.pid
```

终止进程：

```python
proc = psutil.Process(pid)
proc.terminate()
try:
    proc.wait(timeout=timeout)
except psutil.TimeoutExpired:
    proc.kill()
```

注意事项：

- 过滤当前进程 PID，避免误杀自己。
- 捕获 `psutil.AccessDenied`，提示用户手动结束进程或换端口。
- 捕获 `psutil.NoSuchProcess`，视为已结束。
- 如果不希望新增依赖，可以使用 `platform.system()` 分支：
  - Windows：`netstat -ano` 查 PID，`taskkill /PID <pid> /T /F` 终止。
  - macOS/Linux：保留 `lsof` 和 signal 逻辑。

### 验收标准

- 端口空闲时可正常启动。
- 端口被占用且未传 `--kill-existing` 时，明确输出占用 PID。
- 端口被占用且传 `--kill-existing` 时，Windows / macOS / Linux 都能尝试终止旧进程。
- 权限不足时不静默失败。

## 方案二：命令执行工具平台感知

### 目标

- 保持旧 `bash` 工具配置不失效。
- Windows 下默认使用明确的 PowerShell 或 CMD 语义。
- 工具描述和实际 shell 保持一致。
- 允许高级用户显式选择 shell。

### 推荐设计

保留当前 `bash` 工具名作为兼容入口，但内部改造成平台感知 shell runner。

新增或扩展 `Policy` 字段：

```python
shell_kind: str = "auto"  # auto | bash | powershell | cmd
shell_executable: str | None = None
```

自动选择策略：

- Windows：
  - 优先 `pwsh`
  - 其次 `powershell`
  - 最后 `cmd`
- macOS / Linux：
  - 优先 `bash`
  - 其次 `sh`

命令执行参数：

```text
bash:       bash -lc <command>
sh:         sh -lc <command>
powershell: powershell -NoProfile -ExecutionPolicy Bypass -Command <command>
pwsh:       pwsh -NoProfile -Command <command>
cmd:        cmd /c <command>
```

实现建议：

- 新增内部函数：
  - `detect_shell(policy) -> ShellConfig`
  - `build_shell_command(shell_config, command) -> list[str]`
  - `_exec_shell_command(argv, cwd, timeout, env)`
- 优先使用 `asyncio.create_subprocess_exec(*argv)`，避免 `create_subprocess_shell` 的平台默认行为不透明。
- 输出中增加 shell 元信息，例如：

```text
[shell: powershell]
[stdout]
...
```

或仅在错误时提示当前 shell，避免输出过噪。

### UI 和兼容

短期：

- 工具仍叫 `bash`，但描述改为 “Execute a shell command. Uses bash/sh on Unix and PowerShell/CMD on Windows unless configured otherwise.”
- Agent 配置里新增 shell 选项，默认 `auto`。

中期：

- 新增正式工具名 `shell`。
- `bash` 作为 alias 或 compatibility wrapper。
- 模板和默认工具逐步迁移到 `shell`。

### 验收标准

- Windows 下简单命令可执行：
  - PowerShell: `Write-Output "hello"`
  - CMD fallback: `echo hello`
- macOS / Linux 下现有 bash 命令行为不回退。
- 超时、输出截断、cwd 不存在等现有保护仍有效。
- 旧 Agent 配置中引用 `bash` 的工具仍能加载。

## 方案三：前后端路径处理统一

### 目标

- Windows 路径不再被前端硬编码 `/` 拼接。
- 后端继续作为路径解析权威。
- UI 能在 Windows 盘符和目录层级之间稳定导航。

### 前端实现

新增路径 helper，例如 `frontend/src/lib/path.ts`：

```ts
export function joinPath(base: string, child: string, separator: string): string {
  if (!base) return child;
  if (base.endsWith("/") || base.endsWith("\\")) return `${base}${child}`;
  return `${base}${separator}${child}`;
}
```

实际实现需要覆盖：

- `/Users/alice` + `Desktop`
- `/` + `tmp`
- `C:\Users\alice` + `Desktop`
- `C:\` + `Temp`
- `\\server\share` + `folder`
- 尾部分隔符重复处理

调整组件：

- `FolderPicker`
- `FolderPickerModal`
- `TemplatePicker`
- `WorkingDirView`
- `BasedirTree`
- 其他调用 `api.createDir` / `api.renameDir` / `api.deleteDir` 的路径拼接逻辑

使用后端 `listDirs()` 返回的 `separator`：

```ts
const [separator, setSeparator] = useState("/");

const res = await api.listDirs(path);
setSeparator(res.separator || "/");
```

### 后端增强

当前 `/api/files/dirs` 返回：

```json
{
  "current": "...",
  "parent": "...",
  "separator": "...",
  "directories": [...]
}
```

建议在 Windows 下增加可选字段：

```json
{
  "drives": ["C:\\", "D:\\"]
}
```

实现方式：

- Windows 下使用 `string.ascii_uppercase` + `Path(f"{letter}:\\").exists()`。
- UI 可以在根部或下拉里显示盘符入口。

### 验收标准

- Windows 下选择 `~` 可以进入用户目录。
- Windows 下从 `C:\` 进入子目录不会生成混合路径。
- 创建、重命名、删除目录时路径正确。
- macOS / Linux 路径行为不变。

## 方案四：文件预览、编码和占用错误

### 目标

- Windows 常见编码和文件占用错误有更友好的反馈。
- 不因为单个非 UTF-8 文件导致 UI 体验过差。

### 建议

后端 `read_file` / `raw_file`：

- 文本预览可以考虑 `errors="replace"`。
- 或捕获 `UnicodeDecodeError`，返回 415 / 400，并提示文件不是 UTF-8 文本。
- 保持写入默认 UTF-8，避免持久化格式变复杂。

目录删除/重命名：

- 捕获 `PermissionError`。
- Windows 下文件被占用时，返回清楚错误：

```text
Failed to delete directory: file may be open in another application.
```

### 验收标准

- 非 UTF-8 文件预览不会导致未处理异常。
- 被占用文件/目录操作失败时，UI 可以展示明确错误。

## 方案五：MCP 子进程启动兼容

### 目标

- Windows 下 MCP server 启动失败时可诊断。
- `command` / `args` 配置语义明确。

### 建议

文档明确 MCP 配置：

```json
{
  "command": "npx",
  "args": ["some-mcp-server"]
}
```

不要写成：

```json
{
  "command": "npx some-mcp-server",
  "args": []
}
```

实现增强：

- 启动前使用 `shutil.which(command)` 定位可执行文件。
- Windows 下兼容 `.cmd` / `.bat` 包装脚本。
- 启动失败时返回：
  - platform
  - command
  - args
  - cwd，如有
  - PATH 是否找到 command

### 验收标准

- Windows 下 `npx`、`node`、`python` 类 MCP server 可以正常启动或给出明确失败原因。
- macOS / Linux 行为不变。

## 方案六：README 和开发文档

### README 新增 Windows Quickstart

建议增加 PowerShell 示例：

```powershell
git clone https://github.com/LILG98/BBagent.git
cd BBagent
py -m pip install -e ".[web]"

cd frontend
npm install
npm run build
cd ..

py run.py
```

长期记忆：

```powershell
py -m pip install -e ".[web,memory]"
```

说明：

- PowerShell 是 Windows 原生推荐 shell。
- CMD 可用，但命令语义不同。
- Git Bash / WSL 可用于运行 Unix 风格命令，但不是基础兼容的前提。
- `bash` 工具在 Windows 上默认会使用平台 shell，具体以 Agent 配置为准。

### 测试文档

在 `doc/testing-baseline.md` 增加 Windows 兼容测试说明：

```powershell
py -m pytest tests
ruff check .
mypy bbagent backend
cd frontend
npm run lint
npm run build
```

### 验收标准

- Windows 用户可以只看 README 完成安装和启动。
- 文档清楚说明 shell 工具的 Windows 语义。

## 测试方案

### Python 单测

新增测试文件建议：

- `tests/unit/test_run_windows.py`
- `tests/unit/built_in_tool/test_shell_tool.py`
- `tests/unit/backend/test_files_windows_paths.py`

覆盖点：

1. `run.py`
   - mock Windows 平台端口查找。
   - mock 端口被占用时返回 PID。
   - mock kill-existing 成功、权限不足、进程不存在。

2. shell 工具
   - mock `platform.system()`。
   - mock `shutil.which()`。
   - 验证 Windows 默认选择 `pwsh` / `powershell` / `cmd` 的顺序。
   - 验证 Unix 默认选择 `bash` / `sh`。
   - 验证构造的 argv 正确。
   - 验证旧 `bash` 工具名仍存在。

3. 路径 helper
   - 如果 helper 在 TypeScript 端，则用前端测试或把纯函数简单测试纳入后续前端测试框架。
   - 若当前没有前端测试框架，可先通过 TypeScript 编译和小型手动验证清单覆盖。

4. 后端文件 API
   - `tmp_path` 下读写/创建/重命名/删除。
   - Windows 风格字符串处理优先测试 helper，不依赖当前 OS 真实路径。

### 前端检查

当前项目没有前端测试框架时，至少运行：

```bash
cd frontend
npm run lint
npm run build
```

如果后续引入 Vitest，可优先给路径 helper 加纯函数测试。

### CI 建议

加入 GitHub Actions matrix：

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    python-version: ["3.10", "3.12"]
```

基础步骤：

- 安装 Python 包：`pip install -e ".[dev,web]"`
- Python 测试：`python -m pytest tests`
- Ruff：`ruff check .`
- MyPy：`mypy bbagent backend`
- 前端构建：`cd frontend && npm ci && npm run lint && npm run build`

注意：

- 默认 CI 不跑真实 LLM、MCP server、外部网络依赖。
- memory 依赖可以拆成单独 job，避免 Windows 上可选依赖影响基础 gate。

## 分阶段实施计划

### Phase 1：基础启动兼容

范围：

- 改造 `run.py`。
- 增加启动脚本平台分支测试。
- 更新 README Windows 启动说明。

验收：

- Windows 端口占用诊断可用。
- `--kill-existing` 在 Windows 上有确定行为。
- macOS / Linux 启动行为不变。

### Phase 2：shell 工具兼容

范围：

- 改造 `bash.py` 为平台感知 shell runner。
- 扩展 `Policy`。
- 更新后端 schema / factory 映射。
- 更新前端 Agent 配置 UI。
- 增加 shell 工具单测。

验收：

- 旧 `bash` 配置可加载。
- Windows 下 PowerShell/CMD 命令可执行。
- Unix 下 bash 行为不回退。

### Phase 3：路径处理兼容

范围：

- 前端新增路径 helper。
- 替换文件夹选择、创建、重命名、删除中的手动 `/` 拼接。
- 后端可选增加 Windows drives 字段。

验收：

- Windows 路径显示和操作稳定。
- Unix 路径行为不变。

### Phase 4：诊断和文档完善

范围：

- 文件读写错误信息增强。
- MCP 启动诊断增强。
- README 和 testing 文档补齐。

验收：

- Windows 下常见失败原因可被用户理解。
- 文档覆盖原生 Windows、Git Bash、WSL 的边界。

### Phase 5：Windows CI

范围：

- 增加 `windows-latest` CI。
- 将平台分支测试纳入默认 gate。

验收：

- PR 默认能看到 Windows 基础兼容状态。

## 最终验收清单

Windows 原生 PowerShell：

```powershell
py -m pip install -e ".[dev,web]"
cd frontend
npm install
npm run lint
npm run build
cd ..
py -m pytest tests
ruff check .
mypy bbagent backend
py run.py
```

手动 smoke：

- `GET http://localhost:8000/health` 返回 `{"status": "ok"}`。
- Web UI 可以加载。
- Settings 页面可以打开。
- 可以选择工作目录。
- 可以浏览 Windows 用户目录。
- 可以创建、重命名、删除测试目录。
- 可以创建 Agent，并启动。
- 命令执行工具在 Windows 默认 shell 下能运行简单命令。
- 如果选择 bash，需要系统已安装 Git Bash / WSL / bash，并在 UI 或错误信息中明确。

macOS / Linux 回归：

- `python -m pytest tests`
- `ruff check .`
- `mypy bbagent backend`
- `cd frontend && npm run lint && npm run build`
- `python run.py`

## 风险和取舍

### 是否引入 `psutil`

优点：

- 跨平台端口和进程管理更可靠。
- 代码比解析 `netstat` / `lsof` 更清楚。

缺点：

- 增加一个运行时依赖。
- 极少数平台安装可能有额外 wheel 兼容问题。

建议：

- 如果项目重视一键启动体验，引入 `psutil`。
- 如果坚持最小依赖，则使用平台分支命令，但测试和维护成本更高。

### shell 工具命名

保留 `bash` 的优点：

- 不破坏已有 Agent 和模板。

保留 `bash` 的缺点：

- Windows 下语义容易让用户误解。

建议：

- 短期保留 `bash`，内部平台感知。
- 中期新增 `shell`，把 UI 默认工具迁移到 `shell`。
- README 解释 `bash` 是兼容名。

### PowerShell 还是 CMD

建议默认 PowerShell：

- Windows 用户更现代的默认自动化 shell。
- Unicode 和复杂命令能力更好。

保留 CMD fallback：

- 最小 Windows 环境一定存在。

### Git Bash / WSL

建议作为可选增强：

- 用户需要 Unix 命令语义时可显式选择。
- 不作为 Windows 原生兼容的前提。

## 涉及文件清单

后端和核心：

- `run.py`
- `pyproject.toml`
- `bbagent/built_in_tool/bash.py`
- `bbagent/built_in_tool/policy.py`
- `bbagent/built_in_tool/__init__.py`
- `backend/schemas.py`
- `backend/factories/agent_factory.py`
- `backend/api/files.py`
- `bbagent/core/mcp.py`
- `backend/factories/mcp_factory.py`

前端：

- `frontend/src/types/index.ts`
- `frontend/src/components/agents/AgentConfigDialog.tsx`
- `frontend/src/components/FolderPicker.tsx`
- `frontend/src/components/FolderPickerModal.tsx`
- `frontend/src/components/TemplatePicker.tsx`
- `frontend/src/components/workspace/WorkingDirView.tsx`
- `frontend/src/components/workspace/BasedirTree.tsx`
- `frontend/src/lib/path.ts`（新增）

文档和测试：

- `README.md`
- `doc/testing-baseline.md`
- `tests/unit/test_run_windows.py`（新增）
- `tests/unit/built_in_tool/test_shell_tool.py`（新增或扩展）
- `tests/unit/backend/test_files_windows_paths.py`（新增或扩展）

## 推荐优先级

1. `run.py`：先保证 Windows 用户能稳定启动。
2. `bash` / shell runner：再保证 Agent 命令执行能力语义明确。
3. 前端路径 helper：修复文件浏览和目录操作的 Windows 边缘问题。
4. 文档：同步用户入口说明。
5. CI：把 Windows 兼容变成持续保证。
