import json
import re

from .base import ERROR_CODE_MAPPING
from .serial_write import debug_message
from .serial_write import write_raw_string_to_serial


def parse_json_params(
    command_arg: str,
) -> dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]] | None:
    if not command_arg.startswith("{"):
        return None
    debug_message(f"Parsing JSON parameters from command argument: {command_arg!r}")
    try:
        return json.loads(command_arg)
    except ValueError as e:  # apparently there is no json.JSONDecodeError in CircuitPython
        if "syntax error in JSON" in str(e):
            debug_message(f"JSON parsing error: {e!s}, returning None for parameters")
            return None
        raise


def write_response(
    response: str
    | dict[
        str,
        str
        | bool
        | int
        | float
        | None
        | dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]],
    ],
    *,
    instance_id: str | None = None,
):
    str_to_write = response if isinstance(response, str) else json.dumps(response, separators=(",", ":"))
    write_raw_string_to_serial(f"{str_to_write}\r\n", instance_id=instance_id)


def create_error_response(
    *, code: int, msg: str, command_id: int | None = None
) -> dict[
    str,
    str
    | bool
    | int
    | float
    | None
    | dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]],
]:
    return {
        "ok": False,
        "id": command_id,
        "code": code,
        "error_name": ERROR_CODE_MAPPING.get(code, "UNKNOWN_ERROR"),
        "msg": msg,
    }


def get_command_id(
    *,
    json_params: dict[str, str | bool | int | float | None | dict[str, str | bool | int | float | None]] | None,
    command_params: list[str],  # TODO: implement obtaining the ID from the last positional argument in the command
) -> int | str | None:
    potential_id = None
    debug_message(f"Extracting command ID from JSON params: {json_params!r} and command params: {command_params!r}")
    if json_params is not None and "id" in json_params:
        potential_id = json_params["id"]
    if potential_id is None:
        return potential_id
    if not isinstance(potential_id, (str, int)):
        raise TypeError(  # noqa: TRY003 # not worth a custom error class
            f"Command ID must be a string or integer, got type {type(potential_id)} for value {potential_id}"
        )
    try:
        return int(potential_id)
    except (TypeError, ValueError):
        return potential_id


def _matches_command(*, command: str, api: str) -> bool:
    if command.upper() == api.upper():  # match long form
        return True
    short_form = re.sub(r"[a-z]", "", api)
    return command.upper() == short_form.upper()


def matches_command(*, command: str, api: str) -> bool:
    """Confirm match according to SCPI rules (long and short forms).

    Args:
        command: The command received
        api: The API command to match against, e.g. MEASure?
    Returns:
        True if matches, False otherwise.
    """
    command_portions = command.split(":")
    api_portions = api.split(":")
    if len(command_portions) != len(api_portions):
        return False
    return all(
        _matches_command(command=cmd_portion, api=api_portion)
        for cmd_portion, api_portion in zip(  # noqa: B905 # CircuitPython does not support the `strict` kwarg
            command_portions, api_portions
        )
    )
