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
from experiment_runner import ExperimentResult


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
        'benchmark': '#D62828'        # Helles Rot
    }
    
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
    
    def _group_results(self) -> Dict[str, List[ExperimentResult]]:
        """Gruppiert Ergebnisse nach Circuit-Typ"""
        grouped = {}
        for result in self.results:
            if result.circuit_type not in grouped:
                grouped[result.circuit_type] = []
            grouped[result.circuit_type].append(result)
        return grouped
    
    def plot_runtime_vs_size(self, figsize: tuple = (12, 6)):
        """Plottet Runtime vs. Circuit-Größe"""
        fig, ax = plt.subplots(figsize=figsize)
        
        grouped = self._group_results()
        has_plots = False  # Tracken, ob tatsächlich etwas geplottet wurde
        
        for idx, (circuit_type, results) in enumerate(sorted(grouped.items())):
            results_sorted = sorted(results, key=lambda r: r.num_gates)
            
            sizes = [r.num_gates for r in results_sorted]
            runtimes = [r.runtime_ms for r in results_sorted]
            
            if sizes and runtimes:
                ax.plot(sizes, runtimes, 
                       marker='o', 
                       label=circuit_type.capitalize(),
                       color=self._get_color(circuit_type, idx),
                       alpha=0.8,
                       linewidth=2.5)
                has_plots = True
        
        ax.set_xlabel('Circuit Size (Number of Gates)', fontsize=12)
        ax.set_ylabel('Runtime (ms)', fontsize=12)
        ax.set_title('Subgraph-SAT-Solver: Runtime vs. Circuit Size', fontsize=14, fontweight='bold')
        
        # Nur Legende anzeigen, wenn auch Daten da sind
        if has_plots:
            ax.legend(loc='best', framealpha=0.95)
            
        ax.grid(True, alpha=0.25, linestyle='--')
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
        """Plottet Anzahl Gates vs. Runtime (Scatter)"""
        fig, ax = plt.subplots(figsize=figsize)
        
        grouped = self._group_results()
        has_plots = False
        
        for idx, (circuit_type, results) in enumerate(sorted(grouped.items())):
            gates = [r.num_gates for r in results]
            runtimes = [r.runtime_ms for r in results]
            
            if gates and runtimes:
                ax.scatter(gates, runtimes,
                          label=circuit_type.capitalize(),
                          color=self._get_color(circuit_type, idx),
                          alpha=0.75,
                          s=120,
                          edgecolors='#333333',
                          linewidth=0.8)
                has_plots = True
        
        ax.set_xlabel('Number of Gates', fontsize=12)
        ax.set_ylabel('Runtime (ms)', fontsize=12)
        ax.set_title('Subgraph-SAT-Solver: Gates vs. Runtime', fontsize=14, fontweight='bold')
        
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
        runtimes = [np.mean([r.runtime_ms for r in grouped[ct]]) for ct in circuit_types]
        bars1 = axes[0].bar(range(len(circuit_types)), runtimes, color=colors, edgecolor='#333333', linewidth=1.5, alpha=0.85)
        axes[0].set_ylabel('Avg Runtime (ms)', fontsize=11)
        axes[0].set_title('Average Runtime', fontsize=12, fontweight='bold')
        axes[0].set_xticks(range(len(circuit_types)))
        axes[0].set_xticklabels([ct.capitalize() for ct in circuit_types], rotation=15)
        axes[0].grid(True, alpha=0.25, axis='y', linestyle='--')
        
        # Durchschnittliche Gates
        gates = [np.mean([r.num_gates for r in grouped[ct]]) for ct in circuit_types]
        bars2 = axes[1].bar(range(len(circuit_types)), gates, color=colors, edgecolor='#333333', linewidth=1.5, alpha=0.85)
        axes[1].set_ylabel('Avg Gates', fontsize=11)
        axes[1].set_title('Average Gates', fontsize=12, fontweight='bold')
        axes[1].set_xticks(range(len(circuit_types)))
        axes[1].set_xticklabels([ct.capitalize() for ct in circuit_types], rotation=15)
        axes[1].grid(True, alpha=0.25, axis='y', linestyle='--')
        
        # Durchschnittliche Clauses
        clauses = [np.mean([r.num_clauses for r in grouped[ct]]) for ct in circuit_types]
        bars3 = axes[2].bar(range(len(circuit_types)), clauses, color=colors, edgecolor='#333333', linewidth=1.5, alpha=0.85)
        axes[2].set_ylabel('Avg Clauses', fontsize=11)
        axes[2].set_title('Average Clauses', fontsize=12, fontweight='bold')
        axes[2].set_xticks(range(len(circuit_types)))
        axes[2].set_xticklabels([ct.capitalize() for ct in circuit_types], rotation=15)
        axes[2].grid(True, alpha=0.25, axis='y', linestyle='--')
        
        plt.tight_layout()
        return fig
    
    def plot_scaling_analysis(self, figsize: tuple = (14, 10)):
        """Analysiert Skalierungsverhalten"""
        grouped = self._group_results()
        
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        axes = axes.flatten()
        
        for idx, (circuit_type, results) in enumerate(sorted(grouped.items())):
            if idx >= 4:
                break
                
            # Sortiere nach Größe
            results_sorted = sorted(results, key=lambda r: r.num_gates)
            
            sizes = [r.num_gates for r in results_sorted]
            runtimes = [r.runtime_ms for r in results_sorted]
            
            ax = axes[idx]
            
            # Falls für diesen Typ gar keine Daten da sind, überspringen
            if not sizes or not runtimes:
                ax.text(0.5, 0.5, 'No data', 
                        horizontalalignment='center', verticalalignment='center', 
                        transform=ax.transAxes, color='gray')
                ax.set_title(f'{circuit_type.capitalize()} Scaling', fontsize=12, fontweight='bold')
                continue
            
            color = self._get_color(circuit_type, idx)
            
            ax.plot(sizes, runtimes, marker='o', color=color,
                   linewidth=2.5, markersize=10, markeredgecolor='#333333', 
                   markeredgewidth=1, alpha=0.85)
            
            has_legend_item = False
            
            # Fit curve if data is sufficient
            if len(sizes) > 2:
                try:
                    z = np.polyfit(np.log(sizes), np.log(runtimes), 1)
                    p = np.poly1d(z)
                    x_smooth = np.logspace(np.log10(min(sizes)), np.log10(max(sizes)), 100)
                    ax.plot(x_smooth, np.exp(p(np.log(x_smooth))), '--', alpha=0.65, 
                           color=color, linewidth=2, label='Fit (exp)')
                    has_legend_item = True
                except Exception:
                    pass
            
            ax.set_xlabel('Circuit Size', fontsize=11)
            ax.set_ylabel('Runtime (ms)', fontsize=11)
            ax.set_title(f'{circuit_type.capitalize()} Scaling', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.25, linestyle='--')
            
            # Nur eine Legende einblenden, wenn der Fit geklappt hat und das Label existiert
            if has_legend_item:
                ax.legend(framealpha=0.95)
        
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
        
        for name, fig in plots:
            for fmt in formats:
                filepath = self.output_dir / f"{name}.{fmt}"
                fig.savefig(filepath, format=fmt, bbox_inches='tight')
                print(f"✓ Saved: {filepath}")
            plt.close(fig)
    
    def create_summary_report(self, output_file: str = "report.txt"):
        """Erstellt Text-Report der Ergebnisse"""
        grouped = self._group_results()
        
        report = "=" * 70 + "\n"
        report += "SUBGRAPH-SAT-SOLVER EXPERIMENT REPORT\n"
        report += "=" * 70 + "\n\n"
        
        report += f"Total Experiments: {len(self.results)}\n\n"
        
        for circuit_type in sorted(grouped.keys()):
            results = grouped[circuit_type]
            runtimes = [r.runtime_ms for r in results if r.runtime_ms > 0]
            gates = [r.num_gates for r in results]
            clauses = [r.num_clauses for r in results]
            
            report += f"\n{circuit_type.upper()}\n"
            report += "-" * 40 + "\n"
            report += f"  Experiments: {len(results)}\n"
            report += f"  Avg Runtime: {statistics.mean(runtimes):.2f} ms\n"
            report += f"  Min Runtime: {min(runtimes):.2f} ms\n"
            report += f"  Max Runtime: {max(runtimes):.2f} ms\n"
            report += f"  Median Runtime: {statistics.median(runtimes):.2f} ms\n"
            if len(runtimes) > 1:
                report += f"  Std Dev: {statistics.stdev(runtimes):.2f} ms\n"
            report += f"  Avg Gates: {statistics.mean(gates):.1f}\n"
            report += f"  Avg Clauses: {statistics.mean(clauses):.1f}\n"
        
        report += "\n" + "=" * 70 + "\n"
        
        output_path = self.output_dir / output_file
        with open(output_path, 'w') as f:
            f.write(report)
        
        print(f"\n✓ Report saved to {output_path}")
        return report


def main():
    """Hauptfunktion zum Testen"""
    import sys
    
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_path = "experiment_results/experiment_results.json"
    
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