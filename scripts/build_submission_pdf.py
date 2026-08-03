"""The whole submission as one PDF: cover, summary, and the eight points.

One file to attach rather than three. Kadin asked for eight things in a fixed
order, so the document keeps that order and numbers them — he should be able to
find any one of them without reading the rest.

Ink on paper throughout. An earlier draft put the dark artwork on a dark page
and, worse, never switched page template, so every page was painted black and
the whole file was unreadable while its extracted text looked perfect. Hence the
render check at the foot of this file: the pages are looked at, not just parsed.

The blank at section 8 prints as a yellow box on purpose. This document must not
be sent until the Kaggle Support line replaces it.
"""
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

OUT = Path(r"C:\Users\techa\Desktop\Providence-submission.pdf")
COVER = Path(r"C:\Users\techa\Desktop\il-est-ecrit\docs\cover.png")

INK = HexColor("#14140f")
DIM = HexColor("#5a564c")
FAINT = HexColor("#8b8578")
GOLD = HexColor("#8a6d24")
RULE = HexColor("#d8d3c6")
PANEL = HexColor("#f6f4ee")
WARN = HexColor("#fdf6e3")
WARN_EDGE = HexColor("#c9a227")

PAGE_W, PAGE_H = A4
MARGIN = 24 * mm

body = ParagraphStyle("body", fontName="Times-Roman", fontSize=10.6, leading=16.2,
                      textColor=INK, alignment=TA_JUSTIFY, spaceAfter=9)
S = {
    "body": body,
    "lead": ParagraphStyle("lead", parent=body, fontSize=11.6, leading=17.6,
                           textColor=HexColor("#2a2822"), spaceAfter=12),
    "h1": ParagraphStyle("h1", fontName="Times-Bold", fontSize=22, leading=25,
                         textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="Times-Italic", fontSize=11.5, leading=16,
                          textColor=DIM, spaceAfter=16),
    "num": ParagraphStyle("num", fontName="Helvetica-Bold", fontSize=8, leading=12,
                          textColor=GOLD, spaceBefore=16, spaceAfter=5, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Times-Bold", fontSize=10.8, leading=15,
                         textColor=INK, spaceBefore=9, spaceAfter=1, keepWithNext=1),
    "bullet": ParagraphStyle("bullet", parent=body, leftIndent=13, bulletIndent=2,
                             spaceAfter=6),
    "link": ParagraphStyle("link", fontName="Courier", fontSize=8.4, leading=13,
                           textColor=HexColor("#33507a"), spaceAfter=3, leftIndent=13),
    "cell": ParagraphStyle("cell", fontName="Times-Roman", fontSize=9, leading=12.8,
                           textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="Helvetica-Bold", fontSize=7,
                            leading=12, textColor=DIM),
    "warn": ParagraphStyle("warn", fontName="Helvetica", fontSize=8.6, leading=13.4,
                           textColor=HexColor("#6b5410")),
    "sig": ParagraphStyle("sig", fontName="Times-Roman", fontSize=10.6, leading=16,
                          textColor=INK, spaceBefore=14),
}


def draw_mark(c, cx, top, scale, colour=GOLD):
    x = lambda u: cx + (u - 12) * scale
    y = lambda u: top - (u - 3) * scale
    c.setStrokeColor(colour); c.setFillColor(colour); c.setLineCap(2)
    c.setLineWidth(2.2 * scale / 3); c.line(x(4), y(3), x(20), y(3))
    c.setLineWidth(1.54 * scale / 3); c.line(x(12), y(3), x(12), y(15))
    p = c.beginPath(); p.moveTo(x(12), y(15)); p.lineTo(x(16.2), y(18.4))
    p.lineTo(x(12), y(21.5)); p.lineTo(x(7.8), y(18.4)); p.close()
    c.drawPath(p, fill=1, stroke=0)


def cover_page(c, doc):
    """Ink on paper, with the artwork as a plate. The plate is what gives the
    dark image contrast; on a dark page the two disappear into each other."""
    c.saveState()

    mark_top = PAGE_H - 34 * mm
    draw_mark(c, MARGIN + 8, mark_top, 2.6, GOLD)
    c.setFillColor(GOLD)
    c.setFont("Helvetica", 7.6)
    # the beam reaches MARGIN+8+8*2.6 ≈ MARGIN+29, so the text clears at +42
    c.drawString(MARGIN + 42, mark_top - 30,
                 "SCRIPTURE IN NEW FRONTIERS  ·  YOUVERSION × GLOO")

    c.setFillColor(INK); c.setFont("Times-Bold", 46)
    c.drawString(MARGIN, PAGE_H - 72 * mm, "Providence")
    c.setFillColor(DIM); c.setFont("Times-Italic", 15)
    c.drawString(MARGIN, PAGE_H - 82 * mm, "A moral physics layer for game engines.")

    c.setStrokeColor(RULE); c.setLineWidth(0.6)
    c.line(MARGIN, PAGE_H - 89 * mm, PAGE_W - MARGIN, PAGE_H - 89 * mm)

    img_w = PAGE_W - 2 * MARGIN
    img_h = img_w * 9 / 16
    img_y = PAGE_H - 99 * mm - img_h
    c.drawImage(str(COVER), MARGIN, img_y, width=img_w, height=img_h, mask=None)
    c.setStrokeColor(HexColor("#c9c3b4")); c.setLineWidth(0.5)
    c.rect(MARGIN, img_y, img_w, img_h, fill=0, stroke=1)

    c.setFillColor(FAINT); c.setFont("Helvetica", 7)
    c.drawString(MARGIN, img_y - 13,
                 "The relations graph. Each edge carries the reference its rule comes from.")

    below = img_y - 34
    c.setFillColor(INK); c.setFont("Times-Roman", 13.5)
    c.drawString(MARGIN, below, "Your engine already knows where the body falls.")
    c.setFont("Times-Bold", 13.5)
    c.drawString(MARGIN, below - 19, "It has no idea what that costs.")

    c.setStrokeColor(RULE); c.setLineWidth(0.6)
    c.line(MARGIN, 32 * mm, PAGE_W - MARGIN, 32 * mm)
    c.setFillColor(DIM); c.setFont("Helvetica", 7.6)
    c.drawString(MARGIN, 26 * mm, "BRAYAN SORGHO  ·  SOLO ENTRANT")
    c.drawRightString(PAGE_W - MARGIN, 26 * mm, "providencenet.netlify.app")
    c.restoreState()


def furniture(c, doc):
    c.saveState()
    draw_mark(c, MARGIN + 4, PAGE_H - 15 * mm, 1.8)
    c.setFont("Helvetica", 7.2); c.setFillColor(FAINT)
    c.drawString(MARGIN + 15, PAGE_H - 19 * mm, "PROVIDENCE")
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 19 * mm,
                      "Alternative submission documentation  ·  Brayan Sorgho")
    c.setStrokeColor(RULE); c.setLineWidth(0.5)
    c.line(MARGIN, PAGE_H - 22 * mm, PAGE_W - MARGIN, PAGE_H - 22 * mm)
    c.setFillColor(FAINT)
    c.drawCentredString(PAGE_W / 2, 13 * mm, str(doc.page - 1))
    c.restoreState()


def facts_table():
    """What the reader needs before deciding whether to read on."""
    rows = [
        ("WHAT", "A library you put underneath a game engine. Not a game, not an engine."),
        ("THE GAP", "Engines compute where a body falls. None of them know what it costs."),
        ("SCALE", "24 NPC arcs · 10,000-character graph · 522 tests across 37 files"),
        ("YOUVERSION", "The only door text ever comes through. The engine stores zero verses."),
        ("GLOO", "Speaks the characters' words. Never quotes Scripture. Never decides."),
        ("LICENCE", "MIT, public, deployed and running."),
    ]
    data = [[Paragraph(k, S["cellh"]), Paragraph(v, S["cell"])] for k, v in rows]
    t = Table(data, colWidths=[26 * mm, PAGE_W - 2 * MARGIN - 26 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def p(t, s="body"):
    return Paragraph(t, S[s])


def bullet(t):
    return Paragraph(t, S["bullet"], bulletText="—")


def boxed(flowables, bg=PANEL, edge=RULE):
    t = Table([[flowables]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.5, edge),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return t


def timeline():
    rows = [
        ("WHEN (UTC)", "WHAT", "VS DEADLINE"),
        ("07-31 21:17:20", "Engine frozen — last commit touching src/providence/ (26ea4ad)", "7h42 before"),
        ("08-01 01:23:03", "Last commit touching any source at all (6791d96)", "3h36 before"),
        ("08-01 03:05", "Kaggle notebook v1 and v2 saved and executed (23s)", "1h54 before"),
        ("08-01 03:56:17", "Production deploy live on Netlify from 3e5eb5b", "1h03 before"),
        ("08-01 03:44 → 04:56", "Commits touching documentation only", "—"),
        ("08-01 04:59:00", "DEADLINE", ""),
        ("08-01 05:00:05", "YouTube stamps the video public", "65 seconds after"),
    ]
    data = []
    for i, (a, b, c) in enumerate(rows):
        st = "cellh" if i == 0 else "cell"
        bold = i == 6
        fmt = (lambda s: f"<b>{s}</b>") if bold else (lambda s: s)
        data.append([Paragraph(fmt(a), S[st]), Paragraph(fmt(b), S[st]),
                     Paragraph(fmt(c), S[st])])
    t = Table(data, colWidths=[34 * mm, PAGE_W - 2 * MARGIN - 34 * mm - 26 * mm, 26 * mm])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, HexColor("#e8e4d9")),
        ("LINEABOVE", (0, 6), (-1, 6), 0.6, GOLD),
        ("LINEBELOW", (0, 6), (-1, 6), 0.6, GOLD),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def story():
    s = [
        # the cover is drawn entirely in cover_page(); switch template or its
        # background paints every following page
        NextPageTemplate("text"), PageBreak(),

        p("ALTERNATIVE SUBMISSION DOCUMENTATION", "num"),
        p("Providence", "h1"),
        p("Scripture in New Frontiers · YouVersion × Gloo · Brayan Sorgho, solo entrant",
          "sub"),
        facts_table(),
        Spacer(1, 16),

        p("Hi Kadin,", "body"),
        p("Thank you for this, and for the care behind it. Everything my Kaggle "
          "submission would have contained follows, in the order you asked for it — "
          "title, description, team, video, repository, technical write-up, additional "
          "context, and the account issue.", "lead"),

        p("1 — PROJECT TITLE", "num"),
        p("Providence — a moral physics layer for game engines."),

        p("2 — PROJECT DESCRIPTION", "num"),
        p("Godot and Unity compute a falling body to a precision no human can match. "
          "Ask either what it costs when one character betrays another, and there is "
          "nothing there: to an engine, a murder and a handshake are the same event, a "
          "state change."),
        p("Every shipped game papers over this with a number per character, nudged up "
          "and down by events. That number cannot tell the difference between betraying "
          "a stranger and betraying someone you swore an oath to, however many lines you "
          "write around it."),
        p("Providence is the layer that can. It is not a game and not an engine — it is "
          "a library you put underneath one. And it puts Scripture into a game as "
          "physics rather than as a popup."),

        p("3 — TEAM MEMBERS", "num"),
        p("Brayan Sorgho. Solo entrant."),

        p("4 — VIDEO DEMO", "num"),
        p("https://youtu.be/tpELTRyyidk", "link"),
        p("Public, three minutes."),

        p("5 — CODE REPOSITORY AND WORKING PRODUCT", "num"),
        p("https://github.com/Sorghobrayan-dotcom/Providence", "link"),
        p("MIT-licensed. 522 tests across 37 files."),
        p("https://www.kaggle.com/code/brayansorgho/providence-a-moral-physics-layer-for-game-engine", "link"),
        p("The notebook is not a description of the engine. The laws are ported to "
          "Python and executed in front of the reader: press Run All and every claim the "
          "write-up makes prints its own proof, in 23 seconds, with numbers that match "
          "the TypeScript suite exactly."),
        p("https://providencenet.netlify.app", "link"),
        p("The working product. Live, no login, no paywall. Both API proxies run as "
          "Netlify edge functions, so no credential ever reaches the browser."),
    ]

    # ── 6 ───────────────────────────────────────────────────
    s += [
        p("6 — TECHNICAL WRITE-UP", "num"),
        p("<b>The problem.</b> Scripture appears in games, when it appears at all, as "
          "text on a screen — a collectible, a loading-screen quote, a menu the player "
          "dismisses. It is never load-bearing: nothing in the simulation would change "
          "if it were deleted. Providence asks the opposite question — what if the moral "
          "structure of the text were the physics the world runs on?"),

        p("Five parts", "h3"),
        bullet("<b>Souls.</b> 24 NPC arcs drawn from the text, because game characters "
               "never change and biblical ones do little else. Jonah flees the errand you "
               "just gave him. Peter denies you under pressure and cannot be bought back, "
               "only restored. Balaam's donkey overrules the player's own input."),
        bullet("<b>Relations.</b> A graph, because the question is not what one soul "
               "feels but what moves between them. Blessing, birthright, debt and "
               "grievance are property with transfer rules taken from the text. A debt "
               "does not evaporate when someone rescues you: it moves onto the redeemer "
               "at full cost, and only a kinsman may carry it. Nothing consults a "
               "reputation table, so betraying a stranger and betraying a sworn ally "
               "differ by exactly five."),
        bullet("<b>Standing.</b> What the player has done is public record rather than "
               "private mood. The same righteousness, read through 24 pairs of eyes, "
               "arrives as welcome on one face and dread on another."),
        bullet("<b>Drives and places.</b> Martha and Mary stand in one room, see the "
               "same interruption and do opposite things; neither arc mentions the other. "
               "A room presses on whoever is inside it, which is how a frightening place "
               "stops the donkey with no danger ever shown to it."),
        bullet("<b>Grace.</b> Specified in docs/grace.md before a line of it existed, "
               "because it must not be reachable. One draw per episode at 0.2, so four "
               "desperate moments in five receive nothing. No game code can call it, no "
               "parameter shapes it, and its rate moves with nothing the player did. A "
               "system that can be farmed for forgiveness is not modelling grace."),

        p("The YouVersion Platform API", "h3"),
        p("<b>Providence contains no verse text. Not one.</b> The engine stores "
          "references — book, chapter, verse — and the resolver is the only door text "
          "ever comes through, live, in the player's language."),
        p("That is an architectural constraint rather than an integration convenience. "
          "The engine cannot drift out of sync with Scripture, cannot ship a paraphrase "
          "by accident, and cannot present anything the platform did not serve. Every "
          "rule in the relations graph carries the reference it derives from, so a "
          "designer can be shown <i>why</i> a betrayal cost what it cost, with the "
          "passage attached. If the API is unreachable, the engine keeps running on its "
          "rules and shows the reference without the text — it degrades to silence, "
          "never to invention."),

        p("The Gloo AI Studio API", "h3"),
        p("Gloo gives the characters their voices. It does not give them their "
          "decisions, and the separation is enforced rather than merely intended."),
        p("The engine computes what a character will do from the relations graph, and "
          "only then does Gloo phrase it in that character's register. A proposal that "
          "violates the rules is discarded and the character stays silent. Where the "
          "engine genuinely cannot classify something, Gloo arbitrates in a fixed order: "
          "own rules first, the model only if still unsure, then a structural check on "
          "what came back. Every verdict is recorded with what the model decided and "
          "what the engine actually did, so the two can be audited against each other."),
        p("Gloo runs behind an OAuth2 client-credentials exchange, so a small middleware "
          "awaits a bearer token before forwarding anything; a token Gloo stops "
          "accepting is dropped from the cache rather than retried."),
    ]

    # ── 7 ───────────────────────────────────────────────────
    s += [
        p("7 — ADDITIONAL CONTEXT", "num"),
        p("Safeguards", "h3"),
        bullet("<b>Gloo never quotes Scripture.</b> Text reaches the player through "
               "YouVersion or not at all, which removes an entire class of failure — a "
               "model paraphrasing or inventing a verse — by construction rather than by "
               "prompt."),
        bullet("<b>Gloo never changes state.</b> It phrases; the engine decides. Any "
               "output implying a state change is discarded."),
        bullet("<b>Silence over invention.</b> Whenever the model or the API cannot "
               "produce something faithful, the character says nothing. Nothing is "
               "filled in."),
        bullet("<b>Refusal belongs to the character, never to the interface.</b> An "
               "option a character will not take is refused in their own voice rather "
               "than greyed out, so the player learns the moral shape of the world "
               "instead of bumping into a disabled button."),
        bullet("<b>Grace is unreachable from code</b> — it cannot be earned, bought or "
               "optimised toward."),

        p("Evaluation", "h3"),
        p("522 tests across 37 files. Ten thousand characters in the graph. A thousand "
          "headless runs per room. Same cast, same seed, palace against desert: Martha "
          "complains every time in one and settles in the other — the claim made "
          "falsifiable. The Godot add-on is run headless against a real engine, 41 "
          "assertions on Godot 4.7.1, because an add-on never loaded by the engine it "
          "targets is a claim rather than a feature."),

        p("What was hard", "h3"),
        p("Both of our worst problems were honesty problems. An early build shipped our "
          "own paraphrases beside the references — which reads as Scripture and is not, "
          "and is exactly the failure this project exists to avoid. The resolver became "
          "the only door as a direct result. And a character's memory was frozen at "
          "creation, so it reacted to a world that had already moved on; that looked "
          "like personality until it was traced."),

        p("Continued operation", "h3"),
        p("The repository is MIT-licensed and public, and the demo is deployed and stays "
          "up. The Godot add-on is the direction that matters most: Providence is useful "
          "to other developers only if it drops into an engine they already use."),
    ]

    # ── 8 ───────────────────────────────────────────────────
    s += [
        p("8 — THE KAGGLE ACCOUNT ISSUE", "num"),
        p("I want to be precise about what I know and careful not to claim more."),
        p("When I reached the point of submitting, the submission would not go through. "
          "<b>I did not know why.</b> I had no indication of an account problem before "
          "that moment — I had been working in Kaggle normally, and the public notebook "
          "linked above was saved and executed there at 03:05 UTC that same morning. I "
          "learned the account had been suspended only afterwards."),
        p("I emailed the organizers at <b>05:05 UTC on 1 August 2026</b>, six minutes "
          "after the deadline, before I understood the cause."),
        boxed([
            Paragraph("<b>BEFORE SENDING — replace this box.</b>", S["warn"]),
            Spacer(1, 4),
            Paragraph("Kadin asked specifically for the steps taken with Kaggle Support. "
                      "If a case is open, state the date, the reference, and their reply. "
                      "If not, open one first, then write it here. Leaving this line "
                      "unanswered is the only thing in this document that will read "
                      "badly.", S["warn"]),
        ], bg=WARN, edge=WARN_EDGE),
        Spacer(1, 12),

        p("The timeline", "h3"),
        p("The deadline was 2026-08-01 04:59:00 UTC. Every row below is independently "
          "verifiable from GitHub commit history, the notebook's own version history, "
          "the Netlify deploy log, and YouTube's uploadDate metadata — none of it "
          "requires taking my word."),
        Spacer(1, 4),
        timeline(),
        Spacer(1, 12),
        p("No engine code was written in the final hour. The project was finished, "
          "deployed and publicly running more than an hour before the deadline. The only "
          "element that landed late was the video, by 65 seconds, held in YouTube's HD "
          "processing queue — and the link would not validate in the Writeup form while "
          "that processing was still running."),
        p("Nothing has been modified since the deadline, and nothing will be. The commit "
          "history and the notebook version history will confirm that."),

        Spacer(1, 8),
        # the closing must not strand itself on a page of its own
        KeepTogether([
            p("I understand you cannot promise this replaces a Kaggle submission, and I "
              "am grateful you are documenting it either way. If it would help to see "
              "the engine running rather than read about it, I am glad to walk you "
              "through it live at whatever time suits you.", "lead"),
            p("Thank you for your time,", "sig"),
            p("<b>Brayan Sorgho</b>", "sig"),
        ]),
    ]
    return s


def main():
    doc = BaseDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=29 * mm, bottomMargin=20 * mm,
        title="Providence — alternative submission documentation",
        author="Brayan Sorgho",
        subject="Scripture in New Frontiers — reply to Gloo",
    )
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[Frame(0, 0, PAGE_W, 10, id="c")],
                     onPage=cover_page),
        PageTemplate(id="text",
                     frames=[Frame(MARGIN, 19 * mm, PAGE_W - 2 * MARGIN,
                                   PAGE_H - 50 * mm, id="f")],
                     onPage=furniture),
    ])
    doc.build(story())
    print(f"{OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    verify()


def verify() -> None:
    """Look at the pages, do not merely parse them.

    Extracted text reads perfectly from a page of black ink on a black ground,
    which is exactly how the unreadable draft passed two checks.
    """
    import statistics

    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(OUT))
    print(f"  {len(doc)} pages")
    for i in range(len(doc)):
        page = doc[i]
        lum = statistics.mean(page.render(scale=0.5).to_pil().convert("L").getdata())
        chars = len((page.get_textpage().get_text_range() or "").strip())
        flag = ""
        if i == 0:
            flag = "  (cover)"
        elif lum < 200:
            flag = "  <-- DARK PAGE"
        elif chars < 400 and i < len(doc) - 1:
            flag = "  <-- THIN"
        print(f"  p{i}: {lum:3.0f}/255 luminance, {chars:5d} chars{flag}")


if __name__ == "__main__":
    main()
