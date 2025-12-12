import json
import logging
import os
import socket
import subprocess
import time
from pathlib import Path

import httpx

from .jinja_constants import APP_NAME
from .jinja_constants import APPLICATION_BOOTUP_MODE
from .jinja_constants import BACKEND_PORT
from .jinja_constants import ApplicationBootupModes

logger = logging.getLogger(__name__)

DEFAULT_COMPOSE_FILE = Path(__file__).parent.parent.parent.parent / "docker-compose.yaml"
EXE_DIR_PATH = Path(__file__).parent.parent.parent / "dist" / APP_NAME
EXE_FILE_NAME = APP_NAME + (".exe" if os.name == "nt" else "")
EXE_FILE_PATH = EXE_DIR_PATH / EXE_FILE_NAME


def get_random_open_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))  # Bind to an available ephemeral port
        return s.getsockname()[1]  # Return the port number


def _backend_port() -> int:
    if APPLICATION_BOOTUP_MODE == ApplicationBootupModes.DOCKER_COMPOSE:
        return BACKEND_PORT
    return (  # in Windows CI, ports sometimes become unavailable, so we need a random one for executable testing
        get_random_open_port()
    )


BACKEND_E2E_PORT = _backend_port()


def wait_for_backend_to_be_healthy(*, port: int, max_retries: int = 15, retry_delay: int = 2):
    url = f"http://localhost:{port}/api/healthcheck"
    for attempt in range(max_retries):
        try:
            response = httpx.get(url, timeout=5.0)
            if response.is_success:
                logger.info(f"Attempt {attempt + 1}/{max_retries}: Backend is healthy!")
                return

            logger.info(f"Attempt {attempt + 1}/{max_retries}: Backend returned status {response.status_code}")
        except httpx.HTTPError as e:
            logger.info(f"Attempt {attempt + 1}/{max_retries}: Failed to connect to backend: {e}")

        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    raise RuntimeError(f"Backend failed to become healthy after {max_retries} attempts")


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


def get_images_from_compose(compose_file: Path) -> list[str]:
    result = subprocess.run(  # noqa: S603 # we trust this input
        [  # noqa: S607 # docker should definitely be in PATH
            "docker",
            "compose",
            "--file",
            str(compose_file),
            "config",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    config = json.loads(result.stdout)
    return [s["image"] for s in config.get("services", {}).values() if "image" in s and "build" not in s]


def image_exists_locally(image: str) -> bool:
    result = subprocess.run(  # noqa: S603 # we trust this input
        [  # noqa: S607 # docker should definitely be in PATH
            "docker",
            "image",
            "inspect",
            image,
        ],
        check=False,
        capture_output=True,
        timeout=5,
    )
    return result.returncode == 0


def pull_images(*, compose_file: Path = DEFAULT_COMPOSE_FILE):
    images = get_images_from_compose(compose_file)
    for image in images:
        if image_exists_locally(image):
            logger.info(f"Image already exists locally: {image}")
            continue
        logger.info(f"Pulling image: {image}")
        _ = subprocess.run(  # noqa: S603 # we trust this input
            [  # noqa: S607 # docker should definitely be in PATH
                "docker",
                "pull",
                image,
            ],
            check=True,
            timeout=75,
        )


def start_compose(*, compose_file: Path = DEFAULT_COMPOSE_FILE):
    assert compose_file.exists(), f"Compose file {compose_file} does not exist"
    _ = subprocess.run(  # noqa: S603 # we trust this input
        [  # noqa: S607 # docker should definitely be in PATH
            "docker",
            "compose",
            "--file",
            str(compose_file),
            "build",
            "backend",  # don't build the frontend in tests of just the backend
        ],
        check=True,
        timeout=300,
    )
    pull_images(compose_file=compose_file)
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
            "--scale",
            "frontend=0",  # don't boot up the frontend for tests of only the backend
        ],
        check=True,
        timeout=220,  # TODO: figure out why the frontend still attempts to build in CI...so we can reset the timeout back to 20
    )
    try:
        wait_for_service_to_be_healthy(compose_file=compose_file)
    except Exception:
        logger.exception("Failed to verify service health, cleaning up...")
        stop_compose(compose_file=compose_file)
        raise


def stop_compose(*, compose_file: Path = DEFAULT_COMPOSE_FILE):
    assert compose_file.exists(), f"Compose file {compose_file} does not exist"
    _ = subprocess.run(  # noqa: S603 # we trust this input
        [  # noqa: S607 # docker should definitely be in PATH
            "docker",
            "compose",
            "--file",
            str(compose_file),
            "down",
            "--volumes",
        ],
        check=True,
        timeout=45,
    )


def start_exe(*, port: int, env: dict[str, str] | None = None) -> subprocess.Popen[bytes]:
    assert EXE_FILE_PATH.exists(), f"Executable file {EXE_FILE_PATH} does not exist"
    if env is None:
        env = (  # by default, pass in any environmental variables configured during the test setup process
            os.environ.copy()
        )
    process = subprocess.Popen(  # noqa: S603 # we trust this input
        [
            str(EXE_FILE_PATH),
            "--port",
            str(port),
            "--host",
            "0.0.0.0",  # noqa: S104 # until we get Windows CI fully figured out, we're just binding everything
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    wait_for_backend_to_be_healthy(port=port)
    return process


def stop_exe(*, process: subprocess.Popen[bytes], port: int):
    shutdown_url = f"http://localhost:{port}/api/shutdown"
    try:
        response = httpx.get(shutdown_url, timeout=5.0)
        if response.is_success:
            logger.info("Shutdown request sent successfully.")
        else:
            logger.warning(f"Shutdown request returned status code {response.status_code}.")
    except httpx.HTTPError:
        logger.exception("Failed to send shutdown request")

    # Poll to see if process shut down gracefully
    max_attempts = 10
    poll_interval = 0.5  # seconds
    for attempt in range(max_attempts):
        if process.poll() is not None:
            logger.info(f"The /shutdown route successfully stopped the process. This took {attempt * poll_interval}s.")
            return
        time.sleep(poll_interval)

    if process.poll() is None:
        process.terminate()
        try:
            _ = process.wait(timeout=10)
            logger.info("Executable process terminated gracefully.")
        except subprocess.TimeoutExpired:
            process.kill()
            logger.warning("Executable process killed after timeout.")
