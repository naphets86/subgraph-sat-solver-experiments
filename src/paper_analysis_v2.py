"""
Auswertung der neuen Version der Experimente (Version 2.0.0) für die wissenschaftliche Arbeit
(Abschnitt "Neue Version der Experimente" in science/subgraph-sat-solver-experiments.tex).

Eingabe (Zwischenstand des Full-Presets vom 11.10.2026):

    src/results/full_zwischenstand.csv   Median je Solver und Instanz
    src/results/full_log_zwischenstand.log   Konsolenausgabe (enthält die Basislinien)

Die Struktur der Instanzen (Variablen, Klauseln, Literale) wird aus den Generatoren
des Frameworks (``src.instances``) neu berechnet. Ausgabe nach ``src/results/paper/``:

    fig_v2_*.pdf      Abbildungen (matplotlib)
    tab_v2_*.tex      LaTeX-Tabellenfragmente
    summary_v2.json   alle im Text genannten Kennzahlen

Aufruf (aus dem Projektwurzelverzeichnis)::

    python -m src.paper_analysis_v2
"""

import csv
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from src import RESULTS_DIR
from src.instances import build_instances

CSV_PATH = RESULTS_DIR / "full_zwischenstand.csv"
LOG_PATH = RESULTS_DIR / "full_log_zwischenstand.log"
OUT = RESULTS_DIR / "paper"

SG = "SubgraphSATSolver"
REF = "reference-cdcl"
C_SG = "#2a78d6"      # blau
C_REF = "#eb6834"     # orange
C_GRID = "#d9d8d3"
C_INK = "#2b2b29"
TIMEOUT_MS = 60000.0

plt.rcParams.update({
    "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5, "legend.fontsize": 7.5,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.edgecolor": "#8a8984", "axes.linewidth": 0.7,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": C_GRID, "grid.linewidth": 0.5,
    "axes.axisbelow": True, "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.family": "DejaVu Sans", "text.color": C_INK, "axes.labelcolor": C_INK,
    "xtick.color": C_INK, "ytick.color": C_INK,
})


# ---------------------------------------------------------------------------
# Daten
# ---------------------------------------------------------------------------

def load():
    rows = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[(r["solver"], r["instanz"])] = dict(
                gates=int(r["gates"]), status=r["status"], n=int(r["n"]),
                median=float(r["median_ms"]), note=r["anmerkung"])
    base = {}
    for m in re.finditer(r"Basislinie (\S+) \(triviale Instanz, n=(\d+)\): Median ([\d.]+) ms, s=([\d.]+) ms",
                         LOG_PATH.read_text(encoding="utf-8")):
        base[m.group(1)] = dict(n=int(m.group(2)), median=float(m.group(3)), std=float(m.group(4)))
    inst = {}
    for i in build_instances("full"):
        cnf = i.circuit.to_cnf(i.constraint)
        inst[i.name] = dict(family=i.family, expected=i.expected, gates=i.circuit.num_gates,
                            inputs=i.circuit.num_inputs, vars=cnf.num_vars, clauses=cnf.num_clauses,
                            lits=sum(len(c) for c in cnf.clauses), params=i.params)
    names = sorted({n for _, n in rows})
    for n in names:                        # Konsistenz CSV <-> Generatoren
        assert rows[(SG, n)]["gates"] == inst[n]["gates"], n
    return rows, base, inst, names


def names_of(inst, names, family):
    sel = [n for n in names if inst[n]["family"] == family]
    return sorted(sel, key=lambda n: inst[n]["gates"])


def spearman(x, y):
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    return float(np.corrcoef(rx, ry)[0, 1])


def linfit(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    b, a = np.polyfit(x, y, 1)
    res = y - (a + b * x)
    r2 = 1 - res.var() / y.var()
    return float(b), float(a), float(r2)


def powerfit(x, y):
    lx, ly = np.log(np.asarray(x, float)), np.log(np.asarray(y, float))
    n = len(lx)
    b, a = np.polyfit(lx, ly, 1)
    res = ly - (a + b * lx)
    r2 = 1 - res.var() / ly.var()
    se = np.sqrt((res ** 2).sum() / (n - 2) / ((lx - lx.mean()) ** 2).sum())
    return float(b), float(a), float(r2), float(se)


def de(x, d=2):
    """Zahl mit Dezimalkomma für LaTeX."""
    ip, fp = f"{x:.{d}f}".split(".")
    ip = f"{int(ip):,}".replace(",", "\\,")
    return f"{ip}{{,}}{fp}"


def thousands(n):
    s = f"{n:,}".replace(",", "\\,")
    return s


# ---------------------------------------------------------------------------
# Hilfen für Abbildungen
# ---------------------------------------------------------------------------

def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    print("  ->", name)


def style_sg(ax_or_none=None):
    return dict(color=C_SG, mec=C_SG, mfc=C_SG)


def plot_points(ax, rows, names, xs, solver, base_label=True, **kw):
    """Zeichnet Median-Punkte; TIMEOUT als Dreieck, ERROR als Kreuz."""
    color = C_SG if solver == SG else C_REF
    for n, x in zip(names, xs):
        r = rows[(solver, n)]
        if r["status"] == "TIMEOUT":
            ax.plot(x, r["median"], marker="^", ms=6.5, color=color, mfc="white", mew=1.3, ls="none", zorder=4)
        elif r["status"] == "ERROR":
            ax.plot(x, r["median"], marker="X", ms=7, color="#b3261e", mec="white", mew=0.5, ls="none", zorder=5)
        else:
            marker = "o" if solver == SG else "s"
            ax.plot(x, r["median"], marker=marker, ms=4.5, color=color, ls="none", zorder=3)


def baseline_lines(ax, base, label=True):
    ax.axhline(base[SG]["median"], color=C_SG, ls=(0, (1.5, 2)), lw=1.0, zorder=1)
    ax.axhline(base[REF]["median"], color=C_REF, ls=(0, (1.5, 2)), lw=1.0, zorder=1)


def solver_legend(ax, extra=(), loc="best", fig_below=False):
    h = [Line2D([], [], marker="o", color=C_SG, ls="-", lw=1.2, ms=4.5, label="Subgraph-SAT-Solver"),
         Line2D([], [], marker="s", color=C_REF, ls="-", lw=1.2, ms=4.5, label="Referenzsolver (CDCL, Python)"),
         Line2D([], [], color=C_SG, ls=(0, (1.5, 2)), lw=1.0, label="Basislinie Subgraph-SAT-Solver"),
         Line2D([], [], color=C_REF, ls=(0, (1.5, 2)), lw=1.0, label="Basislinie Referenzsolver")]
    h += list(extra)
    if fig_below:
        ax.figure.legend(handles=h, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.24))
        return
    ax.legend(handles=h, loc=loc, frameon=True, framealpha=0.95, edgecolor="#cfcec9", fancybox=False)


H_TO = Line2D([], [], marker="^", color=C_SG, mfc="white", mew=1.3, ls="none", ms=6.5,
              label="Timeout (60 s, Wert = Laufzeit bis Abbruch)")
H_ERR = Line2D([], [], marker="X", color="#b3261e", mec="white", mew=0.5, ls="none", ms=7,
               label="Status ERROR (einzelner Lauf)")


# ---------------------------------------------------------------------------
# Abbildungen
# ---------------------------------------------------------------------------

def fig_overview(rows, base, inst, names):
    fig, ax = plt.subplots(figsize=(6.3, 3.9))
    for solver in (SG, REF):
        plot_points(ax, rows, names, [inst[n]["gates"] for n in names], solver)
    baseline_lines(ax, base)
    ax.axhline(TIMEOUT_MS, color="#8a8984", lw=0.8, ls="--", zorder=1)
    ax.text(1500, TIMEOUT_MS * 1.12, "Zeitlimit 60 s", fontsize=7, color="#6b6a66", va="bottom")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Anzahl der Gates (logarithmisch)")
    ax.set_ylabel("Median der Laufzeit in ms (logarithmisch)")
    ax.set_ylim(4, 3.2e5)
    solver_legend(ax, [H_TO, H_ERR], loc="upper left")
    save(fig, "fig_v2_overview.pdf")


def fig_target_and(rows, base, inst, names):
    t1 = [n for n in names_of(inst, names, "target_and")]
    sc = names_of(inst, names, "scaling")
    sc = [n for n in sc if (SG, n) in rows]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 3.2), gridspec_kw=dict(width_ratios=[1, 1.05]))
    ax = axes[0]
    ms_ = [inst[n]["params"]["m"] for n in t1]
    for solver, c, mk in ((SG, C_SG, "o"), (REF, C_REF, "s")):
        ax.plot(ms_, [rows[(solver, n)]["median"] for n in t1], marker=mk, ms=4.5, color=c, lw=1.2)
    baseline_lines(ax, base)
    ax.set_xlabel("Eingänge $m$ (Target-AND)".replace("$m$", "m"))
    ax.set_ylabel("Median der Laufzeit in ms")
    ax.set_ylim(0, 72)
    ax.set_xticks(ms_)
    ax.set_title("(a) m = 4 bis 20, lineare Achsen", loc="left")
    solver_legend(ax, fig_below=True)
    ax = axes[1]
    allm = t1 + sc
    xs = [inst[n]["params"]["m"] for n in allm]
    for solver, c, mk in ((SG, C_SG, "o"), (REF, C_REF, "s")):
        ok = [(x, rows[(solver, n)]["median"]) for n, x in zip(allm, xs) if rows[(solver, n)]["status"] in ("SAT", "UNSAT")]
        ax.plot(*zip(*ok), marker=mk, ms=4.5, color=c, lw=1.2)
    for n, x in zip(allm, xs):
        r = rows[(SG, n)]
        if r["status"] == "ERROR":
            ax.plot(x, r["median"], marker="X", ms=8, color="#b3261e", mec="white", mew=0.5, ls="none", zorder=5)
            ax.annotate("ERROR\n(%.1f s)" % (r["median"] / 1000), (x, r["median"]), xytext=(-4, -4),
                        textcoords="offset points", ha="right", va="top", fontsize=7)
    baseline_lines(ax, base)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Eingänge m (logarithmisch)")
    ax.set_ylim(4, 1.2e5)
    ax.set_title("(b) m = 4 bis 1000, logarithmische Achsen", loc="left")
    save(fig, "fig_v2_target_and.pdf")


def fig_depth(rows, base, inst, names):
    t2 = sorted(names_of(inst, names, "target_and_random"), key=lambda n: inst[n]["params"]["depth"])
    d = [inst[n]["params"]["depth"] for n in t2]
    lits = [inst[n]["lits"] for n in t2]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 3.2))
    ax = axes[0]
    for solver, c in ((SG, C_SG), (REF, C_REF)):
        y = [rows[(solver, n)]["median"] for n in t2]
        ax.plot(d, y, color=c, lw=1.2, zorder=2)
        for n, x, yy in zip(t2, d, y):
            st = rows[(solver, n)]["status"]
            ax.plot(x, yy, marker="D" if st == "SAT" else "o", ms=5, color=c,
                    mfc=c if st == "SAT" else "white", mew=1.3, ls="none", zorder=3)
    baseline_lines(ax, base)
    ax.set_xticks(d)
    ax.set_xlabel("Tiefe d der Zwischenschichten (m = 10)")
    ax.set_ylabel("Median der Laufzeit in ms")
    ax.set_ylim(0, 72)
    ax.set_title("(a) Laufzeit je Tiefe", loc="left")
    h = [Line2D([], [], marker="D", color="#55544f", ls="none", ms=5, label="Ergebnis SAT"),
         Line2D([], [], marker="o", color="#55544f", mfc="white", mew=1.3, ls="none", ms=5, label="Ergebnis UNSAT")]
    solver_legend(ax, h, fig_below=True)
    ax = axes[1]
    y = [rows[(SG, n)]["median"] for n in t2]
    ax.plot(lits, y, "o", ms=4.5, color=C_SG)
    b, a, r2 = linfit(lits, y)
    xx = np.array([min(lits), max(lits)])
    ax.plot(xx, a + b * xx, color=C_SG, lw=1.0, ls="--")
    for n, x, yy in zip(t2, lits, y):
        dd = inst[n]["params"]["depth"]
        if dd in (1, 7, 12):
            ax.annotate(f"d={dd}", (x, yy), xytext=(-5, 5), textcoords="offset points", ha="right", fontsize=7)
    ax.set_xlabel("Anzahl der Literale der CNF")
    ax.set_ylabel("Median Subgraph-SAT-Solver in ms")
    ax.set_title("(b) Subgraph-SAT-Solver mit linearer Regression", loc="left")
    ax.text(0.04, 0.95, f"Steigung {b*1000:.0f} µs je Literal\n$R^2$ = {r2:.3f}".replace(".", ","), transform=ax.transAxes,
            va="top", fontsize=7.5)
    save(fig, "fig_v2_depth.pdf")
    return dict(slope_ms_per_lit=b, intercept=a, r2=r2)


def fig_iscas(rows, base, inst, names):
    isc = names_of(inst, names, "iscas85")
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.5), gridspec_kw=dict(width_ratios=[1.25, 1]))
    ax = axes[0]
    x = np.arange(len(isc))
    w = 0.38
    for off, solver, c in ((-w / 2, SG, C_SG), (w / 2, REF, C_REF)):
        for i, n in enumerate(isc):
            r = rows[(solver, n)]
            if r["status"] == "ERROR":
                ax.bar(x[i] + off, r["median"], w, color="white", edgecolor="#b3261e", hatch="////", lw=0.8, zorder=3)
            else:
                ax.bar(x[i] + off, r["median"], w, color=c, zorder=3)
    ax.set_yscale("log")
    ax.set_ylim(3, 1e5)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{n} ({inst[n]['gates']})" for n in isc], fontsize=6.8, rotation=55, ha="right")
    ax.set_xlabel("ISCAS'85-Circuit (in Klammern: Gates)")
    ax.set_ylabel("Median der Laufzeit in ms (logarithmisch)")
    ax.axhline(base[SG]["median"], color=C_SG, ls=(0, (1.5, 2)), lw=1.0, zorder=4)
    ax.axhline(base[REF]["median"], color=C_REF, ls=(0, (1.5, 2)), lw=1.0, zorder=4)
    h = [Patch(color=C_SG, label="Subgraph-SAT-Solver"), Patch(color=C_REF, label="Referenzsolver"),
         Patch(facecolor="white", edgecolor="#b3261e", hatch="////", label="Subgraph: ERROR (Laufzeit bis Fehler)"),
         Line2D([], [], color="#55544f", ls=(0, (1.5, 2)), label="Basislinien")]
    fig.legend(handles=h, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.30, -0.33))
    ax.set_title("(a) alle zwölf Circuits", loc="left")
    ax.grid(axis="x", visible=False)

    ax = axes[1]
    ok = [n for n in isc if rows[(SG, n)]["status"] == "SAT" and n not in ("c3", "c17")]
    lits = [inst[n]["lits"] for n in ok]
    y = [rows[(SG, n)]["median"] for n in ok]
    b, a, r2, se = powerfit(lits, y)
    ax.plot(lits, y, "o", ms=5, color=C_SG, zorder=3)
    xx = np.array([min(lits) * 0.8, 3.2e4])
    ax.plot(xx, np.exp(a) * xx ** b, color=C_SG, lw=1.0, ls="--", zorder=2)
    for n in isc:
        r = rows[(SG, n)]
        if r["status"] == "ERROR":
            ax.plot(inst[n]["lits"], r["median"], marker="X", ms=7, color="#b3261e", mec="white", mew=0.5, ls="none", zorder=5)
    for n in ok:
        ax.annotate(n, (inst[n]["lits"], rows[(SG, n)]["median"]), xytext=(4, -9), textcoords="offset points", fontsize=6.8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Literale der CNF (logarithmisch)")
    ax.set_ylabel("Median Subgraph-SAT-Solver in ms")
    ax.set_xlim(900, 3.2e4)
    ax.set_ylim(300, 6e4)
    ax.set_title("(b) Potenzgesetz-Fit", loc="left")
    ax.text(0.04, 0.95, f"Exponent {b:.2f} ± {se:.2f}\n$R^2$ = {r2:.3f}".replace(".", ","), transform=ax.transAxes,
            va="top", fontsize=7.5)
    h = [Line2D([], [], marker="o", color=C_SG, ls="none", ms=5, label="gelöst (SAT)"),
         Line2D([], [], marker="X", color="#b3261e", mec="white", ls="none", ms=7, label="ERROR")]
    ax.legend(handles=h, loc="lower right", frameon=True, framealpha=0.95, edgecolor="#cfcec9", fancybox=False)
    save(fig, "fig_v2_iscas.pdf")
    return dict(exponent=b, se=se, r2=r2, intercept=a, points=ok)


def fig_miter(rows, base, inst, names):
    mt = names_of(inst, names, "miter_self") + names_of(inst, names, "miter_equiv")
    mt = sorted(mt, key=lambda n: inst[n]["gates"])
    fig, ax = plt.subplots(figsize=(6.3, 3.7))
    y = np.arange(len(mt))[::-1]
    h = 0.36
    for off, solver, c in ((h / 2, SG, C_SG), (-h / 2, REF, C_REF)):
        for yy, n in zip(y, mt):
            r = rows[(solver, n)]
            if r["status"] == "TIMEOUT":
                ax.barh(yy + off, r["median"], h, color="white", edgecolor=c, hatch="////", lw=0.9, zorder=3)
            elif r["status"] == "ERROR":
                ax.barh(yy + off, r["median"], h, color="white", edgecolor="#b3261e", hatch="xxxx", lw=0.9, zorder=3)
            else:
                ax.barh(yy + off, r["median"], h, color=c, zorder=3)
    ax.set_xscale("log")
    ax.set_xlim(3, 4e5)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{n.replace('MiterSelf_', 'Selbst-Miter ').replace('Miter_', 'Miter ')} ({inst[n]['gates']})".replace("_", "\\_" if False else "_") for n in mt], fontsize=7)
    ax.set_xlabel("Median der Laufzeit in ms (logarithmisch)")
    ax.axvline(TIMEOUT_MS, color="#8a8984", lw=0.8, ls="--", zorder=1)
    ax.text(TIMEOUT_MS * 1.08, len(mt) - 0.55, "Zeitlimit 60 s", fontsize=7, color="#6b6a66", va="center")
    ax.axvline(base[SG]["median"], color=C_SG, ls=(0, (1.5, 2)), lw=1.0, zorder=4)
    ax.axvline(base[REF]["median"], color=C_REF, ls=(0, (1.5, 2)), lw=1.0, zorder=4)
    ax.grid(axis="y", visible=False)
    hh = [Patch(color=C_SG, label="Subgraph-SAT-Solver"), Patch(color=C_REF, label="Referenzsolver"),
          Patch(facecolor="white", edgecolor=C_SG, hatch="////", label="Subgraph: Timeout (60 s)"),
          Patch(facecolor="white", edgecolor="#b3261e", hatch="xxxx", label="Subgraph: ERROR (Laufzeit bis Fehler)"),
          Line2D([], [], color="#55544f", ls=(0, (1.5, 2)), label="Basislinien")]
    fig.legend(handles=hh, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.45, -0.14))
    save(fig, "fig_v2_miter.pdf")


def fig_status(rows, base, inst, names):
    fams = [("target_and", "Target-AND"), ("target_and_random", "Target-AND-\nRandom"), ("iscas85", "ISCAS'85"),
            ("miter", "Miter\n(UNSAT)"), ("scaling", "Skalierung\n(m ≥ 100)")]
    cols = {"SAT": "#1baf7a", "UNSAT": "#6250d6", "TIMEOUT": "#eda100", "ERROR": "#b3261e"}
    hatch = {"SAT": "", "UNSAT": "\\\\\\\\", "TIMEOUT": "....", "ERROR": "xxxx"}
    order = ["SAT", "UNSAT", "TIMEOUT", "ERROR"]
    fig, ax = plt.subplots(figsize=(6.3, 3.3))
    w = 0.36
    counts = {}
    for i, (fk, _) in enumerate(fams):
        ns = [n for n in names if (inst[n]["family"] in ("miter_self", "miter_equiv") if fk == "miter" else inst[n]["family"] == fk)]
        for off, solver in ((-w / 2 - 0.01, SG), (w / 2 + 0.01, REF)):
            bottom = 0
            for st in order:
                k = sum(1 for n in ns if rows[(solver, n)]["status"] == st)
                counts[(fk, solver, st)] = k
                if k:
                    ax.bar(i + off, k, w, bottom=bottom, color=cols[st], hatch=hatch[st], edgecolor="white", lw=0.8, zorder=3)
                    ax.text(i + off, bottom + k / 2, str(k), ha="center", va="center", fontsize=7.5, color="white", weight="bold", zorder=5,
                            bbox=dict(boxstyle="round,pad=0.15", fc=cols[st], ec="none"))
                bottom += k
            ax.text(i + off, bottom + 0.25, "SG" if solver == SG else "Ref", ha="center", va="bottom", fontsize=6.5, color="#55544f")
    ax.set_xticks(range(len(fams)))
    ax.set_xticklabels([l for _, l in fams], fontsize=7.5)
    ax.set_ylabel("Anzahl Instanzen")
    ax.set_ylim(0, 14)
    ax.grid(axis="x", visible=False)
    ax.legend(handles=[Patch(facecolor=cols[s], hatch=hatch[s], edgecolor="white", label=s) for s in order],
              loc="upper right", ncol=2, frameon=True, framealpha=0.95, edgecolor="#cfcec9", fancybox=False)
    save(fig, "fig_v2_status.pdf")
    return {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in counts.items()}


def fig_ratio(rows, base, inst, names):
    fig, ax = plt.subplots(figsize=(6.3, 3.5))
    fam_style = {"target_and": ("o", "#d55181", "Target-AND"), "scaling": ("o", "#8f2a55", "Skalierung"),
                 "target_and_random": ("D", "#eb6834", "Target-AND-Random"), "iscas85": ("s", "#1baf7a", "ISCAS'85"),
                 "miter_self": ("^", "#6250d6", "Miter"), "miter_equiv": ("^", "#6250d6", None)}
    for n in names:
        fam = inst[n]["family"]
        mk, c, _ = fam_style[fam]
        a, b = rows[(SG, n)], rows[(REF, n)]
        if a["status"] == "ERROR":
            continue
        ratio = a["median"] / b["median"]
        if a["status"] == "TIMEOUT":
            ax.plot(inst[n]["lits"], ratio, marker="^", ms=7, color=c, mfc="white", mew=1.3, ls="none", zorder=4)
            ax.annotate("", (inst[n]["lits"], ratio * 1.9), (inst[n]["lits"], ratio * 1.05),
                        arrowprops=dict(arrowstyle="-|>", color=c, lw=0.8))
        else:
            ax.plot(inst[n]["lits"], ratio, marker=mk, ms=4.8, color=c, ls="none", zorder=3)
    ax.axhline(1, color=C_INK, lw=0.9, zorder=2)
    ax.text(25, 1.12, "gleich schnell", fontsize=7, color="#55544f")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Literale der CNF (logarithmisch)")
    ax.set_ylabel("Median Subgraph / Median Referenz")
    ax.set_ylim(0.08, 800)
    h = [Line2D([], [], marker=v[0], color=v[1], ls="none", ms=5, label=v[2])
         for k, v in fam_style.items() if v[2]]
    h.append(Line2D([], [], marker="^", color="#6250d6", mfc="white", mew=1.3, ls="none", ms=7,
                    label="Timeout: Verhältnis ist nur eine untere Schranke"))
    ax.legend(handles=h, loc="upper left", frameon=True, framealpha=0.95, edgecolor="#cfcec9", fancybox=False)
    save(fig, "fig_v2_ratio.pdf")


# ---------------------------------------------------------------------------
# Tabellen
# ---------------------------------------------------------------------------

ST_SHORT = {"SAT": "SAT", "UNSAT": "UNSAT", "TIMEOUT": "Timeout", "ERROR": "ERROR"}


def cell(r):
    return f"{r['n']} & {de(r['median'])}"


def write_table(name, header, body):
    OUT.mkdir(parents=True, exist_ok=True)
    text = "\\begin{tabular}{" + header[0] + "}\n\\toprule\n" + header[1] + " \\\\\n\\midrule\n" + \
           " \\\\\n".join(body) + " \\\\\n\\bottomrule\n\\end{tabular}\n"
    (OUT / name).write_text(text, encoding="utf-8")
    print("  ->", name)


def tex_name(n):
    return "\\texttt{" + n.replace("_", "\\_") + "}"


def row_inst(rows, inst, n, label=None):
    i = inst[n]
    a, b = rows[(SG, n)], rows[(REF, n)]
    st = ST_SHORT[a["status"]]
    if a["status"] != b["status"]:
        st = f"{ST_SHORT[a['status']]} / {ST_SHORT[b['status']]}"
    return (f"{label or tex_name(n)} & {thousands(i['gates'])} & {thousands(i['clauses'])} & {thousands(i['lits'])} & {st} & "
            f"{cell(a)} & {cell(b)}")


HDR = ("lrrrlrrrr",
       "Instanz & Gates & Klauseln & Literale & Status & $n_{\\mathrm{SG}}$ & $\\tilde{t}_{\\mathrm{SG}}$ & $n_{\\mathrm{Ref}}$ & $\\tilde{t}_{\\mathrm{Ref}}$")


def tables(rows, inst, names):
    t1 = names_of(inst, names, "target_and") + names_of(inst, names, "scaling")
    t1 = [n for n in t1 if (SG, n) in rows]
    write_table("tab_v2_target_and.tex", HDR, [row_inst(rows, inst, n) for n in t1])
    t2 = sorted(names_of(inst, names, "target_and_random"), key=lambda n: inst[n]["params"]["depth"])
    write_table("tab_v2_depth.tex", HDR, [row_inst(rows, inst, n, f"$d={inst[n]['params']['depth']}$") for n in t2])
    write_table("tab_v2_iscas.tex", HDR, [row_inst(rows, inst, n) for n in names_of(inst, names, "iscas85")])
    mt = sorted(names_of(inst, names, "miter_self") + names_of(inst, names, "miter_equiv"), key=lambda n: inst[n]["gates"])
    write_table("tab_v2_miter.tex", HDR, [row_inst(rows, inst, n) for n in mt])


# ---------------------------------------------------------------------------

def main():
    rows, base, inst, names = load()
    print(f"{len(names)} Instanzen, Basislinien: {base}")
    summary = {"baseline": base}
    print("Abbildungen:")
    fig_overview(rows, base, inst, names)
    fig_target_and(rows, base, inst, names)
    summary["depth_fit"] = fig_depth(rows, base, inst, names)
    summary["iscas_fit"] = fig_iscas(rows, base, inst, names)
    fig_miter(rows, base, inst, names)
    summary["status_counts"] = fig_status(rows, base, inst, names)
    fig_ratio(rows, base, inst, names)
    print("Tabellen:")
    tables(rows, inst, names)

    # Kennzahlen für den Text
    t1 = names_of(inst, names, "target_and")
    m = [inst[n]["params"]["m"] for n in t1]
    for solver in (SG, REF):
        y = [rows[(solver, n)]["median"] for n in t1]
        b, a, r2 = linfit(m, y)
        summary[f"target_and_{solver}"] = dict(spearman=spearman(m, y), slope_ms_per_m=b, intercept=a, r2=r2,
                                                 min=min(y), max=max(y))
        t2 = names_of(inst, names, "target_and_random")
        d = [inst[n]["params"]["depth"] for n in t2]
        y2 = [rows[(solver, n)]["median"] for n in t2]
        b2, a2, r22 = linfit(d, y2)
        summary[f"depth_{solver}"] = dict(spearman=spearman(d, y2), slope_ms_per_d=b2, r2=r22, min=min(y2), max=max(y2))
    tot = {s: sum(r["n"] for (sv, _), r in rows.items() if sv == s) for s in (SG, REF)}
    summary["total_runs"] = tot
    agree = [n for n in names if rows[(SG, n)]["status"] in ("SAT", "UNSAT") and rows[(REF, n)]["status"] in ("SAT", "UNSAT")]
    summary["both_decided"] = len(agree)
    summary["disagree"] = [n for n in agree if rows[(SG, n)]["status"] != rows[(REF, n)]["status"]]
    (OUT / "summary_v2.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
