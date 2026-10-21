"""
Visualizer für Subgraph-SAT-Solver Experiment-Ergebnisse

Erzeugt Diagramme mit matplotlib und exportiert als SVG/PDF für LaTeX
"""

import json
import statistics
from pathlib import Path
from typing import List, Dict, Optional
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
import numpy as np
from src import RESULTS_DIR
from src.experiment_runner import ExperimentResult


class ExperimentVisualizer:
    """Visualisiert Experiment-Ergebnisse"""
    
    # LaTeX-kompatible Schriftarten
    FONT_CONFIG = {
        'font.family': 'serif',
        'font.serif': ['DejaVu Serif', 'Times New Roman', 'Times', 'Liberation Serif', 'serif'],
        'text.usetex': False,  # Deaktiviert bei LaTeX-Kompatibilität
        'figure.figsize': (10, 6),
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'lines.linewidth': 2.5,
        'lines.markersize': 10,
        'axes.labelsize': 12,
        'axes.titlesize': 14,
        'axes.facecolor': '#ffffff',  # Weißer Hintergrund
        'figure.facecolor': '#ffffff',  # Weißer Figure-Hintergrund
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'grid.alpha': 0.25,
        'grid.color': '#cccccc',
        'axes.edgecolor': '#333333',
        'axes.linewidth': 1.2
    }
    
    # Erweiterte, vibrant Farben für verschiedene Circuit-Typen
    COLORS = {
        'sequential': '#2E86AB',      # Tiefes Blau
        'parallel': '#A23B72',        # Magenta/Violett
        'grid': '#F18F01',            # Leuchtendes Orange
        'random': '#C73E1D',          # Tiefes Rot
        'iscas': '#06A77D',           # Türkis/Grün
        'benchmark': '#D62828',       # Helles Rot
        # Familien des verbesserten Messaufbaus (src/instances.py)
        'target_and': '#A23B72',
        'target_and_random': '#F18F01',
        'iscas85': '#2E86AB',
        'miter_self': '#06A77D',
        'miter_equiv': '#C73E1D',
        'scaling': '#8338EC',
    }

    # Läufe ohne verwertbares Ergebnis gehen nicht in Laufzeitstatistiken ein
    INVALID_STATUSES = ('TIMEOUT', 'ERROR', 'NO_OUTPUT')
    
    # Erweiterte Farbpalette für Fallback und Histogramme
    EXTENDED_COLORS = [
        '#2E86AB',  # Tiefes Blau
        '#A23B72',  # Magenta
        '#F18F01',  # Orange
        '#C73E1D',  # Rot
        '#06A77D',  # Türkis
        '#D62828',  # Helles Rot
        '#003049',  # Dunkelblau
        '#FB5607',  # Orange-Rot
        '#8338EC',  # Violett
        '#FFBE0B'   # Gold
    ]
    
    def __init__(self, results: List[ExperimentResult], output_dir: str = "."):
        """
        Initialisiert Visualizer
        
        Args:
            results: Liste von ExperimentResult Objekten
            output_dir: Ausgabeverzeichnis für Plots
        """
        plt.style.use('default')
        
        plt.rcParams.update(self.FONT_CONFIG)
        self.results = results
        self._multi_solver = len({getattr(r, 'solver_label', '') for r in results}) > 1
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._color_index = 0  # Für Fallback-Farbvergabe
    
    def _get_color(self, circuit_type: str, fallback_index: int = 0) -> str:
        """
        Gibt Farbe für Circuit-Typ zurück, mit vibranter Fallback-Palette
        
        Args:
            circuit_type: Circuit-Typ (key in COLORS dict)
            fallback_index: Index für Fallback-Farben wenn type nicht gefunden
        
        Returns:
            Hex-Farbcode
        """
        # Versuche zuerst den exakten Typ
        if circuit_type in self.COLORS:
            return self.COLORS[circuit_type]
        
        # Versuche lowercase
        circuit_type_lower = circuit_type.lower()
        if circuit_type_lower in self.COLORS:
            return self.COLORS[circuit_type_lower]
        
        # Fallback zu erweiterte Palette (niemals schwarz!)
        return self.EXTENDED_COLORS[fallback_index % len(self.EXTENDED_COLORS)]
    
    @staticmethod
    def load_results(json_path: str) -> List[ExperimentResult]:
        """Lädt Ergebnisse aus JSON-Datei"""
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        results = [ExperimentResult(**item) for item in data]
        return results
    
    def _label(self, r: ExperimentResult) -> str:
        """Gruppenname: Familie (bzw. Circuit-Typ älterer Daten), bei mehreren Solvern mit Solver-Präfix."""
        base = getattr(r, 'family', '') or r.circuit_type
        return f"{r.solver_label}:{base}" if self._multi_solver else base

    def _group_results(self) -> Dict[str, List[ExperimentResult]]:
        """Gruppiert die verwertbaren Läufe nach Familie (und Solver)."""
        grouped: Dict[str, List[ExperimentResult]] = {}
        for result in self.results:
            if getattr(result, 'status', '') in self.INVALID_STATUSES:
                continue
            grouped.setdefault(self._label(result), []).append(result)
        return grouped

    @staticmethod
    def _instance_stats(results: List[ExperimentResult], net: bool = False) -> List[Dict]:
        """Eine Zeile je Instanz: Gates, Median und 95-%-Bootstrap-CI der Laufzeit."""
        from src.measurement import bootstrap_ci
        by_name: Dict[str, List[ExperimentResult]] = {}
        for r in results:
            by_name.setdefault(r.circuit_name, []).append(r)
        rows = []
        for name, rs in by_name.items():
            values = [(r.runtime_net_ms if net and r.runtime_net_ms is not None else r.runtime_ms) for r in rs]
            lo, hi = bootstrap_ci(values)
            rows.append({'name': name, 'gates': rs[0].num_gates, 'n': len(values),
                         'median': float(np.median(values)), 'lo': lo, 'hi': hi})
        return sorted(rows, key=lambda x: x['gates'])

    def plot_runtime_vs_size(self, figsize: tuple = (12, 6)):
        """Median der Laufzeit je Instanz (mit 95-%-Konfidenzintervall) gegen die Circuit-Größe"""
        fig, ax = plt.subplots(figsize=figsize)
        has_plots = False
        for idx, (group, results) in enumerate(sorted(self._group_results().items())):
            rows = self._instance_stats(results)
            if not rows:
                continue
            x = [r['gates'] for r in rows]
            y = np.array([r['median'] for r in rows])
            err = np.array([[r['median'] - r['lo'] for r in rows], [r['hi'] - r['median'] for r in rows]])
            ax.errorbar(x, y, yerr=np.clip(err, 0, None), marker='o', capsize=3,
                        label=group, color=self._get_color(group.split(':')[-1], idx),
                        alpha=0.85, linewidth=1.8)
            has_plots = True
        ax.set_xlabel('Circuit Size (Number of Gates)', fontsize=12)
        ax.set_ylabel('Median runtime (ms), 95% CI', fontsize=12)
        ax.set_title('Runtime vs. Circuit Size', fontsize=14, fontweight='bold')
        if has_plots:
            ax.legend(loc='best', framealpha=0.95)
        ax.grid(True, alpha=0.25, linestyle='--')
        ax.set_xscale('log')
        ax.set_yscale('log')
        plt.tight_layout()
        return fig

    def plot_runtime_distribution(self, figsize: tuple = (12, 6)):
        """Plottet Runtime-Verteilung als Box-Plot"""
        fig, ax = plt.subplots(figsize=figsize)
        
        grouped = self._group_results()
        data = []
        labels = []
        colors = []
        
        for idx, circuit_type in enumerate(sorted(grouped.keys())):
            results = grouped[circuit_type]
            runtimes = [r.runtime_ms for r in results if r.runtime_ms > 0]
            if runtimes:
                data.append(runtimes)
                labels.append(circuit_type.upper()) # Direkt in Großbuchstaben für den Report-Look
                colors.append(self._get_color(circuit_type, idx))
        
        if not data:
            ax.text(0.5, 0.5, 'No data available', 
                    horizontalalignment='center', verticalalignment='center', 
                    transform=ax.transAxes, fontsize=14, color='gray')
            ax.set_title('Subgraph-SAT-Solver: Runtime Distribution', fontsize=14, fontweight='bold')
            return fig
            
        # Wir übergeben hier KEINE Labels direkt an boxplot, um den Versionskonflikt zu umgehen
        bp = ax.boxplot(data, patch_artist=True)
        
        # Stattdessen setzen wir die Ticks und Labels danach sauber auf die X-Achse
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(labels)
        
        # Färbe Boxen und Whisker mit vibranten Farben
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.75)
            patch.set_linewidth(1.5)
        
        # Färbe auch die Whisker und Medianlinien
        for whisker in bp['whiskers']:
            whisker.set(linewidth=1.5, color='#333333', alpha=0.6)
        for cap in bp['caps']:
            cap.set(linewidth=1.5, color='#333333', alpha=0.6)
        for median in bp['medians']:
            median.set(linewidth=2, color='#000000')
        
        ax.set_ylabel('Runtime (ms)', fontsize=12)
        ax.set_title('Subgraph-SAT-Solver: Runtime Distribution', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.25, axis='y', linestyle='--')
        ax.set_yscale('log')
        
        plt.tight_layout()
        return fig
    
    def plot_gates_vs_runtime(self, figsize: tuple = (12, 6)):
        """Gates gegen Laufzeit: Einzelläufe (blass) und Median je Instanz"""
        fig, ax = plt.subplots(figsize=figsize)
        has_plots = False
        for idx, (group, results) in enumerate(sorted(self._group_results().items())):
            color = self._get_color(group.split(':')[-1], idx)
            ax.scatter([r.num_gates for r in results], [r.runtime_ms for r in results],
                       color=color, alpha=0.18, s=30, linewidths=0)
            rows = self._instance_stats(results)
            ax.scatter([r['gates'] for r in rows], [r['median'] for r in rows], label=group,
                       color=color, alpha=0.9, s=70, edgecolors='#333333', linewidth=0.8)
            has_plots = True
        ax.set_xlabel('Number of Gates', fontsize=12)
        ax.set_ylabel('Runtime (ms)', fontsize=12)
        ax.set_title('Gates vs. Runtime (large markers: median per instance)', fontsize=14, fontweight='bold')
        if has_plots:
            ax.legend(loc='best', framealpha=0.95)
        ax.grid(True, alpha=0.25, linestyle='--')
        ax.set_xscale('log')
        ax.set_yscale('log')
        plt.tight_layout()
        return fig

    def plot_clauses_histogram(self, figsize: tuple = (12, 6)):
        """Histogramm der CNF-Klausel-Verteilung"""
        fig, ax = plt.subplots(figsize=figsize)
        
        grouped = self._group_results()
        has_plots = False  # Tracken, ob Daten geplottet wurden
        
        for idx, circuit_type in enumerate(sorted(grouped.keys())):
            results = grouped[circuit_type]
            clauses = [r.num_clauses for r in results]
            
            # Nur plotten, wenn die Liste nicht leer ist
            if clauses:
                ax.hist(clauses, alpha=0.65, label=circuit_type.capitalize(),
                       color=self._get_color(circuit_type, idx),
                       edgecolor='#333333', linewidth=1.2)
                has_plots = True
        
        ax.set_xlabel('Number of Clauses', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.set_title('Subgraph-SAT-Solver: CNF Clause Distribution', fontsize=14, fontweight='bold')
        
        # Nur Legende anzeigen, wenn auch Balken gezeichnet wurden
        if has_plots:
            ax.legend(loc='best', framealpha=0.95)
            
        ax.grid(True, alpha=0.25, axis='y', linestyle='--')
        
        plt.tight_layout()
        return fig
    
    def plot_performance_comparison(self, figsize: tuple = (12, 7)):
        """Vergleicht Performance verschiedener Circuit-Typen"""
        grouped = self._group_results()
        
        circuit_types = sorted(grouped.keys())
        colors = [self._get_color(ct, idx) for idx, ct in enumerate(circuit_types)]
        
        fig, axes = plt.subplots(1, 3, figsize=figsize)
        
        # Durchschnittliche Runtime
        runtimes = [np.median([r.runtime_ms for r in grouped[ct]]) for ct in circuit_types]
        bars1 = axes[0].bar(range(len(circuit_types)), runtimes, color=colors, edgecolor='#333333', linewidth=1.5, alpha=0.85)
        axes[0].set_ylabel('Median Runtime (ms)', fontsize=11)
        axes[0].set_title('Median Runtime', fontsize=12, fontweight='bold')
        axes[0].set_xticks(range(len(circuit_types)))
        axes[0].set_xticklabels(circuit_types, rotation=25, ha='right')
        axes[0].grid(True, alpha=0.25, axis='y', linestyle='--')
        
        # Durchschnittliche Gates
        gates = [np.mean([r.num_gates for r in grouped[ct]]) for ct in circuit_types]
        bars2 = axes[1].bar(range(len(circuit_types)), gates, color=colors, edgecolor='#333333', linewidth=1.5, alpha=0.85)
        axes[1].set_ylabel('Avg Gates', fontsize=11)
        axes[1].set_title('Average Gates', fontsize=12, fontweight='bold')
        axes[1].set_xticks(range(len(circuit_types)))
        axes[1].set_xticklabels(circuit_types, rotation=25, ha='right')
        axes[1].grid(True, alpha=0.25, axis='y', linestyle='--')
        
        # Durchschnittliche Clauses
        clauses = [np.mean([r.num_clauses for r in grouped[ct]]) for ct in circuit_types]
        bars3 = axes[2].bar(range(len(circuit_types)), clauses, color=colors, edgecolor='#333333', linewidth=1.5, alpha=0.85)
        axes[2].set_ylabel('Avg Clauses', fontsize=11)
        axes[2].set_title('Average Clauses', fontsize=12, fontweight='bold')
        axes[2].set_xticks(range(len(circuit_types)))
        axes[2].set_xticklabels(circuit_types, rotation=25, ha='right')
        axes[2].grid(True, alpha=0.25, axis='y', linestyle='--')
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def fit_exponent(sizes, times):
        """Potenzgesetz t = c * n^a per linearer Regression im Log-Log-Raum.
        Liefert (a, c, R^2) oder None bei zu wenigen Punkten."""
        x, y = np.asarray(sizes, float), np.asarray(times, float)
        ok = (x > 0) & (y > 0)
        if ok.sum() < 3 or len(set(x[ok])) < 3:
            return None
        lx, ly = np.log(x[ok]), np.log(y[ok])
        a, b = np.polyfit(lx, ly, 1)
        ss_res = float(np.sum((ly - (a * lx + b)) ** 2))
        ss_tot = float(np.sum((ly - ly.mean()) ** 2))
        return float(a), float(np.exp(b)), (1.0 - ss_res / ss_tot) if ss_tot > 0 else float('nan')

    def plot_scaling_analysis(self, figsize: tuple = None):
        """Je Gruppe: Median der Netto-Laufzeit (Rohzeit minus Prozessstart-Grundlast)
        gegen die Gate-Zahl, mit Potenzgesetz-Fit t ~ n^a.

        Die Netto-Zeit trennt die Solver-Arbeit von der Prozessstart-Grundlast
        (siehe baseline.json). Der Exponent ist nur aussagekräftig, wenn die
        Netto-Zeiten deutlich über dem Messrauschen der Grundlast liegen."""
        grouped = {g: r for g, r in self._group_results().items() if r}
        n = max(1, len(grouped))
        cols = 2 if n > 1 else 1
        rows_n = (n + cols - 1) // cols
        fig, axes = plt.subplots(rows_n, cols, figsize=figsize or (7 * cols, 4.5 * rows_n), squeeze=False)
        flat = axes.flatten()
        for idx, (group, results) in enumerate(sorted(grouped.items())):
            ax = flat[idx]
            color = self._get_color(group.split(':')[-1], idx)
            stats = self._instance_stats(results, net=True)
            sizes = [r['gates'] for r in stats]
            med = [r['median'] for r in stats]
            ax.errorbar(sizes, np.maximum(med, 1e-3),
                        yerr=np.clip(np.array([[r['median'] - r['lo'] for r in stats],
                                               [r['hi'] - r['median'] for r in stats]]), 0, None),
                        fmt='o', color=color, capsize=3, markeredgecolor='#333333')
            fit = self.fit_exponent(sizes, med)
            if fit:
                a, c, r2 = fit
                xs = np.logspace(np.log10(min(sizes)), np.log10(max(sizes)), 100)
                ax.plot(xs, c * xs ** a, '--', color=color, alpha=0.7, label=f'fit: t ~ n^{a:.2f} (R²={r2:.2f})')
                ax.legend(framealpha=0.95, loc='best')
            ax.set_xlabel('Gates', fontsize=11)
            ax.set_ylabel('Net runtime (ms)', fontsize=11)
            ax.set_title(group, fontsize=12, fontweight='bold')
            ax.set_xscale('log')
            ax.set_yscale('log')
            ax.grid(True, alpha=0.25, linestyle='--')
        for ax in flat[len(grouped):]:
            ax.axis('off')
        plt.tight_layout()
        return fig

    def plot_solver_comparison(self, figsize: tuple = (12, 6)):
        """Median der Laufzeit je Instanz und Solver (nur bei mehreren Solvern)."""
        fig, ax = plt.subplots(figsize=figsize)
        labels = sorted({r.solver_label for r in self.results})
        names = list(dict.fromkeys(r.circuit_name for r in self.results))
        width = 0.8 / max(1, len(labels))
        for k, label in enumerate(labels):
            med = []
            for name in names:
                v = [r.runtime_ms for r in self.results if r.solver_label == label
                     and r.circuit_name == name and r.status not in self.INVALID_STATUSES]
                med.append(float(np.median(v)) if v else np.nan)
            ax.bar(np.arange(len(names)) + k * width, med, width, label=label,
                   color=self.EXTENDED_COLORS[k % len(self.EXTENDED_COLORS)], edgecolor='#333333', linewidth=0.5)
        ax.set_xticks(np.arange(len(names)) + 0.4 - width / 2)
        ax.set_xticklabels(names, rotation=70, ha='right', fontsize=7)
        ax.set_ylabel('Median runtime (ms)')
        ax.set_yscale('log')
        ax.set_title('Solver comparison', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.25, axis='y', linestyle='--')
        plt.tight_layout()
        return fig

    def export_all_plots(self, formats: List[str] = ['svg', 'pdf']):
        """Exportiert alle Plots"""
        plots = [
            ('runtime_vs_size', self.plot_runtime_vs_size()),
            ('runtime_distribution', self.plot_runtime_distribution()),
            ('gates_vs_runtime', self.plot_gates_vs_runtime()),
            ('clauses_histogram', self.plot_clauses_histogram()),
            ('performance_comparison', self.plot_performance_comparison()),
            ('scaling_analysis', self.plot_scaling_analysis())
        ]
        if self._multi_solver:
            plots.append(('solver_comparison', self.plot_solver_comparison()))
        
        for name, fig in plots:
            for fmt in formats:
                filepath = self.output_dir / f"{name}.{fmt}"
                fig.savefig(filepath, format=fmt, bbox_inches='tight')
                print(f"✓ Saved: {filepath}")
            plt.close(fig)
    
    def create_summary_report(self, output_file: str = "report.txt"):
        """Erstellt Text-Report der Ergebnisse (Median, Quartile, Status, Korrektheit)"""
        from src.measurement import describe
        report = "=" * 70 + "\n"
        report += "SUBGRAPH-SAT-SOLVER EXPERIMENT REPORT\n"
        report += "=" * 70 + "\n\n"
        report += f"Total runs: {len(self.results)}\n"
        by_status: Dict[str, int] = {}
        for r in self.results:
            key = getattr(r, 'status', '') or 'n/a'
            by_status[key] = by_status.get(key, 0) + 1
        report += "Status: " + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())) + "\n"
        wrong = [r for r in self.results if getattr(r, 'correct', None) is False]
        invalid = [r for r in self.results if getattr(r, 'rep', 0) == 0 and
                   (getattr(r, 'model_valid', None) is False or getattr(r, 'circuit_valid', None) is False)]
        report += f"Unexpected results (status != expected): {len(wrong)}\n"
        report += f"Invalid models (CNF or circuit check failed): {len(invalid)}\n"

        for group, results in sorted(self._group_results().items()):
            runtimes = [r.runtime_ms for r in results if r.runtime_ms > 0]
            report += f"\n{group.upper()}\n" + "-" * 40 + "\n"
            report += f"  Runs: {len(results)}, instances: {len({r.circuit_name for r in results})}\n"
            if not runtimes:
                report += "  Keine gültigen Laufzeiten (Solver nicht gefunden oder alle Läufe fehlgeschlagen)\n"
                continue
            d = describe(runtimes)
            report += (f"  Median: {d['median_ms']:.2f} ms  (95% CI {d['median_ci_lo_ms']:.2f}-"
                       f"{d['median_ci_hi_ms']:.2f}), Q1/Q3: {d['q1_ms']:.2f}/{d['q3_ms']:.2f}\n")
            report += f"  Mean: {d['mean_ms']:.2f} ms  Std: {d['std_ms']:.2f} ms  Range: {d['min_ms']:.2f}-{d['max_ms']:.2f} ms\n"
            report += (f"  Avg Gates: {statistics.mean(r.num_gates for r in results):.1f}  "
                       f"Avg Clauses: {statistics.mean(r.num_clauses for r in results):.1f}\n")
            stats = self._instance_stats(results, net=True)
            fit = self.fit_exponent([x['gates'] for x in stats], [x['median'] for x in stats])
            if fit:
                report += f"  Scaling fit (net median): t ~ n^{fit[0]:.2f}, R²={fit[2]:.2f}\n"

        report += "\n" + "=" * 70 + "\n"
        output_path = self.output_dir / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n✓ Report saved to {output_path}")
        return report


def main():
    """Hauptfunktion zum Testen"""
    import sys
    
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_path = str(RESULTS_DIR / "experiment_results.json")
    
    if not Path(json_path).exists():
        print(f"Error: {json_path} not found")
        return
    
    print(f"Loading results from {json_path}...")
    results = ExperimentVisualizer.load_results(json_path)
    print(f"Loaded {len(results)} results")
    
    output_dir = Path(json_path).parent / "plots"
    visualizer = ExperimentVisualizer(results, output_dir=str(output_dir))
    
    print("\nGenerating plots...")
    visualizer.export_all_plots(formats=['svg', 'pdf'])
    
    print("\nGenerating report...")
    visualizer.create_summary_report()
    
    print("\n✓ All visualizations complete!")


if __name__ == "__main__":
    main()