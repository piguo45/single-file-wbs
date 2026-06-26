"""配色監査（CUD＋隣接コントラスト＋調和）— 機能追加のたびの標準観点（#35）。

何を守るか:
  ・重なる/隣接する色の組が、色覚3型(P/D/T)でも区別できる（critical=情報が読めなくなる、を出さない）
  ・新しい色を足した時に、既存の意味色と紛れていないかを機械検出する
仕組み:
  ・wbs_viewer.html から実際の色を抽出（:root変数＋バー/状態のリテラル）→ 役割名で索引
  ・「物理的に重なる/隣接する」ペアだけを ΔE(正常+P/D/T最悪) で評価し、閾値未満を検出
  ・別チャネル（形・位置・装飾）で冗長化済みの既知ペアは ACCEPTED で待避（理由つき）
  ・テキストWCAGと調和(明度/彩度レジスタ)は参考出力（gateはしない＝色味の好みを強制しない）
ブラウザ不要の純Python。色を足す/変える機能では必ずここにペアを足すこと。"""
import re
import math
from common import ROOT, check, finish

HTML = (ROOT / "wbs_viewer.html").read_text(encoding="utf-8")

# ---- 色抽出（値が変わっても役割名で追える）----
def rootvars():
    return {m.group(1): m.group(2) for m in re.finditer(r'--([\w-]+):\s*(#[0-9a-fA-F]{3,6})', HTML)}
def lit(pat, label):
    m = re.search(pat, HTML)
    if not m:
        raise SystemExit(f"[color_audit] 色抽出に失敗（HTML構造が変わった?）: {label}")
    return m.group(1)
V = rootvars()
C = {
 "予定枠": V["plan-edge"], "実績": V["actual"],  # 予定=塗りなしの枠線／実績は全階層同色（親も同じ）
 "proj": V["proj"],
 "1L": V["lvl0"], "2L": V["lvl1"], "完了": V["done-bg"], "完了文字": V["done-fg"],
 "3L": lit(r'\.lvl2\{background:(#[0-9a-fA-F]{3,6})', "lvl2"),
 "over": lit(r'\.bar\.over\{[^}]*background:(#[0-9a-fA-F]{3,6})', "over"),
 "完了バー": lit(r'\.grow\.done \.bar\.actual\{background:(#[0-9a-fA-F]{3,6})', "done-bar"),
 "完了遅延": lit(r'\.grow\.done \.bar\.over\{background:(#[0-9a-fA-F]{3,6})', "done-over"),
 "遅延文字": lit(r'\.delay\{[^}]*color:(#[0-9a-fA-F]{3,6})', "delay"),
 # 土日/祝日の列地色＝--weekend（薄ピンク）。ヘッダはソリッド、ガント本体は半透明オーバーレイ(#d94f72 α=0.10)＝白行上の実効色がほぼ--weekendに一致するため代表値として--weekendを用いる
 "土": V["weekend"], "日": V["weekend"],
 "祝文字": "#dc2626",  # 祝日ヘッダ＝赤字（地色は土日と同じ薄ピンク。区別は色相でなく赤字＝別チャネル）
 "イナズマ": lit(r'<circle[^>]*r="2\.5"[^>]*fill="(#[0-9a-fA-F]{3,6})"', "inazuma"),  # r=2.5でロゴ円(#1e2f63)を除外
 "MS既定": lit(r'isColor\(m\.color\)\?m\.color:"(#[0-9a-fA-F]{3,6})"', "ms-default"),
 "進捗トラック": lit(r'\.ptrack\{[^}]*background:(#[0-9a-fA-F]{3,6})', "ptrack"),  # 進捗ビュー：未達トラック(青グレー)
 "進捗完了": lit(r'\.prw\.done \.pbar\.act\{background:(#[0-9a-fA-F]{3,6})', "prw-done"),  # 進捗ビュー：完了バー(グレー)
}

# ---- 色計算 ----
def s2l(c):
    c /= 255; return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
def hx(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    return [s2l(int(h[i:i+2], 16)) for i in (0, 2, 4)]
def lab(rgb):
    r, g, b = rgb
    X = r*0.4124+g*0.3576+b*0.1805; Y = r*0.2126+g*0.7152+b*0.0722; Z = r*0.0193+g*0.1192+b*0.9505
    def f(t): return t**(1/3) if t > 0.008856 else 7.787*t+16/116
    fx, fy, fz = f(X/0.95047), f(Y), f(Z/1.08883)
    return (116*fy-16, 500*(fx-fy), 200*(fy-fz))
def dE(a, b): return math.sqrt(sum((x-y)**2 for x, y in zip(lab(a), lab(b))))
def Yl(rgb): r, g, b = rgb; return r*0.2126+g*0.7152+b*0.0722
def wcag(h1, h2):
    a, b = Yl(hx(h1)), Yl(hx(h2)); L, D = max(a, b), min(a, b); return (L+0.05)/(D+0.05)
# Machado 2009 severity=1.0（linear RGBに適用）
MAT = {"P": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
       "D": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
       "T": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]}
def cvd(c, m): return [sum(m[i][j]*c[j] for j in range(3)) for i in range(3)]
def emin(a, b):
    la, lb = hx(C[a]), hx(C[b])
    return min([dE(la, lb)] + [dE(cvd(la, MAT[k]), cvd(lb, MAT[k])) for k in "PDT"])

# ---- 物理的に重なる/隣接するペア（色を足したらここに足す）----
PAIRS = [
 # ① 同レーンのバー同士（予定=枠／実績は全階層で同色＝親子はバー色で区別しない。着手遅れは枠の空きで表現＝専用色なし）
 ("予定枠", "実績"), ("実績", "over"),
 ("完了バー", "実績"), ("完了バー", "完了"),  # 完了(グレー)は進行中(青)・完了行地色から見分けられること
 ("完了遅延", "over"), ("完了遅延", "完了バー"),  # 完了済み遅延(くすみ赤)は進行中遅延(鮮赤)・完了バー(グレー)から見分けられること
 # ② バー × 週末列の地色
 ("予定枠", "土"), ("予定枠", "日"), ("実績", "日"), ("over", "日"),
 # ③ オーバーレイ線 × 横切るバー
 ("イナズマ", "実績"), ("イナズマ", "予定枠"), ("イナズマ", "over"),
 ("MS既定", "実績"), ("MS既定", "予定枠"), ("MS既定", "over"),
 # ④ 階層の隣接
 ("proj", "1L"), ("1L", "2L"), ("2L", "3L"),
 # ⑤ 完了行
 ("完了", "2L"), ("完了", "予定枠"),
 # ⑥ 進捗ビュー：未達トラック（青グレー）× 同レーンのバー（青=実績／赤=不足分／グレー=完了）
 ("進捗トラック", "実績"), ("進捗トラック", "over"), ("進捗トラック", "進捗完了"),
]
THRESH = 10.0  # 隣接フィル/線は最悪CVDでΔE>=10を要求
# 別チャネル（形・位置・装飾）で冗長化済み＝ΔE未満でも許容する既知ペア（理由必須）
ACCEPTED = {
 frozenset(("イナズマ", "over")): "両方=遅延の赤・意味的に同義（赤線が赤バー上で同化しても情報損失なし）",
 frozenset(("2L", "3L")): "階層は字下げ＋太字（lvl0=bold/lvl1=600/lvl2=通常）で区別",
 frozenset(("完了", "2L")): "完了は取り消し線＋✓＋淡色文字で多重識別",
}

print("=== 隣接/重なりペアの ΔE（正常+P/D/T 最悪）===")
viol = []
for a, b in PAIRS:
    e = emin(a, b); waived = frozenset((a, b)) in ACCEPTED
    tag = ""
    if e < THRESH:
        tag = "  [許容: " + ACCEPTED[frozenset((a, b))] + "]" if waived else "  ⚠NEW"
        if not waived: viol.append((a, b, e))
    print(f'  {a:6}× {b:8} ΔE={e:5.0f}{tag}')

check(not viol, "新規の紛らわしい配色なし（ΔE<10 の非許容ペアがゼロ）"
      + ("" if not viol else " → " + ", ".join(f"{a}×{b}({e:.0f})" for a, b, e in viol)))

# ---- 参考：テキストWCAG（gateしない）----
print("\n=== 参考：テキストのWCAGコントラスト（AA本文4.5・大文字3）===")
for nm, fg, bg in [("遅延ラベル赤", "遅延文字", "2L"), ("遅延ラベル赤/白地", "遅延文字", "3L"),
                   ("完了文字", "完了文字", "完了"), ("祝日赤字/薄ピンク地", "祝文字", "土")]:
    r = wcag(C[fg], C[bg]); print(f'  {nm:16} 比={r:4.1f}' + (" (AA未満・副次/bold)" if r < 4.5 else ""))

# ---- 参考：調和（明度/彩度レジスタ）----
print("\n=== 参考：調和 主要フィルの L*/C*（パステル=高L低中C で揃うか）===")
chs = []
for nm in ["予定枠", "実績", "over", "完了バー", "完了遅延", "proj", "1L", "2L", "完了"]:
    L, a, bb = lab(hx(C[nm])); Cc = math.hypot(a, bb); chs.append((nm, Cc))
    print(f'  {nm:6} L*={L:5.1f}  C*={Cc:5.1f}')
med = sorted(c for _, c in chs)[len(chs)//2]
out = [nm for nm, c in chs if c > med*3]
if out: print(f'  ※高彩度の外れ値（中央値の3倍超）= {out} … パステル基調から浮く（要意図確認）')

finish()
