# ============== WARNING ==============================================================================
# File is managed by a copier template. See .copier-managed-files.json for details.
#
# You are welcome to make changes to this file in your repo if they are custom to your project,
# but if the change should be shared with other projects, please backport it to the template repo.
# =====================================================================================================
import subprocess
import sys
from pathlib import Path


def run_copier_task(
    script_path: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- these are our own scripts
        [sys.executable, str(script_path), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
