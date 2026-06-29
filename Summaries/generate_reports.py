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

# Five-step Likert palette for stacked bars (darker, easier to distinguish)
LIKERT_5_COLORS = ["#B45309", "#D97706", "#64748B", "#2774AE", "#003B5C"]
LIKERT_5_LABELS = [
    ("1", "Strongly disagree"),
    ("2", "Disagree"),
    ("3", "Neutral"),
    ("4", "Agree"),
    ("5", "Strongly agree"),
]

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
         modality="In-person", date="May 4, 2026", rsvp=27,
         file="Sp26 Nurturing Ethical AI/dataset.csv"),
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
    ["Very dissatisfied", "Dissatisfied", "Somewhat dissatisfied",
     "Neither satisfied nor dissatisfied", "Somewhat satisfied", "Satisfied", "Very satisfied"],
    ["Definitely will not", "Probably will not", "Might or might not",
     "Probably will", "Definitely will"],
    ["No", "Maybe", "Yes"],
    ["1. Strongly Disagree", "2. Disagree", "3. Neutral", "4. Agree", "5. Strongly Agree"],
    ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"],
]

ONE_PAGER_WORKSHOP = dict(
    title="Nurturing Engaged and Ethical Learners with Critical AI Literacy",
    series="Preparing to Teach",
    modality="In-person",
    date="May 4, 2026",
    rsvp=27,
    file="Sp26 Nurturing Ethical AI/dataset.csv",
)


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


def likert_color_index(rank, n):
    """Map any ordinal rank to a 0–4 index for the 5-step Likert palette."""
    if n <= 1:
        return 4
    return round(rank / (n - 1) * 4)


def likert_color(rank, n):
    return LIKERT_5_COLORS[likert_color_index(rank, n)]


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


def collect_suggestions(w, parsed, limit=6, max_len=220):
    """Pull verbatim improvement comments from open-ended survey questions."""
    keywords = ("suggest", "improve", "comment", "support", "interest", "topic")
    seen, quotes = set(), []
    if not parsed:
        return quotes
    for q in parsed["questions"]:
        if q["type"] != "text":
            continue
        label = q["label"].lower()
        if not any(k in label for k in keywords):
            continue
        for ans in q["answers"]:
            text = ans.strip()
            if len(text) < 8 or text.lower() in seen:
                continue
            seen.add(text.lower())
            if max_len and len(text) > max_len:
                text = text[: max_len - 1].rstrip() + "\u2026"
            quotes.append(text)
            if len(quotes) >= limit:
                return quotes
    return quotes


def render_compact_bar(label, pct, color=None):
    color = color or UCLA_BLUE
    short = label if len(label) <= 42 else label[:39].rstrip() + "\u2026"
    return (
        f'<div class="c-row"><div class="c-label" title="{esc(label)}">{esc(short)}</div>'
        f'<div class="c-track"><div class="c-fill" style="width:{pct:.1f}%;background:{color}"></div></div>'
        f'<div class="c-val">{pct:.0f}%</div></div>'
    )


def render_likert_stacked_q(q, label=None):
    """Single horizontal stacked bar per Likert question."""
    n = q["n"]
    title = label or q["label"]
    scale = q.get("scale")
    ordered = list(scale) if scale else list(q["ordered"])

    segments = []
    for cat in ordered:
        c = q["counts"].get(cat, 0)
        if not n or c <= 0:
            continue
        pct = 100 * c / n
        rank = scale.index(cat) if scale and cat in scale else 0
        n_scale = len(scale) if scale else max(len(ordered), 1)
        color = likert_color(rank, n_scale)
        chip = likert_color_index(rank, n_scale) + 1
        inner = f"{c} ({pct:.0f}%)"
        sm_cls = " likert-seg-sm" if pct < 16 else ""
        tip = esc(f"{chip} · {cat}: {c} ({pct:.0f}%)")
        segments.append(
            f'<span class="likert-seg{sm_cls}" style="width:{pct:.2f}%;background:{color}" '
            f'title="{tip}">{inner}</span>'
        )

    stack = "".join(segments) if segments else '<span class="likert-empty">No responses</span>'
    fav_line = ""
    if q.get("fav") is not None and n:
        fav_n = q["fav"]
        fav_pct = round(100 * fav_n / n)
        fav_line = f'<div class="likert-fav">{fav_pct}% favorable (n={fav_n}/{n})</div>'

    return (
        f'<div class="likert-q">'
        f'<div class="likert-q-head">'
        f'<div class="likert-q-title">{esc(title)}</div>'
        f'<span class="likert-q-n">n={n}</span></div>'
        f'<div class="likert-stack">{stack}</div>'
        f'{fav_line}</div>'
    )


def render_likert_legend_note(compact=False):
    chips = []
    for i, (num, label) in enumerate(LIKERT_5_LABELS):
        color = LIKERT_5_COLORS[i]
        chips.append(
            f'<span class="likert-legend-chip">'
            f'<i class="likert-swatch likert-swatch-lg" style="background:{color}"></i>'
            f'<span class="likert-legend-num">{num}</span>'
            f'<span class="likert-legend-text">{label}</span></span>'
        )
    wrap_cls = "likert-legend-wrap likert-legend-section" if compact else "likert-legend-wrap"
    hint = "" if compact else (
        '<p class="likert-legend-hint">Longer scales (e.g., 7-point satisfaction) are mapped to these five colors.</p>'
    )
    return (
        f'<div class="{wrap_cls}">'
        '<div class="likert-legend-title">Response scale (1 = low &rarr; 5 = high)</div>'
        f'<div class="likert-legend">{"".join(chips)}</div>'
        f'{hint}</div>'
    )


def fav_pct(q):
    if q["type"] != "scale" or not q["n"] or q.get("fav") is None:
        return None
    return round(100 * q["fav"] / q["n"])


def build_one_pager():
    w = ONE_PAGER_WORKSHOP
    parsed = parse_csv(os.path.join(BASE, w["file"]))
    if not parsed:
        raise SystemExit(f"Could not parse survey data: {w['file']}")

    n_resp = parsed["n_resp"]
    n_finished = parsed["n_finished"]
    rsvp = w.get("rsvp") or 0
    resp_rate = round(100 * n_finished / rsvp) if rsvp else 0

    sent = parsed["sentiment"]
    sent_total = sum(sent.values()) or 1
    pos_pct = round(100 * sent["pos"] / sent_total)
    neu_pct = round(100 * sent["neu"] / sent_total)
    neg_pct = 100 - pos_pct - neu_pct
    avg_fav = parsed["avg_fav"] or 0

    def seg(p, color):
        return (f'<span style="width:{p}%;background:{color}">{p}%</span>' if p >= 7
                else f'<span style="width:{p}%;background:{color}"></span>') if p > 0 else ""

    # Group questions by theme
    experience_keys = ("logistics", "materials", "presenters", "facilitators",
                       "learned new", "achieved its stated", "incorporate", "recommend")
    confidence_keys = ("confident designing", "design ai assignments", "academic integrity",
                       "practical strategies")
    skill_questions = [q for q in parsed["questions"]
                       if q["type"] == "scale" and "support the following skills" in q["label"]]

    scale_questions = [q for q in parsed["questions"] if q["type"] == "scale"]
    n_scale_q = len(scale_questions)

    experience_blocks = ""
    for q in parsed["questions"]:
        if q["type"] != "scale":
            continue
        label_l = q["label"].lower()
        if not any(k in label_l for k in experience_keys):
            continue
        experience_blocks += render_likert_stacked_q(q)

    confidence_blocks = ""
    for q in parsed["questions"]:
        if q["type"] != "scale":
            continue
        if not any(k in q["label"].lower() for k in confidence_keys):
            continue
        confidence_blocks += render_likert_stacked_q(q)

    skill_blocks = ""
    for q in skill_questions:
        short = q["label"].split(" - ")[-1].strip() if " - " in q["label"] else q["label"]
        skill_blocks += render_likert_stacked_q(q, label=short)

    likert_legend = render_likert_legend_note(compact=True)

    suggestions = collect_suggestions(w, parsed, limit=10, max_len=None)
    sugg_items = "".join(f'<blockquote>&ldquo;{esc(s)}&rdquo;</blockquote>' for s in suggestions)
    synthesized = []
    if any("longer" in s.lower() for s in suggestions):
        synthesized.append("Offer a longer session or split content into two focused workshops (values/reflection vs. assignment design).")
    if any("card" in s.lower() or "goals" in s.lower() for s in suggestions):
        synthesized.append("Clarify the workshop arc and streamline activities so participants can connect critical AI literacy to concrete assignment tweaks.")
    if any("organized" in s.lower() for s in suggestions):
        synthesized.append("Maintain the well-organized format participants praised.")
    synth_items = "".join(f"<li>{esc(s)}</li>" for s in synthesized)

    overview = (
        f"In Spring 2026, TLC offered <b>{esc(w['title'])}</b> as an in-person session in the "
        f"<b>{esc(w['series'])}</b> series ({esc(w['date'])}). The workshop focused on critical AI "
        f"literacy, ethical assignment design, and integrating reflection on affective outcomes when "
        f"students use AI. <b>{n_finished}</b> participants completed the post-workshop survey "
        f"({resp_rate}% of {rsvp} RSVPs)."
    )

    participant_blurb = (
        f"Respondents were UCLA instructors and instructional team members who attended the "
        f"in-person workshop. Of {rsvp} RSVPs, {n_finished} completed the survey and "
        f"{n_resp - n_finished} additional partial response(s) were recorded. "
        f"Feedback reflects faculty perspectives on AI-integrated assignment design and ethical "
        f"learning outcomes."
    )

    sent_donut = svg_donut(
        [("Positive", sent["pos"], SENT_POS),
         ("Neutral", sent["neu"], SENT_NEU),
         ("Negative", sent["neg"], SENT_NEG)],
        size=160, stroke=26, center_num=f"{pos_pct}%", center_lbl="POSITIVE")

    sent_explainer = (
        f"The <b>{sent_total} ratings</b> figure is the total number of individual Likert-scale "
        f"selections pooled across all scaled survey questions—not the number of respondents. "
        f"There are <b>{n_scale_q} scaled questions</b>; each answer from a completed survey "
        f"counts as one rating. With <b>{n_finished} completed surveys</b>, most items received "
        f"<b>4 responses</b> (one completed record contained no scaled answers); a few items "
        f"received <b>3</b> where participants skipped. Each selection is classified as "
        f"<b>positive</b> (upper half of that question&rsquo;s scale), <b>neutral</b> (middle), "
        f"or <b>negative</b> (lower half)."
    )

    css = f"""
:root{{--blue:{UCLA_BLUE};--dblue:{UCLA_DARKEST_BLUE};--dkrblue:{UCLA_DARKER_BLUE};--gold:{UCLA_GOLD};--line:#e3e8ee;--muted:#5b6b7a;--panel:#f6f9fc;}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2937;background:#eef2f6;line-height:1.65;font-size:15px}}
.page{{max-width:960px;margin:0 auto;padding:40px 32px 72px}}
header{{background:linear-gradient(120deg,{UCLA_DARKEST_BLUE},{UCLA_DARKER_BLUE} 55%,{UCLA_BLUE});color:#fff;border-radius:16px;padding:36px 40px;border-top:6px solid {UCLA_GOLD};box-shadow:0 10px 28px rgba(0,59,92,.22)}}
header .eyebrow{{text-transform:uppercase;letter-spacing:.14em;font-size:11px;color:{UCLA_GOLD};font-weight:700;margin:0 0 10px}}
header h1{{margin:0 0 10px;font-size:28px;line-height:1.2;max-width:28ch}}
header .sub{{margin:0;font-size:15px;opacity:.92;max-width:52ch;line-height:1.5}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:28px}}
.kpi{{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:12px;padding:16px 14px;text-align:center}}
.kpi .n{{display:block;font-size:28px;font-weight:800;line-height:1.1}}
.kpi .l{{font-size:10px;text-transform:uppercase;letter-spacing:.05em;opacity:.88;margin-top:4px;display:block}}
section{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:32px 36px;margin-top:28px;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
section h2{{margin:0 0 18px;font-size:13px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:12px}}
.prose p{{margin:0 0 1.15em;font-size:15px;color:#374151;line-height:1.65}}
.prose p:last-child{{margin-bottom:0}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:8px}}
.grid2>div{{min-width:0}}
.result-block{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:24px 28px;margin-top:24px}}
.result-block:first-of-type{{margin-top:0}}
.result-block h3{{margin:0 0 6px;font-size:16px;color:var(--dblue);font-weight:700}}
.result-block .hint{{margin:0 0 18px;font-size:13px;color:var(--muted)}}
.sent-panel{{display:grid;grid-template-columns:180px 1fr;gap:32px;align-items:center}}
.sent-bar{{display:flex;height:36px;border-radius:9px;overflow:hidden;margin:12px 0 16px}}
.sent-bar span{{display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700}}
.sent-key{{display:flex;gap:24px;font-size:13px;color:var(--muted);flex-wrap:wrap}}
.sent-key .sw{{width:12px;height:12px;border-radius:3px;display:inline-block;margin-right:6px;vertical-align:middle}}
.sent-table{{width:100%;border-collapse:collapse;margin-top:16px;font-size:14px}}
.sent-table th,.sent-table td{{padding:10px 14px;text-align:left;border-bottom:1px solid var(--line)}}
.sent-table th{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600}}
.sent-table td:last-child,.sent-table th:last-child{{text-align:right}}
.likert-legend-wrap{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:0 0 24px}}
.likert-legend-section{{margin:0 0 20px;padding:12px 16px}}
.likert-legend-section .likert-legend-title{{font-size:12px;margin-bottom:8px}}
.likert-legend-section .likert-legend-chip{{padding:8px 6px}}
.likert-legend-section .likert-swatch-lg{{width:22px;height:22px}}
.likert-legend-section .likert-legend-num{{font-size:15px}}
.likert-legend-section .likert-legend-text{{font-size:10px}}
.likert-legend-title{{font-size:13px;font-weight:700;color:var(--dblue);margin-bottom:12px}}
.likert-legend-hint{{margin:10px 0 0;font-size:12px;color:var(--muted)}}
.likert-legend{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}
.likert-legend-chip{{display:flex;flex-direction:column;align-items:center;gap:6px;padding:10px 8px;background:#fff;border:1px solid var(--line);border-radius:8px;text-align:center}}
.likert-swatch{{display:inline-block;width:12px;height:12px;border-radius:3px;flex-shrink:0;border:1px solid rgba(0,0,0,.18)}}
.likert-swatch-lg{{width:28px;height:28px;border-radius:6px;border:2px solid rgba(0,0,0,.12)}}
.likert-legend-num{{font-size:18px;font-weight:800;color:var(--dblue);line-height:1}}
.likert-legend-text{{font-size:11px;color:#475569;line-height:1.3}}
.likert-q{{margin:22px 0;padding-bottom:22px;border-bottom:1px solid var(--line)}}
.likert-q:last-child{{margin-bottom:0;padding-bottom:0;border-bottom:none}}
.likert-q-head{{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:10px}}
.likert-q-title{{font-weight:600;font-size:15px;color:var(--dblue);line-height:1.45;flex:1}}
.likert-q-n{{font-size:13px;color:var(--muted);white-space:nowrap;font-weight:600}}
.likert-stack{{display:flex;height:38px;border-radius:8px;overflow:hidden;background:#eef2f7;border:1px solid #cbd5e1}}
.likert-seg{{display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:700;min-width:0;overflow:hidden;text-shadow:0 1px 2px rgba(0,0,0,.35);white-space:nowrap;padding:0 4px}}
.likert-seg-sm{{font-size:10px;padding:0 2px}}
.likert-empty{{display:flex;align-items:center;justify-content:center;width:100%;font-size:12px;color:var(--muted);font-style:italic}}
.likert-fav{{display:inline-block;margin-top:10px;background:#DAEBFE;color:#005587;font-size:12px;font-weight:700;padding:4px 12px;border-radius:6px}}
blockquote{{margin:0 0 16px;padding:16px 20px;background:var(--panel);border-left:4px solid {UCLA_LIGHT_BLUE};border-radius:0 10px 10px 0;font-size:14px;color:#334155;line-height:1.6}}
blockquote:last-child{{margin-bottom:0}}
ul{{margin:12px 0 0;padding-left:22px}}
li{{margin:10px 0;font-size:15px;color:#374151;line-height:1.55}}
.muted{{color:var(--muted);font-weight:400;font-size:13px}}
.pill{{display:inline-block;font-size:12px;font-weight:700;padding:5px 14px;border-radius:999px;background:#DAEBFE;color:#005587;margin-top:10px}}
.subhead{{display:block;font-size:15px;font-weight:700;color:var(--dblue);margin:0 0 14px}}
.print-btn{{position:fixed;top:18px;right:18px;z-index:50;background:{UCLA_BLUE};color:#fff;border:none;border-radius:8px;padding:10px 18px;font-size:13px;font-weight:700;cursor:pointer;box-shadow:0 4px 14px rgba(0,59,92,.3)}}
footer{{margin-top:36px;text-align:center;color:var(--muted);font-size:12px;line-height:1.6}}
@media(max-width:760px){{
  .page{{padding:24px 18px 48px}}
  header{{padding:28px 24px}}
  header h1{{font-size:22px}}
  section{{padding:24px 22px}}
  .grid2,.sent-panel{{grid-template-columns:1fr}}
  .kpis{{grid-template-columns:repeat(2,1fr)}}
  .likert-legend{{grid-template-columns:repeat(2,1fr)}}
}}
@media print{{
  @page{{margin:16mm}}
  html,body{{background:#fff;font-size:13px}}
  *{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .print-btn{{display:none}}
  .page{{max-width:100%;padding:0}}
  section,header,.result-block{{box-shadow:none;break-inside:avoid}}
}}
"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(w['title'])} — Post-Survey Summary</title>
<style>{css}</style></head><body>
<button class="print-btn" onclick="window.print()">Save as PDF</button>
<div class="page">
<header>
  <p class="eyebrow">UCLA IEED · Teaching &amp; Learning Center · Spring 2026</p>
  <h1>{esc(w['title'])}</h1>
  <p class="sub">Post-workshop survey summary · {esc(w['modality'])}, {esc(w['date'])}</p>
  <span class="pill">{esc(w['series'])} Series</span>
  <div class="kpis">
    <div class="kpi"><span class="n">{n_finished}</span><span class="l">Completed responses</span></div>
    <div class="kpi"><span class="n">{rsvp}</span><span class="l">RSVPs</span></div>
    <div class="kpi"><span class="n">{resp_rate}%</span><span class="l">Response rate (n={n_finished}/{rsvp})</span></div>
    <div class="kpi"><span class="n">{pos_pct}%</span><span class="l">Positive (n={sent["pos"]}/{sent_total})</span></div>
    <div class="kpi"><span class="n">{avg_fav}%</span><span class="l">Avg favorable ({n_scale_q} Qs)</span></div>
  </div>
</header>

<section>
  <h2>Overview</h2>
  <div class="prose">
    <p>{overview}</p>
    <p>The session introduced frameworks for guiding students to reflect critically on AI use, with an emphasis on affective outcomes alongside technical skills. Participants explored card-based activities and resources for designing assignments that nurture ethical, engaged learners.</p>
  </div>
</section>

<section>
  <h2>Who participated</h2>
  <div class="prose">
    <p>{participant_blurb}</p>
    <p>Survey responses were anonymous. No personally identifying information is included in this summary.</p>
  </div>
</section>

<section>
  <h2>Survey results</h2>
  <p class="muted" style="margin:0 0 12px">Percent favorable = share of responses in the upper half of each rating scale. Each bar shows the full response distribution (stacked by scale point).</p>

  <div class="result-block">
    <h3>Overall sentiment</h3>
    <p class="hint">{sent_total} Likert-scale ratings from {n_scale_q} questions</p>
    <p style="margin:0 0 18px;font-size:14px;color:#374151;line-height:1.65">{sent_explainer}</p>
    <div class="sent-panel">
      {sent_donut}
      <div>
        <div class="sent-bar">{seg(pos_pct, SENT_POS)}{seg(neu_pct, SENT_NEU)}{seg(neg_pct, SENT_NEG)}</div>
        <div class="sent-key">
          <span><span class="sw" style="background:{SENT_POS}"></span>Positive {pos_pct}% (n={sent["pos"]})</span>
          <span><span class="sw" style="background:{SENT_NEU}"></span>Neutral {neu_pct}% (n={sent["neu"]})</span>
          <span><span class="sw" style="background:{SENT_NEG}"></span>Negative {neg_pct}% (n={sent["neg"]})</span>
        </div>
        <table class="sent-table">
          <thead><tr><th>Classification</th><th>Count (n)</th><th>Share</th></tr></thead>
          <tbody>
            <tr><td>Positive</td><td>{sent["pos"]}</td><td>{pos_pct}%</td></tr>
            <tr><td>Neutral</td><td>{sent["neu"]}</td><td>{neu_pct}%</td></tr>
            <tr><td>Negative</td><td>{sent["neg"]}</td><td>{neg_pct}%</td></tr>
            <tr><td><b>Total ratings</b></td><td><b>{sent_total}</b></td><td>100%</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="result-block">
    <h3>Workshop experience</h3>
    <p class="hint">Logistics, delivery, learning outcomes, and likelihood to recommend</p>
    {likert_legend}
    {experience_blocks}
  </div>

  <div class="result-block">
    <h3>AI assignment confidence</h3>
    <p class="hint">Self-reported readiness to design AI-integrated assignments</p>
    {likert_legend}
    {confidence_blocks}
  </div>

  <div class="result-block">
    <h3>Planned skill focus</h3>
    <p class="hint">Skills participants plan to support through AI-integrated assignment design</p>
    {likert_legend}
    {skill_blocks}
  </div>
</section>

<section>
  <h2>Suggestions</h2>
  <div class="grid2">
    <div>
      <span class="subhead">From participants</span>
      {sugg_items}
    </div>
    <div>
      <span class="subhead">Themes for next time</span>
      <ul>{synth_items}</ul>
    </div>
  </div>
</section>

<footer>Generated from Qualtrics post-survey export · UCLA TLC / IEED · Spring 2026<br>
Percent favorable = upper half of each rating scale.</footer>
</div></body></html>"""


def main():
    quarter = "Winter & Spring 2026"
    for series, fname in [
        ("Wellbeing", "Wellbeing_Series_Report.html"),
        ("Preparing to Teach", "Preparing-to-Teach_Series_Report.html"),
    ]:
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            f.write(build_report(series, quarter))
        print(f"wrote {fname}")
    one_pager = "Workshop_One_Pager_Report.html"
    with open(os.path.join(OUT, one_pager), "w", encoding="utf-8") as f:
        f.write(build_one_pager())
    print(f"wrote {one_pager}")


if __name__ == "__main__":
    main()
