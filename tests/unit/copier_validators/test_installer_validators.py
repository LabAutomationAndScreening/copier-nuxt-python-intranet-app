import pytest

from .helpers import validate_installer_answers


class TestInstallerManufacturerValidator:
    @pytest.mark.parametrize(
        "value",
        [
            "Foo Corp",
            "Acme, Inc.",
            "lab-sync",
            "ABC 123 Ltd",
        ],
    )
    def test_accepts_plain_names(self, value: str) -> None:
        validate_installer_answers(installer_manufacturer=value)

    @pytest.mark.parametrize(
        "value",
        [
            "",  # required: no default, empty breaks the WiX Manufacturer attribute
            'Ac"me',  # closes the double-quoted XML attribute and Python f-string
            "Ac\\me",  # RTF control char; also escapes in the Python f-string
            "a<b",  # invalid raw XML
            "x&y",  # invalid raw XML entity
        ],
    )
    def test_rejects_characters_unsafe_in_xml_python_and_rtf(self, value: str) -> None:
        with pytest.raises(ValueError, match="installer_manufacturer"):
            validate_installer_answers(installer_manufacturer=value)


class TestWindowsServiceOrgPrefixValidator:
    @pytest.mark.parametrize(
        "value",
        [
            "",  # help says "leave blank for no prefix"
            "lab-sync-",
            "destroyer-",
            "Org_",
        ],
    )
    def test_accepts_blank_and_plain_prefixes(self, value: str) -> None:
        validate_installer_answers(windows_service_org_prefix=value)

    @pytest.mark.parametrize(
        "value",
        [
            "a/b",  # forward slash is illegal in a Windows service name
            "a\\b",  # backslash is illegal in a Windows service name
            "o'brien-",  # breaks the PowerShell single-quoted $ServiceName literal
            "x" * 300,  # pushes <prefix><repo_name> past the 256-char service-name limit
        ],
    )
    def test_rejects_illegal_service_name_characters_and_length(self, value: str) -> None:
        with pytest.raises(ValueError, match="windows_service_org_prefix"):
            validate_installer_answers(windows_service_org_prefix=value)
