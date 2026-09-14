"""Renders this template into a throwaway directory so generated file contents can be asserted.

The sibling ``copier_validators`` harness passes ``pretend=True``, which is enough to fire answer
validation but discards every rendered byte: copier computes the content, hands it to
``_render_allowed``, and drops it on return (see ``Worker._render_file``). Nothing on the returned
``Worker`` retains it, so asserting generated content requires a real render to disk.

The source is a git-free copy of the working tree rather than the repository itself. Pointing copier
at the repository would make it clone, and for a dirty tree it reconstructs the source by running
`git add -A` against the real work tree from inside that clone (`copier._vcs.clone`), which is both
slower and fragile in the presence of templated symlinks. Copying sidesteps it and picks up
uncommitted edits natively, which is what a test being driven red-green needs.
"""

import shutil
from pathlib import Path

import copier
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
COPIER_DATA_DIR = PROJECT_ROOT / "tests" / "copier_data"
# Copying the tree costs a fraction of a second; these are what would make it cost orders more.
_IGNORED_SOURCE_DIRS = shutil.ignore_patterns(
    ".git",
    ".venv",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    "coverage-report-pytest",
    "tmp",
)


def render_app(tmp_path: Path, *, data_file: str = "data4.yaml", **overrides: object) -> Path:
    """Instantiate this template from the current working tree and return the rendered app.

    ``data4.yaml`` is the default because it is the fixture that deploys as an executable and
    installs as a Windows service, so it exercises every platform-shaped part of the workflows.
    """
    source = tmp_path / "template-source"
    rendered = tmp_path / "rendered"
    _ = shutil.copytree(PROJECT_ROOT, source, symlinks=True, ignore=_IGNORED_SOURCE_DIRS)
    data: dict[str, object] = yaml.safe_load((COPIER_DATA_DIR / data_file).read_text(encoding="utf-8"))
    data.update(overrides)
    _ = copier.run_copy(
        str(source),
        str(rendered),
        data=data,
        defaults=True,
        unsafe=True,
        quiet=True,
    )
    return rendered
