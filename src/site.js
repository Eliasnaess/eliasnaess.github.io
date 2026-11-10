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
