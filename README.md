# TrailPick 🐜📦

**Bio-Inspired Warehouse Routing & Fleet Coordination Simulator**  
*Developed for the NEXUS 2026 Ideathon (Rotaract Club of University of Moratuwa) · Team BackTrack*

---

## 📌 Overview

In mid-sized warehouses that rely on spreadsheets or older Warehouse Management Systems (WMS), order picking accounts for up to **55% of total operating expenses**, with travel and walking consuming over **50% of picking time** ([de Koster et al., 2007](https://doi.org/10.1016/j.ejor.2006.07.009); [Masae et al., 2020](https://doi.org/10.1016/j.ijpe.2020.107748)).

Traditional static heuristics (like S-Shape or Largest Gap) create three critical floor problems:
1. **Inefficient Paths:** Pickers walk back and forth along aisles without location-aware optimization.
2. **Fragility to Disruptions:** A route planned in the morning becomes invalid when an aisle is obstructed by a forklift, restocking pallet, or congestion.
3. **Inventory Spoilage:** Pickers grab the nearest item rather than the earliest-expiring batch, causing older stock to expire on racks.
4. **Fleet Blocking (Narrow-Aisle Congestion):** When multiple pickers enter the floor simultaneously, single-picker heuristics funnel all carts into the same fast-mover aisles, causing convoy jams and idle waiting ([Bahrami et al., 2017](https://doi.org/10.1016/j.promfg.2017.07.303); [Gue et al., 2006](https://doi.org/10.1080/07408170600807466)).

**TrailPick** is a Python simulation and routing engine inspired by collective multi-agent animal foraging that addresses all four challenges without requiring expensive robots, RFID grids, or invasive worker tracking.

---

## 🌿 Nature-Inspired Principles (The Biomimetic Framework)

| Organism | Natural Phenomenon | TrailPick Algorithmic Mapping |
| :--- | :--- | :--- |
| **Argentine Ant**<br>*(Linepithema humile)* | **Positive Trail Feedback**<br>Ants choosing shorter paths complete round trips faster and lay more pheromone, reinforcing optimal shortcuts ([Goss et al., 1989](https://doi.org/10.1007/BF00366405)). | **MAX-MIN Ant System (MMAS)** over a 1 m topological grid graph, finding shortest pick sequences within 50 ms. |
| **Black Garden Ant**<br>*(Lasius niger)* | **Crowding-Induced Diversion**<br>Ants experiencing high encounter rates on a crowded trail divert traffic onto alternate branches ([Dussutour et al., 2004](https://doi.org/10.1038/nature02534)). | **Repulsive Traffic Pheromones** that add virtual impedance to planned aisle-occupancy windows, steering trailing carts into uncongested aisles. |
| **Army Ant**<br>*(Eciton burchellii)* | **Dynamic Living Bridge Trade-offs**<br>Ants dynamically lengthen living bridges across gaps, balancing travel distance savings against the cost of sequestering workers into the structure ([Reid et al., 2015](https://doi.org/10.1073/pnas.1512241112)). | **Dual Cost–Benefit Dials**: (1) The FEFO tolerance dial ($k$) balancing extra walking against inventory waste; (2) The $+18\text{ m}$ detour penalty balancing individual travel against fleet waiting queues. |
| **Honeybee**<br>*(Apis mellifera)* | **Cognitive Spatial Map Inference**<br>Foragers translate waggle dances into georeferenced spatial coordinates rather than rigid polar vectors, allowing navigation from arbitrary displacement origins ([Wang et al., 2023](https://doi.org/10.1073/pnas.2213068120)). | **Topological Metric Graph Re-planning**: Unlike rigid sequential paper pick lists, TrailPick re-plans remaining stops from the picker's *current arbitrary coordinates* when an aisle is blocked. |

---

## 🏗️ Warehouse Model Specification

The simulation models the representative facility specified in the NEXUS problem statement:
* **Footprint:** $\sim 8,000\text{ m}^2$ gross ($\sim 6,700\text{ m}^2$ racked storage plus docks and staging).
* **Grid Graph:** 24 parallel storage aisles ($A = 24$), $60\text{ m}$ aisle length ($L = 60$), $4\text{ m}$ aisle pitch ($P = 4.0$).
* **Cross-Aisles:** Two cross-aisles at the front ($y = 0$) and back ($y = 60$). Depot located at front-left $(0, 0)$.
* **Inventory:** 4,000 SKUs distributed across 696 rack positions (29 bay positions per aisle).
* **Demand Profiles:**
  * **Random Storage:** Uniform pick probability across all aisles.
  * **Class-Based (80/20):** Top 20% high-velocity SKUs clustered in the 5 aisles closest to the depot (generating 80% of order lines).

---

## 🚀 Core Modules

### 1. Static Single-Picker Routing (`trailpick.aco`)
Implements MAX-MIN Ant System (MMAS; [Stützle & Hoos, 2000](https://doi.org/10.1016/S0167-739X(00)00043-1)) with transition probability $P_{ij} \propto \tau_{ij}^\alpha \cdot \eta_{ij}^\beta$ ($\alpha = 1$, $\beta = 3$, evaporation $\rho = 0.1$), benchmarked against:
* **S-Shape (Traversal):** Alternating full aisle traverses.
* **Largest-Gap Heuristic:** Skipping the largest unpicked gap in interior aisles ([Hall, 1993](https://doi.org/10.1080/07408179308964319)).
* **Nearest Neighbour:** Greedy closest-bay selection.
* **Held-Karp Exact DP & 2-Opt/Or-Opt:** Reference bounds.

### 2. Dynamic Disruption & Warm Re-planning (`trailpick.warm_start`)
When an aisle is blocked mid-way or congested by restocking:
* **Local Pheromone Reset:** Only edges whose traversal cost changed by $>5\%$ are reset to $\tau_{\max}$; unaffected edges retain colony memory ([Eyckelhof & Snoek, 2002](https://doi.org/10.1007/3-540-45724-0_3)).
* **Incumbent Seeding:** Seeds the solver with the prior route, guaranteeing that re-planning within 8 iterations achieves $\le 1.9\%$ excess over best-known (vs. $7.7\%$ for the stale route).

### 3. Expiry-Aware Picking / FEFO (`trailpick.aco` with group constraints)
Formulates batch selection as a **Generalized TSP (GTSP)**:
* Each order line has $B = 3$ candidate batches with varying remaining shelf lives.
* Ant colony visits exactly one candidate batch per order line.
* A manager-adjustable tolerance dial ($k$ days) selects batches within $\text{min\_expiry} + k$, balancing food/medicine waste prevention against extra walking.

### 4. Multi-Picker Fleet Coordination (`trailpick.aco_traffic` & `batch_wave_spatially`)
Simulates concurrent multi-cart operations ($K = 12$ pickers):
* **Second-by-second trajectory tracing** with $1.0\text{ m/s}$ walking speed and $8\text{ s}$ pick dwell.
* **Proximity Conflict Evaluation:** Tracks simultaneous occupancy within $\pm 4\text{ m}$ inside narrow storage aisles.
* **Time-Windowed Repulsive Traffic Pheromones:** Adds virtual impedance to occupied segments over time windows $t \pm 6\text{ s}$.
* **Spatial Wave Batching ($m$-TSP):** Partitions pooled wave lines into balanced cart loads along an aisle serpentine scan.

---

## 📊 Benchmark Results Summary

### Single-Picker Static Routing (60 Seeded Orders / Cell)
* **Vs. S-Shape:** $19.5\% \text{ to } 29.1\%$ tour distance reduction.
* **Vs. Nearest Neighbour:** $3.9\% \text{ to } 9.8\%$ tour distance reduction.
* **Vs. Largest Gap:** $3.2\% \text{ to } 9.0\%$ tour distance reduction.
* **Runtime:** $\le 59\text{ ms}$ per order on standard laptop CPU.

### Multi-Picker Wave Coordination (60 Waves, $K = 12$ Concurrent Pickers)
*Based on 80/20 class-based storage and 15 lines per picker:*

| Fleet Policy | Order Assignment | Mean Tour / Picker | Conflict Time / Wave | Wave Makespan |
| :--- | :--- | :--- | :--- | :--- |
| **Independent S-Shape** | Fixed orders | 530 m | 4,141 picker-seconds | 23.9 min |
| **Independent ACO** | Fixed orders | 470 m | 1,207 picker-seconds | 14.9 min |
| **TrailPick + Traffic Pheromones** | Fixed orders | 487 m (+3.7%) | **182 picker-seconds (-84.9%)** | **12.5 min (-16.3%)** |
| **TrailPick + Wave Batching + Traffic** | Pooled ($m$-TSP) | **178 m (-62.1%)** | **66 picker-seconds (-94.5%)** | **10.5 min (-29.8%)** |

---

## ⚡ Quick Start

### 1. Prerequisites & Installation
Requires Python 3.9+:
```bash
git clone <YOUR_REPO_URL>
cd <REPO_FOLDER>
pip install -r requirements.txt
```

### 2. Run the Interactive Demo
Runs a fast (~2 second) end-to-end simulation walkthrough:
```bash
python demo.py
```

### 3. Run the Full Benchmarks
To reproduce all 60-order static, dynamic disruption, FEFO expiry, and multi-picker fleet experiments:
```bash
python prototype/run_experiments.py
```
*(Results are saved to `prototype/results.json`).*

To run a fast sanity check (8 orders/waves):
```bash
python prototype/run_experiments.py quick
```

---

## 📁 Repository Structure

```
├── README.md                     # Comprehensive project documentation
├── requirements.txt              # Minimal dependencies (numpy, scipy)
├── demo.py                       # Interactive CLI walkthrough demo
├── research_papers_summary.md    # Detailed academic synthesis of cited papers
└── prototype/
    ├── trailpick.py              # Core simulation engine and algorithms
    ├── run_experiments.py        # Seeded experimental test suite
    └── results.json              # Full 60-order empirical benchmark output
```

---

## 🔒 Privacy by Design
TrailPick coordinates pick carts **per pick list and cart position**, with no personal worker identifiers, no biometric sensors, and no speed-based worker scoring. All dispatch adjustments comply with the principles of Sri Lanka's **Personal Data Protection Act (No. 9 of 2022)** and international **ILO / EU-OSHA** recommendations on algorithmic worker management.

---

## 👥 Team BackTrack
* **University:** University of Moratuwa  
* **Event:** NEXUS 2026 Ideathon — Round 1  
* **Focus Areas:** 02 AI & Data-Driven Optimization (Primary), 03 Exception Handling, 05 Sustainability
