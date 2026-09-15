"""Every platform CI builds for must also reach the release, and vice versa.

These drifted apart once already: the CI matrices and the release asset list were separate literals,
a project added two ARM runners to the matrices only, and the release workflow went on shipping three
assets out of the five CI produced. Nothing failed -- the artifacts simply never reached the release.
"""

import re
from pathlib import Path

import pytest
import yaml

from .helpers import render_app

_ALL_PLATFORMS = ("linux-x64", "linux-arm64", "windows-x64", "windows-arm64")
_ARCHIVE_SUFFIX = {"linux-x64": "tar", "linux-arm64": "tar", "windows-x64": "zip", "windows-arm64": "zip"}


@pytest.fixture(name="rendered_app", scope="module")
def _rendered_app(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render_app(tmp_path_factory.mktemp("app"))


@pytest.fixture(name="ci_workflow", scope="module")
def _ci_workflow(rendered_app: Path) -> dict[str, object]:
    workflow: dict[str, object] = yaml.safe_load(
        (rendered_app / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
    )
    return workflow


@pytest.fixture(name="release_workflow_text", scope="module")
def _release_workflow_text(rendered_app: Path) -> str:
    return (rendered_app / ".github" / "workflows" / "release.yaml").read_text(encoding="utf-8")


def _matrix_platforms(workflow: dict[str, object], job_name: str) -> list[str]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    strategy = job["strategy"]
    assert isinstance(strategy, dict)
    matrix = strategy["matrix"]
    assert isinstance(matrix, dict)
    # `include` is the only key: an explicit `platform:` axis alongside it would restate every platform
    # a second time, and a typo in either copy silently yields an extra job with an empty `runs-on`
    # instead of a parse error.
    assert set(matrix) == {"include"}
    platforms: list[str] = []
    for entry in matrix["include"]:
        assert isinstance(entry, dict)
        assert set(entry) == {"platform", "runner"}
        platforms.append(str(entry["platform"]))
    return platforms


class TestCiMatrices:
    @pytest.mark.parametrize("job_name", ["unit-test-backend", "build-backend", "e2e-test"])
    def test_Given_every_platform_selected__Then_the_matrix_covers_them_all(
        self, ci_workflow: dict[str, object], job_name: str
    ) -> None:
        assert _matrix_platforms(ci_workflow, job_name) == list(_ALL_PLATFORMS)

    def test_Given_every_platform_selected__Then_windows_only_jobs_cover_only_windows(
        self, ci_workflow: dict[str, object]
    ) -> None:
        assert _matrix_platforms(ci_workflow, "e2e-test-windows-service") == ["windows-x64", "windows-arm64"]


class TestReleaseAssets:
    @pytest.mark.parametrize("platform", _ALL_PLATFORMS)
    def test_Given_a_built_platform__Then_its_artifact_is_downloaded_for_the_release(
        self, release_workflow_text: str, platform: str
    ) -> None:
        assert f"built-baz-{platform}" in release_workflow_text

    @pytest.mark.parametrize("platform", _ALL_PLATFORMS)
    def test_Given_a_built_platform__Then_its_asset_is_attached_to_the_release(
        self, release_workflow_text: str, platform: str
    ) -> None:
        assert f"baz-{platform}-v${{{{ needs.guard.outputs.version }}}}.{_ARCHIVE_SUFFIX[platform]}" in (
            release_workflow_text
        )

    def test_Given_a_windows_service_project__Then_the_installer_asset_names_its_platform(
        self, release_workflow_text: str
    ) -> None:
        assert "baz-windows-x64-installer" in release_workflow_text
        assert "baz--installer" not in release_workflow_text

    @pytest.mark.parametrize("workflow_name", ["release.yaml", "ci.yaml", "build-installer.yaml"])
    def test_Given_a_rendered_workflow__Then_no_jinja_tag_survived_into_it(
        self, rendered_app: Path, workflow_name: str
    ) -> None:
        # These templates are dense with {% raw %} regions, and a control tag placed inside one is
        # emitted verbatim instead of evaluated -- it renders, passes YAML parsing, and quietly
        # produces a wrong value rather than an error.
        text = (rendered_app / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8")
        assert "{%" not in text
        # `${{ ... }}` is GitHub Actions' own expression syntax and is expected; a `{{` without the
        # leading `$` is an unevaluated Jinja expression.
        assert re.search(r"(?<!\$)\{\{", text) is None

    def test_Given_an_org_specific_runner_label__Then_it_does_not_leak_into_asset_names(
        self, release_workflow_text: str
    ) -> None:
        # Asset names are platform ids precisely so a runner's core count -- an org's private
        # scaling decision -- stays out of a filename users download.
        assert "windows-arm-8core-v" not in release_workflow_text
        assert "ubuntu-arm-2core-v" not in release_workflow_text


def test_Given_the_same_answers__Then_ci_builds_exactly_what_the_release_ships(
    ci_workflow: dict[str, object], release_workflow_text: str
) -> None:
    # The invariant the split lists kept breaking: no platform may be built without being released,
    # and none may be released without being built.
    built = set(_matrix_platforms(ci_workflow, "build-backend"))
    released = {platform for platform in _ALL_PLATFORMS if f"built-baz-{platform}" in release_workflow_text}
    assert built == released


def test_Given_a_linux_only_project__Then_no_windows_platform_reaches_ci_or_release(
    tmp_path: Path,
) -> None:
    # The pnpm release-age task shells out to pnpm, which a render does not otherwise need; blanking
    # the patterns turns that task off via its own `when` rather than requiring pnpm on PATH.
    app = render_app(tmp_path, data_file="data5.yaml", pnpm_minimum_release_age_exclude="")
    ci_text = (app / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
    assert "windows-x64" not in ci_text
    assert "windows-arm64" not in ci_text
