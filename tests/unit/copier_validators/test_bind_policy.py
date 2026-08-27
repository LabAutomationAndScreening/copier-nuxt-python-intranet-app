from pathlib import Path

import pytest

from .helpers import render_installer_project

_CONFIGURABLE = ["configurable_loopback_default", "configurable_all_default"]
_FORCED = ["loopback_only", "all_interfaces_only"]


def _read(root: Path) -> tuple[str, str, str, str]:
    return (
        (root / "backend/src/backend_api/jinja_constants.py").read_text(),
        (root / "installer/scripts/install-service.ps1").read_text(),
        (root / "installer/scripts/remove-service.ps1").read_text(),
        (root / "installer/wix/Product.wxs").read_text(),
    )


@pytest.mark.parametrize("policy", _CONFIGURABLE)
def test_configurable_policies_expose_choice_and_firewall(policy: str):
    with render_installer_project(windows_service_bind_policy=policy) as root:
        consts, install_ps, remove_ps, wxs = _read(root)

    # parser default stays loopback; the operator's choice is applied via --host at install time
    assert 'DEFAULT_DEPLOYED_HOST = "127.0.0.1"' in consts
    assert "$AllowRemote" in install_ps
    assert "--host" in install_ps
    assert "New-NetFirewallRule" in install_ps
    assert 'throw "Failed to remove existing firewall rule' in install_ps
    assert "Remove-NetFirewallRule" in remove_ps
    assert "Write-Warning" in remove_ps
    assert 'Id="ALLOW_REMOTE"' in wxs
    assert "BindAddressDlg" in wxs


def test_configurable_all_default_defaults_allow_remote_on():
    with render_installer_project(windows_service_bind_policy="configurable_all_default") as root:
        wxs = (root / "installer/wix/Product.wxs").read_text()
    assert '<Property Id="ALLOW_REMOTE" Value="1"' in wxs


def test_configurable_loopback_default_defaults_allow_remote_off():
    with render_installer_project(windows_service_bind_policy="configurable_loopback_default") as root:
        wxs = (root / "installer/wix/Product.wxs").read_text()
    assert '<Property Id="ALLOW_REMOTE" Value="0"' in wxs


def test_loopback_only_binds_local_and_has_no_bind_ui_or_firewall():
    with render_installer_project(windows_service_bind_policy="loopback_only") as root:
        consts, install_ps, remove_ps, wxs = _read(root)

    assert 'DEFAULT_DEPLOYED_HOST = "127.0.0.1"' in consts
    assert "$AllowRemote" not in install_ps
    assert "@('--host', '127.0.0.1')" in install_ps
    assert "New-NetFirewallRule" not in install_ps
    assert "Remove-NetFirewallRule" not in remove_ps
    assert "ALLOW_REMOTE" not in wxs
    assert "BindAddressDlg" not in wxs


def test_all_interfaces_only_forces_bind_all_and_opens_firewall_without_ui():
    with render_installer_project(windows_service_bind_policy="all_interfaces_only") as root:
        consts, install_ps, remove_ps, wxs = _read(root)

    assert 'DEFAULT_DEPLOYED_HOST = "0.0.0.0"' in consts
    assert "$AllowRemote" not in install_ps
    assert "@('--host', '0.0.0.0')" in install_ps
    assert "New-NetFirewallRule" in install_ps  # always opened when forced remote
    assert 'throw "Failed to remove existing firewall rule' in install_ps
    assert "Remove-NetFirewallRule" in remove_ps
    assert "Write-Warning" in remove_ps
    assert "ALLOW_REMOTE" not in wxs
    assert "BindAddressDlg" not in wxs
