from rtpmidi.protocols.rtp.rtcp import RTCPProtocol
from rtpmidi.protocols.rtp.packets import RTCPCompound
from rtpmidi.protocols.rtp.packets import RTCPPacket

from twisted.trial import unittest
from time import time

class FakeRTP(object):
    def __init__(self):
        self.last_sent_time = 0
        self.ssrc = 0
        self.rtp_ts = 143
        self.total_packets = 100
        self.total_bytes = 800
        self.session_bw = 1024

class TestRTCPProtocol(unittest.TestCase):
    def setUp(self):
        rtp = FakeRTP()
        rtp.ssrc = 424242
        self.rtcp = RTCPProtocol(rtp, "localhost")

        #Some members to test
        new_member = self.rtcp.member.copy()
        new_member['cname'] = "joe@host1"
        new_member['user_name'] = "joe"
        new_member['tool'] = "sropulpof1"
        self.rtcp.members_table[424242] = new_member

        new_member_2 = self.rtcp.member.copy()
        new_member_2['cname'] = "jack@host1"
        new_member_2['user_name'] = "jack"
        new_member_2['tool'] = "sropulpof2"
        self.rtcp.members_table[434343] = new_member_2

    def tearDown(self):
        del self.rtcp

#Receiving function
    def test_receiveSR(self):
        pass

    def test_receiveSRRR(self):
        pass

    def test_receiveSDES(self):
        packet = self.rtcp.send_SDES()
        compound = RTCPCompound()
        compound.addPacket(packet)
        compound_enc = compound.encode()

        new_compound = RTCPCompound(compound_enc)
        #packet_type = packet.getPT()
        #cont = packet.getContents()
        #print cont
        #self.rtcp.receiveSDES(cont)


    def test_receiveBYE(self):
        #First test
        reason = "Normal quit"
        arg_list = ([self.rtcp.rtp.ssrc], reason)

        rtcp = RTCPPacket("BYE", ptcode=203, contents=arg_list)
        rtcp_pac = rtcp.encode()

        #Decoding as datagram received
        packets = RTCPCompound(rtcp_pac)
        packet_type = packets[0].getPT()
        cont = packets[0].getContents()
        ssrc = cont[0][0]
        reas_gave = cont[1]

        #Checking BYE format
        assert(packet_type == "BYE"), \
            self.fail("Wrong packet type encoded or decoded for BYE")
        assert(ssrc == self.rtcp.rtp.ssrc), \
            self.fail("Wrong SSRC encoded or decoded for BYE")
        assert(reas_gave == reason), \
            self.fail("Wrong reason encoded or decoded for BYE")


        #SEcond TEst
        arg_list = ([434343], reason)
        rtcp = RTCPPacket("BYE", ptcode=203, contents=arg_list)
        rtcp_pac = rtcp.encode()
        #Decoding as datagram received
        packets = RTCPCompound(rtcp_pac)
        packet_type = packets[0].getPT()
        cont = packets[0].getContents()
        self.rtcp.receiveBYE(cont)

        #Checking members table
        assert(len(self.rtcp.members_table)==1), \
            self.fail("Forget to delete member when receiving BYE packet from him!")
        for ssrc in self.rtcp.members_table:
            assert(ssrc==424242), \
                self.fail("Wrong member erase after receiving BYE packet")


#Sending function
    def test_send_SDES(self):

        res = self.rtcp.send_SDES()
        #print res

        #Testing res



#Check functions
    def test_check_ssrc_timeout_1(self):
        #Timing_out two members
        #Setting date
        self.rtcp.members_table[434343]['last_rtcp_received'] = time() - 16
        self.rtcp.members_table[424242]['last_rtcp_received'] = time() - 17
        self.rtcp.check_ssrc_timeout()

        #Testing res
        assert(len(self.rtcp.members_table)==0), \
            self.fail("Problem deleting members after SSRC timeout")

    def test_check_ssrc_timeout_1(self):
        #Timing_out one members
        #Setting date
        self.rtcp.members_table[434343]['last_rtcp_received'] = time() - 16
        self.rtcp.members_table[424242]['last_rtcp_received'] = time()
        self.rtcp.check_ssrc_timeout()

        #Testing res
        assert(len(self.rtcp.members_table)==1), \
            self.fail("Problem deleting members after SSRC timeout")

        for ssrc in self.rtcp.members_table:
            assert(ssrc==424242), \
                self.fail("Wrong member erase after SSRC timeout")

    def test_check_ssrc_1(self):
        #check_ssrc(ssrc, addr, ptype, cname)
        #Use cases:
        #First SSRC view
        #Confirm member

        #TODO see CNAME
        ssrc = 484848
        self.rtcp.check_ssrc(ssrc, ("192.168.0.1", 44001), "SR", "bonjour")

        assert(len(self.rtcp.members_table)==3), \
            self.fail("Problem adding a new member")
        if not ssrc in self.rtcp.members_table:
            self.fail("Problem adding a new member")

        assert(self.rtcp.members_table[ssrc]['addr']=="192.168.0.1"), \
            self.fail("Wrong address added for the new member")
        assert(self.rtcp.members_table[ssrc]['rtcp_port']==44001), \
            self.fail("Wrong RTCP port added for the new member")

        self.rtcp.check_ssrc(ssrc, ("192.168.0.1", 44000), "DATA", "bonjour")
        assert(self.rtcp.members_table[ssrc]['rtp_port']==44000), \
            self.fail("Wrong RTP port added for the confirm member")


    def test_check_ssrc_2(self):
        #Use cases:
        #collision with confirmed guest
        #loop
        ssrc = 484848
        self.rtcp.check_ssrc(ssrc, ("192.168.0.1", 44001), "SR", "bonjour")
        self.rtcp.check_ssrc(ssrc, ("192.168.0.1", 44000), "DATA", "bonjour")


        self.rtcp.check_ssrc(ssrc, ("192.168.0.2", 44000), "SDES", "coucou")
        #Test nb_collision var

        self.rtcp.check_ssrc(ssrc, ("192.168.0.2", 44000), "DATA", "coucou")
        #Test nb_loop var


    def test_check_ssrc_3(self):
        #Use cases:
        #conflicting addr
        #SSRC collision
        pass

    def test_we_sent_timeout(self):
        #We sent timeout is based on transmission interval value
        self.rtcp.compute_transmission_interval()

        #Not timing out
        self.rtcp.rtp.last_sent_time = time()
        self.rtcp.we_sent = True
        self.rtcp.we_sent_time_out()
        assert(self.rtcp.we_sent==True), self.fail("Wrong update of we_sent")


        #Timing out (== 2 * 2.5)
        self.rtcp.rtp.last_sent_time = time() - 6
        self.rtcp.we_sent = True

        self.rtcp.we_sent_time_out()

        assert(self.rtcp.we_sent==False), \
            self.fail("Wrong update of we_sent when timingout")


    def test_checksum(self):

        #Testing good checksum packet
        reason = "because"
        arg_list = ([self.rtcp.rtp.ssrc], reason)

        #Testing BYE PAcket
        packet_to_test = RTCPPacket("BYE", ptcode=203, contents=arg_list)
        bytes = packet_to_test.encode()
        res = self.rtcp.checksum(bytes)
        assert(res==1), self.fail("Wrong checksum for BYE packet")


        arg_list = (self.rtcp.rtp.ssrc, self.rtcp.rtp.rtp_ts, \
                self.rtcp.rtp.total_packets, \
                self.rtcp.rtp.total_bytes, self.rtcp.members_table)

        #Test SR packet
        packet_to_test = RTCPPacket("SR", ptcode=201, contents=arg_list)
        compound = RTCPCompound()
        compound.addPacket(packet_to_test)
        bytes = compound.encode()
        res = self.rtcp.checksum(bytes)
        assert(res==1), self.fail("Wrong checksum for SR packet")

        arg_list = (self.rtcp.rtp.ssrc, self.rtcp.members_table)

        #Test RR packet
        packet_to_test = RTCPPacket("RR", ptcode=200, contents=arg_list)
        compound = RTCPCompound()
        compound.addPacket(packet_to_test)
        bytes = compound.encode()
        res = self.rtcp.checksum(bytes)
        assert(res==1), self.fail("Wrong checksum for RR packet")
