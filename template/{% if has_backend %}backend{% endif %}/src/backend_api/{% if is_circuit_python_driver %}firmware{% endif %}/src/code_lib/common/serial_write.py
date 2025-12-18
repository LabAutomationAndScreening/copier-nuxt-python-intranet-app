import sys

from .singletons import debug_mode
from .singletons import get_firmware_instance

if sys.implementation.name == "cpython":
    import logging
    import socket

    logger = logging.getLogger(__name__)

    def write_raw_string_to_serial(data: str, *, instance_id: str | None = None):
        f = get_firmware_instance(instance_id)
        if not isinstance(f.socket, socket.socket):
            raise TypeError(  # noqa: TRY003 # not worth custom exception
                "Firmware instance does not have a valid socket to write to"
            )
        f.socket.sendall(data.encode())

else:
    import usb_cdc  # pyright: ignore[reportMissingImports] # this is a CircuitPython library

    serial = usb_cdc.data  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType] # the usb_cdc library is not well typed
    if serial is None:
        serial = usb_cdc.console  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType] # the usb_cdc library is not well typed

    def write_raw_string_to_serial(
        data: str,
        *,
        instance_id: str | None = None,  # noqa: ARG001 # instance_id is only used when firmware is simulated, but function signature needs to match
    ):
        serial.write(data.encode())  # pyright: ignore[reportUnknownMemberType]


def debug_message(message: str):
    if debug_mode():
        write_raw_string_to_serial(f"DEBUG: {message}\r\n")
