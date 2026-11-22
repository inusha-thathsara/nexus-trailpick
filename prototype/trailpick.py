"""TrailPick core library: simulated warehouse, baseline routers and an ant-colony router.

Everything here is SIMULATION. Layout, demand and expiry parameters are labelled
assumptions (see run_experiments.py), not measurements from a real warehouse.

Layout (single-block, parallel aisles, depot at front-left):
    A aisles, aisle pitch P metres, aisle length L metres, cross aisles at the
    front (y=0) and back (y=L).  Nodes sit on a 1 m grid along every aisle.
"""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra


class Warehouse:
    def __init__(self, A=24, L=60, P=4.0):
        self.A, self.L, self.P = A, L, P
        self.N = A * (L + 1)

    def nid(self, a, y):
        return a * (self.L + 1) + y

    def build(self, congestion=None, block=None):
        """Return a sparse symmetric graph.
        congestion: {aisle: cost multiplier for walking inside that aisle}
        block:      (aisle, y) removes the aisle segment between y and y+1."""
        r, c, w = [], [], []
        for a in range(self.A):
            f = (congestion or {}).get(a, 1.0)
            for y in range(self.L):
                if block is not None and block == (a, y):
                    continue
                r.append(self.nid(a, y)); c.append(self.nid(a, y + 1)); w.append(f)
        for a in range(self.A - 1):
            for y in (0, self.L):
                r.append(self.nid(a, y)); c.append(self.nid(a + 1, y)); w.append(self.P)
        g = sp.coo_matrix((w, (r, c)), shape=(self.N, self.N)).tocsr()
        return g + g.T

    def dist_matrix(self, graph, nodes):
        d = dijkstra(graph, directed=False, indices=nodes)
        return d[:, nodes]

    def paths(self, graph, nodes):
        d, pred = dijkstra(graph, directed=False, indices=nodes, return_predecessors=True)
        return d, pred

    def xy(self, node):
        a, y = divmod(int(node), self.L + 1)
        return a * self.P, y


# ---------------------------------------------------------------- baselines
def tour_len(D, tour):
    t = np.asarray(tour)
    return float(D[t, np.roll(t, -1)].sum())


def nearest_neighbour(D):
    n = len(D)
    seen = {0}
    tour = [0]
    while len(tour) < n:
        cur = tour[-1]
        cand = [j for j in range(n) if j not in seen]
        nxt = min(cand, key=lambda j: D[cur, j])
        tour.append(nxt); seen.add(nxt)
    return tour


def s_shape_length(wh, picks):
    """Classic S-shape (traversal) heuristic length for a single block with the
    depot at the front of aisle 0.  picks: list of (aisle, y)."""
    byaisle = {}
    for a, y in picks:
        byaisle[a] = max(byaisle.get(a, 0), y)
    vis = sorted(byaisle)
    k = len(vis)
    amax = vis[-1]
    horiz = 2 * amax * wh.P
    vert = k * wh.L if k % 2 == 0 else (k - 1) * wh.L + 2 * byaisle[amax]
    return horiz + vert


def largest_gap_length(wh, picks):
    """Largest-gap heuristic (Hall 1993), single block, depot at front of aisle 0.
    First and last visited aisles are traversed fully; every aisle in between is
    entered from the front and from the back, skipping its largest gap."""
    byaisle = {}
    for a, y in picks:
        byaisle.setdefault(a, []).append(y)
    vis = sorted(byaisle)
    k = len(vis)
    if k == 1:
        return 2 * vis[0] * wh.P + 2 * max(byaisle[vis[0]])
    vert = 2 * wh.L                      # first and last aisle: full traversal
    for a in vis[1:-1]:
        ys = [0] + sorted(byaisle[a]) + [wh.L]
        gap = max(b - c for b, c in zip(ys[1:], ys[:-1]))
        vert += 2 * (wh.L - gap)
    return 2 * vis[-1] * wh.P + vert


def s_shape_polyline(wh, picks):
    byaisle = {}
    for a, y in picks:
        byaisle[a] = max(byaisle.get(a, 0), y)
    vis = sorted(byaisle)
    k = len(vis)
    pts = [(0, 0)]
    for i, a in enumerate(vis):
        x = a * wh.P
        if i == k - 1 and k % 2 == 1:
            pts += [(x, 0), (x, byaisle[a]), (x, 0)]
        elif i % 2 == 0:
            pts += [(x, 0), (x, wh.L)]
        else:
            pts += [(x, wh.L), (x, 0)]
    pts.append((0, 0))
    return pts


def two_opt(D, tour):
    t = list(tour)
    n = len(t)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a, b = t[i - 1], t[i]
                c, d = t[j], t[(j + 1) % n]
                if D[a, c] + D[b, d] < D[a, b] + D[c, d] - 1e-9:
                    t[i:j + 1] = reversed(t[i:j + 1])
                    improved = True
        # or-opt (move one node)
        for i in range(1, n):
            node = t[i]
            rest = t[:i] + t[i + 1:]
            base = tour_len(D, t)
            best, bp = base, None
            for p in range(1, len(rest) + 1):
                cand = rest[:p] + [node] + rest[p:]
                L = tour_len(D, cand)
                if L < best - 1e-9:
                    best, bp = L, cand
            if bp is not None:
                t = bp; improved = True
    return t


def held_karp(D):
    n = len(D)
    m = n - 1
    INF = float("inf")
    dp = np.full((1 << m, m), INF)
    for j in range(m):
        dp[1 << j, j] = D[0, j + 1]
    for mask in range(1, 1 << m):
        for j in range(m):
            if not (mask >> j) & 1 or dp[mask, j] == INF:
                continue
            for k in range(m):
                if (mask >> k) & 1:
                    continue
                nm = mask | (1 << k)
                v = dp[mask, j] + D[j + 1, k + 1]
                if v < dp[nm, k]:
                    dp[nm, k] = v
    full = (1 << m) - 1
    return min(dp[full, j] + D[j + 1, 0] for j in range(m))


# ------------------------------------------------------------- ant colony
def aco(D, groups=None, n_ants=20, iters=60, alpha=1.0, beta=3.0, rho=0.1,
        tau=None, tau_max=None, rng=None, init_tour=None):
    """Max-Min Ant System.  Node 0 is the depot.  `groups` (len N) lets several
    candidate nodes (e.g. batches of one SKU) share a group: the tour visits
    exactly one node of each group (generalised TSP).  Returns
    (best_tour, best_len, tau, tau_max, history)."""
    rng = rng or np.random.default_rng()
    N = len(D)
    groups = np.arange(N) if groups is None else np.asarray(groups)
    G = int(groups.max()) + 1
    eta = 1.0 / np.maximum(D, 0.5)
    if tau_max is None:
        # initial scale from a nearest-neighbour style estimate (per group)
        nn_len = _greedy_len(D, groups)
        tau_max = 1.0 / (rho * nn_len)
    tau_min = tau_max / (2.0 * N)
    if tau is None:
        tau = np.full((N, N), tau_max)
    best_len, best_tour, hist = np.inf, None, []
    if init_tour is not None:                      # colony remembers its incumbent route
        best_tour = np.asarray(init_tour)
        best_len = tour_len(D, best_tour)
    for _ in range(iters):
        W = (tau ** alpha) * (eta ** beta)
        visited = np.zeros((n_ants, G), bool)
        visited[:, 0] = True
        cur = np.zeros(n_ants, int)
        tours = np.zeros((n_ants, G), int)
        length = np.zeros(n_ants)
        for step in range(1, G):
            w = W[cur] * (~visited[:, groups])
            cs = np.cumsum(w, axis=1)
            r = rng.random((n_ants, 1)) * cs[:, -1:] * 0.999999
            nxt = (cs < r).sum(axis=1)
            nxt = np.minimum(nxt, N - 1)
            length += D[cur, nxt]
            tours[:, step] = nxt
            visited[np.arange(n_ants), groups[nxt]] = True
            cur = nxt
        length += D[cur, 0]
        i = int(np.argmin(length))
        if length[i] < best_len:
            best_len, best_tour = float(length[i]), tours[i].copy()
        hist.append(best_len)
        tau *= (1 - rho)
        dep = 1.0 / best_len if (len(hist) % 5 == 0) else 1.0 / length[i]
        src = best_tour if (len(hist) % 5 == 0) else tours[i]
        nxt_n = np.roll(src, -1)
        tau[src, nxt_n] += dep
        tau[nxt_n, src] += dep
        tau_max = 1.0 / (rho * best_len)
        tau_min = tau_max / (2.0 * N)
        np.clip(tau, tau_min, tau_max, out=tau)
    return list(best_tour), best_len, tau, tau_max, hist


def _greedy_len(D, groups):
    N = len(D)
    G = int(groups.max()) + 1
    seen = {0}
    cur, tot = 0, 0.0
    for _ in range(1, G):
        cand = [j for j in range(N) if groups[j] not in seen]
        nxt = min(cand, key=lambda j: D[cur, j])
        tot += D[cur, nxt]; seen.add(groups[nxt]); cur = nxt
    return tot + D[cur, 0]


def warm_start(tau, tau_max_old, D_old, D_new, stale_len_new, rho=0.1, thresh=0.05):
    """Local pheromone reset after a disruption: only trails whose edge cost
    changed by more than `thresh` are re-opened to exploration; the rest of the
    colony's memory is kept (cf. Eyckelhof & Snoek 2002)."""
    changed = np.abs(D_new - D_old) > thresh * np.maximum(D_old, 1.0)
    tmax = 1.0 / (rho * stale_len_new)
    tmin = tmax / (2.0 * len(D_new))
    t = np.clip(tau, tmin, tmax)
    t[changed] = tmax
    return t, tmax


# ---------------------------------------------------- multi-picker coordination
def s_shape_tour_order(wh, pts):
    """Return node permutation [0, i_1, ..., i_m] ordering `pts` along an S-shape traversal."""
    by_aisle = {}
    for idx, (a, y) in enumerate(pts, start=1):
        by_aisle.setdefault(a, []).append((y, idx))
    vis = sorted(by_aisle)
    order = [0]
    for i, a in enumerate(vis):
        items = sorted(by_aisle[a], key=lambda item: item[0], reverse=(i % 2 == 1))
        order.extend(idx for _, idx in items)
    return order


def trace_picker_path(wh, pts, tour, pick_dwell=8, speed=1.0):
    """Trace second-by-second (aisle, y, in_aisle) positions for a picker tour."""
    stops = [(0, 0)] + [pts[i - 1] for i in tour if i != 0] + [(0, 0)]
    traj = []
    for k in range(len(stops) - 1):
        a1, y1 = stops[k]
        a2, y2 = stops[k + 1]
        seg = []
        if a1 == a2:
            if y1 != y2:
                step = 1 if y2 > y1 else -1
                for y in range(y1 + step, y2 + step, step):
                    seg.append((a1, y, 0 < y < wh.L))
        else:
            cross_dist = abs(a2 - a1) * wh.P
            d_front = y1 + cross_dist + y2
            d_back = (wh.L - y1) + cross_dist + (wh.L - y2)
            y_cross = 0 if d_front <= d_back else wh.L
            if y1 != y_cross:
                step = 1 if y_cross > y1 else -1
                for y in range(y1 + step, y_cross + step, step):
                    seg.append((a1, y, 0 < y < wh.L))
            n_cross = int(round(cross_dist))
            for c in range(1, n_cross + 1):
                ac = int(round(a1 + (a2 - a1) * (c / n_cross)))
                seg.append((ac, y_cross, False))
            if y_cross != y2:
                step = 1 if y2 > y_cross else -1
                for y in range(y_cross + step, y2 + step, step):
                    seg.append((a2, y, 0 < y < wh.L))
        if speed == 1.0:
            traj.extend(seg)
        elif seg:
            n_sec = max(1, int(round(len(seg) / speed)))
            for s in range(n_sec):
                idx = min(int(s * speed), len(seg) - 1)
                traj.append(seg[idx])
        if k < len(stops) - 2 and pick_dwell > 0:
            traj.extend([(a2, y2, 0 < y2 < wh.L)] * int(round(pick_dwell)))
    return traj


def evaluate_wave_conflicts(wh, trajectories, prox_m=4, delay_per_conflict_s=1.5):
    """Compute narrow-aisle conflict seconds, distinct conflict episodes, and wave makespan."""
    K = len(trajectories)
    max_t = max((len(tr) for tr in trajectories), default=0)
    picker_delays = np.zeros(K, dtype=float)
    conflict_seconds = 0
    conflict_events = 0
    prev_pairs = set()
    for t in range(max_t):
        by_aisle = {}
        for p in range(K):
            tr = trajectories[p]
            if t < len(tr):
                a, y, in_aisle = tr[t]
                if in_aisle:
                    by_aisle.setdefault(a, []).append((p, y))
        cur_pairs = set()
        for active in by_aisle.values():
            m = len(active)
            if m < 2:
                continue
            for i in range(m):
                p, yp = active[i]
                for j in range(i + 1, m):
                    q, yq = active[j]
                    if abs(yp - yq) <= prox_m:
                        pair = (p, q) if p < q else (q, p)
                        cur_pairs.add(pair)
        if cur_pairs:
            conflict_seconds += len(cur_pairs)
            conflict_events += len(cur_pairs - prev_pairs)
            half = 0.5 * delay_per_conflict_s
            for p, q in cur_pairs:
                picker_delays[p] += half
                picker_delays[q] += half
        prev_pairs = cur_pairs
    makespan_s = max((len(trajectories[p]) + float(picker_delays[p]) for p in range(K)), default=0.0)
    return dict(conflict_seconds=int(conflict_seconds), conflict_events=int(conflict_events),
                makespan_s=float(makespan_s))


def update_occ_grid(occ_grid, traj, stagger_s=0, prox_m=4, time_win=6):
    """Record a scheduled picker's narrow-aisle occupancy into the shared traffic grid."""
    t_max, _, l_plus = occ_grid.shape
    L = l_plus - 1
    for dt, (a, y, in_aisle) in enumerate(traj):
        if not in_aisle:
            continue
        t = stagger_s + dt
        t0 = max(0, t - time_win)
        t1 = min(t_max, t + time_win + 1)
        if t0 >= t1:
            continue
        y0 = max(1, y - prox_m)
        y1 = min(L, y + prox_m + 1)
        if y0 < y1:
            occ_grid[t0:t1, a, y0:y1] += 1.0


def aco_traffic(wh, D, pts, occ_grid, n_ants=20, iters=45, alpha=1.0, beta=3.0,
                rho=0.1, penalty_w=18.0, pick_dwell=8, stagger_s=0, rng=None):
    """Time-windowed congestion-aware MAX-MIN Ant System avoiding occupied narrow aisles."""
    rng = rng or np.random.default_rng()
    N = len(D)
    if N <= 1:
        return [0], 0.0, None
    t_max = occ_grid.shape[0]
    occ_node = np.zeros((t_max, N), dtype=float)
    for j, (a, y) in enumerate(pts, start=1):
        occ_node[:, j] = occ_grid[:, a, y]

    nn_len = _greedy_len(D, np.arange(N))
    tau_max = 1.0 / (rho * max(nn_len, 1.0))
    tau_min = tau_max / (2.0 * N)
    tau = np.full((N, N), tau_max)
    best_obj, best_tour = np.inf, None
    cols = np.arange(N)
    ant_idx = np.arange(n_ants)

    for it in range(iters):
        tau_pow = tau ** alpha
        visited = np.zeros((n_ants, N), bool)
        visited[:, 0] = True
        cur = np.zeros(n_ants, int)
        tours = np.zeros((n_ants, N), int)
        length = np.zeros(n_ants, dtype=float)
        conflict_load = np.zeros(n_ants, dtype=float)
        t_cur = np.full(n_ants, float(stagger_s), dtype=float)

        for step in range(1, N):
            d_step = D[cur]
            t_arr = np.clip((t_cur[:, None] + d_step).astype(int), 0, t_max - 1)
            occ_arr = occ_node[t_arr, cols]
            d_eff = d_step + penalty_w * occ_arr
            eta = 1.0 / np.maximum(d_eff, 0.5)
            w = tau_pow[cur] * (eta ** beta) * (~visited)
            cs = np.cumsum(w, axis=1)
            r = rng.random((n_ants, 1)) * cs[:, -1:] * 0.999999
            nxt = (cs < r).sum(axis=1)
            nxt = np.minimum(nxt, N - 1)
            d_chosen = D[cur, nxt]
            length += d_chosen
            conflict_load += occ_arr[ant_idx, nxt]
            t_cur += d_chosen + pick_dwell
            tours[:, step] = nxt
            visited[ant_idx, nxt] = True
            cur = nxt

        length += D[cur, 0]
        obj = length + penalty_w * conflict_load
        i = int(np.argmin(obj))
        if obj[i] < best_obj:
            best_obj, best_tour = float(obj[i]), tours[i].copy()

        tau *= (1.0 - rho)
        dep = 1.0 / best_obj if ((it + 1) % 5 == 0) else 1.0 / obj[i]
        src = best_tour if ((it + 1) % 5 == 0) else tours[i]
        nxt_n = np.roll(src, -1)
        tau[src, nxt_n] += dep
        tau[nxt_n, src] += dep
        tau_max = 1.0 / (rho * best_obj)
        tau_min = tau_max / (2.0 * N)
        np.clip(tau, tau_min, tau_max, out=tau)

    fwd = list(best_tour)
    rev = [0] + fwd[1:][::-1]

    def _eval_cand(cand):
        tr = trace_picker_path(wh, pts, cand, pick_dwell=pick_dwell)
        ov = 0.0
        for dt, (a, y, in_aisle) in enumerate(tr):
            if in_aisle:
                t = stagger_s + dt
                if 0 <= t < t_max:
                    ov += occ_grid[t, a, y]
        plen = tour_len(D, cand)
        return plen + penalty_w * ov, plen, tr

    s_fwd, l_fwd, tr_fwd = _eval_cand(fwd)
    s_rev, l_rev, tr_rev = _eval_cand(rev)
    if s_rev < s_fwd:
        return rev, l_rev, tr_rev
    return fwd, l_fwd, tr_fwd


def batch_wave_spatially(all_picks, K, lines_per_picker=None):
    """Partition pooled wave picks into K balanced cart loads along an aisle-serpentine scan."""
    ordered = sorted(all_picks, key=lambda p: (p[0], p[1] if p[0] % 2 == 0 else -p[1]))
    n = len(ordered)
    batches = []
    for k in range(K):
        s = (k * n) // K
        e = ((k + 1) * n) // K
        seen = set()
        uniq = []
        for p in ordered[s:e]:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        batches.append(uniq)
    return batches
