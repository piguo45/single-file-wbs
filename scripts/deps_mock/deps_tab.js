// 依存タブ（構造の軸）の「動くモック」第3版＝案G′（方眼紙・自動配置・ゴム線）。
// 製品 wbs_viewer.html には手を入れず、生成物 deps_mock.html の末尾に丸ごと差し込んで動かす
// （scripts/build_deps_mock.py）。設計メモ: docs/design/brief-deps.md v0.2（§3 画面・§4 操作・§5 計算）。
//
// モックなので JSON へは保存しない。メモリ上のデータ（window.__PM.data()）を書き換えて
// 描き直すだけ＝「保存済」表示も出さない・queueSave も呼ばない。
(function(){
  "use strict";
  var PM = window.__PM;
  if(!PM || typeof PM.data !== "function")return;            // 橋が無い＝製品が変わった。何もしない（壊さない）

  // ===== 方眼と見た目の定数（色は製品の CSS 変数と同じ値のリテラル＝SVG属性は var() を解決しない） =====
  var CELL = 44;          // マスの1辺。○の直径＝1マス（brief §3）
  var R = 21;             // ○の半径（直径 42 ≒ マス 44・線の太さぶん内側）
  var PAD = CELL;         // 方眼の外側の余白＝1マス
  var STEP = 2;           // 置けるマスは1マスおき＝偶数の列・行（○の周りは必ず1マス空く）
  var COL_STEP = 4;       // 自動配置の段の間隔（マス）。名前（全角9字≒95px）が隣とぶつからない幅を取る
  var DRAG_MIN = 4;       // これ以下の動きはクリック扱い（誤ドラッグ防止・brief B3）
  var C = {
    grid: "#eceef1",      // 方眼の線（= --grid）
    node: "#4a6a9e",      // ○の輪郭・番号（= --plan-edge）
    text: "#1f2430",      // 名前（= --text）
    muted: "#6b7280",     // 添え字（= --muted）
    arrow: "#9aa2ad",     // 矢印（= --btn-border）
    accent: "#2563eb",    // 選択・ゴム線（= --accent）
    red: "#e11d48",       // 最長経路・違反（= 既存の遅延赤）
    ms: "#cc79a7"         // マイルストーン（= 製品と同じ Okabe-Ito モーブ）
  };

  // ===== ホバーの濃淡と ✕ は CSS で（属性では書けない・自前の style を1枚だけ足す） =====
  (function css(){
    if(document.getElementById("depsMockCss"))return;
    var s = document.createElement("style");
    s.id = "depsMockCss";
    s.textContent = [
      "#depsSvg .dedge{opacity:.5}",                          // 既定は薄く（brief §3）
      "#depsSvg .dedge:hover,#depsSvg .dedge.dsel,#depsSvg .dedge.dcrit{opacity:1}",
      "#depsSvg .dedge .dx{opacity:0;cursor:pointer}",        // 矢印ホバーで中点に ✕（外す）
      "#depsSvg .dedge:hover .dx{opacity:1}",
      "#depsSvg .dnode{cursor:pointer}",
      "#depsSvg.dlinking .dnode:hover .dcore{stroke:" + C.accent + ";stroke-width:3}",  // ゴム線中は相手が光る
      "#depsSvg .dnode:hover .dname{font-weight:600}"
    ].join("\n");
    document.head.appendChild(s);
  })();

  // ===== 小道具（製品の esc/日付ヘルパは閉じた中にあるので自前で持つ） =====
  var DAY_MS = 86400000;
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }
  function isDate(s){ return typeof s === "string" && /^(19|20)\d{2}-\d{2}-\d{2}$/.test(s); }
  function ms(s){ return Date.UTC(+s.slice(0,4), +s.slice(5,7)-1, +s.slice(8,10)); }    // 日付→通し時刻
  function diffD(a,b){ return Math.round((ms(b) - ms(a)) / DAY_MS); }                   // a→b の日数
  function md(s){ return isDate(s) ? (+s.slice(5,7)) + "/" + (+s.slice(8,10)) : "—"; }  // 9/18 表記
  function cut(s,n){ s = String(s||""); return s.length > n ? s.slice(0,n) + "…" : s; }  // 名前を n 字で切る
  function today(){ return typeof PM.today === "function" ? PM.today() : new Date().toISOString().slice(0,10); }
  function num(v){ return Number.isFinite(Number(v)) ? Number(v) : 0; }
  // クリック地点の下にある要素を上から順に見て、最初に見つかった sel を返す（重なりの解決）
  function hit(e, sel){
    var stack = document.elementsFromPoint ? document.elementsFromPoint(e.clientX, e.clientY) : [];
    for(var i = 0; i < stack.length; i++){
      var m = stack[i].closest ? stack[i].closest(sel) : null;
      if(m)return m;
    }
    return e.target.closest ? e.target.closest(sel) : null;
  }

  // ===== データの取り出し =====
  function firstProject(){                                   // モックは先頭の（計画を持つ）案件だけを見る
    var d = PM.data();
    var ps = (d && Array.isArray(d.projects)) ? d.projects : [];
    for(var i = 0; i < ps.length; i++)if(ps[i] && Array.isArray(ps[i].tasks) && ps[i].tasks.length)return ps[i];
    return null;
  }
  function leavesOf(tasks, out){                             // 葉（children を持たない節）を並び順に集める
    (tasks||[]).forEach(function(n){
      if(!n || typeof n !== "object")return;
      if(Array.isArray(n.children) && n.children.length)leavesOf(n.children, out);
      else out.push(n);
    });
    return out;
  }
  function phases(proj){                                     // チェックリスト用：第1階層ごとの葉のまとまり
    return (proj.tasks||[]).filter(function(n){ return n && typeof n === "object"; })
      .map(function(n){ return { id:String(n.id), name:String(n.name||""), leaves:leavesOf([n],[]) }; });
  }
  function hasDeps(n){ return !!n && Array.isArray(n._deps); }             // 図に載る＝_deps キーがある
  function planOf(n){ var p = n.plan||{}; return { s:isDate(p.start)?p.start:null, e:isDate(p.end)?p.end:null }; }
  function posOf(n){                                         // 手で置き直した位置（[列,行]・偶数の整数だけ有効）
    var p = n._pos;
    if(!Array.isArray(p) || p.length !== 2)return null;
    var c = Math.round(num(p[0])), r = Math.round(num(p[1]));
    if(!(c >= 0 && r >= 0) || c % STEP || r % STEP)return null;
    return [c, r];
  }

  // ===== 計算（brief §5・ビューアが決定論的に） =====
  function graph(proj){
    var all = leavesOf(proj.tasks, []);
    var nodes = all.filter(hasDeps).filter(function(n){ var p = planOf(n); return p.s && p.e; });
    var byId = {}, pred = {}, succ = {};
    nodes.forEach(function(n){ byId[String(n.id)] = n; pred[String(n.id)] = []; succ[String(n.id)] = []; });
    // 前工程（参照先が無い／自己参照は console.warn して無視）
    nodes.forEach(function(n){
      var id = String(n.id);
      n._deps.forEach(function(raw){
        var p = String(raw);
        if(p === id){ console.warn("[deps] 自己参照を無視: " + id); return; }
        if(!byId[p]){ console.warn("[deps] 参照先が無いので無視: " + id + " → " + p); return; }
        if(pred[id].indexOf(p) < 0)pred[id].push(p);
      });
    });
    // 循環は落として警告（描けないより、警告して描く）
    function ancestor(from, goal, seen){                     // from の前工程を辿って goal に着くか
      if(from === goal)return true;
      if(seen[from])return false; seen[from] = 1;
      return pred[from].some(function(p){ return ancestor(p, goal, seen); });
    }
    nodes.forEach(function(n){
      var id = String(n.id);
      pred[id] = pred[id].filter(function(p){
        if(ancestor(p, id, {})){ console.warn("[deps] 循環を無視: " + p + " → " + id); return false; }
        return true;
      });
    });
    Object.keys(pred).forEach(function(id){ pred[id].forEach(function(p){ succ[p].push(id); }); });

    // 段＝トポロジカル順（前工程の段＋1）
    var rank = {};
    function rk(id){
      if(rank[id] != null)return rank[id];
      rank[id] = 0;                                          // 循環は上で落としているので再入は無い
      rank[id] = pred[id].length ? Math.max.apply(null, pred[id].map(rk)) + 1 : 0;
      return rank[id];
    }
    nodes.forEach(function(n){ rk(String(n.id)); });

    // 日数＝予定の期間（暦日）＝plan.end − plan.start + 1（矢印の数字はこれ・brief §5）
    var days = {}, ids = nodes.map(function(n){ return String(n.id); });
    nodes.forEach(function(n){ var p = planOf(n); days[String(n.id)] = Math.max(1, diffD(p.s, p.e) + 1); });

    // 実質の終了日＝予定終了と実績終了の遅い方（進行中で本日 > 予定終了なら本日）
    var TD = today();
    function effEnd(n){
      var p = planOf(n), a = n.actual || {};
      var ae = isDate(a.end) ? a.end : null, as = isDate(a.start) ? a.start : null;
      if(ae)return ae > p.e ? ae : p.e;
      if(as && TD > p.e)return TD;
      return p.e;
    }
    // 違反＝後続の予定開始 ≤ 前工程の実質の終了日。予定だけで割れているか、実遅れで割れたかを分けて持つ
    var info = {};
    nodes.forEach(function(n){
      var id = String(n.id), p = planOf(n), viol = null, late = null;
      pred[id].forEach(function(q){
        var pe = planOf(byId[q]).e, ee = effEnd(byId[q]);
        if(p.s <= pe){ if(!viol)viol = { from:q, end:pe, gap:diffD(p.s, pe) + 1 }; }
        else if(p.s <= ee){ if(!late)late = { from:q, end:ee, gap:diffD(p.s, ee) + 1 }; }
      });
      info[id] = { node:n, id:id, name:String(n.name||""), start:p.s, end:p.e, days:days[id],
        load:(num(n.qty) * num(n.hours) / 8), rank:rank[id], pred:pred[id], succ:succ[id],
        viol:viol, late:late, effEnd:effEnd(n) };
    });

    // 最長経路＝日数の和が最大の経路（◇まで）。up=ここまで／down=この先（ホバーの「この○を通る」に使う）
    var order = ids.slice().sort(function(a,b){ return (rank[a] - rank[b]) || (a < b ? -1 : 1); });
    var up = {}, upFrom = {};
    order.forEach(function(id){
      var best = 0, from = null;
      pred[id].forEach(function(q){ if(up[q] > best || (up[q] === best && from === null)){ best = up[q]; from = q; } });
      up[id] = best + days[id]; upFrom[id] = from;
    });
    var down = {};
    order.slice().reverse().forEach(function(id){
      var best = 0;
      succ[id].forEach(function(q){ if(down[q] > best)best = down[q]; });
      down[id] = best + days[id];
    });
    // 経路の終点＝up（ここまでの日数の和）が最大の○。同値なら番号の小さい方（決定的）
    var tail = null;
    order.forEach(function(id){
      if(!tail || up[id] > up[tail] || (up[id] === up[tail] && id < tail))tail = id;
    });
    var path = [], pathSet = {}, pathEdges = {};
    for(var v = tail; v; v = upFrom[v]){ path.unshift(v); pathSet[v] = 1; }
    for(var i = 1; i < path.length; i++)pathEdges[path[i-1] + ">" + path[i]] = 1;
    var pathDays = tail ? up[tail] : 0;

    // ◇＝案件の最遅マイルストーン。「予定では残り M 日」＝経路の開始から◇までの暦日（両端を含む）
    var msList = (Array.isArray(proj.milestones) ? proj.milestones : []).filter(function(m){ return m && isDate(m.date); });
    var lastMs = null;
    msList.forEach(function(m){ if(!lastMs || m.date > lastMs.date)lastMs = m; });
    var msDays = (lastMs && path.length) ? diffD(info[path[0]].start, lastMs.date) + 1 : null;

    return { proj:proj, all:all, nodes:nodes, byId:byId, info:info, order:order, ids:ids,
      pred:pred, succ:succ, rank:rank, days:days, up:up, down:down,
      path:path, pathSet:pathSet, pathEdges:pathEdges, pathDays:pathDays,
      ms:lastMs, msDays:msDays,
      maxRank:ids.length ? Math.max.apply(null, ids.map(function(id){ return rank[id]; })) : 0 };
  }

  // 段の中の並びを重心法で決める（前工程／後続の平均行に寄せ、左右に数回往復＝交差が減る・決定的）
  function autoOrder(g){
    var lanes = [];                                          // lanes[段] = 番号の配列（この順が行）
    for(var k = 0; k <= g.maxRank; k++)lanes.push([]);
    g.ids.slice().sort(function(a,b){                        // 初期順＝開始日→番号（同じ入力なら必ず同じ）
      var A = g.info[a], B = g.info[b];
      return (A.start < B.start ? -1 : A.start > B.start ? 1 : 0) || (a < b ? -1 : 1);
    }).forEach(function(id){ lanes[g.info[id].rank].push(id); });

    var rowOf = {};
    function rows(){ lanes.forEach(function(L){ L.forEach(function(id, i){ rowOf[id] = i; }); }); }
    rows();
    function bary(id, side){                                 // 前工程（up）／後続（down）の平均行
      var rel = side === "up" ? g.pred[id] : g.succ[id];
      if(!rel.length)return rowOf[id];
      return rel.reduce(function(s, q){ return s + rowOf[q]; }, 0) / rel.length;
    }
    for(var pass = 0; pass < 4; pass++){                     // 4往復で十分（葉が数十なら一瞬）
      for(var k1 = 1; k1 <= g.maxRank; k1++)sortLane(lanes[k1], "up");
      for(var k2 = g.maxRank - 1; k2 >= 0; k2--)sortLane(lanes[k2], "down");
    }
    return lanes;
    function sortLane(L, side){                              // 重心で並べ替え（同じ重心なら元の順＝安定）
      var key = {};
      L.forEach(function(id, i){ key[id] = [bary(id, side), i]; });
      L.sort(function(a,b){ return (key[a][0] - key[b][0]) || (key[a][1] - key[b][1]); });
      rows();
    }
  }

  // 自動配置＋手動配置（_pos）を混ぜて、1マスおきの格子の上に置く
  function layout(g){
    var lanes = autoOrder(g), pos = {}, used = {};
    function take(c, r){ used[c + "," + r] = 1; }
    function free(c, r){ return !used[c + "," + r]; }
    g.ids.forEach(function(id){                              // 手で置いた○を先に確定（例外が自動に負けない）
      var p = posOf(g.info[id].node);
      if(p && free(p[0], p[1])){ pos[id] = p; take(p[0], p[1]); }
    });
    lanes.forEach(function(L, k){                            // 残りは 列＝段×2、行＝段の中の並び×2
      L.forEach(function(id, i){
        if(pos[id])return;
        var c = k * COL_STEP, r = i * STEP;
        while(!free(c, r))r += STEP;                         // 埋まっていたら下へ（決定的）
        pos[id] = [c, r]; take(c, r);
      });
    });
    var maxC = 0, maxR = 0;
    g.ids.forEach(function(id){ maxC = Math.max(maxC, pos[id][0]); maxR = Math.max(maxR, pos[id][1]); });
    g.pos = pos; g.maxC = maxC; g.maxR = maxR;
    g.msCell = [maxC + STEP, g.path.length ? pos[g.path[g.path.length-1]][1] : 0];   // ◇は最右列・経路の終点の行
    g.crossings = countCross(g);
    return g;
  }
  function cx(c){ return PAD + c * CELL + CELL / 2; }        // 列→中心x
  function cy(r){ return PAD + r * CELL + CELL / 2; }        // 行→中心y
  function countCross(g){                                    // 交差数（自動配置の出来を数字で見るため）
    var segs = [];
    g.ids.forEach(function(id){
      g.pred[id].forEach(function(p){
        segs.push([cx(g.pos[p][0]), cy(g.pos[p][1]), cx(g.pos[id][0]), cy(g.pos[id][1]), p, id]);
      });
    });
    var n = 0;
    for(var i = 0; i < segs.length; i++)for(var j = i + 1; j < segs.length; j++){
      var a = segs[i], b = segs[j];
      if(a[4] === b[4] || a[4] === b[5] || a[5] === b[4] || a[5] === b[5])continue;   // 端点を共有する矢印は数えない
      if(cross(a, b))n++;
    }
    return n;
    function side(x1,y1,x2,y2,x,y){ var v = (x2-x1)*(y-y1) - (y2-y1)*(x-x1); return v > 0 ? 1 : v < 0 ? -1 : 0; }
    function cross(a,b){
      return side(a[0],a[1],a[2],a[3],b[0],b[1]) * side(a[0],a[1],a[2],a[3],b[2],b[3]) < 0
          && side(b[0],b[1],b[2],b[3],a[0],a[1]) * side(b[0],b[1],b[2],b[3],a[2],a[3]) < 0;
    }
  }

  // ===== 画面の状態（localStorage は汚さない＝製品の記憶に触らない） =====
  var selected = null;     // 選択中の○（番号）。ゴム線を引いている○
  var pickOpen = false;    // 「図に載せる」パネルが開いているか（既定＝畳む）
  var zoom = 1;            // 50 / 75 / 100%
  var undo = null;         // Ctrl+Z の1段（_deps と _pos のスナップショット）

  var LEGEND = "○＝作業（中＝番号・下＝名前）。直径＝1マス、周りは必ず1マス空ける\n"
    + "矢印＝依存（前→後）。上の数字＝前の作業の暦日数（予定の期間）\n"
    + "赤い○と太い赤矢印＝最長経路（右下に合計日数）\n"
    + "赤く塗った○＝違反（後続の開始が前工程の終了以前・実績の遅れ込み）\n"
    + "◇＝案件の最遅マイルストーン（横に予定の残りと差）\n"
    + "○をクリック＝ゴム線（別の○でクリックして結ぶ・Esc で取消）\n"
    + "○をドラッグ＝置き直す（1マスおきに吸着・Ctrl+Z で戻す）\n"
    + "矢印にホバー＝中点の ✕ で外す（Ctrl+Z で戻す）\n"
    + "○をダブルクリック＝時間タブのその行へ";

  function snapshot(g){                                      // Ctrl+Z 用に _deps/_pos だけ控える（1段）
    undo = g.nodes.map(function(n){
      return { n:n, deps:Array.isArray(n._deps) ? n._deps.slice() : null,
        pos:Array.isArray(n._pos) ? n._pos.slice() : null };
    });
  }
  function restore(){                                        // 控えを戻す（無ければ何もしない）
    if(!undo)return false;
    undo.forEach(function(u){
      if(u.deps)u.n._deps = u.deps.slice(); else delete u.n._deps;
      if(u.pos)u.n._pos = u.pos.slice(); else delete u.n._pos;
    });
    undo = null;
    return true;
  }

  // ===== 描画 =====
  function tip(g, d){                                        // ○のツールチップ（brief §3「常時は番号と名前だけ」）
    var L = [];
    L.push(d.id + " " + d.name + "　" + d.days + "日（" + (Math.round(d.load * 10) / 10) + "人日）");
    L.push("開始 " + md(d.start) + " → 終了 " + md(d.end));
    if(d.viol)L.push("違反：前工程 " + d.viol.from + " の終了 " + md(d.viol.end) + " 以前に始まる予定（" + d.viol.gap + "日ぶん重なる）");
    else if(d.late)L.push("違反：前工程 " + d.late.from + " が実績で " + md(d.late.end) + " まで延び、開始が追い越された（" + d.late.gap + "日ぶん）");
    var thru = g.up[d.id] + g.down[d.id] - d.days;
    L.push("この○を通る最長経路 " + thru + "日（図の最長経路 " + g.pathDays + "日）");
    if(g.msDays != null)L.push("予定との差：◇まで 残り " + g.msDays + "日・差 " + (g.msDays - thru) + "日");
    L.push("前工程：" + (d.pred.length ? d.pred.map(function(p){ return p + " " + cut(g.info[p].name, 10); }).join("・") : "なし"));
    L.push("後続：" + (d.succ.length ? d.succ.map(function(q){ return q + " " + cut(g.info[q].name, 10); }).join("・") : "なし"));
    L.push("ダブルクリック＝時間タブで見る");
    return L.join("\n");
  }
  function svgOf(g){
    if(!g.ids.length)return '<div style="padding:24px;color:' + C.muted + '">'
      + '図に載せる作業がありません。ヘッダ左の「図に載せる」から選んでください（チェック＝<code>_deps: []</code>）。</div>';
    var W = PAD * 2 + (g.msCell[0] + 5) * CELL;              // ◇の右にラベルぶんの余白
    var H = PAD * 2 + (Math.max(g.maxR, g.msCell[1]) + 3) * CELL;
    var body = "";

    // 方眼（1マスごとの薄い線）
    for(var x = PAD; x <= W - PAD; x += CELL)
      body += '<line x1="' + x + '" y1="' + PAD + '" x2="' + x + '" y2="' + (H - PAD) + '" stroke="' + C.grid + '"/>';
    for(var y = PAD; y <= H - PAD; y += CELL)
      body += '<line x1="' + PAD + '" y1="' + y + '" x2="' + (W - PAD) + '" y2="' + y + '" stroke="' + C.grid + '"/>';

    // ◇（案件の最遅マイルストーン）＋ 予定の残りと差
    var mcx = cx(g.msCell[0]), mcy = cy(g.msCell[1]);
    if(g.ms){
      var msCol = (typeof g.ms.color === "string" && /^#[0-9a-fA-F]{3,8}$/.test(g.ms.color)) ? g.ms.color : C.ms;
      body += '<g id="depsMs"><title>' + esc(String(g.ms.label||"") + " " + md(g.ms.date)
        + (g.msDays != null ? ("\n予定では残り " + g.msDays + "日・最長経路 " + g.pathDays + "日・差 " + (g.msDays - g.pathDays) + "日") : ""))
        + '</title>'
        + '<polygon points="' + mcx + ',' + (mcy-15) + ' ' + (mcx+15) + ',' + mcy + ' ' + mcx + ',' + (mcy+15) + ' '
        + (mcx-15) + ',' + mcy + '" fill="#fff" stroke="' + msCol + '" stroke-width="2"/>'
        + '<text x="' + (mcx+22) + '" y="' + (mcy+4) + '" font-size="11" fill="' + C.text + '">'
        + esc(String(g.ms.label||"") + "　" + md(g.ms.date)) + '</text>'
        + (g.msDays != null ? '<text x="' + (mcx+22) + '" y="' + (mcy+19) + '" font-size="10" fill="' + C.muted + '">'
            + '予定では残り ' + g.msDays + '日・差 ' + (g.msDays - g.pathDays) + '日</text>' : "")
        + '</g>';
      // ◇へ結ぶのは最長経路の終点だけ（後続の無い○すべてから引くと桃色の線で図が埋まる）
      if(g.path.length){
        var t = g.path[g.path.length-1];
        var e0 = edgePts(cx(g.pos[t][0]), cy(g.pos[t][1]), mcx, mcy, R, 16);
        body += '<line x1="' + e0[0] + '" y1="' + e0[1] + '" x2="' + e0[2] + '" y2="' + e0[3]
          + '" stroke="' + C.red + '" stroke-width="2.8"/>';
      }
    }

    // 矢印（依存だけ・直線・上に前の作業の日数）
    g.ids.forEach(function(id){
      g.pred[id].forEach(function(p){
        var a = [cx(g.pos[p][0]), cy(g.pos[p][1])], b = [cx(g.pos[id][0]), cy(g.pos[id][1])];
        var e = edgePts(a[0], a[1], b[0], b[1], R, R + 1);
        var crit = !!g.pathEdges[p + ">" + id];
        var sel = selected && (selected === id || selected === p);
        var col = crit ? C.red : C.arrow, w = crit ? 2.8 : 1.4;
        var lbl = labelAt(e, g, p, id);                       // 数字は根元側 1/3・交差付近は法線方向へ逃がす
        body += '<g class="dedge' + (crit ? " dcrit" : "") + (sel ? " dsel" : "") + '"'
          + ' data-from="' + esc(p) + '" data-to="' + esc(id) + '">'
          + '<title>' + esc(p + " " + cut(g.info[p].name, 10) + " → " + id + " " + cut(g.info[id].name, 10)
            + "\n" + g.days[p] + "日（" + md(g.info[p].start) + "〜" + md(g.info[p].end) + "）\nホバー中の ✕ で外す") + '</title>'
          + '<line class="dline" x1="' + e[0] + '" y1="' + e[1] + '" x2="' + e[2] + '" y2="' + e[3]
          + '" stroke="' + col + '" stroke-width="' + w + '"/>'
          + '<line class="dhit" x1="' + e[0] + '" y1="' + e[1] + '" x2="' + e[2] + '" y2="' + e[3]
          + '" stroke="transparent" stroke-width="12" pointer-events="stroke"/>'
          + head(e, col)
          + '<text class="dnum" x="' + lbl[0] + '" y="' + lbl[1] + '" font-size="' + (crit ? 12 : 11)
          + '" font-weight="' + (crit ? 700 : 400) + '" text-anchor="middle" fill="' + (crit ? C.red : C.muted)
          + '" pointer-events="none">' + g.days[p] + '</text>'
          + '<g class="dx" data-from="' + esc(p) + '" data-to="' + esc(id) + '">'
          + '<circle cx="' + ((e[0]+e[2])/2) + '" cy="' + ((e[1]+e[3])/2) + '" r="8" fill="#fff" stroke="' + C.red + '"/>'
          + '<text x="' + ((e[0]+e[2])/2) + '" y="' + ((e[1]+e[3])/2 + 4) + '" font-size="11" text-anchor="middle"'
          + ' fill="' + C.red + '" pointer-events="none">✕</text></g>'
          + '</g>';
      });
    });

    // ○（直径＝1マス・中に番号・下に名前）
    g.order.forEach(function(id){
      var d = g.info[id], p = g.pos[id], x = cx(p[0]), y = cy(p[1]);
      var crit = !!g.pathSet[id], bad = !!(d.viol || d.late);
      body += '<g class="dnode" data-id="' + esc(id) + '" data-c="' + p[0] + '" data-r="' + p[1] + '"'
        + (crit ? ' data-crit="1"' : "") + (d.viol ? ' data-viol="1"' : "") + (d.late ? ' data-late="1"' : "")
        + '><title>' + esc(tip(g, d)) + '</title>'
        + (selected === id ? '<circle cx="' + x + '" cy="' + y + '" r="' + (R+5) + '" fill="none" stroke="' + C.accent
            + '" stroke-width="1.4" stroke-dasharray="4 3"/>' : "")
        + '<circle class="dcore" cx="' + x + '" cy="' + y + '" r="' + R + '" fill="' + (bad ? C.red : "#fff")
        + '" stroke="' + (crit || bad ? C.red : C.node) + '" stroke-width="' + (crit ? 3 : 1.8) + '"/>'
        + '<text x="' + x + '" y="' + (y+4) + '" font-size="11" font-weight="600" text-anchor="middle"'
        + ' pointer-events="none" fill="' + (bad ? "#fff" : (crit ? C.red : C.node)) + '">' + esc(id) + '</text>'
        + '<text class="dname" x="' + x + '" y="' + (y + R + 15) + '" font-size="10.5" text-anchor="middle"'
        + ' fill="' + (crit || bad ? C.red : C.text) + '">' + esc(cut(d.name, 9)) + '</text>'
        + '</g>';
    });

    // 右下に「最長経路 N 日」（「クリティカルパス」とは呼ばない＝予定日数と混同させないため）
    body += '<text x="' + (W - PAD - 6) + '" y="' + (H - PAD - 8) + '" font-size="12" font-weight="700"'
      + ' text-anchor="end" fill="' + C.red + '">最長経路 ' + g.pathDays + ' 日</text>'
      + '<text x="' + (W - PAD - 6) + '" y="' + (H - PAD + 8) + '" font-size="10" text-anchor="end" fill="' + C.muted + '">'
      + esc(g.path.join(" → ")) + '</text>';

    // ゴム線（結ぶ操作の線。始点は選択中の○・終点はカーソルで動かす）
    body += '<line id="depsRubber" x1="0" y1="0" x2="0" y2="0" stroke="' + C.accent
      + '" stroke-width="1.8" stroke-dasharray="5 4" pointer-events="none" style="display:none"/>';
    // 置ける所の光（ドラッグ中だけ出す）
    body += '<rect id="depsSnap" width="' + CELL + '" height="' + CELL + '" rx="4" fill="' + C.accent
      + '" opacity=".12" pointer-events="none" style="display:none"/>';

    return '<svg id="depsSvg" width="' + (W * zoom) + '" height="' + (H * zoom) + '" data-w="' + W + '" data-h="' + H
      + '" style="display:block;background:#fff">'
      + '<g id="depsZoom" transform="scale(' + zoom + ')">' + body + '</g></svg>';
  }
  function edgePts(x1,y1,x2,y2,r1,r2){                       // ○の縁から縁までの線（中心同士を結んで半径ぶん詰める）
    var dx = x2 - x1, dy = y2 - y1, L = Math.sqrt(dx*dx + dy*dy) || 1;
    return [x1 + dx/L*r1, y1 + dy/L*r1, x2 - dx/L*r2, y2 - dy/L*r2];
  }
  function head(e, col){                                     // 矢印の頭（線の向きに合わせた三角形）
    var dx = e[2] - e[0], dy = e[3] - e[1], L = Math.sqrt(dx*dx + dy*dy) || 1;
    var ux = dx/L, uy = dy/L, nx = -uy, ny = ux, b = 9, w = 4.2;
    return '<polygon points="' + e[2] + ',' + e[3] + ' ' + (e[2]-ux*b+nx*w) + ',' + (e[3]-uy*b+ny*w) + ' '
      + (e[2]-ux*b-nx*w) + ',' + (e[3]-uy*b-ny*w) + '" fill="' + col + '"/>';
  }
  function labelAt(e, g, p, id){                             // 数字の位置＝根元側 1/3 の法線方向。近くに他の矢印があれば逃がす
    var dx = e[2] - e[0], dy = e[3] - e[1], L = Math.sqrt(dx*dx + dy*dy) || 1;
    var mx = e[0] + dx/3, my = e[1] + dy/3;
    var nx = -dy/L, ny = dx/L;
    if(ny > 0){ nx = -nx; ny = -ny; }                        // いつも線の上側へ
    var off = 11, near = 0;
    g.ids.forEach(function(o){                               // 他の矢印との距離を見て、近ければ余分に逃がす
      g.pred[o].forEach(function(q){
        if((q === p && o === id))return;
        var a = [cx(g.pos[q][0]), cy(g.pos[q][1])], b = [cx(g.pos[o][0]), cy(g.pos[o][1])];
        if(distToSeg(mx + nx*off, my + ny*off, a[0], a[1], b[0], b[1]) < 12)near++;
      });
    });
    if(near)off += 9;
    return [mx + nx*off, my + ny*off + 3];
  }
  function distToSeg(px,py,x1,y1,x2,y2){                     // 点と線分の距離（数字の逃がし判定に使う）
    var dx = x2-x1, dy = y2-y1, L2 = dx*dx + dy*dy;
    var t = L2 ? Math.max(0, Math.min(1, ((px-x1)*dx + (py-y1)*dy) / L2)) : 0;
    var qx = x1 + t*dx, qy = y1 + t*dy;
    return Math.sqrt((px-qx)*(px-qx) + (py-qy)*(py-qy));
  }

  // 「図に載せる」チェックリスト（フェーズごと・葉だけ）
  function picker(g){
    var on = 0, total = 0, h = "";
    phases(g.proj).forEach(function(ph){
      h += '<div style="margin:8px 0 3px;color:' + C.muted + ';font-size:11px">' + esc(ph.id + " " + ph.name) + '</div>';
      ph.leaves.forEach(function(n){
        var id = String(n.id), chk = hasDeps(n);
        total++; if(chk)on++;
        h += '<label style="display:flex;gap:6px;align-items:center;padding:2px 0;color:'
          + (chk ? C.text : "#9aa2ad") + '"><input type="checkbox" class="dpick" data-id="' + esc(id) + '"'
          + (chk ? " checked" : "") + ' style="margin:0"><span>' + esc(id + " " + cut(String(n.name||""), 12))
          + '</span></label>';
      });
    });
    return '<div id="depsPick" style="position:sticky;left:0;top:0;z-index:3;flex:0 0 230px;width:230px;'
      + 'border-right:1px solid #e5e7eb;padding:8px 10px;font-size:12px;background:#fff;align-self:flex-start;'
      + 'max-height:100%;overflow:auto">'
      + '<div style="display:flex;align-items:center;margin-bottom:2px">'
      + '<span style="font-weight:600;white-space:nowrap">図に載せる作業</span>'
      + '<button type="button" id="depsPickClose" title="閉じる（Esc）" style="margin-left:auto;' + BTN + '">✕</button></div>'
      + '<div style="color:' + C.muted + ';font-size:10px;margin-bottom:4px">葉だけ・' + on + "/" + total + '</div>' + h
      + '<div style="margin-top:12px;color:' + C.muted + ';font-size:10px;line-height:1.5">'
      + 'チェック＝ <code>_deps: []</code> を足す／外す＝キーと参照を消す（依存が付いていれば確認）。</div></div>';
  }

  // ===== ヘッダと右ペインの差し替え =====
  var BTN = "font:inherit;font-size:11px;line-height:1.3;padding:2px 8px;border:1px solid #9aa2ad;"
    + "border-radius:4px;background:#fff;cursor:pointer;color:#445";
  var depsOn = false, painting = false;
  function tabBar(){ return document.getElementById("rtabs"); }
  function addTab(){                                         // 3つ目の .rtab「依存」を足す（製品は render 毎に作り直す）
    var bar = tabBar(); if(!bar)return;
    if(!bar.querySelector('[data-view="deps"]')){
      var b = document.createElement("button");
      b.className = "rtab"; b.setAttribute("data-view", "deps"); b.textContent = "依存";
      bar.appendChild(b);
    }
    [].forEach.call(bar.querySelectorAll(".rtab"), function(el){
      var isDeps = el.getAttribute("data-view") === "deps";
      if(depsOn)el.classList.toggle("on", isDeps);
      else if(isDeps)el.classList.remove("on");
    });
  }
  // 依存タブの間だけ左の情報表とフィルタバーを隠す（図は全幅・フィルタは図に効かない・brief B6）
  function setChrome(hide){
    ["left", "filterBar"].forEach(function(id){
      var el = document.getElementById(id);
      if(el)el.style.display = hide ? "none" : "";           // "" ＝製品の指定に戻す
    });
  }
  function paint(home){
    var proj = firstProject(), rh = document.getElementById("rightHead"), rb = document.getElementById("rightBody");
    if(!rh || !rb)return;
    var g = proj ? layout(graph(proj)) : null;
    window.__DEPS = g;                                       // 覗き窓（smoke.py が配置・最長経路・交差数を直接見る）
    if(g)g.zoom = zoom;
    var cnt = proj ? (function(){ var ls = leavesOf(proj.tasks, []);
      return { on:ls.filter(hasDeps).length, total:ls.length }; })() : { on:0, total:0 };
    painting = true;
    setChrome(true);
    rh.className = ""; rh.style.width = ""; rh.style.height = "";
    rh.innerHTML = '<div style="height:26px;display:flex;align-items:center;gap:8px;padding:0 8px;'
      + 'background:#eef0f3;border-bottom:2px solid #d7dbe0;font-size:11px;white-space:nowrap;'
      + 'overflow:hidden;color:' + C.muted + '">'
      + '<button type="button" id="depsPickBtn" title="図に載せる作業を選ぶ（_deps キーの有無）" style="' + BTN
      + (pickOpen ? ";background:#eef4ff;border-color:" + C.accent + ";color:" + C.accent : "") + '">'
      + '図に載せる（' + cnt.on + "/" + cnt.total + '）</button>'
      + '<b style="color:' + C.text + '">依存（構造）</b>'
      + '<details id="depsAlign" style="position:relative;margin-left:6px">'
      + '<summary style="list-style:none;' + BTN + '">整列 ▾</summary>'
      + '<div style="position:absolute;top:22px;left:0;z-index:20;background:#fff;border:1px solid #9aa2ad;'
      + 'border-radius:4px;padding:4px;display:flex;flex-direction:column;gap:3px">'
      + '<button type="button" id="depsAlignAll" style="' + BTN + '">全部（手置きを消す）</button>'
      + '<button type="button" id="depsAlignNew" style="' + BTN + '">新規だけ（空きへ）</button></div></details>'
      + '<span style="margin-left:6px">ズーム</span>'
      + [50, 75, 100].map(function(z){
          var on = Math.round(zoom * 100) === z;
          return '<button type="button" class="depsZoomBtn" data-z="' + z + '" style="' + BTN
            + (on ? ";background:" + C.accent + ";border-color:" + C.accent + ";color:#fff" : "") + '">' + z + '%</button>';
        }).join("")
      + '<span id="depsHelp" title="' + esc(LEGEND) + '" style="margin-left:6px;width:16px;height:16px;'
      + 'display:inline-flex;align-items:center;justify-content:center;border:1px solid #9aa2ad;'
      + 'border-radius:50%;cursor:help;color:#445">?</span>'
      + '<span style="margin-left:auto">モック：JSON には保存しません</span></div>';
    rb.style.width = ""; rb.style.height = "";
    rb.innerHTML = '<div id="depsWrap" style="display:flex;align-items:flex-start;min-height:100%">'
      + ((g && pickOpen) ? picker(g) : "")
      + '<div style="flex:0 0 auto">' + (g ? svgOf(g) : "計画（tasks）がありません") + "</div></div>";
    var right = document.getElementById("right");
    if(right){
      right.classList.remove("pview");
      if(home){ right.scrollLeft = 0; right.scrollTop = 0; }
    }
    painting = false;
  }
  function repaint(){ if(depsOn)paint(); }
  function rerender(){                                       // データを変えた後：製品の再描画 → 依存タブを描き直す
    if(typeof PM.render === "function")PM.render();
    setTimeout(repaint, 0);
  }
  var bar = tabBar();
  if(bar){
    new MutationObserver(function(){                         // 製品が再描画＝#rtabs が作り直される
      if(painting)return;
      setTimeout(function(){ addTab(); repaint(); }, 0);
    }).observe(bar, { childList:true });
  }

  // ===== タブの切替（製品のハンドラより先に捕まえる＝activeView も localStorage も汚さない） =====
  document.addEventListener("click", function(e){
    var b = e.target.closest ? e.target.closest(".rtab") : null;
    if(!b || !tabBar() || !tabBar().contains(b))return;
    if(b.getAttribute("data-view") === "deps"){
      e.stopPropagation(); e.preventDefault();
      if(!depsOn){ depsOn = true; selected = null; addTab(); paint(true); }
    }else if(depsOn)leaveDeps();
  }, true);
  function leaveDeps(){                                      // 時間／進捗へ戻す（左表とフィルタバーを復帰）
    depsOn = false; selected = null; addTab(); setChrome(false);
    setTimeout(function(){ if(typeof PM.render === "function")PM.render(); }, 0);
  }

  // ===== キー：Esc（パネル→ゴム線→選択）と Ctrl+Z（1段戻す） =====
  document.addEventListener("keydown", function(e){
    if(!depsOn)return;
    if(e.key === "Escape"){
      if(pickOpen){ pickOpen = false; repaint(); return; }
      if(selected){ selected = null; repaint(); return; }
      return;
    }
    if((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z")){
      var a = document.activeElement;
      if(a && a.tagName === "INPUT")return;                  // 入力欄のテキスト undo は妨げない
      e.preventDefault(); e.stopPropagation();               // 製品の折りたたみ Ctrl+Z より先に処理する
      if(restore())rerender();
    }
  }, true);

  // ===== ヘッダのボタン =====
  document.addEventListener("click", function(e){
    if(!depsOn || !e.target.closest)return;
    if(e.target.closest("#depsPickBtn")){ pickOpen = !pickOpen; repaint(); return; }
    if(e.target.closest("#depsPickClose")){ pickOpen = false; repaint(); return; }
    var z = e.target.closest(".depsZoomBtn");
    if(z){ zoom = num(z.getAttribute("data-z")) / 100; repaint(); return; }
    var g0 = window.__DEPS;
    if(e.target.closest("#depsAlignAll")){                   // 整列＝全部：手置き（_pos）を全部消して自動配置に戻す
      if(!g0)return;
      snapshot(g0);
      g0.nodes.forEach(function(n){ delete n._pos; });
      closeAlign(); rerender(); return;
    }
    if(e.target.closest("#depsAlignNew")){                   // 整列＝新規だけ：_pos の無い○を自動の空きへ置き直す
      if(!g0)return;
      snapshot(g0);
      var g1 = layout(graph(g0.proj));                        // 手置きを尊重したまま自動を計算
      g1.ids.forEach(function(id){
        if(posOf(g1.info[id].node))return;                    // 手で置いた○はそのまま
        g1.info[id].node._pos = g1.pos[id].slice();           // 自動の位置を _pos として固定（「空きへ置いた」記録）
      });
      closeAlign(); rerender(); return;
    }
  });
  function closeAlign(){ var d = document.getElementById("depsAlign"); if(d)d.open = false; }

  // ===== 図に載せる（チェックリスト）＝_deps キーの有無 =====
  document.addEventListener("click", function(e){
    if(!depsOn || !e.target.closest)return;
    var pick = e.target.closest(".dpick");
    if(!pick)return;
    var proj = firstProject(); if(!proj)return;
    var id = pick.getAttribute("data-id");
    var leaves = leavesOf(proj.tasks, []);
    var leaf = leaves.filter(function(n){ return String(n.id) === id; })[0];
    if(!leaf)return;
    if(window.__DEPS)snapshot(window.__DEPS);
    if(pick.checked)leaf._deps = [];
    else{
      var refs = leaves.filter(function(n){ return hasDeps(n) && n._deps.map(String).indexOf(id) >= 0; });
      var mine = hasDeps(leaf) ? leaf._deps.length : 0;
      if((mine || refs.length) && !confirm(id + " には依存が付いています（前工程 " + mine + " 件・後続 " + refs.length
          + " 件）。図から外して依存も消しますか")){ pick.checked = true; return; }
      refs.forEach(function(n){ n._deps = n._deps.filter(function(x){ return String(x) !== id; }); });
      delete leaf._deps; delete leaf._pos;
      if(selected === id)selected = null;
    }
    rerender();
  });

  // ===== 図の操作：○をクリック＝ゴム線／○をドラッグ＝置く／矢印の ✕＝外す =====
  var drag = null;         // { id, x0, y0, moved, c0, r0 }
  function svgEl(){ return document.getElementById("depsSvg"); }
  function toGrid(e){                                        // 画面座標 → 方眼の座標（ズームを戻す）
    var svg = svgEl(); if(!svg)return null;
    var r = svg.getBoundingClientRect();
    return { x:(e.clientX - r.left) / zoom, y:(e.clientY - r.top) / zoom };
  }
  function cellAt(pt){                                       // 方眼の座標 → 置けるマス（1マスおき＝偶数）
    var c = Math.round((pt.x - PAD - CELL/2) / CELL), r = Math.round((pt.y - PAD - CELL/2) / CELL);
    c = Math.max(0, Math.round(c / STEP) * STEP); r = Math.max(0, Math.round(r / STEP) * STEP);
    return [c, r];
  }
  document.addEventListener("mousedown", function(e){
    if(!depsOn || e.button !== 0)return;
    var g = window.__DEPS; if(!g)return;
    var node = hit(e, "g.dnode"); if(!node)return;
    e.preventDefault();                                      // ドラッグ中にテキスト選択が走らないように
    drag = { id:node.getAttribute("data-id"), x0:e.clientX, y0:e.clientY, moved:false };
  });
  document.addEventListener("mousemove", function(e){
    if(!depsOn)return;
    var g = window.__DEPS, svg = svgEl(); if(!g || !svg)return;
    if(drag){                                                // ○を押している：しきい値を超えたら「置く」
      if(!drag.moved && Math.abs(e.clientX - drag.x0) + Math.abs(e.clientY - drag.y0) < DRAG_MIN)return;
      drag.moved = true;
      var pt = toGrid(e), cell = cellAt(pt), taken = occupied(g, cell, drag.id);
      var snap = document.getElementById("depsSnap");
      if(snap){                                              // 置ける所を薄く光らせる（埋まっていたら出さない）
        snap.style.display = taken ? "none" : "";
        snap.setAttribute("x", PAD + cell[0] * CELL); snap.setAttribute("y", PAD + cell[1] * CELL);
      }
      var el = svg.querySelector('g.dnode[data-id="' + cssEsc(drag.id) + '"]');
      if(el){                                                // ドラッグ中の○だけ動かす（再描画しない＝軽い）
        var p = g.pos[drag.id];
        el.setAttribute("transform", "translate(" + (cx(cell[0]) - cx(p[0])) + "," + (cy(cell[1]) - cy(p[1])) + ")");
        el.setAttribute("opacity", taken ? 0.4 : 1);
      }
      drag.cell = taken ? null : cell;
      return;
    }
    if(selected){                                            // ゴム線：選択中の○からカーソルへ
      var line = document.getElementById("depsRubber"); if(!line)return;
      var q = g.pos[selected]; if(!q)return;
      var pt2 = toGrid(e);
      line.style.display = "";
      line.setAttribute("x1", cx(q[0])); line.setAttribute("y1", cy(q[1]));
      line.setAttribute("x2", pt2.x); line.setAttribute("y2", pt2.y);
      svg.classList.add("dlinking");
    }
  });
  document.addEventListener("mouseup", function(e){
    if(!depsOn || !drag)return;
    var g = window.__DEPS, d = drag; drag = null;
    if(!d.moved)return;                                      // 動かしていない＝クリック（下の click が結ぶ／選ぶ）
    if(!g)return;
    if(!d.cell){ repaint(); return; }                        // 置けない所で離した＝元に戻す
    snapshot(g);
    g.info[d.id].node._pos = [d.cell[0], d.cell[1]];         // 手で置いた記録（_pos は例外・整列で消せる）
    selected = null;
    rerender();
  });
  function occupied(g, cell, self){                          // そのマスに他の○（や◇）が居るか
    if(g.msCell && g.msCell[0] === cell[0] && g.msCell[1] === cell[1])return true;
    return g.ids.some(function(id){
      return id !== self && g.pos[id][0] === cell[0] && g.pos[id][1] === cell[1];
    });
  }
  function cssEsc(s){ return String(s).replace(/["\\]/g, "\\$&"); }

  document.addEventListener("click", function(e){
    if(!depsOn || !e.target.closest)return;
    var g = window.__DEPS; if(!g)return;
    if(e.target.closest("#depsPick") || e.target.closest("#rightHead"))return;   // パネル・ヘッダは別のハンドラ

    var x = hit(e, "g.dx");                                  // 矢印の ✕ ＝外す（確認なし・Ctrl+Z で戻す）
    if(x){
      var from = x.getAttribute("data-from"), to = x.getAttribute("data-to");
      snapshot(g);
      var nd = g.info[to] && g.info[to].node;
      if(nd && Array.isArray(nd._deps))nd._deps = nd._deps.filter(function(v){ return String(v) !== from; });
      selected = null; rerender(); return;
    }
    var node = hit(e, "g.dnode");
    if(node){
      var id = node.getAttribute("data-id");
      if(!selected){ selected = id; repaint(); return; }      // 1回目＝選択＋ゴム線
      if(selected === id){ selected = null; repaint(); return; }
      link(g, selected, id); return;                          // 2回目＝前→後で結ぶ
    }
    if(selected){ selected = null; repaint(); }               // 空白クリック＝ゴム線を取消
  });
  // ダブルクリック＝時間タブのその行へ（既存の gotoWbs・brief §3 の導線）
  document.addEventListener("dblclick", function(e){
    if(!depsOn || !e.target.closest)return;
    var node = hit(e, "g.dnode"); if(!node)return;
    var g = window.__DEPS; if(!g)return;
    var id = node.getAttribute("data-id");
    selected = null; depsOn = false; addTab(); setChrome(false);
    if(typeof PM.gotoWbs === "function")PM.gotoWbs(g.proj.name, id);
  });
  // A → B の依存を足す（自己参照・循環・重複は alert で拒否）
  function link(g, a, b){
    if(a === b){ alert("同じ作業には結べません。"); selected = null; repaint(); return; }
    var B = g.info[b];
    if(!B){ selected = null; repaint(); return; }
    if(B.node._deps.map(String).indexOf(a) >= 0){ alert(a + " → " + b + " は既にあります。"); selected = null; repaint(); return; }
    if(reachable(g, b, a)){ alert("循環になるので結べません（" + b + " は " + a + " の前工程から辿れます）。"); selected = null; repaint(); return; }
    snapshot(g);
    B.node._deps.push(a);
    selected = null;
    rerender();
  }
  function reachable(g, from, goal, seen){                   // from から後続を辿って goal に着くか（循環の判定）
    seen = seen || {};
    if(from === goal)return true;
    if(seen[from])return false; seen[from] = 1;
    return g.succ[from].some(function(q){ return reachable(g, q, goal, seen); });
  }

  // 起動：製品がデータを描いた後にタブを足す（読み込み前でもタブは出しておく）
  addTab();
  setTimeout(addTab, 0);
})();
