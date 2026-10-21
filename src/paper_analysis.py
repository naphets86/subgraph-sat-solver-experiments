"""
Auswertung für die wissenschaftliche Arbeit (science/subgraph-sat-solver-experiments.tex)

Liest die ``experiment_results.csv`` aller Suites unter ``src/results/<suite>/``
und erzeugt daraus

- Abbildungen (PDF) und
- LaTeX-Tabellenfragmente (``\\input``-fähig)

im Ordner ``src/results/paper/``. Damit stammen alle Zahlen der Arbeit direkt
aus den Rohdaten und müssen nicht von Hand übertragen werden.

Aufruf (aus dem Projektwurzelverzeichnis)::

    pip install -e ".[paper]"
    python -m src.paper_analysis
"""

import ast
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src import RESULTS_DIR

SUITES = ["quick", "standard", "full", "performance"]
TYPES = ["target_and", "target_and_random", "iscas85"]
TYPE_LABEL = {
    "target_and": "Target-AND",
    "target_and_random": "Target-AND-Random",
    "iscas85": "ISCAS'85",
}
TYPE_COLOR = {
    "target_and": "#A23B72",
    "target_and_random": "#F18F01",
    "iscas85": "#2E86AB",
}
SUITE_LABEL = {
    "quick": "Quick",
    "standard": "Standard",
    "full": "Full",
    "performance": "Performance",
}
TICK_MS = 15.625  # 1/64 s: typische Auflösung von time.time() unter Windows

OUT_DIR = RESULTS_DIR / "paper"


# ----------------------------------------------------------------------------
# Daten
# ----------------------------------------------------------------------------

def load_all() -> pd.DataFrame:
    frames = []
    for suite in SUITES:
        df = pd.read_csv(RESULTS_DIR / suite / "experiment_results.csv")
        df["suite"] = suite
        frames.append(df)
    data = pd.concat(frames, ignore_index=True)
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data["depth"] = data["metadata"].apply(
        lambda s: ast.literal_eval(s).get("depth") if isinstance(s, str) else np.nan
    )
    return data


# ----------------------------------------------------------------------------
# Formatierung
# ----------------------------------------------------------------------------

def f(x, nd=2) -> str:
    """Zahl mit Dezimalkomma."""
    return f"{x:.{nd}f}".replace(".", ",")


def thousands(x) -> str:
    return f"{int(round(x)):,}".replace(",", "\\,")


def ustat(u) -> str:
    return thousands(u) if float(u).is_integer() else f(u, 1).replace(",", "{,}")


def pval(p) -> str:
    if p < 0.001:
        return "$<0{,}001$"
    return "$" + f(p, 3).replace(",", "{,}") + "$"


def write_table(name: str, lines: list) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def tabular(colspec: str, header: str, rows: list) -> list:
    out = [f"\\begin{{tabular}}{{{colspec}}}", "\\toprule", header + " \\\\", "\\midrule"]
    out += [r if r.startswith("\\midrule") else r + " \\\\" for r in rows]
    out += ["\\bottomrule", "\\end{tabular}"]
    return out


# ----------------------------------------------------------------------------
# Tabellen
# ----------------------------------------------------------------------------

def table_suites(d: pd.DataFrame) -> None:
    rows = []
    for s in SUITES:
        x = d[d.suite == s]
        cnt = x.circuit_type.value_counts()
        span = (x.timestamp.max() - x.timestamp.min()).total_seconds()
        rows.append(
            " & ".join([
                SUITE_LABEL[s], str(len(x)),
                str(cnt.get("target_and", 0)), str(cnt.get("target_and_random", 0)),
                str(cnt.get("iscas85", 0)), "$\\leq$ " + str(int(span) + 1),
                f(x.runtime_ms.mean()), f(x.runtime_ms.std()), f(x.runtime_ms.median()),
            ])
        )
    rows.append("\\midrule")
    rows.append(
        " & ".join([
            "Gesamt", str(len(d)),
            str((d.circuit_type == "target_and").sum()),
            str((d.circuit_type == "target_and_random").sum()),
            str((d.circuit_type == "iscas85").sum()), "--",
            f(d.runtime_ms.mean()), f(d.runtime_ms.std()), f(d.runtime_ms.median()),
        ])
    )
    write_table("tab_suites.tex", tabular(
        "lrrrrrrrr",
        "Suite & $n$ & T-AND & T-AND-R & ISCAS & Dauer (s) & $\\bar{t}$ (ms) & $s$ (ms) & $\\tilde{t}$ (ms)",
        rows))


def table_suite_type(d: pd.DataFrame) -> None:
    rows = []
    for s in SUITES:
        for t in TYPES:
            x = d[(d.suite == s) & (d.circuit_type == t)].runtime_ms
            if len(x) == 0:
                continue
            rows.append(" & ".join([
                SUITE_LABEL[s], TYPE_LABEL[t], str(len(x)), f(x.mean()), f(x.std()),
                f(x.min()), f(x.quantile(.25)), f(x.median()), f(x.quantile(.75)), f(x.max()),
            ]))
    write_table("tab_suite_type.tex", tabular(
        "llrrrrrrrr",
        "Suite & Circuit-Typ & $n$ & $\\bar{t}$ & $s$ & Min & $Q_1$ & Median & $Q_3$ & Max",
        rows))


def table_structure(d: pd.DataFrame) -> None:
    rows = []
    for t in TYPES:
        x = d[d.circuit_type == t].drop_duplicates("circuit_name")
        rows.append(" & ".join([
            TYPE_LABEL[t], str(len(x)),
            (str(x.num_inputs.min()) if x.num_inputs.min() == x.num_inputs.max()
             else f"{x.num_inputs.min()}--{x.num_inputs.max()}"),
            f"{thousands(x.num_gates.min())}--{thousands(x.num_gates.max())}",
            f(x.num_gates.mean(), 1),
            f"{thousands(x.num_clauses.min())}--{thousands(x.num_clauses.max())}",
            f(x.num_clauses.mean(), 1),
        ]))
    write_table("tab_structure.tex", tabular(
        "lrrrrrr",
        "Circuit-Typ & Instanzen & Eingänge & Gates & $\\bar{g}$ & Klauseln & $\\bar{k}$",
        rows))


def table_target_and(d: pd.DataFrame) -> None:
    x = d[d.circuit_type == "target_and"]
    rows = []
    for m, g in x.groupby("num_inputs"):
        r = g.runtime_ms
        rows.append(" & ".join([
            str(m), str(g.num_gates.iloc[0]), str(g.num_clauses.iloc[0]), str(len(g)),
            f(r.mean()), f(r.std()), f(r.min()), f(r.median()), f(r.max()),
        ]))
    write_table("tab_target_and.tex", tabular(
        "rrrrrrrrr",
        "$m$ & Gates & Klauseln & $n$ & $\\bar{t}$ & $s$ & Min & Median & Max", rows))


def table_depth(d: pd.DataFrame) -> None:
    x = d[d.circuit_type == "target_and_random"]
    rows = []
    for dep, g in x.groupby("depth"):
        r = g.runtime_ms
        rows.append(" & ".join([
            str(int(dep)), str(g.num_gates.iloc[0]), str(g.num_clauses.iloc[0]), str(len(g)),
            f(r.mean()), f(r.std()), f(r.min()), f(r.median()), f(r.max()),
        ]))
    write_table("tab_depth.tex", tabular(
        "rrrrrrrrr",
        "$d$ & Gates & Klauseln & $n$ & $\\bar{t}$ & $s$ & Min & Median & Max", rows))


def table_iscas(d: pd.DataFrame) -> None:
    x = d[d.circuit_type == "iscas85"]
    order = x.drop_duplicates("circuit_name").sort_values("num_gates").circuit_name
    rows = []
    for name in order:
        g = x[x.circuit_name == name]
        r = g.runtime_ms
        rows.append(" & ".join([
            name, str(g.num_inputs.iloc[0]), thousands(g.num_gates.iloc[0]),
            thousands(g.num_clauses.iloc[0]), str(len(g)),
            f(r.mean()), f(r.std()), f(r.min()), f(r.max()),
        ]))
    write_table("tab_iscas.tex", tabular(
        "lrrrrrrrr",
        "Circuit & Eingänge & Gates & Klauseln & $n$ & $\\bar{t}$ & $s$ & Min & Max", rows))


def table_correlation(d: pd.DataFrame) -> dict:
    sets = [
        ("Alle Läufe", d),
        ("Target-AND", d[d.circuit_type == "target_and"]),
        ("Target-AND-Random", d[d.circuit_type == "target_and_random"]),
        ("ISCAS'85", d[d.circuit_type == "iscas85"]),
    ]
    rows, res = [], {}
    for name, x in sets:
        sp = stats.spearmanr(x.num_gates, x.runtime_ms)
        pe = stats.pearsonr(x.num_gates, x.runtime_ms)
        lr = stats.linregress(x.num_gates, x.runtime_ms)
        res[name] = dict(n=len(x), rho=sp.statistic, p_rho=sp.pvalue, r=pe.statistic,
                         p_r=pe.pvalue, slope=lr.slope, r2=lr.rvalue ** 2)
        rows.append(" & ".join([
            name, str(len(x)),
            "$" + f(sp.statistic, 3).replace(",", "{,}") + "$", pval(sp.pvalue),
            "$" + f(pe.statistic, 3).replace(",", "{,}") + "$", pval(pe.pvalue),
            "$" + f(lr.slope * 1000, 1).replace(",", "{,}") + "$",
            "$" + f(lr.rvalue ** 2, 3).replace(",", "{,}") + "$",
        ]))
    # Tiefe
    x = d[d.circuit_type == "target_and_random"]
    sp = stats.spearmanr(x.depth, x.runtime_ms)
    pe = stats.pearsonr(x.depth, x.runtime_ms)
    lr = stats.linregress(x.depth, x.runtime_ms)
    res["Tiefe"] = dict(rho=sp.statistic, p_rho=sp.pvalue, slope=lr.slope, r2=lr.rvalue ** 2)
    rows.append(" & ".join([
        "Target-AND-Random (Tiefe $d$)", str(len(x)),
        "$" + f(sp.statistic, 3).replace(",", "{,}") + "$", pval(sp.pvalue),
        "$" + f(pe.statistic, 3).replace(",", "{,}") + "$", pval(pe.pvalue),
        "--", "$" + f(lr.rvalue ** 2, 3).replace(",", "{,}") + "$",
    ]))
    write_table("tab_correlation.tex", tabular(
        "lrrrrrrr",
        "Teilmenge & $n$ & $\\rho$ & $p_\\rho$ & $r$ & $p_r$ & Steigung ($\\mu$s/Gate) & $R^2$",
        rows))
    return res


def table_tests(d: pd.DataFrame) -> dict:
    res, rows = {}, []
    kt = stats.kruskal(*[g.runtime_ms for _, g in d.groupby("circuit_type")])
    rows.append(f"Kruskal--Wallis: Circuit-Typ (3 Gruppen) & $H={f(kt.statistic).replace(',', '{,}')}$ & {pval(kt.pvalue)}")
    res["kruskal_type"] = (kt.statistic, kt.pvalue)
    ks = stats.kruskal(*[g.runtime_ms for _, g in d.groupby("suite")])
    rows.append(f"Kruskal--Wallis: Suite (4 Gruppen) & $H={f(ks.statistic).replace(',', '{,}')}$ & {pval(ks.pvalue)}")
    res["kruskal_suite"] = (ks.statistic, ks.pvalue)
    i = d[d.circuit_type == "iscas85"].runtime_ms
    o = d[d.circuit_type != "iscas85"].runtime_ms
    mw = stats.mannwhitneyu(i, o)
    rows.append(f"Mann--Whitney: ISCAS'85 vs.\\ synthetisch & $U={ustat(mw.statistic)}$ & {pval(mw.pvalue)}")
    res["mw_iscas"] = (mw.statistic, mw.pvalue)
    for t in ["target_and", "target_and_random", "iscas85"]:
        a = d[(d.suite == "full") & (d.circuit_type == t)].runtime_ms
        b = d[(d.suite == "performance") & (d.circuit_type == t)].runtime_ms
        m = stats.mannwhitneyu(a, b)
        rows.append(f"Mann--Whitney: Full vs.\\ Performance, {TYPE_LABEL[t]} & $U={ustat(m.statistic)}$ & {pval(m.pvalue)}")
        res[f"mw_full_perf_{t}"] = (m.statistic, m.pvalue)
    out = ["\\begin{tabular}{lrr}", "\\toprule", "Test & Prüfgröße & $p$-Wert \\\\", "\\midrule"]
    out += [r + " \\\\" for r in rows]
    out += ["\\bottomrule", "\\end{tabular}"]
    write_table("tab_tests.tex", out)
    return res


def table_full_vs_perf(d: pd.DataFrame) -> None:
    rows = []
    for t in TYPES:
        a = d[(d.suite == "full") & (d.circuit_type == t)].runtime_ms
        b = d[(d.suite == "performance") & (d.circuit_type == t)].runtime_ms
        diff = b.mean() - a.mean()
        rows.append(" & ".join([
            TYPE_LABEL[t], f(a.mean()), f(b.mean()),
            ("$+$" if diff >= 0 else "$-$") + f(abs(diff)),
            ("$+$" if diff >= 0 else "$-$") + f(abs(diff) / a.mean() * 100, 1) + "\\,\\%",
            f(a.std()), f(b.std()),
        ]))
    write_table("tab_full_vs_perf.tex", tabular(
        "lrrrrrr",
        "Circuit-Typ & $\\bar{t}_{\\text{Full}}$ & $\\bar{t}_{\\text{Perf.}}$ & $\\Delta$ (ms) & $\\Delta$ (\\%) & $s_{\\text{Full}}$ & $s_{\\text{Perf.}}$",
        rows))


def table_quantization(d: pd.DataFrame) -> dict:
    x = d.runtime_ms
    bins = [(0, 10), (10, 15), (15, 16.5), (16.5, 20), (20, 30), (30, 31), (31, 33), (33, 45)]
    rows = []
    for lo, hi in bins:
        n = int(((x > lo) & (x <= hi)).sum())
        rows.append(f"$({f(lo, 1).replace(',', '{,}')};\\,{f(hi, 1).replace(',', '{,}')}]$ & {n} & {f(n / len(x) * 100, 1)}\\,\\%")
    near = ((np.abs(x - TICK_MS) <= 1.0) | (np.abs(x - 2 * TICK_MS) <= 1.0))
    write_table("tab_quantization.tex", tabular("lrr", "Laufzeitbereich (ms) & Anzahl & Anteil", rows))
    return dict(near_share=float(near.mean()), near_n=int(near.sum()), n=len(x))


# ----------------------------------------------------------------------------
# Abbildungen
# ----------------------------------------------------------------------------

def setup_style() -> None:
    plt.style.use("default")
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times New Roman", "serif"],
        "axes.labelsize": 11, "axes.titlesize": 12, "legend.fontsize": 9,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "--",
        "savefig.dpi": 300,
    })


def save(fig, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, bbox_inches="tight")
    plt.close(fig)


def fig_histogram(d: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    bins = np.arange(5, 42, 1.0)
    ax.hist([d[d.circuit_type == t].runtime_ms for t in TYPES], bins=bins, stacked=True,
            color=[TYPE_COLOR[t] for t in TYPES], label=[TYPE_LABEL[t] for t in TYPES],
            edgecolor="#333333", linewidth=0.4)
    ax.axvline(TICK_MS, color="#C73E1D", linestyle="--", linewidth=1.4,
               label="15,625 ms und 31,25 ms")
    ax.axvline(2 * TICK_MS, color="#C73E1D", linestyle="--", linewidth=1.4)
    ax.set_xlabel("Laufzeit (ms)")
    ax.set_ylabel("Anzahl Läufe")
    ax.legend(loc="upper right")
    save(fig, "fig_runtime_histogram.pdf")


def fig_gates_runtime(d: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    rng = np.random.default_rng(0)
    for t in TYPES:
        x = d[d.circuit_type == t]
        jitter = np.exp(rng.normal(0, 0.012, len(x)))
        ax.scatter(x.num_gates * jitter, x.runtime_ms, s=26, alpha=0.7, color=TYPE_COLOR[t],
                   edgecolor="#333333", linewidth=0.4, label=TYPE_LABEL[t])
    ax.set_xscale("log")
    ax.set_xlabel("Anzahl Gates (logarithmisch)")
    ax.set_ylabel("Laufzeit (ms)")
    ax.legend()
    save(fig, "fig_gates_vs_runtime.pdf")


def fig_parameters(d: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8), sharey=True)
    a = d[d.circuit_type == "target_and"]
    g = a.groupby("num_inputs").runtime_ms
    axes[0].errorbar(g.mean().index, g.mean().values, yerr=g.std().values, fmt="o-",
                     color=TYPE_COLOR["target_and"], capsize=3, label="Mittelwert $\\pm$ $s$")
    axes[0].scatter(a.num_inputs, a.runtime_ms, s=10, color="#555555", alpha=0.35, label="Einzelläufe")
    axes[0].set_xlabel("Anzahl Eingänge $m$")
    axes[0].set_ylabel("Laufzeit (ms)")
    axes[0].set_title("Target-AND")
    axes[0].legend()
    r = d[d.circuit_type == "target_and_random"]
    g = r.groupby("depth").runtime_ms
    axes[1].errorbar(g.mean().index, g.mean().values, yerr=g.std().values, fmt="o-",
                     color=TYPE_COLOR["target_and_random"], capsize=3)
    axes[1].scatter(r.depth, r.runtime_ms, s=10, color="#555555", alpha=0.35)
    axes[1].set_xlabel("Tiefe $d$ (zufällige Schichten, $m=10$)")
    axes[1].set_title("Target-AND-Random")
    save(fig, "fig_parameters.pdf")


def fig_iscas(d: pd.DataFrame) -> None:
    x = d[d.circuit_type == "iscas85"]
    order = list(x.drop_duplicates("circuit_name").sort_values("num_gates").circuit_name)
    fig, ax = plt.subplots(figsize=(8.5, 4))
    for i, name in enumerate(order):
        g = x[x.circuit_name == name]
        ax.scatter([i] * len(g), g.runtime_ms, s=20, color="#555555", alpha=0.5, zorder=2)
        ax.scatter(i, g.runtime_ms.mean(), marker="D", s=46, color=TYPE_COLOR["iscas85"],
                   edgecolor="#333333", zorder=3)
    ax.axhline(TICK_MS, color="#C73E1D", linestyle="--", linewidth=1)
    ax.axhline(2 * TICK_MS, color="#C73E1D", linestyle="--", linewidth=1)
    labels = [f"{n}\n({int(x[x.circuit_name == n].num_gates.iloc[0])})" for n in order]
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_xlabel("ISCAS'85-Circuit (Anzahl Gates), aufsteigend nach Größe")
    ax.set_ylabel("Laufzeit (ms)")
    save(fig, "fig_iscas.pdf")


def fig_suites(d: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4))
    suite_colors = ["#2E86AB", "#06A77D", "#F18F01", "#A23B72"]
    width = 0.2
    for si, s in enumerate(SUITES):
        for ti, t in enumerate(TYPES):
            x = d[(d.suite == s) & (d.circuit_type == t)].runtime_ms
            if len(x) == 0:
                continue
            pos = ti + (si - 1.5) * width
            bp = ax.boxplot(x, positions=[pos], widths=width * 0.85, patch_artist=True,
                            showfliers=True, flierprops=dict(markersize=3))
            bp["boxes"][0].set_facecolor(suite_colors[si])
            bp["boxes"][0].set_alpha(0.8)
            for m in bp["medians"]:
                m.set_color("#222222")
    ax.set_xticks(range(len(TYPES)))
    ax.set_xticklabels([TYPE_LABEL[t] for t in TYPES])
    ax.set_ylabel("Laufzeit (ms)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=suite_colors[i], alpha=0.8) for i in range(4)]
    ax.legend(handles, [SUITE_LABEL[s] for s in SUITES], ncol=4, loc="upper center")
    ax.set_ylim(0, 48)
    save(fig, "fig_suites.pdf")


# ----------------------------------------------------------------------------

def main() -> None:
    d = load_all()
    setup_style()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    table_suites(d)
    table_suite_type(d)
    table_structure(d)
    table_target_and(d)
    table_depth(d)
    table_iscas(d)
    table_full_vs_perf(d)
    corr = table_correlation(d)
    tests = table_tests(d)
    quant = table_quantization(d)

    fig_histogram(d)
    fig_gates_runtime(d)
    fig_parameters(d)
    fig_iscas(d)
    fig_suites(d)

    summary = dict(n=len(d), mean=d.runtime_ms.mean(), std=d.runtime_ms.std(),
                   min=d.runtime_ms.min(), max=d.runtime_ms.max(),
                   satisfiable_true=int(d.satisfiable.sum()),
                   errors=int(d.error.notna().sum()),
                   quantization=quant, correlation=corr, tests=tests)
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, default=float, ensure_ascii=False), encoding="utf-8")
    print(f"Fertig: Tabellen und Abbildungen in {OUT_DIR}")


if __name__ == "__main__":
    main()
