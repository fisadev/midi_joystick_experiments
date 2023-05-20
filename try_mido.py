from time import sleep
import sys
import platform

import pygame
import pygame.midi as pgm
import mido


def run_midi_listeners(device_names):
    """
    Run the main loop of the app.
    """
    pygame.init()
    pgm.init()

    if platform.system() == "Windows":
        midi_backend = mido.Backend('mido.backends.pygame')
    else:
        midi_backend = mido.Backend('mido.backends.rtmidi')

    ports = [midi_backend.open_input(name) for name in device_names]

    try:
        while True:
            for port, message in mido.ports.multi_receive(ports, yield_ports=True):
                print("Device:", port.name, "Message:", message, flush=True)

            sleep(0.01)
    except KeyboardInterrupt:
        print("Quitting")
        pgm.quit()


run_midi_listeners(sys.argv[1:])
