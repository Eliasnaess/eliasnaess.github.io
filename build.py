#!/usr/bin/env python3
"""Build Elias's site into docs/ (served by GitHub Pages).

Content lives in content/:
  site.yaml                         name, bio, links, base_url
  papers/<slug>.md                  frontmatter + paper text
  courses/<slug>.yaml               title, term, summary
  courses/<slug>/<seminar>/         one folder per seminar or topic:
      index.md                      frontmatter (title, date, summary, notebooklm, paper) + optional notes
      podcast.(mp3|m4a|wav)         NotebookLM Audio Overview  -> audio player
      video.(mp4|webm)              NotebookLM Video Overview  -> video player
      infographic.(png|jpg|webp)    -> image, also used as the link preview
      slides.pdf / *.pdf            -> download links
      study-guide.md, briefing.md   -> rendered under the media

Run:  python3 build.py
"""
import datetime, html, json, os, re, shutil, subprocess, math
import markdown, yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
C = os.path.join(ROOT, "content")
PREVIEW = os.environ.get("PREVIEW") == "1"
OUT = os.path.join(ROOT, "preview" if PREVIEW else "docs")
E = html.escape
MONTHS = "January February March April May June July August September October November December".split()

def read_front(path):
    s = open(path, encoding="utf-8").read()
    if s.startswith("---"):
        _, fm, body = s.split("---", 2)
        return yaml.safe_load(fm) or {}, body.strip()
    return {}, s.strip()

def nice_date(d):
    if not d: return ""
    d = d if isinstance(d, datetime.date) else datetime.date.fromisoformat(str(d))
    return f"{MONTHS[d.month-1]} {d.year}"

def iso(d): return str(d) if d else ""

def day_date(d):
    if not d: return ""
    d = d if isinstance(d, datetime.date) else datetime.date.fromisoformat(str(d))
    return f"{d.day} {MONTHS[d.month-1][:3]} {d.year}"

# ---------- markdown for papers ----------
HEAD_WORDS = r"(introduction|conclusion|conclusions|references|bibliography|works cited|abstract|discussion)"
def promote_headings(md):
    out = []
    lines = md.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if re.fullmatch(r">\s*\*\*[^*]+\*\*", s): s = s.lstrip("> ").strip()  # bold heading pandoc put in a blockquote
        prev_blank = i == 0 or not lines[i-1].strip()
        next_blank = i == len(lines)-1 or not lines[i+1].strip()
        bare = s.strip("*_ ").replace("\\.", ".")
        is_head = False
        if prev_blank and next_blank and 0 < len(bare) < 110 and not s.startswith(("|", ">", "-", "[")):
            if re.fullmatch(HEAD_WORDS + r"[:.]?", bare, re.I): is_head = True
            elif re.match(r"^\d+(\.\d+)*\.?\s+\S", bare) and not bare.endswith((".", ",", ";")): is_head = True
            elif s.startswith("**") and s.endswith("**") and not bare.endswith("."): is_head = True
        if is_head:
            level = "###" if re.match(r"^\d+\.\d+", bare) else "##"
            out.append(f"{level} {bare.rstrip(':')}")
        else:
            out.append(ln)
    return "\n".join(out)

MD_EXT = ["extra", "footnotes", "sane_lists", "smarty"]
def render_paper(md):
    md = promote_headings(md)
    h = markdown.markdown(md, extensions=MD_EXT)
    # wrap references section
    m = re.search(r"<h2[^>]*>\s*(References|Bibliography|Works Cited)\s*</h2>", h, re.I)
    if m:
        h = h[:m.start()] + '<section class="refs">' + h[m.start():] + "</section>"
    # AI-use statement styling
    h = re.sub(r"(<h2[^>]*>\s*Statement on (the )?[Uu]se of (Gen)?AI[^<]*</h2>)", r'<hr>\1', h)
    return h

def render_md(md): return markdown.markdown(md, extensions=MD_EXT)

# ---------- load ----------
site = yaml.safe_load(open(os.path.join(C, "site.yaml"), encoding="utf-8"))
PODCASTS = site.get("podcasts", True)  # false = build without audio files (small Pages deploy)
BASE = (site.get("base_url") or "").rstrip("/")

courses = {}
for f in sorted(os.listdir(os.path.join(C, "courses"))):
    if f.endswith(".yaml"):
        slug = f[:-5]
        courses[slug] = dict(slug=slug, seminars=[], papers=[], **yaml.safe_load(open(os.path.join(C, "courses", f), encoding="utf-8")))

papers = []
for f in sorted(os.listdir(os.path.join(C, "papers"))):
    if f.endswith(".md"):
        meta, body = read_front(os.path.join(C, "papers", f))
        meta["slug"] = f[:-3]; meta["body"] = body
        meta["minutes"] = max(1, round(meta.get("words", len(body.split())) / 230))
        papers.append(meta)
        if meta.get("course") in courses: courses[meta["course"]]["papers"].append(meta)
papers.sort(key=lambda p: str(p.get("date", "")), reverse=True)

AUDIO = (".mp3", ".m4a", ".wav", ".aac", ".ogg"); VIDEO = (".mp4", ".webm", ".mov"); IMG = (".png", ".jpg", ".jpeg", ".webp")

# ---------- lean media (storage step 1) ----------
# Sources are normalised in place, once, so content/ and docs/ hold identical small files
# (git stores identical files once). Originals stay archived in the vault.
AUDIO_KBPS = 48   # mono speech; ~21 MB per hour
IMG_MAX_W = 2000; IMG_Q = 86

def _probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=channels,bit_rate", "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        ch, br = r.stdout.strip().split(",")[:2]; return int(ch), int(br)
    except Exception: return None, None

def slim_media(sdir):
    for f in sorted(os.listdir(sdir)):
        src = os.path.join(sdir, f); base, ext = os.path.splitext(f); ext = ext.lower()
        if ext in AUDIO:
            ch, br = _probe(src)
            if ext == ".mp3" and ch == 1 and br and br <= (AUDIO_KBPS + 4) * 1000: continue
            tmp = os.path.join(sdir, base + ".tmp.mp3")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-map", "0:a:0", "-ac", "1",
                            "-b:a", f"{AUDIO_KBPS}k", "-map_metadata", "0", tmp], check=True)
            os.remove(src); os.replace(tmp, os.path.join(sdir, base + ".mp3"))
            print(f"  slimmed audio  {f} -> {AUDIO_KBPS} kbps mono")
        elif ext in IMG:
            im = Image.open(src)
            if ext in (".jpg", ".jpeg") and im.width <= IMG_MAX_W: continue
            if im.width > IMG_MAX_W: im = im.resize((IMG_MAX_W, round(im.height * IMG_MAX_W / im.width)), Image.LANCZOS)
            im.convert("RGB").save(os.path.join(sdir, base + ".jpg"), quality=IMG_Q, optimize=True)
            if ext != ".jpg": os.remove(src)
            print(f"  slimmed image  {f} -> {base}.jpg")
seminars = []
for cslug, c in courses.items():
    cdir = os.path.join(C, "courses", cslug)
    if not os.path.isdir(cdir): continue
    for s in sorted(os.listdir(cdir)):
        sdir = os.path.join(cdir, s)
        if not os.path.isdir(sdir): continue
        meta, notes = read_front(os.path.join(sdir, "index.md")) if os.path.exists(os.path.join(sdir, "index.md")) else ({}, "")
        slim_media(sdir)
        files = sorted(os.listdir(sdir))
        sem = dict(slug=s, course=cslug, dir=sdir, notes=notes, files=files, **meta)
        sem.setdefault("title", s.replace("-", " ").title())
        sem["audio"] = [f for f in files if f.lower().endswith(AUDIO)]
        sem["video"] = [f for f in files if f.lower().endswith(VIDEO)]
        sem["images"] = [f for f in files if f.lower().endswith(IMG)]
        sem["pdfs"] = [f for f in files if f.lower().endswith(".pdf")]
        sem["docs"] = [f for f in files if f.lower().endswith(".md") and f != "index.md"]
        if "brief.yaml" in files:  # Classroom v2: at-a-glance brief, course arc, quiz
            sem.update(yaml.safe_load(open(os.path.join(sdir, "brief.yaml"), encoding="utf-8")) or {})
        c["seminars"].append(sem); seminars.append(sem)
for c in courses.values(): c["seminars"].sort(key=lambda s: str(s.get("date", "")), reverse=True)
seminars.sort(key=lambda s: str(s.get("date", "")), reverse=True)

# ---------- output helpers ----------
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(OUT)
shutil.copytree(os.path.join(ROOT, "src"), OUT, dirs_exist_ok=True)
open(os.path.join(OUT, ".nojekyll"), "w").close()

FONT_T = os.path.join(ROOT, "tools/fonts/Newsreader-600.woff")
FONT_B = os.path.join(ROOT, "tools/fonts/Inter-Regular.otf")
FONT_S = os.path.join(ROOT, "tools/fonts/Inter-SemiBold.otf")
def og_card(path, kicker, title, sub=""):
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), "#FFFCF0"); d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 14, H], fill="#24837B")
    d.text((80, 80), kicker.upper(), font=ImageFont.truetype(FONT_S, 26), fill="#24837B")
    size = 74
    while True:
        f = ImageFont.truetype(FONT_T, size); words = title.split(); lines, cur = [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) > W - 160: lines.append(cur); cur = w
            else: cur = t
        lines.append(cur)
        if len(lines) <= 3 or size <= 50: break
        size -= 6
    y = 140
    for ln in lines: d.text((80, y), ln, font=f, fill="#100F0F"); y += int(size * 1.15)
    if sub:
        fs = ImageFont.truetype(FONT_B, 30); line = sub if d.textlength(sub, font=fs) < W - 160 else sub[:70] + "…"
        d.text((80, y + 18), line, font=fs, fill="#6F6E69")
    d.line([80, H - 110, W - 80, H - 110], fill="#DAD8CE", width=2)
    d.text((80, H - 85), site["name"], font=ImageFont.truetype(FONT_S, 30), fill="#100F0F")
    d.text((W - 80, H - 85), "Leiden University", font=ImageFont.truetype(FONT_B, 28), fill="#6F6E69", anchor="ra")
    os.makedirs(os.path.dirname(path), exist_ok=True); img.save(path, optimize=True)

def page(rel, title, desc, body, og=None, depth=0, kind="website"):
    up = "../" * depth
    url = f"{BASE}/{rel}" if BASE else ""
    og_img = f"{BASE}/{og}" if (BASE and og) else (f"{up}{og}" if og else "")
    full = f"{title} · {site['name']}" if title != site["name"] else title
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(full)}</title><meta name="description" content="{E(desc)}">
<meta property="og:type" content="{kind}"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:site_name" content="{E(site['name'])}">{f'<meta property="og:url" content="{url}">' if url else ''}
{f'<meta property="og:image" content="{og_img}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">' if og_img else ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{up}favicon.svg"><link rel="stylesheet" href="{up}style.css">
</head><body>
<header class="top"><a class="home" href="{up}index.html">{E(site['name'])}</a><nav><a href="{up}classroom/index.html">Classroom</a><a href="{up}index.html#papers">Papers</a><a href="{up}index.html#courses">Courses</a></nav></header>
<main>{body}</main>
<footer class="foot"><span>© {datetime.date.today().year} {E(site['name'])}</span>{''.join(f'<a href="{E(l["url"])}">{E(l["label"])}</a>' for l in site.get("links", []) if l.get("url"))}</footer>
<script src="{up}site.js" defer></script>
</body></html>"""
    if PREVIEW and rel == "index.html":
        doc = doc.split("<head>",1)[1]
        doc = doc.replace('<meta name="viewport" content="width=device-width,initial-scale=1">','<meta name="claude:viewport-fit-sides" content="cover">')
        doc = doc.replace("</head><body>","").replace("</body></html>","")
    p = os.path.join(OUT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(doc)

def share_btn(): return '<button class="share" data-share>Share link</button>'

STRANDS = [("legitimacy", "Legitimacy & authority"), ("norway", "Norway in the world"), ("mind", "Freedom & the mind")]
def paper_item(p, up=""):
    sub = f'<span class="sub">{E(p["subtitle"])}</span>' if p.get("subtitle") else ""
    c = courses.get(p.get("course"), {})
    return f'''<li><a href="{up}papers/{p["slug"]}/index.html"><span class="t">{E(p["title"])}</span>{sub}
<span class="meta">{E(c.get("title",""))} · {nice_date(p.get("date"))} · {p["minutes"]} min read</span></a></li>'''

def seminar_item(s, up=""):
    c = courses[s["course"]]
    bits = []
    if s.get("brief"): bits.append("Brief")
    if s["audio"]: bits.append("Podcast")
    if s["video"]: bits.append("Video")
    if s["images"]: bits.append("Infographic")
    if s.get("quiz"): bits.append("Quiz")
    if s["docs"] and not s.get("brief"): bits.append("Notes")
    return f'''<li><a href="{up}courses/{s["course"]}/{s["slug"]}/index.html"><span class="t">{E(s["title"])}</span>
<span class="meta">{E(c["title"])}{(" · " + c.get("unit","Week") + " " + str(s["week"])) if s.get("week") else ""}{(" · " + day_date(s.get("date"))) if s.get("date") else ""}{(" · " + " · ".join(bits)) if bits else ""}</span></a></li>'''

# ---------- media processing ----------
def publish_seminar_media(s, dest):
    # Sources are already lean (slim_media); copy bytes as-is so git deduplicates them.
    os.makedirs(dest, exist_ok=True)
    out = {"audio": [], "video": [], "images": [], "pdfs": []}
    for k in ("audio", "images", "video", "pdfs"):
        if k == "audio" and not PODCASTS: continue  # podcasts paused: keep the deploy small (site.yaml podcasts: false)
        for f in s[k]: shutil.copy(os.path.join(s["dir"], f), dest); out[k].append(f)
    return out

def audio_duration(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
        return f"{math.ceil(float(r.stdout.strip())/60)} min"
    except Exception: return ""


# ---------- Classroom v2 blocks ----------
def li(items): return "".join(f"<li>{E(str(x))}</li>" for x in items or [])

def glance_html(s):
    b = s.get("brief") or {}
    if not b: return ""
    concepts = "".join(f'<details class="chip"><summary>{E(k.get("term",""))}</summary><p>{E(k.get("def",""))}{(" <span class=who>— " + E(k["who"]) + "</span>") if k.get("who") else ""}</p></details>' for k in b.get("key_concepts", []))
    cases = "".join(f'<li><b>{E(c.get("name",""))}</b> <span class="who">{E(c.get("reading",""))}</span><br><span class="d">{E(c.get("detail",""))}</span></li>' for c in b.get("cases", []))
    reads = "".join(f'<tr><td class="who">{E(str(r.get("author","")))} ({E(str(r.get("year","")))})</td><td><b>{E(r.get("title",""))}</b>{((" · pp. " if str(r["pages"])[:1].isdigit() else " · ") + E(str(r["pages"]))) if r.get("pages") else ""}<br><span class="d">{E(r.get("one_line",""))}</span></td></tr>' for r in b.get("readings", []))
    arc = s.get("course_arc") or []
    arc_html = ""
    if arc:
        nowi = next((i for i, a in enumerate(arc) if a.get("now")), -1)
        dots = "".join(f'<li class="{"now" if i == nowi else ("past" if nowi >= 0 and i < nowi else "next")}" title="{E(str(a.get("topic","")))}"><span class="num">{E(str(a.get("week","")))}</span><span class="tp">{E(str(a.get("topic","")))}</span></li>' for i, a in enumerate(arc))
        arc_html = f'<div class="arc-wrap"><h3>Where this fits in the course</h3>{f"<p>{E(s["context"])}</p>" if s.get("context") else ""}<ol class="arc">{dots}</ol></div>'
    return f"""<section id="step-1" class="step">
<h2><span class="n">1</span> At a glance <span class="hint">30 seconds</span></h2>
<div class="glance">
<div class="g-card"><h3>Key questions</h3><ol>{li(b.get("key_questions"))}</ol></div>
<div class="g-card"><h3>Key concepts</h3><div class="chips">{concepts}</div><p class="hint">Tap a concept for its definition.</p></div>
<div class="g-card"><h3>What you get out of it</h3><ul>{li(b.get("takeaways"))}</ul></div>
<div class="g-card"><h3>Cases and evidence</h3><ul class="cases">{cases}</ul></div>
</div>
{f'<h3>The readings</h3><table class="reads">{reads}</table>' if reads else ""}
{arc_html}
</section>"""

def quiz_html(s):
    q = s.get("quiz") or []
    if not q: return ""
    items = []
    for i, it in enumerate(q, 1):
        if it.get("type") == "mc":
            opts = "".join(f'<button type="button" class="opt" data-ok="{1 if j == it.get("answer") else 0}">{E(str(o))}</button>' for j, o in enumerate(it.get("options", [])))
            items.append(f'<li class="qz mc"><p class="q">{E(it["q"])}</p><div class="opts">{opts}</div><p class="why" hidden>{E(it.get("why",""))}</p></li>')
        else:
            items.append(f'<li class="qz short"><p class="q">{E(it["q"])}</p><textarea rows="3" placeholder="Your answer in two or three sentences"></textarea><button type="button" class="reveal">Show model answer</button><p class="why" hidden>{E(it.get("model",""))}</p></li>')
    n_mc = sum(1 for it in q if it.get("type") == "mc")
    return f"""<section id="step-3" class="step">
<h2><span class="n">3</span> Test your understanding</h2>
<p class="hint">{n_mc} quick questions, then {len(q) - n_mc} to answer in your own words. Nothing is saved or sent.</p>
<ol class="quiz" data-total="{n_mc}">{"".join(items)}</ol>
<p class="score" hidden></p>
</section>"""

def steps_nav(s):
    if not s.get("brief"): return ""
    return """<ol class="steps-nav"><li><a href="#step-1"><b>1</b> Read the brief</a></li><li><a href="#step-2"><b>2</b> """ + ("Listen" if s.get("audio") else "Look") + """</a></li>""" +("""<li><a href="#step-3"><b>3</b> Test yourself</a></li>""" if s.get("quiz") else "") + "</ol>"

# ---------- pages ----------
# papers
for p in papers:
    c = courses.get(p.get("course"), {})
    rel = f"papers/{p['slug']}/index.html"
    og = f"og/paper-{p['slug']}.png"; og_card(os.path.join(OUT, og), c.get("title", "Paper"), p["title"], p.get("subtitle", ""))
    listen = ""
    related = [s for s in seminars if s.get("paper") == p["slug"]]
    if related:
        listen = '<aside class="listen">Also: ' + ", ".join(f'<a href="../../courses/{s["course"]}/{s["slug"]}/index.html">{E(s["title"])}</a>' for s in related) + "</aside>"
    others = [q for q in papers if q["slug"] != p["slug"]][:3]
    body = f'''<article class="paper">
<p class="kicker">{E(c.get("title",""))} · Leiden University · {nice_date(p.get("date"))}</p>
<h1>{E(p["title"])}</h1>{f'<p class="subtitle">{E(p["subtitle"])}</p>' if p.get("subtitle") else ""}
<p class="lead">{E(p.get("summary",""))}</p>
<div class="bar"><span>{p.get("words",0):,} words · {p["minutes"]} min read</span><span class="actions">{share_btn()}{"" if PREVIEW else "<button data-print>Save as PDF</button>"}</span></div>
{listen}
<div class="prose">{render_paper(p["body"])}</div>
</article>
<section class="more"><h2>More papers</h2><ul class="list">{"".join(paper_item(q, "../../") for q in others)}</ul></section>'''
    page(rel, p["title"], p.get("summary", "")[:200], body, og, depth=2, kind="article")

# seminars
for s in seminars:
    c = courses[s["course"]]
    dest_rel = f"courses/{s['course']}/{s['slug']}"
    media = publish_seminar_media(s, os.path.join(OUT, dest_rel))
    og = f"og/seminar-{s['course']}-{s['slug']}.png"
    if media["images"]:
        im = Image.open(os.path.join(OUT, dest_rel, media["images"][0])); im = im.convert("RGB")
        ratio = 1200 / 630; w, h = im.size
        if w / h > ratio: nw = int(h * ratio); im = im.crop(((w - nw)//2, 0, (w + nw)//2, h))
        else: nh = int(w / ratio); im = im.crop((0, 0, w, nh))
        os.makedirs(os.path.join(OUT, "og"), exist_ok=True); im.resize((1200, 630)).save(os.path.join(OUT, og), quality=85)
    else:
        og_card(os.path.join(OUT, og), c["title"], s["title"], "Seminar notes")
    blocks = []
    for a in media["audio"]:
        dur = audio_duration(os.path.join(OUT, dest_rel, a))
        stem = os.path.splitext(a)[0].lower()
        custom = (s.get("labels") or {}).get(stem)
        label = custom or {"deep-dive-long": "Deep-dive podcast · long version", "deep-dive-standard": "Deep-dive podcast · standard version"}.get(stem, "Deep-dive podcast" if len(media["audio"]) == 1 else stem.replace("-", " ").capitalize())
        blocks.append(f'<figure class="media audio"><figcaption>🎧 {label}{(" · " + dur) if dur else ""}</figcaption><audio controls preload="metadata" src="{a}"></audio>{"" if PREVIEW else f'<a class="dl" href="{a}" download>Download</a>'}</figure>')
    if not PODCASTS and s["audio"]:
        n_a = len(s["audio"])
        blocks.append(f'<figure class="media audio"><figcaption>🎧 {n_a} deep-dive podcast{"s" if n_a != 1 else ""} for this seminar</figcaption><p class="hint">The podcasts are moving to faster hosting and will be back here shortly.</p></figure>')
    for v in media["video"]:
        blocks.append(f'<figure class="media"><figcaption>Video overview</figcaption><video controls preload="metadata" src="{v}"></video></figure>')
    for i in media["images"]:
        n_img = len(media["images"]); idx = media["images"].index(i) + 1
        cap = os.path.splitext(i)[0].replace("-", " ").capitalize() if not i.startswith("infographic") else ("Infographic" + (f" {idx} of {n_img}" if n_img > 1 else ""))
        blocks.append(f'<figure class="media img"><a href="{i}" target="_blank" rel="noopener"><img src="{i}" alt="{E(s["title"])} — {E(cap)}" loading="lazy"></a><figcaption>{E(cap)} · tap to open full size</figcaption></figure>')
    docs = "".join(f'<section class="prose notes">{render_md(open(os.path.join(s["dir"], d), encoding="utf-8").read())}</section>' for d in s["docs"])
    pdfs = "".join(f'<li><a href="{f}">{E(os.path.splitext(f)[0].replace("-", " ").title())} (PDF)</a></li>' for f in media["pdfs"])
    extra = []
    if s.get("notebooklm"): extra.append(f'<li><a href="{E(s["notebooklm"])}">Open the NotebookLM notebook</a></li>')
    if s.get("paper"):
        pp = next((q for q in papers if q["slug"] == s["paper"]), None)
        if pp: extra.append(f'<li><a href="../../../papers/{pp["slug"]}/index.html">Read my paper: {E(pp["title"])}</a></li>')
    links = (pdfs + "".join(extra))
    listen = "".join(blocks)
    if s.get("brief"):
        step2 = "Listen and look" if (media["audio"] or s["audio"]) else "Look"
        hint2 = '<p class="hint">Two takes on the same readings: pick the length that fits your commute.</p>' if len(media["audio"]) > 1 else ""
        listen = f'<section id="step-2" class="step"><h2><span class="n">2</span> {step2}</h2>{hint2}{listen}</section>'
    body = f'''<article class="seminar">
<p class="kicker"><a href="../../../classroom/index.html">The Classroom</a> · <a href="../index.html">{E(c["title"])}</a>{(" · " + c.get("unit","Week") + " " + str(s["week"])) if s.get("week") else ""}{(" · " + day_date(s.get("date"))) if s.get("date") else ""}</p>
<h1>{E(s["title"])}</h1>{f'<p class="lead">{E(s["summary"])}</p>' if s.get("summary") else ""}
<div class="bar"><span>Seminar materials</span><span class="actions">{share_btn()}</span></div>
{steps_nav(s)}
{glance_html(s)}
{listen}
{quiz_html(s)}
{"" if s.get("brief") else (f'<div class="prose notes">{render_md(s["notes"])}</div>' if s["notes"] else "")}
{docs}
{f'<h2>Links</h2><ul class="links">{links}</ul>' if links else ""}
<p class="credit">Podcasts and infographics are generated with Google NotebookLM from the course readings; the brief and quiz are drafted with Claude from the readings and syllabus. Everything is checked and curated by me.</p>
</article>'''
    page(f"{dest_rel}/index.html", s["title"], s.get("summary") or f"Seminar materials for {c['title']}", body, og, depth=3, kind="article")

# courses
live_courses = [c for c in courses.values() if c["papers"] or c["seminars"]]
def term_key(c):
    season, year = c["term"].split()[:2]; return (int(year), 1 if season == "Fall" else 0)
live_courses.sort(key=term_key, reverse=True)
for c in live_courses:
    og = f"og/course-{c['slug']}.png"; og_card(os.path.join(OUT, og), c["term"] + " · Leiden University", c["title"], c.get("summary", ""))
    body = f'''<article class="course">
<p class="kicker">{E(c["term"])} · Leiden University</p><h1>{E(c["title"])}</h1><p class="lead">{E(c.get("summary",""))}</p>
<div class="bar"><span>{len(c["seminars"])} seminar{'s' if len(c["seminars"])!=1 else ''} · {len(c["papers"])} paper{'s' if len(c["papers"])!=1 else ''}</span><span class="actions">{share_btn()}</span></div>
{f'<h2>Seminar materials</h2><ul class="list">{"".join(seminar_item(s, "../../") for s in c["seminars"])}</ul>' if c["seminars"] else ""}
{f'<h2>My papers</h2><ul class="list">{"".join(paper_item(p, "../../") for p in c["papers"])}</ul>' if c["papers"] else ""}
</article>'''
    page(f"courses/{c['slug']}/index.html", c["title"], c.get("summary", ""), body, og, depth=2)

# classroom
by_course = [c for c in live_courses if c["seminars"]]
cl_body = '<article class="course"><p class="kicker">Leiden University · Seminar companions</p><h1>The Classroom</h1><p class="lead">One page per seminar: what the readings ask, the key concepts and cases, two podcast takes, and a short quiz to check you got it. Read, listen, test.</p>'
for c in by_course:
    cl_body += f'<h2>{E(c["title"])}</h2><ul class="list">{"".join(seminar_item(x, "../") for x in sorted(c["seminars"], key=lambda x: str(x.get("date","")), reverse=True))}</ul>'
cl_body += "</article>"
og_card(os.path.join(OUT, "og/classroom.png"), "Leiden University", "The Classroom", "Seminar briefs, podcasts and quizzes")
page("classroom/index.html", "The Classroom", "Seminar briefs, podcasts and quizzes for Leiden courses.", cl_body, "og/classroom.png", depth=1)

# home
og_card(os.path.join(OUT, "og/home.png"), "Scholarship", site["name"], site.get("tagline", ""))
strand_html = ""
for key, label in STRANDS:
    items = [p for p in papers if p.get("strand") == key]
    if items: strand_html += f'<h3>{label}</h3><ul class="list">{"".join(paper_item(p) for p in items)}</ul>'
featured = [p for p in papers if p.get("featured")]
course_html = "".join(f'''<li><a href="courses/{c["slug"]}/index.html"><span class="t">{E(c["title"])}</span><span class="meta">{E(c["term"])}{(" · " + str(len(c["papers"])) + (" papers" if len(c["papers"])!=1 else " paper")) if c["papers"] else ""}{(" · " + str(len(c["seminars"])) + (" seminars" if len(c["seminars"])!=1 else " seminar")) if c["seminars"] else ""}</span></a></li>''' for c in live_courses)
links = " · ".join(f'<a href="{E(l["url"])}">{E(l["label"])}</a>' for l in site.get("links", []) if l.get("url"))
body = f'''<section class="intro">
<h1>{E(site["name"])}</h1><p class="tagline">{E(site.get("tagline",""))}</p>
<p class="bio">{E(site.get("bio",""))}</p>{f'<p class="links">{links}</p>' if links else ""}
</section>
<blockquote class="question"><span>The question underneath my work</span>{E(site.get("question",""))}</blockquote>
{f'<section id="seminars"><h2>The Classroom <a class="more-link" href="classroom/index.html">all seminars →</a></h2><ul class="list">{"".join(seminar_item(s) for s in seminars[:6])}</ul></section>' if seminars else ""}
<section id="featured"><h2>Selected papers</h2><div class="cards">{"".join(f"""<a class="card" href="papers/{p['slug']}/index.html"><span class="k">{E(courses.get(p['course'],{}).get('title',''))}</span><span class="t">{E(p['title'])}</span><span class="s">{E(p['summary'][:150].rsplit(' ',1)[0])}…</span></a>""" for p in featured)}</div></section>
<section id="papers"><h2>All papers</h2>{strand_html}</section>
<section id="courses"><h2>Courses</h2><ul class="list">{course_html}</ul></section>'''
page("index.html", site["name"], site.get("tagline", ""), body, "og/home.png", depth=0)

# 404
page("404.html", "Not found", "Page not found", f'<article><h1>Not here</h1><p class="lead">This page has moved or never existed. <a href="{(BASE + "/") if BASE else "index.html"}">Go to the home page</a>.</p></article>')
print(f"Built {len(papers)} papers, {len(seminars)} seminar pages, {len(live_courses)} courses → docs/")
