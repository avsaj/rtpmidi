import sys
import time
from twisted.trial import unittest

from rtpmidi.protocols.rtp.packets import RTCPPacket
from rtpmidi.protocols.rtp.packets import RTCPCompound
from rtpmidi.protocols.rtp.packets import ext_32_out_of_64
from rtpmidi.protocols.rtp.packets import unformat_from_32
from rtpmidi.protocols.rtp.packets import RTPPacket

##################RTCP#####################
class TestRTCPPacket(unittest.TestCase):
    """Testing RTCPPacket class"""
    def setUp(self):
        self.member = {'user_name': "name", 'cname': "user@host", 'tool': "none",
                       'addr':0, 'rtp_port':0, 'rtcp_port':0,
                       'last_rtp_received':0, 'last_rtcp_received':0,
                       'total_received_bytes':0, 'total_received_packets':0,
                       'last_seq':0, 'lost':0, 'last_ts':0, 'last_time':0,
                       'jitter':0, 'lsr':0, 'dlsr': 0,
                       'rt_time':0}

    def tearDown(self):
        pass

    def test_ext_32_out_of_64(self):
        ref = 10
        res = ext_32_out_of_64(ref)
        ref = 10 << 16
        assert(res==ref), self.fail("Wrong encoding")


    def test_unformat_from_32(self):
        ref = 10
        res = ext_32_out_of_64(ref)
        res_2 = unformat_from_32(res)
        assert(res_2==ref), self.fail("Wrong encoding or decoding")

        ref = 10.245
        res = ext_32_out_of_64(ref)
        res_2 = unformat_from_32(res)
        assert(res_2==ref), self.fail("Wrong encoding or decoding")

    def test_encode_SR(self):
        """Testing encode functione for SR"""
        ttt = time.time()
        cont \
            = (ssrc, ntp, rtp_ts, total_packets, total_bytes, ssrc_1,
               frac_lost, lost, highest, jitter, lsr, dlsr) \
            = (424242, ttt, 143, 100, 800, 424243, 1, 1, 65535, 15,
               int(time.time()-10), 10)

        members = {}
        new_member = self.member.copy()
        new_member['last_ts'] = rtp_ts
        new_member['last_seq'] = highest
        new_member['jitter'] = jitter
        new_member['lost'] = lost
        members_table = {}
        members_table[ssrc] = new_member

        arg_list = (ssrc, rtp_ts,
                    total_packets,
                    total_bytes, members_table)



        rtcp = RTCPPacket("SR", ptcode=200, contents=arg_list)
        rtcp_pac = rtcp.encode()

        #Testing result
        assert(type(rtcp_pac)==str), self.fail("Wrong type returned for SR" \
                                                   + " RTCP packet")

        assert(len(rtcp_pac) == 28), self.fail("Wrong size returned for SR" \
                                                   + " RTCP packet")

    def test_decode_SR(self):
        """Decode SR packet with only one feed"""
        ttt = time.time()
        (ssrc, ntp, rtp_ts, total_packets, total_bytes, ssrc_1,
         frac_lost, lost, highest, jitter, lsr, dlsr) \
             = (424242, ttt, 143, 100, 800, 424243, 1, 1, 65535, 15,
                int(time.time()-10), 10)

        frac_lost = int(lost / float(total_packets + lost))

        members = {}
        new_member = self.member.copy()
        new_member['last_ts'] = rtp_ts
        new_member['last_seq'] = highest
        new_member['jitter'] = jitter
        new_member['lost'] = lost
        new_member['lsr'] = lsr
        new_member['dlsr'] = dlsr

        members_table = {}
        members_table[ssrc_1] = new_member

        arg_list = (ssrc, rtp_ts,
                    total_packets,
                    total_bytes, members_table)

        rtcp = RTCPPacket("SR", ptcode=200, contents=arg_list)
        rtcp_pac = rtcp.encode()

        #Unpacking
        #Decoding packet
        packet = RTCPCompound(rtcp_pac)

        #Getting content of the first block
        cont = packet._rtcp[0].getContents()

        lsr = ext_32_out_of_64(lsr)
        lsr = unformat_from_32(lsr)

        dlsr = ext_32_out_of_64(dlsr)
        dlsr = unformat_from_32(dlsr)

        #Testing content decode
        assert(cont[0]== ssrc), self.fail("SSRC is not correctly encode or " \
                                              + "decode")

        assert(int(cont[1]['ntpTS'])==int(ntp)), \
            self.fail("NTP Timestamp is not correctly encode or decode")
        assert(cont[1]['packets']==total_packets), \
            self.fail("Cumulative number of packets is not correctly encode or decode")
        assert(cont[1]['octets']==total_bytes), \
            self.fail("Cumulative octets sum is not correctly encode or decode")
        assert(cont[1]['rtpTS']==rtp_ts), \
            self.fail("RTP timestamp is not correctly encode or decode")

        assert(cont[2][0]['ssrc']==ssrc_1), \
            self.fail("SSRC_1 is not correctly encode or decode")
        assert(cont[2][0]['jitter']==jitter), \
            self.fail("Jitter is not correctly encode or decode")
        assert(cont[2][0]['fraclost']==frac_lost), \
            self.fail("Frac lost is not correctly encode or decode")

        assert(cont[2][0]['lsr']==lsr), \
            self.fail("Last received is not correctly encode or decode")
        assert(cont[2][0]['highest']==highest), \
            self.fail("Highest seq num is not correctly encode or decode")

    def test_encode_RR(self):
        ttt = time.time()
        (ssrc, ntp, rtp_ts, total_packets, total_bytes, ssrc_1, \
             frac_lost, lost, highest, jitter, lsr, dlsr) \
             = (424242, ttt, 143, 100, 800, 424243, 1, 1, 65535, 15, \
                    int(time.time()-10), 10)

        frac_lost = int(lost / float(total_packets + lost))

        members = {}
        new_member = self.member.copy()
        new_member['last_ts'] = rtp_ts
        new_member['last_seq'] = highest
        new_member['jitter'] = jitter
        new_member['lost'] = lost
        new_member['lsr'] = lsr
        new_member['dlsr'] = dlsr

        members_table = {}
        members_table[ssrc_1] = new_member

        arg_list = (ssrc, members_table)

        rtcp = RTCPPacket("RR", ptcode=201, contents=arg_list)
        rtcp_pac = rtcp.encode()

        #Testing result
        assert(type(rtcp_pac)==str), self.fail("Wrong type returned for RR" \
                                                   + " RTCP packet")
        assert(len(rtcp_pac) == 32), self.fail("Wrong size returned for RR" \
                                                   + " RTCP packet")

    def test_decode_RR(self):
        ttt = time.time()
        (ssrc, ntp, rtp_ts, total_packets, total_bytes, ssrc_1, \
             frac_lost, lost, highest, jitter, lsr, dlsr) \
             = (424242, ttt, 143, 100, 800, 424243, 1, 1, 65535, 15, \
                    int(time.time()-10), 10)

        frac_lost = int(lost / float(total_packets + lost))

        members = {}
        new_member = self.member.copy()
        new_member['last_ts'] = rtp_ts
        new_member['last_seq'] = highest
        new_member['jitter'] = jitter
        new_member['lost'] = lost
        new_member['lsr'] = lsr
        new_member['dlsr'] = dlsr

        members_table = {}
        members_table[ssrc_1] = new_member

        arg_list = (ssrc, members_table)

        rtcp = RTCPPacket("RR", ptcode=201, contents=arg_list)
        rtcp_pac = rtcp.encode()

        #Unpacking
        #Decoding packet
        packet = RTCPCompound(rtcp_pac)

        #Getting content of the first block
        cont = packet._rtcp[0].getContents()

        lsr = ext_32_out_of_64(lsr)
        lsr = unformat_from_32(lsr)

        dlsr = ext_32_out_of_64(dlsr)
        dlsr = unformat_from_32(dlsr)

        #Testing content decode
        assert(cont[0]== ssrc), self.fail("SSRC is not correctly encode or " \
                                              + "decode")
        assert(cont[1][0]['ssrc']==ssrc_1), \
            self.fail("SSRC_1 is not correctly encode or decode")
        assert(cont[1][0]['jitter']==jitter), \
            self.fail("Jitter is not correctly encode or decode")
        assert(cont[1][0]['fraclost']==frac_lost), \
            self.fail("Frac lost is not correctly encode or decode")

        assert(cont[1][0]['lsr']==lsr), \
            self.fail("Last received is not correctly encode or decode")
        assert(cont[1][0]['highest']==highest), \
            self.fail("Highest seq num is not correctly encode or decode")

    def test_encode_BYE(self):
        """Test encode BYE packet with a single SSRC"""
        cont = (ssrc, reason) = ([4242], "because")
        rtcp = RTCPPacket("BYE", ptcode=203, contents=cont)
        rtcp_pac = rtcp.encode()

        assert(type(rtcp_pac)==str), \
            self.fail("Wrong type returned by encode RTCP BYE packet")
        #MUST be padd ??
        assert(len(rtcp_pac) == 16), \
            self.fail("Wrong size returned by encode RTCP BYE packet")

    def test_decode_BYE(self):
        """Test decode BYE packet with a single SSRC"""
        cont = (ssrc, reason) = ([4242], "because")
        rtcp = RTCPPacket("BYE", ptcode=203, contents=cont)
        rtcp_pac = rtcp.encode()

        #Unpacking
        #Decoding packet
        packet = RTCPCompound(rtcp_pac)

        #Getting content of the first block
        cont = packet._rtcp[0].getContents()

        assert(cont[0][0]==ssrc[0]), \
            self.fail("SSRC is not correctly encode or decode")
        assert(cont[1]==reason), \
            self.fail("Reason is not correctly encode or decode")


    def test_encode_SDES(self):

        item = []
        cont = []
        item.append(("CNAME", "me@myself.mine"))
        item.append(("NAME", "memyselfandi"))
        item.append(("TOOL", "sropulpof_test"))
        cont.append((424242, item))

        rtcp = RTCPPacket("SDES", ptcode=202, contents=cont)
        rtcp_pac = rtcp.encode()

        assert(type(rtcp_pac)==str), \
            self.fail("Wrong type returned by encode RTCP SDES packet")

        #MUST be padd
        length_wait = 8 + 2 + len("me@myself.mine") + 2 + len("memyselfandi") + 2 + len("sropulpof_test")
        pad = 4 - (length_wait%4)
        length_wait += pad

        assert(len(rtcp_pac) == length_wait), \
            self.fail("Wrong size returned by encode RTCP SDES packet")


    def test_decode_SDES(self):
        item = []
        cont = []
        item.append(("CNAME", "me@myself.mine"))
        item.append(("NAME", "memyselfandi"))
        item.append(("TOOL", "sropulpof_test"))
        cont.append((424242, item))

        rtcp = RTCPPacket("SDES", ptcode=202, contents=cont)
        rtcp_pac = rtcp.encode()

        packets = RTCPCompound(rtcp_pac)

        for packet in packets:
            packet_type = packet.getPT()
            cont = packet.getContents()

            assert(packet_type=="SDES"), self.fail("Wrong type select by RTCPCompound")
            assert(cont[0][0]==424242), self.fail("Wrong ssrc")
            for elt in cont[0][1]:
                if elt[0] == "CNAME":
                    assert(elt[1]=="me@myself.mine"), self.fail("wrong encoded for Cname")

                elif elt[0] == "NAME":
                    assert(elt[1]=="memyselfandi"), self.fail("wrong encoded for Name")

                elif elt[0] == "TOOL":
                    assert(elt[1]=="sropulpof_test"), self.fail("wrong encoded for Tool")


class TestRTCPCompound(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


    def test_encode(self):
        pass

    def test_decode(self):
        pass


##################RTP#####################
class TestRTPPacket(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    class TestHeader(unittest.TestCase):
        def setUp(self):
            pass

        def tearDown(self):
            pass

        def test_init(self):
            #params: ssrc, pt, ct, seq, ts, marker=0, xhdrtype=None, xhdrdata=''
            pass

        def test_netbytes(self):
            pass


    def test_init(self):
        #params: ssrc, seq, ts, data, pt=None, ct=None, marker=0,
        #         authtag='', xhdrtype=None, xhdrdata=''
        #
        test = "some data"
        ssrc, seq, ts, data, marker  = (424242, 1, 143, test, 1)
        packet = RTPPacket(ssrc, seq, ts, data, marker=marker)
        #assert(len(packet)==

    def test_netbytes(self):
        pass

    def test_parse_rtppacket(self):
        pass



class TestNTE(unittest.TestCase):
    def test_init(self):
        pass

    def test_getKey(self):
        pass

    def test_getPayload(self):
        pass

    def test_isDone(self):
        pass

