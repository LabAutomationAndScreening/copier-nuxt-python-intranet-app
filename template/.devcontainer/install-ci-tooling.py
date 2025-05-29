import argparse
import os
import platform
import shutil
import subprocess
import sys

UV_VERSION = "0.7.8"
PNPM_VERSION = "10.11.0"
COPIER_VERSION = "9.7.1"
COPIER_TEMPLATES_EXTENSION_VERSION = "0.3.1"
PRE_COMMIT_VERSION = "4.2.0"
GITHUB_WINDOWS_RUNNER_BIN_PATH = r"C:\Users\runneradmin\.local\bin"
parser = argparse.ArgumentParser(description="Install CI tooling for the repo")
_ = parser.add_argument(
    "--no-python",
    default=False,
    action="store_true",
    help="Do not process any environments using python package managers",
)
_ = parser.add_argument(
    "--python-version",
    default=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    type=str,
    help="What version to install.",
)
_ = parser.add_argument(
    "--no-node", action="store_true", default=False, help="Do not process any environments using node package managers"
)


def main():
    args = parser.parse_args(sys.argv[1:])
    is_windows = platform.system() == "Windows"
    uv_env = dict(os.environ)
    uv_env.update({"UV_PYTHON_PREFERENCE": "only-system", "UV_PYTHON": args.python_version})
    uv_path = ((GITHUB_WINDOWS_RUNNER_BIN_PATH + "\\") if is_windows else "") + "uv"
    if not args.no_python:
        if is_windows:
            uv_env.update({"PATH": rf"{GITHUB_WINDOWS_RUNNER_BIN_PATH};{uv_env['PATH']}"})
            pwsh = shutil.which("pwsh") or shutil.which("powershell")
            if not pwsh:
                raise FileNotFoundError("Neither 'pwsh' nor 'powershell' found on PATH")
            # invoke installer in a pwsh process
            _ = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"irm https://astral.sh/uv/{UV_VERSION}/install.ps1 | iex",
                ],
                check=True,
                env=uv_env,
            )
        else:
            _ = subprocess.run(
                f"curl -fsSL https://astral.sh/uv/{UV_VERSION}/install.sh | sh",
                check=True,
                shell=True,
                env=uv_env,
            )
            # TODO: add uv autocompletion to the shell https://docs.astral.sh/uv/getting-started/installation/#shell-autocompletion
        _ = subprocess.run(
            [
                uv_path,
                "tool",
                "install",
                f"copier=={COPIER_VERSION}",
                "--with",
                f"copier-templates-extensions=={COPIER_TEMPLATES_EXTENSION_VERSION}",
            ],
            check=True,
            env=uv_env,
        )
        _ = subprocess.run(
            [
                uv_path,
                "tool",
                "install",
                f"pre-commit=={PRE_COMMIT_VERSION}",
            ],
            check=True,
            env=uv_env,
        )
        _ = subprocess.run(
            [
                uv_path,
                "tool",
                "list",
            ],
            check=True,
            env=uv_env,
        )
    if not args.no_node:
        _ = subprocess.run(["npm", "-v"], check=True)
        _ = subprocess.run(["npm", "install", "-g", f"pnpm@{PNPM_VERSION}"], check=True)
        _ = subprocess.run(["pnpm", "-v"], check=True)


if __name__ == "__main__":
    main()
