import sys
from enum import Enum
from multiprocessing import Process
from time import sleep

import mido
import pyautogui


def extract_midi_value(midi_message):
    """
    Extract the most value-like attribute from the midi message, and convert it to something
    we can understand.
    For control_change and program_change messages, we have the 'value' and 'program'
    attributes.
    For note_on and note_off messages, we return either 1 or 0.
    """
    if hasattr(midi_message, "value"):
        value = midi_message.value
    elif hasattr(midi_message, "program"):
        value = midi_message.program
    elif midi_message.type == "note_on":
        value = 1
    elif midi_message.type == "note_off":
        value = 0
    else:
        raise ValueError("Can't find a value-like attribute in the midi message")

    return value


class Mapping:
    """
    A mapping that does something when something happens.
    """
    KEY_SEP = "+"

    def __init__(self, when_device, when_channel=None, when_is_program=False, when_control=None,
                 when_note=None, when_value_between=(0, 127), do_joystick=None, do_button=None,
                 do_axis=None, do_keys=None, do_on_off_threshold=None, do_axis_range=(0, 255)):
        # conditions
        self.when_device = when_device
        self.when_channel = when_channel
        self.when_is_program = when_is_program
        self.when_control = when_control
        self.when_note = when_note
        self.when_value_between = when_value_between

        # actions
        self.do_joystick = do_joystick
        self.do_button = do_button
        self.do_axis = do_axis
        self.do_keys = do_keys
        self.do_on_off_threshold = do_on_off_threshold
        self.do_axis_range = do_axis_range

        # checks
        if self.do_button is not None or self.do_axis is not None:
            if self.do_joystick is None:
                raise ValueError("To simulate a joystick button or axis, you must specify the "
                                 "joystick number in which to simulate them")

        if self.when_note is not None and self.do_axis is not None:
            raise ValueError("Can't use note buttons as axes, they're binary (on/off) and can "
                             "only be used to launch buttons or keyboard keys presses.")

    def run_if_matches(self, midi_message):
        """
        Process a message, decide if something needs to run, and run it if so.
        """
        if self.matches(midi_message):
            self.run(midi_message)

    def matches(self, midi_message):
        """
        Does a message matches our conditions?
        """
        if self.when_channel is not None and getattr(midi_message, "channel", None) != self.when_channel:
            return False

        if self.when_is_program and midi_message.type != "program_change":
            return False

        if self.when_control is not None:
            if midi_message.type != "control_change":
                return False
            elif midi_message.control != self.when_control:
                return False

        if self.when_note is not None:
            if midi_message.type not in ("note_on", "note_off"):
                return False
            elif midi_message.note != self.when_note:
                return False

        if self.when_is_program or self.when_control is not None:
            value = extract_midi_value(midi_message)
            if not self.when_value_between[0] <= value <= self.when_value_between[1]:
                return False

        return True

    def run(self, midi_message):
        """
        Simulate buttons or axes in a virtual joystick.
        """
        input_value = extract_midi_value(midi_message)

        if self.do_axis is not None:
            input_min, input_max = self.when_value_between
            output_min, output_max = self.do_axis_range
            input_ratio = (input_value - input_min) / (input_max - input_min)
            axis_value = int(output_min + (output_max - output_min) * input_ratio)

            print("Running joystick axis:", self.do_joystick, self.do_axis, axis_value)

        if self.do_button is not None or self.do_keys is not None:
            if self.when_note is not None:
                on = input_value == 1
            else:
                if self.do_on_off_threshold is not None:
                    on = input_value >= self.do_on_off_threshold
                else:
                    on = input_value >= sum(self.when_value_between) / 2

            if self.do_button is not None:
                print("Running joystick button:", self.do_joystick, self.do_button, on)

            if self.do_keys is not None:
                print("Running keys:", self.do_keys, on)
                if on:
                    for key in self.do_keys.split(self.KEY_SEP):
                        pyautogui.keyDown(key)
                else:
                    for key in reversed(self.do_keys.split(self.KEY_SEP)):
                        pyautogui.keyUp(key)


def single_device_loop(device_name, mappings):
    """
    Run the main loop for a single device. We need to have multiple processes with this same loop
    running, one for each device. (to be able to differentiate messages from each device, as mido
    doesn't tell us the device in the messages, so we can't use mido.ports.multi_receive()).
    """
    input_port = mido.open_input(device_name)

    while True:
        for message in input_port.iter_pending():
            print("Device:", device_name, "Message:", message)
            for mapping in mappings:
                mapping.run_if_matches(message)

        sleep(0.01)


def run_midi_joysticks(mappings):
    """
    Run the main loop of the app.
    """
    devices = set(m.when_device for m in mappings)
    processes = []

    for device_name in devices:
        device_mappings = [m for m in mappings if m.when_device == device_name]
        process = Process(target=single_device_loop, args=[device_name, device_mappings])
        process.start()
        processes.append(process)

    for process in processes:
        process.join()


if __name__ == "__main__":
    print("Detected devices:", mido.get_input_names())

    MIDI_CONTROLLER_1 = "W-FADER MIDI 1"
    MIDI_CONTROLLER_2 = "LPD8 MIDI 1"

    my_mappings = [
        # top row knobs
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_control=10,
            when_value_between=(0, 127),
            do_joystick=1,
            do_axis="X",
        ),
        # buttons below sliders
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_control=30,
            when_value_between=(0, 127),
            do_joystick=1,
            do_button=1,
            do_on_off_threshold=64,
        ),
        # program knob
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_is_program=True,
            when_value_between=(0, 127),
            do_joystick=1,
            do_axis="Y",
        ),

        # lpd8 pads
        Mapping(
            when_device=MIDI_CONTROLLER_2,
            when_note=36,
            do_joystick=1,
            do_keys="enter",
        ),
    ]

    run_midi_joysticks(my_mappings)
