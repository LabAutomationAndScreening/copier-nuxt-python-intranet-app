import sys
import traceback

from ..device_constants import DEVICE_MODEL_ID
from ..device_constants import MANUFACTURER_NAME
from ..device_constants import VERSION
from .base import SIMULATION_MODE_MAPPING
from .base import BootMode
from .base import ErrorCodeBase
from .base import ResponseError
from .base import is_command_arg_truthy
from .device_commands import (
    cpus,  # pyright: ignore[reportUnknownVariableType,reportAttributeAccessIssue] # this is circuit python
)
from .device_commands import reload
from .device_commands import reset
from .device_commands import (
    runtime,  # pyright: ignore[reportUnknownVariableType,reportAttributeAccessIssue] # this is circuit python
)
from .device_commands import (
    status_bar,  # pyright: ignore[reportUnknownVariableType,reportAttributeAccessIssue] # this is circuit python
)
from .nvm import read_nvm_data
from .nvm import write_nvm_data
from .parsing import create_error_response
from .parsing import get_command_id
from .parsing import matches_command
from .parsing import parse_json_params
from .parsing import write_response
from .serial_write import debug_message
from .singletons import FirmwareInstanceSkeleton
from .singletons import set_debug_mode

MAX_NAME_BYTES = 128  # 32 4-byte unicode character absolute max
MIN_NAME_LENGTH = 1
BOOT_MODES_STR = f"{BootMode.NORMAL}, {BootMode.DEVELOPMENT}, {BootMode.UPDATE}"


class FirmwareInstanceBase(FirmwareInstanceSkeleton):
    # TODO: see if there's any way to use something like collections.abc.  it seems like that specifically is not available in CircuitPython
    def __init__(self, id: str | None = None, *, persisted_nvm_data: dict[str, str | int] | None = None):
        super().__init__(id=id, persisted_nvm_data=persisted_nvm_data)
        self.simulated_reset()

    def simulated_reboot(  # pyright: ignore[reportImplicitOverride] # CircuitPython doesn't support the override decorator
        self,
    ):
        self.working_nvm_data["boot_mode"] = self.working_nvm_data.get("next_boot_mode", BootMode.NORMAL)
        self.working_nvm_data["next_boot_mode"] = BootMode.NORMAL
        self.write_nvm_data()
        self.simulated_reset()

    def simulated_reset(  # pyright: ignore[reportImplicitOverride] # CircuitPython doesn't support the override decorator
        self,
    ):
        self._soft_reset_variables()
        self.read_nvm_data()

    def read_nvm_data(self):
        self.working_nvm_data.clear()
        _persisted_data = self._persisted_nvm_data
        if not self.is_simulated_firmware:
            _persisted_data = read_nvm_data()
        self.working_nvm_data.update(_persisted_data)

    def write_nvm_data(self):
        if self.is_simulated_firmware:
            self._persisted_nvm_data.clear()
            self._persisted_nvm_data.update(self.working_nvm_data)
        else:
            write_nvm_data(self.working_nvm_data)

    def set_name(
        self,
        *,
        json_params: dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]] | None,
        response_data: dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]],
    ):
        if json_params is None:
            raise ValueError(  # noqa: TRY003 # custom error not warranted
                "Expected JSON parameters for NAME command"
            )
        if "name" not in json_params:
            raise KeyError(  # noqa: TRY003 # custom error not warranted
                f"Expected 'name' parameter in JSON for NAME command: {json_params!r}"
            )
        if not isinstance(json_params["name"], str):
            raise TypeError(  # noqa: TRY003 # custom error not warranted
                f"Expected 'name' parameter to be a string, got {type(json_params['name'])} for value {json_params['name']}"
            )
        new_name = json_params["name"]
        if len(new_name) < MIN_NAME_LENGTH:
            raise ResponseError(
                code=ErrorCodeBase.NAME_TOO_SHORT,
                msg=f"Minimum allowed length of a name is {MIN_NAME_LENGTH} characters. Attempted name is {len(new_name)} characters long: {new_name}",
            )
        num_bytes = len(new_name.encode())
        if num_bytes > MAX_NAME_BYTES:
            raise ResponseError(
                code=ErrorCodeBase.NAME_TOO_LONG,
                msg=f"Maximum allowed byte-encoded length of a name is {MAX_NAME_BYTES} bytes. Attempted name is {num_bytes} bytes long: {new_name}",
            )
        self.working_nvm_data["assigned_name"] = new_name
        response_data["name"] = new_name
        self.write_nvm_data()

    def create_response(  # noqa: PLR0911,C901,PLR0915,PLR0912 # TODO: consider breaking this up into sub functions
        self,
        command_line: str,
    ) -> (
        str
        | dict[
            str,
            str
            | bool
            | int
            | float
            | None
            | dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]],
        ]
        | None
    ):
        parts = command_line.split(" ", 1)
        debug_message(f"Received command: {command_line!r}, parsed parts: {parts!r}")
        command = parts[0].strip()
        command_args = parts[1].strip().split(" ") if len(parts) > 1 else [""]
        debug_message(f"Parsed into command: {command}, and args: {command_args!r}")
        json_params = parse_json_params(command_arg=" ".join(command_args))
        command_id = get_command_id(json_params=json_params, command_params=parts[1:])
        response_data: dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]] = {}
        response: dict[
            str,
            str
            | bool
            | int
            | float
            | None
            | dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]],
        ] = {
            "ok": True,
            "id": command_id,
            "data": response_data,
        }
        try:
            if command == "*IDN?":
                id = self.working_nvm_data["id"]
                if not isinstance(id, str):
                    raise RuntimeError(  # noqa: TRY003 # custom error not warranted
                        f"NVM data does not contain a valid 'id' string, it was {id} of type {type(id)}"
                    )
                return f"{MANUFACTURER_NAME},{DEVICE_MODEL_ID},{id},{VERSION}"

            if command == "*RST":
                write_response(response, instance_id=self._id)
                reload(self._id)
                if self.is_simulated_firmware:
                    return None
                """Code past here will not execute.  But various text may be dumped into the serial console, e.g. Code done running. soft reboot.

                Auto-reload is on. Simply save files over USB to run them or enter REPL to disable.
                """
                raise ResponseError(  # noqa: TRY301 # we specifically want to raise here if the reset didn't occur
                    code=ErrorCodeBase.EXPECTED_SOFT_RESET_FAILED,
                    msg="Expected soft reset did not occur",
                )
            if matches_command(command=command, api="SYSTem:BOOT:MODE:ONCE"):
                if json_params is not None and "boot_mode" in json_params:
                    command_args[0] = str(json_params["boot_mode"])
                if command_args[0] == "":
                    return create_error_response(
                        code=ErrorCodeBase.INVALID_ARGUMENT,
                        msg=f"SYSTem:BOOT:MODE:ONCE command requires an argument (e.g. {BOOT_MODES_STR}).",
                    )
                parsed_boot_mode: str | None = None
                for possible_boot_mode in (BootMode.NORMAL, BootMode.DEVELOPMENT, BootMode.UPDATE):
                    if matches_command(command=command_args[0], api=possible_boot_mode):
                        parsed_boot_mode = possible_boot_mode
                        break
                if parsed_boot_mode is None:
                    return create_error_response(
                        code=ErrorCodeBase.INVALID_ARGUMENT,
                        msg=f"Invalid boot mode specified: {command_args[0]!r}. Must be one of: {BOOT_MODES_STR}.",
                    )
                self.working_nvm_data["next_boot_mode"] = parsed_boot_mode
                response_data["next_boot_mode"] = parsed_boot_mode
                self.write_nvm_data()
                return response
            if matches_command(command=command, api="SYSTem:REBoot"):
                write_response(response, instance_id=self._id)
                reset(self._id)
                if self.is_simulated_firmware:
                    return None
                """Code past here should not execute."""
                raise ResponseError(  # noqa: TRY301 # we specifically want to raise here if the reset didn't occur
                    code=ErrorCodeBase.EXPECTED_REBOOT_FAILED,
                    msg="Expected reboot did not occur",
                )
            if matches_command(command=command, api="INITialize"):
                self.initialize()
                response_data["detected_sensors"] = {  # pyright: ignore[reportArgumentType] # deeply nested JSON object not worth typing
                    sensor_type: ({addr: {} for addr in sensor_data})
                    for sensor_type, sensor_data in self._available_sensors.items()
                }
                return response
            if command == "AUTORELOAD":
                # TODO: figure out what to do if in simulation mode
                if command_args[0] == "":
                    raise ResponseError(  # noqa: TRY301 # we can move this to a separate function later
                        code=ErrorCodeBase.INVALID_ARGUMENT,
                        msg="AUTORELOAD command requires an argument (e.g., 'ON' or 'OFF').",
                    )
                parsed_value = is_command_arg_truthy(command_args[0])
                runtime.autoreload = parsed_value
                response_data["runtime_autoreload"] = parsed_value
                return response
            if command == "DEBUG":
                # TODO: figure out what to do if in simulation mode...writing back to the socket isn't wired up yet if debug mode is on
                if command_args[0] == "":
                    raise ResponseError(  # noqa: TRY301 # we can move this to a separate function later
                        code=ErrorCodeBase.INVALID_ARGUMENT,
                        msg="DEBUG command requires an argument (e.g., 'ON' or 'OFF').",
                    )

                parsed_value = is_command_arg_truthy(command_args[0])
                set_debug_mode(parsed_value)
                response_data["debug_mode"] = parsed_value
                return response

            if matches_command(command=command, api="METAdata?"):
                # TODO: handle case where name hasnot ever been set...it threw a key error
                # TODO: figure out how to display all the system modules...apparently different UF2 files can have different system modules
                response_data["identifier"] = self.working_nvm_data["id"]
                response_data["firmware_version"] = VERSION
                response_data["device_type"] = DEVICE_MODEL_ID
                response_data["assigned_name"] = self.working_nvm_data.get(
                    "assigned_name", ""
                )  # TODO: create a test where just working_nvm_data["assigned_name"] would throw a KeyError...we saw that once when booting up a board from scratch one time
                response_data["next_boot_mode"] = self.working_nvm_data.get("next_boot_mode", BootMode.NORMAL)
                response_data["boot_mode"] = self.working_nvm_data.get("boot_mode", BootMode.NORMAL)
                response_data["is_initialized"] = self.is_initialized
                response_data["simulation_mode"] = {
                    "code": self.simulation_mode,
                    "name": SIMULATION_MODE_MAPPING[self.simulation_mode],
                }
                response_data["debug_mode"] = self.debug_mode
                circuitpython_version_info = sys.implementation.version
                circuitpython_version = (
                    f"{circuitpython_version_info[0]}.{circuitpython_version_info[1]}.{circuitpython_version_info[2]}"
                )
                response_data["os_info"] = {
                    "implementation_version": circuitpython_version,
                    "runtime_autoreload": runtime.autoreload,  # pyright: ignore[reportUnknownMemberType] # circuit python
                    "run_reason": str(
                        runtime.run_reason  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType] # circuit python
                    )
                    .split(".")[-1]
                    .rstrip(">"),
                    "safe_mode_reason": str(
                        runtime.safe_mode_reason  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType] # circuit python
                    )
                    .split(".")[-1]
                    .rstrip(">"),
                    "status_bar_console": status_bar.console,  # pyright: ignore[reportUnknownMemberType] # circuit python
                    "status_bar_display": status_bar.display,  # pyright: ignore[reportUnknownMemberType] # circuit python
                }
                response_data["cpu"] = {  # pyright: ignore[reportArgumentType] # not sure why pyright is upset
                    str(i): {
                        "temperature_celsius": float(
                            cpu.temperature  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType] # the microcontroller library is not well typed
                        ),
                        "frequency_hz": int(
                            cpu.frequency  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType] # the microcontroller library is not well typed
                        ),
                        "reset_reason": str(
                            cpu.reset_reason  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType] # the microcontroller library is not well typed
                        )
                        .split(".")[-1]
                        .rstrip(">"),
                        "voltage": float(
                            cpu.voltage  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType] # the microcontroller library is not well typed
                        )
                        if cpu.voltage is not None  # pyright: ignore[reportUnknownMemberType] # the microcontroller library is not well typed
                        else None,
                    }
                    for i, cpu in enumerate(  # pyright: ignore[reportUnknownVariableType] # the microcontroller library is not well typed
                        cpus  # pyright: ignore[reportUnknownArgumentType] # the microcontroller library is not well typed
                    )
                }
                return response
            if command == "NAME":
                if json_params is None:
                    json_params: (
                        dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]] | None
                    ) = {"name": " ".join(parts[1:]).strip()}
                self.set_name(json_params=json_params, response_data=response_data)
                return response

            if command == "MEMory:CLEar":  # TODO: implement allowing shortened forms
                current_id = self.working_nvm_data["id"]
                self.working_nvm_data.clear()
                self.working_nvm_data["id"] = current_id
                self.write_nvm_data()
                self.read_nvm_data()
                return response
            if self._handle_command(
                command=command,
                command_args=command_args,
                json_params=json_params,
                command_id=command_id,
                response_data=response_data,
            ):
                return response

        except ResponseError as e:
            return create_error_response(code=e.code, msg=e.msg)
        return create_error_response(code=ErrorCodeBase.UNKNOWN_COMMAND, msg=f"Unknown command: '{command}'")

    def initialize(self):
        self._initialize()
        # Initialize I2C bus and sensors
        self.is_initialized = True
        debug_message("Initialization complete")

    def _initialize(self) -> None:
        raise NotImplementedError("Subclasses must implement _initialize")

    def _handle_command(
        self,
        *,
        command: str,
        command_args: list[str],
        json_params: dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]] | None,
        command_id: int | str | None,
        response_data: dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]],
    ) -> bool:
        """Handle custom commands for this firmware.

        Return True if command was handled, False otherwise.
        """
        raise NotImplementedError("Subclasses must implement _handle_command")

    def process_serial_line(self, command_line: bytes):
        command_line_str = command_line.decode("utf-8")  # Read the full command line
        try:
            response = self.create_response(command_line_str)
        except Exception as e:  # noqa: BLE001 # catch-all for anything that happened during a command
            write_response(
                create_error_response(
                    code=ErrorCodeBase.UNHANDLED_EXCEPTION,
                    msg=f"Unhandled exception while processing command {command_line_str}: {e!r}.  Traceback {traceback.format_exception(None, e, e.__traceback__)}",
                ),
                instance_id=self._id,
            )
            return
        if response is not None:
            write_response(response, instance_id=self._id)


def ensure_initialized(  # noqa: ANN201 # don't think I can type decorators well in CircuitPython
    func,  # noqa: ANN001 # pyright: ignore[reportMissingParameterType,reportUnknownParameterType] # not worth typing the decorator
):
    def wrapper(
        self: FirmwareInstanceBase,
        response_data: dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]] | str,
    ) -> None:
        if not self.is_initialized:
            self.initialize()
        return func(self, response_data)  # pyright: ignore[reportUnknownVariableType]

    return wrapper
