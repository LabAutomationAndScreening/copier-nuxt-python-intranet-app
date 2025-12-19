import storage  # pyright: ignore[reportMissingImports] # this is a CircuitPython library
import supervisor  # pyright: ignore[reportMissingImports] # this is a CircuitPython library
import usb_cdc  # pyright: ignore[reportMissingImports] # this is a CircuitPython library
from code_lib import DEVICE_NAME
from code_lib import MANUFACTURER_NAME
from code_lib import USB_PID
from code_lib import USB_VID
from code_lib import BootMode
from code_lib import read_nvm_data
from code_lib import write_nvm_data

# ruff: noqa: T201 # boot.py print commands go to boot_out.txt for debugging
desired_boot_mode = BootMode.DEVELOPMENT  # fallback to dev mode if errors encountered

# TODO: see if there's some way via one of the pins to force dev mode, e.g., holding a button on boot https://learn.adafruit.com/customizing-usb-devices-in-circuitpython/circuitpy-midi-serial
# if you have access to the buttons and it bricks, tap reset, then tap boot to go into safe mode...the "slow double click" on reset doesn't seem to actually work

try:
    nvm_data = read_nvm_data()
    print(f"Serial ID: {nvm_data.get('id')}")
    desired_boot_mode = nvm_data.get("next_boot_mode", BootMode.NORMAL)
    previous_boot_mode = nvm_data.get("boot_mode", BootMode.NORMAL)
    print(f"Read stored value for next_boot_mode: {desired_boot_mode}  (type {type(desired_boot_mode)})")
    update_nvm = False
    if desired_boot_mode != BootMode.NORMAL:
        nvm_data["next_boot_mode"] = BootMode.NORMAL
        update_nvm = True
    if previous_boot_mode != desired_boot_mode:
        nvm_data["boot_mode"] = desired_boot_mode
        update_nvm = True
    if update_nvm:
        write_nvm_data(nvm_data)

except Exception:  # noqa: BLE001 # catch-all to ensure dev mode is enabled if NVM read fails
    print("Error reading NVM data; enabling development mode")

print("Boot mode:", desired_boot_mode)


usb_cdc.enable(  # pyright: ignore[reportUnknownMemberType] # the usb_cdc library is not well typed
    console=desired_boot_mode == BootMode.DEVELOPMENT,  # console allows REPL
    data=desired_boot_mode
    != BootMode.DEVELOPMENT,  # TODO: consider whether to enable both data and console in dev mode
)
if desired_boot_mode == BootMode.NORMAL:  # pyright: ignore[reportUnnecessaryComparison] # pyright doesn't seem to understand that what happens in the try/except block could change the variable value
    storage.disable_usb_drive()  # pyright: ignore[reportUnknownMemberType] # the storage library is not well typed

supervisor.set_usb_identification(  # pyright: ignore[reportUnknownMemberType] # the supervisor library is not well typed
    manufacturer=MANUFACTURER_NAME,
    product=DEVICE_NAME,
    vid=int(USB_VID, 16),
    pid=int(USB_PID, 16),
)
