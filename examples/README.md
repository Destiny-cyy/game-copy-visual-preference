# examples —— 示例数据（全部为编造，可安全外发）

> ⚠️ 本目录所有数字、游戏名、图片链接、人群分层、**日期**都是**编的假数据**，只用来让你在不接真实数据源的情况下，把脚本空跑一遍、确认「配置读得到、脚本能跑通、产物长这样」。
> 和任何真实项目、真实业务数据没有任何关系。
> 表里的 `2026-01` 这类年月只是为了让「按月分组」能跑出结果，**不代表任何真实投放档期**，正式使用时会被你的真实数据整批替换掉。

## 文件清单

### 常规素材复盘（旧主链，仍完整保留）

| 文件 | 是什么 | 对应脚本 |
|---|---|---|
| `config.demo.json` | 一份「填好」的示例配置，指向本目录的假数据（含 `copy` 主线区块） | 所有脚本 |
| `master.sample.csv` | 投放明细主表（含复用：一张图被多条记录投） | `fetch_materials.py` 的产出形态 |
| `labels.sample.json` | 逐张看图打标的结果 | `label_merge.py` 的输入形态 |
| `tagged.sample.csv` | 打标回填后的明细（分析主输入） | `analyze.py` / `reuse_map.py` |
| `bench.json` | 大盘「游戏 × 月」聚合（假） | `benchmark.py` |
| `bench_materials.json` | 大盘「单条素材」明细（假） | `benchmark.py` |

### ⭐ 主线：文案卖点 × 图片素材用户偏好分析（本版新增）

| 文件 | 是什么 | 对应脚本 |
|---|---|---|
| `copy_planning.sample.csv` | 投放规划表（含**素材块继承**：一条素材拆多行、文案/图只在首行；含未标注 / 无曝光行） | `analyze_copy.py` |
| `copy_labels.sample.json` | 逐条文案打标结果（主卖点 / 行动钩子 / 语气句式 / 置信度） | `analyze_copy.py` |
| `copy_master.sample.csv` | 旧台账主表（用来做「文案桥」匹配） | `analyze_copy.py --master` |
| `copy_tagged.sample.csv` | 旧台账已回填的图片视觉标签 | `analyze_copy.py --tagged` |
| `copy_index.sample.csv` | 旧台账素材 ID → 原图链接索引 | `analyze_copy.py --index` |

样例里**故意**留了几种真实会遇到的情况，方便验证脚本有没有处理对：素材块继承、未标注人群行、无曝光行、
文案桥匹配成功、2 条新文案挂接失败、同一素材投给多类人群。

## 三分钟空跑（不需要联网、不需要在线表格授权）

**从包根目录执行**（就是能看到 `README.md` 和 `examples/` 文件夹的那一层）：

### 常规三条（素材复盘主链）

```bash
# 1. 用示例配置跑分析（读假 tagged 数据）
python skills/ad-material-review/scripts/analyze.py \
  --config examples/config.demo.json \
  --csv examples/tagged.sample.csv \
  --out examples/out/analysis.json

# 2. 跑大盘双口径对比
python skills/ad-material-review/scripts/benchmark.py \
  --config examples/config.demo.json \
  --data-dir examples \
  --out examples/out/benchmark.json

# 3. 跑复用衰减明细
python skills/ad-material-review/scripts/reuse_map.py \
  --config examples/config.demo.json \
  --master examples/master.sample.csv \
  --tagged examples/tagged.sample.csv \
  --out examples/out/reuse_map.csv
```

### ⭐ 主线三步（文案卖点 × 图片素材用户偏好分析）

```bash
# 1. 归一人群 + 素材块继承 + 文案桥挂接旧图标签 + 各人群交叉分析
python skills/ad-material-review/scripts/analyze_copy.py \
  --config examples/config.demo.json \
  --planning examples/copy_planning.sample.csv \
  --labels examples/copy_labels.sample.json \
  --master examples/copy_master.sample.csv \
  --tagged examples/copy_tagged.sample.csv \
  --index examples/copy_index.sample.csv \
  --out-base examples/out/copy_base.csv \
  --out-json examples/out/copy_results.json

# 2. 生成三联图结论报告（画图库内嵌，离线自包含）
python skills/ad-material-review/scripts/build_report_copy.py \
  --config examples/config.demo.json \
  --results examples/out/copy_results.json --out examples/out/copy_report.html

# 3.（可选，需装 Node）运行级验证：确认报告里的图真的画得出来
node skills/ad-material-review/scripts/verify_html_charts.js examples/out/copy_report.html 4
```

跑完看 `examples/out/`：

- 常规三条 → `analysis.json` / `benchmark.json` / `reuse_map.csv`，确认整套流程的形状。
- 主线三步 → `copy_base.csv`（归一+继承+挂接后的底表）、`copy_results.json`（各人群基线 / 各维度 TOP / 挂接率 / 同素材跨人群）、
  `copy_report.html`（每类人群一列的三联图结论报告）。
- 第 3 步会真实执行 HTML 里的画图代码，报「4 图全渲染」才算过；**不装 Node 也能跑完前两步**，只是少了这道白屏保险。

> **Windows 用户**：把命令里的 `\` 换行去掉、写成一行即可；或用 PowerShell 的反引号 `` ` `` 换行。
> 跑不通先检查两件事：① 是不是站在包根目录执行的；② Python 版本（需 3.8+）。
> 脚本会自动把 `scripts/` 加入模块搜索路径，所以不用额外配置 `PYTHONPATH`。

> `fetch_materials.py` / `write_smarttable.py` 依赖在线表格授权，**不需要**在空跑里执行；
> 它们只在「接真实数据源」时才用，语法已通过校验。
>
> `examples/out/` 是空跑产物目录（已被 `.gitignore` 排除），可随时清空重建，**不会进分发包**。
