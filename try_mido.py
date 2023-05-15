from multiprocessing import Process
from time import sleep

import pygame
import pygame.midi as pgm
import mido


def single_device_loop(device_name):
    mido.set_backend('mido.backends.pygame')
    input_port = mido.open_input(device_name)

    while True:
        for message in input_port.iter_pending():
            print("Device:", device_name, "Message:", message, flush=True)

        sleep(0.01)


if __name__ == "__main__":
    pygame.init()
    pgm.init()
    mido.set_backend('mido.backends.pygame')

    device_names = set(mido.get_input_names())

    print("Listening to devices:")
    print()
    print("\n".join(device_names))
    print(flush=True)

    processes = []

    for device_name in device_names:
        process = Process(target=single_device_loop, args=[device_name])
        process.start()
        processes.append(process)

    for process in processes:
        process.join()

    pgm.quit()
