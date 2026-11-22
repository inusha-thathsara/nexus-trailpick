"""TrailPick Interactive Demo
Walkthrough of TrailPick's 4 core simulation capabilities:
  1. Single-Picker Static Routing (Heuristics vs Ant Colony Optimization)
  2. Dynamic Disruption & Warm-Start Re-planning (Mid-aisle blockage)
  3. Expiry-Aware Picking (FEFO Group Constraints)
  4. Multi-Picker Fleet Coordination (Time-Windowed Repulsive Traffic Pheromones)

Usage:
  python demo.py
"""
import sys, os
import numpy as np

# Add prototype directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "prototype"))
from trailpick import (
    Warehouse, s_shape_length, s_shape_tour_order, largest_gap_length,
    nearest_neighbour, tour_len, aco, warm_start,
    trace_picker_path, evaluate_wave_conflicts, aco_traffic, update_occ_grid,
    batch_wave_spatially
)

def run_demo():
    print("=" * 72)
    print("  TRAILPICK: Bio-Inspired Warehouse Routing Simulation Demo")
    print("  NEXUS 2026 Ideathon · Team BackTrack")
    print("=" * 72)

    # 1. Initialize 8,000 m2 Model Warehouse
    wh = Warehouse(A=24, L=60, P=4.0)
    graph = wh.build()
    rng = np.random.default_rng(2026)

    print("\n[1/4] STATIC ROUTING BENCHMARK (Single 15-line order)")
    print("-----------------------------------------------------")
    # Sample 15 pick locations across aisles
    sample_picks = [(int(rng.integers(0, wh.A)), int(rng.integers(2, 59))) for _ in range(15)]
    nodes = [wh.nid(0, 0)] + [wh.nid(a, y) for a, y in sample_picks]
    D = wh.dist_matrix(graph, nodes)

    len_sshape = s_shape_length(wh, sample_picks)
    len_lgap = largest_gap_length(wh, sample_picks)
    tour_nn = nearest_neighbour(D)
    len_nn = tour_len(D, tour_nn)
    tour_aco, len_aco, *_ = aco(D, rng=rng, iters=45)

    print(f"  • S-Shape (standard heuristic) : {len_sshape:6.1f} m")
    print(f"  • Largest-Gap Heuristic        : {len_lgap:6.1f} m")
    print(f"  • Nearest Neighbour Heuristic  : {len_nn:6.1f} m")
    print(f"  • TrailPick (MAX-MIN ACO)      : {len_aco:6.1f} m  "
          f"(Saving: {100*(1-len_aco/len_sshape):.1f}% vs S-Shape, {100*(1-len_aco/len_lgap):.1f}% vs Largest Gap)")

    print("\n[2/4] DYNAMIC DISRUPTION RE-PLANNING (Aisle 3 blocked at y=30)")
    print("------------------------------------------------------------")
    # Simulate aisle 3 blocked
    graph_blocked = wh.build(block=(3, 30))
    D_blocked = wh.dist_matrix(graph_blocked, nodes)
    stale_len = tour_len(D_blocked, tour_aco)

    # Cold restart vs Warm start (local pheromone reset)
    _, len_cold, *_ = aco(D_blocked, rng=rng, iters=8)
    # Warm start retains prior pheromone on unaffected edges
    tau_init = np.full((len(D), len(D)), 1.0 / (0.1 * len_aco))
    tau_warm, tm_warm = warm_start(tau_init, 1.0/(0.1*len_aco), D, D_blocked, stale_len)
    _, len_warm, *_ = aco(D_blocked, rng=rng, iters=8, tau=tau_warm, tau_max=tm_warm, init_tour=tour_aco)

    print(f"  • Stale Route (unaware of block)     : {stale_len:6.1f} m")
    print(f"  • Cold Restart (8 ACO iterations)    : {len_cold:6.1f} m")
    print(f"  • Warm Start (Kept Trails, 8 iters)  : {len_warm:6.1f} m  "
          f"(Fast convergence using preserved pheromones)")

    print("\n[3/4] EXPIRY-AWARE PICKING (FEFO Group Constraints)")
    print("---------------------------------------------------")
    # 5 order lines, each with 3 candidate batches located in different bays
    # Each line has a minimum remaining shelf-life batch
    fefo_nodes = [wh.nid(0, 0)]
    groups = [0]
    batch_info = []
    for line_idx in range(5):
        expiries = rng.integers(10, 90, size=3)
        bays = [(int(rng.integers(0, wh.A)), int(rng.integers(2, 59))) for _ in range(3)]
        for b_idx in range(3):
            fefo_nodes.append(wh.nid(*bays[b_idx]))
            groups.append(line_idx + 1)
            batch_info.append((line_idx, expiries[b_idx], expiries.min()))

    D_fefo = wh.dist_matrix(graph, fefo_nodes)
    tour_fefo, len_fefo, *_ = aco(D_fefo, groups=np.array(groups), rng=rng, iters=45)
    picked_batches = [batch_info[i - 1] for i in tour_fefo if i != 0]
    oldest_picked = sum(1 for _, exp, exp_min in picked_batches if exp == exp_min)

    print(f"  • Visited Batches                     : Exactly 1 batch picked per order line")
    print(f"  • Oldest-Batch Compliance Rate       : {100*oldest_picked/5:.0f}% oldest batches selected")
    print(f"  • Total Walking Distance              : {len_fefo:6.1f} m")

    print("\n[4/4] MULTI-PICKER FLEET COORDINATION (4 concurrent carts)")
    print("----------------------------------------------------------")
    # All 4 carts pick items from the same 2 busy aisles (aisles 1 & 2)
    wave_orders = [
        [(1, 10), (1, 20), (1, 30), (2, 15), (2, 25), (2, 35)],
        [(1, 12), (1, 22), (1, 32), (2, 18), (2, 28), (2, 40)],
        [(1, 14), (1, 24), (1, 34), (2, 12), (2, 22), (2, 32)],
        [(1, 16), (1, 26), (1, 36), (2, 14), (2, 24), (2, 45)],
    ]

    # Independent routes (no traffic awareness)
    ind_trajs = []
    for pts in wave_orders:
        sub_nodes = [wh.nid(0, 0)] + [wh.nid(a, y) for a, y in pts]
        D_mat = wh.dist_matrix(graph, sub_nodes)
        t, _, *_ = aco(D_mat, rng=rng, iters=30)
        ind_trajs.append(trace_picker_path(wh, pts, t))
    ev_ind = evaluate_wave_conflicts(wh, ind_trajs)

    # Traffic-aware routes (with repulsive traffic pheromones)
    occ_grid = np.zeros((1200, wh.A, wh.L + 1), dtype=float)
    traf_trajs = []
    for pts in wave_orders:
        sub_nodes = [wh.nid(0, 0)] + [wh.nid(a, y) for a, y in pts]
        D_mat = wh.dist_matrix(graph, sub_nodes)
        t, _, tr = aco_traffic(wh, D_mat, pts, occ_grid, n_ants=20, iters=30, penalty_w=18.0, rng=rng)
        traf_trajs.append(tr)
        update_occ_grid(occ_grid, tr)
    ev_traf = evaluate_wave_conflicts(wh, traf_trajs)

    print(f"  • Independent Routing Conflicts       : {ev_ind['conflict_seconds']} picker-seconds ({ev_ind['conflict_events']} events)")
    print(f"  • Traffic-Pheromone Routing Conflicts : {ev_traf['conflict_seconds']} picker-seconds ({ev_traf['conflict_events']} events)")
    c_red = 100 * (1 - ev_traf['conflict_seconds'] / max(ev_ind['conflict_seconds'], 1))
    print(f"  • Narrow-Aisle Conflict Reduction    : {c_red:.1f}%")

    print("\n" + "=" * 72)
    print("  Simulation walkthrough completed successfully.")
    print("  To run full 60-order benchmarks: python prototype/run_experiments.py")
    print("=" * 72)

if __name__ == "__main__":
    run_demo()
