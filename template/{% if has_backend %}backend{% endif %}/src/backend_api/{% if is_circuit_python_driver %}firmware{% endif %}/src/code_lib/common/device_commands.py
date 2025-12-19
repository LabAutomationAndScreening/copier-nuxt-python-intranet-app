import sys

from .singletons import get_firmware_instance

if sys.implementation.name == "circuitpython":
    import microcontroller
    import supervisor  # pyright: ignore[reportMissingImports] # this is a CircuitPython library
    from microcontroller import (
        cpus,  # noqa: F401 # imported for use in firmware_instance_base.py # pyright: ignore[reportUnknownVariableType,reportAttributeAccessIssue] # this is a CircuitPython library
    )
    from supervisor import (  # pyright: ignore[reportMissingImports] # this is a CircuitPython library
        runtime,  # noqa: F401 # imported for use in firmware_instance_base.py # pyright: ignore[reportUnknownVariableType] # this is a CircuitPython library
    )
    from supervisor import (  # pyright: ignore[reportMissingImports] # this is a CircuitPython library
        status_bar,  # noqa: F401 # imported for use in firmware_instance_base.py # pyright: ignore[reportUnknownVariableType] # this is a CircuitPython library
    )

    def _reset_real(_: str | None = None):
        microcontroller.reset()  # pyright: ignore[reportUnknownMemberType,reportAttributeAccessIssue] # the microcontroller library is not well typed

    def _reload_real(_: str | None = None):
        supervisor.reload()  # pyright: ignore[reportUnknownMemberType] # the supervisor library is not well typed

    reload = _reload_real
    reset = _reset_real

else:
    from types import SimpleNamespace

    cpus = {}
    # TODO: some of these simulated values are mutable (like autoreload), so decide how to address that
    # TODO: ensure these simulated values make sense
    runtime = SimpleNamespace(
        autoreload=False,
        run_reason="UNKNOWN",
        safe_mode_reason="UNKNOWN",
    )
    status_bar = SimpleNamespace(console=False, display=False)

    def _reload_sim(instance_id: str | None = None):
        get_firmware_instance(instance_id).simulated_reset()

    def _reset_sim(instance_id: str | None = None):
        get_firmware_instance(instance_id).simulated_reboot()

    reload = _reload_sim
    reset = _reset_sim
