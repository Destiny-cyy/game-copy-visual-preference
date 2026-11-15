# 版本变更记录（CHANGELOG）

> 本包按「主版本.次版本.修订号」维护，版本号单一来源见 `VERSION`。
> 只记录「包本身」的变化，与任何真实项目、真实业务数据无关。
> `v1.0.x` 为本次统一补记的版本标记，便于后续拿到包的人追溯改动；不写具体发布日期，避免与任何真实档期混淆。

---

## v1.2.0 · 文案卖点 × 图片素材用户偏好分析（主线进阶版）

把「文案卖点 × 图片素材 × 用户偏好」交叉分析做成**包内主线**，并把包整体聚焦、改名到这一主题。
**只新增能力与文档，不改旧主链任何脚本逻辑**；常规的素材复盘 / 大盘对比 / 复用衰减 / 缺口测算能力全部保留。

**新增主线能力**

- `references/copy-analysis.md`：主线方法论。两套独立标签体系（视觉判画面 / 文案判文本）、
  三个数据准备坑（人群归一、素材块继承、文案桥挂接）、五条归因铁律（曝光加权 / 同类内部比较 / 样本不足标注 /
  同素材跨人群 / 组内混杂检查）、三联图报告与结论写法、常见误判。
- `scripts/analyze_copy.py`：config 驱动，一次完成人群归一（`copy.segment_map` 有序优先级）、
  素材块继承（未标注 / 无曝光行不继承）、文案桥挂接旧台账图片标签、各人群 × 各维度曝光加权 CTR、
  同素材跨人群对比；输出 `copy_base.csv` / `copy_results.json`；挂接率与口径声明写进结果。
- `scripts/build_report_copy.py` + `assets/report_template_copy.html`：每类人群一列的三联图结论报告，
  维度 / TOP N / 配色 / 人群显示名全部由 `config.copy` 驱动，支持任意 N 类人群。
- `assets/echarts.min.js`：随包自带画图库，内嵌进 HTML，**保证双击打开、转发给别人、断网都能出图**。
- `scripts/verify_html_charts.js`：**运行级渲染验证**。用 Node 真实执行 HTML 里的画图代码，
  断言每张图都渲染出 SVG；并扫描 `<script>/<link>/<img>` 有无渲染依赖外链。
  只检查占位符 / 结构不算过——这条是针对「CDN 404 导致 4 图全空白」事故加的保险。
- `examples/copy_*.sample.*`：5 份全假样例（规划表 / 文案标签 / 旧台账 master / tagged / index），
  故意构造素材块继承、未标注行、无曝光行、挂接成功与挂接失败、同素材多人群等真实场景。

**配置（仍是唯一事实源）**

- `taxonomy` 新增 `copy_main` / `copy_hook` / `copy_tone` / `copy_confidence` / `copy_multi_separator`。
- 新增 `copy` 区块：`segment_map` / `core_segments` / `unlabeled` / `other` / `strip_markers` /
  `bridge.enabled` / `chart_dims` / `chart_topn` / `segment_colors` / `segment_display` / `short_labels`。
- `config.example.json` / `config.demo.json` / `presets/preset.A.json` / `preset.B.json` / `config.schema.md` 同步补齐；
  两套 preset 各给一套文案标签样板，演示「同一流程、两套标签」。
- 三份旧台账文件由命令行 `--master/--tagged/--index` 传入，**不写死在 config**。

**硬规矩（写进 `SKILL.md`）**

- 第 13 条：用户偏好结论**只做同类人群内部比较 / 相对该人群基线**，禁止跨人群硬比绝对 CTR。
- 第 14 条：HTML 报告**必须离线自包含**，页面显示所需资源内嵌或随包自带，禁止渲染依赖外链。
  > 边界：报告正文里给人点开看原图的 CDN 网址是内容超链接，不受此限制。
- `table-ops.md` 补「宿主安全层拦截带 `file_path` 的本地内容上传」与内联 `mdx` 分段写入的合规通道。

**主线聚焦与改名（包内外一起改）**

- 包改名为《文案卖点 × 图片素材用户偏好分析 · 分发版》（zip 文件名、包根 README 封面、包结构树根名一致）。
- `skills/ad-material-review` 目录名**不改**，避免破坏安装路径与配置路径；其 `SKILL.md` / `说明文档.md` /
  `README.md` 主线聚焦，`README.md` 包名引用同步。
- 分发侧文档全部补主线：安装与前置条件（Node 可选前置、三步空跑）、团队定制清单（必改 5→6 处补 `config.copy`）、
  避坑指南（新增 7 条主线专属坑、自检 7→11 项）、使用示例与提示词（主线提示词 + 命令行三步）、
  `examples/README.md`（主线样例与空跑）、迁移到新游戏指南（新增 Step 10 `copy` 配置、Step 11 空跑、检查清单与翻车点）。
- 主技能业务向 / 技术向说明文档新增主线章节、目录树、配置区块、避坑与自检项。
- 常规素材复盘能力保留为配套，不删不改脚本逻辑。

**复核结论**

- 自检由 7 项扩为 **11 项**（新增：HTML 离线自包含 / 运行级渲染验证 / config 换值空跑 / 版本一致）；
  「分发前 3 项自检」扩为 **5 项**（新增：HTML 零外链、跑 `verify_html_charts.js` 确认图能画出来）。
- 脱敏 0 命中；3 个 `SKILL.md` frontmatter 规范；脚本零第三方依赖（可选验证脚本用 Node，不装不影响主流程）；
  全部 `.py` 语法通过、全部 JSON 可解析；常规三条 + 主线三步离线空跑通过；
  三联图报告零外链、4 图运行级渲染通过；换一套假值配置后主线仍跑通；
  `VERSION` / `CHANGELOG.md` / `README.md` 三处版本号一致。

---

## v1.1.0 · 分发就绪版

面向「可作为分发版交付」的复核与补齐，**仅补规范层，不改动任何脚本逻辑与方法论**。

**新增**

- `LICENSE`：使用许可（MIT），明确可自由使用 / 修改 / 二次分发，以及分发方需替换的占位。
- `VERSION`：当前版本号的单一来源。
- `CHANGELOG.md`：本文件，让版本可追溯。
- `.gitignore`：防止真实 `config.json` / `spec.json`、运行时 `data/`、素材图、空跑产物、Python 缓存被误提交或误打包。

**文档**

- 总 `README.md`：顶部标注版本；包结构树补齐新增文件；自检记录由「交付前 3 项」升级为「分发版 7 项」；新增「版本 / 许可 / 维护与反馈」与「分发前 3 项自检」。
- `examples/README.md`：补充「示例里的日期也是编造的」说明，避免把 `2026-01` 误读成真实投放档期。
- `skills/ad-material-review/README.md`：分层视图里 `schema.md` 的简写改为真实文件名 `config.schema.md`。

**复核结论**

- 脱敏 0 命中；3 个 `SKILL.md` 的 frontmatter 规范；脚本零第三方依赖；离线空跑可跑通；zip 完整；包内文件与构建目录逐一一致。

---

## v1.0.1

- 新增 `skills/ad-material-review/README.md`（技术向：作用 / 用法 / 工作流 / 项目架构 / 数据契约 / 扩展点）。
- 修复 `分享包文档/使用示例与提示词.md` 中一处遗留的真实表格名，改为占位。

---

## v1.0.0 · 首版

- 由多套实际使用过的 skill 合并、脱敏、抽象为 3 个通用 Skill：`ad-material-review` / `channel-resource-table` / `retrospective`。
- 建立 config 驱动架构（换游戏只改配置、不动脚本）、8 个脚本、5 份方法论文档、报告模板、两套标签预设。
- 交付分享包四件套、总 README、迁移指南、全假数据 `examples/`。
