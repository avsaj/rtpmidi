# Copyright (C) 2004-2005 Anthony Baxter
# $Id: rtp.py,v 1.40 2004/03/07 14:41:39 anthony Exp $
# Completed by Antoine Collet

#utils
import random
import os
import hashlib
import socket
from time import sleep
from time import time
import struct

#twisted
from twisted.internet import reactor
from twisted.internet import defer
from twisted.python import log
from twisted.internet.protocol import DatagramProtocol
from twisted.internet.error import MessageLengthError
from twisted.internet.error import CannotListenError

#rtp
from rtpmidi.protocols.rtp.packets import RTPPacket, parse_rtppacket
from rtpmidi.protocols.rtp import rtcp

#data
from rtpmidi.protocols.rtp.jitter_buffer import JitterBuffer
from struct import unpack

#Constants
TWO_TO_THE_16TH = 2L<<16
TWO_TO_THE_32ND = 2L<<32
TWO_TO_THE_48TH = 2L<<48
CHECK_FREQ = 50
MAX_LOST_RATE = 30
MIN_JITTER_BUFFER_TIME = 10
JITTER_CALC_TIME_OUT = 500
MIN_LATENCY = 20

DEBUG = 0
VERBOSE = 0

class RTPProtocol(DatagramProtocol):
    """Implementation of the RTP protocol.
    Also manages a RTCP instance.
    """
    _stunAttempts = 0
    _cbDone = None
    dest = None
    Done = False

    def __init__(self, app, cookie, payload, jitter_buffer_time=10, session_bw=524288, verbose=0):
        #Verbose mode
        if verbose:
            global VERBOSE
            VERBOSE = 1
        #Init settings
        self.app = app
        self.cookie = cookie
        self.payload = payload
        #Reserved bandwidth
        self.session_bw = session_bw
        self._pendingDTMF = []
        self.ptdict = {}
        #seq num send
        self.seq = self.genRandom(bits=16)
        #seq num receiv
        self.jitter_buffer = JitterBuffer()
        #Init Random Timestamp and SSRC (<- use to send data)
        self.ts = self.genInitTS()
        self.ssrc = self.genSSRC()
        if VERBOSE:
            print "  SSRC: " + str(self.ssrc)
        #To check Silent
        self._silent = True
        # only for debugging -- the way to prevent the sending of RTP packets
        # onto the Net is to reopen the audio device with a None (default)
        # media sample handler instead of this RTP object as the media sample
        #handler.
        self.sending = False
        #SR infos
        self.currentSentBytesTotal = 0
        self.currentSentPacketsTotal = 0
        #Jitter vars
        self.jitter_buffer_flag = True
        self.last_sent_time = 0
        #Estimation of round trip time
        self.rt_time = None
        self.rt_time_ref = None
        #jitter buffer time in ms (default 10)
        self.jitter_buffer_time = jitter_buffer_time

    def createRTPSocket(self, locIP, rport=0, sport=0, needSTUN=False):
        """ Start listening on UDP ports for RTP and RTCP.
            Returns a Deferred, which is triggered when the sockets are
            connected, and any STUN has been completed. The deferred
            callback will be passed (extIP, extPort). (The port is the RTP
            port.) We don't guarantee a working RTCP port, just RTP.
        """
        self.needSTUN = needSTUN
        self.rport = rport
        self.sport = sport
        d = defer.Deferred()
        self._socketCompleteDef = d
        if rport != 0:
            port = rport
        else:
            port = sport
        rtp_port, rtcp_port = self._socketCreationAttempt(locIP, port)
        if sport != 0:
            if VERBOSE:
                if sport != rtp_port :
                    print "Warning: Selected sending port could not be used, another one has been selected"
                print "  Sending port:", rtp_port
        if rport != 0:
            if VERBOSE:
                if rport != rtp_port :
                    print "Warning: Selected receiving port could not be used, another one has been selected"
                print "  Receiving port:", rtp_port
        self.lastreceivetime = time()
        self.init_time = time()*1000
        return d

    def _socketCreationAttempt(self, locIP, locPort):
        """Creating socket and determining port to be used in the session"""
        self.RTCP = rtcp.RTCPProtocol(self, locIP, VERBOSE)
        # RTP port must be even, RTCP must be odd
        # We select a RTP port at random, and try to get a pair of ports
        # next to each other. What fun!
        # Note that it's kinda pointless when we're behind a NAT that
        # rewrites ports. We can at least send RTCP out in that case,
        # but there's no way we'll get any back.
        #rtpPort = self.app.getPref('force_rtp_port')
        rtpPort = locPort
        if not rtpPort:
            rtpPort = 11000 + random.randint(0, 9000)
        if (rtpPort % 2) == 1:
            rtpPort += 1
        while True:
            try:
                self.rtpListener = reactor.listenUDP(rtpPort, self)
            except CannotListenError:
                rtpPort += 2
                continue
            else:
                break
        rtcpPort = rtpPort + 1
        #else:
        #    rtcpPort = self.sport + 1
        while True:
            try:
                self.rtcpListener = reactor.listenUDP(rtcpPort, self.RTCP)
            except CannotListenError:
                # Not quite right - if it fails, re-do the RTP listen
                if self.rport > 0:
                    self.rtpListener.stopListening()
                rtpPort = rtpPort + 2
                rtcpPort = rtpPort + 1
                continue
            else:
                break
        #self.rtpListener.stopReading()
        if self.needSTUN is False:
            # The pain can stop right here
            self._extRTPPort = rtpPort
            self._extIP = locIP
            #Passing port to rtcp session ( is it in right place ??)
            self.RTCP.peer_port = rtcpPort
            d = self._socketCompleteDef
            del self._socketCompleteDef
            d.callback(self.cookie)
        else:
            # If the NAT is doing port translation as well, we will just
            # have to try STUN and hope that the RTP/RTCP ports are on
            # adjacent port numbers. Please, someone make the pain stop.
            self.natMapping()
        return rtpPort, rtcpPort

    def getVisibleAddress(self):
        ''' returns the local IP address used for RTP (as visible from the
            outside world if STUN applies) as ( 'w.x.y.z', rtpPort)
        '''
        # XXX got an exception at runtime here as mapper hasn't finished yet
        #and
        #attribute _extIP doesn't exist.  I guess this means this should be
        #triggered by
        #the mapper instead of being a return value... --Zooko 2005-04-05
        return (self._extIP, self._extRTPPort)

    def natMapping(self):
        ''' Uses STUN to discover the external address for the RTP/RTCP
            ports. deferred is a Deferred to be triggered when STUN is
            complete.
        '''
        if VERBOSE:
            print "Nat mapping ..."
        # See above comment about port translation.
        # We have to do STUN for both RTP and RTCP, and hope we get a sane
        # answer.
        from nat import getMapper
        d = getMapper()
        d.addCallback(self._cb_gotMapper)
        return d

    def unmapRTP(self):
        from nat import getMapper
        if self.needSTUN is False:
            return defer.succeed(None)
        # Currently removing an already-fired trigger doesn't hurt,
        # but this seems likely to change.
        try:
            reactor.removeSystemEventTrigger(self._shutdownHook)
        except:
            pass
        d = getMapper()
        d.addCallback(self._cb_unmap_gotMapper)
        return d

    def _cb_unmap_gotMapper(self, mapper):
        rtpDef = mapper.unmap(self.transport)
        rtcpDef = mapper.unmap(self.RTCP.transport)
        dl = defer.DeferredList([rtpDef, rtcpDef])
        return dl

    def _cb_gotMapper(self, mapper):
        rtpDef = mapper.map(self.transport)
        rtcpDef = mapper.map(self.RTCP.transport)
        #TODO check addSystemEventTrigger function of reactor
        self._shutdownHook =reactor.addSystemEventTrigger('before',
                                                          'shutdown',
                                                          self.unmapRTP)
        dl = defer.DeferredList([rtpDef, rtcpDef])
        dl.addCallback(self.setStunnedAddress).addErrback(log.err)

    def setStunnedAddress(self, results):
        ''' Handle results of the rtp/rtcp STUN. We have to check that
            the results have the same IP and usable port numbers
        '''
        log.msg("got NAT mapping back! %r"%(results), system='rtp')
        rtpres, rtcpres = results
        if rtpres[0] != defer.SUCCESS or rtcpres[0] != defer.SUCCESS:
            # barf out.
            log.msg("uh oh, stun failed %r"%(results), system='rtp')
        else:
            # a=RTCP might help for wacked out RTCP/RTP pairings
            # format is something like "a=RTCP:AUDIO 16387"
            # See RFC 3605
            code1, rtp = rtpres
            code2, rtcp = rtcpres
            if rtp[0] != rtcp[0]:
                print "stun gave different IPs for rtp and rtcp", results
            # We _should_ try and see if we have working rtp and rtcp, but
            # this seems almost impossible with most firewalls. So just try
            # to get a working rtp port (an even port number is required).
            elif False and ((rtp[1] % 2) != 0):
                log.error("stun: unusable RTP/RTCP ports %r, retry #%d"%
                                            (results, self._stunAttempts),
                                            system='rtp')
                # XXX close connection, try again, tell user
                if self._stunAttempts > 8:
                    # XXX
                    print "Giving up. Made %d attempts to get a working port" \
                        % (self._stunAttempts)
                self._stunAttempts += 1
                defer.maybeDeferred(
                            self.rtpListener.stopListening).addCallback( \
                    lambda x:self.rtcpListener.stopListening()).addCallback( \
                    lambda x:self._socketCreationAttempt())
            else:
                # phew. working NAT
                log.msg("stun: sane NAT for RTP/RTCP; rtp addr: %s" \
                            % (rtp,), system='rtp')
                #Register address and port
                self._extIP, self._extRTPPort = rtp
                self._stunAttempts = 0
                d = self._socketCompleteDef
                del self._socketCompleteDef
                d.callback(self.cookie)

    def connectionRefused(self):
        if VERBOSE:
            print "RTP got a connection refused, continuing anyway",
            print " (May be remote has close his connection...)"
        self.Done = True
        self.app.drop_call(self.cookie)

    def whenDone(self, cbDone):
        self._cbDone = cbDone

    def stopSendingAndReceiving(self):
        self.Done = 1
        self.jitter_buffer_flag = False
        self.RTCP.send_BYE("Normal quit, ending session")
        self.RTCP.stop()
        #XXXSHTOOM
        #d = self.unmapRTP()
        d = defer.succeed(None)
        if self.rport > 0:
            d.addCallback(lambda x: self.rtpListener.stopListening())
        d.addCallback(lambda x: self.rtcpListener.stopListening())

    def _send_packet(self, pt, data, marker=0, xhdrtype=None, xhdrdata=''):
        if not self.RTCP.we_sent:
            #Updating we_sent
            self.RTCP.we_sent = True
            #Adding itself to senders table
            new_member =self.RTCP.member.copy()
            loc = self.getVisibleAddress()
            #new_member['addr'] = "localhost"
            #new_member['port'] = loc[1]+1
            self.RTCP.senders_table[self.ssrc] = new_member
        #Building packet
        packet = RTPPacket(self.ssrc, self.seq, self.ts, data, pt=pt,
                           marker=marker, xhdrtype=xhdrtype, xhdrdata=xhdrdata)
        self.seq += 1
	rtp, session = self.app.currentRecordings[self.cookie]
	session.seq = self.seq
        # Note that seqno gets modulo 2^16 in RTPPacket, so it doesn't need
        # to be wrapped at 16 bits here.
        if self.seq >= 65536:
            self.seq = 1
        bytes = packet.netbytes()
        ## For RTCP sender report.
        self.currentSentBytesTotal += len(bytes)
        self.currentSentPacketsTotal += 1
        for ssrc in self.RTCP.members_table:
            if (ssrc != self.ssrc) and (self.RTCP.members_table[ssrc]['rtcp_port'] != 0):
                try:
                    dest = (self.RTCP.members_table[ssrc]['addr'],
                            self.RTCP.members_table[ssrc]['rtcp_port']-1)
                    if DEBUG:
                        print "send RTP to " + str(dest)
                    self.transport.write(bytes, dest)
                except MessageLengthError, e:
                    print "Cannot write on socket ! Exception e (member: " \
                        + str(self.RTCP.members_table[ssrc])
                self.last_sent_time = time()

    def _send_cn_packet(self, logit=False, recovery=0):
        """Send empty packet in order to signal a silence and detect any
        loss of packet (also usefull fro the first packet"""
        assert hasattr(self, 'dest'), "_send_cn_packet called before start %r" \
            % (self,)
        if logit:
            if VERBOSE:
                print
                print "Sending CN(%s) to seed firewall to %s:%d" % (self.payload, self.dest[0], self.dest[1])
        self._send_packet(self.payload, chr(127))

    def start(self, dest, fp=None):
        self.dest = dest
        self.jitter_buffer_flag = True
        self.Done = False
        self.sending = True
        # don't use udp connected mode if were sending to localhost, otherwise we won't be able
        # to receive on localhost as this sender will also listen on this port, blocking any
        # woudl be receiver from using this port
        #if hasattr(self.transport, 'connect') and self.dest[0] != '127.0.0.1':
        #    self.transport.connect(*self.dest)

        # Now send a single CN packet to seed any firewalls that might
        # need an outbound packet to let the inbound back.
        self._send_cn_packet(logit=True)
        #Launching jitter buffer polling
        if self.rport > 0:
            reactor.callInThread(self._polling_jitter_buffer)
        #Launching RTCP
        self.RTCP.start()

    def _polling_jitter_buffer(self):
        while self.jitter_buffer_flag:
            #if something in the jitter buffer
            if len(self.jitter_buffer.buffer) > 0:
                #Getting packets from jitter buffer
                ref_time = time()*1000 - self.jitter_buffer_time
                res = self.jitter_buffer.get_packets(ref_time)
                #Checking seq num and silent packets
                for packet in res:
                    ssrc = packet.header.ssrc
                    #Wrap around seq num
                    if self.RTCP.members_table[ssrc]['last_seq'] >= 65535:
                        self.RTCP.members_table[ssrc]['last_seq'] = 1
                    #Checking seq num
                    if self.RTCP.members_table[ssrc]['last_seq']+1 \
                            == packet.header.seq:
                        #Call app without recovery
                        self.app.incoming_rtp(self.cookie, packet.header.ts, \
                                                  packet, 0)
                        self.RTCP.members_table[ssrc]['last_seq'] += 1
                    else:
                        if self.RTCP.members_table[ssrc]['last_seq'] == 0:
                            #Call app with recovery journal
                            self.app.incoming_rtp(self.cookie, packet.header.ts, \
                                                      packet, 0)
                            self.RTCP.members_table[ssrc]['last_seq'] \
                                = packet.header.seq
                        else:
                            #recover infos
                            self.RTCP.members_table[ssrc]['lost'] += 1
                            self.RTCP.members_table[ssrc]['last_seq'] \
                                = packet.header.seq
                            #logging
                            if VERBOSE:
                                line = "Packet Num " \
                                    + str(self.RTCP.members_table[ssrc]['last_seq']-1)
                                line += " lost (total lost: " \
                                    + str(self.RTCP.members_table[ssrc]['lost']) + ")"
                                line += " for client " \
                                    + str(self.RTCP.members_table[ssrc]['addr'])
                                print line
                            #Call app with recovery journal
                            self.app.incoming_rtp(self.cookie, packet.header.ts,
                                                  packet, 1)
            sleep(0.001)

    def datagramReceived(self, datagram, addr, t=time):
        """Handle packets arriving"""
        if self.rport == 0:
            return
        if not self.checksum(datagram):
            if VERBOSE:
                print "Warning: Packet received with wrong checksum RTP"
            return
        #parse the packet
        packet = parse_rtppacket(datagram)
        #Checking SSRC
        ssrc = packet.header.ssrc
        if ssrc in self.RTCP.members_table:
            cname = self.RTCP.members_table[ssrc]['cname']
        else:
            cname = ""
        if not self.RTCP.check_ssrc(ssrc, addr, "DATA", cname):
            if VERBOSE:
                print "Warning: Bad SSRC leaving packet on the floor"
            return
        else:
            #Update last_seq and lastreceivetime
            self.RTCP.members_table[ssrc]['total_received_bytes'] += len(datagram)
            self.RTCP.members_table[ssrc]['total_received_packets'] += 1
            self.RTCP.members_table[ssrc]['last_rtp_receive'] = time()

            if self.RTCP.members_table[ssrc]['last_seq'] != 0 :
                if packet.data == "p":
                    #Silent without recovery
                    if DEBUG :
                        print "silent packet received"
                    #self.RTCP.members_table[ssrc]['last_seq'] += 1
                    return
                #Testing payload type TODO erase this test
                if packet.header.pt == self.payload:
                    if DEBUG:
                        print "payload of packet accepted"
                    #Getting stats
                    last_ts = self.RTCP.members_table[ssrc]['last_ts']
                    last_time = self.RTCP.members_table[ssrc]['last_time']
                    jitter = self.RTCP.members_table[ssrc]['jitter']
                    #Jitter calculation (rfc 3550 6.4.1)
                    #S = RTP Timestamp and R is time of arrival
                    if (last_ts == 0 and last_time == 0) \
                            or ( (int(time()*1000 - self.init_time) \
                                      - last_time) > JITTER_CALC_TIME_OUT ):
                        last_ts = packet.header.ts
                        last_time = int(time()*1000 - self.init_time)
                    else:
                        arrival_time = int(time()*1000 - self.init_time)
                        timestamp = packet.header.ts
                        delta = float(( arrival_time - last_time ) \
                                      - ( timestamp - last_ts ))
                        jitter = jitter \
                            + ( abs(delta) - jitter ) / 16
                        self.RTCP.members_table[ssrc]['last_ts'] = timestamp
                        last_time = self.RTCP.members_table[ssrc]['last_time'] = arrival_time
                        self.RTCP.members_table[ssrc]['jitter_values'].to_list(jitter)
                        self.RTCP.members_table[ssrc]['jitter'] = jitter
                    if self.RTCP.members_table[ssrc]['total_received_packets'] % CHECK_FREQ == 0:
                        if DEBUG:
                            print "Estimate jitter time"
                        jitter_average = self.RTCP.members_table[ssrc]['jitter_values'].average()
                        total_received = self.RTCP.members_table[ssrc]['total_received_packets']
                        #Lost rate estimation
                        lost = self.RTCP.members_table[ssrc]['lost']
                        lost_rate = (lost / float(total_received + lost)) * 100
                        #Keep this ?
                        if lost_rate > MAX_LOST_RATE :
                            if VERBOSE:
                                line = "Loosing too much packet !!"
                                print line
                        #Adjusting latency (based on round trip time/jitter)
                        #self.test_jitter()
                        #self.test_delay()

                    #Adding packet to the jitter buffer
                    if DEBUG:
                        print "Adding packet to jitter buffer"
                    self.jitter_buffer.add([packet, time()*1000])
                else:
                    if VERBOSE:
                        print "Incompatible payload type"
            else:
                #this is the first packet
                if VERBOSE:
                    line = "First RTP packet received from " + str(addr)
                    print line
                self.RTCP.members_table[ssrc]['last_seq'] = packet.header.seq

##
#Testing function
##
    def checksum(self, bytes):
        """Testing that the packet is valid"""
        #FIXME: rename for a better name
        try:
            header = unpack('!BBHII', bytes[:12])
        except struct.error, e:
            return False
        except IndexError, e:
            return False
        #(version)
        version = (header[0]>>6)
        if version != 2:
            return False
        # Payload type
        pt = header[1] & 127
        if pt != self.payload:
            return False
        # Padding
        padding = (header[0] & 32) and 1 or 0
        if padding:
            oct_count = len(bytes) - 12
            if (oct_count % 4) != 0:
                return 0
        #Others test ??
        # Extension header present
        #ext = (hdrpieces[0] & 16) and 1 or 0
        #TODO test ext
        #si ext, extension mecanism n'est pas present dans session RTP sinon
        #return 0
        #sinon
        #
        #TEst : packet must be consistent with CC ? and
        #payload type(chek midi payload)
        return True

#   def test_jitter(self, ):
#       jbtime = self.jitter_buffer_time
#       #Ajusting jitter buffer size and timestamp
#       if int(jitter_average) > int(jbtime) + 3:
#           self.app.midi_out.latency += \
#               int(jitter_average - jbtime) \
#               + 10
#           self.jitter_buffer_time += \
#               int(jitter_average - jbtime) \
#               + 10
#           #Logging
#           line = "Increasing jitter buffer, now set to "
#           line += str(self.jitter_buffer_time)
#           line += " ms, jitter estimation is "
#           line += str(int(jitter_average)) + " ms"
#           log.info(line)
#       elif int(jitter_average) < (int(jbtime) - 10) \
#               and (jbtime - (jbtime - jitter_average) - 3) \
#               > MIN_JITTER_BUFFER_TIME \
#               and jbtime > MIN_JITTER_BUFFER_TIME:
#           self.app.midi_out.latency -= \
#               int(jbtime - jitter_average) - 3
#           self.jitter_buffer_time -= \
#               int(jbtime - jitter_average) - 3
#           #Logging
#           line = "Decreasing jitter buffer, now set to "
#           line += str(self.jitter_buffer_time)
#           line += " ms, jitter estimation is "
#           line += str(int(jitter_average)) + " ms"
#           log.info(line)

#   def test_delay(self):
#       if DEBUG:
#           print "test delay"
#       if self.rt_time != None and self.rt_time_ref != None:
#           rt_time = self.rt_time * 1000
#           rt_time_ref = self.rt_time_ref * 1000
#           if rt_time > rt_time_ref:
#                           #latency MUST be > to the split between initial
#                           #rt_time and rt_time_ref
#               self.app.midi_out.latency += \
#                   int(rt_time - rt_time_ref) + 10
#                           #Logging action
#               line = "Updating latency to feet the changing delay"
#               line += ", now set to "
#               line += str(self.app.midi_out.latency) + " ms"
#               log.nfo(line)

#                           #Update split_ts
#               self.split_ts = new_split_ts
#           elif rt_time < (rt_time_ref - 40)  \
#                   and (self.app.midi_out.latency  > MIN_LATENCY) \
#                   and ((self.app.midi_out.latency  \
#                             - int(rt_time_ref - rt_time) - 10)  \
#                            > MIN_LATENCY):
#                           #latency
#               self.app.midi_out.latency -= \
#                   int(rt_time_ref - rt_time) - 10
#                           #Logging action
#               line = "Updating latency to feet the changing delay"
#               line += ", now set to "
#               line += str(self.app.midi_out.latency) + " ms"
#               log.info(line)
#                           #Update round trip time ref
#               self.rt_time_ref = rt_time / 1000
#       else:
#           if self.rt_time != None:
#               if DEBUG:
#                   print "init rt_ref time"
#               self.rt_time_ref = self.rt_time
#

    def genSSRC(self):
        # Python-ish hack at RFC1889, Appendix A.6
        m = hashlib.new('md5')
        m.update(str(time()))
        m.update(str(id(self)))
        if hasattr(os, 'getuid'):
            m.update(str(os.getuid()))
            m.update(str(os.getgid()))
        m.update(str(socket.gethostname()))
        hex = m.hexdigest()
        nums = hex[:8], hex[8:16], hex[16:24], hex[24:]
        nums = [ long(x, 17) for x in nums ]
        ssrc = 0
        for n in nums: ssrc = ssrc ^ n
        ssrc = ssrc & (2**32 - 1)
        return ssrc

    def genInitTS(self):
        # Python-ish hack at RFC1889, Appendix A.6
        m = hashlib.new('md5')
        m.update(str(self.genSSRC()))
        m.update(str(time()))
        hex = m.hexdigest()
        nums = hex[:8], hex[8:16], hex[16:24], hex[24:]
        nums = [ long(x, 16) for x in nums ]
        ts = 0
        for n in nums: ts = ts ^ n
        ts = ts & (2**32 - 1)
        return ts

    def genRandom(self, bits):
        """Generate up to 128 bits of randomness."""
        if os.path.exists("/dev/urandom"):
            hex = open('/dev/urandom').read(16).encode("hex")
        else:
            m = hashlib.new('md5')
            m.update(str(time()))
            m.update(str(random.random()))
            m.update(str(id(self.dest)))
            hex = m.hexdigest()
        return int(hex[:bits//4],16)

    def handle_data(self, pt, timestamp, sample, marker):
        if self.Done:
            if self._cbDone:
                self._cbDone()
            return
        # We need to keep track of whether we were in silence mode or not -
        # when we go from silent->talking, set the marker bit. Other end
        # can use this as an excuse to adjust playout buffer.
        if not self.sending:
            if not hasattr(self, 'warnedaboutthis'):
                log.info(("%s.handle_media_sample() should only be called" +
                         " only when it is in sending mode.") % (self,))

                if VERBOSE:
                    print "WARNING: warnedaboutthis"

                self.warnedaboutthis = True
            return
        incTS = True
        #Marker is on first packet after a silent
        if not self._silent:
            if marker:
                marker = 0
                self._silent = True
                incTS = False
        else:
            marker = 1
            self._silent = False
        if incTS:
            #Taking care about ts
            self.ts += int(timestamp)
        # Wrapping
        if self.ts >= TWO_TO_THE_32ND:
            self.ts = self.ts - TWO_TO_THE_32ND
        self._send_packet(pt, sample, marker=marker)
