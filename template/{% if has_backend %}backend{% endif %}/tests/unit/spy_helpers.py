from unittest.mock import MagicMock


def logged_message(spy: MagicMock, *, call_index: int = 0) -> str:
    call_args = spy.call_args_list[call_index].args
    assert isinstance(call_args[0], str), f"Expected the logged message to be a str, got {type(call_args[0])}"
    return call_args[0]
