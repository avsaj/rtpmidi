# Copyright (C) 2004 Anthony Baxter

"""
RTCP packet encoding and decoding code. RTCP is a bit of a bitch - there's
so many things you can stuff in a packet.

Note that this code merely encodes and decodes the various formats - it does
not attempt to do anything useful with the data. Nor is there code here (yet)
to generate RR or SR packets from the RTP stack. Soon.
"""

#utils
from time import time
import struct

#twisted imports
from twisted.internet.protocol import DatagramProtocol
from twisted.internet.task import LoopingCall

#data import
from rtpmidi.protocols.rtp.packets import RTCPPacket
from rtpmidi.protocols.rtp.packets import rtcpPTdict
from rtpmidi.protocols.rtp.packets import RTCPCompound
from rtpmidi.protocols.rtp.packets import ext_32_out_of_64
from rtpmidi.protocols.rtp.packets import unformat_from_32

from rtpmidi.protocols.rtp.list_circ import DelayCirc

DEBUG = 0
VERBOSE = 0

class RTCPProtocol(DatagramProtocol):
    """Control RTCP in and out for the application
    """

    def __init__(self, rtp, peer_address, verbose=0):
        if verbose:
            global VERBOSE
            VERBOSE = 1

        self.rtp = rtp
        self.peer_address = peer_address
        self.peer_port = 0
        self.lastreceivetime = None

        #RTCP var
        self.initial = True
        self.we_sent = False
        self.last_sent_time = 0 #(tp)
        self.next_scheduled_time = 0 #(tn)
        self.senders = 0
        self.pmembers = 1
        self.members = 1
        self.avg_rtcp_size = 52 #32 if RR is the first packet
        self.transmission_interval = 0 #(T)


        #Total bandwidth that will be used for
        #RTCP packets by all members of this sessions
        #Value of this var is a fractionnal part of the total session bw
        #5% is RECOMMANDED to start
        self.init_time = time()
        self.rtcp_bw = 5
        self.tmin = 2.5
        self.timeout = 30
        self.m_timeout = 5
        self.transmission_interval_ref = self.tmin

        #Members of the session and senders
        jitter_values = DelayCirc(50)
        self.member = {'user_name': "name", 'cname': "user@host",
                       'tool': "none", 'addr':0, 'rtp_port':0, 'rtcp_port':0,
                       'last_rtp_received':0, 'last_rtcp_received':0,
                       'total_received_bytes':0, 'total_received_packets':0,
                       'last_seq':0, 'lost':0, 'last_ts':0, 'last_time':0,
                       'jitter_values':jitter_values, 'jitter':0, 'lsr':0,
                       'dlsr': 0, 'rt_time':0, 'checkpoint': 0}

        #Tables share with RTP
        self.members_table = {}
        self.senders_table = {}

        #Timing out a conflict (10 * transmission interval)
        self.conflict = {'time': 0}
        self.conflicting_add = {}

        #stats
        self.nb_packets_sent = 0

        #LoopingCall
        self.send_sr_lc = LoopingCall(self.send_report)

        #Var for instant stats
        self.last_ntp = 0
        self.last_lost = 0
        self.last_jitter = 0

        #Error count
        self.collision_nb = 0
        self.loop_nb = 0


    def start(self):
        """starting RTCP protocol"""

        #Adding itself to member table
        new_member =self.member.copy()
        rtp, session = self.rtp.app.currentRecordings[self.rtp.cookie]
        new_member['cname'] = session.fqdn
        new_member['user_name'] = session.user_name
        new_member['tool'] = session.tool_name

        self.members_table[self.rtp.ssrc] = new_member

        self.send_sr_lc.start(self.tmin)

    def stop(self):
        """stoping RTCP protocol"""
        if self.send_sr_lc.running:
            self.send_sr_lc.stop()


    def send_report(self):
        """Send report, choosing report type with we_sent var"""
        if DEBUG:
            print "sending rtcp report"

        #Checking timeouts
        self.check_ssrc_timeout()
        self.we_sent_time_out()

        #Building report
        compound = RTCPCompound()

        #Selecting type of sending
        if self.we_sent:
            sr_pac = self.send_SR()
            compound.addPacket(sr_pac)

        else:
            rr_pac = self.send_RR()
            compound.addPacket(rr_pac)

        if len(self.members_table) > 1:
            sdes_pac = self.send_SDES()
            compound.addPacket(sdes_pac)

        #Encoding report
        compound_enc = compound.encode()

        #Sending reports
        if self.initial:
            if DEBUG:
                print "(initial) to " + str((self.rtp.dest[0],
                                             self.rtp.dest[1]+1))

            self.transport.write(compound_enc,(self.rtp.dest[0],
                                               self.rtp.dest[1]+1))
            self.tmin = 5

        else:
            self.sendDatagram(compound_enc)

        #scheduled_sending
        new_inter = self.compute_transmission_interval()
        if self.transmission_interval_ref != new_inter:
            self.transmission_interval_ref = new_inter
            self.send_sr_lc.stop()
            self.send_sr_lc.start(self.transmission_interval, now=False)

        if DEBUG:
            print " RTCP TI " + str(self.transmission_interval)

    def datagramReceived(self, datagram, addr):
        if DEBUG:
            print "received RTCP packet from " + str(addr)

        if self.initial:
            self.initial = False
            if DEBUG:
                print "Members=>"
                print self.members_table
                print

        if not self.checksum(datagram):
            if DEBUG:
                print "Wrong rtcp checksum"
            return

        if DEBUG:
            print "good rtcp checksum"

        #Decoding packet(s)
        packets = RTCPCompound(datagram)

        #First must be a SR or RR
        packet_type = packets[0].getPT()
        cont = packets[0].getContents()

        if packet_type == "SR" or packet_type == "RR":
            ssrc = cont[0]

        elif packet_type == "BYE":
            ssrc = cont[0][0]

        else:
            return

        #Check SSRC
        if ssrc in self.members_table:
            cname = self.members_table[ssrc]['cname']
        else:
            cname = ""

        if not self.check_ssrc(ssrc, addr, packet_type, cname):
            return

        self.members_table[ssrc]['last_rtcp_received'] = time()

        for packet in packets:
            #var
            packet_type = packet.getPT()
            cont = packet.getContents()

            #Dispatching thanks to packet type
            if packet_type == "SR":
                self.members_table[ssrc]['lsr'] = time()
                self.receiveSR(cont)

            elif packet_type == "RR":
                self.receiveSRRR(cont[1])

            elif packet_type == "SDES":
                self.receiveSDES(cont)

            elif packet_type == "BYE":
                self.receiveBYE(cont)

                #usurps the normal role of the members variable
                #to count BYE packets instead
                if len(self.members_table) >= 50:
                    self.members += 1

            else:
                if VERBOSE:
                    line = "RTCP packet with unknown type received " \
                        + str(packet_type)
                    print line

        #avg size
        self.avg_rtcp_size \
            = (1/float(16)) * len(datagram) + (15/float(16)) \
            * self.avg_rtcp_size

        if DEBUG:
            print "avg rtcp size " + str(self.avg_rtcp_size)


    def checksum(self, bytes):
       version = ord(bytes[0])>>6
       if version != 2:
            return 0

       pt = ord(bytes[1])
       PT = rtcpPTdict.get(pt, "UNKNOWN")

       #Is it really right ?
       if PT == "BYE":
           return 1

       #SR or RR must be first of compound
       if PT != "SR" and PT != "RR":
           return 0

       #no padding on first of compound
       padding = (ord(bytes[0])&32) and 1 or 0
       if padding :
           return 0

       #Checking len on all packets of compound
       count = ord(bytes[0])&31
       try:
           length, = struct.unpack('!H', bytes[2:4])
       except struct.error:
           print "RTCP: struct.unpack got bad number of bytes"
           print "RTCP: incorrect checksum!!"
           return


       #Others test ??
       return 1

##
#Sending functions
##
    def send_RR(self):
        """Send Receiver report"""
        arg_list = (self.rtp.ssrc, self.members_table)
        rtcp = RTCPPacket("RR", ptcode=201, contents=arg_list)
        return rtcp
        #Saving last checkpoint saved (needed by recovery journal)
        #self.rtp.app.last_checkpoint = highest


    def send_SR(self):
        """Sending Sender report"""
        arg_list = (self.rtp.ssrc, self.rtp.ts, \
                        self.rtp.currentSentPacketsTotal, \
                        self.rtp.currentSentBytesTotal, self.members_table)

        rtcp = RTCPPacket("SR", ptcode=200, contents=arg_list)


        return rtcp


    def send_SDES(self):
        arg_list = []
        for member in self.members_table:
            item = []
            cname = self.members_table[member]['cname']
            #CNAME is mandatory !
            if cname != "user@host":
                item.append(("CNAME", cname))

                name = self.members_table[member]['user_name']
                item.append(("NAME", name))

                tool = self.members_table[member]['tool']
                item.append(("TOOL", tool))
                arg_list.append((member, item))

        rtcp = RTCPPacket("SDES", ptcode=202, contents=arg_list)
        return rtcp

    def send_BYE(self, reason):
        """Sending a BYE packet to inform others participant that we are
        leaving the session
        """
        ssrcs = self.members_table.keys()
        arg_list = ([self.rtp.ssrc], reason)

        rtcp = RTCPPacket("BYE", ptcode=203, contents=arg_list)

        #ssrcs, reason
        if len(self.members_table) >= 50:
            self.last_sent_time = time()
            self.pmembers = 1
            self.members = 1
            self.initial = True
            self.we_sent = False
            self.avg_rtcp_size = 0 #BYE packet size ??

            self.compute_transmission_interval()
            self.next_scheduled_time = time() + self.transmission_interval
            self.rescheduled_sending()

        rtcp_pac = rtcp.encode()
        self.sendDatagram(rtcp_pac)

    def sendDatagram(self, packet):
        """Send the packet to every member of the session"""
        for ssrc in list(self.members_table.keys()):
            if ((ssrc != self.rtp.ssrc)
                and (self.members_table[ssrc]['rtcp_port'] != 0)):
                if DEBUG:
                    print "sending RTCP to ", \
                        str(self.members_table[ssrc]['addr'])

                self.transport.write(packet,
                                     (self.members_table[ssrc]['addr'],
                                      self.members_table[ssrc]['rtcp_port']))

#Receiving functions
    def receiveSR(self, cont):
        """Parsing SR information in order to launch action link to SR stats"""
        #Stats specific to SR
        #Compare stats received with stats of the member
        remote_ssrc = cont[0]
        member = self.members_table[remote_ssrc]


        #cont[1]['ntpTS']

        #Comparing octets count and packet count from the sender with
        #stats on him
        diff_o = cont[1]['octets'] - member['total_received_bytes']
        diff_p = cont[1]['packets'] - member['total_received_packets']

        #cont[1]['rtp_ts']

        if len(cont[2]) > 0:
            self.receiveSRRR(cont[2])


    def receiveSRRR(self, cont):
        """Parsing RR information in order to launch action link to SR stats"""
        #ssrc, highest, jitter, lsr, dlsr, frac_lost, pack_lost
        for item in cont:
            ssrc = item['ssrc']

            #Stats about me
            if ssrc == self.rtp.ssrc:

                #Updating check point
                if item['highest'] != 0:
                    rtp, session = self.rtp.app.currentRecordings[self.rtp.cookie]
                    if session.checkpoint != item['highest']:
                        session.update_checkpoint(item['highest'])
                        self.members_table[ssrc]['checkpoint'] = item['highest']

                #Some calculations
                #print "jitter and packlost things : jitter ",
                instant_jitter = item['jitter'] - self.members_table[ssrc]['jitter']
                instant_p_lost = item['packlost'] - self.members_table[ssrc]['lost']
                #self.members_table[ssrc]['frac_lost']
                #print instant_jitter, "// lost ", instant_p_lost


                if item['lsr'] != 0 and item['dlsr'] != 0:
                    rt_time = self.round_trip_time(item['lsr'], \
                                                       item['dlsr'])
                    self.members_table[ssrc]['rt_time'] = rt_time

                    if DEBUG:
                        print "RT time calc ", rt_time


    def receiveSDES(self, cont):
        """Learning CNAME, Name, and Tool from remote peer """
        for ssrc,items in cont:
            for sdes, value in items:
                if ssrc in self.members_table:
                    #Updating values of members table
                    if sdes == "CNAME":
                        self.members_table[ssrc]['cname'] = value

                    elif sdes == "NAME":
                        self.members_table[ssrc]['user_name'] = value

                    elif sdes == "TOOL":
                        self.members_table[ssrc]['tool'] = value


    def receiveBYE(self, cont):
        """Process operations for member leaving the session properly
        """
        ssrc = cont[0][0]
        #Remove SSRC from members table
        if ssrc in self.members_table:
            self.members -= 1

            if VERBOSE:
                line = "A member (" + str(self.members_table[ssrc]['addr'])
                line +=  ") is going away from the session ,\n  "
                line += "reason : " + str(cont[1])
                print line

            del self.members_table[ssrc]


            #Remove SSRC from senders table
            if ssrc in self.senders_table:
                self.senders -= 1
                del self.senders_table[ssrc]

            if DEBUG:
                print "members table " + str(self.members_table)

        #Reverse consideration
        if self.members <= self.pmembers:
            tc = (time() - self.init_time)
            #This should be soon now!
            self.next_scheduled_time \
                = tc + ( self.members / self.pmembers ) \
                * ( self.next_scheduled_time - tc )

            self.last_sent_time = \
                tc - ( self.members / self.pmembers ) \
                * ( tc - self.last_sent_time )

        #Updating estimate number of sessions
        self.pmembers = self.members


#Commons functions
    #Section 8.2 RFC 3550
    def check_ssrc(self, ssrc, addr, ptype, cname):
        """Check ssrc and manage it with RTP"""
        if ssrc == 0:
            #Problem can't send without SSRC
            return 0

        ip_addr = addr[0]
        port = addr[1]

        if not ssrc in self.members_table:
            #build member
            new_member = self.member.copy()

            if ptype == "DATA":
                new_member['last_rtp_receive'] = time()

                #Storing transport address
                new_member['addr'] = ip_addr
                new_member['rtp_port'] = port

            elif ptype == "SR" or ptype == "RR" or ptype == "SDES":
                new_member['last_rtcp_receive'] = time()

                #Storing transport address
                new_member['addr'] = ip_addr
                new_member['rtcp_port'] = port

            #Adding the member
            self.members_table[ssrc] = new_member
            self.members += 1
            if DEBUG:
                print "new number of member " , len(self.members_table)
                print "add memebr. res member table : ", \
                    ssrc, " (ip:", ip_addr, ")"


            #log it
            if VERBOSE:
                line = "New member for the session : " + str(ip_addr)
                print line

            if ptype == "SR":
                if not ssrc in self.senders_table:
                #adding the member to sender
                    self.senders_table[ssrc] = new_member
                    self.senders += 1

                    #log it
                    if VERBOSE:
                        line = "New sender for the session : " + str(ip_addr)
                        print line

            return 1

        elif (ssrc in self.members_table
              and ((self.members_table[ssrc]['rtp_port'] == 0
                    and ptype == "DATA")
                   or (self.members_table[ssrc]['rtcp_port'] == 0
                       and (ptype == "RR" or ptype == "SR")))):

            #Assuming that this is the same ip address
            if self.members_table[ssrc]['rtp_port'] == 0:
            #Storing IP address and link it to ssrc
                self.members_table[ssrc]['rtp_port'] = port

            else:
                self.members_table[ssrc]['rtcp_port'] = port


            #log it
            if VERBOSE:
                line = "Confirm member for the session : " + str(ip_addr)
                print line

            return 1

        elif ( ssrc in self.members_table
               and ip_addr != self.members_table[ssrc]['addr']):
            #Loop or collision detected
            if ssrc != self.rtp.ssrc:
                #ssrc is not mine

                if (ptype == "SDES"
                    and self.members_table[ssrc]['cname'] != cname):
                    #source identifier is from an RTCP SDES chunk
                    #containing a CNAME item that differs from the CNAME
                    #in the table entry
                    self.collision_nb += 1

                else:
                   self.loop_nb += 1

                #abort processing
                return 0

            elif ip_addr in self.conflicting_add:
                #Address in conflicting address
                rtp, session = self.rtp.app.currentRecordings[self.rtp.cookie]
                if ptype != "SDES" or cname == session.fqdn:
                    #source identifier is not from an RTCP SDES chunk
                    #containing a CNAME item or CNAME is the
                    #participant's own
                    if VERBOSE:
                        print "Own loop traffic detected"

                #mark current time
                self.conflicting_add[ip_addr]['time'] = time()

                #abort processing
                return 0

            else:
                #SSRC collision detected
                #log it
                if VERBOSE:
                    print "SSRC collision detected"

                #Adding to conflict table and mark time
                conflict = self.conflict.copy()
                conflict['time'] = time()
                self.conflicting_add[ip_addr] = conflict

                #send RTCP BYE with old ssrc
                bye_cont = self.send_BYE("SSRC collision detected")

                #Renew SSRC
                new_ssrc = self.rtp.genSSRC()
                #Check that the new SSRC is not in use yet
                while new_ssrc in self.members_table:
                    new_ssrc = self.rtp.genSSRC()

                self.rtp.ssrc = new_ssrc

                #Create entry for old ssrc and ip source
                new_member = self.member.copy()
                new_member['last_receive'] = time()
                new_member['addr'] = ip_addr
                new_member['port'] = port

                self.members_table[ssrc] = new_member

                #Process packet
                return 1

        else:
            #Process packet
            return 1


    def check_ssrc_timeout(self):
        #interval (T)
        for member in list(self.members_table.keys()):
            if member != self.rtp.ssrc:
            #If we doesn't have received a packet for a while
            #remove participant ssrc from members table
                if ((self.members_table[member]['last_rtcp_received']
                     + self.m_timeout * 3) < time()):

                    if VERBOSE:
                        line = "Timing out ssrc for member "
                        line += str(self.members_table[member]['addr'])
                        print line

                    del self.members_table[member]
                    self.members -= 1

            #if member was a sender remove its ssrc from senders table
            if member in self.senders_table:
                del self.senders_table[member]
                self.senders -= 1

    def we_sent_time_out(self):
        """timing out we_sent flag"""
        if self.we_sent:
            #timeout is time() - 2 T
            if ((self.rtp.last_sent_time + 2 * self.transmission_interval)
                < time()):
                #timing out
                self.we_sent = False

                if DEBUG:
                    print "timing out we_sent"

                #Updating senders table
                #del self.senders_table[self.rtp.ssrc]


    def round_trip_time(self, lsr, dlsr):
        """Calcule round trip time
        Caution: TO make this work all the users must use NTP to syncronize
        their wallclock"""
        #Calculate round trip time
        if lsr != 0 and dlsr != 0:
            marker_a = time()
            marker_a = ext_32_out_of_64(marker_a)
            marker_a = unformat_from_32(marker_a)
            round_trip = marker_a - dlsr - lsr
            round_trip = "%.3f" % round_trip
            round_trip_time = float(round_trip)
            #print "Round trip time " + str(round_trip_time)

            #Perform test in case ntp is not syncronize
            #if
            return round_trip_time
        else:
            return None


    def compute_transmission_interval(self):
        """Dynamicaly calculate RTCP transmission interval
        based on the rtcp_bw and sender / receivers repartition
        """
        #Bandwith calculation based on RTCP BW part (in octets / seconds)
        band_width = self.rtcp_bw * self.rtp.session_bw / float(100)

        if self.senders <= ( self.members / float(4) ):
            if self.we_sent:
                c = self.avg_rtcp_size / float( band_width / float(4))
                n = self.senders

            else:
                c = self.avg_rtcp_size / float(( 3 * band_width ) / float(4))
                n = self.members - self.senders

        else:
            #Members are treated in the same way
            c = self.avg_rtcp_size / float(band_width)
            n = self.members


        #Transmission interval = max (tmin, n*c)
        if self.tmin < (n * c):
            self.transmission_interval = n * c
        else:
            self.transmission_interval = self.tmin


        #Calculate transmission intervall
        if DEBUG:
            print "Transmission intervall calculated => " \
                + str(self.transmission_interval) + " second(s)"



#Estimate bw
def estimate_bandwidth(device="eth0"):
    #Envoie de donner(1 fichier de 30Mo)
    #lorsque l'envoie est fini on fait une moyenne des
    # stats
    #find a way to list devices???

    #Recup des stats
    #reading infos
    f = open("/proc/net/dev")
    dev_lines = f.read()
    f.close()

    import re
    r = re.compile( r"^\s*" + re.escape(device) + r":(.*)$", re.MULTILINE )
    match = r.search(dev_lines)

    parts = match.group(1).split()

    #en octets
    return int(parts[0])


