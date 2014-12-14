from twisted.trial.unittest import TestCase
from rtpmidi.engines.midi.list_circ import ListCirc, PacketCirc
from rtpmidi.engines.midi.midi_object import OldPacket


class TestListCirc(TestCase):
    def setUp(self):
        self.list_to_test = ListCirc(10)

    def tearDown(self):
        del self.list_to_test

    def test_to_list(self):

        #Testing type
        assert(type(self.list_to_test) == ListCirc), \
            self.fail("Problem with list type")

        #Test add note on first items
        for i in range(10):
            self.list_to_test.to_list(i)

        #Testing content
        for i in range(10):
            assert(self.list_to_test[i] == i),\
                self.fail("Problem with content of the listcirc")

        #Test replace note
        for i in range(20):
            self.list_to_test.to_list(i)

        #Testing size
        assert(len(self.list_to_test) == 10),\
            self.fail("Problem of size with the listcirc")

        #Testing content of the list
        for i in range(10):
            assert(self.list_to_test[i] == 10+i),\
                self.fail("Problem with content of the listcirc")


    def test_flush(self):
        #Test add note on first items
        for i in range(10):
            self.list_to_test.to_list(i)

        #Flushing list
        self.list_to_test.flush()

        #Testing attribute
        assert(len(self.list_to_test)==0), \
            self.fail("Problem flushing the list")

        assert(self.list_to_test.round==0), \
            self.fail("Problem with round attributeflushing the list")

        assert(self.list_to_test.index==0), \
            self.fail("Problem with index attribute flushing the list")



class TestPacketCirc(TestCase):
    """Testing packet Circ"""

    def setUp(self):
        self.packet_circ = PacketCirc(10)

        #list to test the packet list
        plist = [[[192, 120, 100],0],[[144, 104, 50],1], [[145, 110, 0],2], \
                     [[145, 112, 0],3], [[144, 124, 50],4], \
                     [[145, 114, 0],5], [[145, 12, 0],6]]

        #test without wrap around
        for i in range(10):
            #modify plist for each packet
            plist_1 = [ [[plist[j][0][0], plist[j][0][1], plist[j][0][2]], \
                           plist[j][1] + i] for j in range(len(plist)) ]
            packy = OldPacket(i, plist_1, 0)
            #Adding packet to list
            self.packet_circ.to_list(packy)

    def test_find_packet(self):
        #Trying find a packet
        emplacement = self.packet_circ.find_packet(5)

        #Testing type return
        assert(type(emplacement)==int), \
            self.fail("Problem with type returned in find packet function")

        packet = self.packet_circ[emplacement]

        #Testing type
        assert(type(packet)==OldPacket), \
            self.fail("Problem with type contained in packet list")

        #Testing content
        for i in range(len(packet.packet)):
            assert(packet.packet[i][1]==i+5), \
                self.fail("Problem getting right element , find packet fun")


    def test_get_packets_1_2(self):
        """Packet Circ Testing get packet (case: checkpoint > act_seq)"""
        #TestCase 1.2
        checkpoint = 6
        act_seq = 4
        midi_cmd = self.packet_circ.get_packets(checkpoint, act_seq)

        #Test len, 8 == nb packets to get
        length = (10 - 6 + 4)
        assert(len(midi_cmd) == length), \
            self.fail("Problem getting the good length from get_packets")

        #Verify content (base on timestamp control)
        #iterator modulo 10
        iterator = 7
        for i in range(len(midi_cmd)):
            midi_cmd_notes = midi_cmd[i].packet

            if i != 0:
                iterator = (iterator + 1 )% 10

            for j in range(len(midi_cmd_notes)):
                assert(midi_cmd_notes[j][1]== iterator + j), \
                    self.fail("Problem with midi cmd content")

    def test_get_packets_1_1(self):
        """Packet Circ Testing get packet (case: checkpoint > act_seq with wrap around)"""
        #TestCase 1.1
        checkpoint = 8
        act_seq = 1

        #Adapting list
        self.packet_circ.flush()

        #listto test the packet list
        plist = [[[192, 120, 100],0],[[144, 104, 50],1], [[145, 110, 0],2], \
                     [[145, 112, 0],3], [[144, 124, 50],4], \
                     [[145, 114, 0],5], [[145, 12, 0],6]]

        #Create the gap
        empty_list = []
        for i in range(8):
            packy = OldPacket(i, [], 0)
            #Adding packet to list
            self.packet_circ.to_list(packy)

        #fulling the list
        for i in range(10):
            #modify plist for each packet
            plist_1 = [ [[plist[j][0][0], plist[j][0][1], plist[j][0][2]], \
                           plist[j][1] + i] for j in range(len(plist)) ]

            packy = OldPacket(i, plist_1, 0)
            #Adding packet to list
            self.packet_circ.to_list(packy)

        midi_cmd = self.packet_circ.get_packets(checkpoint, act_seq)

        #Test len (nb packets)
        length = 3
        assert(len(midi_cmd) == length), \
            self.fail("Problem getting the good length from get_packets")

        #Testing content
        #iterator
        iterator = 9
        for i in range(len(midi_cmd)):
            #increment iterator
            if i != 0:
                iterator = (iterator + 1 )% 10

            midi_cmd_notes = midi_cmd[i].packet

            #Testing content of packet 9, 0, 1
            for j in range(len(midi_cmd_notes)):
                assert(midi_cmd_notes[j][1]== j + iterator), \
                    self.fail("Problem with midi cmd content")

    def test_get_packets_2(self):
        """Packet Circ Testing get packet (case: checkpoint < act_seq)"""
        #TestCase 2
        checkpoint = 2
        act_seq = 8
        midi_cmd = self.packet_circ.get_packets(checkpoint, act_seq)

        #Test len, of packet list returned
        length = (8 - 2)
        assert(len(midi_cmd) == length), \
            self.fail("Problem getting the good length from get_packets")

        #Verify content (base on timestamp control)
        #iterator modulo 10
        iterator = 3
        for i in range(len(midi_cmd)):
            midi_cmd_notes = midi_cmd[i].packet
            for j in range(len(midi_cmd_notes)):
                #increment iterator
                if not j%7 and i != 0:
                    iterator = (iterator+1)%10

                assert(midi_cmd_notes[j][1]== iterator + j%7), \
                    self.fail("Problem with midi cmd content")
