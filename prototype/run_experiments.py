"""Preliminary simulation experiments for the NEXUS Round-1 proposal.
All parameters below are ASSUMPTIONS (labelled) - nothing is measured on a real warehouse.
Usage: python run_experiments.py [quick|multipick]
"""
import json, sys, time
import numpy as np
from trailpick import *

QUICK = len(sys.argv) > 1 and sys.argv[1] == "quick"
MULTIPICK_ONLY = len(sys.argv) > 1 and sys.argv[1] == "multipick"
N_ORD = 8 if QUICK else 60
SEED = 2026
rng_master = np.random.default_rng(SEED)

# ---- ASSUMED warehouse (about 96 m x ~70 m footprint incl. docks ~ 8,000 m2 gross)
WH = Warehouse(A=24, L=60, P=4.0)
N_SKU = 4000
Y_POS = np.arange(2, 59, 2)                      # 29 bay positions per aisle
POSITIONS = [(a, int(y)) for a in range(WH.A) for y in Y_POS]   # 696 positions
GRAPH = WH.build()


def make_storage(policy, rng):
    """SKU -> (aisle,y). random: uniform. class: top-20% demand SKUs (A class)
    in the 5 aisles nearest the depot, others spread over the rest."""
    loc = {}
    if policy == "random":
        idx = rng.integers(0, len(POSITIONS), N_SKU)
        for s in range(N_SKU):
            loc[s] = POSITIONS[idx[s]]
    else:
        nA = int(0.2 * N_SKU)
        near = [p for p in POSITIONS if p[0] < 5]
        far = [p for p in POSITIONS if p[0] >= 5]
        for s in range(N_SKU):
            pool = near if s < nA else far
            loc[s] = pool[rng.integers(0, len(pool))]
    return loc


def demand_probs(policy):
    p = np.ones(N_SKU)
    if policy == "class":                       # 80/20 demand (assumption)
        nA = int(0.2 * N_SKU)
        p[:nA] = 0.8 / nA; p[nA:] = 0.2 / (N_SKU - nA)
    return p / p.sum()


def sample_order(n, policy, loc, rng):
    skus = rng.choice(N_SKU, size=n, replace=False, p=demand_probs(policy))
    pts = list({loc[int(s)] for s in skus})      # merge same-bay lines
    return pts


def instance(pts):
    nodes = [WH.nid(0, 0)] + [WH.nid(a, y) for a, y in pts]
    return nodes, WH.dist_matrix(GRAPH, nodes)


def best_known(D, rng, extra_tours=()):
    n = len(D)
    cands = [two_opt(D, nearest_neighbour(D))]
    if extra_tours:
        cands.append(two_opt(D, list(extra_tours[0])))
    for _ in range(3):
        t = [0] + list(rng.permutation(np.arange(1, n)))
        cands.append(two_opt(D, t))
    return min(tour_len(D, t) for t in cands)


# =========================================================== EXP 1 static routing
def exp_static():
    out = {}
    for policy in ("random", "class"):
        loc = make_storage(policy, np.random.default_rng(SEED + 1))
        for n in (5, 10, 20, 30):
            rng = np.random.default_rng(SEED + n)
            rows = []
            for _ in range(N_ORD):
                pts = sample_order(n, policy, loc, rng)
                nodes, D = instance(pts)
                if len(D) < 3:
                    continue
                m = len(D)
                s_len = s_shape_length(WH, pts)
                lg_len = largest_gap_length(WH, pts)
                nn_t = nearest_neighbour(D); nn_len = tour_len(D, nn_t)
                lst_len = tour_len(D, list(range(m)))                     # as listed (random order)
                t0 = time.perf_counter()
                a_t, a_len, *_ = aco(D, rng=rng, iters=60)
                ms = (time.perf_counter() - t0) * 1000
                ref = held_karp(D) if m - 1 <= 10 else None
                if ref is None:
                    ref = best_known(D, rng, extra_tours=[a_t])
                    ref = min(ref, a_len)
                rows.append(dict(lines=m - 1, listed=lst_len, sshape=s_len, lgap=lg_len, nn=nn_len,
                                 aco=a_len, ref=ref, ms=ms))
            out[f"{policy}-{n}"] = rows
            print(policy, n, len(rows), "S", np.mean([r['sshape'] for r in rows]).round(0),
                  "NN", np.mean([r['nn'] for r in rows]).round(0),
                  "ACO", np.mean([r['aco'] for r in rows]).round(0),
                  "ref", np.mean([r['ref'] for r in rows]).round(0), flush=True)
    return out


# =========================================================== EXP 2 dynamic disruption
def exp_dynamic():
    # class-based storage: fast movers crowd the aisles nearest the depot, which is
    # where congestion realistically forms (assumption).
    loc = make_storage("class", np.random.default_rng(SEED + 1))
    rng = np.random.default_rng(SEED + 7)
    n = 20
    res = {"congestion": [], "block": []}
    curves = {"congestion": {"cold": [], "warm": []}, "block": {"cold": [], "warm": []}}
    for kind in ("congestion", "block"):
        for _ in range(N_ORD):
            pts = sample_order(n, "class", loc, rng)
            nodes, D0 = instance(pts)
            t0, l0, tau0, tm0, _ = aco(D0, rng=rng, iters=60)
            aisles = sorted({a for a, _ in pts if 0 < a < 5}) or sorted({a for a, _ in pts if a > 0})
            if kind == "congestion":       # two hot aisles become 5x slower to walk
                ks = rng.choice(aisles, size=min(2, len(aisles)), replace=False)
                g = WH.build(congestion={int(k): 5.0 for k in ks})
            else:                          # one aisle blocked part-way
                ak = int(rng.choice(aisles))
                g = WH.build(block=(ak, int(rng.integers(10, 50))))
            D1 = WH.dist_matrix(g, nodes)
            stale = tour_len(D1, t0)
            nn1 = tour_len(D1, nearest_neighbour(D1))
            ref_t, ref_l, *_ = aco(D1, rng=rng, iters=150, n_ants=40)
            ref = min(best_known(D1, rng, extra_tours=[ref_t]), ref_l)
            B = 8
            c_t, c_len, *_ , hc = aco(D1, rng=rng, iters=B)
            tauw, tmw = warm_start(tau0.copy(), tm0, D0, D1, stale)
            w_t, w_len, *_ , hw = aco(D1, rng=rng, iters=B, tau=tauw, tau_max=tmw, init_tour=t0)
            _, _, _, _, hc_full = aco(D1, rng=rng, iters=30)
            tauw2, tmw2 = warm_start(tau0.copy(), tm0, D0, D1, stale)
            _, _, _, _, hw_full = aco(D1, rng=rng, iters=30, tau=tauw2, tau_max=tmw2, init_tour=t0)
            res[kind].append(dict(stale=stale, nn=nn1, cold=c_len, warm=w_len, ref=ref))
            curves[kind]["cold"].append((np.array(hc_full) / ref).tolist())
            curves[kind]["warm"].append((np.array(hw_full) / ref).tolist())
        r = res[kind]
        print(kind, {k: (round(100 * (np.mean([x[k] / x['ref'] for x in r]) - 1), 1),
                         round(100 * (np.percentile([x[k] / x['ref'] for x in r], 90) - 1), 1))
                      for k in ("stale", "nn", "cold", "warm")}, flush=True)
    return res, curves


# =========================================================== EXP 3 expiry (FEFO)
def exp_fefo():
    """Each order line has B=3 batches with different remaining shelf life.
    Layout 'scattered': batches of one SKU sit in random bays (worst case, poorly
    managed receiving). Layout 'aisle': all batches of a SKU share one aisle
    (simple slotting rule). Policies differ in which batches a line may use."""
    rng = np.random.default_rng(SEED + 11)
    n, B = 15, 3
    pol = ["distance_only", "strict_fefo", "tol_7d", "tol_14d", "tol_30d"]
    rows = {f"{lay}:{p}": [] for lay in ("scattered", "aisle") for p in pol}
    for k in range(N_ORD):
        exps, cands = [], {"scattered": [], "aisle": []}
        for _l in range(n):
            exps.append(rng.choice(np.arange(5, 91), size=B, replace=False))
            cands["scattered"].append([POSITIONS[i] for i in rng.integers(0, len(POSITIONS), B)])
            a = int(rng.integers(0, WH.A))
            cands["aisle"].append([(a, int(Y_POS[j])) for j in rng.integers(0, len(Y_POS), B)])
        for lay in ("scattered", "aisle"):
            for p in pol:
                nodes, groups, meta = [WH.nid(0, 0)], [0], [(-1, -1)]
                for li in range(n):
                    e = exps[li]; emin = e.min()
                    if p == "distance_only": allowed = range(B)
                    elif p == "strict_fefo": allowed = [int(np.argmin(e))]
                    else:
                        tol = int(p.split("_")[1][:-1])
                        allowed = [b for b in range(B) if e[b] <= emin + tol]
                    for b in allowed:
                        a, y = cands[lay][li][b]
                        nodes.append(WH.nid(a, y)); groups.append(li + 1); meta.append((li, b))
                D = WH.dist_matrix(GRAPH, nodes)
                tour, L, *_ = aco(D, groups=np.array(groups), rng=rng, iters=60)
                picked = [meta[i] for i in tour if i != 0]
                excess = [exps[li][b] - exps[li].min() for li, b in picked]
                rows[f"{lay}:{p}"].append(dict(len=L, oldest=float(np.mean([x == 0 for x in excess])),
                                               excess=float(np.mean(excess))))
    return rows


# =========================================================== EXP 4 multi-picker fleet
def exp_multipicker():
    """K=12 concurrent pickers dispatched in a wave across the 24-aisle class-based warehouse."""
    loc = make_storage("class", np.random.default_rng(SEED + 1))
    rng = np.random.default_rng(SEED + 23)
    K, n = 12, 15
    pols = ("ind_sshape", "ind_aco", "traffic_aco", "batched_aco")
    res = {p: [] for p in pols}
    occ_grid = np.zeros((2400, WH.A, WH.L + 1), dtype=float)

    for _ in range(N_ORD):
        wave_orders = [sample_order(n, "class", loc, rng) for _ in range(K)]

        # 1. Independent S-shape
        dists, trajs = [], []
        for pts in wave_orders:
            _, D = instance(pts)
            t = s_shape_tour_order(WH, pts)
            dists.append(tour_len(D, t))
            trajs.append(trace_picker_path(WH, pts, t))
        ev = evaluate_wave_conflicts(WH, trajs)
        res["ind_sshape"].append(dict(mean_dist=float(np.mean(dists)), tot_dist=float(np.sum(dists)),
                                      conflict_s=ev["conflict_seconds"], conflict_ev=ev["conflict_events"],
                                      makespan_s=ev["makespan_s"]))

        # 2. Independent single-picker ACO
        dists, trajs = [], []
        for pts in wave_orders:
            _, D = instance(pts)
            t, l, *_ = aco(D, rng=rng, iters=30)
            dists.append(l)
            trajs.append(trace_picker_path(WH, pts, t))
        ev = evaluate_wave_conflicts(WH, trajs)
        res["ind_aco"].append(dict(mean_dist=float(np.mean(dists)), tot_dist=float(np.sum(dists)),
                                   conflict_s=ev["conflict_seconds"], conflict_ev=ev["conflict_events"],
                                   makespan_s=ev["makespan_s"]))

        # 3. Fixed orders + shared time-windowed traffic pheromones
        occ_grid.fill(0.0)
        dists, trajs = [], []
        for pts in wave_orders:
            _, D = instance(pts)
            t, l, tr = aco_traffic(WH, D, pts, occ_grid, n_ants=20, iters=30, penalty_w=18.0, rng=rng)
            dists.append(l)
            trajs.append(tr)
            update_occ_grid(occ_grid, tr)
        ev = evaluate_wave_conflicts(WH, trajs)
        res["traffic_aco"].append(dict(mean_dist=float(np.mean(dists)), tot_dist=float(np.sum(dists)),
                                       conflict_s=ev["conflict_seconds"], conflict_ev=ev["conflict_events"],
                                       makespan_s=ev["makespan_s"]))

        # 4. Spatial wave batching + shared traffic pheromones
        all_picks = [p for pts in wave_orders for p in pts]
        batches = batch_wave_spatially(all_picks, K, n)
        occ_grid.fill(0.0)
        dists, trajs = [], []
        for pts_b in batches:
            if not pts_b:
                continue
            _, D = instance(pts_b)
            t, l, tr = aco_traffic(WH, D, pts_b, occ_grid, n_ants=20, iters=30, penalty_w=18.0, rng=rng)
            dists.append(l)
            trajs.append(tr)
            update_occ_grid(occ_grid, tr)
        ev = evaluate_wave_conflicts(WH, trajs)
        res["batched_aco"].append(dict(mean_dist=float(np.mean(dists)), tot_dist=float(np.sum(dists)),
                                       conflict_s=ev["conflict_seconds"], conflict_ev=ev["conflict_events"],
                                       makespan_s=ev["makespan_s"]))

    for p in pols:
        rows = res[p]
        print("multipick", p,
              "dist", round(float(np.mean([r["mean_dist"] for r in rows])), 1),
              "c_s", round(float(np.mean([r["conflict_s"] for r in rows])), 1),
              "c_ev", round(float(np.mean([r["conflict_ev"] for r in rows])), 1),
              "mk", round(float(np.mean([r["makespan_s"] for r in rows])), 1), flush=True)
    return res


if __name__ == "__main__":
    t0 = time.time()
    if MULTIPICK_ONLY:
        with open("results.json", "r", encoding="utf8") as f:
            data = json.load(f)
        data["multipicker"] = exp_multipicker()
        print("multipick done", time.time() - t0, flush=True)
        with open("results.json", "w", encoding="utf8") as f:
            json.dump(data, f)
    else:
        r1 = exp_static(); print("static done", time.time() - t0, flush=True)
        r2, cur = exp_dynamic(); print("dynamic done", time.time() - t0, flush=True)
        r3 = exp_fefo(); print("fefo done", time.time() - t0, flush=True)
        r4 = exp_multipicker(); print("multipick done", time.time() - t0, flush=True)
        with open("results_quick.json" if QUICK else "results.json", "w", encoding="utf8") as f:
            json.dump(dict(static=r1, dynamic=r2, curves=cur, fefo=r3, multipicker=r4, n_orders=N_ORD, seed=SEED), f)
