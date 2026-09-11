"""配色監査（課題側）— wbs 側 tests/e2e/test_color_audit.py と同じ方式を課題の色に当てる。

何を守るか:
  ・重なる/隣接する色の組が、色覚3型(P/D/T)でも区別できる（ΔE<10 の新規ペアを出さない）
  ・文字は WCAG AA（本文 4.5・小字や副次は 3 を理由つきで許容）
仕組み:
  ・wbs_viewer.html（製品は 1 つ）から、課題側の色を実際に抽出する。
    課題側の CSS は `#isMain` にスコープされ、変数は `--is-` 接頭辞を持つ（wbs 側と衝突しないため）。
  ・役割名で索引するので、値を変えても追える。色を足す機能では必ずここにペアを足すこと
ブラウザ不要の純Python。"""
import math
import re
from common import ROOT, check, finish

HTML = (ROOT / "wbs_viewer.html").read_text(encoding="utf-8")


def rootvars(html):
    """課題側の :root ブロック（--is-* を持つ方）を読み、`is-` を外した名前で返す。

    統合ビューアには :root が 2 つある（計画側／課題側）。--is- を含む方だけを選ばないと、
    両方に同名同値で存在する --muted / --text を計画側から拾ってしまい、
    課題側のパレットを監査したつもりで別のパレットを見ることになる。
    """
    blocks = [b for b in re.findall(r":root\{(.*?)\n  \}", html, re.S) if "--is-" in b]
    if len(blocks) != 1:
        raise SystemExit(f"[color_audit_issue] 課題側の :root が 1 つに定まらない: {len(blocks)}")
    return {k[3:]: v for k, v in re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{3,6})", blocks[0])
            if k.startswith("is-")}


def lit(pat, label):
    m = re.search(pat, HTML)
    if not m:
        raise SystemExit(f"[color_audit_issue] 色抽出に失敗（HTML構造が変わった?）: {label}")
    return m.group(1)


V = rootvars(HTML)
C = {
    # 地色・文字の基準
    "白地": "#ffffff", "本文": V["text"], "薄字": V["muted"],
    "完了行地": V["done-bg"], "完了行文字": V["done-fg"],
    "期限超過": V["red"], "警告": V["amber"], "★": V["star"],
    # 状態バッジ（地色／文字）4種
    "未着手地": lit(r"#isMain \.bdg\.s-todo\{background:(#[0-9a-fA-F]{3,6})", "s-todo-bg"),
    "未着手字": lit(r"#isMain \.bdg\.s-todo\{[^}]*?[;{]color:(#[0-9a-fA-F]{3,6})", "s-todo-fg"),
    "対応中地": lit(r"#isMain \.bdg\.s-wip\{background:(#[0-9a-fA-F]{3,6})", "s-wip-bg"),
    "対応中字": lit(r"#isMain \.bdg\.s-wip\{[^}]*?[;{]color:(#[0-9a-fA-F]{3,6})", "s-wip-fg"),
    "完了地": lit(r"#isMain \.bdg\.s-closed\{background:(#[0-9a-fA-F]{3,6})", "s-closed-bg"),
    "完了字": lit(r"#isMain \.bdg\.s-closed\{[^}]*?[;{]color:(#[0-9a-fA-F]{3,6})", "s-closed-fg"),
    # 優先度バッジ 3種
    "高地": lit(r"#isMain \.bdg\.p-high\{background:(#[0-9a-fA-F]{3,6})", "p-high-bg"),
    "高字": lit(r"#isMain \.bdg\.p-high\{[^}]*?[;{]color:(#[0-9a-fA-F]{3,6})", "p-high-fg"),
    "低地": lit(r"#isMain \.bdg\.p-low\{background:(#[0-9a-fA-F]{3,6})", "p-low-bg"),
    # 区切りの帯（備考の印はリンク行へ移したので「リンク」の色で見る）
    "帯地": lit(r"#isMain \.sec\{[^}]*?background:(#[0-9a-fA-F]{3,6})", "sec-bg"),
    "帯字": lit(r"#isMain \.sec\{[^}]*?[;{]color:(#[0-9a-fA-F]{3,6})", "sec-fg"),
    # 済／未の濃淡
    "済": lit(r"#isMain \.act \.dn\.dn-d\{color:(#[0-9a-fA-F]{3,6})", "dn-d"),
    "未": lit(r"#isMain \.act \.dn\.dn-t\{color:(#[0-9a-fA-F]{3,6})", "dn-t"),
    "完了行の未": lit(r"#isMain tr\.st-closed \.act \.dn\.dn-t\{color:(#[0-9a-fA-F]{3,6})", "dn-t-closed"),
    # 印（状態列の下・タイトル横の未決・未決の経過日数）
    "印字": V["muted"],
    "印の添え字": lit(r"#isMain \.mk \.mksub\{color:(#[0-9a-fA-F]{3,6})", "mksub"),
    "未決の印": lit(r"#isMain \.mk\.mk-open\{color:(#[0-9a-fA-F]{3,6})", "mk-open"),
    "タイトル横の未決": lit(r"#isMain \.opn\{[^}]*?[;{]color:(#[0-9a-fA-F]{3,6})", "opn"),
    "タブ未決": lit(r"#isMain \.stab \.tb\.un\{color:(#[0-9a-fA-F]{3,6})", "tb-un"),
    # リンク行
    "リンク": lit(r"#isMain \.lk\{[^}]*?[;{]color:(#[0-9a-fA-F]{3,6})", "lk"),
    "リンクhover": lit(r"#isMain \.lk \.lk-i:hover\{color:(#[0-9a-fA-F]{3,6})", "lk-hover"),
    # 飛び先の強調（課題側）
    "強調黄": lit(r"#isMain #isTbody tr\.jump>td\{background:(#[0-9a-fA-F]{3,6})", "jump"),
    # 統合で足した色（計画側の逆引き札・タブのバッジ）
    "札": lit(r"\.pmb\{[^}]*?[;{]color:(#[0-9a-fA-F]{3,6})", "pmb"),
    "札hover": lit(r"\.pmb:hover\{color:(#[0-9a-fA-F]{3,6})", "pmb-hover"),
    "タブ⚠": lit(r"#isMain \.stab \.tb\.ov\{color:(#[0-9a-fA-F]{3,6})", "tb-ov"),
}
C["タブ★"] = C["★"]   # タブの★は --is-star（1か所で持つ）


def s2l(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hx(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [s2l(int(h[i:i + 2], 16)) for i in (0, 2, 4)]


def lab(rgb):
    r, g, b = rgb
    X = r * 0.4124 + g * 0.3576 + b * 0.1805
    Y = r * 0.2126 + g * 0.7152 + b * 0.0722
    Z = r * 0.0193 + g * 0.1192 + b * 0.9505

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(X / 0.95047), f(Y), f(Z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def dE(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(lab(a), lab(b))))


def Yl(rgb):
    r, g, b = rgb
    return r * 0.2126 + g * 0.7152 + b * 0.0722


def wcag(h1, h2):
    a, b = Yl(hx(h1)), Yl(hx(h2))
    L, D = max(a, b), min(a, b)
    return (L + 0.05) / (D + 0.05)


MAT = {"P": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
       "D": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
       "T": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]}


def cvd(c, m):
    return [sum(m[i][j] * c[j] for j in range(3)) for i in range(3)]


def emin(a, b):
    la, lb = hx(C[a]), hx(C[b])
    return min([dE(la, lb)] + [dE(cvd(la, MAT[k]), cvd(lb, MAT[k])) for k in "PDT"])


# ---- 物理的に重なる/隣接するペア（色を足したらここに足す）----
PAIRS = [
    # ① 帯と、その下に続く本文
    ("帯地", "白地"), ("帯字", "帯地"),
    # ② ★（黒の記号）と、同じ行に並ぶ済/未
    ("★", "済"), ("★", "未"), ("★", "白地"),
    # ③ 完了行（灰背景）に載る文字
    ("完了行地", "完了行の未"), ("完了行地", "済"), ("完了行地", "本文"), ("完了行地", "白地"),
    # ④ 飛び先の黄色い強調に載る本文・★
    ("強調黄", "本文"), ("強調黄", "★"), ("強調黄", "白地"),
    # ⑤ タブのバッジ同士（★＝黒／⚠＝赤が並ぶ）
    ("タブ★", "タブ⚠"),
    # ⑥ タイトルの下に重なるリンク行／計画側の逆引き札はタスク名の隣
    ("リンク", "本文"), ("リンク", "白地"), ("リンクhover", "リンク"),
    ("札", "本文"), ("札hover", "札"),
    # ⑦ 状態バッジの地色どうし（同じ列に縦に並ぶ）
    ("未着手地", "対応中地"), ("対応中地", "完了地"), ("未着手地", "完了地"),
    # ⑦' 状態バッジの下に並ぶ印（薄字・橙・赤が縦に続く）
    ("印字", "白地"), ("印の添え字", "印字"), ("未決の印", "印字"), ("未決の印", "白地"),
    ("タイトル横の未決", "本文"), ("タブ未決", "タブ★"), ("タブ未決", "タブ⚠"),
    # ⑧ 優先度バッジの地色どうし（高＝赤系／中＝無色／低＝灰）
    ("高地", "白地"), ("高地", "低地"), ("低地", "白地"),
    # ⑨ 意味色どうし（期限超過の赤と警告の琥珀が同じ行に出る）
    ("期限超過", "警告"), ("期限超過", "本文"),
    # ⑩ 済と未の濃淡（同じ列に縦に並ぶ）
    ("済", "未"), ("未", "白地"),
]
THRESH = 10.0
# 別チャネル（形・位置・語・装飾）で冗長化済み＝ΔE未満でも許容する既知ペア（理由必須）
ACCEPTED = {

    frozenset(("完了行地", "白地")): "完了行は取り消し線＋グレー文字＋状態バッジ『完了』で多重識別（地色だけに頼らない）",
    frozenset(("強調黄", "白地")): "強調は2秒だけの一時表示。消えることそのものが情報で、色の弁別に依存しない",
    frozenset(("未着手地", "完了地")): "未着手=白地＋琥珀の枠と文字／完了=灰地＋灰文字。枠と文字色、さらに語で区別",
    frozenset(("リンク", "札")): "同じ役割（リンク）に同じ色を意図的に使い回している",
    # 状態・優先度のバッジは「色＋枠＋語」の3チャネル。語（未決/対応中/保留/完了・高/中/低）が常に併記される
    frozenset(("未着手地", "対応中地")): "バッジは地色だけでなく枠色と文字色が違い、何より語が併記される（CUD の冗長化）",
    frozenset(("対応中地", "完了地")): "同上。対応中=青の枠＋太字／完了=灰の枠＋灰の文字＋取り消し線の行",
    frozenset(("タブ未決", "タブ⚠")): "タブの札は必ず語か記号が前に付く（未決N／⚠N／★N）。色ではなく文字で読む",
    frozenset(("高地", "白地")): "優先度は語（高/中/低）が必ず併記され、高だけ枠と文字が赤系＋太字",
    frozenset(("高地", "低地")): "同上。高=赤系の枠と太字／低=灰の枠と薄字",
    frozenset(("低地", "白地")): "低は『目立たせない』のが意図。語と灰の枠で識別する",
    frozenset(("期限超過", "警告")): "別の列に出る（期限セルの数字 と タイトル脇の⚠）。形が数字と記号で異なり、隣接しない",
}

print("=== 隣接/重なりペアの ΔE（正常+P/D/T 最悪）===")
viol = []
for a, b in PAIRS:
    e = emin(a, b)
    waived = frozenset((a, b)) in ACCEPTED
    tag = ""
    if e < THRESH:
        tag = "  [許容: " + ACCEPTED[frozenset((a, b))] + "]" if waived else "  ⚠NEW"
        if not waived:
            viol.append((a, b, e))
    print(f"  {a:8}× {b:10} ΔE={e:5.1f}{tag}")

check(not viol, "新規の紛らわしい配色なし（ΔE<10 の非許容ペアがゼロ）"
      + ("" if not viol else " → " + ", ".join(f"{a}×{b}({e:.1f})" for a, b, e in viol)))

# ---- テキストの WCAG（本文 4.5 / 小字・副次は 3 を理由つきで許容）----
print("\n=== テキストのWCAGコントラスト ===")
TEXT = [
    # (名前, 文字, 地, 最低比, 3で許容する理由 or None)
    ("状態:未着手", "未着手字", "未着手地", 4.5, None),
    ("状態:対応中", "対応中字", "対応中地", 4.5, None),

    ("状態:完了", "完了字", "完了地", 4.5, None),
    ("優先度:高", "高字", "高地", 4.5, None),
    ("帯の文字", "帯字", "帯地", 4.5, None),
    ("印（薄字）", "印字", "白地", 4.5, None),
    ("印の添え字", "印の添え字", "白地", 3.0, "10px の添え字（相手名・再開条件）。前に必ず語（待ち／凍結）が付く"),
    ("未決の印", "未決の印", "白地", 4.5, None),
    ("タイトル横の未決", "タイトル横の未決", "白地", 4.5, None),
    ("済", "済", "白地", 4.5, None),
    ("未", "未", "白地", 3.0, "『まだ済んでいない』を薄さで示す意図的な減衰。語（未/☐）で冗長化"),
    ("完了行の未", "完了行の未", "完了行地", 3.0, "上と同じ意図的な減衰。灰背景でも溶けないよう一段濃くしてある"),
    ("期限超過", "期限超過", "白地", 4.5, None),
    ("警告⚠", "警告", "白地", 4.5, None),
    ("リンク行", "リンク", "白地", 3.0, "11px・タイトルより弱くする序列。ホバーで濃色＋下線になる"),
    ("逆引き札", "札", "白地", 3.0, "10px・タスク名より弱くする序列。ホバーで濃色＋下線になる"),
    ("★", "★", "白地", 4.5, None),
    ("本文", "本文", "白地", 4.5, None),
]
bad = []
for nm, fg, bg, need, why in TEXT:
    r = wcag(C[fg], C[bg])
    ok = r >= need
    note = "" if why is None else f"  [{need} で許容: {why}]"
    print(f"  {nm:12} 比={r:5.2f} (要{need}){'' if ok else '  ⚠不足'}{note}")
    if not ok:
        bad.append((nm, r, need))
check(not bad, "テキストのコントラストが基準を満たす"
      + ("" if not bad else " → " + ", ".join(f"{n}({r:.2f}<{k})" for n, r, k in bad)))

# ---- 参考：調和（明度/彩度レジスタ）----
print("\n=== 参考：主要な地色の L*/C*（パステル基調で揃うか）===")
chs = []
for nm in ["未着手地", "対応中地", "完了地", "高地", "低地", "帯地", "強調黄", "完了行地"]:
    L, a, bb = lab(hx(C[nm]))
    Cc = math.hypot(a, bb)
    chs.append((nm, Cc))
    print(f"  {nm:8} L*={L:5.1f}  C*={Cc:5.1f}")
med = sorted(c for _, c in chs)[len(chs) // 2]
out = [nm for nm, c in chs if c > med * 3]
if out:
    print(f"  ※高彩度の外れ値（中央値の3倍超）= {out} … パステル基調から浮く（要意図確認）")
finish()
