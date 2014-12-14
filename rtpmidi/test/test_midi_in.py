import sys

from twisted.trial import unittest
from rtpmidi.engines.midi.midi_in import MidiIn

class FakeClient(object):
    def __init__(self):
        pass

    def send_midi_data(self, data, time):
        pass

class TestMidiIn(unittest.TestCase):
    def setUp(self):
        fake_client = FakeClient
        self.midi_in = MidiIn(fake_client)

    def test_start(self):
        res = self.midi_in.start()
        assert(res == 0), self.fail("Can start without a midi device set")

        #Faking midiDevice
        self.midi_in.midi_in = 1
        res = self.midi_in.start()
        assert(res == 1), self.fail("Can't start with a midi device set")

    def test_stop_1(self):
        self.midi_in.midi_in = 1
        self.midi_in.start()
        self.midi_in.stop()
        assert(self.midi_in.end_flag == True), \
            self.fail("Problem stopping Midi in.")

    def test_stop_2(self):
        #Set midi device
        #Getting list of midi device
        self.midi_in.get_devices()

        #Setting and testing midi device
        if len(self.midi_in.midi_device_list) > 0:
            dev_to_use = self.midi_in.midi_device_list
            self.midi_in.midi_in = 1

        else:
            self.fail("Problem getting list of midi" \
                          + " devices or no midi device available.")

        #Launch midi in
        self.midi_in.start()

        #Testing end flag
        assert( self.midi_in.end_flag == False ), \
            self.fail("Problem with end flag when midi is in activity")


        self.midi_in.stop()
        assert( self.midi_in.end_flag == True ), \
            self.fail("Problem with end flag when midi out in activity")

    def test_get_devices(self):
        self.midi_in.get_devices()
        assert(len(self.midi_in.midi_device_list) > 0), self.fail("Problem getting devices")

    def test_set_device(self):
        #Getting list of midi device
        self.midi_in.get_devices()

        #Setting and testing midi device
        if len(self.midi_in.midi_device_list) > 0:
            dev_to_use = self.midi_in.midi_device_list
            print dev_to_use
            #Port midi failed with the following lines ??
            #res = self.midi_in.set_device(1)
            #assert( res == True ), self.fail("Problem setting midi device in")
        else:
            self.fail("Problem getting list of midi" \
                          + " devices or no midi device available.")


    def test_get_device_info(self):
        #setting device midi
        self.midi_in.get_devices()
        self.midi_in.set_device(self.midi_in.midi_device_list[0][0])

        #Getting device infos
        res = self.midi_in.get_device_info()

        #Testing device infos
        assert(res[1] == "Midi Through Port-0"), \
            self.fail("Problem getting right info from midi device")


    def test_get_input(self):
        pass


    def test_polling(self):
        pass


