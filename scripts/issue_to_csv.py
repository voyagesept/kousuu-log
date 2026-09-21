"""Issueフォームの本文を1行のCSVに変換して data/records.csv に追記する。

GitHub Actions から呼ばれる。Issue本文は環境変数で受け取る（コマンドラインに直接
埋め込むと、本文に書かれた文字がコマンドとして解釈されてしまうため）。
"""

import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS = os.path.join(ROOT, "data", "records.csv")

COLUMNS = ["issue", "作業日", "担当者", "対象", "工程", "開始", "終了", "中断分", "数量", "不良", "備考"]

# Issueフォームの見出し -> CSVの列名
FIELDS = {
    "作業日": "作業日",
    "担当者": "担当者",
    "対象": "対象",
    "工程": "工程",
    "開始時刻": "開始",
    "終了時刻": "終了",
    "中断（分）": "中断分",
    "数量（個）": "数量",
    "不良（個）": "不良",
    "備考": "備考",
}

REQUIRED = ["作業日", "担当者", "対象", "工程", "開始", "終了", "数量"]


def parse_body(body):
    """### 見出し ごとに本文を切り分ける。"""
    values = {}
    current = None
    buffer = []
    for line in body.replace("\r\n", "\n").split("\n"):
        heading = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        if heading:
            if current:
                values[current] = "\n".join(buffer).strip()
            current = heading.group(1)
            buffer = []
        elif current:
            buffer.append(line)
    if current:
        values[current] = "\n".join(buffer).strip()

    out = {}
    for label, column in FIELDS.items():
        value = values.get(label, "").strip()
        # 未入力の任意項目は GitHub が "_No response_" と書く
        if value in ("_No response_", "_未入力_"):
            value = ""
        out[column] = value
    return out


def normalize(row, errors):
    row["作業日"] = row["作業日"].replace("/", "-").strip()
    if row["作業日"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["作業日"]):
        errors.append("作業日は 2026-09-18 の形式で入力してください")

    for column in ("開始", "終了"):
        value = row[column].strip()
        matched = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
        if not matched:
            errors.append(f"{column}時刻は 09:05 の形式で入力してください")
            continue
        hour, minute = int(matched.group(1)), int(matched.group(2))
        if hour > 23 or minute > 59:
            errors.append(f"{column}時刻が時刻として正しくありません（{value}）")
        row[column] = f"{hour:02d}:{minute:02d}"

    for column in ("中断分", "数量", "不良"):
        value = row[column].strip().replace(",", "")
        if value == "":
            continue
        if not re.fullmatch(r"\d+", value):
            errors.append(f"{column}は数字だけで入力してください（入力値: {value}）")
        row[column] = value

    for column in REQUIRED:
        if column == "数量" and row["工程"] == "段取り":
            continue  # 段取りは数量なしでよい
        if not row[column]:
            errors.append(f"{column}が空です")

    # 改行やカンマが入ると表が崩れるので、備考は1行にまとめる
    row["備考"] = " ".join(row["備考"].split())
    return row


def already_recorded(issue_number):
    if not os.path.exists(RECORDS):
        return False
    with open(RECORDS, encoding="utf-8-sig", newline="") as f:
        return any(r.get("issue") == issue_number for r in csv.DictReader(f))


def append(row):
    is_new = not os.path.exists(RECORDS) or os.path.getsize(RECORDS) == 0
    with open(RECORDS, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def main():
    body = os.environ.get("ISSUE_BODY", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "").strip()

    if already_recorded(issue_number):
        print(f"issue #{issue_number} は記録済みです。何もしません。")
        return

    parsed = parse_body(body)
    if not any(parsed.values()):
        # 実績記録以外のIssue（質問や覚え書き）は、そのままにしておく
        print("実績記録のIssueではないようなので、何もしません。")
        return

    errors = []
    row = normalize(parsed, errors)
    row["issue"] = issue_number

    if errors:
        print("入力内容を読み取れませんでした:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        # ワークフローがそのままIssueへ返信できるよう、ファイルにも書いておく
        with open(os.path.join(ROOT, "errors.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(f"- {e}" for e in errors))
        sys.exit(1)

    append({column: row.get(column, "") for column in COLUMNS})
    print(f"issue #{issue_number} を data/records.csv に追記しました: {row}")


if __name__ == "__main__":
    main()
