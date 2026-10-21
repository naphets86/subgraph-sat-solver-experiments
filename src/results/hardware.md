# Hardware- und Softwareumgebung der Messungen

Umgebung, in der die Tests und Experimente der Projekte `subgraph-sat-solver`, `csubgraph` und `subgraph-sat-solver-experiments` am 11.10.2026 ausgeführt wurden. Es handelt sich um eine virtuelle Maschine in der Cloud, nicht um einen physischen Rechner.

## Prozessor

| Merkmal | Wert |
|---|---|
| Architektur | x86_64 |
| Bitbreite | 64 Bit (die CPU kann zusätzlich 32-Bit-Code ausführen) |
| Byte-Reihenfolge | Little Endian |
| Modell | Intel(R) Xeon(R) Processor @ 2.80 GHz |
| Sockets | 1 |
| Kerne pro Socket | 1 |
| Threads pro Kern | 1 |
| CPUs insgesamt | 1 |
| Adressbreite | 46 Bit physisch, 48 Bit virtuell |
| L2-Cache | 1 MiB (1 Instanz) |
| L3-Cache | 33 MiB (1 Instanz) |

## Speicher

| Merkmal | Wert |
|---|---|
| Arbeitsspeicher | 3,9 GiB |
| Swap | keiner |

## Software

| Komponente | Version |
|---|---|
| Betriebssystem | Linux, Kernel 6.18.44 (glibc 2.39) |
| Python | CPython 3.12.3 |
| NumPy | 2.4.4 |
| Matplotlib | 3.10.8 |
| C++-Compiler | g++ (C++17, `-O2 -Wall -Wextra`) |
| Zeitgeber | `time.perf_counter_ns` (monoton, Auflösung 1 ns) |

## Hinweise für die Interpretation der Messwerte

- **Ein einziger Kern:** Solver und Messprozess teilen sich die CPU. Das kann die gemessenen Laufzeiten leicht verzerren.
- **Wenig Arbeitsspeicher, kein Swap:** Die Adjazenzmatrix der Reduktion wächst quadratisch mit der Literalzahl. Bei sehr großen Instanzen (z. B. `TargetAND_m10000`) kann der Speicher knapp werden. Ob dies der Grund für den Abbruch des Full-Laufs war, wurde nicht geprüft.
- **Build ohne `-march=native`:** Die Binaries wurden ohne cmake direkt mit g++ gebaut. Die CMake-Konfiguration des Solvers setzt dagegen `-O3 -march=native`. Die Laufzeiten sind daher mit Messungen aus einem CMake-Build nur eingeschränkt vergleichbar.
- **Virtuelle Maschine:** Die Taktrate und die Cache-Angaben sind die Werte, die die VM meldet. Die tatsächlich zugeteilte Rechenzeit kann schwanken.
