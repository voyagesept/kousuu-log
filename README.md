# 工数記録（練習用）

標準工数の洗い出しと、作業にかかった時間の集計をGitHubの上でやってみるための置き場です。
Issueに入力すると、CSVに1行たまって、集計が自動でやり直されます。

- 記録する → [Issues](../../issues/new/choose) から「作業実績を記録する」
- 結果を見る → [reports/summary.md](reports/summary.md)
- 生データ → [data/records.csv](data/records.csv)

## 携帯から入力する

GitHubのスマホアプリは、この形式の入力フォーム（YAMLで書いたIssueテンプレート）に
対応していません。アプリから新規Issueを作ろうとすると、ブラウザに飛ばされます。
携帯からはブラウザで直接この画面を開くのが確実です。

https://github.com/voyagesept/kousuu-log/issues/new?template=record.yml

ブラウザのメニューから「ホーム画面に追加」しておくと、アイコンを押すだけで
入力画面が開きます。アプリのほうは、集計を見たり、記録できた通知を受け取るのに使えます。

## 入れてから出るまで

```
携帯 / パソコン
   │  Issueフォームに入力して Submit
   ▼
Issue が立つ
   │  ここで GitHub Actions が自動で動く（.github/workflows/record.yml）
   ▼
scripts/issue_to_csv.py   … 本文を読んで data/records.csv に1行追記
scripts/aggregate.py      … 標準工数と突き合わせて reports/summary.md を作り直す
   │  結果をコミットして push
   ▼
Issue に「記録しました」と返信がついて、自動で閉じる
```

## ファイルの役割

| ファイル | 中身 |
|---|---|
| `data/records.csv` | 実績の生データ。1行 = 1人が1工程を1回やった記録 |
| `data/standards.csv` | 標準工数マスタ。手で育てていく表 |
| `reports/summary.md` | 集計結果。自動生成なので、直接編集しても次回上書きされます |
| `scripts/issue_to_csv.py` | Issueの本文をCSVの1行に変換する |
| `scripts/aggregate.py` | CSVを読んで集計表を作る。手元でも `python scripts/aggregate.py` で動きます |
| `.github/ISSUE_TEMPLATE/record.yml` | 入力フォームの定義。項目を足したいときはここ |
| `.github/workflows/record.yml` | Issueが立ったときに動く手順 |
| `.github/workflows/aggregate.yml` | CSVを画面から直接編集したときに動く手順 |

## 標準工数の育て方

1. 最初は勘で `data/standards.csv` を埋めます（空でも動きます）。
2. 実績が20〜30件たまったら、`reports/summary.md` の「標準工数の候補」列を見ます。
   これは実績の中央値です。
3. 納得できる値なら `data/standards.csv` を書き換え、`適用開始日` を書き換えた日にします。
   過去の行は消さずに残してください。当時の標準と比べた過去の集計が、そのまま残ります。

## つまずきやすいところ

**Actionsが失敗する（Permission denied / 403）**
Settings → Actions → General → Workflow permissions を
「Read and write permissions」にして Save してください。ここが読み取り専用だと、
自動でコミットできません。

**Actionsが動いた様子がない**
Actionsタブを開くと、実行の履歴とログが全部残っています。赤い×をクリックすると、
どの行で止まったか読めます。

**CSVをActionsが更新したのに、集計のワークフローが動かない**
仕様です。Actionsが押したコミットでは、別のワークフローは起動しません
（無限ループを防ぐため）。なので `record.yml` の中で集計まで済ませています。

**入力を間違えた**
`data/records.csv` を画面から直接編集して構いません。保存すると `aggregate.yml` が
動いて、集計だけ作り直されます。

## この仕組みで出てくるGitHubの言葉

| 言葉 | ここでの役目 |
|---|---|
| リポジトリ | この置き場そのもの |
| コミット | 「この状態で保存」の1回分。誰がいつ何を変えたかが全部残る |
| ブランチ | 作業用の枝。`main` が本線 |
| プルリクエスト | 枝で作った変更を本線に入れてよいか見てもらう場 |
| Issue | もともとは課題を書く場所。ここでは入力フォームとして使っています |
| Actions | 何かが起きたら自動で動く仕組み。ここでは記録と集計を任せています |
| ワークフロー | Actionsに「何が起きたら、何をするか」を書いたファイル |
