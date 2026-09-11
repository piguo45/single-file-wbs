# ドキュメント一覧

single-file-wbs (WBS Viewer) の設計ドキュメント。
仕様の単一ソースは [`CLAUDE.md`](../CLAUDE.md)、使い方は [`README.md`](../README.md)。

*自動生成（`scripts/refresh_docs_index.py`）: 16ファイル*

## 設計書

| ドキュメント | 概要 |
|---|---|
| [single-file-issue v0.1（MVP）設計ブリーフ](design/brief-v0.1.md) | 課題管理表を「JSON 1枚＋単一HTMLビューア＋`CLAUDE.md`」で回す v0.1（MVP）の設計ブリーフ（一次記録）。 |
| [v0.2 設計ブリーフ：計画（WBS）と課題（Issue）を 1 枚の HTML・1 つの JSON に統合する](design/brief-v0.2-unified.md) | 計画（WBS）と課題（Issue）を1枚の HTML・1つの JSON に統合すると決めた v0.2 の設計ブリーフ（一次記録）。 |
| [WBS Viewer 全体概要](design/system-overview.md) | `wbs_viewer.html` と周辺ファイルの構成から逆生成した全体像（構成・依存・データの流れ）。 |
| [統合ビューアの差し込み口（段階 C で wbs 本家へ移すための指示書）](design/unified-touchpoints.md) | 統合ビューアを本家へ移すための差し込み口の一覧（橋 `PM` の窓口・課題描画器の作り方・取り込み手順）。 |

## 設計決定記録 (ADR)

| ドキュメント | 概要 |
|---|---|
| [ADR-0001: 依存ゼロの単一HTML・`file://` で動かす](adr/0001-dependency-free-single-file.md) | サーバー・ビルド・外部依存を持たず、単一HTMLを `file://` で開く形態を製品の前提にする。 |
| [ADR-0002: ブラウザ内編集に File System Access API を使う](adr/0002-file-system-access-editing.md) | サーバーレスのまま `wbs.json` へ書き戻すため、ブラウザ内編集の保存に File System Access API を使う。 |
| [ADR-0003: 派生値をデータに持たせない（描画時に算出）](adr/0003-no-derived-values-in-data.md) | データは事実（日付・数量）だけを持ち、工数・進捗・座標は描画時に決定論的に算出する。 |
| [ADR-0004: AIを第一級ユーザーにする（JSON＝AIのAPI仕様）](adr/0004-ai-first-json-as-api.md) | 人間=GUI／AI=素のJSON＋`CLAUDE.md` の2経路を第一級にし、スキーマをほぼ固定する。 |
| [ADR-0005: 配色はCUD配慮（色だけに意味を担わせない）](adr/0005-cud-color-design.md) | 色だけに意味を持たせず、形・位置・ラベルで冗長化する（色覚多様性への配慮）。 |
| [ADR-0006: 回帰テストは headless Chromium（self-contained・uv）](adr/0006-e2e-headless-chromium.md) | 実ブラウザの描画が仕様なので、回帰テストは headless Chromium で実描画を検証する（uvで自己完結）。 |
| [ADR-0007: ライセンスは MIT を継続（AGPL移行は却下）](adr/0007-license-mit.md) | クライアント完結でAGPLの前提と噛み合わないため、ライセンスは MIT を継続する。 |
| [ADR-0008: 状態を持たず、事実から導出する](adr/0008-facts-only-derived-status.md) | `wbs.json` は事実（決めた・止めた・閉じた・行動が済んだ）だけを持ち、状態（未着手／対応中／完了）と印はビューアが導出する。 |
| [ADR-0009: 「二つの問い」と「完了条件」を第一級フィールドにする](adr/0009-two-questions-and-close-condition.md) | 課題を載せる条件（放置するとどうなるか／やると何が生まれるか）と完了条件を、備考ではなく専用フィールドで持つ。 |
| [ADR-0010: シート＝Excel の「1ブック＝複数シート」に倣う](adr/0010-sheets-as-excel-workbook.md) | 課題表のファイル1枚を「ブック」とし、案件ごとの「シート」をタブで切り替える。 |
| [ADR-0011: 計画と課題を1つの JSON に置く（案件＝project・リンク台帳は課題側だけ）](adr/0011-plan-and-issues-in-one-json.md) | `projects[]` の中に 計画（`tasks`）と課題（`issues`）を並べ、つながりは課題の `links[]` にだけ書く。 |

## 研究ノート

| ドキュメント | 概要 |
|---|---|
| [計画（WBS）と課題管理の有無で何が変わるか](notes/study-wbs-x-issue.md) | 「計画がある／ない」×「課題管理がある／ない」の 2×2 で、現場の行動と AI の答えられる問いがどう変わるかの研究ノート。 |
