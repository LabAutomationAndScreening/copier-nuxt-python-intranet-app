class ResponseError(Exception):
    def __init__(self, *, code: int, msg: str):
        super().__init__(f"[{code}] {msg}")
        self.code = code
        self.msg = msg


def is_command_arg_truthy(command_arg: str) -> bool:
    return str(command_arg).upper() in ("1", "TRUE", "ON", "YES")


class IntEnum(int):  # `from enum import IntEnum` seemed to cause issues, and this is fine for JSON serialization
    pass


class StrEnum(str):  # `from enum import StrEnum` seemed to cause issues, and this is fine for JSON serialization
    __slots__ = ()


class BootMode(StrEnum):
    NORMAL = "NORMal"
    DEVELOPMENT = "DEVelopment"
    UPDATE = "UPDate"


class ErrorCodeBase(IntEnum):
    UNKNOWN_COMMAND = 3
    UNHANDLED_EXCEPTION = 4
    INVALID_ARGUMENT = 5
    COMMAND_PARTIALLY_FORMED = 6
    EXPECTED_SOFT_RESET_FAILED = 7
    EXPECTED_REBOOT_FAILED = 8
    NAME_TOO_LONG = 21
    NAME_TOO_SHORT = 22


ERROR_CODE_MAPPING: dict[int, str] = {
    # 2 through 20 reserved for codes likely to be applicable across all serial devices
    # 21 through 40 reserved for codes common across CircuitPython firmware
    # 60 through 99 reserved for device-specific error codes
    3: "UNKNOWN_COMMAND",
    4: "UNHANDLED_EXCEPTION",
    5: "INVALID_ARGUMENT",
    6: "COMMAND_PARTIALLY_FORMED",
    7: "EXPECTED_SOFT_RESET_FAILED",
    8: "EXPECTED_REBOOT_FAILED",
    21: "NAME_TOO_LONG",
    22: "NAME_TOO_SHORT",
}


# TODO: distinguish between "data simulation mode" vs the actual device is being simulated entirely
class SimulationModeBase(IntEnum):
    NOT_SIMULATED = 0
    # TODO: sinusoidal mode, random noise, etc.


SIMULATION_MODE_MAPPING: dict[int, str] = {0: "NOT_SIMULATED"}
