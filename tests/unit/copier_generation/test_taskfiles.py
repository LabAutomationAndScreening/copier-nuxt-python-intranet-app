import json
import random
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.unit.copier_generation.helpers import ANSWER_SET_DIR

TASK_NAMES_BY_ANSWER_SET = {
    # has_backend, backend_uses_graphql, frontend_uses_graphql, not deploy_as_executable
    "data1.yaml": frozenset(
        {
            "build-frontend",
            "codegen",
            "copier-update",
            "dev-backend",
            "dev-frontend",
            "gen-backend-graphql-client",
            "gen-backend-openapi-client",
            "gen-frontend-graphql-client",
            "gen-frontend-openapi-client",
            "gen-openapi-snapshot",
            "preview-frontend",
            "prune-copier-rejects",
            "run-stack",
        }
    ),
    # no backend, not deploy_as_executable
    "data2.yaml": frozenset(
        {
            "build-frontend",
            "copier-update",
            "dev-frontend",
            "preview-frontend",
            "prune-copier-rejects",
            "run-stack",
        }
    ),
    # has_backend, no graphql on either side, not deploy_as_executable
    "data3.yaml": frozenset(
        {
            "build-frontend",
            "codegen",
            "copier-update",
            "dev-backend",
            "dev-frontend",
            "gen-backend-openapi-client",
            "gen-frontend-openapi-client",
            "gen-openapi-snapshot",
            "preview-frontend",
            "prune-copier-rejects",
            "run-stack",
        }
    ),
    # has_backend, no graphql on either side, deploy_as_executable
    "data4.yaml": frozenset(
        {
            "build-executable",
            "build-frontend",
            "codegen",
            "copier-update",
            "copy-frontend-static",
            "dev-backend",
            "dev-frontend",
            "gen-backend-openapi-client",
            "gen-frontend-openapi-client",
            "gen-openapi-snapshot",
            "preview-frontend",
            "prune-copier-rejects",
            "reload-frontend-in-stack",
            "run-backend-entrypoint",
            "run-stack",
        }
    ),
    # has_backend, no graphql on either side, deploy_as_executable
    "data5.yaml": frozenset(
        {
            "build-executable",
            "build-frontend",
            "codegen",
            "copier-update",
            "copy-frontend-static",
            "dev-backend",
            "dev-frontend",
            "gen-backend-openapi-client",
            "gen-frontend-openapi-client",
            "gen-openapi-snapshot",
            "preview-frontend",
            "prune-copier-rejects",
            "reload-frontend-in-stack",
            "run-backend-entrypoint",
            "run-stack",
        }
    ),
}
DOCKER_STACK_ANSWER_SETS = ("data1.yaml", "data2.yaml", "data3.yaml")
EXECUTABLE_STACK_ANSWER_SETS = ("data4.yaml", "data5.yaml")


def _task_names(repo: Path) -> frozenset[str]:
    """Ask Task itself to enumerate the tasks, which also proves the taskfiles are parseable.

    Task fails the whole listing on unparsable YAML, an unresolvable include, or a name collision between two
    flattened includes, so a successful listing is a stronger guarantee than parsing the YAML directly.
    """
    result = subprocess.run(
        ["task", "--list-all", "--json"],  # noqa: S607 -- resolving `task` from PATH is how the devcontainer and CI both provide it
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"`task --list-all` failed in {repo}: {result.stderr}"
    return frozenset(entry["name"] for entry in json.loads(result.stdout)["tasks"])


def _taskfile_paths(repo: Path) -> list[Path]:
    return sorted((repo / ".config" / "taskfiles").iterdir())


@pytest.mark.parametrize("answer_set_name", TASK_NAMES_BY_ANSWER_SET.keys())
def test_When_app_generated_Then_task_names_match_the_answer_set(
    generated_repo: Callable[[str], Path], answer_set_name: str
):
    repo = generated_repo(answer_set_name)

    actual_task_names = _task_names(repo)

    assert actual_task_names == TASK_NAMES_BY_ANSWER_SET[answer_set_name]


def test_When_answer_sets_enumerated_Then_every_one_has_expected_task_names():
    answer_set_names = frozenset(path.name for path in ANSWER_SET_DIR.glob("*.yaml"))

    assert answer_set_names == frozenset(TASK_NAMES_BY_ANSWER_SET.keys())


@pytest.mark.parametrize("answer_set_name", DOCKER_STACK_ANSWER_SETS)
def test_When_app_generated_without_deploy_as_executable_Then_only_the_compose_stack_is_present(
    generated_repo: Callable[[str], Path], answer_set_name: str
):
    repo = generated_repo(answer_set_name)

    taskfile_names = [path.name for path in _taskfile_paths(repo)]
    compose_commands = (repo / ".config" / "taskfiles" / "docker-stack.yaml").read_text()
    pyinstaller_taskfiles = [path.name for path in _taskfile_paths(repo) if "pyinstaller" in path.read_text()]

    assert "docker-stack.yaml" in taskfile_names
    assert "docker compose up" in compose_commands
    assert "executable-stack.yaml" not in taskfile_names
    assert pyinstaller_taskfiles == []


@pytest.mark.parametrize("answer_set_name", EXECUTABLE_STACK_ANSWER_SETS)
def test_When_app_generated_with_deploy_as_executable_Then_only_the_executable_stack_is_present(
    generated_repo: Callable[[str], Path], answer_set_name: str
):
    repo = generated_repo(answer_set_name)

    taskfile_names = [path.name for path in _taskfile_paths(repo)]
    executable_commands = (repo / ".config" / "taskfiles" / "executable-stack.yaml").read_text()

    assert "executable-stack.yaml" in taskfile_names
    assert "pyinstaller.spec --noconfirm" in executable_commands
    assert "docker-stack.yaml" not in taskfile_names


def test_When_app_generated_Then_no_jinja_delimiter_survives_in_a_taskfile(generated_repo: Callable[[str], Path]):
    answer_set_name = random.choice(list(TASK_NAMES_BY_ANSWER_SET.keys()))
    repo = generated_repo(answer_set_name)

    taskfiles = _taskfile_paths(repo)
    files_with_jinja = [path.name for path in taskfiles if "{%" in path.read_text()]

    assert taskfiles != []
    assert files_with_jinja == []


def test_When_app_generated_Then_the_root_shim_defines_no_commands_of_its_own(
    generated_repo: Callable[[str], Path],
):
    answer_set_name = random.choice(list(TASK_NAMES_BY_ANSWER_SET.keys()))
    repo = generated_repo(answer_set_name)

    shim = (repo / "Taskfile.yaml").read_text()

    assert "includes:" in shim
    assert "tasks:" not in shim
    assert "cmds:" not in shim
