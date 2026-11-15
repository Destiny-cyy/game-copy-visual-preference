#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「文案卖点 × 图片素材 × 用户偏好」结论报告 HTML（离线自包含）。

读 analyze_copy.py 产出的 copy_results.json + config，套 assets/report_template_copy.html，
产出每类人群一列的 TOP-N 三联图（红虚线=该人群基线、条形右侧 CTR 与 n）。

⭐ HTML 离线自包含：画图库 assets/echarts.min.js **内嵌进 HTML**，零 CDN 外链——
   双击打开 / 转发给别人 / 断网都能出图。交付前用 scripts/verify_html_charts.js 跑运行级验证。

用法（包根目录空跑）:
  python skills/ad-material-review/scripts/build_report_copy.py \
    --config examples/config.demo.json \
    --results examples/out/copy_results.json \
    --out examples/out/copy_report.html
  # 再验证（期望图数 = chart_dims 个数，缺省 4）
  node skills/ad-material-review/scripts/verify_html_charts.js examples/out/copy_report.html 4
"""
import argparse
import datetime
import json
import os

from config_loader import load_config, add_config_arg

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
_TEMPLATE = os.path.join(_PKG, "assets", "report_template_copy.html")
_LIB = os.path.join(_PKG, "assets", "echarts.min.js")


def topn(dim_data, seg, k):
    items = list(dim_data.get(seg, {}).items())
    items.sort(key=lambda kv: -kv[1]["ctr"])
    return items[:k]


def main():
    ap = argparse.ArgumentParser(description="生成文案×图片用户偏好结论报告 HTML")
    add_config_arg(ap)
    ap.add_argument("--results", default="./data/copy_results.json")
    ap.add_argument("--out", default="./data/copy_report.html")
    args = ap.parse_args()

    cfg = load_config(args.config)
    cp = cfg["copy"]
    tax = cfg["taxonomy"]
    proj = cfg.get("project", {})
    with open(args.results, encoding="utf-8") as f:
        res = json.load(f)

    order = res["core_segments"]
    colors = res.get("segment_colors", {})
    display = cp.get("segment_display", {})
    short = cp.get("short_labels", {})
    topn_k = cp.get("chart_topn", 3)
    chart_dims = cp.get("chart_dims", [
        {"key": "copy_main", "title": "主卖点", "note": "主卖点单选，判文案主句。"},
        {"key": "copy_hook", "title": "行动钩子", "note": "行动钩子多选，一条文案可命中多个。"},
        {"key": "benefit", "title": "福利呈现", "note": "图片维度（文案桥挂接的视觉标签）。"},
        {"key": "style", "title": "画风", "note": "图片维度（文案桥挂接的视觉标签）。"},
    ])
    palette = ["#58a6ff", "#e3b341", "#3fb950", "#bc8cff", "#f0883e", "#56d4dd"]
    seg_color = {seg: colors.get(seg, palette[i % len(palette)]) for i, seg in enumerate(order)}
    seg_display = {seg: display.get(seg, seg) for seg in order}

    def sname(k):
        return short.get(k, k)

    # 每个维度：每人群 TOP-N 数据
    chart_data, titles = {}, {}
    for d in chart_dims:
        key, title = d["key"], d.get("title", d["key"])
        titles[key] = title
        one = {}
        dim_data = res["dims"].get(key, {})
        for seg in order:
            items = topn(dim_data, seg, topn_k)
            one[seg] = {
                "names": [sname(k) for k, _ in items],
                "ctrs": [x["ctr"] for _, x in items],
                "ns": [x["n"] for _, x in items],
                "base": res["overall"][seg]["ctr"],
                "color": seg_color[seg],
            }
        chart_data[key] = one

    # 图表区块：标题栏（每人群一列）+ 图容器 + 说明
    sections = []
    for d in chart_dims:
        key = d["key"]
        cols = "".join(
            '<div style="color:%s">%s<small>基线 %.2f%% · 红虚线</small></div>' % (
                seg_color[seg], seg_display[seg], res["overall"][seg]["ctr"])
            for seg in order)
        sections.append(
            '<div class="cbox"><div style="font-weight:600;margin-bottom:2px">图 · %s TOP-%d CTR</div>'
            '<div class="chartcols">%s</div><div id="chart_%s" style="height:390px"></div>'
            '<div class="note">%s</div></div>' % (
                d.get("title", key), topn_k, cols, key, d.get("note", "")))

    draw_calls = "\n".join("draw('chart_%s', CHART_DATA['%s']);" % (d["key"], d["key"])
                           for d in chart_dims)

    # 顶部人群基线 chips
    seg_chips = "".join(
        '<div class="chip"><span style="color:%s">■</span> %s 基线 <b>%.2f%%</b></div>' % (
            seg_color[seg], seg_display[seg], res["overall"][seg]["ctr"])
        for seg in order)

    # 同素材跨人群表
    cross_head = "".join('<th class="num">%s</th>' % seg_display[seg] for seg in order)
    cross_rows = []
    for e in res["cross"]["samples"][:8]:
        cells = ""
        for seg in order:
            x = e["by_segment"].get(seg)
            if x:
                cls = "good" if x["vs_base"] > 0 else "bad"
                cells += '<td class="num">%.2f%% <span class="%s">(n=%d, %+.2fpp)</span></td>' % (
                    x["ctr"], cls, x["n"], x["vs_base"])
            else:
                cells += '<td class="num">—</td>'
        cross_rows.append('<tr><td>%s</td><td>%s</td><td>%s</td>%s</tr>' % (
            e["material_id"], e["style"] or "—", e["benefit"] or "—", cells))

    # 核心结论（通用化措辞，不含任何真实游戏/平台/业务数字）
    concl = []
    # 结论1：各类人群内最强的主卖点（相对基线提升最大、且样本足够者优先）
    hi = []
    for seg in order:
        items = topn(res["dims"].get("copy_main", {}), seg, 1)
        if items:
            k, x = items[0]
            hi.append("%s：<b>%s</b> %.2f%%（%+.2fpp，n=%d）" % (
                seg_display[seg], sname(k), x["ctr"], x["vs_base"], x["n"]))
    concl.append('<div class="cbox"><span class="tag t-g">结论① 各人群最吃的主卖点不同</span>'
                 '<div>%s</div><p>均为同类人群内部、相对该人群基线的比较；跨人群的绝对值不可直接对比。</p></div>'
                 % ("；".join(hi) if hi else "主卖点维度暂无足够数据。"))
    # 结论2：钩子维度，找普遍偏弱 / 偏强的方向
    hook_note = "行动钩子为多选口径，一条文案可命中多个；建议结合样本量看，n 小的组只作方向参考。"
    concl.append('<div class="cbox"><span class="tag t-r">结论② 行动钩子要看「相对基线」</span>'
                 '<div>图·行动钩子 中超过红虚线的钩子才是真正带来增量的方向；把所有人群拉平看绝对 CTR 会误判'
                 '（人群精准度不同）。</div><p>%s</p></div>' % hook_note)
    # 结论3：图片维度
    concl.append('<div class="cbox"><span class="tag t-b">结论③ 图片维度（福利/画风）</span>'
                 '<div>图片结论基于文案桥挂接的视觉标签（挂接率 %.1f%%），未挂接记录不参与；'
                 '与文案维度是两条独立的线，互不污染。</div>'
                 '<p>福利呈现、画风各人群 TOP 见下方图；若某卖点特别强，记得做组内混杂检查（见 copy-analysis.md 第五节）。</p></div>'
                 % res["meta"]["bridge_rate"])
    # 结论4：通吃素材 / 样本
    concl.append('<div class="cbox"><span class="tag t-p">结论④ 通吃素材与样本边界</span>'
                 '<div>同素材跨人群共 %d 组，第三节表里各类人群都跑赢自己基线（绿色 pp）的是「通吃素材」，可优先复用；'
                 '全红的是偏科/不建议复用。</div><p>n &lt; %d 的组均标注「样本不足」，只作方向性结论，不宜直接作为投放决策。</p></div>'
                 % (res["cross"]["group_count"], res["min_sample"]))

    meta = res["meta"]
    scope = ("%s 条曝光记录 / %d 张唯一素材ID / %d 类核心人群 · 区间 %s · 来源只读快照（原表未改动）"
             % (meta["total_rows"], meta["unique_material_ids"], len(order),
                proj.get("period", "<数据区间>")))

    with open(_TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    with open(_LIB, encoding="utf-8") as f:
        lib = f.read()

    repl = {
        "__ECHARTS_LIB__": lib,
        "__GAME_NAME__": proj.get("game_name", "<游戏名>"),
        "__PLATFORM__": proj.get("platform", "<平台>"),
        "__SCOPE__": scope,
        "__CORE_N__": str(len(order)),
        "__REC_ROWS__": str(meta["total_rows"]),
        "__UNIQ_MAT__": str(meta["unique_material_ids"]),
        "__BRIDGE_RATE__": "%.1f" % meta["bridge_rate"],
        "__MIN_SAMPLE__": str(res["min_sample"]),
        "__TOPN__": str(topn_k),
        "__SEG_CHIPS__": seg_chips,
        "__CONCLUSIONS__": "\n  ".join(concl),
        "__CHART_SECTIONS__": "\n  ".join(sections),
        "__CROSS_N__": str(res["cross"]["group_count"]),
        "__CROSS_HEAD__": cross_head,
        "__CROSS_ROWS__": "\n".join(cross_rows),
        "__APPENDIX_MAIN__": " / ".join(tax.get("copy_main", [])),
        "__APPENDIX_HOOK__": " / ".join(tax.get("copy_hook", [])),
        "__APPENDIX_TONE__": " / ".join(tax.get("copy_tone", [])),
        "__GEN_DATE__": datetime.date.today().isoformat(),
        "__ORDER__": json.dumps(order, ensure_ascii=False),
        "__DISPLAY__": json.dumps(seg_display, ensure_ascii=False),
        "__CHART_TITLES__": json.dumps(titles, ensure_ascii=False),
        "__CHART_DATA__": json.dumps(chart_data, ensure_ascii=False),
        "__DRAW_CALLS__": draw_calls,
    }
    for k, v in repl.items():
        html = html.replace(k, v)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("OK 写出 %s, len=%d, 图表数=%d" % (args.out, len(html), len(chart_dims)))
    print("交付前请跑：node scripts/verify_html_charts.js <html> %d" % len(chart_dims))


if __name__ == "__main__":
    main()
