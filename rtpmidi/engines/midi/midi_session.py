#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Scenic
# Copyright (C) 2008 Société des arts technologiques (SAT)
# http://www.sat.qc.ca
# All rights reserved.
#
# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# Scenic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Scenic. If not, see <http://www.gnu.org/licenses/>.
"""
RTP MIDI session.
"""
#History Needs
from midi_object import OldPacket
from midi_object import MidiCommand
from list_circ import  PacketCirc
#rtp import
from recovery_journal import RecoveryJournal
from recovery_journal import compare_history_with_recovery
from rtpmidi.protocols.rtp.rtp_session import RTPSession
#twisted import
from twisted.internet import task
#midi import
from rtpmidi.engines.midi.midi_in import MidiIn
from rtpmidi.engines.midi.midi_out import MidiOut
try:
    import pypm
except ImportError:
    from pygame import pypm
from time import time

#Constants
DEFAULT_PORT = 44000
PAYLOAD = 96
#RTP Timeout is 60 (need it because
#midi data are not sent when no note are played)
MIDI_RTP_TIME_OUT = 40
TOOL_NAME = "Sropulpof_midi" #FIXME: rename this
HISTORY_SIZE = 1024
DEBUG = 1

class MidiSession(RTPSession):
    """
    Control RTP for MIDI payload.
    """
    def __init__(self, peer_address, sport=0, rport=0, latency=20,
                 jitter_buffer_size=10, safe_keyboard=0, recovery=1,
                 follow_standard=0, verbose=0):
        #Init mother class
        RTPSession.__init__(self, peer_address, sport, rport, PAYLOAD,
                            jitter_buffer_size, TOOL_NAME)
        self.verbose = verbose
        if verbose:
            print "Your configuration:"
            print "  Latency:", latency, "ms"
            print "  Jitter Buffer Time:", jitter_buffer_size, "ms"
        #init midi
        if self.sport > 0:
            self.midi_in = MidiIn(self, verbose)
        #1 == Permisive mode (make this configurable)
        if self.rport > 0:
            self.midi_out = MidiOut(0, latency, safe_keyboard, verbose)
        #history of the feed
        self.packets_received_list = PacketCirc(HISTORY_SIZE)
        #Recovery utils
        self.recovery = 0
        self.recovery_journal_system = None
        if recovery:
            self.recovery = 1
            self.recovery_journal_system = RecoveryJournal(follow_standard)
            if verbose:
                print "  Recovery journal is running"
                if follow_standard:
                    print "  Recovery is following standard"
        self.init_timestamp = None
        #Flag
        self.sending_data = 0
        self.receiving_data = 0
        #Timestamp story
        self.last_midi_time_sent = pypm.Time()
        self.timeouterLoop = None

    def start(self):
        """
        Launch the MIDI session and the RTP session
        """
        if self.sport > 0:
            self.midi_in.start()
        if self.rport > 0:
            self.midi_out.start()
        self._keep_alive()

    def stop(self):
        """
        Stop midi session and the RTP session
        """
        if self.sport > 0:
            self.midi_in.stop()
        if self.rport > 0:
            self.midi_out.stop()
        if not self.timeouterLoop is None:
            if self.timeouterLoop.running:
                self.timeouterLoop.stop()

    def _keep_alive(self):
        #FIXME: document this
        def check_timeout():
            """
            Sends an empty packet if there is no activity.
            """
            if time.time() > self.last_send + MIDI_RTP_TIME_OUT:
                self.send_silence()
                #Deccomment following line if want to log keep aive packet
                #log.info("silent packet sent to keep alive the connection")
            self.timeouterLoop = task.LoopingCall(check_timeout, now=False)
            self.timeouterLoop.start(15)

    def incoming_rtp(self, cookie, timestamp, packet, read_recovery_journal=0):
        """
        Function called by RTPControl when incoming
        data comes out from jitter buffer.
        """
        #Parsing RTP MIDI Header
        marker_b, marker_j, marker_z, marker_p, length = \
            MidiCommand().parse_header(packet.data[0])
        if marker_p :
            #silent packet with recovery
            midi_list = []
        else:
            #normal packet
            #Extract Midi Note (length en nb notes)
            midi_list = packet.data[1:length*7+1]
            #Decoding midi commands
            midi_list =  MidiCommand().decode_midi_commands(midi_list, length)
        if DEBUG:
            print "receiving data", midi_list
            #Saving feed history
            packet_to_save = OldPacket(self.seq, midi_list, 0)
            self.packets_received_list.to_list(packet_to_save)
        #Extract Midi Recovery Journal if is present in the packet and
        #the previous packet has been lost
        if self.recovery:
            if marker_j and read_recovery_journal:
                if DEBUG:
                    print "Read recovery journal"
                    print packet.header.marker
                journal = packet.data[length*7+1:]
                if len(journal)>0:
                    #Parse Recovery journal
                    r_journal = self.recovery_journal_system.parse(journal)
                else:
                    r_journal = []
                #compare it with history feed
                #Extract midi notes from checkpoint sent to actual seq
                midi_history = self.packets_received_list.get_packets(self.last_checkpoint,self.seq)
                #Selecting only notes present in recovery
                #that are not in feed history
                midi_cmd_history = []
                for i in range(len(midi_history)):
                    cmd_tmp = midi_history[i].packet
                    for j in range(len(cmd_tmp)):
                        midi_cmd_history.append(cmd_tmp[j])
                if DEBUG:
                    rem = time()
                midi_from_history = compare_history_with_recovery(r_journal, midi_cmd_history)
                if DEBUG:
                    print "tps for history compare:", str(time() - rem)
        #Initialize timestamp diff
        if self.init_timestamp is None:
            self.init_timestamp = timestamp
            #calculate delta midi
            self.midi_out.set_init_time()
        #adding recovery journal to the list
        if self.recovery:
            if marker_j and read_recovery_journal:
                midi_list.extend(midi_from_history)
        #profiter du parcours pour appliquer les timestamps
        for i in range(len(midi_list)):
            midi_list[i][1] = (timestamp - self.init_timestamp + self.midi_out.init_time)
        #Adding the note to the playing buffer
        for i in range(len(midi_list)):
            self.midi_out.midi_cmd_list.put(midi_list[i])
        #switch off witness
        self.receiving_data = 0

    def send_silence(self):
        """
        Sends empty packet to signal a silent period
        """
        recovery_journal = ""
        marker_j = 0
        #Getting recovery
        if self.recovery:
            recovery_journal = self.recovery_journal_system.content
            if recovery_journal != "":
                #Recovery Journal 1 if present
                marker_j = 1
        #Creating empty midicommand filed
        header = MidiCommand().header(0, marker_j, 1, 1, 0)
        if recovery_journal != "":
            chunk = header + recovery_journal
        else:
            chunk = str(0)
        #sending silent packet with recovery journal
        RTPSession.send_empty_packet(self, chunk)
        #RTPControl().send_empty_packet(self.cookie, chunk)

    def send_midi_data(self, data, midi_time, recovery=1, timestamp=1):
        """
        Sends MIDI data through the RTP session.
        """
        if DEBUG:
            print "Sending data", data
        #Witness
        self.sending_data = 1
        #midi Cmd List
        midi_list = data
        #Saving packet
        packet = OldPacket(self.seq, midi_list, 0)
        chunk = ""
        recovery_journal = ""
        if recovery:
            #Recovery Journal (can be empty)
            #TODO customize it for each member of the feed
            if self.recovery_journal_system is not None:
                recovery_journal = self.recovery_journal_system.content
                if recovery_journal == "":
                    recovery = 0
        #Packing All
        #Testing length of midi list ( in nb notes )
        if len(midi_list) < 1:
            return
        #Formating commands for network
        midi_list_formated, length = \
            MidiCommand().encode_midi_commands(midi_list)
        #Creating Header
        header = MidiCommand().header(0, recovery, 0, 0, length)
        #Building Chunk
        chunk = header + midi_list_formated + recovery_journal
        #Timestamp care (TS == temps midi ecouler depuis la creation de rtp)
        ts = midi_time - self.last_midi_time_sent
        self.last_midi_time_sent = midi_time
        #sending data to rtp session
        RTPSession.send_data(self, chunk, ts)
        self.sending_data = 0
        #Updating Recovery Journal
        if self.recovery:
            self.recovery_journal_system.update(packet)

    def update_checkpoint(self, new_checkpoint):
        """
        Function called by RTCP to reduce size of recovery journal.
        """
        if self.recovery:
            self.recovery_journal_system.trim(new_checkpoint)

        self.checkpoint = new_checkpoint

    def drop_connection(self, cookie=0):
        """
        Called by RTP when the connection has been dropped.
        """
        #Rename drop connection
        print "drop connexion for midi session"

    def get_devices(self):
        """
        Lists MIDI devices on this computer.
        @rtype: tuple
        @return: Tuple of list of device info. Input devices first, then output devices.
        """
        #FIXME: return a dict, not a tuple.
        if self.sport > 0:
            devices_in = self.midi_in.get_devices()
        else:
            devices_in = []
        if self.rport > 0:
            devices_out = self.midi_out.get_devices()
        else:
            devices_out = []
        return devices_in, devices_out

    def set_device_in(self, dev):
        """
        Selects the MIDI device to be polled.

        @param dev: The device number to choose.
        @type dev: int
        @rtype: bool
        @return: Success or not
        """
        return self.midi_in.set_device(dev)

    def set_device_out(self, dev):
        """
        Selects the MIDI output device to send data to.

        @param dev: The device number to choose.
        @type dev: int
        @rtype: bool
        @return: Success or not
        """
        return self.midi_out.set_device(dev)
