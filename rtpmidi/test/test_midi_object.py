from twisted.trial import unittest
from rtpmidi.engines.midi.midi_object import MidiCommand
from rtpmidi.engines.midi.midi_object import SafeKeyboard
class TestMidiCommand(unittest.TestCase):
    """Testing MidiCommand class"""

    def setUp(self):
        self.midi_command = MidiCommand()

    def tearDown(self):
        del self.midi_command

    def test_header(self):
        """Testing header for MIDICommand"""
        marker_b, recovery, timestamp, phantom, length = 0, 0, 0, 0, 10
        res = self.midi_command.header(marker_b, recovery, timestamp, phantom, length)

        assert(type(res)==str), self.fail("Wrong type returned")
        assert(len(res)==1), self.fail("Wrong size returned")


    def test_parse_header(self):
        """Testing parse header for MIDICommand"""
        marker_b, recovery, timestamp, phantom, length = 0, 0, 0, 0, 10
        res = self.midi_command.header(marker_b, recovery, timestamp, phantom, length)
        marker_b, marker_j, marker_z, marker_p, length = self.midi_command.parse_header(res)

        assert(marker_b==0), self.fail("Wrong value returned for marker_b")
        assert(marker_j==0), self.fail("Wrong value returned for marker_j")
        assert(marker_z==0), self.fail("Wrong value returned for marker_z")
        assert(marker_p==0), self.fail("Wrong value returned for marker_p")
        assert(length==10), self.fail("Wrong value returned for length")

    def test_encode_midi_commands(self):

        plist = [[[192, 120, 100],1069],[[144, 104, 50],1030],
                 [[145, 110, 0],10], [[145, 112, 0],1044],
                 [[144, 124, 50],19],[[145, 114, 0],8],
                 [[145, 12, 0],999]]

        decorate =  [((x[0][0]&15), (x[0][0]&240), x[0][1],x) for x in plist]
        decorate.sort()
        plist = [x[3] for x in decorate]

        res, nb_notes = self.midi_command.encode_midi_commands(plist)

        assert(nb_notes==7), \
            self.fail("Problem with nb_notes , it's not corresponding" \
                           + " to reality")
        assert(len(res) == nb_notes*7), \
            self.fail("Problem of size with formated command")

    def test_decode_midi_commands(self):
        plist = [[[192, 120, 100],1069],[[144, 104, 50],1069], \
                     [[145, 110, 0],1070], [[145, 112, 0],1071], \
                     [[144, 124, 50],1071],[[145, 114, 0],1072], \
                     [[145, 12, 0],1072]]

        decorate =  [((x[0][0]&15), (x[0][0]&240), x[0][1],x) for x in plist]
        decorate.sort()
        plist = [x[3] for x in decorate]

        res, nb_notes = self.midi_command.encode_midi_commands(plist)

        midi_cmd = self.midi_command.decode_midi_commands(res, nb_notes)

        assert(len(plist)==len(midi_cmd)), \
            self.fail("list haven't got the same size")

        for i in range(len(midi_cmd)):
            if midi_cmd[i][0][0] != plist[i][0][0]:
                self.fail("Problem with event encoding")
            if midi_cmd[i][0][1] != plist[i][0][1]:
                self.fail("Problem with note encoding")
            if midi_cmd[i][0][2] != plist[i][0][2]:
                self.fail("Problem with velocity encoding")

            if midi_cmd[i][1] != plist[i][1] - plist[0][1]:
                self.fail("Problem with timestamp encoding")


class TestSafeKeyboard(unittest.TestCase):
       def setUp(self):
              self.key_safe = SafeKeyboard()


       def test_note_index(self):
              pass


       def test_check_1(self):
              """Test SafeKeyboard with only one flow only one chan"""
              plist = [[[144, 120, 100], 1069], [[144, 120, 100], 1069],
                       [[128, 120, 100],1069], [[128, 120, 100], 1069],
                       [[144, 120, 100], 1069],[[128, 120, 100], 1069],
                       [[128, 120, 100],1069], [[144, 120, 100], 1069]]

              #Test with only one flow
              res = self.key_safe.check(plist)

              #Verify that all note are of afther the pass (nb off == nb on)
              for i in range(len(self.key_safe.keyboard)):
                     assert(self.key_safe.keyboard[0][i] == False), \
                         self.fail("Note history is not respected")


              #Checking alternate
              for i in range(len(res)):
                     if i % 2 == 0:
                            assert(res[i][0][0]==144), self.fail("Bad alternation")
                     else:
                            assert(res[i][0][0]==128), self.fail("Bad alternation")


       def test_check_2(self):
              """Test SafeKeyboard with all channels (doesn't have to delete notes)"""
              plist = [[[144, 120, 100], 1069], [[144, 110, 100], 1069],
                       [[128, 110, 100],1069], [[128, 120, 100], 1069],
                       [[128, 120, 100], 1069],[[128, 110, 100], 1069],
                       [[144, 120, 100],1069], [[144, 110, 100], 1069]]

              note_list = []
              for i in range(16):
                     for j in range(len(plist)):
                            note_list.append([[plist[j][0][0] + i,
                                               plist[j][0][1], plist[j][0][2]],
                                              plist[j][1]])

              res = self.key_safe.check(note_list)

              keyboard =  []

              #Building a map of all notes to test the result
              for i in range(16):
                     note_list =  [False for i in range(127)]
                     keyboard.append(note_list)


              for i in range(len(res)):
                     #Note on
                     if res[i][0][0]&240 == 144:
                            chan = res[i][0][0]&15
                            pitch = res[i][0][1]
                            if not keyboard[chan][pitch]:
                                   keyboard[chan][pitch] = True
                            else:
                                   self.fail("Problem of alternation")

                     #Note off
                     elif res[i][0][0]&240 == 128:
                            chan = res[i][0][0]&15
                            pitch = res[i][0][1]
                            if keyboard[chan][pitch]:
                                   keyboard[chan][pitch] = False
                            else:
                                   self.fail("Problem of alternation")


