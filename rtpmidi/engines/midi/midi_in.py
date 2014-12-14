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
MIDI input device manager.
"""
from twisted.internet import reactor
from twisted.internet import task
from twisted.internet import defer
import time
try:
    import pypm
except ImportError:
    from pygame import pypm

# FIXME: what are those two vars?
INPUT = 0
OUTPUT = 1

class MidiIn(object):
    """
    Midi device input.

    Manages a single MIDI input (source) device.
    Can list all input devices.
    """
    def __init__(self, client, verbose=0):
        self.verbose = verbose
        #Init var
        self.midi_device_list = []
        self.midi_device = None
        self.midi_in = None
        #setting looping task
        self.releaser = task.LoopingCall(self._get_input)
        #Launching RTP Client to call after midi time start in order to sync TS
        self.client = client
        #stats
        self.nbNotes = 0
        self.fps_note = 0
        #flag ( 1 == syncronyse with remote peer )
        self.sync = 0
        self.end_flag = True
        #check activity
        self.last_activity = 0
        self.in_activity = False
        #value to set
        #in s (increase it when note frequency is high in order to reduce packet number)
        self.polling_interval = 0.015
        #in ms
        #Time out must be > to polling
        self.time_out = 5
        #Init time is for timestamp in RTP
        self.init_time = pypm.Time()

    def start(self):
        """
        Starts polling the selected device.
        One must first select a device !
        @rtype: bool
        Returns success.
        """
        if self.end_flag :
            if self.midi_in is not None:
                self.end_flag = False
                reactor.callInThread(self._polling)
                return True
            else:
                line = "INPUT: you have to set a midi device before start "
                line += "sending midi data"
                print line
                return False
        else:
            line = "INPUT: already sending midi data"
            return False

    def stop(self):
        """
        Stops polling the selected device.
        """
        if not self.end_flag:
            self.end_flag = True

    def _polling(self):
        """
        Starts a never ending loop in a python thread.
        @rtype: Deferred
        """
        #need by twisted to stop properly the thread
        d = defer.Deferred()
        #setting new scopes
        last_poll = self.last_activity
        midi_in = self.midi_in
        in_activity = self.in_activity
        while not self.end_flag:
            # hasattr is workaround for weird race condition on stop whereby midi_in is an int
            if hasattr(midi_in, 'Poll') and midi_in.Poll():
                last_poll = time.time() * 1000
                reactor.callInThread(self._get_input)
                in_activity = True
            if in_activity and ((time.time() * 1000) - last_poll >= self.time_out):
                #send silent packet after 3ms of inactivity
                self.client.send_silence()
                in_activity = False
            time.sleep(self.polling_interval)
        return d

    def get_devices(self):
        """
        Returns the list of MIDI input devices on this computer.
        @rtype: list
        """
        self.midi_device_list = []
        for loop in range(pypm.CountDevices()):
            interf, name, inp, outp, opened = pypm.GetDeviceInfo(loop)
            if inp == 1:
                self.midi_device_list.append([loop,name, opened])
        return self.midi_device_list

    def get_device_info(self):
        """
        Returns info about the currently selected device
        """
        return pypm.GetDeviceInfo(self.midi_device)

    def set_device(self, device):
        """
        Selects the MIDI device to be polled.

        @param device: The device number to choose.
        @type device: int
        @rtype: bool
        @return: Success or not
        """
        #check if device exist
        dev_list = [self.midi_device_list[i][0] for i in range(len(self.midi_device_list))]
        if device in dev_list: # if the number is not in list of input devices
            self.midi_device = device
            if self.midi_in is not None:
                #delete old midi device if present
                del self.midi_in
            #Initializing midi input stream
            self.midi_in = pypm.Input(self.midi_device)
            if self.verbose:
                line = "  Midi device in: " + str(self.get_device_info()[1])
                print line
            return True
        else:
            print "INPUT: Invalid midi device selected"
            print dev_list
            return False

    def _get_input(self):
        """
        Get input from selected device
        """
        current_time = pypm.Time()
        #Reading Midi Input
        midi_data = self.midi_in.Read(1024)
        if self.verbose:
            print midi_data
        if len(midi_data) > 0:
            reactor.callFromThread(self.client.send_midi_data, midi_data, current_time)

    def __del__(self):
        #deleting objects
        del self.client
        del self.midi_in
