"""E2Eテスト共通ヘルパー（依存: playwright のみ）"""
import json
import re
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]   # リポジトリルート
# 製品は統合ビューア 1 つ（単体版 issue_viewer.html は v2.0.0 で退役）
VIEWER_FILE = "wbs_viewer.html"
VIEWER = (ROOT / VIEWER_FILE).as_uri()
UNIFIED = True          # 読み替え（S()/J()）を常に効かせる。残してあるのは断言本文を単体版の素の
                        # セレクタのまま書けるようにするため（本文を一斉に書き換えない）
# ブラウザのタブ名の接尾辞（製品名は WBS Viewer のまま「課題」表示を足した形）
TITLE_SUFFIX = " – WBS Viewer"

# 統合ビューアでは課題側が #isMain の中に入り、wbs と衝突する id だけ is* に改名されている。
# テスト本文は単体版のセレクタのまま書き、ここ 1 か所で読み替える。
_ID_MAP = [("#filterBar", "#isFilterBar"), ("#stateFilter", "#isStateFilter"),
           ("#allCaret", "#isAllCaret"), ("#empty", "#isEmpty"),
           ("#stat", "#isStat"), ("#saveMsg", "#isSaveMsg"),
           ("#tabBar", "#isTabBar"), ("#tbl", "#isTbl"), ("#thead", "#isThead"),
           ("#tbody", "#isTbody"), ("#cgrp", "#isCgrp"), ("#addRow", "#isAddRow"),
           ("#counts", "#isCounts"), ("#starCount", "#isStarCount"), ("#starRange", "#isStarRange")]
_GLOBAL = ("#isForm", "#notePop", "#legendPop", "#openBtn", "#refreshBtn", "#editBtn", "#langBtn",
           "#legendBtn", "#notice", "#topbar", "#brandTitle", "#fallbackInput", "#pmSwitch")


# 統合ビューアでは wbs と名前がぶつかるクラスも is- 接頭辞になる
_CLS = ["sf-btn", "sf-lbl", "sf-sep", "sf-solo", "sfilter", "asg-dd", "asg-cnt", "asg-list",
        "asg-acts", "asg-cb", "asg-all", "asg-none", "seg-btn", "seg", "fbar-ttl", "date-wrap",
        "cal-proxy", "cal-btn", "nm-in", "mstat", "donechk", "ic"]
_CLS_RE = re.compile(r"(?<![\w-])(%s)(?![\w-])" % "|".join(sorted(_CLS, key=len, reverse=True)))


def S(sel):
    """セレクタを実行対象のビューアに合わせて読み替える（単体版ではそのまま）"""
    if not UNIFIED:
        return sel
    out = _CLS_RE.sub(lambda m: "is-" + m.group(1), sel)
    for a, b in _ID_MAP:
        out = out.replace(a + " ", b + " ").replace(a + ",", b + ",")
        if out.endswith(a):
            out = out[:-len(a)] + b
        out = out.replace(a + ":", b + ":").replace(a + "[", b + "[").replace(a + ">", b + ">")
    if any(g in out for g in _GLOBAL) or "#isMain" in out:
        return out
    # 課題側の DOM は #isMain の中。素のクラス指定が wbs 側に当たらないよう必ずスコープする
    return ", ".join("#isMain " + part.strip() for part in out.split(","))


def J(js):
    """evaluate に渡す JS 文字列の中のセレクタ／id を読み替える（id だけ・スコープは付けない）"""
    if not UNIFIED:
        return js
    out = _CLS_RE.sub(lambda m: "is-" + m.group(1), js)
    for a, b in _ID_MAP:
        out = out.replace(a, b)
        out = out.replace("getElementById('" + a[1:] + "')", "getElementById('" + b[1:] + "')")
        out = out.replace('getElementById("' + a[1:] + '")', 'getElementById("' + b[1:] + '")')
    return out

_failures = []


def check(cond, msg):
    print(("OK  " if cond else "FAIL") + " " + msg)
    if not cond:
        _failures.append(msg)


def finish(errors=None):
    """JSエラーとFAILを集計して終了コードを返す"""
    errors = [e for e in (errors or []) if e]
    if errors:
        print("=== JSエラー ===", errors)
    print("=== RESULT ===", "ALL PASS" if not _failures and not errors
          else f"{len(_failures)} FAIL + {len(errors)} error")
    sys.exit(1 if (_failures or errors) else 0)


def load_test_json(name):
    """課題側のコーパスは tests/issue/ に置く（wbs 本家のコーパス tests/*.json と名前が衝突するため）"""
    return json.loads((ROOT / "tests" / "issue" / name).read_text(encoding="utf-8"))


def issue(id, title, priority="mid", opened="2026-09-01", due=None,
          if_ignored="放置すると困る", if_done="", close_when="確かめられること",
          decisions=None, pending=None, closed=None, actions=None, note="", links=None):
    """fixture 用の課題1件（テスト本文を短くするためのヘルパー）。

    課題側の形は v0.2 が最初の公開形。旧キー（`decision` / `assignee` / `pending.reason` /
    `actions[].wbs`）は読み替えごと廃止したので、ここでも作らない。
    """
    return {"id": id, "title": title, "priority": priority,
            "opened": opened, "due": due, "ifIgnored": if_ignored, "ifDone": if_done,
            "closeWhen": close_when, "decisions": decisions if decisions is not None else [],
            "pending": pending, "closed": closed,
            "actions": actions if actions is not None else [], "note": note,
            **({"links": links} if links is not None else {})}


def action(date, text, assignee="", done=False):
    return {"date": date, "text": text, "assignee": assignee, "done": done}


def decision(q, since="2026-09-02", decided=None, a="", until=None):
    """方針1件。decided が null なら「未決」。until＝いつまでに決めるか（任意）"""
    d = {"q": q, "since": since, "decided": decided, "a": a}
    if until is not None:
        d["until"] = until
    return d


def issue_ref(id, project=None):
    """待ちの相手／リンクに書く課題の指し方（同じ案件は project を省く）"""
    return {"issue": id} if project is None else {"project": project, "issue": id}


def waiting(who="開発部", what="回答", since="2026-09-02", until=None):
    """止まっている理由（1）相手の返事待ち"""
    return {"kind": "waiting", "since": since, "who": who, "what": what, "until": until}


def frozen(resume_when="移行が終わったら", since="2026-09-02", detail=""):
    """止まっている理由（2）事情で止めた"""
    return {"kind": "frozen", "since": since, "resumeWhen": resume_when, "detail": detail}


DECIDED = [decision("対応方針", "2026-09-02", "2026-09-02", "対応する")]


def book(issues, name="テスト", project=None, **top):
    """v0.2 形のブック（projects[0].issues）を作る。top は star / _meta などトップレベルのキー"""
    d = {"name": name, "projects": [{"name": project or name, "issues": issues}]}
    d.update(top)
    return d


def saved_issues(data, i=0):
    """保存 JSON から i 番目の案件の issues を取り出す（v0.2）"""
    return data["projects"][i]["issues"]

# 本日を固定する init script。todayStr() は描画毎に new Date() を呼ぶので、これで
# 「期限超過」「決定/保留/完了の記録日」など本日依存の挙動を決定論化する。
PINNED_TODAY = "2026-09-15"
CLOCK_PIN = """(()=>{const FIXED=Date.UTC(2026,8,15,0,0,0);const _D=Date;
function F(...a){return a.length===0?new _D(FIXED):new _D(...a);}
F.prototype=_D.prototype;F.now=()=>FIXED;F.UTC=_D.UTC;F.parse=_D.parse;window.Date=F;})();"""


def new_page(browser, clock=CLOCK_PIN, issue_view=True, **kwargs):
    """本日固定(CLOCK_PIN)を既定で注入したページを返す。

    テストの本日を実行日に依存させない＝既定でドリフト不能にするための入口。
    統合ビューアでは「計画｜課題」の既定表示を課題側に寄せる（課題スイートの断言をそのまま使うため）。
    既定表示そのものを試す test_unified.py だけ issue_view=False で外す。
    """
    pg = browser.new_page(**kwargs)
    if clock:
        pg.add_init_script(clock)
    if UNIFIED and issue_view:
        pg.add_init_script("try{localStorage.setItem('pmView','issue');}catch(e){}")
    return pg


def granted_handle_init(data):
    """書込可のフェイクFSAハンドル（メモリ上のファイル）。window.__file に内容、__writes に書込回数"""
    return """
window.__file = %s; window.__writes = 0;
const fh = {kind:'file',
  getFile: async()=> new File([window.__file],'issue.json',{type:'application/json',lastModified:window.__mt||1000}),
  queryPermission: async()=>'granted', requestPermission: async()=>'granted',
  createWritable: async()=>{let b=null;return {write:async s=>{b=s;},abort:async()=>{},
    close:async()=>{window.__file=b;window.__mt=(window.__mt||1000)+1;window.__writes++;}}}};
window.showOpenFilePicker = async()=>[fh];
""" % json.dumps(json.dumps(data, ensure_ascii=False))


# --- リロードをまたいで localStorage を保全する -------------------------------
# 課題側の e2e は file:// を、テストごとの新しい BrowserContext（incognito 相当）で開く。
# この構成の localStorage はメモリ上にしか無く、リロードで古い document が壊れてから
# 新しい document が結び付くまでの隙に、Chromium が保存領域ごと捨てることがある。
# ストア全体が空になり（init script が書くキーだけが残る）、「リロード後も … を記憶」の
# 断言が散発的に赤くなる。CDP で確かめた限りブラウザ側への書き込みはリロード前に
# 済んでいた＝書き込みの遅れではない。
# 「同一オリジンの補助ページを開いたままにして参照を 0 にしない」も試したが、喪失率は
# 5%（2/40）→ 25%（10/40）と悪化したので採らない。消えたら書き戻して読み込み直す。


def _page_storage(pg):
    return pg.evaluate("()=>{const o={};for(let i=0;i<localStorage.length;i++)"
                       "{const k=localStorage.key(i);o[k]=localStorage.getItem(k);}return o;}")


def reload(pg, attempts=3, **kw):
    """記憶（localStorage）の検証を伴うリロードはこれを使う。

    リロードでストアが捨てられていたら、消えたキーを書き戻して読み込み直す
    （そのときだけ stderr に WARN を出す）。
    """
    before = _page_storage(pg)
    r = pg.reload(**kw)
    for i in range(attempts + 1):      # 直し 3 回＝確かめ 4 回（最後の読み込みも確かめる）
        lost = {k: v for k, v in before.items() if k not in _page_storage(pg)}
        if not lost:
            return r
        if i == attempts:
            break
        print("WARN: reload で localStorage が失われた（書き戻して再読込）: %s"
              % sorted(lost), file=sys.stderr)
        pg.evaluate("o=>{for(const k in o)localStorage.setItem(k,o[k]);}", lost)
        r = pg.reload(**kw)
    print("WARN: reload 後も localStorage を復元できなかった: %s"
          % sorted(before), file=sys.stderr)
    return r
