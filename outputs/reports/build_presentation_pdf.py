"""Generate the presentation briefing PDF for the 60-DTE IV RV desk."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent / "60DTE_IV_Relative_Value_Briefing.pdf"

NAVY = colors.HexColor("#1b2838")
ACCENT = colors.HexColor("#2b5d8a")
RULE = colors.HexColor("#c5d0da")
ROW = colors.HexColor("#f4f7fa")
MUTED = colors.HexColor("#4a5560")
GREEN = colors.HexColor("#1f7a4d")
RED = colors.HexColor("#b23b32")
GOLD = colors.HexColor("#8a6d12")


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover_kicker": ParagraphStyle(
            "cover_kicker", parent=base["Normal"], fontName="Times-Bold",
            fontSize=11, textColor=ACCENT, letterSpacing=1.2, alignment=TA_CENTER, spaceAfter=8,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontName="Times-Bold",
            fontSize=22, leading=26, textColor=NAVY, alignment=TA_CENTER, spaceAfter=10,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontName="Times-Italic",
            fontSize=12, leading=16, textColor=MUTED, alignment=TA_CENTER, spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Times-Bold",
            fontSize=15, leading=19, textColor=NAVY, spaceBefore=14, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Times-Bold",
            fontSize=12.5, leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Times-Roman",
            fontSize=10, leading=14, textColor=NAVY, alignment=TA_JUSTIFY, spaceAfter=7,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Times-Roman",
            fontSize=10, leading=13.5, textColor=NAVY, leftIndent=8, spaceAfter=2,
        ),
        "note": ParagraphStyle(
            "note", parent=base["Normal"], fontName="Times-Italic",
            fontSize=9.5, leading=13, textColor=MUTED, alignment=TA_JUSTIFY, spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], fontName="Times-Italic",
            fontSize=8.5, leading=11, textColor=MUTED, alignment=TA_CENTER, spaceBefore=2, spaceAfter=10,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontName="Times-Roman",
            fontSize=8, textColor=MUTED, alignment=TA_CENTER,
        ),
        "mono": ParagraphStyle(
            "mono", parent=base["Code"], fontName="Courier",
            fontSize=8, leading=11, textColor=NAVY, backColor=ROW, leftIndent=4, rightIndent=4,
            spaceBefore=4, spaceAfter=8,
        ),
        "th": ParagraphStyle("th", parent=base["Normal"], fontName="Times-Bold", fontSize=8, leading=11, textColor=colors.white),
        "td": ParagraphStyle("td", parent=base["Normal"], fontName="Times-Roman", fontSize=8, leading=11, textColor=NAVY),
    }
    return s


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
    canvas.setFont("Times-Italic", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, A4[1] - 10 * mm, "60-DTE IV relative-value desk  ·  presentation briefing")
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 10 * mm, "Holdout frozen 11 Sep 2026")
    canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
    canvas.drawString(18 * mm, 8 * mm, "Internal research note. Not a live trading recommendation.")
    canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def P(text, st):
    return Paragraph(text, st)


def bullets(items, st):
    return ListFlowable(
        [ListItem(Paragraph(x, st["bullet"]), leftIndent=12) for x in items],
        bulletType="bullet",
        start="•",
        leftIndent=16,
        spaceAfter=8,
    )


def table(headers, rows, st, col_widths=None):
    head = [Paragraph(h, st["th"]) for h in headers]
    body = [[Paragraph(str(c), st["td"]) for c in r] for r in rows]
    t = Table([head] + body, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW]),
                ("GRID", (0, 0), (-1, -1), 0.3, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def build():
    st = styles()
    story = []

    story += [
        Spacer(1, 28 * mm),
        P("RESEARCH BRIEFING  ·  FOR PRESENTATION", st["cover_kicker"]),
        P("How the 60-DTE implied-volatility<br/>relative-value model works", st["cover_title"]),
        P(
            "A walk-through of the data, smile models, residual, z-gate, "
            "TRADE / NO TRADE / CANNOT DECIDE rule, and how fair those calls really are.",
            st["cover_sub"],
        ),
        Spacer(1, 8 * mm),
        table(
            ["Item", "Value"],
            [
                ["Research / train / tune", "2025-06-05 → 2026-09-08"],
                ["Unused gap", "2026-09-09 and 2026-09-10"],
                ["Frozen holdout", "2026-09-11 (signals only, no retuning)"],
                ["Target tenor", "Nearest single expiry to 60 calendar DTE"],
                ["Frozen production gate", "z = 3.0 on the 60-day residual"],
                ["Dashboard", "https://snp-60dte-iv-desk.vercel.app"],
                ["Repo", "github.com/Ayushkumarsingh09/snp-60dte-iv-relative-value"],
            ],
            st,
            [55 * mm, 115 * mm],
        ),
        Spacer(1, 8 * mm),
        P(
            "One-line thesis: cheap is not low IV, and cheap is not “below SVI”. "
            "A trade is only a residual that is historically extreme, agrees with its own sign, "
            "is not extrapolated, and still looks small versus costs. On a quiet day the honest answer is NO TRADE.",
            st["note"],
        ),
        PageBreak(),
    ]

    # 1
    story += [
        P("1. What this project is — and is not", st["h1"]),
        P(
            "This is a research engine and a static desk for <b>relative-value on a single ~60-day implied-volatility slice</b> "
            "of SNP / S&amp;P-like option chains. Each trading day we take the last snapshot, pick the expiry nearest to 60 DTE, "
            "fit several smiles, measure how the market differs from a fair smile, standardise that difference against the "
            "structure’s own history, and then decide <b>TRADE</b>, <b>NO TRADE</b>, or <b>CANNOT DECIDE</b>.",
            st["body"],
        ),
        P("The objective is predictive relative value, not a pretty surface.", st["h2"]),
        P(
            "A smile that interpolates every listed strike with a tiny RMSE can still be useless for trading. "
            "SVI has the lowest in-sample IV RMSE (~0.47 vol points) but that is <i>not</i> why we use it. "
            "We care whether a residual today tells us anything about residual change over the next few days, "
            "and whether that change is large enough to survive a conservative cost model.",
            st["body"],
        ),
        bullets(
            [
                "<b>It is</b> a causal, walk-forward, holdout-protected study of 60-DTE IV residuals and structures.",
                "<b>It is</b> a dashboard that can score any RR, butterfly, slope, delta-point or listed strike.",
                "<b>It is not</b> a live execution system. There is no bid/ask, volume or open interest in the files.",
                "<b>It is not</b> a claim that 11 Sep 2026 had a trade. The frozen book said NO TRADE.",
                "<b>It is not</b> a calendar-consistent SSVI surface. One maturity cannot identify that.",
            ],
            st,
        ),
        P("The three sentences you can say in a meeting", st["h2"]),
        bullets(
            [
                "We compare market IV (or a structure built from it) to an ensemble fair value, not to a single parametric smile.",
                "We only call TRADE when that residual is historically extreme at a frozen z-gate of 3.0 and the signs agree.",
                "Residuals do mean-revert a little (5-day correlation about −0.44), but the typical size is 1–10 basis points of vol and does not survive modelled costs.",
            ],
            st,
        ),
    ]

    # 2
    story += [
        P("2. Research calendar — how we stop ourselves cheating", st["h1"]),
        P(
            "Every threshold, feature and model choice was locked on data through 8 September 2026. "
            "The holdout day is used only to <i>apply</i> the frozen rule. Later dates may score that decision; they must not reopen the gate.",
            st["body"],
        ),
        table(
            ["Window", "Dates", "Allowed use"],
            [
                ["Research", "2025-06-05 … 2026-09-08", "Fit smiles, compute z, choose gate, train ML, backtest"],
                ["Gap", "2026-09-09, 2026-09-10", "Present on disk; unused for train or tune"],
                ["Holdout", "2026-09-11", "Generate signals with the frozen rule only"],
                ["After test", "2026-09-14 onward", "Score the frozen NO TRADE / TRADE call"],
            ],
            st,
            [32 * mm, 52 * mm, 86 * mm],
        ),
        P("Figure-style reminder: 11 Sep 2026 must never change the gate.", st["caption"]),
        P(
            "Walk-forward inside the research window uses expanding training, ~20-day validation blocks, and a 5-day embargo so that a residual used as a feature is not paired with a label that leaked from the next fold. "
            "There are no random train/test splits.",
            st["body"],
        ),
    ]

    # 3
    story += [
        P("3. What the data actually is", st["h1"]),
        P(
            "324 daily parquet files, weekdays only, 2025-06-05 to 2026-09-22. A typical file has ~12,000–13,000 rows, hourly stamps 09:00–16:00, ~43 expiries and ~80–90 strikes. "
            "We inspected the files first; we did not trust the brief when the files disagreed.",
            st["body"],
        ),
        table(
            ["Field / fact", "What we found and what we do"],
            [
                ["Column name", "Files say <b>contract</b>, not contact."],
                ["Snapshot", "Last timestamp of the day, usually 16:00. Early closes keep the last print."],
                ["rate", "Identically 0. Using F = S·e<sup>rT</sup> would give F = S, which is wrong."],
                ["Forward", "Put-call parity near ATM: F = median(K + C − P). Discount factor = 1."],
                ["Underlying", "Treated as spot. PCP carry is ~30–40 index points at ~57 DTE."],
                ["IV units", "Decimal (0.16 = 16%). Vendor IV kept after a BS reconstruction audit."],
                ["put_delta", "Unsigned to 2026-07-15, signed after. Engine always uses abs(put_delta)."],
                ["atm", "Integer strike offset (0 = closest listed strike), not a boolean."],
                ["DTE", "Calendar days. Exact DTE = 60 on only 36/317 research+test days."],
                ["Missing", "No bid, ask, volume, OI, dividends or event calendar."],
            ],
            st,
            [38 * mm, 132 * mm],
        ),
        P(
            "Cleaning is logged, not silent: IV bounds 2%–150%, minimum 8 usable strikes, reconstruction audit on selected days. "
            "Across snapshots, 517,395 rows were seen, 504,690 kept, 12,705 removed. "
            "Call IV reconstruction MAE median is about 0.46 vol points on audit days — close enough in the centre, worse in the wings, which we filter.",
            st["body"],
        ),
    ]

    # 4
    story += [
        P("4. Building one day’s 60-DTE surface", st["h1"]),
        P("Step-by-step for every date t", st["h2"]),
        bullets(
            [
                "Load the parquet for date t and keep the last snapshot.",
                "Clean the full chain and record every drop.",
                "Select <b>one</b> expiry: exact 60 if it exists, otherwise the nearest expiry to 60. Never mix expiries across strikes. Mean |DTE−60| ≈ 2.85 days, max 8.",
                "Infer the PCP forward near ATM.",
                "Year-fraction T = DTE / 365. Log-moneyness k = ln(K / F).",
                "OTM IV rule: K &lt; F uses put IV; K &gt; F uses call IV; |k| &lt; 0.01 blends them.",
                "Build total variance w = IV² T. That is what SVI / SSVI / the polynomial actually fit.",
                "Fit five smiles. Fair IV is the <b>median</b> of the five. Residual = market IV − ensemble fair IV.",
                "Interpolate a delta grid and build structures (RR, BF, slopes, points, verticals, listed strikes).",
                "Update rolling z-scores using only dates ≤ t.",
            ],
            st,
        ),
        P(
            "On 11 Sep 2026 this produces: snapshot 16:00, expiry 2026-11-05 (OWSNP1EX26), actual DTE 56, spot 7661, PCP forward ≈ 7700, ATM IV 13.45%, 25-delta risk reversal −5.14 vol points.",
            st["body"],
        ),
    ]

    # 5
    story += [
        P("5. The five smile models and the ensemble", st["h1"]),
        P(
            "Each model is a different opinion of “what a 60-DTE smile should look like”. "
            "A large residual where they agree is more interesting than a large residual where they fight.",
            st["body"],
        ),
        table(
            ["Method", "What it fits", "Role"],
            [
                ["Quadratic polynomial", "Total variance vs k: w(k) ≈ a + b k + c k²", "Smooth global parabola; weak in the wings."],
                ["Smoothing spline", "Flexible w(k) or IV(k), vega-weighted", "Local shape; can overfit noise."],
                ["SVI (Gatheral)", "w(k) = a + b{ρ(k−m) + √((k−m)²+σ²)}", "Best in-sample RMSE (~0.00047). Still not the decision rule."],
                ["SSVI slice", "θ, ρ, φ on a single maturity", "Arbitrage-aware slice. Cannot be a full calendar SSVI here."],
                ["SABR, β = 1", "α, ρ, ν on IV(K) at fixed T", "Lognormal backbone; good near ATM, stylised wings."],
                ["Ensemble", "Median of the five fair IVs", "The official fair value. Dispersion = cross-model standard deviation."],
            ],
            st,
            [38 * mm, 72 * mm, 60 * mm],
        ),
        P(
            "Weights for the fits are vega by default (liquidity and hybrid weights exist). "
            "Previous-day SVI parameters warm-start the next research day, but the holdout day does not inherit a non-research initialisation. "
            "In-sample RMSE ranking is SVI &lt; SABR &lt; spline &lt; SSVI &lt; polynomial. We ignore that ranking when deciding trades.",
            st["body"],
        ),
        P("Residual — the central object", st["h2"]),
        Preformatted(
            "  residual  =  market_value  −  ensemble_fair_value\n"
            "  For a strike:   residual = market_IV − median(poly, spline, SVI, SSVI, SABR)\n"
            "  For 25D RR:     residual = (IV_25C − IV_25P)_mkt  −  (IV_25C − IV_25P)_fair",
            st["mono"],
        ),
        P(
            "Sign convention: residual &lt; 0 means the market is <b>cheap versus the ensemble</b> (below fair). "
            "Residual &gt; 0 means <b>expensive versus the ensemble</b>. "
            "That is only Definition 1. It is not yet a trade.",
            st["body"],
        ),
    ]

    # 6
    story += [
        P("6. Structures the model can talk about", st["h1"]),
        P(
            "A structure is any repeatable combination of smile points. Raw strike 7700 is not a time series — the forward moves — so listed-strike history is mapped to a log-moneyness bin of width 0.02.",
            st["body"],
        ),
        P("Research-period book (pipeline)", st["h2"]),
        bullets(
            [
                "ATM IV level.",
                "Risk reversals RR_d = IV_dC − IV_dP at 10 / 15 / 20 / 25 / 30 delta.",
                "Butterflies BF_d = ½(IV_dP + IV_dC) − IV_ATM at the same deltas.",
                "Put / call skew vs ATM.",
                "Slopes ATM → wing (sometimes scaled by delta gap).",
                "Call and put verticals at pairs (25/15, 30/20, 20/10, 25/10, 40/25).",
                "Wing curvature and left–right asymmetry.",
            ],
            st,
        ),
        P("Expanded dashboard book (gate not retuned)", st["h2"]),
        bullets(
            [
                "RR and BF at 5 / 10 / 15 / 20 / 25 / 30 / 35 / 40 / 45 delta.",
                "Delta points: ATM plus each put and call node (POINT_25P, POINT_25C, …).",
                "Slopes: ATM → every wing, and every far-minus-near pair on each wing.",
                "Listed strikes STRIKE_K, with z taken from KBIN of k = ln(K/F).",
                "The k-bins themselves.",
            ],
            st,
        ),
        P(
            "That expansion was built from the already-saved surfaces. Smiles were not refit and 3.0 was not retuned. "
            "The point was to stop missing a name the old 46-structure book never looked at. "
            "On 11 Sep 2026 the expanded book still has zero TRADE at the frozen gate.",
            st["body"],
        ),
        table(
            ["Kind", "Named count", "What residual means"],
            [
                ["Risk reversal", "9", "Skew vs the ensemble skew"],
                ["Butterfly", "9", "Smile convexity vs ensemble convexity"],
                ["Delta point", "19", "That node’s IV vs ensemble IV"],
                ["Slope", "90", "Wing-minus-belly (or ATM) vs ensemble"],
                ["k-bin", "14", "Average residual in a moneyness bucket"],
                ["Listed strike", "varies by day", "That K’s IV; history from its k-bin"],
            ],
            st,
            [38 * mm, 32 * mm, 100 * mm],
        ),
        P("Named catalog on the live desk is 141 structures plus listed strikes each day.", st["caption"]),
    ]

    # 7
    story += [
        P("7. Historical z — how “unusual” is measured", st["h1"]),
        P(
            "A 3 basis-point residual can be huge for a quiet butterfly and noise for a wild wing. "
            "So each structure is standardised against <b>its own past</b>, using only dates ≤ t.",
            st["body"],
        ),
        Preformatted(
            "  z_w(t)  =  [ residual(t)  −  mean(residual over the last w days, including t) ]\n"
            "              /  std(residual over the same window)\n"
            "  Windows w ∈ {20, 60, 120, 252} trading days.\n"
            "  The official gate uses z_60.",
            st["mono"],
        ),
        P(
            "Minimum periods are capped so a 20-day window does not demand 20+ observations before it exists. "
            "Percentile rank in the same window is stored as a second view. "
            "We also z-score the raw market value (the level), but the trade rule uses the <b>residual</b> z. "
            "A high ATM IV is a regime fact, not a cheap/expensive call.",
            st["body"],
        ),
        P(
            "For listed strikes the time series is the k-bin, not the integer K. "
            "Otherwise a 6600 strike would “look cheap” simply because spot has rallied and that K is now a deep put.",
            st["body"],
        ),
    ]

    # 8
    story += [
        P("8. Ten definitions of cheap / expensive — none is a trade by itself", st["h1"]),
        P(
            "The research engine attaches many definitions so a reviewer can see <i>why</i> something looks odd. "
            "The dashboard still shows those votes as cards. The frozen decision is stricter than any single card.",
            st["body"],
        ),
        table(
            ["#", "Definition", "Meaning"],
            [
                ["1", "Structural", "Sign of residual vs ensemble. Market below fair → cheap."],
                ["2", "Historical residual z", "Is this residual unusual vs this name’s last 60 days?"],
                ["3", "Relative to surface", "Neighbour / local residual, not just the point in isolation."],
                ["4", "Relative to delta", "Same structure historically (the z series)."],
                ["5", "Skew", "RR or put/call skew residual."],
                ["6", "Curvature", "Butterfly / wing-curvature residual."],
                ["7", "Regime", "High/low ATM IV; RV vs IV. Event premium proxy only."],
                ["8", "Event-adjusted", "No calendar in the files; RV / IV−RV stands in."],
                ["9", "Liquidity-adjusted", "Residual shrunk when the vega/liquidity score is poor."],
                ["10", "Executable", "Residual after a modelled half-spread. No real bid/ask."],
            ],
            st,
            [12 * mm, 42 * mm, 116 * mm],
        ),
        P(
            "Agreement matters. Structural cheap + historically cheap is a candidate. "
            "Structural cheap + historically normal is “a small residual on a quiet name”. "
            "Structural cheap + historically expensive is a contradiction → CANNOT DECIDE.",
            st["body"],
        ),
    ]

    # 9
    story += [
        P("9. How the gate value 3.0 was decided", st["h1"]),
        P(
            "The gate g is the number of residual standard deviations required before we are willing to speak. "
            "Candidates tested <b>only inside walk-forward validation</b>: 1.0, 1.5, 2.0, 2.5, 3.0. "
            "The holdout was not allowed to vote.",
            st["body"],
        ),
        P("Selection rule (exact)", st["h2"]),
        bullets(
            [
                "For each candidate g, keep validation rows with |z_60| ≥ g and at least 30 observations.",
                "Score = mean 5-day residual convergence on those rows. Convergence is −sign(residual) × future residual change, i.e. “did the residual shrink in the fade direction?”",
                "Pick the g with the highest mean convergence. That winner is <b>3.0</b>, mean convergence ≈ 0.0013 (about 0.13 vol points).",
                "Then freeze g. Refit the ridge / logistic models on all research dates. Never touch g after reading 11 Sep.",
            ],
            st,
        ),
        P("Is 3.0 “fair”?", st["h2"]),
        P(
            "Fair in the statistical sense: it was the walk-forward winner for <i>mean convergence given that you actually got a signal</i>. "
            "At |z| ≥ 3 the research-period signalled book had about 96% residual-convergence hit rate. "
            "That sounds excellent until you look at two other facts.",
            st["body"],
        ),
        bullets(
            [
                "<b>Sample collapse.</b> Moving from 1.5 to 3.0 throws most days away. The original research book had only ~92 signalled rows (99 labelled) at 3.0. RR_25D alone had about 6 days. High hit rate on a tiny, selected sample is not the same as a robust strategy.",
                "<b>Economic size is small.</b> 0.13 vol points of mean fade is real statistically and tiny versus a 0.20 vol-point modelled IV half-spread plus price half-spreads that grow in the wings.",
                "<b>Cost-adjusted P&amp;L is negative.</b> Mid-price fade can look positive; the conservative executable P&amp;L does not. That is why NO TRADE is a first-class output.",
                "<b>1.5 remains an analysis slider</b> on the dashboard so you can inspect milder dislocations without pretending they cleared the frozen book.",
            ],
            st,
        ),
        P(
            "A lower gate would be “fairer” if the goal were more conversation and more false positives. "
            "A higher gate would be “fairer” if the goal were almost never to speak. "
            "3.0 is the research compromise: speak rarely, and only when the residual is historically extreme. "
            "It is not a proof that 3.0 will win on the next sample.",
            st["body"],
        ),
        table(
            ["Gate", "What you get", "What you pay"],
            [
                ["1.0", "Many flags, noisy", "Mostly ordinary residuals; weak as a book"],
                ["1.5 analysis", "More names to inspect", "Not the frozen production rule"],
                ["2.0–2.5", "Middle ground", "Still a lot of small edges vs costs"],
                ["3.0 frozen", "Highest val mean-convergence, ~96% hit on the few signals", "n collapses; exec P&amp;L still negative"],
            ],
            st,
            [32 * mm, 68 * mm, 70 * mm],
        ),
    ]

    # 10
    story += [
        P("10. How a decision is made today", st["h1"]),
        P("Dashboard rule (what you see on Vercel)", st["h2"]),
        P(
            "This is the rule the live desk uses. It does not retune anything. Changing the z-gate slider only re-applies the same logic.",
            st["body"],
        ),
        Preformatted(
            "  Let R = residual,  z = z_60 of that residual.\n"
            "\n"
            "  CANNOT DECIDE  if any of:\n"
            "      • z is missing (not enough history)\n"
            "      • R is missing\n"
            "      • the delta point was extrapolated more than 0.03\n"
            "      • sign(R) and sign(z) conflict\n"
            "\n"
            "  NO TRADE       if the reading is clean but |z| < gate\n"
            "\n"
            "  TRADE          if |z| ≥ gate  and  sign(R) = sign(z)\n"
            "                   and not extrapolated\n"
            "      direction: CHEAP if R < 0, EXPENSIVE if R > 0\n"
            "      intended action: fade (buy cheap / sell expensive residual)",
            st["mono"],
        ),
        P("Worked example — 25-delta risk reversal on 11 Sep 2026", st["h2"]),
        table(
            ["Step", "Number"],
            [
                ["Expiry / DTE / forward", "2026-11-05 · 56 DTE · F ≈ 7699.96"],
                ["IV 25-delta call / put", "0.115918 / 0.167339"],
                ["Market RR = IV_C − IV_P", "−0.051421  (−5.14 vol points)"],
                ["Ensemble fair RR", "−0.051769"],
                ["Residual R", "+0.000348  (about +3.5 bp of vol)"],
                ["z_60", "+0.18"],
                ["Signs", "R > 0 and z > 0 — they agree, so not a conflict"],
                ["|z| vs gate 3.0", "0.18 ≪ 3  →  NO TRADE"],
                ["Plain English", "Slightly expensive vs the smile, historically ordinary"],
            ],
            st,
            [70 * mm, 100 * mm],
        ),
        P(
            "A forced ranking by raw residual would have invented a “best” name. The historical rule correctly refuses. "
            "On the expanded book the largest named |z| that day is about 1.38 (POINT_15P). Still NO TRADE.",
            st["body"],
        ),
        P("Research-engine extras (stricter live-book filter)", st["h2"]),
        P(
            "The pipeline’s decide_trade can also refuse a name that cleared the z-gate if model dispersion &gt; 3 vol points, liquidity score &lt; 0.25, predicted convergence probability &lt; 0.5, or predicted edge after costs ≤ 0. "
            "Those filters matter on days that <i>do</i> clear |z| ≥ 3. On 11 Sep nothing reached the gate, so they never came into play.",
            st["body"],
        ),
    ]

    # 11
    story += [
        P("11. Predictive models — used as a check, not as the judge", st["h1"]),
        P(
            "Walk-forward models try to forecast 5-day residual convergence from features known at t. "
            "Primary model: Ridge (standardised features). Secondary: logistic regression for P(convergence &gt; 0). "
            "Elastic net, random forest and gradient boosting exist in the library but the frozen pair is ridge + logreg.",
            st["body"],
        ),
        P("Features (only those present, never future IV or future RV)", st["h2"]),
        bullets(
            [
                "residual, price residual, z_20 / z_60 / z_120 of residual and of market level",
                "model dispersion, confidence = |residual| / dispersion, liquidity score",
                "actual DTE, |DTE−60|",
                "ATM IV, RV_20, RV_60, IV−RV_20",
                "spot return 5d / 20d, 20-day drawdown",
            ],
            st,
        ),
        P(
            "Out-of-sample information coefficient flipped sign across folds (−0.17 to +0.16). Sign-hit ranged 47%–75%. "
            "There is <b>not</b> a stable mapping from the feature list to residual change. "
            "That is an independent reason the desk is allowed to say NO TRADE even when a residual is non-zero.",
            st["body"],
        ),
    ]

    # 12
    story += [
        P("12. What the backtest actually showed", st["h1"]),
        P(
            "Horizon is 5 trading days. “Convergence hit” means the residual moved in the fade direction. "
            "Executable P&amp;L uses modelled half-spreads (about 0.50 price points near ATM, plus up to 1.50 extra in the wings, and 0.20 vol points of IV spread) because the files have no bid/ask.",
            st["body"],
        ),
        table(
            ["Book", "n with P&amp;L", "Conv. hit", "Mean conv.", "Exec. hit", "Mean exec P&amp;L"],
            [
                ["All structures", "9,167", "63%", "+1.9 bp vol", "31%", "negative"],
                ["Signalled |z|≥3", "80", "96%", "+14 bp vol", "53%", "still negative"],
                ["Risk reversals", "1,465", "65%", "+2.1 bp vol", "~0%", "negative"],
                ["Butterflies", "1,465", "62%", "+1.7 bp vol", "52%", "least-bad, Sharpe ~0.08"],
                ["Verticals signalled", "12", "100%", "+12 bp vol", "0%", "negative"],
            ],
            st,
            [38 * mm, 26 * mm, 24 * mm, 28 * mm, 24 * mm, 30 * mm],
        ),
        P(
            "Read this table as: statistics can be right and the trade still not be worth doing. "
            "Butterflies were the least-bad package in-sample. That is not a robustness claim.",
            st["note"],
        ),
        P(
            "On the expanded universe, using the same frozen 3.0 and no retune, there are 501 TRADE rows across 102 research dates "
            "(230 slopes, 140 listed-strike prints, 69 points, 31 RR, 27 BF, 4 k-bins). "
            "So the old 46-name book <i>was</i> missing names. The holdout still has none.",
            st["body"],
        ),
    ]

    # 13
    story += [
        P("13. How fair / correct is this? An honest scorecard", st["h1"]),
        P(
            "“Correct” has to be split. A model can be correct as a <b>description of residuals</b>, correct as a "
            "<b>forecast of fade</b>, and still be incorrect as a <b>money machine</b>.",
            st["body"],
        ),
        table(
            ["Question", "Verdict", "Evidence"],
            [
                ["Is the surface construction honest?", "Yes", "PCP forward, abs(delta), OTM IV, logged cleaning, one expiry."],
                ["Is “fair IV” a unique truth?", "No", "Five models; we take the median. Dispersion is shown, not hidden."],
                ["Do residuals mean-revert?", "Weakly yes", "corr(R, ΔR_5d) = −0.44. Size is small."],
                ["Does |z|≥3 pick better fades?", "Yes, in-sample", "Hit ~96% vs ~63% unfiltered. n is small."],
                ["Is 3.0 the only fair gate?", "No", "It won one walk-forward score. 1.5 is for inspection."],
                ["Does the ML add a stable edge?", "No", "IC changes sign by fold."],
                ["Do trades survive costs?", "Not shown", "Modelled exec P&amp;L negative. No real bid/ask."],
                ["Was 11 Sep handled correctly?", "Yes, given the rule", "Largest |z| ~1.2–1.4. Gate 3.0 → NO TRADE."],
                ["Did we overfit the holdout?", "Protected", "Gap days unused; holdout not used to pick g."],
                ["Multiple testing?", "A real risk", "Many names × horizons × gates. Holdout is the main brake."],
            ],
            st,
            [48 * mm, 32 * mm, 90 * mm],
        ),
        P("What you should say if someone asks “how confident are you?”", st["h2"]),
        bullets(
            [
                "Confident that 11 Sep 2026 was not an extreme residual day versus this history.",
                "Confident that “below SVI” is not a trade on this slice — almost every strike is close to the smiles.",
                "Moderately confident that large residuals fade a few basis points of vol over five days.",
                "Not confident that fading them makes money after spreads.",
                "Not confident the same gate or the same names will win on the next year of data.",
            ],
            st,
        ),
        P(
            "If the presentation needs a single number for “how correct”: treat the <b>direction of extreme residuals</b> as the supported claim (~high 60s% unfiltered, ~90s% at |z|≥3 in-sample) and treat <b>P&amp;L</b> as unsupported. "
            "That is a more honest slide than a Sharpe.",
            st["body"],
        ),
    ]

    # 14
    story += [
        P("14. Complete catalogue of methods used", st["h1"]),
        P("A. Data and surface", st["h2"]),
        bullets(
            [
                "Last-print daily snapshot; calendar DTE; nearest-expiry selection with tie-break logging.",
                "Put-call parity ATM-neighbourhood median forward; DF = 1 because rate ≡ 0.",
                "OTM IV construction; total variance w = σ²T; k = ln(K/F).",
                "Black–Scholes price and IV inversion (audit only; vendor IV is the market).",
                "Static no-arbitrage checks: call decreasing in K, put increasing, discrete butterfly convexity.",
                "Liquidity score from vega (and optional hybrid with a quality bucket). No volume/OI available.",
            ],
            st,
        ),
        P("B. Smile / fair-value methods", st["h2"]),
        bullets(
            [
                "Quadratic polynomial in total variance.",
                "Smoothing spline in log-moneyness.",
                "Gatheral SVI on total variance, previous-day warm start on research days.",
                "SSVI <i>slice</i> (θ, ρ, φ) — not a multi-expiry SSVI surface.",
                "Hagan SABR with β fixed at 1 (lognormal).",
                "Robust ensemble = median; disagreement = cross-model standard deviation.",
                "Vega (default), equal, liquidity, or hybrid fit weights.",
            ],
            st,
        ),
        P("C. Interpolation and structures", st["h2"]),
        bullets(
            [
                "Linear interpolation of IV versus |delta|, max 0.03 extrapolation.",
                "Risk reversals, butterflies, delta points, ATM, skews, slopes, verticals, wing curvature.",
                "Price-space residuals via BS prices on interpolated strikes where defined.",
                "Listed-strike time series via 0.02 log-moneyness bins.",
            ],
            st,
        ),
        P("D. Statistics and signals", st["h2"]),
        bullets(
            [
                "Causal rolling mean / std / z / percentile at 20, 60, 120, 252 days.",
                "Realized vol: close-to-close, windows 5–60, annualised √252; RiskMetrics EWMA λ = 0.94.",
                "Future labels at horizons 1, 3, 5, 10, 20 days (research dates only; label date ≤ train end).",
                "Ten cheap/expensive definitions listed in §8.",
                "Frozen z-gate search on walk-forward mean 5-day convergence, n ≥ 30.",
            ],
            st,
        ),
        P("E. Predictive ML (research window)", st["h2"]),
        bullets(
            [
                "Walk-forward expanding window, 80-day minimum train, 20-day validation, 5-day embargo.",
                "Ridge regression (α = 1) on 5-day convergence.",
                "Elastic net (available).",
                "Logistic regression for P(positive convergence).",
                "Random forest and gradient-boosting classifiers (available, not the frozen pair).",
                "StandardScaler inside the linear pipelines. Seed 7.",
                "Metrics: IC (Pearson of prediction vs realised), sign-hit, MAE.",
            ],
            st,
        ),
        P("F. Backtest and costs", st["h2"]),
        bullets(
            [
                "Fade the residual for 5 days on research dates only.",
                "Mid P&amp;L vs conservative executable P&amp;L.",
                "Cost model: 0.50 ATM price half-spread, +1.50 wing extra, 0.002 IV half-spread.",
                "Hit rate, mean/median P&amp;L, Sharpe proxy, max-drawdown proxy — all labelled as proxies.",
            ],
            st,
        ),
        P("G. Validation design", st["h2"]),
        bullets(
            [
                "No random splits. No peeking at 11 Sep for thresholds.",
                "9–10 Sep unused.",
                "Single frozen holdout. Subsequent days score that decision only.",
                "Multiple-testing warning recorded in the final report.",
            ],
            st,
        ),
        P("H. Software / delivery", st["h2"]),
        bullets(
            [
                "Python: pandas, numpy, scipy, scikit-learn, pytest.",
                "Modular pipeline under src/ (loader, clean, DTE, construction, models, structures, features, signals, backtest).",
                "Static dashboard (HTML/JS/CSS) + compact columnar panel.json.",
                "Private GitHub repo; Vercel static host.",
            ],
            st,
        ),
    ]

    # 15
    story += [
        P("15. How to present the dashboard in five minutes", st["h1"]),
        bullets(
            [
                "Open https://snp-60dte-iv-desk.vercel.app and click <b>Jump to 11 Sep 2026</b>. Gate defaults to 3.0 frozen.",
                "The count strip is the slide: TRADE / NO TRADE / CANNOT DECIDE for that day. On the holdout, TRADE is zero.",
                "Pick RR_25D. Show market vs ensemble (almost on top of each other) and z ≈ 0.18.",
                "Switch the gate slider to 1.5 and explain that this is <i>analysis</i>, not a retune. Most names still do not clear it that day.",
                "Filter Kind = slope or listed_strike to show that the book is no longer just 46 names.",
                "Open a research date that does have TRADEs (102 such dates exist at gate 3.0) if you want to show what a cleared signal looks like — then remind the room those days were inside the sample that chose the gate.",
                "Close on the cost slide: 96% statistical hit, negative executable P&amp;L, therefore NO TRADE is the designed output.",
            ],
            st,
        ),
        P("16. What this project refuses to claim", st["h1"]),
        bullets(
            [
                "That ATM IV of 13.45% on 11 Sep is cheap or expensive. That is a level.",
                "That any strike below SVI is a buy.",
                "That 25P/15P or any other vertical is “the best trade” after scanning many deltas.",
                "That walk-forward IC will stay positive.",
                "That modelled costs equal live SNP bid/ask.",
                "That SSVI here is a calendar-arbitrage-free surface.",
                "That the expanded universe was used to retune 3.0 — it was not.",
            ],
            st,
        ),
        P("17. Bottom line for the room", st["h1"]),
        P(
            "The model is a disciplined way to say whether a 60-DTE structure is cheap or expensive <i>relative to a multi-model smile and to its own history</i>. "
            "The frozen gate of 3.0 was chosen by walk-forward mean 5-day convergence, not by the holdout, and not by RMSE. "
            "That rule is statistically conservative and economically humble: it found residual fade and did not find a cost-surviving book. "
            "On 11 September 2026 the correct output of that frozen rule, even after opening every RR, butterfly, slope and strike, is <b>NO TRADE</b>.",
            st["body"],
        ),
        P(
            "Training 2025-06-05 → 2026-09-08. Gap 9–10 Sep unused. Holdout 11 Sep 2026 untouched. "
            "Do not retune the gate after reading this briefing or after clicking the dashboard.",
            st["note"],
        ),
    ]

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="60-DTE IV Relative-Value Briefing",
        author="Ayush Singh",
        subject="How the 60-DTE IV relative-value model decides TRADE / NO TRADE / CANNOT DECIDE",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"wrote {OUT} bytes={OUT.stat().st_size}")


if __name__ == "__main__":
    build()
