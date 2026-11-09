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
