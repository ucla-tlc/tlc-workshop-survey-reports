# TLC Workshop Post-Survey Reports

UCLA-branded HTML summary reports of participant post-survey feedback for the
Teaching & Learning Center (TLC) workshop series, Winter & Spring 2026.

Each report is a single, self-contained HTML file (no internet required to view)
with an executive summary, a clickable "at a glance" status grid, per-workshop
response visualizations, and verbatim participant comments.

## Reports

| Series | Report |
|---|---|
| Wellbeing | [Wellbeing_Series_Report.html](Summaries/Wellbeing_Series_Report.html) |
| Preparing to Teach | [Preparing-to-Teach_Series_Report.html](Summaries/Preparing-to-Teach_Series_Report.html) |

> GitHub displays these as source code rather than rendering them. To view a
> report as a webpage, open the file and click **Download raw file**, then open
> it in a browser (or open the local copy in `Summaries/`).

## Regenerating

The reports are generated from Qualtrics post-survey CSV exports:

```bash
python3 Summaries/generate_reports.py
```

## Data privacy

Raw survey exports are **intentionally excluded** from this repository (see
`.gitignore`) because they contain participant PII (IP addresses, geolocation,
and personal comments). Only the aggregated HTML reports and the generator
script are tracked here.
