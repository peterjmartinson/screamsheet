---
date: 2026-05-06
type: transcript
participants:
  - Peter (user)
  - Gemini (AI assistant)
topic: PDF layout quality control — Platypus templates, KeepTogether, and overflow handling
summary: >
  During a broader discussion about the screamsheet-dispatch system, Peter
  identifies recurring layout failures in the screamsheet PDF generator:
  unwanted page breaks, blank pages, and standings charts splitting across
  pages. The agreed solution is to migrate news sheets to Platypus flowing
  templates and wrap sports standings in KeepTogether containers. Overflow is
  managed by dynamically compressing the scores table (reducing padding/white
  space) that precedes the standings, rather than splitting the standings
  itself. The generator should attempt deterministic retries before flagging
  a layout failure; on failure it signals the caller but still produces a
  deliverable PDF.
tags:
  - layout
  - reportlab
  - platypus
  - keeptogether
  - overflow
  - quality-control
  - scores
  - standings
related-repo: screamsheet-dispatch
---

# PDF Layout Quality Control — Architecture Discussion (May 6, 2026)

**Participants:** Peter, Gemini  
**Context:** This excerpt is from a broader session on the screamsheet-dispatch architecture. The layout/QC portion — which belongs to this repo — is highlighted below. The full transcript (including the dispatch/runner discussion) is archived in the `screamsheet-dispatch` repo at `transcripts-and-emails/20260506_ScreamsheetRunnerDiscussion.md`.

---

## Key Exchange: Layout Problems and Solutions

**Peter (08:24):**
> So, yeah, I don't know. Those are my basic thoughts for the actual sending part, but then I need to get more robust quality control on the actual screen sheets. There's a couple problems that I need to address, and this will probably be straight from the screen sheet repository.
>
> So we use ReportLab, and sometimes when the text is a little bit long — I set it so that there's always a front and a back. Like for the news screamsheets, there's two articles in the front, two articles in the back. For the sports screamsheets, there's scores and standings in the front and then game summary and box score on the back.
>
> The problem is that almost every day, one of the screamsheets — one of the articles is a little too long — and there's an immediate page break after the title. The whole front of the page is blank and the actual articles start on the back. Or the next page will be too long, so one page looks normal and then the back is just a second white page, and then the third page will have the actual stories. Or the standings chart will get broken up — part of it's on the front, part of it's on the back.

**Gemini:**
> Before abandoning ReportLab completely, we should look into using Platypus templates. Instead of drawing text to fixed positions, you define frames, and the content flows naturally, automatically starting on the next page if needed.

**Peter:**
> Yes, that sounds great. I definitely want to do that for at the very least the news screamsheets.
> For the charts like baseball scores charts, I think we might need a different solution though — I need the charts to stay as charts. I can't just have them flowing from one column to another.

**Gemini (first attempt — rejected):**
> We could build in logic to check the chart's height and split it at a sensible point, like after a division's standings, and continue it on the back.

**Peter:**
> I don't really like that idea. Something like the standings chart needs to stay as one solid thing on one side.

**Gemini:**
> Got it. So for standings charts that simply cannot split, we'll use Platypus's `KeepTogether` function. That tells ReportLab to always keep the whole table together on a single page.

**Peter:**
> One other way we could handle this — if the standings has to overflow, instead of messing with the standings, we could mess with the scores which come above the standings chart. We could compress the scores so the padding in that table is not so big. There's a lot of white space in the scores part.

**Gemini:**
> That's a great idea. We can make the scores table more compact, reducing the white space and padding to shrink its vertical height. That gives the standings table more room on the page without splitting it.

---

## Agreed Design Decisions

| Concern | Decision |
|---------|----------|
| News sheet overflow | Migrate to Platypus `SimpleDocTemplate` with flowing frames — content flows naturally across front/back |
| Sports standings splitting | Wrap in `KeepTogether` — never split across pages |
| Overflow when standings won't fit | Dynamically compress scores table padding/white space to reclaim vertical space |
| Deterministic retry | Generator attempts layout with progressively tighter scores compression before declaring failure |
| On failure | Generator signals a layout warning to the caller; still produces and returns the PDF for delivery |
