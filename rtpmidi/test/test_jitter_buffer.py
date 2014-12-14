from twisted.trial import unittest
from rtpmidi.protocols.rtp.jitter_buffer import JitterBuffer
from rtpmidi.protocols.rtp.packets import RTPPacket


class TestJitterBuffer(unittest.TestCase):
    """Testing function from JitterBuffer"""

    def setUp(self):
        self.jitter_buffer = JitterBuffer()

    def tearDown(self):
        pass

    def test_init(self):
        jitter_buffer = JitterBuffer()
        assert(len(jitter_buffer.buffer) == 0), self.fail("Wrong size at initialization")

    def test_add(self):
        """Test Adding a packet to jitter buffer"""
        packet = RTPPacket(0, 42, 0, "", 0, \
                               marker=0, \
                               xhdrtype=None, xhdrdata='')
        time = 0

        self.jitter_buffer.add([packet, time])
        assert(len(self.jitter_buffer.buffer) == 1), \
            self.fail("Wrong size afther adding an element")
        assert(self.jitter_buffer.buffer[0][1] == 0), self.fail("Wrong value in the buffer for time")
        assert(self.jitter_buffer.buffer[0][0].header.seq == 42), self.fail("Wrong value in the buffer for seq num")

        packet = RTPPacket(0, 41, 0, "", 0, \
                               marker=0, \
                               xhdrtype=None, xhdrdata='')
        time = 2

        self.jitter_buffer.add([packet, time])

    def test_has_seq(self):
        """Testing seq num existenze in the buffer"""
        #Adding packets
        packet = RTPPacket(0, 42, 0, "", 0, \
                               marker=0, \
                               xhdrtype=None, xhdrdata='')
        time = 0
        self.jitter_buffer.add([packet, time])


        packet = RTPPacket(0, 43, 0, "", 0, \
                               marker=0, \
                               xhdrtype=None, xhdrdata='')
        time = 5
        self.jitter_buffer.add([packet, time])

        #TEsting values
        res = self.jitter_buffer.has_seq(42)
        assert(res==True), \
            self.fail("Wrong answer from has_seq, can't find an int that is in the buffer")

        res = self.jitter_buffer.has_seq(54)
        assert(res==False), \
            self.fail("Wrong answer from has_seq, can find an int that isn't in the buffer")

    def test_get_packets(self):
        """Testing Get Packets from jitter buffer"""
        #Adding packets
        packet = RTPPacket(0, 42, 0, "", 0, \
                               marker=0, \
                               xhdrtype=None, xhdrdata='')
        time = 0
        self.jitter_buffer.add([packet, time])


        packet = RTPPacket(0, 43, 0, "", 0, \
                               marker=0, \
                               xhdrtype=None, xhdrdata='')
        time = 5
        self.jitter_buffer.add([packet, time])

        packet = RTPPacket(0, 45, 0, "", 0, \
                               marker=0, \
                               xhdrtype=None, xhdrdata='')
        time = 8
        self.jitter_buffer.add([packet, time])

        packet = RTPPacket(0, 44, 0, "", 0, \
                               marker=0, \
                               xhdrtype=None, xhdrdata='')
        time = 9
        self.jitter_buffer.add([packet, time])

        res = self.jitter_buffer.get_packets(9)

        assert(len(res)==4), self.fail("Wrong size returned")
        for i in range(len(res)):
            assert(res[i].header.seq==42+i), self.fail("Wrong seq num returned")


        assert(len(self.jitter_buffer.buffer)==0), self.fail("Packets have not been erase from jitter buffer")
