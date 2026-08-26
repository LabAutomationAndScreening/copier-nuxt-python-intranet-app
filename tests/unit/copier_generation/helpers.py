from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ANSWER_SET_DIR = PROJECT_ROOT / "tests" / "copier_data"
# Everything copier needs to render the template. `_tasks` scripts under src/ are intentionally absent because
# generation runs with --skip-tasks.
SNAPSHOT_CONTENTS = ("copier.yml", "extensions", "template")
