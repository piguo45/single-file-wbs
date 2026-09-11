"""課題管理 JSON（v0.2 統合形式）の検査スクリプト。

`projects[]` の中に計画（`tasks`）と課題（`issues`）が並ぶ v0.2 の形を
読み、番号・日付・enum・リンク先の存在などを検査する。依存ゼロ・標準
ライブラリだけで動く（Python 3.12）。

指摘は行番号ではなく「案件名 / #課題番号 / 項目」の形で出す。JSON の
整形は道具によって変わるので、行番号では場所を指せないため。

Example:
    $ uv run python scripts/check.py issue_sample.json issue_dogfood.json
    $ uv run python scripts/check.py --quiet issue.json
"""

import argparse
import json
import re
import sys
from typing import Any

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

PRIORITIES = ("high", "mid", "low")
PENDING_KINDS = ("waiting", "frozen")
PENDING_WAIT_KEYS = frozenset({"kind", "since", "who", "until", "what"})
PENDING_FROZEN_KEYS = frozenset({"kind", "since", "resumeWhen", "detail"})
# v0.1/v0.2 前半の旧形（読み込み時に読み替える）
LEGACY_REASON_MAP = {"missing": "waiting", "frozen": "frozen",
                     "undecided": "waiting"}
CLOSE_HOWS = ("resolved", "wontfix", "not_occurred", "duplicate")

# links[] の 4 形（鍵の集合で種類を区別する。混ぜて書けない）
LINK_FORMS = (
    frozenset({"wbs"}),
    frozenset({"issue"}),
    frozenset({"project", "issue"}),
    frozenset({"project", "wbs"}),
    frozenset({"title", "url"}),
)

# 派生値（ビューアが計算する）を JSON に書いてはいけない
DERIVED_KEYS = frozenset({
    "status", "state", "stateLabel", "overdue", "isOverdue", "hasStar",
    "starred", "current", "currentStep", "nextAction", "counts",
    "summary", "derived",
})

# 課題と行動で使える鍵（これ以外は '_' 始まりでなければエラー）
ISSUE_KEYS = frozenset({
    "id", "title", "priority", "opened", "due", "ifIgnored", "ifDone",
    "closeWhen", "decisions", "pending", "closed", "links", "actions",
    "note",
})
DECISION_KEYS = frozenset({"q", "since", "until", "decided", "a"})
# 待ちの相手に課題を指せる（文字列 or 課題参照）
WHO_ISSUE_FORMS = (frozenset({"issue"}), frozenset({"project", "issue"}))
ACTION_KEYS = frozenset({"date", "text", "assignee", "done"})

# v0.1 の旧キー（読まないが保存では消さない）
# v0.2 が最初の公開形。課題側の旧キーは読み替えずエラーにする
LEGACY_TOP_KEYS = ("sheets",)
LEGACY_ISSUE_KEYS = ("assignee", "decision", "decisionLog")
LEGACY_ACTION_KEYS = ("wbs",)
LEGACY_HINT = "v0.2 が最初の公開形。読み替えないので新形式に直す"


class Report:
    """1 ファイル分の指摘をためる入れ物。

    Attributes:
        path: 検査したファイルのパス。
        errors: 直さないといけない指摘。
        warnings: 直さなくても動くが直したほうがよい指摘。
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        """エラーを 1 件足す。"""
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        """警告を 1 件足す。"""
        self.warnings.append(f"{where}: {msg}")


def _is_date(value: Any) -> bool:
    """`YYYY-MM-DD` かつ 1900〜2099 年なら True を返す。"""
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    return 1900 <= int(value[:4]) <= 2099


def _check_date(rep: Report, where: str, value: Any,
                allow_null: bool = True) -> None:
    """日付欄を検査する（null は「未定」として許す）。"""
    if value is None:
        if not allow_null:
            rep.error(where, "日付が必要（null 不可）")
        return
    if not _is_date(value):
        rep.error(where, f"日付は YYYY-MM-DD（1900〜2099）: {value!r}")


def _scan_derived(rep: Report, node: Any, where: str) -> None:
    """派生値らしきキーが書かれていないか、木をたどって調べる。"""
    if isinstance(node, dict):
        for key, val in node.items():
            if key in DERIVED_KEYS:
                rep.error(where, f"派生値のキー {key!r} は JSON に書かない")
            _scan_derived(rep, val, where)
    elif isinstance(node, list):
        for item in node:
            _scan_derived(rep, item, where)


def _collect_task_ids(tasks: Any, out: set[str]) -> None:
    """`tasks` を再帰的にたどり、タスク id を集める。"""
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if not isinstance(task, dict):
            continue
        tid = task.get("id")
        if isinstance(tid, str):
            out.add(tid)
        _collect_task_ids(task.get("children"), out)


def _build_index(projects: list[Any]) -> dict[str, dict[str, Any]]:
    """案件名から「課題番号の集合・タスク id の集合」を引ける表を作る。"""
    index: dict[str, dict[str, Any]] = {}
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        name = proj.get("name")
        if not isinstance(name, str):
            continue
        task_ids: set[str] = set()
        _collect_task_ids(proj.get("tasks"), task_ids)
        raw_issues = proj.get("issues")
        raw_issues = raw_issues if isinstance(raw_issues, list) else []
        issue_ids = {
            i["id"] for i in raw_issues
            if isinstance(i, dict) and isinstance(i.get("id"), int)
        }
        index[name] = {
            "issues": issue_ids,
            "tasks": task_ids,
            "has_tasks": "tasks" in proj,
        }
    return index


def _check_link(rep: Report, where: str, link: Any, own: str,
                index: dict[str, dict[str, Any]]) -> None:
    """`links[]` の 1 要素の形と、リンク先の存在を検査する。"""
    if not isinstance(link, dict):
        rep.error(where, "links の要素はオブジェクトで書く")
        return
    keys = frozenset(link)
    if keys not in LINK_FORMS:
        rep.error(
            where,
            "links の形が不正（{wbs} / {issue} / {project,issue} / "
            f"{{project,wbs}} / {{title,url}} のどれか）: {sorted(keys)}",
        )
        return

    if keys == frozenset({"title", "url"}):
        if not isinstance(link.get("title"), str) or not link["title"]:
            rep.error(where, "外部リンクの title は必須")
        url = link.get("url")
        if not isinstance(url, str) or not URL_RE.match(url):
            rep.error(where, f"url は http(s):// のみ: {url!r}")
        return

    target = link.get("project", own)
    if target not in index:
        rep.error(where, f"リンク先の案件が無い: {target!r}")
        return
    entry = index[target]

    if "issue" in keys:
        num = link.get("issue")
        if not isinstance(num, int) or isinstance(num, bool):
            rep.error(where, f"issue は整数で書く: {num!r}")
        elif num not in entry["issues"]:
            rep.error(where, f"リンク先の課題が無い: {target} / #{num}")
        return

    tid = link.get("wbs")
    if not isinstance(tid, str) or not tid:
        rep.error(where, f"wbs は文字列の id で書く: {tid!r}")
    elif not entry["has_tasks"]:
        rep.warn(where, f"{target} に計画（tasks）が無いので照合できない")
    elif tid not in entry["tasks"]:
        rep.error(where, f"リンク先のタスクが無い: {target} / {tid}")


def _check_actions(rep: Report, where: str, actions: Any) -> None:
    """`actions[]`（実績と予定）を検査する。"""
    if not isinstance(actions, list):
        rep.error(f"{where} / actions", "配列で書く")
        return
    for pos, act in enumerate(actions):
        aw = f"{where} / actions[{pos}]"
        if not isinstance(act, dict):
            rep.error(aw, "オブジェクトで書く")
            continue
        _check_date(rep, f"{aw}.date", act.get("date"))
        if not isinstance(act.get("text"), str) or not act["text"]:
            rep.error(f"{aw}.text", "何をした／するかは必須")
        if "done" in act and not isinstance(act["done"], bool):
            rep.error(f"{aw}.done", "true / false で書く")
        for key in act:
            if key in ACTION_KEYS or key in LEGACY_ACTION_KEYS \
                    or key.startswith("_"):
                continue
            rep.error(f"{aw} / {key}",
                      "未知のキー（自由に足すなら '_' 始まりにする）")
        for key in LEGACY_ACTION_KEYS:
            if key in act:
                rep.error(aw, f"旧キー {key!r}（{LEGACY_HINT}："
                              "課題の links へ移す）")


def _check_issue(rep: Report, proj_name: str, issue: Any, seen: set[int],
                 index: dict[str, dict[str, Any]]) -> None:
    """課題 1 件を検査する。"""
    if not isinstance(issue, dict):
        rep.error(proj_name, "issues の要素はオブジェクトで書く")
        return
    num = issue.get("id")
    where = f"{proj_name} / #{num}"
    if not isinstance(num, int) or isinstance(num, bool):
        rep.error(where, f"id は整数で書く: {num!r}")
    elif num in seen:
        rep.error(where, "id が案件の中で重複している")
    else:
        seen.add(num)

    for key in issue:
        if key in ISSUE_KEYS or key in LEGACY_ISSUE_KEYS \
                or key.startswith("_"):
            continue
        rep.error(f"{where} / {key}",
                  "未知のキー（自由に足すなら '_' 始まりにする）")

    if not isinstance(issue.get("title"), str) or not issue["title"]:
        rep.error(f"{where} / title", "見出しは必須")
    priority = issue.get("priority", "mid")
    if priority not in PRIORITIES:
        rep.error(f"{where} / priority",
                  f"high / mid / low のどれか: {priority!r}")
    _check_date(rep, f"{where} / opened", issue.get("opened"))
    _check_date(rep, f"{where} / due", issue.get("due"))

    if not (issue.get("ifIgnored") or issue.get("ifDone")):
        rep.warn(f"{where} / ifIgnored・ifDone",
                 "二つの問いのどちらかに答える")
    if not issue.get("closeWhen"):
        rep.warn(f"{where} / closeWhen", "完了条件が空")

    decisions = issue.get("decisions")
    if decisions is not None:
        if not isinstance(decisions, list):
            rep.error(f"{where} / decisions", "配列で書く")
        else:
            for pos, item in enumerate(decisions):
                dw = f"{where} / decisions[{pos}]"
                if not isinstance(item, dict):
                    rep.error(dw, "オブジェクトで書く")
                    continue
                if set(item) - DECISION_KEYS:
                    rep.error(dw,
                              "使える鍵は q・since・until・decided・a だけ")
                if not item.get("q"):
                    rep.error(f"{dw}.q", "決めるべきことは必須")
                _check_date(rep, f"{dw}.since", item.get("since"),
                            allow_null=False)
                _check_date(rep, f"{dw}.until", item.get("until"))
                _check_date(rep, f"{dw}.decided", item.get("decided"))
                if item.get("decided") and not item.get("a"):
                    rep.warn(f"{dw}.a", "決めたのに方針が空")

    pending = issue.get("pending")
    if pending is not None and not isinstance(pending, dict):
        rep.error(f"{where} / pending", "オブジェクトか null で書く")
    elif pending is not None:
        _check_date(rep, f"{where} / pending.since", pending.get("since"),
                    allow_null=False)
        if "reason" in pending:
            old_r = pending.get("reason")
            new_r = LEGACY_REASON_MAP.get(old_r, "waiting")
            rep.error(f"{where} / pending.reason",
                      f"旧キー（{LEGACY_HINT}：kind に直す。"
                      f"{old_r!r} なら {new_r!r}）")
        kind = pending.get("kind")
        if kind not in PENDING_KINDS:
            rep.error(f"{where} / pending.kind",
                      f"waiting / frozen のどちらか: {kind!r}")
        elif kind == "waiting":
            if "reason" not in pending and set(pending) - PENDING_WAIT_KEYS:
                rep.error(f"{where} / pending",
                          "待ちで使える鍵は kind・since・who・until・what")
            who = pending.get("who")
            if isinstance(who, dict):
                if frozenset(who) not in WHO_ISSUE_FORMS:
                    rep.error(f"{where} / pending.who",
                              "課題を指すなら {issue} か {project,issue}")
                else:
                    _check_link(rep, f"{where} / pending.who", who,
                                proj_name, index)
            elif not who:
                rep.warn(f"{where} / pending.who", "誰を待っているかを書く")
            if not pending.get("what"):
                rep.warn(f"{where} / pending.what", "何を待っているかを書く")
            _check_date(rep, f"{where} / pending.until", pending.get("until"))
        else:
            if "reason" not in pending and set(pending) - PENDING_FROZEN_KEYS:
                rep.error(f"{where} / pending",
                          "凍結で使える鍵は kind・since・resumeWhen・detail")
            if not pending.get("resumeWhen"):
                rep.warn(f"{where} / pending.resumeWhen",
                         "凍結には再開条件を書く")

    closed = issue.get("closed")
    if closed is not None and not isinstance(closed, dict):
        rep.error(f"{where} / closed", "オブジェクトか null で書く")
    elif closed is not None:
        _check_date(rep, f"{where} / closed.at", closed.get("at"),
                    allow_null=False)
        how = closed.get("how")
        if how not in CLOSE_HOWS:
            rep.error(f"{where} / closed.how",
                      "resolved / wontfix / not_occurred / duplicate の"
                      f"どれか: {how!r}")
        elif how == "duplicate":
            raw = issue.get("links")
            raw = raw if isinstance(raw, list) else []
            if not any(isinstance(x, dict) and "issue" in x for x in raw):
                rep.error(f"{where} / closed.how",
                          "duplicate は元の課題への links が必須"
                          "（{issue} か {project,issue} を1件以上）")

    for key in LEGACY_ISSUE_KEYS:
        if key in issue:
            rep.error(where, f"旧キー {key!r}（{LEGACY_HINT}：decision →"
                             " decisions・assignee は actions[] へ）")

    links = issue.get("links")
    if links is not None:
        if not isinstance(links, list):
            rep.error(f"{where} / links", "配列で書く")
        else:
            for pos, link in enumerate(links):
                _check_link(rep, f"{where} / links[{pos}]", link,
                            proj_name, index)

    _check_actions(rep, where, issue.get("actions", []))


def _check_star(rep: Report, star: Any) -> None:
    """トップレベルの `star`（更新期間）を検査する。"""
    if star is None:
        return
    if not isinstance(star, dict):
        rep.error("（全体）/ star", "オブジェクトで書く")
        return
    if set(star) - {"from", "to"}:
        rep.error("（全体）/ star", "使える鍵は from と to だけ")
    _check_date(rep, "（全体）/ star.from", star.get("from"),
                allow_null=False)
    _check_date(rep, "（全体）/ star.to", star.get("to"))
    since, until = star.get("from"), star.get("to")
    if _is_date(since) and _is_date(until) and since > until:
        rep.error("（全体）/ star", "from が to より後になっている")


def _check_task_dates(rep: Report, proj_name: str, tasks: Any) -> None:
    """計画（`tasks`）の日付だけを軽く検査する（仕様は wbs 側が正）。"""
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if not isinstance(task, dict):
            continue
        where = f"{proj_name} / WBS {task.get('id')}"
        for group in ("plan", "actual"):
            block = task.get(group)
            if isinstance(block, dict):
                for edge in ("start", "end"):
                    _check_date(rep, f"{where} / {group}.{edge}",
                                block.get(edge))
        _check_task_dates(rep, proj_name, task.get("children"))


def check_document(rep: Report, doc: Any) -> None:
    """JSON 1 ファイル分（ブック全体）を検査する。"""
    if not isinstance(doc, dict):
        rep.error("（全体）", "トップはオブジェクトで書く")
        return

    _scan_derived(rep, doc, "（全体）")
    _check_star(rep, doc.get("star"))

    for key in LEGACY_TOP_KEYS:
        if key in doc:
            rep.error("（全体）",
                      f"旧キー {key!r}（{LEGACY_HINT}：projects[] に直す）")

    projects = doc.get("projects")
    if projects is None:
        if "sheets" in doc or "issues" in doc or "tasks" in doc:
            rep.error("（全体）",
                      "課題側に旧形式は無い（v0.2 が最初の公開形）。"
                      "projects[] に直す")
            legacy = doc.get("sheets")
            if isinstance(legacy, list):
                projects = legacy
            else:
                projects = [{"name": doc.get("name") or "(名前なし)",
                             "issues": doc.get("issues", [])}]
        else:
            rep.error("（全体）", "projects[] が無い")
            return
    if not isinstance(projects, list) or not projects:
        rep.error("（全体）/ projects", "非空の配列で書く")
        return

    index = _build_index(projects)
    names: set[str] = set()
    for pos, proj in enumerate(projects):
        if not isinstance(proj, dict):
            rep.error(f"（全体）/ projects[{pos}]", "オブジェクトで書く")
            continue
        name = proj.get("name")
        if not isinstance(name, str) or not name:
            rep.error(f"（全体）/ projects[{pos}]", "案件名は必須")
            name = f"(名前なし{pos})"
        elif name in names:
            rep.error(f"（全体）/ {name}",
                      "案件名が重複している（リンクが指せなくなる）")
        names.add(name)

        _check_task_dates(rep, name, proj.get("tasks"))

        issues = proj.get("issues", [])
        if not isinstance(issues, list):
            rep.error(f"{name} / issues", "配列で書く")
            continue
        seen: set[int] = set()
        for issue in issues:
            _check_issue(rep, name, issue, seen, index)


def check_file(path: str) -> Report:
    """ファイルを読んで検査し、結果を返す。"""
    rep = Report(path)
    # 読めない入力（BOM・別の文字コード・ディレクトリ・権限なし・深すぎる入れ子）は
    # traceback を出さず「読めない」エラー 1 件にする（検査は他のファイルへ続ける）。
    try:
        with open(path, encoding="utf-8-sig") as handle:   # BOM 付き UTF-8 も読む
            doc = json.load(handle)
    except FileNotFoundError:
        rep.error("（全体）", "ファイルが見つからない")
        return rep
    except json.JSONDecodeError as exc:
        rep.error("（全体）", f"JSON として読めない: {exc}")
        return rep
    except UnicodeDecodeError as exc:
        rep.error("（全体）", f"読めない（文字コードが UTF-8 ではない: {exc.reason}）")
        return rep
    except RecursionError:
        rep.error("（全体）", "読めない（入れ子が深すぎる）")
        return rep
    except IsADirectoryError:
        rep.error("（全体）", "読めない（ディレクトリ）")
        return rep
    except PermissionError:
        rep.error("（全体）", "読めない（権限がない）")
        return rep
    except OSError as exc:
        rep.error("（全体）", f"読めない（{exc.strerror or exc}）")
        return rep
    try:
        check_document(rep, doc)
    except RecursionError:
        rep.error("（全体）", "読めない（入れ子が深すぎる）")
    return rep


def main(argv: list[str] | None = None) -> int:
    """コマンドラインの入口。エラーが 1 件でもあれば 1 を返す。"""
    parser = argparse.ArgumentParser(
        description="課題管理 JSON（v0.2）を検査する（依存ゼロ）。")
    parser.add_argument("paths", nargs="+", metavar="JSON",
                        help="検査する JSON ファイル（複数可）")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="件数の要約だけを出す")
    args = parser.parse_args(argv)

    total_errors = 0
    total_warnings = 0
    for path in args.paths:
        rep = check_file(path)
        total_errors += len(rep.errors)
        total_warnings += len(rep.warnings)
        mark = "NG" if rep.errors else "ok"
        print(f"[{mark}] {path}: "
              f"エラー {len(rep.errors)} 件 / 警告 {len(rep.warnings)} 件")
        if args.quiet:
            continue
        for line in rep.warnings:
            print(f"  WARN  {line}")
        for line in rep.errors:
            print(f"  ERROR {line}")

    print(f"合計: エラー {total_errors} 件 / 警告 {total_warnings} 件")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
