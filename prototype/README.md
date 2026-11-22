# TrailPick prototype (Round 1 simulation)

All results in the proposal come from this code (seeded, `SEED = 2026`). Every warehouse parameter is an assumption stated in `run_experiments.py`; nothing is field data.

```
pip install numpy scipy matplotlib pandas python-docx pymupdf   # pymupdf only for page previews
python run_experiments.py        # ~2 min -> results.json  (use `quick` for a smoke test)
python make_figures.py           # -> ../figures/*.png (color)
python make_figures.py --bw      # -> ../figures_bw/*.png (optional grayscale)
python build_proposal.py         # -> ../NEXUS_IDEATHON_TEAMNAME_R1.pdf (needs Microsoft Edge)
python build_proposal_docx.py    # -> ../NEXUS_IDEATHON_TEAMNAME_R1.docx (B&W document with ../figures/*.png graphs)
```

* `trailpick.py` - aisle-graph warehouse, S-shape, largest gap, nearest neighbour, 2-opt/or-opt, Held-Karp (exact, small orders), MAX-MIN ant-colony router with group (FEFO) constraints and warm start.
* `run_experiments.py` - static routing, blocked/congested aisles, FEFO trade-off.
* Rename `TEAM` / `UNI` at the top of `build_proposal.py` and `build_proposal_docx.py` before generating the final proposal.
