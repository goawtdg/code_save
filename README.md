### 项目简介

`safe-codegen` 是一个基于 **LangGraph** 的三层多代理代码生成与防护系统，通过「分层防御 + 渐进式缓存」机制在保持高效代码生成的同时，降低病毒式污染风险。

**双目标（写项目时）：**

| 目标 | 含义 | 实现方式 |
|------|------|----------|
| **语义不偏移** | 产出与用户需求一致，无需求漂移、无范围蔓延 | 基座锁定 + 各层 prompt 显式约束「语义不偏移」；L2 生成/打分、L3 验收均带入 `user_request` 做对齐评估 |
| **Token 节约** | 少调用、少重试，总 token 可控 | 基座与增量缓存（同请求命中即复用）；验证模型仅用于 L1 安全审计 + L3 验收，减少重试与重复生成 |

核心包含三层：
- **Layer 1: 基座净化层** — 校验初始代码基座，生成形式化契约并锁定为不可变基座。
- **Layer 2: 模块监督层** — FastCoder 风格模块增量生成与监督，支持版本化增量缓存与回滚；生成与打分均约束语义不偏移。
- **Layer 3: 全局收敛层** — 全局一致性校验、语义对齐与风险评估，输出最终报告与结果。

---

### 一、使用 conda 创建并进入 `code_env`

在 Windows PowerShell 中执行（确保已安装 Anaconda/Miniconda）：

```powershell
conda create -n code_env python=3.11 -y
conda activate code_env
```

之后每次使用本项目前，只需：

```powershell
conda activate code_env
```

---

### 二、安装依赖（pip 为主，uv 可选）

#### 1. 使用 pip 安装

在已激活的 `code_env` 环境下，进入本项目根目录（例如 `d:\py\code`）：

```powershell
cd d:\py\code
pip install -e .
```

这会根据 `pyproject.toml` 安装运行所需依赖。

如需安装开发/测试依赖（包括 pytest 等）：

```powershell
pip install -e .[dev]
```

#### 2. 可选：使用 uv 安装

如果你习惯使用 `uv`，可以在已激活的 `code_env` 中先安装 `uv`：

```powershell
pip install uv
```

然后在项目根目录执行：

```powershell
uv pip install -e .
uv pip install -e .[dev]
```

> 说明：项目的依赖声明仍以 `pyproject.toml` 为主，`uv` 只是更快的安装工具。

---

### 三、环境变量配置

在项目根目录创建 `.env` 文件（或复制 `cp .env.example .env` 后修改），至少配置：

```env
OPENAI_API_KEY=your_openai_api_key_here
```

如果使用本地 Ollama/Llama 模型，可额外配置：

```env
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3
```

**智谱 / DeepSeek（OpenAI 兼容 base_url）**

使用智谱或 DeepSeek 时，设置 `SAFE_CODEGEN_BACKEND=openai` 并指定 base_url 与模型即可：

```env
SAFE_CODEGEN_BACKEND=openai
OPENAI_API_KEY=你的智谱或DeepSeek的API_KEY

# 智谱 GLM-4
SAFE_CODEGEN_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
SAFE_CODEGEN_OPENAI_MODEL=glm-4-flash

# 或 DeepSeek（官网 / 阿里云百炼等）
# SAFE_CODEGEN_OPENAI_BASE_URL=https://api.deepseek.com
# SAFE_CODEGEN_OPENAI_MODEL=deepseek-chat
```

项目中的 LLM 适配层会根据配置自动选择 OpenAI、Ollama 或上述兼容端点。

> **两个 API Key（智谱 + DeepSeek）怎么放？**  
> 一次运行只用一套 API：要么用智谱，要么用 DeepSeek。在 `.env` 里只保留一套配置（`OPENAI_API_KEY` + 对应的 `SAFE_CODEGEN_OPENAI_BASE_URL` 和 model）。要做两次实验时，改这几行再跑即可。根目录有 `.env.example` 模板可参考。

---

### 四、核心目录结构（规划）

项目采用 `src` layout：

- `src/safe_codegen/` — 核心包
  - `config.py` — 配置与阈值管理
  - `llm/` — LLM 适配层（OpenAI、Ollama）
  - `agents/` — 三层多代理逻辑
  - `cache/` — 基座与增量缓存实现
  - `graph/` — LangGraph 状态、节点与构建器
  - `runner.py` — CLI 入口和 demo 流程
- `tests/` — Pytest 测试

后续文件会按上述规划逐步完善。

---

### 五、运行一个最小示例（待实现）

在依赖安装完成、环境变量配置正确后，可以直接运行：

```powershell
safe-codegen --prompt "为一个 FastAPI TODO 应用生成安全的项目骨架"
```

或直接通过 Python 调用：

```powershell
python -m safe_codegen.runner --prompt "为一个 FastAPI TODO 应用生成安全的项目骨架"
```

你也可以使用自带脚本运行一个简单 demo：

```powershell
python scripts/run_demo.py
```

当前仓库已经提供一个 **可运行的三层 LangGraph demo**：当环境变量 `SAFE_CODEGEN_BACKEND=mock` 时，所有 LLM 调用都会使用本地 mock 后端，不依赖外部 API，方便在离线环境中验证整体流程。

---

### 六、运行测试

在已安装开发依赖的前提下：

```powershell
pytest
```

部分测试会在未检测到 `OPENAI_API_KEY` 或本地 Ollama 服务时自动跳过真实模型调用，仅测试接口与数据流。

---

### 七、多 API 交叉验证以节约 Token

通过「主 API 生成 + 验证 API 关键节点把关」的方式，可以减少因误判导致的重试和重复调用，从而在保证质量的前提下节约 token。

**策略简述：**

- **主 API（便宜/本地）**：承担 Layer 1 基座正确性评审、Layer 2 模块生成与初评等大量调用。
- **验证 API（贵一点或另一家）**：参与 Layer 1 基座安全审计（双模型验证）、Layer 3 最终验收（完整性、可用性、安全合规）；一致则通过，避免不必要的重试。

**三阶段模型分工（配置 `SAFE_CODEGEN_VALIDATION_*` 后生效）：**

| 阶段 | 说明 | 主模型 | 验证模型 |
|------|------|--------|----------|
| **基座** | 双模型验证纯净后固定 | CorrectnessCritic（正确性） | SecurityAuditor（安全审计） |
| **中间增量** | 由一个模型完成 | 模块生成 + 模块打分 | 不参与 |
| **最后验收** | 另一模型验证完整性、可用性、安全合规 | 可选交叉校验 | 主审，决定是否通过 |

未配置验证后端时：基座两个评审均用主模型；验收仅用主模型，行为与原先一致。

**建议配置 2 个 API 即可：**

1. **主后端**：`gpt-4o-mini` 或本地 Ollama，用于日常生成与初评。
2. **验证后端**：在 Layer 3 全局收敛（或关键模块打分）时再调用一次更强模型或另一家 API；若与主后端结论一致，则直接通过，减少整条链路重试。

**环境变量示例（开启验证后端时）：**

```env
# 主后端：日常生成与初评
SAFE_CODEGEN_BACKEND=openai
OPENAI_API_KEY=sk-...

# 可选：验证后端 — 基座 Layer1 安全审计（双模型之一）+ 最后验收 Layer3 主审
# SAFE_CODEGEN_VALIDATION_BACKEND=openai
# SAFE_CODEGEN_VALIDATION_BASE_URL=https://api.deepseek.com
# SAFE_CODEGEN_OPENAI_VALIDATION_MODEL=deepseek-chat
# SAFE_CODEGEN_VALIDATION_API_KEY=sk-...
```

**实验验证（概览）**

- **同一任务多轮重复（单 API）**：  
  - 任务：反复生成「安全的 FastAPI TODO 完整项目（CRUD+SQLite）」。  
  - 结果：实验组首轮总 tokens ≈ 3761，高于基线（≈ 835）；第 2、3 轮因命中基座与模块缓存，总 tokens ≈ 740，已接近/略优于基线。  
  - 结论：在重复同一需求场景下，第 2 轮起开始显著摊薄多层校验成本。

- **多轮真实迭代（单 API，多任务漂移实验）**：  
  - 任务：在同一个 TODO 项目上连续加 JWT、中间件、安全上传、导出 Excel、Webhook、审计日志等功能。  
  - 结果汇总（`drift_results.csv`）：  
    - 基线（增量版本，每轮重写全项目）平均总 tokens ≈ **2615**。  
    - 实验组（首尾 full，中间 light + 基座/模块缓存）平均总 tokens ≈ **2062**。  
    - Token 节省率约 **21.1%**，且 6 轮中仅首轮 foundation 发生变化（后续全部复用同一基座）。  

- **多轮真实迭代（主 API + DeepSeek 验证 API）**：  
  - 配置：主后端使用智谱（生成/初评），验证后端使用 DeepSeek（L1 安全审计 + L3 最终验收）。  
  - 结果汇总（`drift_results_dual.csv`）：  
    - 基线平均总 tokens ≈ **2498**。  
    - 实验组平均总 tokens ≈ **2464**，Token 节省率约 **1.3%**。  
    - foundation 仅首轮变更，证明在引入验证模型成本后，多轮平均 token 仍不高于增量基线。

**实验 CSV 示例片段**

重复同一任务三轮的缓存实验（`cache_savings.csv`）示例：

```text
任务,轮次,组别,输入tokens,输出tokens,总tokens,安全违规数,foundation是否变,备注
生成安全的 FastAPI TODO 完整项目（CRUD + SQLite）,1,基线组,49,778,827,N/A,-,
生成安全的 FastAPI TODO 完整项目（CRUD + SQLite）,2,基线组,49,702,751,N/A,-,
生成安全的 FastAPI TODO 完整项目（CRUD + SQLite）,3,基线组,49,878,927,N/A,-,
生成安全的 FastAPI TODO 完整项目（CRUD + SQLite）,1,实验组(safe-codegen),671,3090,3761,N/A,是,status=success
生成安全的 FastAPI TODO 完整项目（CRUD + SQLite）,2,实验组(safe-codegen),176,562,738,N/A,否,status=success
生成安全的 FastAPI TODO 完整项目（CRUD + SQLite）,3,实验组(safe-codegen),176,570,746,N/A,否,status=success
```

如需查看完整实验脚本与更详细的数据分析，请参考 `scripts/run_cache_savings_experiment.py`、`scripts/run_drift_experiment.py` 以及 `docs/EXPERIMENT_CACHE_SAVINGS.md`、`docs/EXPERIMENT_GUIDE.md`。

