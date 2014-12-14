from struct import pack
from struct import unpack

TWO_TO_THE_32ND = 2L<<32

class MidiCommand(object):
	"""
        Figure 2 shows the format of the MIDI command section.
        rfc 4695

        0                   1                   2                 3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 0
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |B|J|Z|P|LEN... |  MIDI list ...                          |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        """
	def __init__(self):
		pass

	def header(self, marker_b, recovery, timestamp, phantom, length):
		"""Create header for MIDI Command part"""
		#MIDI PAYLOAD
		marker_b = 0 << 7

                #Recovery Journal 1 if present
		marker_j = recovery << 6

                #if Z = 1 of packet are play with the same timestamp
                #( no delay between notes => no delta field)
		marker_z = timestamp << 5

                #Phantom
		marker_p = phantom << 4

		#Check length (max 255)

		first = marker_b | marker_j | marker_z | marker_p | length
		header = pack('!B',first)

		return header

	def parse_header(self, header_to_parse):
		"""Parsing header for MIDI Command part"""
		#Heading
		header = unpack('!B', header_to_parse)

                #Parsing RTP MIDI Header
		marker_b = (header[0] & 128) and 1 or 0
		marker_j = (header[0] & 64) and 1 or 0
		marker_z =  (header[0] & 32) and 1 or 0
		marker_p =  (header[0] & 16) and 1 or 0
		length = header[0] & 15

		return marker_b, marker_j, marker_z, marker_p, length


	def encode_midi_commands(self, commands):
		"""Take a list of cmd in argument, and provide a midi command list
		format for network

		Each element:
		| EVENT | NOTE | VELOCITY |

		Notes must be chronologically ordered oldest first

		+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
		|Delta T 4 octets long, 0 octets if Z = 1   |
		+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
		| MIDI Command 0   (3 octets long)          |
		+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
		"""

		if len(commands) > 0:
                        #Ordering notes
			#Order history by channels midi command and pitch
			decorate =  [((x[0][0]&15), (x[0][0]&240), x[0][1], x)
				     for x in commands]
			decorate.sort()
			commands = [x[3] for x in decorate]
			#commands = bubble_sort(commands,len(commands))
			notes = ""
			nb_notes = 0
			time_calc =  [x[1] for x in commands]
			time_calc.sort()
			time_ref = time_calc[0]

                        #Formating the list
			for i in range(len(commands)):
                                #recup time
				timestamp = commands[i][1] - time_ref

				if timestamp >= TWO_TO_THE_32ND:
					timestamp = timestamp - TWO_TO_THE_32ND

                                #print timestamp
				event = commands[i][0][0]
				note = commands[i][0][1]
				velocity = commands[i][0][2]

				tmp = pack('!BBB', event , note , velocity)
				tmp = pack('!I', timestamp) + tmp

				notes += tmp

				nb_notes += 1

			return notes, nb_notes
		else:
			return "", 0


	def decode_midi_commands(self, bytes, nb_notes):
		"""decode a note list from bytes formated for network"""
                #iterator
		j = 0
		midi_list = []
		for i in range(nb_notes):
			cmd = bytes[j:j+7]

			timestamp = unpack('!I', cmd[0:4])
			event, note, velocity = unpack('!BBB', cmd[4:])
			timestamp = timestamp[0]

                        #applique modif ts
			midi_list.append([[event, note, velocity],timestamp])
			j += 7

		return midi_list


class MidiNote(object): #TODO: Maybe we could convert this object to a tuple to improve the performance

	def __init__(self, time, event, note, velocity, what=0):
		self.time = time
		self.event = event
		self.note = note
		self.velocity = velocity


class OldPacket(object):

    def __init__(self, seqNo, packet, marker=0):
        self.seqNo = seqNo
        self.packet = packet
        self.marker = marker



class SafeKeyboard(object):
    """This class is needed in the case where
    some note are invert (with pypm, sometime, when notes are played very
    fast i.e more than two notes in a ms the output of midi_in.Read() invert note off
    and note on. The result of that is an indefinite artefact midi_out side.
    """
    def __init__(self):
        self.keyboard =  []

        #Building a map of all notes
        for i in range(16):
            note_list =  [False for i in range(127)]
            self.keyboard.append(note_list)

    def note_index(self, chan, pitch, on, ind, midi_list):
        """Getting the nearest note for a given pitch and a given pitch
        ex : note_index(120, 1, 10, cmd_list)
        research a note on for 120 pitch near index 10 in cmd_list"""
        ind_list = []
        value = 0
        res = -1

        if on == 1:
            value = 144
        else:
            value = 128

        #getting index of pitch (possibilit de stopper si trouver)
        for i in range(ind, len(midi_list)):
            if (midi_list[i][0][1] == pitch and midi_list[i][0][0]&240 == value
		and  midi_list[i][0][0]&15 == chan):
                res = i
                break

        return res

        #Calcul the distance between note to check and values retreive
        #ind_list_calc = [[ind_list[i], ind_list[i] - ind] for i in range(len(ind_list))
        #if (ind_list[i] - ind) > 0]
        #for i in range(len(ind_list_calc)):
        #    if ind_list_calc[i][1] == 1:
        #        return ind_list_calc[i][0]


    def check(self, midi_notes):
	"""Verify that note off and note on alternate
	in a safe way (no double note off)
        """

        #Checking if notes are playing
        i = 0
        j = 0
        long = len(midi_notes)
        while j < long:
            #Test for note on
            if midi_notes[i][0][0]&240 == 144:
                #getting channel
                chan = midi_notes[i][0][0]&15
                #if note is already playing (reorder neededor sup)
                if self.keyboard[chan][midi_notes[i][0][1]]:

                    #Getting nearest good note
                    ind_to_swap = self.note_index(chan, midi_notes[i][0][1], 0, i, midi_notes)

                    #if the note paire is found after it
                    if ind_to_swap != -1:
                        if (midi_notes[i][1] <= midi_notes[ind_to_swap][1] + 1
			    and midi_notes[i][1] >= midi_notes[ind_to_swap][1] - 1):
                            tmp = midi_notes[i]
                            midi_notes[i] = midi_notes[ind_to_swap]
                            midi_notes[ind_to_swap] = tmp

                            self.keyboard[chan][midi_notes[i][0][1]] = False
                            i += 1

                        else:
                            #else we delete it
                            #can't swap with different timestamp
                            del  midi_notes[i]

                    else:
                        #else we delete it
                        del  midi_notes[i]

                else:
                    self.keyboard[chan][midi_notes[i][0][1]] = True
                    i += 1


            elif midi_notes[i][0][0]&240 == 128:
                #getting channel
                chan = midi_notes[i][0][0]&15

                #Getting nearest good note
                if not self.keyboard[chan][midi_notes[i][0][1]]:
                    ind_to_swap = self.note_index(chan, midi_notes[i][0][1], 1, i, midi_notes)
                    #if the note paire is found
                    if ind_to_swap != -1:
                        if (midi_notes[i][1] <= midi_notes[ind_to_swap][1] + 1
			    and midi_notes[i][1] >= midi_notes[ind_to_swap][1] - 1):
                            tmp = midi_notes[i]
                            midi_notes[i] = midi_notes[ind_to_swap]
                            midi_notes[ind_to_swap] = tmp
                            self.keyboard[chan][midi_notes[i][0][1]] = True
                            i += 1

                        else:
                            #else we delete it
                            #can't swap with different timestamp
                            del  midi_notes[i]
                    else:
                        #else we delete i
                        del  midi_notes[i]
                else:
                    self.keyboard[chan][midi_notes[i][0][1]] = False
                    i += 1

            j += 1
        return midi_notes
