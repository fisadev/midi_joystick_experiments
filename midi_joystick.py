from time import sleep

import mido
import pyautogui
import pygame
import pygame.midi as pgm
from vgamepad import VX360Gamepad, XUSB_BUTTON


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
                 when_note=None, when_value_between=(0, 127), with_joystick=None, do_button=None,
                 do_axis=None, do_keys=None, do_on_off_threshold=None):
        # conditions
        self.when_device = when_device
        self.when_channel = when_channel
        self.when_is_program = when_is_program
        self.when_control = when_control
        self.when_note = when_note
        self.when_value_between = when_value_between

        # actions
        self.with_joystick = with_joystick
        self.do_button = do_button
        self.do_axis = do_axis
        self.do_keys = do_keys
        self.do_on_off_threshold = do_on_off_threshold

        # checks
        if self.do_button is not None or self.do_axis is not None:
            if self.with_joystick is None:
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
            axis_value = (input_value - input_min) / (input_max - input_min)

            print("Running joystick axis:", self.do_axis, axis_value, flush=True)
            self.with_joystick.move_axis(self.do_axis, axis_value)

        if self.do_button is not None or self.do_keys is not None:
            if self.when_note is not None:
                on = input_value == 1
            else:
                if self.do_on_off_threshold is not None:
                    on = input_value >= self.do_on_off_threshold
                else:
                    on = input_value >= sum(self.when_value_between) / 2

            if self.do_button is not None:
                print("Running joystick button:", self.do_button, on, flush=True)
                if on:
                    self.with_joystick.press(self.do_button)
                else:
                    self.with_joystick.release(self.do_button)

            if self.do_keys is not None:
                print("Running keys:", self.do_keys, on, flush=True)
                if on:
                    for key in self.do_keys.split(self.KEY_SEP):
                        pyautogui.keyDown(key)
                else:
                    for key in reversed(self.do_keys.split(self.KEY_SEP)):
                        pyautogui.keyUp(key)


class Joystick:
    """
    Wrapper around vgamepad joystick classes, to keep state and be able to alter 1 axis at a time.
    """
    # conversion from button number (0 to 14) to the internal vgamepad button id
    BUTTONS = (
        XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
        XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
        XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
        XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        XUSB_BUTTON.XUSB_GAMEPAD_START,
        XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
        XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
        XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
        XUSB_BUTTON.XUSB_GAMEPAD_A,
        XUSB_BUTTON.XUSB_GAMEPAD_B,
        XUSB_BUTTON.XUSB_GAMEPAD_X,
        XUSB_BUTTON.XUSB_GAMEPAD_Y,
    )
    # conversion from axis number (0 to 5) to the internal vgamepad axis name
    AXES = (
        "triggers",  # both triggers add up together...
        "left_joystick_float:x_value_float",
        "left_joystick_float:y_value_float",
        "right_joystick_float:x_value_float",
        "right_joystick_float:y_value_float",
    )

    def __init__(self):
        self.pad = VX360Gamepad()
        # using the same names from vgamepad, to make things easier
        self.current_params_left_joystick_float = dict(x_value_float=-1, y_value_float=1)
        self.current_params_right_joystick_float = dict(x_value_float=-1, y_value_float=1)

    def press(self, button_number):
        """
        Hold down a button.
        """
        self.pad.press_button(button=self.BUTTONS[button_number])
        self.pad.update()

    def release(self, button_number):
        """
        Release a button.
        """
        self.pad.release_button(button=self.BUTTONS[button_number])
        self.pad.update()

    def move_axis(self, axis_number, value):
        """
        Set the value of an axis, as a ratio from 0 to 1.
        """
        axis_name = self.AXES[axis_number]
        if ":" in axis_name:
            value = value * 2 - 1
            axis_name, param = axis_name.split(":")
            if "y" in param:
                value = -value
            current_params = getattr(self, f"current_params_{axis_name}")
            current_params[param] = value
            getattr(self.pad, axis_name)(**current_params)
            self.pad.update()
        else:
            if value >= 0.5:
                # first half
                self.pad.left_trigger_float(value_float=value * 2)
                self.pad.right_trigger_float(value_float=0)
            else:
                # second half
                self.pad.left_trigger_float(value_float=0)
                self.pad.right_trigger_float(value_float=1 - value * 2)
            self.pad.update()


def run_midi_joysticks(mappings):
    """
    Run the main loop of the app.
    """
    pygame.init()
    pgm.init()
    midi_backend = mido.Backend('mido.backends.pygame')

    device_names = set(m.when_device for m in mappings)
    ports = [midi_backend.open_input(name) for name in device_names]

    try:
        while True:
            for port, message in mido.ports.multi_receive(ports, yield_ports=True):
                print("Device:", port.name, "Message:", message, flush=True)
                for mapping in mappings:
                    mapping.run_if_matches(message)

            sleep(0.01)
    except KeyboardInterrupt:
        print("Quitting")
        pgm.quit()


if __name__ == "__main__":
    MIDI_CONTROLLER_1 = "W-FADER"

    js1 = Joystick()

    my_mappings = [
        # top row knobs
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_control=10,
            when_value_between=(0, 127),
            with_joystick=js1,
            do_axis=0,
        ),
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_control=11,
            when_value_between=(0, 127),
            with_joystick=js1,
            do_axis=1,
        ),
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_control=12,
            when_value_between=(0, 127),
            with_joystick=js1,
            do_axis=2,
        ),
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_control=13,
            when_value_between=(0, 127),
            with_joystick=js1,
            do_axis=3,
        ),
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_control=14,
            when_value_between=(0, 127),
            with_joystick=js1,
            do_axis=4,
        ),
        # buttons below sliders
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_control=30,
            when_value_between=(0, 127),
            with_joystick=js1,
            do_button=0,
            do_on_off_threshold=64,
        ),
        Mapping(
            when_device=MIDI_CONTROLLER_1,
            when_control=31,
            when_value_between=(0, 127),
            do_keys="enter",
        ),
        # program knob
        # Mapping(
            # when_device=MIDI_CONTROLLER_1,
            # when_is_program=True,
            # when_value_between=(0, 127),
            # with_joystick=js1,
            # do_axis=0,
        # ),
    ]

    run_midi_joysticks(my_mappings)
