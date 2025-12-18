from .common import FirmwareInstanceBase


class FirmwareInstance(FirmwareInstanceBase):
    # API based on Standard Commands for Controllable Instruments specification (SCPI)

    def _handle_command(  # pyright: ignore[reportImplicitOverride] # CircuitPython doesn't have support for the override decorator
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
        raise NotImplementedError("this is a placeholder from the template, you must implement it")

    def _initialize(  # pyright: ignore[reportImplicitOverride] # CircuitPython doesn't have support for the override decorator
        self,
    ):
        pass
