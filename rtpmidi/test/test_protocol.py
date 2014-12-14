from twisted.trial import unittest
from rtpmidi.protocols.rtp.protocol import RTPProtocol
from rtpmidi.protocols.rtp.packets import RTPPacket

class TestRTPProtocol(unittest.TestCase):
    def setUp(self):
        self.rtp = RTPProtocol(self, "ahahahahaha", 96)

    def tearDown(self):
        pass

    def test_checksum(self):
        #Test a good packet
        packet = RTPPacket(424242, 2, 10, "", pt=96)
        bytes = packet.netbytes()
        res = self.rtp.checksum(bytes)
        assert(res==1), self.fail("Wrong checksum for RTP packet")




