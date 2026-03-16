# safe-codegen 对比实验指南

按下面步骤跑完实验并整理数据，即可证明项目达到「省 token + 基座干净合规」的预期效果。

---

## 一、实验前准备（约 10 分钟）

### 1. 环境与依赖

```powershell
conda activate code_env
cd D:\py\code
pip install -e .
pip install bandit
```

### 2. 配置 .env

确保 `.env` 中已配置**一套** API（智谱或 DeepSeek 二选一），例如：

```env
SAFE_CODEGEN_BACKEND=openai
SAFE_CODEGEN_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
SAFE_CODEGEN_OPENAI_MODEL=glm-4-flash
OPENAI_API_KEY=你的API_KEY
```

### 3. 快速试跑（可选）

先跑 1 轮、只做基线组，确认 API 和 bandit 正常：

```powershell
python scripts/run_experiment.py --rounds 1 --group baseline --task 0
```

再跑 1 轮实验组、同一任务：

```powershell
python scripts/run_experiment.py --rounds 1 --group experiment --task 0
```

若两者都正常结束并生成 CSV，即可进行正式实验。

---

## 二、正式对比实验（3 任务 × 3 轮 × 2 组）

### 一键跑全量

在项目根目录执行：

```powershell
python scripts/run_experiment.py --rounds 3 --out experiment_results.csv
```

- 会依次跑：任务 0 / 1 / 2，每个任务下基线组 3 轮 + 实验组 3 轮，共 **18 行** 结果写入 `experiment_results.csv`。
- 若不想跑 bandit，可加 `--no-bandit`（安全违规数列会为 N/A）。

### 只跑部分（节省时间）

```powershell
# 只跑任务 0，3 轮，两组
python scripts/run_experiment.py --rounds 3 --task 0 --out exp_task0.csv

# 只跑实验组、任务 1、1 轮
python scripts/run_experiment.py --rounds 1 --group experiment --task 1 --out exp_single.csv
```

---

## 三、分析结果、证明预期效果

### 1. 用自带分析脚本（推荐）

项目提供汇总脚本，直接算「平均 tokens、节省率、安全违规对比」：

```powershell
python scripts/analyze_experiment.py experiment_results.csv
```

会输出类似：

- 基线组 / 实验组：平均输入、输出、总 tokens
- **Token 节省率** = (基线总 tokens − 实验总 tokens) / 基线总 tokens
- 安全违规数：基线 vs 实验（若未装 bandit 则显示 N/A）
- foundation 是否变化：实验组第 2、3 轮应为「否」

可直接把终端输出贴进报告。

### 2. 用 Excel 手动分析

1. 用 Excel（或 WPS）打开 `experiment_results.csv`。
2. **按组别筛选**：
   - 筛选「组别」=「基线组」→ 对「总tokens」列求**平均值**，记为「基线平均 tokens」。
   - 筛选「组别」=「实验组(safe-codegen)」→ 对「总tokens」列求**平均值**，记为「实验组平均 tokens」。
3. **算 Token 节省率**：
   ```
   Token 节省率 = (基线平均 tokens − 实验组平均 tokens) / 基线平均 tokens
   ```
   若为正数，即说明实验组更省 token。
4. **画图（轮次 vs 总 tokens）**：
   - 横轴：轮次（1、2、3）
   - 纵轴：总 tokens
   - 两条折线：基线组、实验组（可按任务分别画，或同一图里用不同颜色）。
   - 预期：实验组在第 2、3 轮明显低于基线（体现缓存/复用效果）。
5. **安全与基座**：
   - 对比「安全违规数」列：基线组常有 1～3，实验组目标 0。
   - 对比「foundation是否变」：实验组第 2、3 轮应为「否」，说明基座未被动摇。

---

## 四、预期结论（用于写报告）

| 指标 | 预期 | 如何验证 |
|------|------|----------|
| **Token 节省** | 第 1 轮实验组可能略多；第 2、3 轮明显少于基线，整体可省约 50%～70% | 看「总tokens」均值与节省率、折线图 |
| **基座干净** | 实验组 foundation 只建一次，后续轮次不变 | 「foundation是否变」第 2、3 轮为「否」 |
| **安全合规** | 实验组 Bandit 违规数 ≤ 基线组，目标 0 | 对比「安全违规数」列 |

---

## 五、可选：多轮漂移验证（第 5～6 天）

用**同一 TODO 项目**连续加 5 轮新功能（登录、导出 Excel、Webhook 等），观察：

- **实验组**：`data/foundation.json` 不变，第 2 轮起 tokens 明显下降。
- **基线组**（若用同一项目不断追加）：代码易乱、安全问题易累积。

操作思路：对任务 0 跑 6 轮，第 1 轮 prompt 为「生成 FastAPI TODO…」，第 2～6 轮 prompt 为「在现有 TODO 项目上添加 XXX 功能」；实验组不清空 `data/`，基线组每次重新生成。当前脚本为「每任务 round 0 清空 data」，若要严格做 6 轮漂移，可先只跑实验组、`--rounds 6`、`--task 0`，并修改脚本使仅第 1 轮 `clear_data=True`（或单独写一个小脚本跑 6 轮同一任务、不清 data）。

---

## 六、时间线小结

| 阶段 | 操作 | 产出 |
|------|------|------|
| 第 1 天 | 准备环境、.env、试跑 1 轮 | 能跑通 baseline + experiment |
| 第 2～3 天 | 全量实验：`--rounds 3 --out experiment_results.csv` | experiment_results.csv |
| 第 4 天 | 运行 `analyze_experiment.py` + Excel 画图 | 节省率、折线图、安全对比 |
| 第 5～6 天（可选） | 多轮漂移 6 轮同一任务 | 证明 foundation 不变、tokens 暴跌 |
| 第 7 天 | 整理数据、写总结报告 | 实验报告 + 结论 |

跑完第二步、第四步并保存好 CSV 与脚本输出，即可证明项目达到预期效果。
