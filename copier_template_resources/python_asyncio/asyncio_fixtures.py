# ============== WARNING ==============================================================================
# File is managed by copier template: gh:LabAutomationAndScreening/copier-base-template.git
# See .config/.copier-managed-files.json for details.
#
# You are welcome to make changes to this file in your repo if they are custom to your project,
# but if the change should be shared with other projects, please backport it to the template repo.
# =====================================================================================================
import asyncio

import pytest
from backend_api.background_tasks import background_task_exceptions
from backend_api.background_tasks import background_tasks_set


async def _wait_for_tasks(tasks_list: list[asyncio.Task[None]]):
    _, pending = await asyncio.wait(tasks_list, timeout=5.0)
    if len(pending) > 0:
        raise RuntimeError(f"There are still pending tasks: {pending}")


@pytest.fixture(autouse=True)
def fail_on_background_task_errors():
    """Automatically fail tests if ANY background task raises an exception."""
    background_task_exceptions.clear()

    yield

    # Wait for background tasks to complete (using asyncio.run for sync fixture)
    if len(background_tasks_set) > 0:
        tasks_list = list(background_tasks_set)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_wait_for_tasks(tasks_list))
        else:
            loop.run_until_complete(_wait_for_tasks(tasks_list))

    # Fail if any exceptions occurred
    if len(background_task_exceptions) > 0:
        pytest.fail(
            f"Background tasks raised {len(background_task_exceptions)} exception(s):\n"
            + "\n\n".join(f"{type(e).__name__}: {e}" for e in background_task_exceptions)
        )
