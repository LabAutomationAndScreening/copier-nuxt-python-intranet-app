import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.unit.copier_generation.helpers import ANSWER_SET_DIR
from tests.unit.copier_generation.helpers import PROJECT_ROOT
from tests.unit.copier_generation.helpers import SNAPSHOT_CONTENTS


@pytest.fixture(scope="session")
def template_snapshot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copy the template out of the git working tree so copier renders the current files.

    Copier resolves a git repository source to a committed ref, so pointing it at PROJECT_ROOT would silently
    test the last commit rather than the working tree. A snapshot with no .git directory is used as-is.
    """
    snapshot = tmp_path_factory.mktemp("template-snapshot")
    for relative_path in SNAPSHOT_CONTENTS:
        source = PROJECT_ROOT / relative_path
        if source.is_dir():
            _ = shutil.copytree(source, snapshot / relative_path)
        else:
            _ = shutil.copy2(source, snapshot / relative_path)
    return snapshot


@pytest.fixture(scope="session")
def generated_repo(template_snapshot: Path, tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    generated_by_answer_set: dict[str, Path] = {}

    def _generate(answer_set_name: str) -> Path:
        if answer_set_name in generated_by_answer_set:
            return generated_by_answer_set[answer_set_name]
        destination = tmp_path_factory.mktemp(answer_set_name.removesuffix(".yaml"))
        result = subprocess.run(  # noqa: S603 -- the template source and answer sets are all our own files
            [
                sys.executable,
                "-m",
                "copier",
                "copy",
                "--trust",
                "--skip-tasks",
                "--quiet",
                "--data-file",
                str(ANSWER_SET_DIR / answer_set_name),
                "--data",
                f"python_version={platform.python_version()}",
                str(template_snapshot),
                str(destination),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"copier failed for {answer_set_name}: {result.stderr}"
        generated_by_answer_set[answer_set_name] = destination
        return destination

    return _generate
