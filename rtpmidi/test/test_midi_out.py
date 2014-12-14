import sys
from twisted.trial import unittest
from rtpmidi.engines.midi.midi_out import MidiOut

class TestMidiOut(unittest.TestCase):
    """Test on MidiOut class"""

    def setUp(self):
        self.midi_out = MidiOut(1, 10)

    def tearDown(self):
        del self.midi_out

    def test_get_devices(self):
        self.midi_out.get_devices()
        assert(len(self.midi_out.midi_device_list) > 0), \
            self.fail("Problem getting devices")

    def test_get_device_info(self):
        #setting device midi
        self.midi_out.get_devices()
        self.midi_out.set_device(self.midi_out.midi_device_list[0][0])

        #Getting device infos
        res = self.midi_out.get_device_info()
        print res

        #Testing device infos
        assert(res[1] == "Midi Through Port-0"), \
            self.fail("Problem getting right info from midi device")

    def test_set_device(self):
        #Getting list of midi device
        self.midi_out.get_devices()

        #Setting and testing midi device
        if len(self.midi_out.midi_device_list) > 0:
            dev_to_use = self.midi_out.midi_device_list
            res = self.midi_out.set_device(dev_to_use[0][0])
            assert( res == True ), self.fail("Problem setting midi device out")
        else:
            self.fail("Problem getting list of midi" \
                          + " devices or no midi device available.")

    def test_start(self):
        #Without device
        res = self.midi_out.start()
        assert(res == 0), \
            self.fail("Can start publy before setting a midi device")

        #With device
        self.midi_out.get_devices()

        dev = self.midi_out.set_device(self.midi_out.midi_device_list[0][0])

        if dev == 0:
            res = self.midi_out.start()
            assert(res == 1), \
                self.fail("Can't start publy with a midi device set")

    def test_send_note_off(self):
        self.midi_out.get_devices()
        self.midi_out.set_device(self.midi_out.midi_device_list[0][0])
        self.midi_out.send_note_off()
        #Nothin to test ??

    def test_play_midi_notes(self):
        pass

    def test_publish_midi_notes(self):
        pass

