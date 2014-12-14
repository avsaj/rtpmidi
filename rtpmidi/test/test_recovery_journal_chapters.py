from twisted.trial import unittest

from rtpmidi.engines.midi.recovery_journal_chapters import *

class TestNote(unittest.TestCase):
    def setUp(self):
        self.note = Note()

    def test_note_on(self):
        #simple
        note_to_test = self.note.note_on(100, 90)

        #Testing type
        assert(type(note_to_test)==str), self.fail("Wrong type return")
        #length test
        assert(len(note_to_test)==2), \
            self.fail("len of note On is higher than 2 octet")

        #with all args
        note_to_test = self.note.note_on(100, 90, 0, 1)
        #length test
        assert(len(note_to_test)==2), \
            self.fail("len of note On is higher than 2 octet")

    def test_parse_note_on(self):
        #Simple
        note_to_test = self.note.note_on(100, 90)
        res_n = self.note.parse_note_on(note_to_test)

        #Testing content
        assert(res_n[1] == 100), self.fail("Note number is not respected")
        assert(res_n[3] == 90), self.fail("Note velocity is not respected")

        #With all args
        note_to_test = self.note.note_on(100, 90, 0, 1)
        res_n = self.note.parse_note_on(note_to_test)

        #Testing content
        assert(res_n[0] == 1), self.fail("S mark is not respected")
        assert(res_n[1] == 100), self.fail("Note number is not respected")
        assert(res_n[2] == 0), self.fail("Y mark not respected")
        assert(res_n[3] == 90), self.fail("Note velocity is not respected")

    def test_note_off(self):
        #list of notes to test (note from the same midi channel)
        plist = [[[128, 57, 100],1000], [[144, 4, 0],1000], \
                     [[144, 110, 0],1000], [[144, 112, 0],1000]]

        #setting low and high like in create_chapter_n
        high = 113 / 8
        low = 4 / 8

        #selecting note off like in create_chapter_n
        note_off_list = [ plist[i][0][1]  for i in range(len(plist))\
                        if (plist[i][0][0]&240 == 128) or \
                        (plist[i][0][2] == 0) ]
        res = self.note.note_off(note_off_list, low, high)

        #type test
        assert(type(res)==str), self.fail("Wrong type return")

        #checking size
        size_wait = high - low + 1
        assert(len(res) == size_wait), \
            self.fail("Problem of size with note off creation")

    def test_parse_note_off(self):
        """Test parse note off"""
        #list of notes to test
        #plist = [[[128, 120, 100],1000],[[145, 4, 0],1000],\
         #            [[145, 110, 0],1000], [[145, 112, 0],1000]]

        #setting low and high like in create_chapter_n
        note_off_test =  [12, 57, 112, 114 ]
        high = 115 / 8
        low = 12 / 8

        res = self.note.note_off(note_off_test, low, high)

        #testing the result of parsing
        res_parsed = self.note.parse_note_off(res, low, high)

        #Testing type
        assert(type(res_parsed)==list), self.fail("Wrong type returned")

        #res_parsed.sort()
        #Testing content
        note_off_test =  [12, 57, 112, 114 ]
        for i in range(len(note_off_test)):
            assert(res_parsed[i][1]==note_off_test[i]), \
                self.fail("Problem getting the good value for note off encoded")


class TestChapterP(unittest.TestCase):
    def setUp(self):
        self.chapter_p = ChapterP()

        #program change with msb and lsb
        self.plist = [[[176, 0, 75], 1000], [[176, 32, 110], 1000], \
                     [[192, 110, 0], 1000]]

        #program change without msb and lsb
        self.plist_1 = [[[192, 110, 0], 1000]]

    def test_update(self):
        """Testing chapter P creation from a list (with MSB and LSB)"""
        self.chapter_p.update(self.plist)
        chapter = self.chapter_p.content

        #Testing len
        assert(len(chapter)==3), \
            self.fail("Size of chapter p is not 24 bits!!!")

        #Testing type
        assert(type(chapter)==str), self.fail("Problem of type")

        #Testing content
        size, chapter_parse, marker_s, marker_x, marker_b  \
            = self.chapter_p.parse(chapter)

        #Testing content
        assert(marker_s==1), \
            self.fail("Problem getting right value of S")
        assert(chapter_parse[0][1]==110), \
            self.fail("Problem getting right value of PROGRAM")
        assert(marker_b==1), \
            self.fail("Problem getting right value of B")
        assert(chapter_parse[1][2]==75), \
            self.fail("Problem getting right value of MSB")
        assert(marker_x==0), \
            self.fail("Problem getting right value of X")
        assert(chapter_parse[2][2]==110), \
            self.fail("Problem getting right value of LSB")

    def test_update_1(self):
        """Testing chapter P creation from a list (without MSB and LSB)"""
        self.chapter_p.update(self.plist_1)
        chapter = self.chapter_p.content

        #Testing len
        assert(len(chapter)==3), \
            self.fail("Size of chapter p is not 24 bits!!!")

        #Testing type
        assert(type(chapter)==str), self.fail("Problem of type")

        #Testing content
        size, chapter_parse, marker_s, marker_x, marker_b \
            = self.chapter_p.parse(chapter)

        #Testing content
        assert(marker_s==1), \
            self.fail("Problem getting right value of S")
        assert(chapter_parse[0][1]==110), \
            self.fail("Problem getting right value of PROGRAM")
        assert(marker_b==0), \
            self.fail("Problem getting right value of B")
        assert(marker_x==0), \
            self.fail("Problem getting right value of X")



class TestChapterC(unittest.TestCase):
    def setUp(self):
        self.chapter_c = ChapterC()
        self.plist =  []

        for i in range(127):
            self.plist.append([[176, i, 100],6])


    def test_header(self):
        """Test header creation ChapterC"""
        #Creating header
        header = self.chapter_c.header(10, 1)

        #Testing type
        assert(type(header)==str), self.fail("Wrong type returned")
        #Testing length
        assert(len(header)==1), self.fail("Wrong header size")

    def test_parse_header(self):
        """Test header parsing ChapterC"""
        #Creating header
        header = self.chapter_c.header(10, 1)

        #Parsing header
        header_parsed = self.chapter_c.parse_header(header)

        #Testing type
        assert(type(header_parsed)==tuple), self.fail("Wrong size returned")

        #Testing content
        assert(header_parsed[0]==1), self.fail("Wrong marker_s value")
        assert(header_parsed[1]==10), self.fail("Wrong length value")

    def test_create_log_c(self):
        """Test create log C (individual component from ChapterC"""
        res = self.chapter_c.create_log_c(0, 110, 1, 90)
        assert(type(res)==str), self.fail("Wrong type returned")
        assert(len(res)==2), self.fail("Wrong size returned")

    def test_parse_log_c(self):
        """Test parsing individual component from chapterC"""
        res = self.chapter_c.create_log_c(0, 110, 1, 90)
        res_parsed = self.chapter_c.parse_log_c(res)

        assert(res_parsed[0]==0), self.fail("Wrong value for marker_s")
        assert(res_parsed[1]==110), self.fail("Wrong value for number")
        assert(res_parsed[2]==1), self.fail("Wrong value for marker_a")
        assert(res_parsed[3]==90), self.fail("Wrong value for value")


    def test_update(self):
        """Testing chapter C creation"""
        self.chapter_c.update(self.plist)
        assert(type(self.chapter_c.content)==str), self.fail("Wrong type returned")

        #length calc header == 1 + 2 * length
        length_wait = 1 + 2 * len(self.plist)
        assert(len(self.chapter_c.content)==length_wait), self.fail("Wrong length returned")


    def test_update_1(self):
        self.plist.append([[176, 42, 100],6])
        self.chapter_c.update(self.plist)
        length_wait = 1 + 2 * 127
        assert(len(self.chapter_c.content)==length_wait), self.fail("Wrong length returned")


    def test_parse(self):
        """Test chapter C parsing"""
        self.chapter_c.update(self.plist)

        size, parsed_res, marker_s = self.chapter_c.parse(self.chapter_c.content)
        assert(len(parsed_res)==len(self.plist)), \
            self.fail("Wrong number of command returned")

        for i in range(len(self.plist)):
            assert(parsed_res[i][0]==self.plist[i][0][0]), \
                self.fail("Wrong value returned for cmd")
            assert(parsed_res[i][1]==self.plist[i][0][1]), \
                self.fail("Wrong value returned for pitch")
            assert(parsed_res[i][2]==self.plist[i][0][2]), \
                self.fail("Wrong value returned for velocity")



    def test_trim(self):
        plist =  []
        plist.append([[176, 42, 100],6])
        plist.append([[176, 43, 100],7])
        plist.append([[176, 44, 100],8])
        self.chapter_c.update(plist)
        self.chapter_c.trim(7)
        assert(len(self.chapter_c.controllers)==1), self.fail("Problem erasing controllers on trim")


    def test_update_highest(self):
        plist =  []
        plist.append([[176, 42, 100],6])
        plist.append([[176, 43, 100],7])
        plist.append([[176, 44, 100],8])

        self.chapter_c.update(plist)
        assert(self.chapter_c.highest==8), \
            self.fail("Problem with highest on update")

        self.chapter_c.trim(7)
        assert(self.chapter_c.highest==8), \
            self.fail("Problem with highest on trim(1)")

        self.chapter_c.trim(8)
        assert(self.chapter_c.highest==0), \
            self.fail("Problem with highest on trim(2)")


class TestChapterW(unittest.TestCase):
    def setUp(self):
        self.chapter_w = ChapterW()
        self.plist = [[[224, 0,  120], 6], [[224, 1,  110], 6]]

    def test_update(self):
        """Test create chapter W"""
        self.chapter_w.update(self.plist)

        assert(type(self.chapter_w.content)==str), self.fail("Wrong type returned")
        assert(len(self.chapter_w.content)==2), \
            self.fail("Wrong size for chapter W part in recovery journal")

    def test_parse(self):
        self.chapter_w.update(self.plist)
        size, res_2, mark_s = self.chapter_w.parse(self.chapter_w.content)
        assert(mark_s == 1), \
            self.fail("Wrong value for S bit in Chapter W")
        assert(res_2[0][2]==120), \
            self.fail("Wrong value for wheel_1 in Chapter W")
        assert(res_2[1][2]==110), \
            self.fail("Wrong value for wheel_2 in Chapter W")

    def test_trim(self):
        self.chapter_w.update(self.plist)
        self.chapter_w.trim(6)

        for data in self.chapter_w.data_list:
            assert(data[0]==0), self.fail("Problem trimming chapter")

        assert(self.chapter_w.highest==0), self.fail("Wrong update for highest")


class TestChapterN(unittest.TestCase):
    def setUp(self):
        self.chapter_n = ChapterN()
        self.plist_on = []
        self.plist_off = []

        #List of notes to test
        #Note on
        for i in range(127):
            self.plist_on.append([[144, i, 100],6])

        #Note off
        for i in range(127):
            self.plist_off.append([[128, i, 100],7])


    def test_header(self):
        """Test Create header of chapterN """
        #Creating chapter
        self.chapter_n.update(self.plist_on)

        res = self.chapter_n.header()

        #length type test
        assert(len(res)==2), self.fail("length of header is not good")
        assert(type(res)==str), self.fail("Wrong type return")

    def test_parse_header(self):
        """Test parse header of ChapterN"""
        #Creating chapter
        self.chapter_n.update(self.plist_off)

        res = self.chapter_n.header()

        #Parsing
        res_parsed = self.chapter_n.parse_header(res)

        #Testing type
        assert(type(res_parsed)==tuple), self.fail("Wrong type return")

        #Testing content
        assert(res_parsed[1]==0), \
            self.fail("Problem getting good value of LEN")
        assert(res_parsed[2]==0), \
            self.fail("Problem getting good value of LOW")
        assert(res_parsed[3]==15), \
            self.fail("Problem getting good value of HIGH")


    def test_update(self):
        """Update with 127 note_off"""
        self.chapter_n.update(self.plist_off)

        #Test len content
        length_wait = 128 / 8 + 2

        assert(len(self.chapter_n.content)==length_wait), \
            self.fail("Wrong size for chapter encoded returned")

        #Test note_on
        assert(len(self.chapter_n.note_on)==0), \
            self.fail("Wrong nb of note on recorded")

        #Test note_off
        assert(len(self.chapter_n.note_off)==127), \
            self.fail("Wrong nb of note off recorded")

        #Test low
        assert(self.chapter_n.low==0), self.fail("Wrong low calculation")

        #Test high
        assert(self.chapter_n.high==15), self.fail("Wrong high calculation")

        #TEst highest
        assert(self.chapter_n.highest==7), self.fail("Wrong highest saved")

    def test_update_1(self):
        """Update with 127 note_on"""
        self.chapter_n.update(self.plist_on)

        #Test len content
        length_wait = 127 * 2 + 2

        assert(len(self.chapter_n.content)==length_wait), \
            self.fail("Wrong size for chapter encoded returned")

        #Test note_on
        assert(len(self.chapter_n.note_on)==127), \
            self.fail("Wrong nb of note on recorded")

        #Test note_off
        assert(len(self.chapter_n.note_off)==0), \
            self.fail("Wrong nb of note off recorded")

        #Test low
        assert(self.chapter_n.low==0), self.fail("Wrong low calculation")

        #Test high
        assert(self.chapter_n.high==0), self.fail("Wrong high calculation")

        #TEst highest
        assert(self.chapter_n.highest==6), self.fail("Wrong highest saved")

    def test_update_2(self):
        """Update with note_on / off and ..."""
        self.plist_on.append([[144, 42, 100],6])
        self.chapter_n.update(self.plist_on)

        #Test len content
        length_wait = 127 * 2 + 2
        assert(len(self.chapter_n.content)==length_wait), \
            self.fail("Wrong size for chapter encoded returned")

        assert(len(self.chapter_n.note_on)==127), \
            self.fail("Wrong nb of note on recorded")

        self.chapter_n.update(self.plist_off)

        #Test len content
        length_wait = 128 / 8 + 2

        assert(len(self.chapter_n.content)==length_wait), \
            self.fail("Wrong size for chapter encoded returned")

        #Test note_on
        assert(len(self.chapter_n.note_on)==0), \
            self.fail("Wrong nb of note on recorded")

        #Test note_off
        assert(len(self.chapter_n.note_off)==127), \
            self.fail("Wrong nb of note off recorded")


    def test_parse(self):
        """ Test parse chapter N with several notes"""
        #creating chapter
        self.chapter_n.update(self.plist_off)

        size, notes_parsed = self.chapter_n.parse(self.chapter_n.content)
        assert(len(notes_parsed)==127), self.fail("Wrong number of notes returned")
        assert(size==18), self.fail("Wrong size of encoded chapter")

    def test_parse_2(self):
	off_mont = [[[128, 62, 100],1000]]
	self.chapter_n.update(off_mont)
    	size, notes_parsed = self.chapter_n.parse(self.chapter_n.content)


    def test_trim(self):
        self.chapter_n.update(self.plist_off)
        self.chapter_n.trim(6)

        #Test highest
        assert(self.chapter_n.highest==7), \
            self.fail("Wrong highest saved")

        #Test note_on
        assert(len(self.chapter_n.note_on)==0), \
            self.fail("Wrong nb of note on recorded")

        #Test note_off
        assert(len(self.chapter_n.note_off)==127), \
            self.fail("Wrong nb of note off recorded")

        self.chapter_n.trim(7)
        assert(len(self.chapter_n.note_off)==0), \
            self.fail("Wrong nb of note off recorded after trim")


    def test_update_highest(self):
        plist = []
        plist.append([[144, 1, 100],6])
        plist.append([[144, 1, 100],7])
        plist.append([[144, 1, 100],8])

        self.chapter_n.update(plist)
        assert(self.chapter_n.highest==8), \
            self.fail("wrong update of highest on update")

        self.chapter_n.trim(7)
        assert(self.chapter_n.highest==8), \
            self.fail("wrong update of highest on trim")

        self.chapter_n.trim(8)
        assert(self.chapter_n.highest==0), \
            self.fail("wrong update of highest on trim")


class TestChapterT(unittest.TestCase):
    def setUp(self):
        self.chap_t = ChapterT()

    def test_update(self):
        """Test Create Chapter T (After Touch)"""
        plist = [[[208, 80, 98], 1000]]
        self.chap_t.update(plist)
        res = self.chap_t.content
        assert(type(res)==str), self.fail("Wrong type returned")
        assert(len(res) == 1), self.fail("Wrong size returned")

        assert(self.chap_t.highest==1000), self.fail("Problem with highest update")

    def test_parse(self):
        """Test parse Chapter T"""
        self.chap_t.update( [[[208, 80, 0], 1000]])
        res = self.chap_t.content

        size, midi_cmd = self.chap_t.parse(res)
        pressure = midi_cmd[0][1]
        assert(size==1), self.fail("Wrong size returned")
        assert(pressure==80), self.fail("Wrong value returned for pressure")


class TestChapterA(unittest.TestCase):
    def setUp(self):
        self.chap_a = ChapterA()

    def test_header(self):
        """Test header for Chapter A"""
        res = self.chap_a.header(1, 127)
        assert(type(res)==str), self.fail("Wrong type returned")
        assert(len(res)==1), self.fail("Wrong size returned")

    def test_parse_header(self):
        """Test parse header Chapter A"""
        res = self.chap_a.header(1, 127)
        marker_s, length = self.chap_a.parse_header(res)
        assert(marker_s==1), self.fail("Wrong value returned for marker S")
        assert(length==127), self.fail("Wrong value returned for length")

    def test_create_log_a(self):
        """Test Create log A"""
        res = self.chap_a.create_log_a(1, 127, 1, 127)
        assert(type(res)==str), self.fail("Wrong type returned")
        assert(len(res)==2), self.fail("Wrong size returned")

    def test_parse_log_a(self):
        """Test Parse log A"""
        res = self.chap_a.create_log_a(1, 127, 1, 110)
        marker_s, notenum, marker_x, pressure = self.chap_a.parse_log_a(res)

        assert(marker_s==1), self.fail("Wrong value returned for marker S")
        assert(notenum==127), self.fail("Wrong value returned for length")
        assert(marker_x==1), self.fail("Wrong value returned for marker S")
        assert(pressure==110), self.fail("Wrong value returned for length")

    def test_update(self):
        """Test create Chapter A"""
        midi_cmd =  [[[160, 80, 98], 1000], [[160, 82, 90], 1000]]
        self.chap_a.update(midi_cmd)
        res = self.chap_a.content
        len_expected = 1 + 2 * len(midi_cmd)

        assert(type(res)==str), self.fail("Wrong type returned")
        assert(len(res)==len_expected), self.fail("Wrong size returned")

    def test_update_1(self):
        """Test create Chapter A with a big amount of commands"""
        #With 127 notes (max is 127)
        midi_cmd =  []
        for i in range(127):
            midi_cmd.append([[160, i, 98], 1])


        self.chap_a.update(midi_cmd)

        #Test content
        res = self.chap_a.content
        size, marker_s, midi_cmd_parsed = self.chap_a.parse(res)
        size_waited = 1 + 2 *127
        assert(size==size_waited), self.fail("Wrong size returned for 127 notes(1) !")

        midi_cmd =  []
        midi_cmd.append([[160, 42, 98], 2])
        self.chap_a.update(midi_cmd)

        #Test content
        res = self.chap_a.content
        size, marker_s, midi_cmd_parsed = self.chap_a.parse(res)
        assert(size==size_waited), self.fail("Wrong size returned for 127 notes(2) !")


    def test_update_2(self):
        """Test create Chapter A with a big amount of commands
        in a lonely function call"""
        #With 127 notes (max is 127)
        midi_cmd =  []
        for i in range(127):
            midi_cmd.append([[160, i, 98], 1])

        for i in range(127):
            midi_cmd.append([[160, i, 98], 1])


        self.chap_a.update(midi_cmd)

        #Test content
        res = self.chap_a.content
        size, marker_s, midi_cmd_parsed = self.chap_a.parse(res)
        size_waited = 1 + 2 *127
        assert(size==size_waited), self.fail("Wrong size returned for 127 notes(1) !")


    def test_parse(self):
        """Test parsing chapterA"""
        midi_cmd =  [[[160, 80, 98], 1000], [[160, 82, 90], 1000]]
        self.chap_a.update(midi_cmd)
        res = self.chap_a.content

        size, marker_s, midi_cmd_parsed = self.chap_a.parse(res)

        assert(size==5), self.fail("Wrong value for size returned")
        assert(marker_s==1), self.fail("Wrong value for marker_s returned")
        assert(len(midi_cmd)==len(midi_cmd)), self.fail("Wrong size returned")

        for i in range(len(midi_cmd)):
            assert(midi_cmd[i][0]==midi_cmd_parsed[i]), \
                self.fail("Wrong value returned")



    def test_trim(self):
        """Test trim without note remplacement"""
        #Adding Packet 1000
        midi_cmd =  [[[160, 80, 98], 1000], [[160, 82, 90], 1000]]
        self.chap_a.update(midi_cmd)

        #Adding Packet 1001
        midi_cmd =  [[[160, 84, 98], 1001], [[160, 86, 90], 1001]]
        self.chap_a.update(midi_cmd)

        #Adding Packet 1002
        midi_cmd =  [[[160, 88, 98], 1002], [[160, 90, 90], 1002]]
        self.chap_a.update(midi_cmd)

        self.chap_a.trim(1001)

        res = self.chap_a.parse(self.chap_a.content)

    def test_update_highest(self):
        #Adding Packet 1000
        midi_cmd =  [[[160, 80, 98], 1000], [[160, 82, 90], 1000]]
        self.chap_a.update(midi_cmd)

        self.chap_a.update_highest()
        assert(self.chap_a.highest==1000), \
            self.fail("Update problem for highest after an update")

        #Adding Packet 1001
        midi_cmd =  [[[160, 84, 98], 1001], [[160, 86, 90], 1001]]
        self.chap_a.update(midi_cmd)

        self.chap_a.update_highest()
        assert(self.chap_a.highest==1001), \
            self.fail("Update problem for highest after an update")


        self.chap_a.trim(1001)
        assert(self.chap_a.highest==0), \
            self.fail("Update problem for highest after an trim")

