#Twisted
from twisted.internet import defer
from twisted.internet import reactor

#Midi Streams
from rtpmidi.engines.midi.ringBuffer import myRingBuffer
from rtpmidi.engines.midi.midi_object import SafeKeyboard

import Queue

#Utils
import time
try:
    import pypm
except ImportError:
    from pygame import pypm

#Midi Commands
NOTE_ON = 0x90
NOTE_OFF = 0x80
PRESSURE_CHANGE = 0xA0
CONTROL_CHANGE = 0xB0
PROGRAM_CHANGE = 0xC0
CHANNEL_PRESSURE = 0xD0
PITCH_CHANGE = 0xE0

#Midi Constants
NUM_MIDI_CHANS = 15
MIDI_MAX = 2**7 - 1
INPUT = 0
OUTPUT = 1

VERBOSE = 0

class MidiOut(object):

    def __init__(self, permissif, latency, safe_keyboard=0, verbose=0):
        if verbose:
            global VERBOSE
            VERBOSE = 1

        self.midi_device_list = []
        self.midi_out = None
        self.midi_device = None
        self.latency = latency
        self.tolerance = latency / float(2)

        #time for a round trip packet
        self.delay = 0

        #stat
        self.nb_notes = 0
        self.nb_lost = 0
        self.nb_xrun = 0
        self.start_chrono = 0

        #Struct
        #self.midi_cmd_list = myFIFO()
        self.midi_cmd_list = Queue.Queue(0)
        self.playing_buffer = myRingBuffer()

        #flag
        self.is_listening = 0
        self.publish_flag = False
        self.start_time = 0

                #checking
        self.keyboard =  [False for i in range(127)]

                #Mode
        self.permissif = permissif

        #Checking non wanted artefact
        self.safe_k = 0
        if safe_keyboard:
            self.safe_keyboard = SafeKeyboard()
            self.safe_k = 1

            if VERBOSE:
                print "  SafeKeyboard is running for Midi Out"


    def start(self):
        """Start publishing notes
        """
        if not self.midi_out is None:
            #self.send_note_off()
            self.publish_flag = True
            reactor.callInThread(self.publish_midi_notes)
            if VERBOSE:
                print "OUTPUT: Start publish notes"

            return 1

        else:
            if VERBOSE:
                print "OUTPUT: Can not start publish without a midi device set"

            return 0


    def get_midi_time(self):
        return pypm.Time()

    def stop(self):
        """Stop publish
        """
        self.publish_flag = False
        if not self.midi_out is None:
            #Why a midi problem with send note_off
            #(only when closing app ) <- patch it silly man !
            self.send_note_off()

    def set_init_time(self):
        """Sync set the difference between local midi time and
        remote midi time in order to apply it to the notes
        """
        self.init_time = pypm.Time()

    def get_devices(self):
        """list and set midi device
        """
        self.midi_device_list = []
        for loop in range(pypm.CountDevices()):
            interf, name, inp, outp, opened = pypm.GetDeviceInfo(loop)
            if outp == 1:
                self.midi_device_list.append([loop, name, opened])

        return self.midi_device_list


    def set_device(self, device):
        """set output midi device
        """
        #check if device exist
        dev_list = [self.midi_device_list[i][0]
        for i in range(len(self.midi_device_list))]

        if device in dev_list :
            self.midi_device = device

            if self.midi_out is not None :
                del self.midi_out # delete old midi device if present
            # Initializing midi input stream
            self.midi_out = pypm.Output(self.midi_device, 0)
            if VERBOSE:
                line = "  Midi device out: " + str(self.get_device_info()[1])
                print line
            return True

        else:
            print "OUTPUT: Invalid midi device selected"
            print dev_list
        return False


    def get_device_info(self):
        """print info of the current device
        """
        res  = pypm.GetDeviceInfo(self.midi_device)
        return res


    def send_note_off(self):
        """send Note Off all pitches and all channels
        """
        midi_time = pypm.Time()
        #127 note off and 16 channels
        #TODO check problem: portMidi found host error (link to zynadd?)
        for i in range(NUM_MIDI_CHANS):
            for j in range(MIDI_MAX):
                self.midi_out.Write([[[NOTE_OFF + i,j,0],0]])

#Permisive Mode => joue toutes les notes meme si en retard de qq
#milisecond en affichant
#un erreur style xrun dans le fichier de log

    def play_midi_note(self):
        """PlayMidi Note
           Separate midi infos to choose the good function for
           the good action
        """
        #getting time
        midi_time = pypm.Time()

        #getting notes
        midi_notes = self.playing_buffer.get_data(midi_time - self.latency,
                          self.tolerance)

        self.nb_notes += len(midi_notes)

        if self.safe_k:
            midi_notes = self.safe_keyboard.check(midi_notes)

            if self.permissif :
                #Building list of lates notes in order to log it
                new_list = [midi_notes[i][1]
                for i in range(len(midi_notes))
                if (midi_time > (midi_notes[i][1] + self.latency))]

                if (len(new_list) > 0) :
                    self.nb_xrun += 1

            if VERBOSE:
                line = "OUTPUT: time=" + str(midi_time)
                line += "ms  can't play in time , "
                line += str(len(midi_notes))
                line += " notes - late of "
                calc = ( midi_time - ( self.latency + new_list[0] ))
                line += str(calc) + " ms"
                print line

            note_filtered = midi_notes

        else:
        # filter note off program change for notes that are late
        # if mode non permissif is on skip late notes except
        # note off, notes with velocitiy 0 or program change
            note_filtered = [midi_notes[i] for i in range(len(midi_notes))
            if midi_notes[i][1] + self.latency >= midi_time
            or ( midi_notes[i][0][0] == PROGRAM_CHANGE
                 or midi_notes[i][0][2] == 0
                 or midi_notes[i][0][0] == NOTE_OFF)]

            if (len(note_filtered) < len(midi_notes)):
                if VERBOSE:
                    line = "OUTPUT: time=" + str(pypm.Time())
                    line += "ms can't play in time,  "
                    line += str(len(midi_notes) - len(note_filtered))
                    line += " note(s) skipped, late of: "
                    calc = ( midi_time - ( self.latency + midi_notes[0][1] ))
                    line += str(calc) + " ms"
                    print line

        #Playing note on the midi device
        self.midi_out.Write(midi_notes)

    def publish_midi_notes(self):
        """Polling function for midi out"""
        def_p = defer.Deferred()
    # put in local scope to improve performance
        midi_cmd_list = self.midi_cmd_list
        play_midi_note = self.play_midi_note

        while self.publish_flag :
            """ if there are notes in the shared buffer
            Put the in the playing buffer """
            while True:
                try:
                    cur_data = midi_cmd_list.get_nowait()
                    if VERBOSE:
                        print cur_data
                    self.playing_buffer.put(cur_data)
                except Queue.Empty:
                    break

            if self.playing_buffer.len() > 0:
                current_time = pypm.Time()
                #if the first is in time
                #12 correspond to the polling interval on the
                #test machine and the jitter of thread
                #switching ( to test on others computers with
                #diff set up)
                #The problem is that scheduler taking time to
                #switch between process
                if ((self.playing_buffer.buffer[0][1] + self.latency - self.tolerance) <= current_time):
                    reactor.callInThread(play_midi_note)
                    #time.sleep(0.001)  # this probably used to be the sleep below

            # don't hog the cpu
            time.sleep(0.001)


        return def_p


    def __del__(self):
            self.terminate = 1
