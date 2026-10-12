import polychromatic.bindings as bindings

import json
import os
import tempfile
import unittest


class TestBindings(unittest.TestCase):
    """
    Test the button binding profiles.
    """
    def setUp(self):
        self.layout = bindings.get_layout("Razer Naga V3 Pro (Wireless)")
        self.profile = bindings.new_profile(self.layout, "Test")

    def test_layout_only_for_supported_devices(self):
        self.assertIsNotNone(self.layout)
        self.assertEqual(len(self.layout.buttons), 20)
        self.assertIsNone(bindings.get_layout("Razer DeathAdder V2"))

    def test_new_profile_is_factory(self):
        for button in self.layout.buttons:
            self.assertFalse(bindings.is_remapped(self.layout, self.profile, bindings.STANDARD, button.uid))
        self.assertEqual(self.profile[bindings.HYPERSHIFT], {})
        self.assertEqual(bindings.get_hypershift_key(self.profile), "rf")

    def test_remap_and_reset(self):
        bindings.set_binding(self.layout, self.profile, bindings.STANDARD, "s1", {"type": "key", "keys": ["KEY_F1"]})
        self.assertTrue(bindings.is_remapped(self.layout, self.profile, bindings.STANDARD, "s1"))
        default = self.layout.get_button("s1").default
        bindings.set_binding(self.layout, self.profile, bindings.STANDARD, "s1", dict(default))
        self.assertFalse(bindings.is_remapped(self.layout, self.profile, bindings.STANDARD, "s1"))

    def test_only_one_hypershift_key(self):
        shift = {"type": "media", "function": "hypershift"}
        bindings.set_binding(self.layout, self.profile, bindings.STANDARD, "b2", shift)
        self.assertEqual(bindings.get_hypershift_key(self.profile), "b2")

        bindings.set_binding(self.layout, self.profile, bindings.STANDARD, "s12", shift)
        self.assertEqual(bindings.get_hypershift_key(self.profile), "s12")
        self.assertEqual(self.profile[bindings.STANDARD]["b2"], self.layout.get_button("b2").default)

    def test_moving_factory_hypershift_key_unbinds_it(self):
        bindings.set_hypershift_key(self.layout, self.profile, "s12")
        self.assertEqual(bindings.get_hypershift_key(self.profile), "s12")
        self.assertNotIn("rf", self.profile[bindings.STANDARD])

        bindings.set_binding(self.layout, self.profile, bindings.STANDARD, "rf", self.layout.get_button("rf").default)
        self.assertEqual(bindings.get_hypershift_key(self.profile), "rf")
        self.assertEqual(self.profile[bindings.STANDARD]["s12"], self.layout.get_button("s12").default)

    def test_hypershift_key_has_no_hypershift_binding(self):
        self.profile[bindings.HYPERSHIFT]["s3"] = {"type": "key", "keys": ["KEY_F3"]}
        bindings.set_hypershift_key(self.layout, self.profile, "s3")
        self.assertNotIn("s3", self.profile[bindings.HYPERSHIFT])

        bindings.set_hypershift_key(self.layout, self.profile, None)
        self.assertIsNone(bindings.get_hypershift_key(self.profile))
        self.assertEqual(self.profile[bindings.STANDARD]["s3"], self.layout.get_button("s3").default)

    def test_conflicts(self):
        bindings.set_binding(self.layout, self.profile, bindings.STANDARD, "s5", {"type": "key", "keys": ["KEY_1"]})
        conflicts = bindings.find_conflicts(self.layout, self.profile, bindings.STANDARD)
        self.assertEqual(conflicts, {"s1": ["s5"], "s5": ["s1"]})

    def test_empty_bindings_do_not_conflict(self):
        bindings.set_binding(self.layout, self.profile, bindings.STANDARD, "s1", bindings.new_binding("key"))
        bindings.set_binding(self.layout, self.profile, bindings.STANDARD, "s2", bindings.new_binding("key"))
        self.assertEqual(bindings.find_conflicts(self.layout, self.profile, bindings.STANDARD), {})

    def test_describe(self):
        self.assertEqual(bindings.describe(None), "Not bound")
        self.assertEqual(bindings.describe({"type": "key", "keys": ["KEY_LEFTCTRL", "KEY_Z"]}), "Key: Ctrl + Z")
        self.assertEqual(bindings.short_text({"type": "key", "keys": ["KEY_LEFTCTRL", "KEY_Z"]}), "Ctrl+Z")
        self.assertEqual(bindings.describe({"type": "mouse", "button": "BTN_SIDE"}), "Mouse: Back")

    def test_store_round_trip(self):
        folder = tempfile.mkdtemp()
        store = bindings.ProfileStore(folder, self.layout)
        self.assertEqual(len(store.profiles), 1)
        store.add(bindings.clone_profile(store.active, "Second"))
        store.active[bindings.STANDARD]["s1"] = {"type": "text", "text": "gg"}
        store.save()

        reloaded = bindings.ProfileStore(folder, self.layout)
        self.assertEqual([p["name"] for p in reloaded.profiles], ["Default", "Second"])
        self.assertEqual(reloaded.active["name"], "Second")
        self.assertEqual(reloaded.active[bindings.STANDARD]["s1"]["text"], "gg")

    def test_store_upgrades_old_factory_bindings(self):
        folder = tempfile.mkdtemp()
        profile = bindings.new_profile(self.layout, "Old")
        profile[bindings.STANDARD]["t1"] = {"type": "mouse", "button": "BTN_EXTRA"}
        profile[bindings.STANDARD]["b1"] = {"type": "key", "keys": ["KEY_F5"]}
        with open(os.path.join(folder, "naga-v3.json"), "w") as f:
            json.dump({"active": profile["id"], "profiles": [profile]}, f)

        store = bindings.ProfileStore(folder, self.layout)
        self.assertEqual(store.active[bindings.STANDARD]["t1"], self.layout.get_button("t1").default)
        self.assertEqual(store.active[bindings.STANDARD]["b1"], {"type": "key", "keys": ["KEY_F5"]})

    def test_store_keeps_last_profile(self):
        store = bindings.ProfileStore(tempfile.mkdtemp(), self.layout)
        self.assertFalse(store.delete(store.active_id))
        self.assertEqual(len(store.profiles), 1)

    def test_import(self):
        folder = tempfile.mkdtemp()
        store = bindings.ProfileStore(folder, self.layout)
        path = os.path.join(folder, "export.json")
        with open(path, "w") as f:
            json.dump(self.profile, f)
        imported = store.import_file(path)
        self.assertEqual(imported["name"], "Test")
        self.assertEqual(store.active_id, imported["id"])

        with open(path, "w") as f:
            json.dump({"unrelated": True}, f)
        self.assertRaises(ValueError, store.import_file, path)


if __name__ == '__main__':
    unittest.main()
