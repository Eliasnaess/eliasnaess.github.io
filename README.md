# Elias Andreas Næss — scholarship site

Static site, built with `python3 build.py` into `docs/` and served by GitHub Pages (Settings → Pages → Deploy from branch → `main` / `docs`).

## Add things
| What | Where |
|---|---|
| A paper | `content/papers/<slug>.md` — frontmatter: title, subtitle, course, date, strand (legitimacy · norway · mind), featured, summary |
| A course | `content/courses/<slug>.yaml` — title, term, summary |
| Seminar materials (NotebookLM) | `content/courses/<course>/<seminar-slug>/` with `index.md` (title, date, summary, optional `notebooklm:` link and `paper:` slug) plus any of `podcast.m4a/.mp3/.wav`, `video.mp4`, `infographic.png`, `*.pdf`, `study-guide.md` |

Audio is converted to mono 48 kbps MP3 and infographics to ≤2000 px JPG automatically, in place in `content/` (originals stay in the vault); the first infographic becomes the WhatsApp/LinkedIn link preview. Courses appear once they have a paper or a seminar.

## Settings
`content/site.yaml` — name, bio, links, and `base_url` (needed for link previews).

## Rules
- Only Elias's own work and his own NotebookLM outputs. No course readings.
- Student numbers are stripped from papers on import.
