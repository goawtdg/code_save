# 缓存省 Token 实验说明

本实验用于验证：**同一需求重复执行时，safe-codegen 因命中 L1/L2 缓存，总 token 显著低于基线或第 2/3 轮骤降**。

---

## 一、环境变量（建议）

为便于对比，建议**只开主后端、关闭验证后端**：

- 主后端：智谱（或 DeepSeek）一套即可。
- 关闭验证：在 `.env` 中注释掉 `SAFE_CODEGEN_VALIDATION_BACKEND`、`SAFE_CODEGEN_VALIDATION_BASE_URL`、`SAFE_CODEGEN_VALIDATION_API_KEY`。

**是否需要你改？** 若当前已是「单后端、无验证」，则无需改；若开着双后端，请注释掉验证相关行后再跑实验。

---

## 二、全新实验步骤（推荐）

### 1. 清空旧缓存（可选但推荐）

在项目根目录删除 `data`，保证实验从零开始：

```powershell
Remove-Item -Recurse -Force data
```

（若目录不存在可忽略。）

### 2. 运行「缓存省 token」专用实验

```powershell
conda activate code_env
cd d:\py\code

python scripts/run_cache_savings_experiment.py --out cache_savings.csv
```

- 同一 prompt 跑 3 轮基线 + 3 轮实验组，共 6 行。
- 实验组：第 1 轮建基座+模块（多 LLM），第 2、3 轮命中 L1+L2 缓存，仅 L3 调用。

### 3. 汇总分析

```powershell
python scripts/analyze_experiment.py cache_savings.csv
```

关注：

- **Token saving rate**：若为正值，表示实验组平均总 token 少于基线。
- **实验组第 2、3 轮**：在 CSV 中查看「总tokens」应明显小于第 1 轮；`foundation是否变` 为「否」。

---

## 三、用原有脚本做同一任务 3 轮

也可用通用实验脚本，只跑任务 0、3 轮：

```powershell
Remove-Item -Recurse -Force data
python scripts/run_experiment.py --rounds 3 --task 0 --out exp_task0_r3.csv
python scripts/analyze_experiment.py exp_task0_r3.csv
```

结论判定方式同上：看实验组第 2、3 轮总 token 是否骤降、foundation 是否不变。

---

## 四、预期结果

- **第 1 轮**：实验组总 token 通常高于基线（建基座 + 模块 + L3）。
- **第 2、3 轮**：实验组仅 L3 调用，总 token 应远小于第 1 轮，且有机会低于基线单轮。
- **Foundation 稳定性**：实验组 3 轮中仅 1 次「是」，其余为「否」。

满足上述即说明「基座固定 + 命中缓存省 token」达到预期。
