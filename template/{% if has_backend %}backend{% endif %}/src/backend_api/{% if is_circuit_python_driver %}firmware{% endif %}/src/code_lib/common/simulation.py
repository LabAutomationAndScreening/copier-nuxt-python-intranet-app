import sys


class SimulatedPeripheral:
    # Sentinel value to indicate no side effect was specified
    _NO_SIDE_EFFECT = object()

    def __init__(  # pyright: ignore[reportMissingSuperCall] # we don't want to call the super because it will do circuit python things with the class this is mixed in with
        self, *, method_side_effects: dict[str, list[object]] | None = None
    ):
        if method_side_effects is None:
            method_side_effects = {}
        self._method_side_effects = method_side_effects
        self._init()

    def _init(self) -> None:
        """Run additional initialization a subclass may require."""

    def _handle_side_effects(self) -> object:
        """Handle side effects for the calling method.

        Returns:
            _NO_SIDE_EFFECT if no side effect is specified for this method,
            otherwise returns (or raises) the side effect value (which could be None).
        """
        method_name = sys._getframe(  # noqa: SLF001 # this isn't ideal, but inspect module doesn't seem to be on circuit python, and not sure of another way to get the method name dynamically
            1
        ).f_code.co_name

        if method_name in self._method_side_effects:
            side_effects = self._method_side_effects[method_name]
            if side_effects:
                result = side_effects.pop(0)
                if isinstance(result, Exception):
                    raise result
                return result
        return self._NO_SIDE_EFFECT
