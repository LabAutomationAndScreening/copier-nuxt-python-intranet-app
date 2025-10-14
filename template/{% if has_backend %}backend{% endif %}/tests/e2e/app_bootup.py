import json
import logging
import subprocess
import time
from pathlib import Path

import pytest

from .jinja_constants import APPLICATION_BOOTUP_MODE
from .jinja_constants import ApplicationBootupModes

logger = logging.getLogger(__name__)

DEFAULT_COMPOSE_FILE = Path(__file__).parent.parent.parent.parent / "docker-compose.yaml"


def wait_for_service_to_be_healthy(*, max_retries: int = 15, retry_delay: int = 2, compose_file: Path):
    for attempt in range(max_retries):
        try:
            # Get container health status using docker ps
            result = subprocess.run(  # noqa: S603 # we trust this input
                [  # noqa: S607 # docker should definitely be in PATH
                    "docker",
                    "compose",
                    "--file",
                    str(compose_file),
                    "ps",
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if not result.stdout.strip():
                logger.info(f"Attempt {attempt + 1}/{max_retries}: Container info not available yet")
                time.sleep(retry_delay)
                continue

            container_info = [json.loads(line) for line in result.stdout.splitlines()]
            health_statuses: dict[str, str] = {}
            for service_info in container_info:
                assert isinstance(service_info, dict), f"Expected dict, got {type(service_info)} for {service_info}"
                health_statuses[service_info["Service"]] = service_info["Health"]

            logger.info(f"Attempt {attempt + 1}/{max_retries}: Container health status: {health_statuses}")

            if all(status in ("healthy", "") for status in health_statuses.values()):
                logger.info("Application containers are healthy!")
                break
        except Exception:
            logger.exception(f"Attempt {attempt + 1}/{max_retries}: Error checking container health:")

        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    else:
        raise RuntimeError(f"Application containers failed to become healthy after {max_retries} attempts")


def start_compose(*, compose_file: Path = DEFAULT_COMPOSE_FILE):
    assert compose_file.exists(), f"Compose file {compose_file} does not exist"
    _ = subprocess.run(  # noqa: S603 # we trust this input
        [  # noqa: S607 # docker should definitely be in PATH
            "docker",
            "compose",
            "--file",
            str(compose_file),
            "build",
        ],
        check=True,
        timeout=300,
    )
    _ = subprocess.run(  # noqa: S603 # we trust this input
        [  # noqa: S607 # docker should definitely be in PATH
            "docker",
            "compose",
            "--file",
            str(compose_file),
            "up",
            "--detach",
            "--force-recreate",
            "--renew-anon-volumes",
            "--remove-orphans",
        ],
        check=True,
        timeout=20,
    )
    wait_for_service_to_be_healthy(compose_file=compose_file)


def stop_compose(*, compose_file: Path = DEFAULT_COMPOSE_FILE):
    assert compose_file.exists(), f"Compose file {compose_file} does not exist"
    _ = subprocess.run(  # noqa: S603 # we trust this input
        [  # noqa: S607 # docker should definitely be in PATH
            "docker",
            "compose",
            "--file",
            str(compose_file),
            "down",
        ],
        check=True,
        timeout=45,
    )


@pytest.fixture(scope="session", autouse=True)
def running_application():
    if APPLICATION_BOOTUP_MODE == ApplicationBootupModes.DOCKER_COMPOSE:
        start_compose()
    else:
        raise NotImplementedError(f"Unsupported application bootup mode: {APPLICATION_BOOTUP_MODE}")
    yield
    if APPLICATION_BOOTUP_MODE == ApplicationBootupModes.DOCKER_COMPOSE:
        stop_compose()
    else:
        raise NotImplementedError(f"Unsupported application bootup mode: {APPLICATION_BOOTUP_MODE}")
