#!/usr/bin/env python3
"""Generate self-contained, UCLA-branded HTML summary reports for TLC
workshop series from Qualtrics post-survey CSV exports.

Two reports are produced (one per series):
  - Wellbeing_Series_Report.html
  - Preparing-to-Teach_Series_Report.html

Each report opens with an executive summary (status donut + overall
sentiment), then a clickable "at a glance" grid, then per-workshop detail.
"""
import csv
import html
import math
import os
import re
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# UCLA brand palette
# ---------------------------------------------------------------------------
UCLA_BLUE = "#2774AE"
UCLA_DARKEST_BLUE = "#003B5C"
UCLA_DARKER_BLUE = "#005587"
UCLA_LIGHT_BLUE = "#8BB8E8"
UCLA_LIGHTEST_BLUE = "#DAEBFE"
UCLA_GOLD = "#FFD100"
UCLA_DARKER_GOLD = "#FFC72C"
UCLA_DARKEST_GOLD = "#FFB81C"
GRAY = "#8A8B8C"

# Diverging scale used for ALL Likert questions: gold (low) -> gray -> blue (high)
DIVERGING = ["#E89C00", "#FFC72C", "#FFE08A", "#E5E5E0", UCLA_LIGHT_BLUE, UCLA_BLUE, UCLA_DARKEST_BLUE]

# Three-way sentiment colors (consistent with the diverging ends)
SENT_POS = UCLA_BLUE
SENT_NEU = "#D9DCE1"
SENT_NEG = UCLA_DARKER_GOLD

# Status colors (one coherent system, used for box accents + badges)
STATUS = {
    "data":         dict(label="Complete",       accent=UCLA_BLUE,   bg="#e7f0f8", fg=UCLA_DARKER_BLUE),
    "missing":      dict(label="No data file",   accent=UCLA_GOLD,   bg="#fff6d6", fg="#8a6d00"),
    "nopostsurvey": dict(label="No post-survey", accent="#F0C419",   bg="#fdf3cf", fg="#8a6d00"),
    "cancelled":    dict(label="Cancelled",      accent=GRAY,        bg="#eceef0", fg="#52525b"),
    "noinfo":       dict(label="Info not found", accent="#C7C9C7",   bg="#f1f3f4", fg="#6b7280"),
}

# ---------------------------------------------------------------------------
# Workshop catalogue (chronological within each series).
# ---------------------------------------------------------------------------
WORKSHOPS = [
    # ---------------- Wellbeing ----------------
    dict(series="Wellbeing", title="Trauma-Informed and Care-Centered Pedagogies",
         modality="In-person", date="Jan 22, 2026", rsvp=11,
         file="W26 Trauma Informed/W26_2026-01-22_Trauma-Informed-Pedagogies_in-person_post-survey.csv"),
    dict(series="Wellbeing", title="Trauma-Informed and Care-Centered Pedagogies",
         modality="Online", date="Feb 11, 2026", rsvp=14,
         file="W26 Trauma Informed/W26_2026-02-11_Trauma-Informed-Pedagogies_online_post-survey.csv"),
    dict(series="Wellbeing", title="Nurturing Meaningful Collaboration for Instructor/TA Teams",
         modality="In-person", date="Mar 5, 2026", rsvp=27,
         file="W26 Nurturing meaningful/W26_2026-03-05_Nurturing-Meaningful-Collaboration_in-person_post-survey.csv"),
    dict(series="Wellbeing", title="Fostering Wellbeing through Mindful Play",
         modality="In-person", date="Apr 24, 2026", rsvp=None,
         file="Sp26 Mindful Play/Sp26_2026-04-24_Mindful-Play_in-person_post-survey.csv"),

    # ---------------- Preparing to Teach ----------------
    dict(series="Preparing to Teach", title="Developing an AI Course Policy",
         modality="In-person", date="Jan 13, 2026", rsvp=10, status="missing",
         note="Post-survey data file not found (table shows 1 response)."),
    dict(series="Preparing to Teach", title="Developing an AI Course Policy",
         modality="Online", date="Jan 21, 2026", rsvp=13,
         file="W26 Developing AI/W26_2026-01-21_Developing-AI-Course-Policy_online_post-survey.csv"),
    dict(series="Preparing to Teach", title="Aligning Learning Objectives with Lesson Planning",
         modality="In-person", date="Feb 3, 2026", rsvp=None, status="cancelled",
         note="Workshop cancelled \u2014 no post-survey expected."),
    dict(series="Preparing to Teach", title="Aligning Learning Objectives with Lesson Planning",
         modality="Online", date="Feb 9, 2026", rsvp=5,
         file="W26 Aligning Learning/W26_2026-02-09_Aligning-Learning-Objectives_online_post-survey.csv"),
    dict(series="Preparing to Teach", title="Giving Feedback",
         modality="In-person", date="Apr 21, 2026", rsvp=None, status="cancelled",
         note="Workshop cancelled \u2014 no post-survey expected."),
    dict(series="Preparing to Teach", title="Dialoguing with your Instructional Team about AI",
         modality="In-person", date="Apr 30, 2026", rsvp=4, status="missing",
         note="Post-survey data file not found (table shows 1 response)."),
    dict(series="Preparing to Teach", title="Nurturing Engaged and Ethical Learners with Critical AI Literacy",
         modality="In-person", date="May 4, 2026", rsvp=27, status="missing",
         note="Post-survey data file not found (table shows 6 responses)."),
    dict(series="Preparing to Teach", title="Dialoguing with your Instructional Team about AI",
         modality="Online", date="May 11, 2026", rsvp=7,
         file="Sp26 Dialogue with/Sp26_2026-05-11_Dialoguing-about-AI_online_post-survey.csv"),
    dict(series="Preparing to Teach", title="Bring Your Own Syllabus",
         modality="In-person", date="May 21, 2026", rsvp=21, status="nopostsurvey",
         note="21 RSVPs but 0 post-survey responses and no export file \u2014 confirm whether a survey was distributed."),
    dict(series="Preparing to Teach", title="Giving Feedback",
         modality="Online", date="May 22, 2026", rsvp=11,
         file="Sp26 Giving Feedback/Sp26_2026-05-22_Giving-Feedback_online_post-survey.csv"),
    dict(series="Preparing to Teach", title="Bring Your Own Syllabus",
         modality="In-person", date="\u2014", rsvp=None, status="noinfo",
         note="No date, RSVP, or post-survey information located (Winter 2026)."),
]

# ---------------------------------------------------------------------------
# Ordinal scales (low -> high). Used for ordering and sentiment.
# ---------------------------------------------------------------------------
SCALES = [
    ["Strongly disagree", "Disagree", "Somewhat disagree", "Neither agree nor disagree",
     "Somewhat agree", "Agree", "Strongly agree"],
    ["Not at all confident", "Not confident", "Slightly confident", "Somewhat confident",
     "Moderately confident", "Very confident", "Extremely confident"],
    ["Not at all likely", "Not likely", "Slightly likely", "Somewhat likely",
     "Moderately likely", "Very likely", "Extremely likely"],
    ["Not at all useful", "Not useful", "Slightly useful", "Somewhat useful",
     "Moderately useful", "Very useful", "Extremely useful"],
    ["Never", "Rarely", "Sometimes", "Often", "Always"],
    ["Poor", "Fair", "Good", "Very good", "Excellent"],
]


def slug(w):
    base = f'{w["title"]}-{w["modality"]}-{w["date"]}'
    return "ws-" + re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


def status_of(w, parsed):
    return "data" if (w.get("file") and parsed) else w.get("status", "missing")


def detect_scale(values):
    best, best_hits = None, 0
    vset = set(values)
    for scale in SCALES:
        hits = len(vset & set(scale))
        if hits > best_hits:
            best, best_hits = scale, hits
    return best if best_hits >= 1 else None


def color_for(rank, n):
    if n <= 1:
        return UCLA_BLUE
    return DIVERGING[round(rank / (n - 1) * (len(DIVERGING) - 1))]


def classify(rank, n):
    """pos / neu / neg relative to the middle of the scale."""
    mid = (n - 1) / 2
    return "pos" if rank > mid else "neg" if rank < mid else "neu"


def parse_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if len(rows) < 3:
        return None
    keys, labels, import_ids, data = rows[0], rows[1], rows[2], rows[3:]

    q_start = 17
    questions = []
    for i in range(q_start, len(keys)):
        label = labels[i].strip() if i < len(labels) else ""
        imp = import_ids[i] if i < len(import_ids) else ""
        if not label:
            continue
        questions.append(dict(idx=i, label=label,
                              is_text="_TEXT" in imp,
                              is_multi=("Selected Choice" in label) or ("check all" in label.lower())))

    n_resp = n_finished = 0
    fin_idx = keys.index("Finished") if "Finished" in keys else 6
    rid_idx = keys.index("ResponseId") if "ResponseId" in keys else 8
    for r in data:
        if len(r) > rid_idx and r[rid_idx].strip():
            n_resp += 1
            if len(r) > fin_idx and r[fin_idx].strip().lower() == "true":
                n_finished += 1

    results = []
    sentiment = Counter()
    for q in questions:
        i = q["idx"]
        raw = [r[i].strip() for r in data if len(r) > i and r[i].strip()]
        if q["is_text"]:
            results.append(dict(type="text", label=q["label"], answers=raw))
        elif q["is_multi"]:
            opts = Counter()
            for v in raw:
                for piece in v.split(","):
                    piece = piece.strip()
                    if piece:
                        opts[piece] += 1
            results.append(dict(type="multi", label=q["label"], n=len(raw),
                                counts=opts.most_common()))
        else:
            cnt = Counter(raw)
            scale = detect_scale(list(cnt.keys()))
            if scale:
                ordered = [c for c in scale if c in cnt]
                fav_cut = len(scale) / 2.0
                fav = sum(cnt[c] for c in cnt if c in scale and scale.index(c) >= fav_cut)
                for cat, c in cnt.items():
                    if cat in scale:
                        sentiment[classify(scale.index(cat), len(scale))] += c
            else:
                ordered = [c for c, _ in cnt.most_common()]
                fav = None
            results.append(dict(type="scale", label=q["label"], n=len(raw),
                                ordered=ordered, counts=cnt, scale=scale, fav=fav))

    favs = [100 * q["fav"] / q["n"] for q in results
            if q["type"] == "scale" and q.get("fav") is not None and q["n"]]
    avg_fav = round(sum(favs) / len(favs)) if favs else None
    return dict(n_resp=n_resp, n_finished=n_finished, questions=results,
                avg_fav=avg_fav, sentiment=sentiment)


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s))


def svg_donut(segments, size=190, stroke=30, center_num="", center_lbl=""):
    r = (size - stroke) / 2
    cx = cy = size / 2
    circ = 2 * math.pi * r
    total = sum(v for _, v, _ in segments) or 1
    offset = 0.0
    parts = [f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="#eef1f4" stroke-width="{stroke}"/>']
    for _, v, color in segments:
        if v <= 0:
            continue
        dash = v / total * circ
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="{color}" '
                     f'stroke-width="{stroke}" stroke-dasharray="{dash:.2f} {circ - dash:.2f}" '
                     f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>')
        offset += dash
    parts.append(f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" font-size="38" '
                 f'font-weight="800" fill="{UCLA_DARKEST_BLUE}">{center_num}</text>'
                 f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" font-size="11" '
                 f'letter-spacing="1.5" fill="#64748b">{center_lbl}</text>')
    return f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img">{"".join(parts)}</svg>'


def render_box(w, parsed):
    st = status_of(w, parsed)
    mod_class = "online" if w["modality"].lower() == "online" else "inperson"
    if st == "data":
        avg = f'{parsed["avg_fav"]}%' if parsed["avg_fav"] is not None else "\u2014"
        foot = (f'<div class="box-foot"><span class="box-metric"><b>{parsed["n_resp"]}</b> participants</span>'
                f'<span class="box-metric"><b>{avg}</b> favorable</span></div>')
    else:
        foot = f'<div class="box-foot"><span class="badge s-{st}">{esc(STATUS[st]["label"])}</span></div>'
    return (f'<a class="box box-{st}" href="#{slug(w)}">'
            f'<div class="box-date">{esc(w["date"])}</div>'
            f'<div class="box-title">{esc(w["title"])}</div>'
            f'<span class="pill {mod_class}">{esc(w["modality"])}</span>{foot}</a>')


def render_scale_q(q):
    n = q["n"]
    parts = [f'<div class="q"><div class="q-label">{esc(q["label"])}<span class="q-n">n={n}</span></div>']
    if q.get("fav") is not None and n:
        parts.append(f'<div class="fav">{round(100 * q["fav"] / n)}% favorable</div>')
    scale = q["scale"]
    for cat in q["ordered"]:
        c = q["counts"][cat]
        pct = 100 * c / n if n else 0
        color = color_for(scale.index(cat), len(scale)) if scale else UCLA_BLUE
        parts.append('<div class="bar-row">'
                     f'<div class="bar-cat">{esc(cat)}</div>'
                     '<div class="bar-track">'
                     f'<div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div></div>'
                     f'<div class="bar-val">{c} <span class="muted">({pct:.0f}%)</span></div></div>')
    parts.append('</div>')
    return "".join(parts)


def render_multi_q(q):
    n = q["n"]
    maxc = max((c for _, c in q["counts"]), default=1)
    parts = [f'<div class="q"><div class="q-label">{esc(q["label"])}<span class="q-n">{n} respondents</span></div>']
    for cat, c in q["counts"]:
        pct = 100 * c / maxc if maxc else 0
        parts.append('<div class="bar-row">'
                     f'<div class="bar-cat">{esc(cat)}</div>'
                     '<div class="bar-track">'
                     f'<div class="bar-fill" style="width:{pct:.1f}%;background:{UCLA_DARKER_BLUE}"></div></div>'
                     f'<div class="bar-val">{c}</div></div>')
    parts.append('</div>')
    return "".join(parts)


def render_text_q(q):
    if not q["answers"]:
        return ""
    parts = [f'<div class="q"><div class="q-label">{esc(q["label"])}<span class="q-n">{len(q["answers"])} comments</span></div>'
             '<div class="comments">']
    for a in q["answers"]:
        parts.append(f'<blockquote>{esc(a)}</blockquote>')
    parts.append('</div></div>')
    return "".join(parts)


def render_workshop(w, parsed):
    mod_class = "online" if w["modality"].lower() == "online" else "inperson"
    avg = parsed["avg_fav"]
    head = (f'<div class="ws-head"><div><h3>{esc(w["title"])}</h3>'
            f'<div class="ws-meta"><span class="pill {mod_class}">{esc(w["modality"])}</span>'
            f'<span class="muted">{esc(w["date"])}</span></div></div>'
            f'<div class="ws-stats">'
            f'<div class="stat"><span class="num">{parsed["n_resp"]}</span><span class="lbl">responses</span></div>'
            + (f'<div class="stat"><span class="num">{avg}%</span><span class="lbl">favorable</span></div>'
               if avg is not None else "")
            + (f'<div class="stat"><span class="num">{w["rsvp"]}</span><span class="lbl">RSVPs</span></div>'
               if w.get("rsvp") else "")
            + '</div></div>')
    body = "".join(render_scale_q(q) if q["type"] == "scale"
                   else render_multi_q(q) if q["type"] == "multi"
                   else render_text_q(q) for q in parsed["questions"])
    return f'<section class="card" id="{slug(w)}">{head}{body}</section>'


def render_status_card(w, parsed):
    st = status_of(w, parsed)
    mod_class = "online" if w["modality"].lower() == "online" else "inperson"
    return (f'<section class="card status-card sc-{st}" id="{slug(w)}">'
            f'<div class="ws-head"><div><h3>{esc(w["title"])}</h3>'
            f'<div class="ws-meta"><span class="pill {mod_class}">{esc(w["modality"])}</span>'
            f'<span class="muted">{esc(w["date"])}</span>'
            f'<span class="badge s-{st}">{esc(STATUS[st]["label"])}</span></div></div></div>'
            f'<p class="note">{esc(w.get("note", "Data not available."))}</p></section>')


# ---------------------------------------------------------------------------
# Print / PDF stylesheet (plain string: keeps figures & tables off page breaks)
# ---------------------------------------------------------------------------
PRINT_CSS = """
@media print{
  @page{margin:14mm;}
  html,body{background:#fff;}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
  .print-btn{display:none !important;}
  .wrap{max-width:100%;padding:0;}
  header.hero,.card,.panel,.overview{box-shadow:none;}
  /* Never split a figure, table row, comment, box, or summary tile */
  .panel,.box,.hl,.kpi,.q,.bar-row,.ov-row,.dl-row,blockquote,
  .sent-bar,.donut-wrap,.ws-head,.status-card{
    break-inside:avoid;page-break-inside:avoid;
  }
  /* Keep section headings with the content that follows */
  h2.section,h3,.q-label{break-after:avoid;page-break-after:avoid;}
  /* Stack the two-column executive summary for clean pagination */
  .exec{display:block;}
  .exec .panel{margin-bottom:14px;}
  .grid{gap:10px;}
  a[href]{color:inherit;text-decoration:none;}
  .back{display:none;}
  footer{margin-top:20px;}
}
"""


# ---------------------------------------------------------------------------
# CSS (UCLA branded)
# ---------------------------------------------------------------------------
def build_css():
    status_box_css = "".join(
        f".box-{k}{{border-left-color:{v['accent']}}}\n.badge.s-{k}{{background:{v['bg']};color:{v['fg']}}}\n"
        f".status-card.sc-{k}{{border-color:{v['accent']}55;background:{v['bg']}33}}\n"
        for k, v in STATUS.items())
    return f"""
:root{{--blue:{UCLA_BLUE};--dblue:{UCLA_DARKEST_BLUE};--gold:{UCLA_GOLD};--ink:{UCLA_DARKEST_BLUE};--muted:#5b6b7a;--line:#e3e8ee;}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2937;background:#eef2f6;line-height:1.5}}
.wrap{{max-width:1040px;margin:0 auto;padding:30px 20px 80px}}
header.hero{{background:linear-gradient(120deg,{UCLA_DARKEST_BLUE} 0%,{UCLA_DARKER_BLUE} 55%,{UCLA_BLUE} 100%);color:#fff;border-radius:16px;padding:34px 34px;border-top:6px solid {UCLA_GOLD};box-shadow:0 12px 30px rgba(0,59,92,.28)}}
header.hero .eyebrow{{text-transform:uppercase;letter-spacing:.16em;font-size:12px;color:{UCLA_GOLD};font-weight:700;margin:0 0 8px}}
header.hero h1{{margin:0 0 6px;font-size:32px;line-height:1.12}}
header.hero p.sub{{margin:6px 0 0;opacity:.92;font-size:15px;max-width:70ch}}
.kpis{{display:flex;flex-wrap:wrap;gap:14px;margin-top:24px}}
.kpi{{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:12px;padding:14px 18px;min-width:120px}}
.kpi .num{{font-size:27px;font-weight:800;display:block}}
.kpi .num small{{font-size:15px;font-weight:600;opacity:.8}}
.kpi .lbl{{font-size:11px;opacity:.85;text-transform:uppercase;letter-spacing:.05em}}
h2.section{{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:34px 4px 14px;border-bottom:2px solid var(--line);padding-bottom:8px}}
h2.section .legend{{float:right;text-transform:none;letter-spacing:0;font-size:11px;color:var(--muted)}}
.legend .lg{{display:inline-flex;align-items:center;gap:5px;margin-left:12px}}
.legend .sw{{width:11px;height:11px;border-radius:3px;display:inline-block}}

/* executive summary */
.exec{{display:grid;grid-template-columns:300px 1fr;gap:18px}}
@media(max-width:760px){{.exec{{grid-template-columns:1fr}}}}
.panel{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:22px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
.panel h4{{margin:0 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}
.donut-wrap{{display:flex;flex-direction:column;align-items:center;gap:14px}}
.donut-legend{{width:100%;display:flex;flex-direction:column;gap:7px}}
.dl-row{{display:flex;align-items:center;gap:9px;font-size:13px}}
.dl-row .sw{{width:13px;height:13px;border-radius:4px}}
.dl-row .cnt{{margin-left:auto;font-weight:700;color:var(--ink)}}
.sent-bar{{display:flex;height:30px;border-radius:8px;overflow:hidden;margin:6px 0 10px}}
.sent-bar span{{display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:700}}
.sent-key{{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:var(--muted)}}
.sent-key .sw{{width:11px;height:11px;border-radius:3px;display:inline-block;margin-right:5px;vertical-align:middle}}
.hl-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px}}
@media(max-width:560px){{.hl-grid{{grid-template-columns:1fr 1fr}}}}
.hl{{background:#f6f9fc;border:1px solid var(--line);border-radius:10px;padding:13px 14px}}
.hl .n{{font-size:22px;font-weight:800;color:var(--blue)}}
.hl .t{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:2px}}
.takeaways{{margin:14px 0 0;padding-left:18px;font-size:13.5px;color:#374151}}
.takeaways li{{margin:5px 0}}

/* at a glance grid */
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:14px}}
.box{{display:flex;flex-direction:column;gap:8px;text-decoration:none;color:#1f2937;background:#fff;border:1px solid var(--line);border-left:5px solid {UCLA_BLUE};border-radius:12px;padding:15px 16px;transition:transform .12s,box-shadow .12s;min-height:130px}}
.box:hover{{transform:translateY(-3px);box-shadow:0 10px 22px rgba(0,59,92,.14)}}
.box-date{{font-size:12px;color:var(--muted);font-weight:600}}
.box-title{{font-size:14.5px;font-weight:600;line-height:1.25;flex:1;color:var(--ink)}}
.box .pill{{align-self:flex-start}}
.box-foot{{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin-top:2px}}
.box-metric{{font-size:12px;color:var(--muted)}}
.box-metric b{{color:var(--ink);font-size:15px}}
.badge{{font-size:11px;font-weight:700;padding:3px 9px;border-radius:6px}}
{status_box_css}

.overview{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px 22px}}
.ov-row{{display:flex;align-items:center;gap:12px;margin:9px 0}}
.ov-name{{flex:0 0 46%;font-size:14px}}
.ov-name a{{color:var(--ink);text-decoration:none;font-weight:600}}
.ov-name .muted{{font-size:12px}}
.ov-track{{flex:1;background:#eef2f7;border-radius:6px;height:22px;overflow:hidden}}
.ov-fill{{height:100%;border-radius:6px;background:linear-gradient(90deg,{UCLA_BLUE},{UCLA_DARKEST_BLUE})}}
.ov-val{{flex:0 0 42px;text-align:right;font-weight:700;font-size:13px;color:var(--ink)}}

.card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:22px 24px;margin:16px 0;box-shadow:0 1px 2px rgba(0,0,0,.04);scroll-margin-top:16px}}
.status-card{{border-width:1px;border-style:solid}}
.ws-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:6px}}
.ws-head h3{{margin:0 0 6px;font-size:18px;color:var(--ink)}}
.ws-meta{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.pill{{font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px}}
.pill.inperson{{background:{UCLA_LIGHTEST_BLUE};color:{UCLA_DARKER_BLUE}}}
.pill.online{{background:#fff2c2;color:#8a6d00}}
.ws-stats{{display:flex;gap:18px}}
.stat{{text-align:center}}
.stat .num{{font-size:24px;font-weight:800;display:block;color:var(--blue)}}
.stat .lbl{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
.q{{margin:18px 0 4px}}
.q-label{{font-weight:600;font-size:14px;margin-bottom:8px;display:flex;justify-content:space-between;gap:14px;align-items:baseline;color:var(--ink)}}
.q-n{{font-weight:400;color:var(--muted);font-size:12px;white-space:nowrap}}
.fav{{display:inline-block;background:{UCLA_LIGHTEST_BLUE};color:{UCLA_DARKER_BLUE};font-size:12px;font-weight:700;padding:2px 10px;border-radius:6px;margin-bottom:8px}}
.bar-row{{display:flex;align-items:center;gap:10px;margin:5px 0}}
.bar-cat{{flex:0 0 38%;font-size:13px;color:#334155}}
.bar-track{{flex:1;background:#f1f5f9;border-radius:5px;height:18px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:5px;min-width:2px}}
.bar-val{{flex:0 0 76px;text-align:right;font-size:13px;font-weight:600}}
.muted{{color:var(--muted);font-weight:400}}
.comments{{display:flex;flex-direction:column;gap:8px;margin-top:6px}}
blockquote{{margin:0;padding:10px 14px;background:#f6f9fc;border-left:3px solid {UCLA_LIGHT_BLUE};border-radius:0 8px 8px 0;font-size:13.5px;color:#334155}}
.note{{color:#475569;font-size:14px;margin:10px 0 0}}
.back{{display:inline-block;margin:6px 0 0 4px;font-size:12px;color:var(--blue);text-decoration:none;font-weight:600}}
footer{{margin-top:40px;text-align:center;color:var(--muted);font-size:12px}}
.print-btn{{position:fixed;top:18px;right:18px;z-index:50;background:{UCLA_BLUE};color:#fff;border:none;border-radius:8px;padding:10px 16px;font-size:13px;font-weight:700;cursor:pointer;box-shadow:0 4px 14px rgba(0,59,92,.35)}}
.print-btn:hover{{background:{UCLA_DARKER_BLUE}}}
""" + PRINT_CSS


def build_report(series, quarter_label):
    items = [w for w in WORKSHOPS if w["series"] == series]
    parsed_items = [(w, parse_csv(os.path.join(BASE, w["file"])) if w.get("file") else None)
                    for w in items]

    total_resp = sum(p["n_resp"] for _, p in parsed_items if p)
    n_with_data = sum(1 for w, p in parsed_items if status_of(w, p) == "data")
    n_missing = sum(1 for w, p in parsed_items if status_of(w, p) == "missing")
    total_rsvp = sum(w["rsvp"] for w, _ in parsed_items if w.get("rsvp"))

    # status breakdown for donut
    status_counts = Counter(status_of(w, p) for w, p in parsed_items)
    donut_segments = [(STATUS[k]["label"], status_counts.get(k, 0), STATUS[k]["accent"])
                      for k in ["data", "missing", "nopostsurvey", "cancelled", "noinfo"]
                      if status_counts.get(k, 0)]
    donut_legend = "".join(
        f'<div class="dl-row"><span class="sw" style="background:{c}"></span>{esc(lbl)}'
        f'<span class="cnt">{v}</span></div>' for lbl, v, c in donut_segments)

    # pooled sentiment
    sent = Counter()
    for _, p in parsed_items:
        if p:
            sent.update(p["sentiment"])
    sent_total = sum(sent.values()) or 1
    pos_pct = round(100 * sent["pos"] / sent_total)
    neu_pct = round(100 * sent["neu"] / sent_total)
    neg_pct = 100 - pos_pct - neu_pct

    def seg(p, color):
        return (f'<span style="width:{p}%;background:{color}">{p}%</span>' if p >= 7
                else f'<span style="width:{p}%;background:{color}"></span>') if p > 0 else ""
    sent_bar = seg(pos_pct, SENT_POS) + seg(neu_pct, SENT_NEU) + seg(neg_pct, SENT_NEG)

    # response rate (data workshops with an RSVP figure)
    rr_resp = sum(p["n_resp"] for w, p in parsed_items if p and w.get("rsvp"))
    rr_rsvp = sum(w["rsvp"] for w, p in parsed_items if p and w.get("rsvp"))
    resp_rate = round(100 * rr_resp / rr_rsvp) if rr_rsvp else 0

    # top-rated workshop
    rated = [(w, p) for w, p in parsed_items if p and p["avg_fav"] is not None]
    top = max(rated, key=lambda x: x[1]["avg_fav"], default=None)
    top_txt = (f'{top[1]["avg_fav"]}% \u00b7 {esc(top[0]["title"][:34])}\u2026'
               if top else "\u2014")

    # at-a-glance legend
    glance_legend = "".join(
        f'<span class="lg"><span class="sw" style="background:{STATUS[k]["accent"]}"></span>{esc(STATUS[k]["label"])}</span>'
        for k in ["data", "missing", "nopostsurvey", "cancelled", "noinfo"]
        if status_counts.get(k, 0))

    boxes = "".join(render_box(w, p) for w, p in parsed_items)

    ov_max = max((p["n_resp"] for _, p in parsed_items if p), default=1)
    ov_rows = "".join(
        '<div class="ov-row">'
        f'<div class="ov-name"><a href="#{slug(w)}">{esc(w["title"])}</a> '
        f'<span class="muted">\u2014 {esc(w["modality"])}, {esc(w["date"])}</span></div>'
        f'<div class="ov-track"><div class="ov-fill" style="width:{100 * p["n_resp"] / ov_max:.1f}%"></div></div>'
        f'<div class="ov-val">{p["n_resp"]}</div></div>'
        for w, p in parsed_items if p)

    cards = "".join((render_workshop(w, p) if p else render_status_card(w, p))
                    + '<a class="back" href="#top">\u2191 Back to top</a>'
                    for w, p in parsed_items)

    total_ws = len(parsed_items)
    avg_fav_all = round(sum(p["avg_fav"] for _, p in rated) / len(rated)) if rated else 0
    missing_li = (f'<li><b>{n_missing}</b> workshop(s) still missing a post-survey export '
                  '\u2014 see flagged cards below.</li>') if n_missing else ""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(series)} Series \u2014 Post-Survey Report</title>
<style>{build_css()}</style></head><body>
<button class="print-btn" onclick="window.print()">\u2193 Save as PDF</button>
<div class="wrap" id="top">
<header class="hero">
  <p class="eyebrow">UCLA TLC \u00b7 Workshop Post-Survey Report \u00b7 {esc(quarter_label)}</p>
  <h1>{esc(series)} Series</h1>
  <p class="sub">Participant post-survey feedback across the {esc(series.lower())} workshop series, summarizing reach, satisfaction, and themes.</p>
  <div class="kpis">
    <div class="kpi"><span class="num">{total_ws}</span><span class="lbl">Workshops</span></div>
    <div class="kpi"><span class="num">{total_resp}</span><span class="lbl">Survey responses</span></div>
    <div class="kpi"><span class="num">{total_rsvp}</span><span class="lbl">Total RSVPs</span></div>
    <div class="kpi"><span class="num">{pos_pct}<small>%</small></span><span class="lbl">Positive sentiment</span></div>
  </div>
</header>

<h2 class="section">Executive summary</h2>
<div class="exec">
  <div class="panel">
    <h4>Workshop status</h4>
    <div class="donut-wrap">
      {svg_donut(donut_segments, center_num=str(total_ws), center_lbl="WORKSHOPS")}
      <div class="donut-legend">{donut_legend}</div>
    </div>
  </div>
  <div class="panel">
    <h4>Overall participant sentiment <span class="muted" style="text-transform:none;letter-spacing:0">({sent_total} ratings across {total_resp} participants)</span></h4>
    <div class="sent-bar">{sent_bar}</div>
    <div class="sent-key">
      <span><span class="sw" style="background:{SENT_POS}"></span>Positive {pos_pct}%</span>
      <span><span class="sw" style="background:{SENT_NEU}"></span>Neutral {neu_pct}%</span>
      <span><span class="sw" style="background:{SENT_NEG}"></span>Negative {neg_pct}%</span>
    </div>
    <div class="hl-grid">
      <div class="hl"><div class="n">{n_with_data}/{total_ws}</div><div class="t">With survey data</div></div>
      <div class="hl"><div class="n">{resp_rate}%</div><div class="t">Response rate</div></div>
      <div class="hl"><div class="n">{avg_fav_all}%</div><div class="t">Avg favorable</div></div>
    </div>
    <ul class="takeaways">
      <li><b>{total_resp}</b> responses collected across <b>{n_with_data}</b> workshops with data; <b>{pos_pct}%</b> of all ratings were positive.</li>
      <li>Highest-rated session: <b>{top_txt}</b> favorable.</li>
      {missing_li}
    </ul>
  </div>
</div>

<h2 class="section">Workshops at a glance \u00b7 click to jump
  <span class="legend">{glance_legend}</span></h2>
<div class="grid">{boxes}</div>

<h2 class="section">Responses by workshop</h2>
<div class="overview">{ov_rows}</div>

<h2 class="section">Workshop details</h2>
{cards}

<footer>Generated from Qualtrics post-survey CSV exports \u00b7 UCLA TLC / IEED.<br>
Question bars use a gold\u2013to\u2013blue scale (gold = lower / less favorable, blue = higher / more favorable); "favorable" = upper half of each rating scale.</footer>
</div></body></html>"""


def main():
    for series, quarter, fname in [
        ("Wellbeing", "Winter & Spring 2026", "Wellbeing_Series_Report.html"),
        ("Preparing to Teach", "Winter & Spring 2026", "Preparing-to-Teach_Series_Report.html"),
    ]:
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            f.write(build_report(series, quarter))
        print(f"wrote {fname}")


if __name__ == "__main__":
    main()
