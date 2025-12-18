# TODO: move debug mode inside FirmwareInstance

_debug_mode = False


def debug_mode() -> bool:
    return _debug_mode


def set_debug_mode(
    mode: bool,  # noqa: FBT001 # this boolean argument is clear
) -> None:
    global _debug_mode  # noqa: PLW0603 # we need some simple globals/singletons for easy firmware usage
    _debug_mode = mode


class FirmwareInstanceSkeleton:
    simulation_mode: int  # pyright: ignore[reportUninitializedInstanceVariable] # it's initialized in the DRY method to reset variables
    debug_mode: bool  # pyright: ignore[reportUninitializedInstanceVariable]
    is_initialized: bool  # pyright: ignore[reportUninitializedInstanceVariable]
    working_nvm_data: dict[str, str | int]  # pyright: ignore[reportUninitializedInstanceVariable]
    _available_sensors: dict[str, dict[str, object]]  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(self, id: str | None = None, *, persisted_nvm_data: dict[str, str | int] | None = None):
        super().__init__()
        self._id = id
        self.socket: object | None = None
        if persisted_nvm_data is None:
            persisted_nvm_data = {}
        self._persisted_nvm_data = persisted_nvm_data  # for when firmware is simulated
        self._soft_reset_variables()
        add_firmware_instance(self)

    def set_socket(self, sock: object) -> None:
        self.socket = sock  # the socket module isn't available in circuit python, so we just represent as object

    def _soft_reset_variables(self) -> None:
        self.simulation_mode = 0
        self.debug_mode = False
        self.is_initialized = False
        self.working_nvm_data = {}
        self._available_sensors = {}

    def simulated_reboot(self) -> None:
        raise NotImplementedError("simulated_reboot must be implemented in the child class")

    def simulated_reset(self) -> None:
        raise NotImplementedError("simulated_reset must be implemented in the child class")

    @property
    def id(self) -> str | None:
        return self._id

    @property
    def is_simulated_firmware(self) -> bool:
        return self._id is not None


_firmware_instances: dict[str | None, FirmwareInstanceSkeleton] = {}


def add_firmware_instance(
    instance: FirmwareInstanceSkeleton,
) -> None:
    _firmware_instances[instance.id] = instance


def get_firmware_instance(
    id: str | None = None,
) -> FirmwareInstanceSkeleton:
    return _firmware_instances[id]


def reset_singletons():
    """Mimic a soft reset of the device by resetting all singletons to their default state."""
    set_debug_mode(False)
