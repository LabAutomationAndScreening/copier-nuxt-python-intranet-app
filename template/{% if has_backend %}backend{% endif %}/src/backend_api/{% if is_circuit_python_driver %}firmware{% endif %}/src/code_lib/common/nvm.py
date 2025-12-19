import json
import os
import sys

MAX_ID_LENGTH = 36  # GUID is max 36 chars


def generate_uuid4() -> str:
    # Get 16 random bytes
    random_bytes = bytearray(os.urandom(16))

    # Set version to 4 => xxxx => 0100
    random_bytes[6] = (random_bytes[6] & 0x0F) | 0x40

    # Set variant to RFC 4122 => 10xx
    random_bytes[8] = (random_bytes[8] & 0x3F) | 0x80

    # Format into UUID string
    return "".join(
        [
            f"{random_bytes[0]:02x}{random_bytes[1]:02x}{random_bytes[2]:02x}{random_bytes[3]:02x}-",
            f"{random_bytes[4]:02x}{random_bytes[5]:02x}-",
            f"{random_bytes[6]:02x}{random_bytes[7]:02x}-",
            f"{random_bytes[8]:02x}{random_bytes[9]:02x}-",
            f"{random_bytes[10]:02x}{random_bytes[11]:02x}{random_bytes[12]:02x}",
            f"{random_bytes[13]:02x}{random_bytes[14]:02x}{random_bytes[15]:02x}",
        ]
    )


if sys.implementation.name == "circuitpython":
    import microcontroller

    def _read_string_from_nvm(*, start: int, length: int) -> str:
        try:
            nvm_bytes = microcontroller.nvm[  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType,reportAttributeAccessIssue] # the microcontroller library is not well typed
                start : (start + length)
            ]
            # Find the null terminator if it exists
            null_pos = 0
            while (
                null_pos
                < len(
                    nvm_bytes  # pyright: ignore[reportUnknownArgumentType] # the library is not well typed
                )
                and nvm_bytes[null_pos] != 0
            ):
                null_pos += 1
            return bytes(
                nvm_bytes[0:null_pos]  # pyright: ignore[reportUnknownArgumentType] # the library is not well typed
            ).decode("utf-8")
        except Exception:  # noqa: BLE001 # not sure what types of errors could be thrown
            return ""

    def read_identifier() -> str:  # DEPRECATED, can be removed once all boards converted to using JSON-formatted NVM
        return _read_string_from_nvm(start=0, length=MAX_ID_LENGTH)

    def _write_nvm_data_real(data: dict[str, str | int]):
        nvm_str = json.dumps(data, separators=(",", ":"))
        new_nvm_bytes = nvm_str.encode("utf-8")
        # Ensure it fits in NVM
        nvm_size = len(
            microcontroller.nvm  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType,reportAttributeAccessIssue] # the microcontroller library is not well typed
        )
        if len(new_nvm_bytes) >= nvm_size:
            raise ValueError(  # noqa: TRY003 # TODO: create more custom error/handling
                f"NVM data too large to store: {len(new_nvm_bytes)} bytes, max is {nvm_size - 1} bytes"
            )
        # Pad with null bytes
        padded = new_nvm_bytes + bytes([0] * (nvm_size - len(new_nvm_bytes)))
        microcontroller.nvm[  # pyright: ignore[reportUnknownMemberType,reportAttributeAccessIssue] # this is a custom ByteArray class, which pyright will probably never understand, so even isinstance won't help
            0:nvm_size
        ] = padded

    def _read_nvm_data_real() -> dict[str, str | int]:
        nvm_bytes = microcontroller.nvm  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType,reportAttributeAccessIssue] # this is a custom ByteArray class, which pyright will probably never understand, so even isinstance won't help

        loaded_id = ""
        # backwards compatibility for when only ID was stored
        first_byte = nvm_bytes[0]  # pyright: ignore[reportUnknownVariableType] # the microcontroller library is not well typed
        if first_byte != ord("{"):
            loaded_id = read_identifier()  # in the future, when we know no raw IDs would have been written to bytes, we can drop the support for read_identifier and just assume the board is fresh if the first character isn't '{' and then generate the ID
            if loaded_id == "":
                loaded_id = generate_uuid4()
            _nvm_data: dict[str, str | int] = {"id": loaded_id}
            _write_nvm_data_real(_nvm_data)
            return _nvm_data

        # read entire NVM as JSON
        nvm_size = len(
            nvm_bytes  # pyright: ignore[reportUnknownArgumentType] # the microcontroller library is not well typed
        )
        null_pos = 0
        while null_pos < nvm_size and nvm_bytes[null_pos] != 0:
            null_pos += 1
        nvm_str = bytes(
            nvm_bytes[  # pyright: ignore[reportUnknownArgumentType] # the microcontroller library is not well typed
                0:null_pos
            ]
        ).decode("utf-8")
        _loaded_data = json.loads(nvm_str)
        if "assigned_name" not in _loaded_data:
            _loaded_data["assigned_name"] = ""
        return _loaded_data

    read_nvm_data = _read_nvm_data_real
    write_nvm_data = _write_nvm_data_real


else:

    def _read_nvm_data_sim():
        raise RuntimeError(  # noqa: TRY003
            "in simulation mode this should never have been reached"
        )

    def _write_nvm_data_sim():
        raise RuntimeError(  # noqa: TRY003
            "in simulation mode this should never have been reached"
        )

    read_nvm_data = _read_nvm_data_sim
    write_nvm_data = _write_nvm_data_sim
