from twisted.trial import unittest
from rtpmidi.engines.midi.recovery_journal import *
from rtpmidi.engines.midi.midi_object import OldPacket
from rtpmidi.engines.midi.midi_object import MidiCommand
from rtpmidi.protocols.rtp.packets import RTPPacket, parse_rtppacket

class TestChannelJournal(unittest.TestCase):
    def setUp(self):
        self.channel_journal = ChannelJournal()

        #program change with msb and lsb
        self.plist = [[[176, 0, 75], 1000], [[176, 32, 110], 1000],
                      [[192, 110, 0], 1000]]

        self.plist_channel =  [[[176, 0, 75], 1000], [[176, 32, 110], 1000],
                               [[192, 110, 0], 1000]]

        #list of notes to test
        for i in range(128):
            #note on
            if i == 127:
                self.plist_channel.append([[144, i, 1], 10*i])
            else:
                self.plist_channel.append([[144, i, 127-i], 10*i])

            #note off
            self.plist_channel.append([[128, i, 100], 10*i])

            #controller change (no special)
            if i > 32 and i < 100 :
                self.plist_channel.append([[176, i, 127 - i], 10*i])

    def test_header(self):
        #Creating header with default argument
        header = self.channel_journal.header(1, 10)

        #Testing length and type
        assert(len(header)==3),self.fail("length of header is not good")
        assert(type(header)==str), self.fail("Wrong type returned")

        #Creating header with custom argument
        header = self.channel_journal.header(1, 10, 1, 1, 0, 0, 1, 1,
                                             0, 0, 1, 1)

        #Testing length and type
        assert(len(header)==3), self.fail("length of header is not good")
        assert(type(header)==str), self.fail("Wrong type returned")

    def test_dispatch_data(self):
        """Testing with normal feature"""
        dico = {}
        dico[1] = self.plist_channel
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)

        #Checking length of each list retured
        assert(len(controllers)==67), self.fail("Wrong size for controllers list")
        assert(len(programs)==3), self.fail("Wrong size for programs list returned")
        assert(len(notes)==256), self.fail("Wrong size for notes list returned")

    def test_dispatch_data_1(self):
        """Testing commands that has special cares OMNI ON/OFF and POLY/MONO"""
        dico = {}

        #Controllers test
        #OMNI ON/OFF
        #omni_on then omni_off
        self.plist = [[[176, 125, 75], 1000], [[176, 124, 110], 1000]]

        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, \
            extras, afters, poly_afters = self.channel_journal.dispatch_data(dico)

        assert(len(controllers)==2), \
            self.fail("Wrong size for controllers list")
        assert(controllers[0][0][1]==124), \
            self.fail("Wrong priority applied for omni feature (omni on then omni off)")

        #omni_off then omni_on
        self.plist = [[[176, 124, 75], 1000], [[176, 125, 110], 1000]]
        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)

        assert(len(controllers)==2), self.fail("Wrong size for controllers list")
        assert(controllers[0][0][1]==124), \
            self.fail("Wrong priority applied for omni feature (omni off then omni on)")

        #solo omni off
        self.plist =  [[[176, 124, 110], 1000]]
        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)

        assert(len(controllers)==1), \
            self.fail("Wrong size for controllers list")
        assert(controllers[0][0][1]==124), \
            self.fail("Wrong priority applied for omni feature (solo omni off)")

        #solo omni on
        self.plist =  [[[176, 125, 110], 1000]]
        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)

        assert(len(controllers)==1), self.fail("Wrong size for controllers list")
        assert(controllers[0][0][1]==125), \
            self.fail("Wrong priority applied for omni feature (solo omni on)")

        #MONO / POLY
        #mono then poly
        self.plist = [[[176, 126, 75], 1000], [[176, 127, 110], 1000]]

        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)

        assert(len(controllers)==2), \
            self.fail("Wrong size for controllers list")
        assert(controllers[0][0][1]==127), \
            self.fail("Wrong priority applied for poly feature (mono on then poly)")

        #poly then mono
        self.plist = [[[176, 127, 75], 1000], [[176, 126, 110], 1000]]
        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)


        assert(len(controllers)==2), \
            self.fail("Wrong size for controllers list")
        assert(controllers[0][0][1]==127), \
            self.fail("Wrong priority applied for poly feature (poly then mono)")

        #solo poly
        self.plist =  [[[176, 127, 110], 1000]]
        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)

        assert(len(controllers)==1), \
            self.fail("Wrong size for controllers list")
        assert(controllers[0][0][1]==127), \
            self.fail("Wrong priority applied for poly feature (solo poly)")

        #solo mono
        self.plist =  [[[176, 126, 110], 1000]]
        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)


        assert(len(controllers)==1), \
            self.fail("Wrong size for controllers list")
        assert(controllers[0][0][1]==126), \
            self.fail("Wrong priority applied for mono feature (solo mono)")

    def test_dispatch_data_2(self):
        """Testing commands that has special cares RESET ALL and MSB/LSB"""
        dico = {}
        #MSB/LSB
        #solo MSB (no prog change following)
        self.plist =  [[[176, 0, 110], 1000]]
        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)

        assert(len(controllers)==1), \
            self.fail("Wrong size for controllers list testing solo MSB")
        assert(controllers[0][0][1]==0), \
            self.fail("Wrong decision take for a solo MSB")
        assert(controllers[0][0][2]==110), \
            self.fail("Wrong decision take for a solo MSB")

        #solo LSB (no prog change following)
        self.plist =  [[[176, 32, 110], 1000]]
        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)

        assert(len(controllers)==1), \
            self.fail("Wrong size for controllers list testing solo LSB")
        assert(controllers[0][0][1]==32), \
            self.fail("Wrong decision take for a solo MSB")
        assert(controllers[0][0][2]==110), \
            self.fail("Wrong decision take for a solo LSB")


        #MSB and prog change
        self.plist =  [[[176, 0, 110], 1000], [[192, 110, 0], 1000]]
        dico[1] = self.plist
        special_consideration, controllers, programs, system_p, wheels, notes, extras, \
            afters, poly_afters = self.channel_journal.dispatch_data(dico)

        assert(len(controllers)==0), \
            self.fail("Wrong size for controllers list testing MSB and prog change")

        assert(len(programs)==2), \
            self.fail("Wrong size for controllers list testing MSB and prog change")
        assert(programs[0][0][0]==176), \
            self.fail("Wrong decision take for MSB and prog changeB")
        assert(programs[0][0][1]==0), \
            self.fail("Wrong decision take for MSB and prog change")

        assert(programs[1][0][0]==192), \
            self.fail("Wrong decision take for MSB and prog change")
        assert(programs[1][0][1]==110), \
            self.fail("Wrong decision take for MSB and prog change")

        #TODO reset ALL wheels/after touch

    def test_dispatch_data_3(self):
         """Testing commands with only note on and note off"""
         dico = {}
         custom_list_1 = [[[144, 70, 100, 0], 1535516382],
                          [[128, 70, 100, 0], 1535516382],
                          [[144, 70, 100, 0], 1535516382],
                          [[128, 70, 100, 0], 1535516382],
                          [[144, 70, 100, 0], 1535516382],
                          [[128, 70, 100, 0], 1535516382],
                          [[144, 70, 100, 0], 1535516382],
                          [[128, 70, 100, 0], 1535516382],
                          [[144, 70, 100, 0], 1535516382]]

         dico[1986] = custom_list_1

         custom_list_2 = [[[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392],
                          [[128, 70, 100, 0], 1535516392],
                          [[144, 70, 100, 0], 1535516392]]

         dico[1987] = custom_list_2

         custom_list_3 =  [[[128, 70, 100, 0], 1535516402],
                           [[144, 70, 100, 0], 1535516402],
                           [[128, 70, 100, 0], 1535516402],
                           [[144, 70, 100, 0], 1535516402],
                           [[128, 70, 100, 0], 1535516402],
                           [[144, 70, 100, 0], 1535516402],
                           [[128, 70, 100, 0], 1535516402],
                           [[144, 70, 100, 0], 1535516402],
                           [[128, 70, 100, 0], 1535516402],
                           [[144, 70, 100, 0], 1535516402],
                           [[128, 70, 100, 0], 1535516402],
                           [[144, 70, 100, 0], 1535516402],
                           [[128, 70, 100, 0], 1535516402],
                           [[144, 70, 100, 0], 1535516402],
                           [[128, 70, 100, 0], 1535516402],
                           [[144, 70, 100, 0], 1535516402],
                           [[128, 70, 100, 0], 1535516402]]

         dico[1988] = custom_list_2

         special_consideration, controllers, programs, system_p, wheels, \
             notes, extras, afters, poly_afters \
             = self.channel_journal.dispatch_data(dico)


    def test_parse_header(self):
        """Test parsing header Channel Journal"""
        #Creating header with default argument
        header = self.channel_journal.header(1, 10)

        header_parsed = self.channel_journal.parse_header(header)
        #Testing content
        assert(header_parsed[1]==1), \
            self.fail("Problem getting true value of CHAN")
        assert(header_parsed[3]==10), \
            self.fail("Problem getting true value of L")

        #Creating header with custom argument
        header = self.channel_journal.header(1, 10, 1, 1, 0, 0, 1, 1, \
                                                 0, 0, 1, 1)
        header_parsed = self.channel_journal.parse_header(header)

        #Testing content ( s, chan, h, length, p, c, m, w, n, e, t, a )
        assert(header_parsed[0]==1), self.fail("Wrong value for marker_s")
        assert(header_parsed[1]==1), self.fail("Wrong value for chan")
        assert(header_parsed[2]==1), self.fail("Wrong value for marker_h")
        assert(header_parsed[3]==10), self.fail("Wrong value for length")
        assert(header_parsed[4]==1), self.fail("Wrong value for marker_p")
        assert(header_parsed[5]==1), self.fail("Wrong value for marker_c")
        assert(header_parsed[6]==0), self.fail("Wrong value for marker_m")
        assert(header_parsed[7]==0), self.fail("Wrong value for marker_w")
        assert(header_parsed[8]==1), self.fail("Wrong value for marker_n")
        assert(header_parsed[9]==1), self.fail("Wrong value for marker_e")
        assert(header_parsed[10]==0), self.fail("Wrong value for marker_t")
        assert(header_parsed[11]==0), self.fail("Wrong value for marker_a")


        #Creating header with custom argument
        header = self.channel_journal.header(0, 164, 0, 0, 0, 0, 0, 0, \
                                                 0, 0, 0, 0)
        header_parsed = self.channel_journal.parse_header(header)

        #Testing content ( s, chan, h, length, p, c, m, w, n, e, t, a )
        assert(header_parsed[0]==0), self.fail("Wrong value for marker_s")
        assert(header_parsed[1]==0), self.fail("Wrong value for chan")
        assert(header_parsed[2]==0), self.fail("Wrong value for marker_h")
        assert(header_parsed[3]==164), self.fail("Wrong value for length")
        assert(header_parsed[4]==0), self.fail("Wrong value for marker_p")
        assert(header_parsed[5]==0), self.fail("Wrong value for marker_c")
        assert(header_parsed[6]==0), self.fail("Wrong value for marker_m")
        assert(header_parsed[7]==0), self.fail("Wrong value for marker_w")
        assert(header_parsed[8]==0), self.fail("Wrong value for marker_n")
        assert(header_parsed[9]==0), self.fail("Wrong value for marker_e")
        assert(header_parsed[10]==0), self.fail("Wrong value for marker_t")
        assert(header_parsed[11]==0), self.fail("Wrong value for marker_a")

    def test_update(self):
        """Test create channel journal"""
        dico = {}
        dico[1] = self.plist_channel

        #creating channel
        self.channel_journal.update(dico)
        channel = self.channel_journal.content
        note_off_presence = 1

        #Testing type
        assert(type(channel)==str), self.fail("Wrong type returned")

        #Testing size ( (note_off + note_on + header_n) + (controllers + header_c)
        #+ (chapter_p) + len(header_channel)
        length_wait = (16 + 2 ) + (67 * 2 +1) + 3 + 3
        assert( len(channel) == length_wait), self.fail("Wrong size returned")

        #Testing note off presence marker
        assert(note_off_presence==1), \
            self.fail("Problem with note off presence marker")

    def test_parse(self):
        #creating channel
        dico = {}
        dico[1] = self.plist_channel
        self.channel_journal.update(dico)
        channel = self.channel_journal.content
        #Que verifier ( le recovery journal se charge de parser le header
        #des differents channel pour savoir comment les parser ??
        #parsing header manualy!
        channel_h = channel[:3]
        res = self.channel_journal.parse_header(channel_h)
        channel_size = res[3]

        #extracting channel
        channel = channel[3:3+channel_size]

        marker_p, marker_c, marker_m, marker_w, marker_n, marker_e, marker_t, \
            marker_a =  res[4:]


        channel_p = self.channel_journal.parse_channel_journal(channel,
                                                               marker_p,
                                                               marker_c,
                                                               marker_m,
                                                               marker_w,
                                                               marker_n,
                                                               marker_e,
                                                               marker_t,
                                                               marker_a)

        #Testing type
        assert(type(channel_p)==list), self.fail("Wrong type returned")

        #Testing len -128 note On that must be filtred at the creation
        len_expected = len(self.plist_channel) - 128

        assert(len(channel_p)==len_expected), \
            self.fail("Nb note from recovery journal parsed is not "\
                          + "corresponding to the nb of notes put at the "\
                          + "creation")

        #Testing content
        self.plist_channel =  [[[192, 110, 0], 1000], [[176, 0, 75], 1000], [[176, 32, 110], 1000]]

        #list of notes to test
        for i in range(128):
            #controller change (no special)
            if i > 32 and i < 100 :
                self.plist_channel.append([[176, i, 127 - i], 10*i])

        for i in range(128):
            #note off
            self.plist_channel.append([[128, i, 100], 10*i])



        for i in range(len(self.plist_channel)):
            #Testing note value
            assert(self.plist_channel[i][0]==channel_p[i]), \
                self.fail("Wrong note value returned")


class TestRecoveryJournal(unittest.TestCase):
    def setUp(self):
        self.recovery_journal = RecoveryJournal()
        self.partition_on = []
        self.partition_off = []

        #COmplete notes
        #Note On
        for i in range(127):
            self.partition_on.append( [[144, i, 100], 1000])

        #Note Off
        for i in range(127):
            self.partition_off.append( [[128, i, 100], 1000])

        #Program
        progs =  [[[192, 120, 0], 1000]]
        for prog in progs:
             self.partition_on.append(prog)
             self.partition_off.append(prog)

        #Wheels
        wheels =  [[[224, 0, 0], 1000],[[224, 0, 1], 1000] ]
        for wheel in wheels:
            self.partition_on.append(wheel)
            self.partition_off.append(wheel)

        #Controllers
        for i in range(127):
             self.partition_on.append( [[176, i, 100], 1000])
             self.partition_off.append( [[176, i, 100], 1000])


        #Aftertouch
        for i in range(127):
             self.partition_on.append( [[160, i, 100], 1000])
             self.partition_off.append( [[160, i, 100], 1000])


    def test_header(self):
        """Test recovery journal header creation"""
        #Creating header
        header = self.recovery_journal.header(10, 15, marker_s=1)

        #Testing type
        assert(type(header)==str), self.fail("Wrong type returned")

        #Testing length
        assert(len(header)==3), self.fail("length of header is not good")

    def test_parse_header(self):
        """Test recovery journal header parsong"""
        #Creating header
        header = self.recovery_journal.header(10, 15, marker_s=1)

        #Parsing header
        header_parsed = self.recovery_journal.parse_header(header)

        #Testing content
        assert(header_parsed[0] == 1), \
            self.fail("Problem getting true value of marker_s")
        assert(header_parsed[4] == 10), \
            self.fail("Problem getting true value of TOTCHAN")
        assert(header_parsed[5] == 15), \
            self.fail("Problem getting true value of checkpoint packet")

    def test_update(self):
        """Test simple recovery journal creation"""
        #Test for one packet
        #Creating packet
        packy = OldPacket(6, self.partition_on, 0)

        #Creating recovery journal
        self.recovery_journal.update(packy)
        recovery_journal = self.recovery_journal.content

        #Testing type
        assert(type(recovery_journal) == str), self.fail("Wrong type returned")
        recovery_journal_parsed = self.recovery_journal.parse(recovery_journal)

        #print recovery_journal_parsed
        #Testing length (recovery_h + 2 * channel_h + 2 * chapter_n_h
        #+ 2 *note_on + note_off_2 + programm change
        #length_expected = 3 + 2 * 1 + (2 + 3) + (2 + 14)

        #assert( len(recovery_journal) == length_expected ),
        #self.fail("Wrong size returned")

        #TODO test for several packet

    def test_create_recovery_journal(self):
        """Test with several channels for recovery journla creation"""
        self.plist_channel_0 =  [ [[176, 0, 75], 1000],
                                  [[176, 32, 110], 1000],
                                  [[192, 110, 0], 1000]]
        #list of notes to test
        for i in range(128):
            #note off
            self.plist_channel_0.append([[128, i, 100], 10*i])

            #controller change (no special)
            if i > 32 and i < 100 :
                self.plist_channel_0.append([[176, i, 127 - i], 10*i])


        self.plist_channel_1 =  [[[177, 0, 75], 1000],
                                 [[177, 32, 110], 1000],
                                 [[193, 110, 0], 1000]]
        for i in range(128):
            #note on
            if i == 127:
                self.plist_channel_1.append([[145, i, 1], 10*i])
            else:
                self.plist_channel_1.append([[145, i, 127-i], 10*i])

            #controller change (no special)
            if i > 32 and i < 100 :
                self.plist_channel_0.append([[177, i, 127 - i], 10*i])


        self.plist_channel_0.extend(self.plist_channel_1)
        packy = OldPacket(6, self.plist_channel_0, 0)


        #Creating recovery journal
        self.recovery_journal.update(packy)
        recovery_journal = self.recovery_journal.content
        # header + channel_1(header_channel + prog_chapter + note_chapter + control chapter) + channel_2...
        length_expected = 3 + ( 3 +  3 + (2 + 16) + (1 + 2*67) ) \
            + ( 3 +  3 + (2 + 2 * 128) + (1 + 2*67) )

        assert(type(recovery_journal)==str), self.fail("Wrong type returned")
        assert(len(recovery_journal)==length_expected), self.fail("Wrong length returned")

    def test_parse(self):
        """Test simple parsing of recovery journal with note on"""
        #Test for one packet
        #Creating packet list
        packy = OldPacket(6, [[[128, 62, 100],1000]], 0)

        #Creating recovery journal
        self.recovery_journal.update(packy)
        recovery_journal = self.recovery_journal.content
	print "len of recovery journa for a note off: ", len(self.recovery_journal.content)
        #Parsing recovery journal
        recovery_journal_parsed = self.recovery_journal.parse(recovery_journal)

        #Testing nb notes
        assert(len(recovery_journal_parsed)==1), \
            self.fail("Nb note from recovery journal "
                      + "parsed is not corresponding to the nb of notes put at"
                      + "the creation")


        decorate = [(t[0][0], t[0][1], t[0][2], t) for t in recovery_journal_parsed]
        decorate.sort()
        recovery_journal_parsed =  [t[3] for t in decorate]

        decorated = [(t[0][0], t[0][1], t[0][2], t) for t in self.partition_off]
        decorated.sort()
        partition_off =  [t[3] for t in decorated]

        #Testing content
	print recovery_journal_parsed
        for i in range(len(recovery_journal_parsed)):
            assert(recovery_journal_parsed[i][0][0]==partition_off[i][0][0]), \
                self.fail("Problem getting right event after parsing")

            assert(recovery_journal_parsed[i][0][1]==partition_off[i][0][1]), \
                self.fail("Problem getting right note number after parsing")

            #Pb velocity and change from vel 0 to note off
            assert(recovery_journal_parsed[i][0][2]==partition_off[i][0][2]), \
                self.fail("Problem getting right velocity number after" \
                              + " parsing")
    test_parse.skip = "This always fails for some reason." # FIXME



    def test_parse_1(self):
        """Test simple parsing of recovery journal with note on"""
        packy = OldPacket(6, self.partition_on, 0)

        #Creating recovery journal
        self.recovery_journal.update(packy)
        recovery_journal = self.recovery_journal.content

    def test_packet_with_recovery(self):
	midi_list = [[[128, 10, 0], 1000],
                     [[144, 32, 110], 1000]]

	recovery_journal_system = RecoveryJournal()
	seq = 12

	#midi session part (sending)
	packet = OldPacket(seq, midi_list, 0)

	midi_list_formated, length = MidiCommand().encode_midi_commands(midi_list)
	header = MidiCommand().header(0, 1, 0, 0, length)

        #Building Chunk

	recovery_journal_system.update(packet)
	recovery_journal = recovery_journal_system.content

	chunk = header + midi_list_formated + recovery_journal
	#protocol part
	packet = RTPPacket(424242, seq, 10, chunk, 96, marker=1)

	bytes = packet.netbytes()
	packet = parse_rtppacket(bytes)

	#midisession part (receiving)
	marker_b, marker_j, marker_z, marker_p, length = MidiCommand().parse_header(packet.data[0])
	if marker_p :
            #silent packet with recovery
            midi_list = []

        else:
            #normal packet
            #Extract Midi Note (length en nb notes)
	    print "test 1:", len(packet.data[1:length*7+1])
            midi_list = packet.data[1:length*7+1]

            #Decoding midi commands
            midi_list =  MidiCommand().decode_midi_commands(midi_list, length)

            #Saving feed history
            packet_to_save = OldPacket(seq, midi_list, 0)

	#Extract Midi Recovery Journal if is present in the packet and
        #the previous packet has been lost
        if marker_j:
	    print "recovery journal"
	    print len(packet.data[length*7+1:])
            journal = packet.data[length*7+1:]

            #Parse Recovery journal
            r_journal = recovery_journal_system.parse(journal)




class TestLonelyFunctions(unittest.TestCase):
    def setUp(self):
        pass

    def test_compare_history_with_recovery(self):
        """Single test on compare history with recovery"""
        journal = [[[128, 65, 100], 0], [[128, 69, 100], 0],
                   [[128, 70, 100], 0], [[128, 72, 100], 0]]

        midi_history =  [[[128, 69, 100], 1000],
                         [[144, 65, 100], 1009],
                         [[144, 72, 100], 1012]]

        res = compare_history_with_recovery(journal, midi_history)

        assert(type(res)==list), self.fail("Wrong type returned")
        assert(len(res)==3), self.fail("Wrong size returned")

        assert(res[0][0][0]==128), self.fail("Wrong event returned")
        assert(res[0][0][1]==65), self.fail("Wrong pitch returned")

        assert(res[1][0][0]==128), self.fail("Wrong event returned")
        assert(res[1][0][1]==70), self.fail("Wrong pitch returned")

        assert(res[2][0][0]==128), self.fail("Wrong event returned")
        assert(res[2][0][1]==72), self.fail("Wrong pitch returned")
