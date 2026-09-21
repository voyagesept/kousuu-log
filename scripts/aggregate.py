"""data/ のCSVを読んで、reports/summary.md に集計結果を書き出す。

標準ライブラリだけで動くので、GitHub Actions 側で何もインストールしなくてよい。
生データ（records.csv）には計算結果を書き戻さない。計算はいつでもここでやり直せる。
"""

import csv
import os
import statistics
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS = os.path.join(ROOT, "data", "records.csv")
STANDARDS = os.path.join(ROOT, "data", "standards.csv")
OUT = os.path.join(ROOT, "reports", "summary.md")


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.DictReader(f) if any(v.strip() for v in row.values())]


def to_int(value, default=0):
    value = (value or "").strip()
    if not value:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def to_float(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def minutes_between(start, end):
    """HH:MM を2つ受け取って分を返す。日をまたぐ場合は24時間を足す。"""
    fmt = "%H:%M"
    s = datetime.strptime(start.strip(), fmt)
    e = datetime.strptime(end.strip(), fmt)
    diff = (e - s).total_seconds() / 60
    if diff < 0:
        diff += 24 * 60
    return diff


def load_standards():
    """(対象, 工程) -> 適用開始日の新しい順に並べた標準のリスト"""
    table = {}
    for row in read_csv(STANDARDS):
        key = (row["対象"].strip(), row["工程"].strip())
        table.setdefault(key, []).append(
            {
                "段取り": to_float(row.get("標準段取り分")),
                "個あたり": to_float(row.get("標準分per個")),
                "適用開始日": (row.get("適用開始日") or "").strip(),
            }
        )
    for rows in table.values():
        rows.sort(key=lambda r: r["適用開始日"], reverse=True)
    return table


def find_standard(standards, target, process, work_date):
    """作業日の時点で有効だった標準を返す。見直し後も過去の集計が変わらないようにするため。"""
    for row in standards.get((target, process), []):
        if not row["適用開始日"] or row["適用開始日"] <= work_date:
            return row
    return None


def build_rows():
    standards = load_standards()
    rows, problems = [], []

    for raw in read_csv(RECORDS):
        label = f"issue #{raw.get('issue', '?')}"
        try:
            minutes = minutes_between(raw["開始"], raw["終了"]) - to_int(raw.get("中断分"))
        except (ValueError, KeyError):
            problems.append(f"{label}: 開始・終了の時刻を読み取れませんでした")
            continue
        if minutes <= 0:
            problems.append(f"{label}: 所要時間が0以下になりました（中断が長すぎるか、時刻が逆）")
            continue

        quantity = to_int(raw.get("数量"), default=0)
        defects = to_int(raw.get("不良"), default=0)
        good = max(quantity - defects, 0)
        work_date = (raw.get("作業日") or "").strip()
        target = (raw.get("対象") or "").strip()
        process = (raw.get("工程") or "").strip()

        std = find_standard(standards, target, process, work_date)
        std_minutes = None
        if std:
            if quantity and std["個あたり"] is not None:
                std_minutes = std["個あたり"] * good
                if std["段取り"] and process == "段取り":
                    std_minutes = std["段取り"]
            elif std["段取り"] is not None:
                std_minutes = std["段取り"]

        rows.append(
            {
                "issue": raw.get("issue", ""),
                "作業日": work_date,
                "担当者": (raw.get("担当者") or "").strip(),
                "対象": target,
                "工程": process,
                "所要分": minutes,
                "数量": quantity,
                "良品": good,
                "不良": defects,
                "標準分": std_minutes,
                "備考": (raw.get("備考") or "").strip(),
            }
        )

    return rows, problems


def fmt(value, digits=1):
    return "—" if value is None else f"{value:,.{digits}f}"


def rate(actual, standard):
    if not standard:
        return "—"
    diff = (actual - standard) / standard * 100
    return f"{diff:+.0f}%"


def group(rows, keys):
    out = {}
    for row in rows:
        out.setdefault(tuple(row[k] for k in keys), []).append(row)
    return dict(sorted(out.items()))


def table(header, body_rows):
    if not body_rows:
        return "（データがありません）\n"
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines += ["| " + " | ".join(cells) + " |" for cells in body_rows]
    return "\n".join(lines) + "\n"


def per_piece(group_rows):
    """良品が入っている記録だけで 分/個 を出す。段取りのように数量のない工程は None。"""
    values = [r["所要分"] / r["良品"] for r in group_rows if r["良品"] > 0]
    return values or None


def main():
    rows, problems = build_rows()
    total_minutes = sum(r["所要分"] for r in rows)
    dates = sorted({r["作業日"] for r in rows if r["作業日"]})
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    out = [
        "# 集計結果",
        "",
        f"最終更新: {generated}（このファイルは自動生成です。直接編集しても次回上書きされます）",
        "",
        f"- 記録件数: {len(rows)} 件",
        f"- 期間: {dates[0] if dates else '—'} 〜 {dates[-1] if dates else '—'}",
        f"- 合計時間: {total_minutes / 60:,.1f} 時間（{total_minutes:,.0f} 分）",
        "",
        "## 対象×工程ごとの実績と標準",
        "",
    ]

    body = []
    for (target, process), group_rows in group(rows, ["対象", "工程"]).items():
        minutes = sum(r["所要分"] for r in group_rows)
        good = sum(r["良品"] for r in group_rows)
        std = sum(r["標準分"] for r in group_rows if r["標準分"] is not None) or None
        values = per_piece(group_rows)
        if values:
            actual_unit = f"{statistics.mean(values):.2f} 分/個"
            candidate = f"{statistics.median(values):.2f} 分/個"
        else:
            actual_unit = f"{minutes / len(group_rows):.1f} 分/回"
            candidate = f"{statistics.median([r['所要分'] for r in group_rows]):.1f} 分/回"
        body.append(
            [
                target,
                process,
                str(len(group_rows)),
                fmt(minutes, 0),
                str(good) if good else "—",
                actual_unit,
                fmt(std, 0),
                rate(minutes, std) if std else "—",
                candidate,
            ]
        )
    out.append(
        table(
            ["対象", "工程", "件数", "合計分", "良品計", "実績", "標準合計", "差異率", "標準工数の候補"],
            body,
        )
    )
    out += [
        "",
        "「標準工数の候補」は実績の中央値です。件数が20件を超えたあたりで、",
        "`data/standards.csv` の標準をこの値に置き換えると、根拠のある標準工数になります。",
        "",
        "## 工程別の合計",
        "",
    ]

    body = []
    for (process,), group_rows in group(rows, ["工程"]).items():
        minutes = sum(r["所要分"] for r in group_rows)
        share = minutes / total_minutes * 100 if total_minutes else 0
        body.append([process, str(len(group_rows)), fmt(minutes, 0), f"{share:.0f}%"])
    out.append(table(["工程", "件数", "合計分", "割合"], body))

    out += ["", "## 担当者別", ""]
    body = []
    for (person,), group_rows in group(rows, ["担当者"]).items():
        minutes = sum(r["所要分"] for r in group_rows)
        defects = sum(r["不良"] for r in group_rows)
        quantity = sum(r["数量"] for r in group_rows)
        body.append(
            [
                person,
                str(len(group_rows)),
                fmt(minutes, 0),
                f"{minutes / 60:.1f}",
                f"{defects / quantity * 100:.1f}%" if quantity else "—",
            ]
        )
    out.append(table(["担当者", "件数", "合計分", "合計時間", "不良率"], body))

    out += ["", "## 直近の記録（新しい順に10件）", ""]
    body = []
    for row in sorted(rows, key=lambda r: (r["作業日"], r["issue"]), reverse=True)[:10]:
        diff = "—"
        if row["標準分"]:
            gap = row["所要分"] - row["標準分"]
            diff = "±0 分" if round(gap) == 0 else f"{gap:+.0f} 分"
        body.append(
            [
                row["作業日"],
                row["担当者"],
                row["対象"],
                row["工程"],
                fmt(row["所要分"], 0),
                str(row["数量"]) if row["数量"] else "—",
                diff,
                row["備考"] or "",
            ]
        )
    out.append(table(["作業日", "担当", "対象", "工程", "所要分", "数量", "標準との差", "備考"], body))

    if problems:
        out += ["", "## 読み取れなかった記録", ""]
        out += [f"- {p}" for p in problems]
        out.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"{OUT} を更新しました（{len(rows)} 件、読み取り不可 {len(problems)} 件）")


if __name__ == "__main__":
    main()
