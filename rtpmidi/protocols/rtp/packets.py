# Copyright (C) 2004 Anthony Baxter

import struct
from time import time

# This class supports extension headers, but only one per packet.
class RTPPacket:
    """ Contains RTP data. """
    class Header:
        def __init__(self, ssrc, pt, ct, seq, ts, marker=0,
                     xhdrtype=None, xhdrdata=''):
            """
            If xhdrtype is not None then it is required to be an
            int >= 0 and < 2**16 and xhdrdata is required to be
            a string whose length is a multiple of 4.
            """
            assert isinstance(ts, (int, long,)), "ts: %s :: %s" % (ts, type(ts))
            assert isinstance(ssrc, (int, long,))
            assert xhdrtype is None or isinstance(xhdrtype, int) \
                    and xhdrtype >= 0 and xhdrtype < 2**16
            # Sorry, RFC standard specifies that len is in 4-byte words,
            # and I'm not going to do the padding and unpadding for you.
            assert xhdrtype is None or (isinstance(xhdrdata, str) and \
                    len(xhdrdata) % 4 == 0), \
                    "xhdrtype: %s, len(xhdrdata): %s, xhdrdata: %s" % (
                    xhdrtype, len(xhdrdata), `xhdrdata`,)

            (self.ssrc, self.pt, self.ct, self.seq, self.ts,
                 self.marker, self.xhdrtype, self.xhdrdata) = (
             ssrc,      pt,      ct,      seq,      ts,
                 marker,      xhdrtype,      xhdrdata)

        def netbytes(self):
            "Return network-formatted header."
            assert isinstance(self.pt, int) and self.pt >= 0 and \
                self.pt < 2**8, \
                "pt is required to be a simple byte, suitable " + \
                "for stuffing into an RTP packet and sending. pt: %s" % self.pt
            if self.xhdrtype is not None:
                firstbyte = 0x90
                xhdrnetbytes = struct.pack('!HH', self.xhdrtype,
                                    len(self.xhdrdata)/4) + self.xhdrdata
            else:
                firstbyte = 0x80
                xhdrnetbytes = ''
            return struct.pack('!BBHII', firstbyte,
                                        self.pt | self.marker << 7,
                                        self.seq % 2**16,
                                        self.ts, self.ssrc) + xhdrnetbytes

    def __init__(self, ssrc, seq, ts, data, pt=None, ct=None, marker=0,
                 authtag='', xhdrtype=None, xhdrdata=''):
        assert pt is None or isinstance(pt, int) and pt >= 0 and pt < 2**8, \
            "pt is required to be a simple byte, suitable for stuffing " + \
            "into an RTP packet and sending. pt: %s" % pt
        self.header = RTPPacket.Header(ssrc, pt, ct, seq, ts, marker,
                                       xhdrtype, xhdrdata)
        self.data = data
        # please leave this alone even if it appears unused --
        # it is required for SRTP
        self.authtag = authtag

    def __repr__(self):
        if self.header.ct is not None:
            ptrepr = "%r" % (self.header.ct,)
        else:
            ptrepr = "pt %s" % (self.header.pt,)

        if self.header.xhdrtype is not None:
            return "<%s #%d (%s) %s [%s] at %x>"%(self.__class__.__name__,
                                                  self.header.seq,
                                                  self.header.xhdrtype,
                                                  ptrepr,
                                                  repr(self.header.xhdrdata),
                                                  id(self))
        else:
            return "<%s #%d %s at %x>"%(self.__class__.__name__,
                                        self.header.seq, ptrepr, id(self))

    def netbytes(self):
        "Return network-formatted packet."
        return self.header.netbytes() + self.data + self.authtag




def parse_rtppacket(bytes, authtaglen=0):
    # Most variables are named for the fields in the RTP RFC.
    hdrpieces = struct.unpack('!BBHII', bytes[:12])

    # Padding
    p = (hdrpieces[0] & 32) and 1 or 0
    # Extension header present
    x = (hdrpieces[0] & 16) and 1 or 0
    # CSRC Count
    cc = hdrpieces[0] & 15
    # Marker bit
    marker = hdrpieces[1] & 128
    # Payload type
    pt = hdrpieces[1] & 127
    # Sequence number
    seq = hdrpieces[2]
    # Timestamp
    ts = hdrpieces[3]
    ssrc = hdrpieces[4]
    headerlen = 12 + cc * 4
    # XXX throwing away csrc info for now
    bytes = bytes[headerlen:]
    if x:
        # Only one extension header
        (xhdrtype, xhdrlen,) = struct.unpack('!HH', bytes[:4])
        xhdrdata = bytes[4:4+xhdrlen*4]
        bytes = bytes[xhdrlen*4 + 4:]
    else:
        xhdrtype, xhdrdata = None, None
    if authtaglen:
        authtag = bytes[-authtaglen:]
        bytes = bytes[:-authtaglen]
    else:
        authtag = ''
    if p:
        # padding
        padlen = struct.unpack('!B', bytes[-1])[0]
        if padlen:
            bytes = bytes[:-padlen]
    return RTPPacket(ssrc, seq, ts, bytes, marker=marker, pt=pt,
                     authtag=authtag, xhdrtype=xhdrtype, xhdrdata=xhdrdata)


class NTE:
    "An object representing an RTP NTE (rfc2833)"
    # XXX at some point, this should be hooked into the RTPPacketFactory.
    def __init__(self, key, startTS):
        self.startTS = startTS
        self.ending = False
        self.counter = 3
        self.key = key
        if key >= '0' and key <= '9':
            self._payKey = chr(int(key))
        elif key == '*':
            self._payKey = chr(10)
        elif key == '#':
            self._payKey = chr(11)
        elif key >= 'A' and key <= 'D':
            # A - D are 12-15
            self._payKey = chr(ord(key)-53)
        elif key == 'flash':
            self._payKey = chr(16)
        else:
            raise ValueError, "%s is not a valid NTE"%(key)

    def getKey(self):
        return self.key

    def end(self):
        self.ending = True
        self.counter = 1

    def getPayload(self, ts):
        if self.counter > 0:
            if self.ending:
                end = 128
            else:
                end = 0
            payload = self._payKey + chr(10|end) + \
                                struct.pack('!H', ts - self.startTS)
            self.counter -= 1
            return payload
        else:
            return None

    def isDone(self):
        if self.ending and self.counter < 1:
            return True
        else:
            return False

    def __repr__(self):
        return '<NTE %s%s>'%(self.key, self.ending and ' (ending)' or '')


####################################RTCP Packets############################
#Constants
RTCP_PT_SR = 200
RTCP_PT_RR = 201
RTCP_PT_SDES = 202
RTCP_PT_BYE = 203
RTCP_PT_APP = 204
rtcpPTdict = {RTCP_PT_SR: 'SR', RTCP_PT_RR: 'RR', RTCP_PT_SDES:'SDES', \
                  RTCP_PT_BYE:'BYE'}

for k,v in rtcpPTdict.items():
    rtcpPTdict[v] = k

RTCP_SDES_CNAME = 1
RTCP_SDES_NAME = 2
RTCP_SDES_EMAIL = 3
RTCP_SDES_PHONE = 4
RTCP_SDES_LOC = 5
RTCP_SDES_TOOL = 6
RTCP_SDES_NOTE = 7
RTCP_SDES_PRIV = 8

RTP_VERSION = 2

rtcpSDESdict = {RTCP_SDES_CNAME: 'CNAME',
                RTCP_SDES_NAME: 'NAME',
                RTCP_SDES_EMAIL: 'EMAIL',
                RTCP_SDES_PHONE: 'PHONE',
                RTCP_SDES_LOC: 'LOC',
                RTCP_SDES_TOOL: 'TOOL',
                RTCP_SDES_NOTE: 'NOTE',
                RTCP_SDES_PRIV: 'PRIV',
               }

for k,v in rtcpSDESdict.items():
    rtcpSDESdict[v] = k

def hexrepr(bytes):
    out = ''
    bytes = bytes + '\0'* ( 8 - len(bytes)%8 )
    for i in range(0,len(bytes), 8):
        out = out +  "    %02x%02x%02x%02x %02x%02x%02x%02x\n" \
            % tuple([ord(bytes[i+x]) for x in range(8)])
    return out

def ext_32_out_of_64(value):
    """16 bits for int part and 16 bit for fractionnal part
    These two values are format in I (unsigned int)"""
    value_int = int(value)
    value_frac = value - value_int
    value_int = value_int & 65535

    if value_frac > 0:
        value_frac = value_frac * (10 ** 4)
        #Why all that needed...
        value_frac = int(float(str(value_frac)))

    else:
        value_frac = 0

    value_int = value_int << 16
    res = value_int | value_frac
    return res

def unformat_from_32(value):
    value_int = value >> 16
    value_frac = value & 65535
    value =  value_int + ( value_frac * (10 ** -4))
    return value

class RTCPPacket:
    def __init__(self, pt, contents=None, ptcode=None):
        self._pt = pt
        if ptcode is None:
            self._ptcode = rtcpPTdict.get(pt)
        else:
            self._ptcode = ptcode
        self._body = ''
        if contents:
            self._contents = contents
        else:
            self._contents = None

    def getPT(self):
        return self._pt

    def getContents(self):
        return self._contents

    def decode(self, count, body):
        self._count = count
        self._body = body
        getattr(self, 'decode_%s'%self._pt)()

    def encode(self):
        out = getattr(self, 'encode_%s'%self._pt)()
        return out

    def _padIfNeeded(self, packet):
        if len(packet)%4:
            pad = '\0' * (4-(len(packet)%4))
            packet += pad

        return packet

    def _patchLengthHeader(self, packet):
        length = (len(packet)/4) - 1
        packet = packet[:2] + struct.pack('!H', length) + packet[4:]
        return packet

    def decode_SDES(self):
        for i in range(self._count):
            self._contents = []
            ssrc, = struct.unpack('!I', self._body[:4])
            self._contents.append((ssrc,[]))
            self._body = self._body[4:]

            off = 0
            while True:
                type, length = ord(self._body[0]), ord(self._body[1])

                #Cumul length to check padding
                off += length+2

                maybepadlen = 4-((off)%4)

                body, maybepad = self._body[2:length+2], \
                    self._body[length+2:length+2+maybepadlen]

                #Flushing body
                self._body = self._body[length+2:]
                self._contents[-1][1].append((rtcpSDESdict[type], body))

                if ord(maybepad[0]) == 0:
                    # end of list. eat the padding.
                    self._body = self._body[maybepadlen:]
                    break


    def encode_SDES(self):
        """
        6.5 SDES: Source Description RTCP Packet

        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |V=2|P|    SC   |  PT=SDES=202  |             length            |
       +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
       |                          SSRC/CSRC_1                          |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                           SDES items                          |
       |                              ...                              |
       +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
        """
        blocks = self._contents
        packet = struct.pack('!BBH',len(blocks)|128, self._ptcode, 0)

        for ssrc,items in blocks:
            packet += struct.pack('!I', ssrc)

            for sdes, value in items:
                sdescode = rtcpSDESdict[sdes]
                packet += struct.pack('!BB', sdescode, len(value)) + value
            if len(packet)%4:
                packet = self._padIfNeeded(packet)
            else:
                packet += '\0\0\0\0'

        packet = self._patchLengthHeader(packet)
        return packet

    def decode_BYE(self):
        self._contents = [[],'']
        for i in range(self._count):
            ssrc, = struct.unpack('!I', self._body[:4])
            self._contents[0].append(ssrc)
            self._body = self._body[4:]
        if self._body:
            # A reason!
            length = ord(self._body[0])
            reason = self._body[1:length+1]
            self._contents[1] = reason
            self._body = ''

    def encode_BYE(self):
        """
        6.6 BYE: Goodbye RTCP Packet

        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |V=2|P|    SC   |   PT=BYE=203  |             length            |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |                           SSRC/CSRC                           |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        :                              ...                              :
        +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
        |     length    |               reason for leaving            ...
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        """
        #the BYE packet MUST be padded with null octets to the next 32-
        #bit boundary.
        ssrcs, reason = self._contents
        packet = struct.pack('!BBH',len(ssrcs)|128, self._ptcode, 0)
        for ssrc in ssrcs:
            packet = packet + struct.pack('!I', ssrc)
        if reason:
            packet = packet + chr(len(reason)) + reason
        packet = self._padIfNeeded(packet)
        packet = self._patchLengthHeader(packet)
        return packet

    def decode_SR(self):
        self._contents = []
        ssrc, = struct.unpack('!I', self._body[:4])
        bits = struct.unpack('!IIIII', self._body[4:24])
        names = 'ntpHi', 'ntpLo', 'rtpTS', 'packets', 'octets'
        sender = dict(zip(names, bits))

        #ntpTS care
        sender['ntpTS'] = sender['ntpHi'] + sender['ntpLo'] * ( 10 ** -9)
        del sender['ntpHi'], sender['ntpLo']

        self._body = self._body[24:]
        blocks = self._decodeRRSRReportBlocks()
        self._contents = [ssrc,sender,blocks]

    def encode_SR(self):
        """
        Sender report
        6.4.1 rfc 3550
        NTP Timestamps represents the ntp time in timestamp format
        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |V=2|P|    RC   |   PT=SR=200   |             length            |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                         SSRC of sender                        |
       +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
       |              NTP timestamp, most significant word             |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |             NTP timestamp, least significant word             |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                         RTP timestamp                         |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                     sender's packet count                     |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                      sender's octet count                     |
       +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
       + blocks
       """

        #header
        version = RTP_VERSION * (2**6)
        #Padding 0 or 1
        padding = 0
        #Count 0->31 Number of reception block contain in the packet

        #Packet type
        type = self._ptcode
        #Length
        length = 0

        #Building packet
        #Contents wait (order is important for what's above)
        #(ssrc, ts, total_packets, total_bytes, members)
        (ssrc, ts, total_packets, total_bytes, members) = self._contents

        #Take care about ntp
        ntp = time()
        ntp_m = int(ntp)
        ntp_l = ntp - ntp_m
        ntp_l = int(ntp_l * ( 10 ** 9))

        #SR parts
        packet = struct.pack('!IIIIII', ssrc, ntp_m, ntp_l, ts, total_packets, total_bytes)

        #Processing blocks
        block_packets, count = self._encodeRRSRReportBlocks(ssrc, members)
        starter = version | padding | count
        packet += block_packets

        #+ 4 is for header (see page 36 of RFC 3550)
        #length = len(packet) + 4
        header = struct.pack('!BBH', starter, type, 0)

        packet = header + packet

        #Checking padding
        packet = self._padIfNeeded(packet)
        packet = self._patchLengthHeader(packet)

        return packet

    def decode_RR(self):
        ssrc, = struct.unpack('!I', self._body[:4])
        self._body = self._body[4:]
        blocks = self._decodeRRSRReportBlocks()
        self._contents = [ssrc,blocks]

    def encode_RR(self):
        """
        rfc 3550
        6.4.2 RR: Receiver Report RTCP Packet

        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |V=2|P|    RC   |   PT=RR=201   |             length            |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                     SSRC of packet sender                     |
       +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
       + blocks
       """

        #header
        #Version 1 ou 2
        version = RTP_VERSION * (2**6)
        #Padding 0 ou 1
        padding = 0 * (2**5)

        #Packet type
        type = self._ptcode
        #Length
        length = 0

        (ssrc, members) \
            = self._contents

        #ount = len(members)
        packet = struct.pack('!I', ssrc)
        block_packets, count = self._encodeRRSRReportBlocks(ssrc, members)
        starter = version | padding | count
        packet += block_packets

        #+ 4 is for header (see page 36 of RFC 3550)
        length = len(packet) + 4
        header = struct.pack('!BBH', starter, type, length)
        packet = header + packet

        #Checking padding
        packet = self._padIfNeeded(packet)
        packet = self._patchLengthHeader(packet)

        return packet

    def _encodeRRSRReportBlocks(self, my_ssrc, members):
        """
        +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
        |                 SSRC_1 (SSRC of first source)                 |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        | fraction lost |       cumulative number of packets lost       |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |           extended highest sequence number received           |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |                      interarrival jitter                      |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |                         last SR (LSR)                         |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |                   delay since last SR (DLSR)                  |
        +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
        """
        packet = ""
        count = 0
        ref_time = time()
        for ssrc in members:
            if ssrc != my_ssrc:
            #ssrc_1, frac_lost, lost, highest, jitter, lsr, dlsr
                lost = members[ssrc]['lost']
                if members[ssrc]['total_received_packets'] > 0:
                    frac_lost = int(lost / float(members[ssrc]['total_received_packets'] + lost))
                else:
                    frac_lost = 0

                #Take care about fraction lost
                frac_lost = frac_lost << (3*8)
                lost_part = frac_lost | lost

                #Take care about lsr and dlsr
                lsr = members[ssrc]['lsr']
                lsr = ext_32_out_of_64(lsr)

                if lsr != 0:
                    dlsr = ref_time - lsr
                else:
                    dlsr = 0

                dlsr = ext_32_out_of_64(dlsr)

                highest = members[ssrc]['last_seq']
                jitter = members[ssrc]['jitter']

                arg_list = (ssrc, lost_part, highest, jitter, lsr, dlsr)

                packet += struct.pack('!IIIIII', *arg_list)
                count += 1

                #Max 31 members in a report
                if count == 31:
                    break

        return packet, count

    def _decodeRRSRReportBlocks(self):
        blocks = []
        for i in range(self._count):
            bits = struct.unpack('!IIIIII', self._body[:24])
            names = 'ssrc', 'lost', 'highest', 'jitter', 'lsr', 'dlsr'
            c = dict(zip(names,bits))

            #Take care about lost part
            c['fraclost'] = c['lost'] >> 24
            c['packlost'] = (c['lost'] & 0x00FFFFFF)
            del c['lost']

            c['lsr'] = unformat_from_32(c['lsr'])
            c['dlsr'] = unformat_from_32(c['dlsr'])

            blocks.append(c)
            self._body = self._body[24:]
        return blocks

    def decode_APP(self):
        self._contents = []
        subtype = self._count
        ssrc, = struct.unpack('!I', self._body[:4])
        name = self._body[4:8]
        value = self._body[8:]
        self._contents = [subtype,ssrc,name,value]

    def encode_APP(self):
        subtype,ssrc,name,value = self._contents
        packet = struct.pack('!BBHI',subtype|128, self._ptcode, 0, ssrc)
        packet = packet + name + value
        packet = self._padIfNeeded(packet)
        packet = self._patchLengthHeader(packet)
        return packet

    # We can at least roundtrip unknown RTCP PTs
    def decode_UNKNOWN(self):
        self._contents = (self._count, self._body)
        self._body = ''

    def encode_UKNOWN(self):
        count, body = self._contents
        packet = struct.pack('!BBH',count|128, self._ptcode, 0)
        packet = packet + body
        packet = self._padIfNeeded(packet)
        packet = self._patchLengthHeader(packet)
        return packet

    def __repr__(self):
        if self._body:
            leftover = ' '+repr(self._body)
        else:
            leftover = ''
        return '<RTCP %s %r %s>'%(self._pt, self._contents, leftover)


class RTCPCompound:
    "A single RTCP packet can contain multiple RTCP items"
    def __init__(self, bytes=None):
        self._rtcp = []
        if bytes:
            self.decode(bytes)

    def addPacket(self, packet):
        self._rtcp.append(packet)

    def decode(self, bytes):
        while bytes:
            #Getting infos to decode
            count = ord(bytes[0]) & 31
            pt = ord(bytes[1])
            PT = rtcpPTdict.get(pt, "UNKNOWN")
            try:
                length, = struct.unpack('!H', bytes[2:4])
            except struct.error:
                print "struct.unpack got bad number of bytes"
                return
            offset = 4*(length+1)
            body, bytes = bytes[4:offset], bytes[offset:]
            p = RTCPPacket(PT, ptcode=pt)
            p.decode(count, body)
            self._rtcp.append(p)

        return p

    def encode(self):
        return ''.join([x.encode() for x in self._rtcp])

    def __len__(self):
        return len(self._rtcp)

    def __getitem__(self, i):
        return self._rtcp[i]

    def __repr__(self):
        return "<RTCP Packet: (%s)>" \
            % (', '.join([x.getPT() for x in self._rtcp]))

