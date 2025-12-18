import time
import traceback

import usb_cdc  # pyright: ignore[reportMissingImports] # this is a CircuitPython library
from code_lib import ErrorCodeBase
from code_lib import FirmwareInstance
from code_lib import create_error_response
from code_lib import write_response

serial = usb_cdc.data  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType] # the usb_cdc library is not well typed
if serial is None:
    serial = usb_cdc.console  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType] # the usb_cdc library is not well typed


def read_until(terminator: bytes = b"\r") -> bytes:  # Change this to any character you want
    buffer = b""
    while True:
        if serial.in_waiting > 0:  # pyright: ignore[reportUnknownMemberType] # the serial library is not well typed
            char = serial.read(  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType] # the serial library is not well typed
                1
            )  # Read one byte at a time
            if char == terminator:
                return buffer  # pyright: ignore[reportUnknownVariableType] # the serial library is not well typed
            buffer += char  # Append character to the buffer # pyright: ignore[reportUnknownVariableType] # the serial library is not well typed


def main():
    f = FirmwareInstance()
    # TODO: create a "simulation mode" where it returns various different types of measurements (sinusoidal, square wave...)
    # TODO: implement watchdog: https://docs.circuitpython.org/en/latest/shared-bindings/watchdog/index.html#watchdog.WatchDogTimer
    while True:
        if serial.in_waiting > 0:  # pyright: ignore[reportUnknownMemberType] # the serial library is not well typed
            command_line = read_until(b"\r")  # Read the full command line
            f.process_serial_line(command_line)

        time.sleep(0.01)  # Small delay to prevent overwhelming the CPU


try:
    main()
except Exception as e:  # noqa: BLE001 # catch-all to prevent firmware from crashing
    write_response(
        create_error_response(
            code=ErrorCodeBase.UNHANDLED_EXCEPTION,
            msg=f"Unhandled exception in main application: {e!r}. Traceback {traceback.format_exception(None, e, e.__traceback__)}",
        )
    )
