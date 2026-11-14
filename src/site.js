document.addEventListener("click", async (e) => {
  const s = e.target.closest("[data-share]");
  if (s) {
    const data = { title: document.title, url: location.href };
    if (navigator.share) { try { await navigator.share(data); } catch (_) {} return; }
    try { await navigator.clipboard.writeText(location.href); s.textContent = "Link copied"; s.classList.add("done");
      setTimeout(() => { s.textContent = "Share link"; s.classList.remove("done"); }, 2000); } catch (_) {}
  }
  if (e.target.closest("[data-print]")) window.print();
});
// Classroom v2 quiz
document.addEventListener("click", (e) => {
  const o = e.target.closest(".opt");
  if (o) {
    const qz = o.closest(".qz"); if (qz.classList.contains("done")) return;
    qz.classList.add("done");
    qz.querySelectorAll(".opt").forEach((b) => { if (b.dataset.ok === "1") b.classList.add("right"); });
    if (o.dataset.ok !== "1") o.classList.add("wrong"); else qz.dataset.correct = "1";
    qz.querySelector(".why").hidden = false;
    const quiz = qz.closest(".quiz"), done = quiz.querySelectorAll(".mc.done").length, total = +quiz.dataset.total;
    if (done === total) { const sc = quiz.parentElement.querySelector(".score");
      const n = quiz.querySelectorAll(".mc[data-correct]").length;
      sc.textContent = `${n} / ${total} correct${n === total ? " — ready for the seminar." : ". Revisit the brief above for the ones you missed."}`; sc.hidden = false; }
  }
  const r = e.target.closest(".reveal");
  if (r) { r.nextElementSibling.hidden = false; r.remove(); }
});
document.querySelectorAll(".arc .now").forEach((n) => { const a = n.parentElement; a.scrollLeft = n.offsetLeft - a.clientWidth / 2 + n.clientWidth / 2; });
// Classroom quiz-prep edition: tabs, flashcards, practice, mock quiz, progress
(() => {
  const el = document.getElementById("prep-data"); if (!el) return;
  const D = JSON.parse(el.textContent), KEY = D.key;
  const store = { get() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (_) { return {}; } },
    set(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (_) {} } };
  let S = Object.assign({ ans: {}, cards: {} }, store.get());
  const save = () => store.set(S);
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

  // tabs (hash-addressable)
  const show = (k, push) => { $$(".ptab").forEach((t) => (t.hidden = t.id !== "tab-" + k));
    $$(".ptabs [data-tab]").forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === k ? "true" : "false"));
    if (push) history.replaceState(null, "", "#" + k); if (k === "plan") progress(); };
  $$(".ptabs [data-tab]").forEach((b) => b.addEventListener("click", () => { show(b.dataset.tab, true); $(".ptabs").scrollIntoView({ block: "start", behavior: "smooth" }); }));
  $$("[data-go]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); show(a.dataset.go, true); $(".ptabs").scrollIntoView({ block: "start" }); }));
  const h = location.hash.slice(1); if ($("#tab-" + h)) show(h); 

  // countdown
  const cd = $("[data-countdown]");
  if (cd && D.quizdate) { const t = new Date(D.quizdate + "T11:15:00"), d = Math.ceil((t - new Date()) / 864e5);
    cd.textContent = d > 1 ? d + " days" : d === 1 ? "Tomorrow" : d === 0 ? "Today — good luck" : "Done"; }

  // progress
  function progress() { $$(".progress .pw").forEach((row) => { const w = +row.dataset.w, qs = D.mcq.filter((q) => q.w === w);
      const done = qs.filter((q) => q.id in S.ans), right = done.filter((q) => S.ans[q.id] === q.a).length;
      const pct = done.length ? Math.round((100 * right) / done.length) : 0;
      row.querySelector("i").style.width = (done.length / qs.length) * 100 + "%";
      row.querySelector("i").className = pct >= 80 ? "good" : pct >= 60 ? "ok" : "low";
      row.querySelector(".pn").textContent = done.length ? `${done.length}/${qs.length} answered · ${pct}% right` : "not started"; }); }
  progress();

  // flashcards
  let cw = 0, onlyAgain = false, deck = [], ci = 0;
  const fc = $(".fc"), cardId = (c) => c.w + ":" + c.f;
  function buildDeck(sh) { deck = D.cards.filter((c) => (!cw || c.w === cw) && (!onlyAgain || S.cards[cardId(c)] === "again"));
    if (sh) deck = shuffle(deck); ci = 0; drawCard(); }
  function drawCard() { fc.classList.remove("flip"); const n = $(".fc-n");
    if (!deck.length) { $(".fc-f").innerHTML = "<p>No cards here — nothing marked 'again'. 🎉</p>"; $(".fc-b").innerHTML = ""; n.textContent = ""; return; }
    const c = deck[ci]; $(".fc-f").innerHTML = `<span class="tag">Week ${c.w} · ${esc(c.src)}</span><p class="t">${esc(c.f)}</p><span class="hint">tap to flip</span>`;
    $(".fc-b").innerHTML = `<span class="tag">${esc(c.src)}</span><p>${esc(c.b)}</p>`;
    const known = D.cards.filter((x) => S.cards[cardId(x)] === "got").length;
    n.textContent = `Card ${ci + 1} of ${deck.length} · ${known} of ${D.cards.length} marked 'got it'`; }
  const nextCard = (mark) => { if (!deck.length) return; if (mark) { S.cards[cardId(deck[ci])] = mark; save(); }
    if (onlyAgain && mark === "got") { deck.splice(ci, 1); if (ci >= deck.length) ci = 0; } else ci = (ci + 1) % deck.length; drawCard(); };
  if (fc) { fc.addEventListener("click", () => fc.classList.toggle("flip"));
    $$("[data-fc]").forEach((b) => b.addEventListener("click", () => b.dataset.fc === "flip" ? fc.classList.toggle("flip") : nextCard(b.dataset.fc)));
    document.addEventListener("keydown", (e) => { if ($("#tab-cards").hidden || /TEXTAREA|INPUT/.test(e.target.tagName)) return;
      if (e.key === " ") { e.preventDefault(); fc.classList.toggle("flip"); } else if (e.key === "ArrowLeft") nextCard("again"); else if (e.key === "ArrowRight") nextCard("got"); });
    $$('[data-for="cards"] button').forEach((b) => b.addEventListener("click", () => {
      if ("w" in b.dataset) { cw = +b.dataset.w; $$('[data-for="cards"] [data-w]').forEach((x) => x.setAttribute("aria-pressed", x === b)); buildDeck(true); }
      else if ("again" in b.dataset) { onlyAgain = !onlyAgain; b.setAttribute("aria-pressed", onlyAgain); buildDeck(true); }
      else buildDeck(true); }));
    buildDeck(true); }

  // question renderer (practice + mock)
  const qHTML = (q, i, cls) => `<li class="${cls}" data-id="${q.id}"><p class="q"><span class="tag">Week ${q.w} · ${esc(q.src)}</span>${esc(q.q)}</p><div class="opts">${q.o
    .map((o, j) => `<button type="button" class="popt" data-j="${j}">${String.fromCharCode(65 + j)}. ${esc(o)}</button>`).join("")}</div><p class="why" hidden></p></li>`;
  const reveal = (li, q, j) => { li.classList.add("done"); $$(".popt", li).forEach((b) => { const k = +b.dataset.j; if (k === q.a) b.classList.add("right"); else if (k === j) b.classList.add("wrong"); });
    const w = $(".why", li); w.innerHTML = `<b>${j === q.a ? "Right." : (j < 0 ? "Unanswered" : "Not quite") + " — the answer is " + String.fromCharCode(65 + q.a) + "."}</b> ${esc(q.why)}`; w.hidden = false; };
  const byId = Object.fromEntries(D.mcq.map((q) => [q.id, q]));

  // practice
  let pw = 1;
  function drawPractice() { const qs = D.mcq.filter((q) => !pw || q.w === pw); const ol = $(".pq-list"); ol.innerHTML = qs.map((q, i) => qHTML(q, i, "pq")).join("");
    $$(".pq", ol).forEach((li) => { const q = byId[li.dataset.id]; if (q.id in S.ans) reveal(li, q, S.ans[q.id]); }); pscore(); }
  function pscore() { const qs = D.mcq.filter((q) => !pw || q.w === pw), done = qs.filter((q) => q.id in S.ans), r = done.filter((q) => S.ans[q.id] === q.a).length;
    $(".pscore").textContent = done.length ? `${r} of ${done.length} right so far (${qs.length} in this set)` + (done.length === qs.length ? (r / qs.length >= 0.8 ? " — solid. Try the mock quiz." : " — reset and go again, or revisit the Map.") : "") : ""; }
  $(".pq-list")?.addEventListener("click", (e) => { const b = e.target.closest(".popt"); if (!b) return; const li = b.closest(".pq"); if (li.classList.contains("done")) return;
    const q = byId[li.dataset.id], j = +b.dataset.j; S.ans[q.id] = j; save(); reveal(li, q, j); pscore(); });
  $$('[data-for="practice"] button').forEach((b) => b.addEventListener("click", () => { pw = +b.dataset.w; $$('[data-for="practice"] button').forEach((x) => x.setAttribute("aria-pressed", x === b)); drawPractice(); }));
  $("[data-reset-practice]")?.addEventListener("click", () => { D.mcq.filter((q) => !pw || q.w === pw).forEach((q) => delete S.ans[q.id]); save(); drawPractice(); });
  if ($(".pq-list")) drawPractice();

  // mock quiz
  let mock = [], picks = {}, tick = null, end = 0;
  $("[data-mock-start]")?.addEventListener("click", () => { mock = shuffle(D.mcq).slice(0, 30); picks = {};
    $(".mq-list").innerHTML = mock.map((q, i) => qHTML(q, i, "mq")).join(""); $(".mock-start").hidden = true; $(".mock-result").hidden = true; $(".mock-run").hidden = false;
    end = Date.now() + 30 * 60e3; clearInterval(tick); tick = setInterval(timer, 1000); timer(); });
  function timer() { const left = Math.max(0, end - Date.now()), m = Math.floor(left / 60e3), s = Math.floor((left % 60e3) / 1e3);
    $("[data-timer]").textContent = `${m}:${String(s).padStart(2, "0")} left · ${Object.keys(picks).length}/30 answered`; if (!left) submit(); }
  $(".mq-list")?.addEventListener("click", (e) => { const b = e.target.closest(".popt"); if (!b) return; const li = b.closest(".mq");
    $$(".popt", li).forEach((x) => x.classList.toggle("sel", x === b)); picks[li.dataset.id] = +b.dataset.j; timer(); });
  $("[data-mock-submit]")?.addEventListener("click", () => submit());
  function submit() { clearInterval(tick); const right = mock.filter((q) => picks[q.id] === q.a).length;
    $$(".mq").forEach((li) => { const q = byId[li.dataset.id]; reveal(li, q, li.dataset.id in picks ? picks[li.dataset.id] : -1); });
    const byW = [1, 2, 3].map((w) => { const qs = mock.filter((q) => q.w === w); return `Week ${w}: ${qs.filter((q) => picks[q.id] === q.a).length}/${qs.length}`; }).join(" · ");
    S.mocks = (S.mocks || []).concat([{ t: Date.now(), r: right }]); save();
    const best = Math.max(...S.mocks.map((m) => m.r));
    const r = $(".mock-result"); r.hidden = false;
    r.innerHTML = `<p class="big">${right} / 30 <span>(${Math.round((right / 30) * 100)}%)</span></p><p>${byW}</p><p class="hint">Best so far: ${best}/30 over ${S.mocks.length} attempt${S.mocks.length > 1 ? "s" : ""}. Scroll down: every question now shows the right answer and why.</p><button type="button" class="pri" data-mock-again>New mock quiz</button>`;
    $("[data-mock-submit]").hidden = true; $("[data-timer]").textContent = "Finished";
    r.querySelector("[data-mock-again]").addEventListener("click", () => { $("[data-mock-submit]").hidden = false; $("[data-mock-start] ").click(); });
    r.scrollIntoView({ behavior: "smooth", block: "start" }); }

  // short answers
  document.addEventListener("click", (e) => { const b = e.target.closest(".reveal2"); if (b) { b.nextElementSibling.hidden = false; b.remove(); } });
})();
