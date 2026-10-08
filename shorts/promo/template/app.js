/* 시간 t(초)만 주면 그 시점 화면이 결정되는 순수 렌더러.
   CSS transition/animation 을 쓰지 않으므로 프레임 캡처가 항상 같은 결과를 준다. */
(function () {
  const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
  const easeOut = (p) => 1 - Math.pow(1 - p, 3);
  const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const lerp = (a, b, p) => a + (b - a) * p;

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const rich = (s) => esc(s).replace(/\|\|/g, "<br>").replace(/\[([^\]]+)\]/g, "<em>$1</em>");
  const MASCOT = '<svg class="mascot" viewBox="0 0 120 120"><use href="#mascot"/></svg>';
  const AVATAR = '<svg viewBox="0 0 120 120"><use href="#mascot"/></svg>';
  const CURSOR = '<div class="cursor"><svg viewBox="0 0 24 24"><path d="M5 2l14.5 9.2-6.6 1.3 3.4 6.4-2.9 1.6-3.4-6.4L5 18.6z"/></svg></div>';

  const CENTERED = { cover: 1, outro: 1, stat: 1 };
  const STAGGER = { chat: 0.58, ui: 0.30, stat: 0.18 };
  const CLICK0 = 1.5, CLICK_GAP = 0.68, REACH = 0.46;  // 커서가 토글을 누르는 시각

  let SC = [], TOTAL = 0, root = null, prog = null, blobs = [];

  function visualHtml(sc) {
    if (sc.kind === "ui") {
      return '<div class="rows">' + sc.items.map((it) =>
        '<div class="card row"><div class="av">' + AVATAR + "</div>" +
        '<div class="tt"><b>' + esc(it.title) + "</b><span>" + esc(it.sub) + "</span></div>" +
        '<div class="toggle off"><i></i><span>' + esc(it.state || "켜짐") + "</span></div></div>").join("") +
        "</div>" + CURSOR;
    }
    if (sc.kind === "chat") {
      return '<div class="card chat"><div class="bar"><i></i><i></i><i></i><b>' +
        esc(sc.eyebrow || "대화") + '</b></div><div class="msgs">' +
        sc.items.map((m) => '<div class="msg ' + (m.from === "me" ? "me" : "them") + '">' + esc(m.text) + "</div>").join("") +
        "</div></div>";
    }
    return MASCOT;
  }

  function buildScene(sc) {
    const el = document.createElement("div");
    el.className = "scene " + (CENTERED[sc.kind] ? "center" : "split");
    const head = (sc.eyebrow ? '<div class="eyebrow">' + esc(sc.eyebrow) + "</div>" : "") +
      (sc.title ? "<h1>" + rich(sc.title) + "</h1>" : "") +
      (sc.body ? '<div class="body">' + esc(sc.body) + "</div>" : "");

    if (sc.kind === "stat") {
      el.innerHTML = head + '<div class="stats">' + sc.items.map((s) =>
        '<div class="stat"><div class="v">' + esc(s.value) + (s.unit ? "<u>" + esc(s.unit) + "</u>" : "") +
        '</div><div class="l">' + esc(s.label) + "</div></div>").join("") + "</div>";
    } else if (CENTERED[sc.kind]) {
      el.innerHTML = MASCOT + head;
    } else {
      el.innerHTML = '<div class="col-text">' + head + '</div><div class="col-visual">' + visualHtml(sc) + "</div>";
    }

    const anims = [];
    const push = (node, delay, dy, s0, idle) => {
      if (node) anims.push({ el: node, delay: delay, dur: 0.62, dy: dy, s0: s0 || 1, idle: !!idle });
    };
    push(el.querySelector(".mascot"), 0.0, 26, 0.92, true);
    push(el.querySelector(".eyebrow"), 0.10, 16);
    push(el.querySelector("h1"), 0.20, 26);
    push(el.querySelector(".body"), 0.34, 20);
    const chat = el.querySelector(".chat");
    if (chat) push(chat, 0.34, 24, 0.985);
    const step = STAGGER[sc.kind] || 0.16;
    const items = el.querySelectorAll(".rows .row, .msgs .msg, .stats .stat");
    items.forEach((node, i) => push(node, 0.46 + i * step, 22, 0.97));

    const out = { el: el, anims: anims, on: null, kind: sc.kind };
    if (sc.kind === "ui") {
      out.cursor = {
        el: el.querySelector(".cursor"),
        rows: [].slice.call(el.querySelectorAll(".rows .row")),
        wantsOn: sc.items.map((it) => !/^(꺼|off|해제)/i.test(it.state || "")),
      };
    }
    return out;
  }

  function build(spec) {
    root = document.getElementById("scenes");
    prog = document.querySelector("#progress i");
    blobs = [].slice.call(document.querySelectorAll(".blob"));
    root.innerHTML = "";
    const rs = document.documentElement.style;
    rs.setProperty("--accent", spec.accent || "#1F7A45");
    rs.setProperty("--vw", (spec.width || 1920) + "px");
    rs.setProperty("--vh", (spec.height || 1080) + "px");
    SC = [];
    let t = 0;
    for (const raw of spec.scenes) {
      const s = buildScene(raw);
      s.start = raw.start != null ? raw.start : t;
      s.dur = raw.dur;
      t = s.start + s.dur;
      root.appendChild(s.el);
      SC.push(s);
    }
    TOTAL = spec.total || t;
    seek(0);
    return { total: TOTAL, scenes: SC.length };
  }

  /* UI 장면: 커서가 토글을 하나씩 눌러 켜는 연출 */
  function measureCursor(s) {
    const c = s.cursor;
    if (!c || !c.el || c.pts) return;
    // 커서는 .col-visual 안의 absolute 요소이므로, 좌표 기준도 그 상자여야 한다
    const base = (c.el.offsetParent || s.el).getBoundingClientRect();
    c.pts = c.rows.map((row) => {
      const r = row.querySelector(".toggle i").getBoundingClientRect();
      return { x: r.left + r.width / 2 - base.left, y: r.top + r.height / 2 - base.top };
    });
    if (!c.pts.length) { c.pts = null; c.el = null; return; }
    c.home = { x: c.pts[0].x + 150, y: c.pts[c.pts.length - 1].y + 190 };
  }

  function driveCursor(s, lt) {
    const c = s.cursor;
    if (!c || !c.el || !c.pts) return;
    const n = c.pts.length;
    const clickAt = (i) => CLICK0 + i * CLICK_GAP;
    let pos = c.home, press = 0;
    for (let i = 0; i < n; i++) {
      const ct = clickAt(i);
      const from = i === 0 ? c.home : c.pts[i - 1];
      if (lt >= ct - REACH) pos = { x: lerp(from.x, c.pts[i].x, easeInOut(clamp01((lt - (ct - REACH)) / REACH))),
                                    y: lerp(from.y, c.pts[i].y, easeInOut(clamp01((lt - (ct - REACH)) / REACH))) };
      if (lt >= ct && lt < ct + 0.16) press = Math.sin(((lt - ct) / 0.16) * Math.PI);
      const tog = c.rows[i].querySelector(".toggle");
      const on = c.wantsOn[i] && lt >= ct;
      if (tog.classList.contains("off") === on) tog.classList.toggle("off", !on);
    }
    const appear = clamp01((lt - (CLICK0 - REACH - 0.35)) / 0.3);
    const leave = clamp01((clickAt(n - 1) + 1.0 - lt) / 0.4);
    c.el.style.opacity = (easeOut(appear) * easeOut(leave)).toFixed(3);
    c.el.style.transform = "translate(" + pos.x.toFixed(1) + "px," + pos.y.toFixed(1) + "px) scale(" +
      (1 - 0.16 * press).toFixed(3) + ")";
  }

  function seek(t) {
    for (let i = 0; i < blobs.length; i++) {
      const k = i + 1;
      blobs[i].style.transform = "translate(" + (Math.sin(t * 0.13 * k + k) * 38).toFixed(2) + "px," +
        (Math.cos(t * 0.11 * k + k * 2) * 30).toFixed(2) + "px) scale(" +
        (1 + Math.sin(t * 0.09 * k) * 0.05).toFixed(4) + ")";
    }
    for (const s of SC) {
      const lt = t - s.start;
      const on = lt >= 0 && lt < s.dur;
      if (s.on !== on) {
        s.el.style.display = on ? "flex" : "none";
        s.on = on;
        if (on) measureCursor(s);
      }
      if (!on) continue;
      const fi = easeOut(clamp01(lt / 0.45));
      const fo = easeInOut(clamp01((s.dur - lt) / 0.38));
      s.el.style.opacity = (fi * fo).toFixed(4);
      // 들어오고 나가는 움직임 + 머무는 동안의 아주 느린 떠오름(화면이 멎어 보이지 않게)
      s.el.style.transform = "translateY(" + ((1 - fi) * 20 - (1 - fo) * 16 - lt * 1.15).toFixed(2) + "px)";
      for (const a of s.anims) {
        const e = easeOut(clamp01((lt - a.delay) / a.dur));
        const bob = a.idle ? Math.sin(lt * 1.45) * 5.5 : 0;
        const tilt = a.idle ? Math.sin(lt * 0.95) * 1.3 : 0;
        a.el.style.opacity = e.toFixed(4);
        a.el.style.transform = "translateY(" + ((1 - e) * a.dy + bob).toFixed(2) + "px) scale(" +
          (a.s0 + (1 - a.s0) * e).toFixed(4) + ")" + (tilt ? " rotate(" + tilt.toFixed(2) + "deg)" : "");
      }
      driveCursor(s, lt);
    }
    if (prog) prog.style.width = (100 * clamp01(TOTAL ? t / TOTAL : 0)).toFixed(3) + "%";
  }

  window.build = build;
  window.seek = seek;
  window.promoReady = true;
})();
