"""Run every analysis section in order with the current Python interpreter."""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = [
    "01_curriculum_alignment/build_market_demand.py",
    "01_curriculum_alignment/gap_matrix.py",
    "02_career_archetypes/archetype_clusters.py",
    "03_transition_dynamics/markov_transitions.py",
    "03_transition_dynamics/sequence_mining.py",
    "04_hedonic_salary/hedonic_ols.py",
    "04_hedonic_salary/xgb_shap.py",
]

for script in SCRIPTS:
    start = time.time()
    print(f"\n=== {script} ===", flush=True)
    subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, check=True)
    print(f"--- done in {time.time() - start:.1f}s", flush=True)
