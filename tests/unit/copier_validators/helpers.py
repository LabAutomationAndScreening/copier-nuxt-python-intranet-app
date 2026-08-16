"""Drives copier's own answer validation so copier.yml validators can be asserted.

``pretend=True`` skips file writes and tasks but still validates; ``vcs_ref="HEAD"``
auto-includes dirty working-tree changes, so uncommitted validator edits are picked up.
"""

import contextlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import copier

if TYPE_CHECKING:
    from collections.abc import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Minimal answers that turn the Windows-service questions on and satisfy every
# no-default question in that branch; tests override the single field under test.
_INSTALLER_ANSWERS: dict[str, object] = {
    "repo_name": "baz",
    "repo_org_name": "foo",
    "description": "Installer validator test fixture",
    "python_version": "3.12",
    "python_package_registry": "PyPI",
    "pull_from_ecr": False,
    "install_aws_ssm_port_forwarding_plugin": False,
    "has_backend": True,
    "is_circuit_python_driver": False,
    "backend_rest_api_description": "Test API",
    "deploy_as_executable": True,
    "use_windows_in_ci": True,
    "install_as_windows_service": True,
    "installer_manufacturer": "Foo Corp",
    "installer_upgrade_code": "3b9d1f6a-2c84-4e7b-9a1f-6d5c4b3a2e10",
    "sign_installer": False,
}


def validate_installer_answers(**overrides: object) -> None:
    data = {**_INSTALLER_ANSWERS, **overrides}
    with tempfile.TemporaryDirectory() as tmp:
        _ = copier.run_copy(
            str(PROJECT_ROOT),
            tmp,
            data=data,
            defaults=True,
            unsafe=True,
            quiet=True,
            vcs_ref="HEAD",
            pretend=True,
        )


@contextlib.contextmanager
def render_installer_project(**overrides: object) -> Iterator[Path]:
    """Fully render the template to a temp dir (files written) and yield its root, for asserting rendered content."""
    data = {**_INSTALLER_ANSWERS, **overrides}
    with tempfile.TemporaryDirectory() as tmp:
        copier.run_copy(
            str(PROJECT_ROOT),
            tmp,
            data=data,
            defaults=True,
            unsafe=True,
            quiet=True,
            vcs_ref="HEAD",
        )
        yield Path(tmp)
