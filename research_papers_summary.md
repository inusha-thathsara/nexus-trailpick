# Academic Research Synthesis: Teammate Papers Integration

**Project**: TrailPick — Ant-Colony Pick Routing with Expiry Awareness for Spreadsheet-Run Warehouses  
**Competition**: NEXUS 2026 Ideathon (Rotaract Club of University of Moratuwa)  
**Date**: November 2026  

---

## Executive Overview

This document synthesizes three primary research papers identified by the team, analyzing their methodology, empirical/theoretical findings, and concrete architectural mapping to the **TrailPick** system for the NEXUS Round 1 proposal.

| Paper | Domain | Key Finding | Direct Impact on TrailPick |
| :--- | :--- | :--- | :--- |
| **Bahrami, Aghezzaf, & Limère (2017)**<br>*(Procedia Manufacturing / FAIM)* | Warehouse Logistics & Simulation | Single-picker travel-minimizing heuristics (S-shape, largest gap) severely amplify **picker blocking** and order throughput time when multiple pickers share narrow aisles. | Directly validates our multi-picker simulation findings in Section 3.4 and justifies our time-windowed traffic-pheromone coordination layer. |
| **Reid et al. (2015)**<br>*(PNAS, 112(51))* | Biomimicry & Dynamic Optimization | Army ants (*Eciton burchellii*) dynamically adjust living bridges across gaps, balancing shortcut distance savings against the cost of sequestering workers into the structure. | Provides the biological foundation for TrailPick's **dual cost-benefit dials**: balancing detour length vs. expiry loss (FEFO) and detour length vs. aisle congestion. |
| **Wang, Menzel, et al. (2023)**<br>*(PNAS, 120(13))* | Animal Cognition & Spatial Mapping | Honeybee (*Apis mellifera*) waggle dance recruits infer true georeferenced spatial coordinates rather than rigidly executing polar vectors, navigating from arbitrary displacement origins. | Justifies replacing rigid sequential pick lists (polar vectors) with a topological metric graph, enabling arbitrary mid-tour re-routing when aisles are blocked. |

---

## 1. Evidence Paper: Picker Blocking in Manual Warehouses

### Citation
> **Bahrami, B., Aghezzaf, E.-H., & Limère, V. (2017).** *Using simulation to analyze picker blocking in manual order picking systems.* **Procedia Manufacturing**, 11, 1624–1631. [DOI: 10.1016/j.promfg.2017.07.303](https://doi.org/10.1016/j.promfg.2017.07.303)

### Core Findings & Methodology
1. **The Core Mechanism**:
   - In manual picker-to-parts warehouses handling high e-commerce volumes (smaller orders, tight dispatch deadlines), multiple human pickers operate simultaneously in narrow or wide aisles.
   - **Picker blocking** occurs whenever a picker’s movement or retrieval task is obstructed by another operator ahead in the same aisle, leading to substantial waiting queues and idle delay.
2. **The Heuristic Paradox**:
   - Traditional routing heuristics (S-shape, largest-gap, traversal) are mathematically designed to minimize *individual* travel distance. 
   - However, when deployed across concurrent pickers without fleet-level synchronization, these heuristics **funnel pickers into identical high-density picking aisles simultaneously**, causing convoy effects and dramatically increasing total system makespan and idle waiting times.
3. **Simulation Insights**:
   - The authors used full factorial discrete-event simulation to evaluate combinations of order batching rules and routing heuristics.
   - The study concluded that order-picking lead time is not a monotonic function of travel distance: **reducing travel distance can increase total order turnaround time if picker blocking is unmanaged**.

### Concrete Integration into TrailPick
- **Evidence Section (Section 02)**: We cite Bahrami et al. (2017) alongside Gue et al. (2006) to demonstrate that narrow-aisle congestion is not a minor edge case, but an established operational bottleneck in literature.
- **Multi-Picker Fleet Coordination (Section 3.4)**: Directly mirrors Bahrami’s findings:
  - In our 60-wave simulation (12 pickers in 24 aisles with 80/20 demand), independent S-shape produced **4,141 picker-seconds of conflict** per wave because all pickers swept aisles 0–4 in lockstep.
  - TrailPick’s time-windowed repulsive traffic pheromones add a $+3.7\%$ detour to individual routes but slash conflict time by **$84.9\%$** (to 182 picker-seconds) and reduce wave makespan from 23.9 min to 12.5 min, resolving the exact paradox identified by Bahrami et al.

---

## 2. Nature Lens Paper 1: Army Ant Living Bridges & Cost-Benefit Trade-Offs

### Citation
> **Reid, C. R., Lutz, M. J., Powell, S., Kao, A. B., Couzin, I. D., & Garnier, S. (2015).** *Army ants dynamically adjust living bridges in response to a cost–benefit trade-off.* **Proceedings of the National Academy of Sciences (PNAS)**, 112(51), 15613–15618. [DOI: 10.1073/pnas.1512241112](https://doi.org/10.1073/pnas.1512241112)

### Core Biological Findings
1. **Dynamic Architecture**:
   - Neotropical army ants (*Eciton burchellii*) forage in dense predatory swarms of up to 200,000 workers. When crossing irregular terrain with V-shaped deviations, ants link their bodies together using specialized tarsal claws to form "living bridges."
   - Previously thought to be static scaffolding, Reid et al. demonstrated that these bridges **actively migrate across space** over time.
2. **The Cost–Benefit Trade-Off**:
   - **Benefit**: Moving the bridge further away from the apex of the V-gap creates a shorter shortcut across the gap, significantly reducing the round-trip travel distance and transit time for the massive foraging column.
   - **Cost**: A longer bridge requires significantly more ants. Because the ants forming the bridge are physically immobilized, they are **sequestered from the active foraging and prey-carrying workforce**.
   - **Optimization Equilibrium**: The colony does not build the maximum possible shortcut. Instead, it dynamically halts bridge migration at an intermediate position where the marginal transit-time savings equal the marginal cost of sequestered worker capacity.
3. **Decentralized Information**:
   - No individual ant calculates the global cost-benefit function. Instead, local tactile stimuli (shear stress on holding legs and frequency of ants walking over their backs) govern when individual ants join or release from the living bridge.

### Concrete Integration into TrailPick
- **Nature Lens Section (Section 04)**:
  - While Argentine ants (*Linepithema humile*) provide our primary positive-feedback trail reinforcement mechanism, *Eciton burchellii* provides the theoretical grounding for **dynamic multi-objective cost-benefit trade-offs**:
    1. **FEFO vs. Walking Cost Dial**: Taking an older batch located far away (a shortcut to low inventory waste) "costs" extra picker walking meters. TrailPick's tolerance parameter ($k$) balances inventory write-off savings against physical walking effort.
    2. **Congestion Detour Dial**: Walking an extra 18 m around an occupied aisle "sequesters" slight extra travel effort from one picker to prevent immobilizing multiple pickers in a narrow-aisle queue.
- **Where the Analogy Breaks Down**:
  - Army ants pay the cost in biological biomass (immobilized bodies); warehouses pay the cost in human labor-hours. Real ants use tactile mechanoreceptors; TrailPick calculates marginal penalties on a central graph server.

---

## 3. Nature Lens Paper 2: Honeybee Spatial Map Inference from Waggle Dances

### Citation
> **Wang, C., Menzel, R., et al. (2023).** *Honey bees infer source location from the dances of returning foragers.* **Proceedings of the National Academy of Sciences (PNAS)**, 120(13), e2213068120. [DOI: 10.1073/pnas.2213068120](https://doi.org/10.1073/pnas.2213068120)

### Core Biological Findings
1. **Vector vs. Map Debate**:
   - For decades following Karl von Frisch (1967), the waggle dance was understood as a strict **polar flight vector**: communicating egocentric direction (angle relative to the sun/gravity) and flight distance (duration of the waggle run).
   - Critics argued that recruited bees were simply executing dead-reckoning vectors without understanding geographic topography.
2. **The Experimental Proof**:
   - Wang, Menzel, et al. captured newly recruited bees inside the hive after they observed waggle dances indicating a specific feeding site.
   - Instead of letting them fly from the hive, researchers displaced the recruits into an unfamiliar release location several hundred meters away and tracked their full flight paths using harmonic radar.
3. **The Cognitive Insight**:
   - Although the bees initially made a brief orientation flight along the communicated bearing, their trajectory quickly corrected: they **actively navigated toward the true geographic coordinates** of the food source in the terrain.
   - **Conclusion**: Honeybees translate symbolic dance signals into an internal, allocentric **cognitive spatial coordinate map**, enabling navigation toward target locations from *arbitrary starting origins* across the landscape.

### Concrete Integration into TrailPick
- **Solution Architecture & Nature Lens (Sections 03 & 04)**:
  - **Traditional Paper Pick Lists as "Blind Vectors"**: In a typical spreadsheet warehouse, a printed pick list is a static vector sequence (`Item 1 -> Item 2 -> Item 3`). If a picker encounters a blocked aisle at Item 2, the sequential vector breaks completely, leaving the picker disoriented and forced to backtrack.
  - **TrailPick as a "Cognitive Spatial Map"**: Inspired by Wang et al.'s findings, TrailPick abstracts the warehouse into a full topological coordinate space (`Warehouse.build()` over a 1 m grid). 
  - When an aisle obstruction occurs, the picker does not have to restart or abandon the sequence. The system calculates optimal paths from the picker's **current arbitrary coordinates**, translating target SKU identities into true spatial destinations rather than rigid list indices.
- **Where the Analogy Breaks Down**:
  - Bees infer coordinates through celestial compass cues, optic flow, and landscape memory; TrailPick computes Dijkstra shortest paths over a deterministic sparse graph on a computer.

---

## 4. Proposal Action Items Completed

1. **Section 02 (Evidence)**:
   - Added Bahrami, Aghezzaf, & Limère (2017) to the evidence matrix alongside de Koster (2007) and Gue et al. (2006).
2. **Section 04 (Nature Lens)**:
   - Formally framed TrailPick's nature lens as a unified bio-inspired framework:
     - **Foraging Path Reinforcement**: *Linepithema humile* (Argentine ant double-bridge positive feedback).
     - **Traffic & Mutual Avoidance**: *Lasius niger* (black garden ant crowding-induced repulsion).
     - **Dynamic Trade-off Optimization**: *Eciton burchellii* (army ant living bridge cost-benefit balance; Reid et al. 2015).
     - **Topological Coordinate Navigation**: *Apis mellifera* (honeybee spatial map inference; Wang et al. 2023).
3. **Section 10 (References)**:
   - Added full citations for Bahrami et al. (2017), Reid et al. (2015), and Wang et al. (2023) as references `[23]`, `[24]`, and `[25]`.
4. **Documents Generated & Verified**:
   - `research_papers_summary.md` (this standalone research brief).
   - Rebuilt `NEXUS_IDEATHON_TEAMNAME_R1.docx` and `NEXUS_IDEATHON_TEAMNAME_R1.pdf` (fully verified, 7 pages, grayscale typography/tables, full-color figures).
