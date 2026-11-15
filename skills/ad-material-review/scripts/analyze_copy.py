#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文案卖点 × 图片素材 × 用户偏好 交叉分析（通用版 / config 驱动 / 纯标准库）。

把「一条素材拆多行投给不同人群」的规划表，加工成可归因的底表 + 结果 JSON：
  1) 人群归一   segment_raw --(config.copy.segment_map 有序优先级)--> segment
  2) 素材继承   文案/图只在块首行出现时，后续标注行继承最近素材；未标注行不继承
  3) 文案桥挂接 用整段文案匹配旧台账，复用已打好的视觉标签（免重复看图）；可关闭
  4) 文案标签   按主句回填 主卖点/行动钩子/语气句式/置信度（来自 copy_labels JSON）
  5) 交叉分析   各维度 × 各核心人群 的曝光加权 CTR + 基线 + 样本不足标注 + 同素材跨人群

口径铁律（详见 references/copy-analysis.md）：
  CTR = SUM(点击)/SUM(曝光)，绝不逐行平均；
  只在同类人群内部比较 / 相对该人群基线，禁止跨人群硬比绝对 CTR；
  n < thresholds.min_sample 标注「样本不足」，只给方向性结论。

所有「取值」(人群、标签、颜色、维度、短名、优先级) 一律读 config，脚本不含任何游戏/平台专属值。
输入表统一用「内部列名」数据契约（见 references/copy-analysis.md 第四节 / config.schema.md）：
  planning : segment_raw, copy_text, image_url, impressions, clicks, date, position, material_id
  master   : copy_text, material_id            （文案桥，可选）
  tagged   : material_id, style, elements, benefit, node, confidence   （文案桥，可选）
  index    : material_id, image_url            （素材ID -> CDN原图链接，可选）
  labels   : { "<主句>": {"main":..., "hooks":[...], "tones":[...], "conf":...} }  （JSON）

用法（包根目录空跑）:
  python skills/ad-material-review/scripts/analyze_copy.py \
    --config examples/config.demo.json \
    --planning examples/copy_planning.sample.csv \
    --labels examples/copy_labels.sample.json \
    --master examples/copy_master.sample.csv \
    --tagged examples/copy_tagged.sample.csv \
    --index examples/copy_index.sample.csv \
    --out-base examples/out/copy_base.csv --out-json examples/out/copy_results.json
"""
import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict

from config_loader import load_config, add_config_arg


# ---- 文案归一：去字面 \n / 零宽字符 / 全部空白（新旧表换行与空格常不一致）----
def norm(s):
    s = (s or "").replace("\\n", "").replace("\u200b", "")
    return re.sub(r"\s+", "", s)


def read_csv(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def first_sentence(copy_text):
    """主句 = 第一行非空句（先把字面 \\n 还原成换行，并剔除分时段指引行）。"""
    txt = (copy_text or "").replace("\\n", "\n")
    for line in txt.split("\n"):
        line = line.strip()
        if line:
            return line
    return ""


def strip_markers(copy_text, markers):
    """剔除「X点-X点文案：」这类指引行，不当正文；返回 (有效正文, 是否本行素材)。"""
    if not copy_text:
        return "", False
    txt = copy_text.replace("\\n", "\n")
    lines = [l for l in txt.split("\n") if l.strip()]
    kept = [l for l in lines if not any(m in l for m in markers)]
    eff = "\n".join(kept).strip()
    return eff, bool(eff)


def normalize_segment(raw, seg_map, unlabeled, other):
    """按 config.copy.segment_map 的有序优先级归一人群；命中第一条即停。"""
    if not (raw or "").strip():
        return unlabeled
    for rule in seg_map:
        for kw in rule.get("match", []):
            if kw and kw in raw:
                return rule["to"]
    return other


def wctr(rows):
    e = sum(to_int(r.get("impressions")) or 0 for r in rows)
    c = sum(to_int(r.get("clicks")) or 0 for r in rows)
    return {"n": len(rows), "exp": e, "clk": c, "ctr": round(c / e * 100, 3) if e else 0.0}


def build_base(planning, cfg, args):
    """归一 + 继承 + 文案桥挂接 + 文案标签回填，返回底表行列表与统计。"""
    cp = cfg["copy"]
    tax = cfg["taxonomy"]
    seg_map = cp["segment_map"]
    core = cp["core_segments"]
    unlabeled = cp.get("unlabeled", "未标注")
    other = cp.get("other", "其他")
    strip = cp.get("strip_markers", [])
    markers = [m if isinstance(m, str) else str(m) for m in strip]
    multi_sep = tax.get("copy_multi_separator", ";")

    # 文案标签：主句 -> {main, hooks, tones, conf}（key 做归一，容忍空格/换行差异）
    labels = {}
    if args.labels and os.path.exists(args.labels):
        with open(args.labels, encoding="utf-8") as f:
            raw_lab = json.load(f)
        for k, v in raw_lab.items():
            labels[norm(k)] = v

    # 文案桥：master(copy->素材ID) / tagged(素材ID->视觉标签) / index(素材ID->CDN)
    copy2mat, tagged, mat2link = {}, {}, {}
    if cp.get("bridge", {}).get("enabled", False):
        for r in read_csv(args.master):
            key = norm(r.get("copy_text", ""))
            if key and r.get("material_id"):
                copy2mat.setdefault(key, Counter())[r["material_id"]] += 1
        for r in read_csv(args.tagged):
            if r.get("material_id"):
                tagged[r["material_id"]] = r
        for r in read_csv(args.index):
            if r.get("material_id"):
                mat2link[r["material_id"]] = r.get("image_url", "")

    out, stats = [], Counter()
    prev_copy, prev_img = "", ""
    for r in planning:
        exp = to_int(r.get("impressions"))
        clk = to_int(r.get("clicks"))
        seg = normalize_segment(r.get("segment_raw", ""), seg_map, unlabeled, other)

        eff_copy, is_block_head = strip_markers(r.get("copy_text", ""), markers)
        # 素材继承：本行有文案 -> 更新「最近素材」；空行且人群已标注 -> 继承；未标注行不继承
        if is_block_head:
            prev_copy, cur_copy, inherited = eff_copy, eff_copy, False
        elif seg not in (unlabeled, other):
            cur_copy, inherited = prev_copy, bool(prev_copy)
        else:
            cur_copy, inherited = "", False
        raw_img = r.get("image_url", "") or ""
        if raw_img:
            prev_img, cur_img = raw_img, raw_img
        elif seg not in (unlabeled, other):
            cur_img = prev_img
        else:
            cur_img = ""

        # 无曝光行（排期/汇总行）不进分析
        if exp is None:
            stats["无曝光行(跳过)"] += 1
            continue
        stats["曝光行"] += 1

        main = first_sentence(cur_copy)
        # 文案标签回填（两套体系独立：文案维度只依赖文案，不依赖图片）
        lab = labels.get(norm(main), {})
        rec = {
            "date": r.get("date", ""), "position": r.get("position", ""),
            "segment_raw": r.get("segment_raw", "").replace("\n", "/"), "segment": seg,
            "copy_text": cur_copy, "copy_main": lab.get("main", ""),
            "copy_hook": multi_sep.join(lab.get("hooks", [])),
            "copy_tone": multi_sep.join(lab.get("tones", [])),
            "copy_conf": lab.get("conf", ""),
            "material_id": r.get("material_id", ""), "image_url": cur_img,
            "style": "", "elements": "", "benefit": "", "node": "", "confidence": "",
            "bridge_hit": "", "inherited": "继承" if inherited else "本行",
            "impressions": exp, "clicks": clk or 0,
        }

        # 文案桥挂接：有文案、且本行还没有素材ID时，用整段文案认亲旧台账
        if cp.get("bridge", {}).get("enabled", False) and cur_copy and not rec["material_id"]:
            cnt = copy2mat.get(norm(cur_copy))
            if cnt:
                mat_id, _n = cnt.most_common(1)[0]
                t = tagged.get(mat_id)
                if t:
                    rec.update({
                        "material_id": mat_id,
                        "style": t.get("style", ""), "elements": t.get("elements", ""),
                        "benefit": t.get("benefit", ""), "node": t.get("node", ""),
                        "confidence": t.get("confidence", ""),
                        "image_url": mat2link.get(mat_id, cur_img),
                        "bridge_hit": "高" if len(cnt) == 1 else "中(同文案多素材)",
                    })
                    stats["挂接成功"] += 1
                else:
                    stats["挂接失败(素材ID无标签)"] += 1
            else:
                stats["挂接失败(文案未命中)"] += 1
        elif cur_copy:
            stats["无桥接(本行自带素材/桥关闭)"] += 1

        out.append(rec)
    return out, stats


def analyze(base, cfg):
    """各维度 × 各核心人群 曝光加权 CTR + 基线 + 样本不足标注 + 同素材跨人群。"""
    cp = cfg["copy"]
    tax = cfg["taxonomy"]
    core = cp["core_segments"]
    min_sample = cfg["thresholds"]["min_sample"]
    multi_sep = tax.get("copy_multi_separator", ";")
    elem_sep = tax.get("element_separator", "+")

    rows = [r for r in base if to_int(r.get("impressions")) is not None]
    core_rows = [r for r in rows if r["segment"] in core]

    res = {"core_segments": core,
           "segment_colors": cp.get("segment_colors", {}),
           "min_sample": min_sample,
           "overall": {}, "dims": {}, "cross": {}, "meta": {}}

    # 基线 = 各核心人群整体 CTR（红虚线）
    res["overall"] = {seg: wctr([r for r in core_rows if r["segment"] == seg]) for seg in core}
    res["overall"]["全部(含未标注/其他)"] = wctr(rows)

    # 维度定义：(结果key, 内部字段名, 多选分隔符 or None, 是否文案维度)
    # 文案维度只统计「有主卖点标签」的行；图片维度只统计「有画风标签」的行（互不污染）
    dim_specs = [
        ("copy_main", "copy_main", None, True),
        ("copy_hook", "copy_hook", multi_sep, True),
        ("copy_tone", "copy_tone", multi_sep, True),
        ("benefit", "benefit", None, False),
        ("style", "style", None, False),
        ("elements", "elements", elem_sep, False),
    ]

    def dimx(field, sep, is_copy, seg):
        buckets = defaultdict(list)
        for r in core_rows:
            if r["segment"] != seg:
                continue
            if is_copy and not r["copy_main"]:
                continue
            if not is_copy and not r["style"]:
                continue
            val = r.get(field, "") or ""
            keys = [k.strip() for k in val.split(sep) if k.strip()] if sep else ([val.strip()] if val.strip() else [])
            for k in keys:
                buckets[k].append(r)
        d = {}
        for k, grp in sorted(buckets.items(), key=lambda kv: -sum(to_int(x["impressions"]) or 0 for x in kv[1])):
            x = wctr(grp)
            x["flag"] = "样本不足" if x["n"] < min_sample else ""
            x["base"] = res["overall"][seg]["ctr"]
            x["vs_base"] = round(x["ctr"] - res["overall"][seg]["ctr"], 3)
            d[k] = x
        return d

    for key, field, sep, is_copy in dim_specs:
        res["dims"][key] = {seg: dimx(field, sep, is_copy, seg) for seg in core}

    # 同素材跨人群：同一 material_id 投给 >=2 类核心人群
    groups = defaultdict(lambda: defaultdict(list))
    for r in core_rows:
        if r["material_id"]:
            groups[r["material_id"]][r["segment"]].append(r)
    cross = []
    for mat, by_seg in groups.items():
        if len(by_seg) >= 2:
            first = next(iter(by_seg.values()))[0]
            entry = {"material_id": mat, "style": first["style"], "benefit": first["benefit"],
                     "by_segment": {}}
            for seg, grp in by_seg.items():
                x = wctr(grp)
                x["vs_base"] = round(x["ctr"] - res["overall"][seg]["ctr"], 3)
                entry["by_segment"][seg] = x
            cross.append(entry)
    cross.sort(key=lambda e: -sum(x["clk"] for x in e["by_segment"].values()))
    res["cross"] = {"group_count": len(cross), "samples": cross[:15]}

    need_bridge = sum(1 for r in rows if r["copy_text"])
    hit = sum(1 for r in rows if r["bridge_hit"])
    res["meta"] = {
        "total_rows": len(rows),
        "core_rows": len(core_rows),
        "segment_distribution": dict(Counter(r["segment"] for r in rows)),
        "copy_labeled_rows": sum(1 for r in rows if r["copy_main"]),
        "visual_labeled_rows": sum(1 for r in rows if r["style"]),
        "unique_material_ids": len(set(r["material_id"] for r in rows if r["material_id"])),
        "bridge_need": need_bridge, "bridge_hit": hit,
        "bridge_rate": round(hit / need_bridge * 100, 1) if need_bridge else 0.0,
    }
    return res


def show(res):
    print("=== 基线（各人群整体 CTR）===")
    for seg, x in res["overall"].items():
        print("  %-16s n=%-4d 曝光=%-10d CTR=%.3f%%" % (seg, x["n"], x["exp"], x["ctr"]))
    for dim in ("copy_main", "copy_hook", "benefit", "style"):
        if dim not in res["dims"]:
            continue
        print("=== 维度 %s ===" % dim)
        for seg in res["core_segments"]:
            tops = sorted(res["dims"][dim][seg].items(), key=lambda kv: -kv[1]["ctr"])[:3]
            print("  --", seg)
            for k, x in tops:
                print("     %-16s n=%-3d CTR=%.2f%% (%+.2fpp) %s" % (
                    k, x["n"], x["ctr"], x["vs_base"], x["flag"]))
    m = res["meta"]
    print("=== 元信息 ===")
    print("  曝光行 %d / 核心人群行 %d / 文案打标行 %d / 图片打标行 %d" % (
        m["total_rows"], m["core_rows"], m["copy_labeled_rows"], m["visual_labeled_rows"]))
    print("  文案桥挂接率 %.1f%% (%d/%d)；唯一素材ID %d；同素材跨人群组 %d" % (
        m["bridge_rate"], m["bridge_hit"], m["bridge_need"],
        m["unique_material_ids"], res["cross"]["group_count"]))
    print("  [警告] 口径：偏好结论只做同类内部比较 / 相对该人群基线，禁止跨人群比绝对 CTR。")


def main():
    ap = argparse.ArgumentParser(description="文案卖点 × 图片素材 × 用户偏好 交叉分析")
    add_config_arg(ap)
    ap.add_argument("--planning", default="./data/copy_planning.csv", help="规划表(内部列名)")
    ap.add_argument("--labels", default="./data/copy_labels.json", help="文案标签 JSON")
    ap.add_argument("--master", default=None, help="旧台账 master.csv(文案->素材ID，文案桥可选)")
    ap.add_argument("--tagged", default=None, help="旧台账 tagged.csv(素材ID->视觉标签，文案桥可选)")
    ap.add_argument("--index", default=None, help="素材ID->CDN原图链接(可选)")
    ap.add_argument("--out-base", default="./data/copy_base.csv", help="底表输出")
    ap.add_argument("--out-json", default="./data/copy_results.json", help="结果JSON输出")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if "copy" not in cfg:
        raise SystemExit("[analyze_copy] 配置缺少 copy 区块，请参照 config.example.json 补齐。")

    planning = read_csv(args.planning)
    if not planning:
        raise SystemExit("[analyze_copy] 规划表为空或不存在：%s" % args.planning)

    base, stats = build_base(planning, cfg, args)
    res = analyze(base, cfg)

    for p in (args.out_base,):
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(base[0].keys()))
            w.writeheader()
            w.writerows(base)
        print("已写出底表:", p, len(base), "行")
    for p in (args.out_json,):
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print("已写出结果:", p)

    print("=== 数据准备统计 ===")
    for k, n in stats.items():
        print("  %-24s %d" % (k, n))
    show(res)


if __name__ == "__main__":
    main()
