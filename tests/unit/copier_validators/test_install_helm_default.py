import pytest

from .helpers import rendered_answers


class TestWhenInstallHelmIsLeftUnanswered:
    @pytest.mark.parametrize(
        ("deploy_as_executable", "expected_install_helm"),
        [
            pytest.param(False, True, id="served-app-gets-pinned-helm"),
            pytest.param(True, False, id="standalone-executable-has-no-chart"),
        ],
    )
    def test_Then_it_defaults_to_the_opposite_of_deploy_as_executable(
        self, deploy_as_executable: bool, expected_install_helm: bool
    ) -> None:
        answers = rendered_answers(deploy_as_executable=deploy_as_executable)

        assert answers["install_helm"] is expected_install_helm
