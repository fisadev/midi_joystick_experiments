from time import sleep


import vgamepad as vg

pad1 = vg.VX360Gamepad()
pad2 = vg.VX360Gamepad()
pad3 = vg.VX360Gamepad()

while True:
    sleep(1)
    pad2.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
    pad2.update()
    sleep(0.1)
    pad2.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
    pad2.update()

    pad1.update()
    pad3.update()
