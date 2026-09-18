// 依存タブ（構造の軸）の「動くモック」。製品 wbs_viewer.html には手を入れず、
// 生成物 deps_mock.html の末尾にこのファイルを丸ごと差し込んで動かす（scripts/build_deps_mock.py）。
//
// 設計メモ: docs/design/brief-deps.md（§3 画面・§4 操作・§5 計算が正）
// モックなので JSON へは保存しない。メモリ上のデータ（window.__PM.data()）を書き換えて
// 再描画するだけ＝「保存済」表示も出さない・queueSave も呼ばない。
(function(){
  "use strict";
  var PM = window.__PM;
  if(!PM || typeof PM.data !== "function")return;         // 橋が無い＝製品が変わった。何もしない（壊さない）

  // ===== 見た目の定数（色は製品の CSS 変数と同じ値のリテラル。SVG属性は var() を解決しないため） =====
  var ROW = 64;        // ○1つぶんの縦の間隔
  var TOP = 40;        // 図の上端（「第N段」のラベルぶん）
  var COLW = 300;      // 段（rank）1つぶんの横幅
  var DAYPX = 10;      // 線の目盛り1日ぶんの px
  var MAXD = 22;       // 線に出す最大日数（超えは「…」）
  var R = 13;          // ○の半径
  var X0 = 30;         // 図の左余白
  var C = {
    node: "#4a6a9e",   // ○の輪郭・番号（= --plan-edge 予定の枠線と同じ）
    text: "#1f2430",   // 名前（= --text）
    muted: "#6b7280",  // 「第N段」等の添え字（= --muted）
    line: "#c5cad3",   // 線と目盛り（= --line 表の区切り）
    arrow: "#9aa2ad",  // 矢印（= --btn-border。線より一段濃い＝別の意味だと分かる）
    accent: "#2563eb", // 選択（= --accent）
    red: "#e11d48",    // 余裕0・違反（= 既存の遅延赤）
    ms: "#cc79a7"      // マイルストーンの既定色（= 製品と同じ Okabe-Ito モーブ）
  };

  // ===== 小道具（製品の esc/日付ヘルパは閉じた中にあるので自前で持つ） =====
  var DAY_MS = 86400000;
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }
  function isDate(s){ return typeof s === "string" && /^(19|20)\d{2}-\d{2}-\d{2}$/.test(s); }
  function ms(s){ return Date.UTC(+s.slice(0,4), +s.slice(5,7)-1, +s.slice(8,10)); }   // 日付→通し時刻
  function iso(t){ return new Date(t).toISOString().slice(0,10); }                     // 通し時刻→日付
  function addD(s,n){ return iso(ms(s) + n*DAY_MS); }                                  // s の n 日後
  function diffD(a,b){ return Math.round((ms(b) - ms(a)) / DAY_MS); }                  // a→b の日数
  function md(s){ return isDate(s) ? (+s.slice(5,7)) + "/" + (+s.slice(8,10)) : "—"; } // 9/18 表記
  function dow(s){ return "日月火水木金土".charAt(new Date(ms(s)).getUTCDay()); }
  function isMon(s){ return new Date(ms(s)).getUTCDay() === 1; }
  function cut(s,n){ s = String(s||""); return s.length > n ? s.slice(0,n) + "…" : s; }  // 名前を n 字で切る
  function today(){ return typeof PM.today === "function" ? PM.today() : iso(Date.now()); }
  // クリック地点の下にある要素を上から順に見て、最初に見つかった sel を返す（重なりの解決）
  function hit(e, sel){
    var stack = document.elementsFromPoint ? document.elementsFromPoint(e.clientX, e.clientY) : [];
    for(var i = 0; i < stack.length; i++){
      var m = stack[i].closest ? stack[i].closest(sel) : null;
      if(m)return m;
    }
    return e.target.closest ? e.target.closest(sel) : null;    // 合成イベント等で座標が無い時の保険
  }

  // ===== データの取り出し =====
  function firstProject(){                                  // モックは先頭の（計画を持つ）案件だけを見る
    var d = PM.data();
    var ps = (d && Array.isArray(d.projects)) ? d.projects : [];
    for(var i=0;i<ps.length;i++)if(ps[i] && Array.isArray(ps[i].tasks) && ps[i].tasks.length)return ps[i];
    return null;
  }
  function leavesOf(tasks, out){                            // 葉（children を持たない節）を並び順に集める
    (tasks||[]).forEach(function(n){
      if(!n || typeof n !== "object")return;
      if(Array.isArray(n.children) && n.children.length)leavesOf(n.children, out);
      else out.push(n);
    });
    return out;
  }
  function phases(proj){                                    // チェックリスト用：第1階層ごとの葉のまとまり
    return (proj.tasks||[]).filter(function(n){ return n && typeof n === "object"; })
      .map(function(n){ return { id:String(n.id), name:String(n.name||""), leaves:leavesOf([n],[]) }; });
  }
  function hasDeps(n){ return !!n && Array.isArray(n._deps); }            // ○がある＝_deps キーがある
  function planOf(n){ var p = n.plan||{}; return { s:isDate(p.start)?p.start:null, e:isDate(p.end)?p.end:null }; }

  // ===== CPM（暦日・brief §5） =====
  // 返すのは描画に必要な派生値だけ。JSON には書かない。
  function compute(proj){
    var all = leavesOf(proj.tasks, []);
    var nodes = all.filter(hasDeps).filter(function(n){ var p = planOf(n); return p.s && p.e; });
    var byId = {};
    nodes.forEach(function(n){ byId[String(n.id)] = n; });

    // 前工程（参照先が無い／自己参照は console.warn して無視）
    var pred = {}, succ = {};
    nodes.forEach(function(n){ pred[String(n.id)] = []; succ[String(n.id)] = []; });
    nodes.forEach(function(n){
      var id = String(n.id);
      n._deps.forEach(function(raw){
        var p = String(raw);
        if(p === id){ console.warn("[deps] 自己参照を無視: " + id); return; }
        if(!byId[p]){ console.warn("[deps] 参照先が無いので無視: " + id + " → " + p); return; }
        if(pred[id].indexOf(p) < 0)pred[id].push(p);
      });
    });
    // 循環は「あとから来た辺」を落とす（描けないより、警告して描く）
    function reaches(from, goal, seen){
      if(from === goal)return true;
      if(seen[from])return false; seen[from] = 1;
      return pred[from].some(function(p){ return reaches(p, goal, seen); });
    }
    nodes.forEach(function(n){
      var id = String(n.id);
      pred[id] = pred[id].filter(function(p){
        if(reaches(p, id, {})){ console.warn("[deps] 循環を無視: " + p + " → " + id); return false; }
        return true;
      });
    });
    Object.keys(pred).forEach(function(id){ pred[id].forEach(function(p){ succ[p].push(id); }); });

    // 段（rank）＝トポロジカル順の深さ
    var rank = {};
    function rk(id, seen){
      if(rank[id] != null)return rank[id];
      if(seen[id])return 0;                                  // 念のための番人（上で循環は落としている）
      seen[id] = 1;
      rank[id] = pred[id].length ? Math.max.apply(null, pred[id].map(function(p){ return rk(p, seen); })) + 1 : 0;
      return rank[id];
    }
    nodes.forEach(function(n){ rk(String(n.id), {}); });

    // 線の右端の根拠＝いちばん遅いマイルストーン（無ければ全葉の最遅終了）
    var msList = (Array.isArray(proj.milestones) ? proj.milestones : [])
      .filter(function(m){ return m && isDate(m.date); });
    var lastMs = null;
    msList.forEach(function(m){ if(!lastMs || m.date > lastMs.date)lastMs = m; });
    var horizon = lastMs ? lastMs.date : null;                 // マイルストーンがあればそれ
    if(!horizon)all.forEach(function(n){                       // 無ければ全葉の最遅終了
      var p = planOf(n); if(p.e && (!horizon || p.e > horizon))horizon = p.e; });
    if(!horizon)horizon = today();

    var TD = today();
    function effEnd(n){                                      // 「実際にはいつ終わったか（終わりそうか）」
      var p = planOf(n), a = n.actual || {};
      var ae = isDate(a.end) ? a.end : null, as = isDate(a.start) ? a.start : null;
      if(ae)return ae > p.e ? ae : p.e;                       // 実績終了が予定を超えている＝実遅れ
      if(as && TD > p.e)return TD;                            // 進行中で予定終了を過ぎている＝いまも遅れ中
      return p.e;
    }

    var info = {};
    nodes.forEach(function(n){
      var id = String(n.id), p = planOf(n);
      var dur = Math.max(1, diffD(p.s, p.e) + 1);
      // 前向き：最早開始 ES＝max(前工程の予定終了)+1（前工程なし＝いまの予定開始）
      // 前工程があるときは「いまの開始」を混ぜない（混ぜると ES が現状より前にならず、違反が出なくなる）
      var es = null, esReal = null;
      pred[id].forEach(function(q){
        var qs = addD(planOf(byId[q]).e, 1); if(es === null || qs > es)es = qs;
        var qr = addD(effEnd(byId[q]), 1);   if(esReal === null || qr > esReal)esReal = qr;
      });
      if(es === null){ es = p.s; esReal = p.s; }               // 前工程なし＝いまの予定開始が最早
      // 後ろ向き：最遅終了 LF＝min(後続のいまの開始)−1（後続なし＝マイルストーンの前日）
      var lf = null;
      succ[id].forEach(function(q){ var t = addD(planOf(byId[q]).s, -1); if(lf === null || t < lf)lf = t; });
      if(lf === null)lf = addD(horizon, -1);
      var ls = addD(lf, -(dur - 1));
      var slack = Math.max(0, diffD(es, ls));                 // 余裕（フロート）。負＝動かせない＝0 と同じ扱い
      info[id] = {
        node:n, id:id, name:String(n.name||""), start:p.s, end:p.e, dur:dur,
        es:es, esReal:esReal, ls:ls, slack:slack,
        winStart:(esReal > es ? esReal : es),                 // 実遅れがあれば線の左端が右へ動く（brief §4）
        viol:(p.s < es),                                      // 違反＝いまの開始が最早開始より前
        late:(p.s < esReal && p.s >= es),                     // 前工程の実遅れで線からはみ出した
        lateEnd:(effEnd(n) > p.e),                            // この葉自身が実績で予定終了を超えている（波及元の印）
        pred:pred[id], succ:succ[id], rank:rank[id]
      };
    });

    // 並び順：段（rank）→ 開始日 → 番号。これが上から下への行順になる
    var order = nodes.map(function(n){ return String(n.id); }).sort(function(a,b){
      return (info[a].rank - info[b].rank) || (info[a].start < info[b].start ? -1 : info[a].start > info[b].start ? 1 : 0)
        || (a < b ? -1 : 1);
    });
    var maxRank = 0;
    order.forEach(function(id){ if(info[id].rank > maxRank)maxRank = info[id].rank; });
    return { proj:proj, all:all, info:info, order:order, maxRank:maxRank, ms:lastMs, horizon:horizon };
  }
  function downstream(g, id, acc){                           // その葉と、そこから後ろにつながる全部（ずらす対象）
    acc = acc || {}; if(acc[id])return acc; acc[id] = 1;
    g.info[id].succ.forEach(function(q){ downstream(g, q, acc); });
    return acc;
  }

  // ===== SVG の部品 =====
  function curve(x1,y1,x2,y2,col,w,op,attr){                 // 依存の矢印＝3次ベジェ＋三角形の頭
    var c = Math.max(30, (x2 - x1) / 2);
    return '<g ' + (attr||"") + ' opacity="' + op + '">'
      + '<path d="M' + x1 + ',' + y1 + ' C' + (x1+c) + ',' + y1 + ' ' + (x2-c) + ',' + y2 + ' ' + x2 + ',' + y2 + '"'
      + ' fill="none" stroke="' + col + '" stroke-width="' + w + '"/>'
      + '<path d="M' + x1 + ',' + y1 + ' C' + (x1+c) + ',' + y1 + ' ' + (x2-c) + ',' + y2 + ' ' + x2 + ',' + y2 + '"'
      + ' fill="none" stroke="transparent" stroke-width="10" pointer-events="stroke"/>'   // 掴み代（見えない太い線）
      + '<polygon points="' + x2 + ',' + y2 + ' ' + (x2-8) + ',' + (y2-4) + ' ' + (x2-8) + ',' + (y2+4) + '" fill="' + col + '"/>'
      + '</g>';
  }
  function tip(g, d){                                        // ○のツールチップ（brief §3「数字は常時出さずホバーで」）
    var L = [];
    L.push(d.id + " " + d.name + " " + d.dur + "日");
    L.push("開始 " + md(d.start) + " → 終了 " + md(d.end));
    if(d.viol){
      L.push("違反：最早開始 " + md(d.es) + " より " + diffD(d.start, d.es) + "日早い開始になっている（影響あり）");
    }else if(d.late){
      // N＝「遅れた前工程から後ろにつながる葉」の数（前工程そのものは含めない）＝押し直す必要がある本数
      var hitIds = {};
      d.pred.forEach(function(p){
        if(!g.info[p].lateEnd)return;                          // 実際に遅れている前工程だけ
        var down = downstream(g, p); delete down[p];
        Object.keys(down).forEach(function(x){ hitIds[x] = 1; });
      });
      L.push("前工程の実績遅れで最早開始が " + md(d.esReal) + " へ動いた（線からはみ出している）");
      L.push("後続 " + Object.keys(hitIds).length + " 件をずらす提案（モックでは表示のみ）");
    }else if(d.slack <= 0){
      L.push("余裕（フロート）0日：1日も動かせない＝クリティカルパス");
    }else{
      L.push("余裕（フロート）" + d.slack + "日：" + md(d.winStart) + "〜" + md(d.ls) + " の間で開始できる");
    }
    L.push("前工程：" + (d.pred.length ? d.pred.map(function(p){ return p + " " + cut(g.info[p].name, 10); }).join("・") : "なし"));
    L.push("後続：" + (d.succ.length ? d.succ.map(function(q){ return q + " " + cut(g.info[q].name, 10); }).join("・") : "なし"));
    return L.join("\n");
  }

  // ===== 画面の状態（localStorage は汚さない＝製品の記憶に触らない） =====
  var selected = null;       // 選択中の○（番号）。null＝未選択
  var pickOpen = false;      // 「○を選ぶ」パネルが開いているか（既定＝畳む＝図だけ）
  var layout = "packed";     // 縦の並び。"packed"＝段の中で上から詰める（既定）／"rows"＝1葉1行
  var PACK_ROW = 44;         // packed のときの行高

  // 凡例（ヘッダ右の「?」のツールチップ＝既存の title の作法。パネルからは外した）
  var LEGEND = "○＝作業（中＝番号・下＝名前）\n"
    + "線＝開始日として選べる範囲（＝余裕）。目盛りは1日・月曜が長い\n"
    + "赤い輪＝余裕0（クリティカルパス）\n"
    + "赤い○＝影響あり（違反・前工程の実遅れで線からはみ出した）\n"
    + "◇＝マイルストーン（線の右端の根拠）\n"
    + "○をクリック→別の○をクリック＝依存を結ぶ／矢印をクリック＝外す\n"
    + "選択中に線の目盛りをクリック＝その日を開始に（Esc で解除）";

  // 依存タブの間だけ左の情報表を隠す（右ペインを画面幅いっぱいに使う）。
  // 製品は render のたびに #left を "block" に戻すので、塗り直しのたびに掛け直す。
  function setLeftHidden(hide){
    var l = document.getElementById("left");
    if(l)l.style.display = hide ? "none" : "";               // "" ＝製品の指定に戻す
  }
  function pickCount(proj){                                  // ボタンに出す「○を置いた葉 / 葉ぜんぶ」
    var ls = leavesOf(proj.tasks, []);
    return { on:ls.filter(hasDeps).length, total:ls.length };
  }

  // ===== 図（SVG）を組む =====
  function figure(g){
    var n = g.order.length;
    if(!n)return '<div style="padding:24px;color:' + C.muted + '">'
      + '○を置く作業がありません。ヘッダ左の「○を選ぶ」から選んでください（チェック＝<code>_deps: []</code> を足す）。</div>';
    // 縦の並びは2通り（brief の未決。どちらが読みやすいかを触って決めるための切替）
    //   packed = 段の中で上から詰める（1段に N 個・行高 44px）＝縦が短く、段＝列として読める
    //   rows   = 1葉1行（段→開始日の順）＝v1 の階段状
    var packed = (g.layout !== "rows");
    var seen = {};                                           // 段ごとに何個置いたか（packed の縦位置）
    var pos = {};                                            // 番号 → ○と線の座標
    g.order.forEach(function(id, i){
      var d = g.info[id];
      // 線に出す日数＝いま選べる範囲（winStart〜LS）。実遅れで左端が右へ動いた分だけ短くなる
      // ＝目盛りをクリックできる範囲と線の見た目が必ず一致する（余裕 slack は ES 基準の別の値）
      var span = Math.max(0, diffD(d.winStart, d.ls));
      var shown = Math.min(span, MAXD);
      var L = X0 + d.rank * COLW + 20;                        // 線の左端＝その段の基準線
      var k = seen[d.rank] = (seen[d.rank] == null ? 0 : seen[d.rank] + 1);
      var y = packed ? (TOP + k * PACK_ROW + 22) : (TOP + i * ROW + 22);
      var off = Math.max(-6, Math.min(diffD(d.winStart, d.start), shown));  // ○の位置＝いまの開始日（左にはみ出しは6日で頭打ち）
      pos[id] = { x:L + off * DAYPX, y:y, L:L, shown:shown, span:span };
    });
    // 図の高さ＝いちばん背の高い段（packed）／葉の数（rows）
    var rowsUsed = packed ? (Math.max.apply(null, g.order.map(function(id){ return seen[g.info[id].rank]; })) + 1) : n;
    var step = packed ? PACK_ROW : ROW;
    var mx = X0 + (g.maxRank + 1) * COLW + 40;               // ◇の x（いちばん右の段のさらに右）
    var my = TOP + step * rowsUsed / 2;
    var body = "";

    for(var k = 0; k <= g.maxRank; k++)                       // 段の見出し
      body += '<text x="' + (X0 + k*COLW + 20) + '" y="16" font-size="10" fill="' + C.muted + '">第' + (k+1) + '段</text>';
    body += '<text x="' + mx + '" y="16" font-size="10" fill="' + C.muted + '">◇ マイルストーン</text>';

    // 依存の矢印（既定は薄く・選択した○の関係だけ濃く）
    g.order.forEach(function(id){
      g.info[id].pred.forEach(function(p){
        var a = pos[p], b = pos[id];
        var rel = selected && (selected === id || selected === p);
        var op = selected ? (rel ? 1 : 0.15) : 0.45;
        body += curve(a.x + R + 1, a.y, b.x - R - 1, b.y, C.arrow, rel ? 1.8 : 1.4, op,
          'class="dedge" data-from="' + esc(p) + '" data-to="' + esc(id) + '" style="cursor:pointer"');
      });
    });
    // ◇と、後続の無い○からの薄い線（線の右端の根拠）
    g.order.forEach(function(id){
      if(g.info[id].succ.length)return;
      var a = pos[id];
      // 選択中は◇への線も一緒に沈める（依存の矢印だけ濃く見せるため）
      body += curve(a.x + R + 1, a.y, mx - 13, my, C.ms, 1.1, selected ? 0.12 : 0.35, "");
    });
    var msCol = (g.ms && typeof g.ms.color === "string" && /^#[0-9a-fA-F]{3,8}$/.test(g.ms.color)) ? g.ms.color : C.ms;
    var msLbl = g.ms ? (String(g.ms.label||"") + "　" + md(g.ms.date)) : "（マイルストーン無し）";
    body += '<polygon points="' + mx + ',' + (my-12) + ' ' + (mx+12) + ',' + my + ' ' + mx + ',' + (my+12) + ' '
      + (mx-12) + ',' + my + '" fill="#fff" stroke="' + msCol + '" stroke-width="2"><title>'
      + esc(msLbl) + '</title></polygon>'
      + '<text x="' + (mx+18) + '" y="' + (my+4) + '" font-size="11" fill="' + C.text + '">' + esc(msLbl) + '</text>';

    // 線（開始日として選べる範囲）＋目盛り＋○＋名前
    g.order.forEach(function(id){
      var d = g.info[id], q = pos[id];
      if(q.span > 0){
        var w = q.shown * DAYPX;
        body += '<line x1="' + q.L + '" y1="' + q.y + '" x2="' + (q.L + w) + '" y2="' + q.y
          + '" stroke="' + C.line + '" stroke-width="1.2"/>';
        for(var i = 0; i <= q.shown; i++){
          var ds = addD(d.winStart, i), h = isMon(ds) ? 5 : 2.5;   // 月曜だけ長い目盛り
          body += '<line x1="' + (q.L + i*DAYPX) + '" y1="' + (q.y - h) + '" x2="' + (q.L + i*DAYPX)
            + '" y2="' + (q.y + h) + '" stroke="' + C.line + '"/>'
            + '<rect class="dtick" data-id="' + esc(id) + '" data-day="' + ds + '" x="' + (q.L + i*DAYPX - 5)
            + '" y="' + (q.y - 9) + '" width="10" height="18" fill="#fff" fill-opacity="0" pointer-events="all"'
            + ' style="cursor:pointer"><title>' + md(ds) + "（" + dow(ds) + "）"
            + (selected === id ? "　クリック＝この日を開始に" : "") + '</title></rect>';
        }
        if(q.span > MAXD)
          body += '<text x="' + (q.L + w + 5) + '" y="' + (q.y + 4) + '" font-size="11" fill="' + C.muted + '">…</text>';
      }
      var red = d.viol || d.late;                                // 赤で塗る＝影響あり
      var ring = "";
      if(d.slack <= 0)                                           // 余裕0＝赤い輪（クリティカルパス）
        ring = '<circle cx="' + q.x + '" cy="' + q.y + '" r="' + (R+3) + '" fill="none" stroke="' + C.red + '" stroke-width="1.5"/>';
      if(selected === id)                                        // 選択＝破線の輪（アクセント青）
        ring += '<circle cx="' + q.x + '" cy="' + q.y + '" r="' + (R+6) + '" fill="none" stroke="' + C.accent
          + '" stroke-width="1.4" stroke-dasharray="4 3"/>';
      // data-* は「なぜ赤いか」を DOM に残す印（ホバーせずに読める・smoke.py が数える）
      body += '<g class="dnode" data-id="' + esc(id) + '"' + (d.slack <= 0 ? ' data-crit="1"' : "")
        + (d.viol ? ' data-viol="1"' : "") + (d.late ? ' data-late="1"' : "")
        + ' style="cursor:pointer"><title>' + esc(tip(g, d)) + '</title>'
        + ring
        + '<circle cx="' + q.x + '" cy="' + q.y + '" r="' + R + '" fill="' + (red ? C.red : "#fff") + '" stroke="'
        + (red ? C.red : C.node) + '" stroke-width="1.6"/>'
        + '<text x="' + q.x + '" y="' + (q.y+3) + '" font-size="8" text-anchor="middle" pointer-events="none" fill="'
        + (red ? "#fff" : C.node) + '">' + esc(id) + '</text>'
        + '<text x="' + q.x + '" y="' + (q.y + R + 13) + '" font-size="10.5" text-anchor="middle" fill="' + C.text + '">'
        + esc(cut(d.name, 9)) + '</text></g>';
    });

    var W = mx + 220, H = TOP + step * rowsUsed + 20;
    return '<svg id="depsSvg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H
      + '" style="display:block;background:#fff">' + body + '</svg>';
  }

  // ===== ○を置く作業のチェックリスト（左端・幅230px） =====
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
    // パネルは図の左に重ねず、左端に貼り付く1枚（横スクロールでも残る・縦は上に貼り付く）
    return '<div id="depsPick" style="position:sticky;left:0;top:0;z-index:3;flex:0 0 230px;width:230px;'
      + 'border-right:1px solid #e5e7eb;padding:8px 10px;font-size:12px;background:#fff;align-self:flex-start;'
      + 'max-height:100%;overflow:auto">'
      + '<div style="display:flex;align-items:center;margin-bottom:2px">'
      + '<span style="font-weight:600;white-space:nowrap">○を置く作業を選ぶ</span>'
      + '<button type="button" id="depsPickClose" title="閉じる（Esc）" style="margin-left:auto;font:inherit;'
      + 'font-size:11px;line-height:1;padding:2px 5px;border:1px solid #9aa2ad;border-radius:4px;'
      + 'background:#fff;cursor:pointer;color:#445">✕</button></div>'
      + '<div style="color:' + C.muted + ';font-size:10px;margin-bottom:4px">葉だけ・' + on + "/" + total + '</div>' + h
      + '<div style="margin-top:12px;color:' + C.muted + ';font-size:10px;line-height:1.5">'
      + 'チェック＝ <code>_deps: []</code> を足す／外す＝キーと参照を消す（依存が付いていれば確認）。</div></div>';
  }

  // ===== タブと描画の差し込み =====
  var depsOn = false, painting = false;
  function tabBar(){ return document.getElementById("rtabs"); }
  function addTab(){                                          // 3つ目の .rtab「依存」を足す（製品は render 毎に rtabs を作り直す）
    var bar = tabBar(); if(!bar)return;
    if(!bar.querySelector('[data-view="deps"]')){
      var b = document.createElement("button");
      b.className = "rtab"; b.setAttribute("data-view", "deps"); b.textContent = "依存";
      bar.appendChild(b);
    }
    // 選択の塗りは自前で付け替える（製品は activeView しか知らない）
    [].forEach.call(bar.querySelectorAll(".rtab"), function(el){
      var isDeps = el.getAttribute("data-view") === "deps";
      if(depsOn)el.classList.toggle("on", isDeps);
      else if(isDeps)el.classList.remove("on");
    });
  }
  var BTN = "font:inherit;font-size:11px;line-height:1.3;padding:2px 8px;border:1px solid #9aa2ad;"
    + "border-radius:4px;background:#fff;cursor:pointer;color:#445";   // 製品の操作ボタンと同じトーン
  function paint(home){                                       // 右ペインを依存タブの図に差し替える（home=true でスクロールも先頭へ）
    var proj = firstProject(), rh = document.getElementById("rightHead"), rb = document.getElementById("rightBody");
    if(!rh || !rb)return;
    // window.__DEPS.layout に外から代入された値を拾う（覗き窓＝切替の口も兼ねる）
    var prev = window.__DEPS;
    if(prev && (prev.layout === "rows" || prev.layout === "packed"))layout = prev.layout;
    var g = proj ? compute(proj) : null;
    if(g)g.layout = layout;
    window.__DEPS = g;                                        // 計算結果の覗き窓（smoke.py が CPM の値を直接見る）
    var cnt = proj ? pickCount(proj) : { on:0, total:0 };
    painting = true;
    setLeftHidden(true);                                      // 左の情報表を隠して右ペインを画面幅いっぱいに（案A）
    rh.className = ""; rh.style.width = ""; rh.style.height = "";
    rh.innerHTML = '<div style="height:26px;display:flex;align-items:center;gap:8px;padding:0 8px;'
      + 'background:#eef0f3;border-bottom:2px solid #d7dbe0;font-size:11px;white-space:nowrap;'
      + 'overflow:hidden;color:' + C.muted + '">'
      // 図の左上＝ヘッダ左端に「○を選ぶ」。押すと幅230pxのパネルが開く（既定は畳む）
      + '<button type="button" id="depsPickBtn" title="○を置く作業を選ぶ（_deps キーの有無）" style="' + BTN
      + (pickOpen ? ";background:#eef4ff;border-color:" + C.accent + ";color:" + C.accent : "") + '">'
      + '○を選ぶ（' + cnt.on + "/" + cnt.total + '）</button>'
      + '<b style="color:' + C.text + '">依存（構造）</b>'
      + '<button type="button" id="depsLayoutBtn" title="縦の並びを変える（詰める＝段の中で上から／行ごと＝1葉1行）"'
      + ' style="margin-left:8px;' + BTN + '">並び：' + (layout === "packed" ? "詰める" : "行ごと") + '</button>'
      + '<span id="depsHelp" title="' + esc(LEGEND) + '" style="margin-left:6px;width:16px;height:16px;'
      + 'display:inline-flex;align-items:center;justify-content:center;border:1px solid #9aa2ad;'
      + 'border-radius:50%;cursor:help;color:#445">?</span>'
      + '<span style="margin-left:auto">モック：JSON には保存しません</span></div>';
    rb.style.width = ""; rb.style.height = "";
    rb.innerHTML = '<div id="depsWrap" style="display:flex;align-items:flex-start;min-height:100%">'
      + ((g && pickOpen) ? picker(g) : "")
      + '<div style="flex:0 0 auto">' + (g ? figure(g) : "計画（tasks）がありません") + "</div></div>";
    var right = document.getElementById("right");
    if(right){
      right.classList.remove("pview");                        // 進捗ビューの横スクロール止めを外す（図は横に長い）
      if(home){                                               // タブに入った時だけ先頭へ（選択や編集のたびに戻すと図を見失う）
        right.scrollLeft = 0;                                 // 製品が本日へ寄せた横スクロールを戻す
        right.scrollTop = 0;                                  // 図は左表の行と対応しない＝先頭から見せる
      }
    }
    painting = false;
  }
  function repaint(){ if(depsOn)paint(); }
  function rerender(){                                        // データを変えた後：製品の再描画 → 依存タブを描き直す
    if(typeof PM.render === "function")PM.render();
    setTimeout(repaint, 0);                                   // 製品の render は rightBody を書き直すので、その後ろで塗る
  }

  // 製品が再描画すると #rtabs が作り直される＝そこを見て、タブを足し直し・依存タブなら塗り直す
  var bar = tabBar();
  if(bar){
    new MutationObserver(function(){
      if(painting)return;                                     // 自分の書き換えで呼ばれた分は無視（自己ループ防止）
      setTimeout(function(){ addTab(); repaint(); }, 0);       // 製品の render が rightHead/Body を書き終えた後ろで
    }).observe(bar, { childList:true });
  }

  // ===== 操作 =====
  // タブの切替。製品のハンドラより先に捕まえる（activeView も localStorage も汚さない）
  document.addEventListener("click", function(e){
    var b = e.target.closest ? e.target.closest(".rtab") : null;
    if(!b || !tabBar() || !tabBar().contains(b))return;
    if(b.getAttribute("data-view") === "deps"){
      e.stopPropagation(); e.preventDefault();
      if(!depsOn){ depsOn = true; selected = null; addTab(); paint(true); }
    }else if(depsOn){
      depsOn = false; selected = null; addTab();
      setLeftHidden(false);                                   // 左の情報表を元の幅・表示に戻す
      setTimeout(function(){ if(typeof PM.render === "function")PM.render(); }, 0);   // 製品のガントへ戻す
    }
  }, true);

  // Esc＝まずパネルを閉じ、開いていなければ選択解除
  document.addEventListener("keydown", function(e){
    if(e.key !== "Escape" || !depsOn)return;
    if(pickOpen){ pickOpen = false; repaint(); return; }
    if(selected){ selected = null; repaint(); }
  });

  // ヘッダのボタン（○を選ぶ／並びの切替）。パネルの ✕ でも閉じる
  document.addEventListener("click", function(e){
    if(!depsOn || !e.target.closest)return;
    if(e.target.closest("#depsPickBtn")){ pickOpen = !pickOpen; repaint(); return; }
    if(e.target.closest("#depsPickClose")){ pickOpen = false; repaint(); return; }
    if(e.target.closest("#depsLayoutBtn")){
      layout = (layout === "packed" ? "rows" : "packed");
      if(window.__DEPS)window.__DEPS.layout = layout;         // 覗き窓も合わせる
      repaint(); return;
    }
  });

  document.addEventListener("click", function(e){
    if(!depsOn || !e.target.closest)return;
    var proj = firstProject(); if(!proj)return;

    // (1) ○を置く作業を選ぶ＝_deps キーの有無
    var pick = e.target.closest(".dpick");
    if(pick){
      var id = pick.getAttribute("data-id");
      var leaf = leavesOf(proj.tasks, []).filter(function(n){ return String(n.id) === id; })[0];
      if(!leaf)return;
      if(pick.checked)leaf._deps = [];
      else{
        var refs = leavesOf(proj.tasks, []).filter(function(n){
          return hasDeps(n) && n._deps.map(String).indexOf(id) >= 0; });
        var mine = hasDeps(leaf) ? leaf._deps.length : 0;
        if((mine || refs.length) && !confirm(id + " には依存が付いています（前工程 " + mine + " 件・後続 " + refs.length
            + " 件）。○を外して依存も消しますか")){ pick.checked = true; return; }
        refs.forEach(function(n){ n._deps = n._deps.filter(function(x){ return String(x) !== id; }); });
        delete leaf._deps;
        if(selected === id)selected = null;
      }
      rerender(); return;
    }

    // (2) ○／目盛り／矢印は重なるので、クリック地点の「下にある要素」を上から順に見て拾う。
    //     目盛りの当たり判定（透明な小さな箱）が矢印の曲線を覆うため、e.target だけでは矢印を押せない。
    var node = hit(e, "g.dnode");                              // ○＝いちばん強い（選択・結ぶ）
    var tick = hit(e, "rect.dtick");                           // 線の目盛り＝選択中の○のものだけ効く
    var edge = hit(e, "g.dedge");                              // 矢印＝いちばん弱い（下にあっても拾う）

    // (3) ○をクリック＝選択／2つ目で依存を結ぶ
    if(node){
      var nid = node.getAttribute("data-id");
      if(!selected || selected === nid){ selected = (selected === nid ? null : nid); repaint(); return; }
      link(compute(proj), selected, nid); return;
    }
    // (4) 線の目盛りをクリック＝選択中の○をその日へ（期間は維持・線の外は不可）
    if(tick && selected && tick.getAttribute("data-id") === selected){
      moveStart(compute(proj), selected, tick.getAttribute("data-day")); return;
    }
    // (5) 矢印をクリック＝依存を外す
    if(edge){
      var from = edge.getAttribute("data-from"), to = edge.getAttribute("data-to");
      if(!confirm("依存を外しますか：" + from + " → " + to))return;
      var g0 = compute(proj), nd = g0.info[to] && g0.info[to].node;
      if(nd && Array.isArray(nd._deps))nd._deps = nd._deps.filter(function(x){ return String(x) !== from; });
      rerender(); return;
    }
  });

  // A → B の依存を足す（循環・自己参照は拒否／違反になるなら B と後続をずらすか聞く）
  function link(g, a, b){
    var A = g.info[a], B = g.info[b];
    if(!A || !B)return;
    if(a === b){ alert("同じ作業には結べません。"); return; }
    if(B.node._deps.map(String).indexOf(a) >= 0){ alert(a + " → " + b + " は既にあります。"); return; }
    if(downstream(g, b)[a]){ alert("循環になるので結べません（" + b + " は " + a + " の後続です）。"); return; }
    var need = addD(A.end, 1);                                 // B が始められる最も早い日
    if(B.start < need){
      var shift = diffD(B.start, need);
      if(!confirm(b + " は " + md(B.start) + " 開始で、" + a + " の終了（" + md(A.end) + "）より前です。\n"
          + b + " と後続を " + shift + "日 後ろへずらしますか（キャンセル＝結ばない）"))return;
      var ids = Object.keys(downstream(g, b));
      ids.forEach(function(id){ shiftPlan(g.info[id].node, shift, "#" + a + " との依存で後ろ倒し"); });
    }
    B.node._deps.push(a);
    selected = null;
    rerender();
  }

  // ○を動かす＝予定を新しい開始日へ。理由を受けて _planLog に1件追記（モックなので保存はしない）
  function moveStart(g, id, day){
    var d = g.info[id];
    if(!d || !isDate(day))return;
    if(day < d.winStart || day > d.ls){ alert("線の外（" + md(d.winStart) + "〜" + md(d.ls) + "）には出せません。"); return; }
    if(day === d.start){ selected = null; repaint(); return; }
    var reason = prompt("開始を " + md(d.start) + " → " + md(day) + " に動かします。理由（任意）", "");
    if(reason === null)return;                                 // キャンセル＝何もしない
    shiftPlan(d.node, diffD(d.start, day), reason || "依存タブで開始日を変更");
    selected = null;
    rerender();
  }

  // 予定を n 日ずらして _planLog に1件追記（append-only・by は "mock"）
  function shiftPlan(n, days, reason){
    if(!days)return;
    var p = planOf(n);
    if(!p.s || !p.e)return;
    var from = { start:p.s, end:p.e }, to = { start:addD(p.s, days), end:addD(p.e, days) };
    n.plan.start = to.start; n.plan.end = to.end;
    if(!Array.isArray(n._planLog))n._planLog = [];
    n._planLog.push({ at:new Date().toISOString(), from:from, to:to, by:"mock",
      reason:reason + "（" + (days > 0 ? "+" : "") + days + "日）" });
  }

  // 起動：製品がデータを描いた後にタブを足す（読み込み前でもタブは出しておく）
  addTab();
  setTimeout(addTab, 0);
})();
