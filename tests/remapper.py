import polychromatic.bindings as bindings
import polychromatic.remapper as remapper

import unittest

PRESS, RELEASE, REPEAT = remapper.PRESS, remapper.RELEASE, remapper.REPEAT


class FakeOutput(object):
    def __init__(self):
        self.events = []

    def key(self, name, value):
        self.events.append((name, value))

    def scroll(self, axis, steps):
        self.events.append((axis, steps))

    def sync(self):
        pass


class TestRemapper(unittest.TestCase):
    """
    Test how button presses turn into remapped actions.
    """
    def setUp(self):
        self.layout = bindings.get_layout("Razer Naga V3 Pro")
        self.profile = bindings.new_profile(self.layout, "Test")
        self.output = FakeOutput()
        self.actions = []
        self.remapper = remapper.Remapper(self.layout, self.profile, self.output, self.actions.append)

    def click(self, source, *values):
        for value in values or (PRESS, RELEASE):
            self.remapper.button_event(source, value)

    def bind(self, layer, uid, binding):
        bindings.set_binding(self.layout, self.profile, layer, uid, binding)

    def wait_for_macros(self):
        for runner in self.remapper.macros.values():
            runner.join(2)

    def test_factory_profile_sends_defaults(self):
        self.click("KEY_1")
        self.click("KEY_F15")
        self.assertEqual(self.output.events, [("KEY_1", PRESS), ("KEY_1", RELEASE), ("REL_HWHEEL", -1)])

    def test_key_combo_presses_in_order_and_releases_in_reverse(self):
        self.bind(bindings.STANDARD, "s1", {"type": "key", "keys": ["KEY_LEFTCTRL", "KEY_Z"]})
        self.click("KEY_1")
        self.assertEqual(self.output.events, [("KEY_LEFTCTRL", PRESS), ("KEY_Z", PRESS),
                                              ("KEY_Z", RELEASE), ("KEY_LEFTCTRL", RELEASE)])

    def test_unbound_button_sends_nothing(self):
        self.bind(bindings.STANDARD, "s2", None)
        self.click("KEY_2")
        self.assertEqual(self.output.events, [])

    def test_hypershift_layer_applies_while_held(self):
        self.bind(bindings.HYPERSHIFT, "s1", {"type": "key", "keys": ["KEY_F1"]})
        self.click("KEY_F17", PRESS)
        self.click("KEY_1")
        self.click("KEY_2")
        self.click("KEY_F17", RELEASE)
        self.click("KEY_1")
        # Side 2 has no Hypershift binding, so it does nothing on that layer.
        self.assertEqual(self.output.events, [("KEY_F1", PRESS), ("KEY_F1", RELEASE),
                                              ("KEY_1", PRESS), ("KEY_1", RELEASE)])

    def test_release_matches_press_after_layer_change(self):
        self.bind(bindings.HYPERSHIFT, "s1", {"type": "key", "keys": ["KEY_F1"]})
        self.click("KEY_1", PRESS)
        self.click("KEY_F17", PRESS)
        self.click("KEY_1", RELEASE)
        self.assertEqual(self.output.events, [("KEY_1", PRESS), ("KEY_1", RELEASE)])

    def test_moved_hypershift_key(self):
        self.bind(bindings.STANDARD, "s12", {"type": "media", "function": "hypershift"})
        self.bind(bindings.HYPERSHIFT, "s1", {"type": "media", "function": "mute"})
        self.click("KEY_EQUAL", PRESS)
        self.click("KEY_1")
        self.click("KEY_EQUAL", RELEASE)
        self.click("KEY_F17")
        self.assertEqual(self.output.events, [("KEY_MUTE", PRESS), ("KEY_MUTE", RELEASE)])

    def test_scroll_repeats_while_held(self):
        self.click("KEY_F16", PRESS, REPEAT, REPEAT, RELEASE)
        self.assertEqual(self.output.events, [("REL_HWHEEL", 1)] * 3)

    def test_key_repeat_is_ignored(self):
        self.click("KEY_1", PRESS, REPEAT, RELEASE)
        self.assertEqual(self.output.events, [("KEY_1", PRESS), ("KEY_1", RELEASE)])

    def test_device_actions(self):
        self.click("KEY_F13")
        self.assertEqual(self.actions, ["dpi_up"])
        self.assertEqual(self.output.events, [])

    def test_text(self):
        self.bind(bindings.STANDARD, "s3", {"type": "text", "text": "Hi!"})
        self.click("KEY_3")
        self.wait_for_macros()
        self.assertEqual(self.output.events, [
            ("KEY_LEFTSHIFT", PRESS), ("KEY_H", PRESS), ("KEY_H", RELEASE), ("KEY_LEFTSHIFT", RELEASE),
            ("KEY_I", PRESS), ("KEY_I", RELEASE),
            ("KEY_LEFTSHIFT", PRESS), ("KEY_1", PRESS), ("KEY_1", RELEASE), ("KEY_LEFTSHIFT", RELEASE)])

    def test_macro_once(self):
        steps = [{"event": "press", "key": "KEY_Q"}, {"event": "delay", "ms": 5}, {"event": "release", "key": "KEY_Q"}]
        self.bind(bindings.STANDARD, "s4", {"type": "macro", "name": "Q", "repeat": "once", "steps": steps})
        self.click("KEY_4")
        self.wait_for_macros()
        self.assertEqual(self.output.events, [("KEY_Q", PRESS), ("KEY_Q", RELEASE)])

    def test_stopped_macro_releases_its_keys(self):
        steps = [{"event": "press", "key": "KEY_Q"}, {"event": "delay", "ms": 5000}]
        self.bind(bindings.STANDARD, "s4", {"type": "macro", "name": "Q", "repeat": "held", "steps": steps})
        self.click("KEY_4", PRESS)
        self.click("KEY_4", RELEASE)
        self.wait_for_macros()
        self.assertEqual(self.output.events[-1], ("KEY_Q", RELEASE))
        self.assertFalse(self.remapper.macros["s4"].is_alive())

    def test_new_profile_applies_to_next_press(self):
        other = bindings.new_profile(self.layout, "Other")
        bindings.set_binding(self.layout, other, bindings.STANDARD, "s1", {"type": "key", "keys": ["KEY_A"]})
        self.remapper.set_profile(other)
        self.click("KEY_1")
        self.assertEqual(self.output.events, [("KEY_A", PRESS), ("KEY_A", RELEASE)])


if __name__ == '__main__':
    unittest.main()
