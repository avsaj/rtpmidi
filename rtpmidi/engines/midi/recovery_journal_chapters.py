#utils
from struct import pack
from struct import unpack

def timestamp_compare(x, y):
    if x[1]>y[1]:
        return 1
    elif x[1]==y[1]:
        return 0
    else: # x[1]<y[1]
        return -1

def reverse_timestamp(x, y):
    return y[1]-x[1]

class Note(object):

    def note_on(self, note_num, velocity, recommand=1, marker_s=0):
        """ A.6.3 rfc 4695
        0                   1
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |S|   NOTENUM   |Y|  VELOCITY   |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        """

        #S
        marker_s = marker_s << 7
        #NOTENUM (unique in the chapter) 0->127

        first = marker_s | note_num

        #Y bit of recommandation to play 1 or to skip 0
        marker_y = recommand << 7

        #Velocity 1->100 ( velocity is never 0
        #or the note is coded as NoteOff bitfields

        second = marker_y | velocity

        return pack('!BB', first, second)

    def parse_note_on(self, note):
        first, second = unpack('!BB', note)
        marker_s = first >> 7
        note_num = first&127

        marker_y = second >> 7
        velocity = second&127
        return (marker_s, note_num, marker_y, velocity)

    def note_off(self, notes, low, high):
        """OFFBITS of 1 octet, each OFFBITS code NoteOff informations for 8
        consecutive MIDI
        note number based on HIGH and LOW for the correspondance with note
        number"""
        #trick to encode in a simple way
        for i in range(len(notes)):
            notes[i] += 1
        #getting number of offbits
        nb_offbits = high - low + 1
        pack_algo = '!'

        #determine render form
        for i in range(nb_offbits):
            pack_algo += 'B'

        #writting offbits
        offbits_l = []

        for i in range(len(notes)):
            #decallage pour chaque bit
            decallage =  8 - notes[i]%8
            decallage = decallage % 8

            #Calcul de l'emplacement
            emplacement = notes[i] - (low * 8) - 1
            emplacement = emplacement /8

            try:
                #Try the emplacement
                _res = offbits_l[emplacement]
            except IndexError:
                while len(offbits_l) < emplacement:
                    offbits_l.append(0)

                offbits_l.append(1<<decallage)
            else:
                offbits_l[emplacement] |= 1<<decallage


        p = pack(pack_algo, *offbits_l)
        return p

    def parse_note_off(self, notes, low, high):
        note_l = []

        nb = high - low + 1
        unpack_algo = '!'

        #nb octets where note off are coded
        for i in range(nb):
            unpack_algo += 'B'

        #unpacking
        offbits = unpack(unpack_algo, notes)
        #for each offbits getting note off coded
        for i in range(len(offbits)):
            o_b = offbits[i]
            j = 7
            while j >= 0:
                #MSB coded the lowest pitch
                if (o_b&(2**j) and 1 or 0) == 1 :
                    #Note Off present
                    note = 8 - j + i*8
                    note = note + (low*8)
                    #notes -1 to compense +1 in creation
                    note_l.append([128, note-1, 100])
                j -= 1

        return note_l


##
#Chapters
##
class Chapter(object):
    def __init__(self):
        self.content = ""
        self.highest = 0

    def update(self, new_data):
        raise NotImplementedError

    def trim(self, new_checkpoint):
        raise NotImplementedError


class ChapterP(Chapter):
    """
    0                   1                   2
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |S|   PROGRAM   |B|   BANK-MSB  |X|  BANK-LSB   |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

    Figure A.2.1 -- Chapter P format
    """

    def __init__(self):
        #List of programs
        #((prog_val, bank_msb, bank_lsb), packet_num)
        Chapter.__init__(self)
        self.prog = ((0, 0, 0), 0)
        self.marker_x = 0
        self.marker_b = 0

    def update(self, programs):
        #only prog
        if len(programs) == 1:
            val = programs[0][0][1]
            seq = programs[0][1]

            self.prog = ((val, 0, 0), seq)

            #Update content and highest
            self.update_highest()
            self.build()

        else:
        #msb lsb thing
            msb = 0
            lsb = 0
            for i in range(len(programs)):
                if (programs[i][0][0]>>4)==12:
                    program = programs[i][0][1]
                elif (programs[i][0][0]>>4)==11:
                    if programs[i][0][1] == 0:
                        self.marker_b = 1
                        msb = programs[i][0][2]
                    elif programs[i][0][1] == 32:
                        lsb = programs[i][0][2]
                elif programs[i][0][0]==0 and programs[i][0][1]==0 \
                        and programs[i][0][2]==0 and programs[i][1]==0:
                    self.marker_x = 1

            seq = programs[0][1]
            self.prog = ((program, msb, lsb), seq)

            #Update content and highest
            self.update_highest()
            self.build()

    def trim(self, checkpoint):
        if self.highest <= checkpoint:
            self.highest = 0
            self.content = ""
            self.prog = ((0, 0, 0), 0)

            #Update content and highest
            self.update_highest()
            self.build()

    def build(self):
        program = self.prog[0][0]
        bank_msb = self.prog[0][1]
        bank_lsb = self.prog[0][2]

        if program==0 and bank_msb==0 and bank_lsb==0:
            self.content = ""

        else:
            marker_s = 1 << 7

            #Program max 127
            first = marker_s | program

            #This field are only set if an 0Xb appear before the program
            #change for the controller 0
            #( bank_msb = control chang command )
            marker_b = self.marker_b << 7
            #BANK_MSB max 127
            second = marker_b | bank_msb

            marker_x = self.marker_x << 7

            #BANK_LSB max 127
            third = marker_x | bank_lsb

            self.content = pack('!BBB', first, second, third)

    def parse(self, chapterp):
        first, second, third = unpack('!BBB', chapterp)

        marker_s = first >> 7
        program = first&127

        marker_b = second >> 7
        bank_msb = second&127

        marker_x = third >> 7
        bank_lsb = third&127

        midi_cmd = []

        midi_cmd.append([192, program, 0])
        if marker_b == 1:
            midi_cmd.append([176, 0, bank_msb])
            midi_cmd.append([176, 32, bank_lsb])

        #marker_x is only important if using 0 and 32 in a non standard way.
        return 3, midi_cmd, marker_s, marker_x, marker_b

    def update_highest(self):
        #Getting higest from data list
        if self.prog[0][0]!=0 :
            self.highest = self.prog[1]

        else:
            self.highest = 0


class ChapterC(Chapter):
    """
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 8 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |S|     LEN     |S|   NUMBER    |A|  VALUE/ALT  |S|   NUMBER    |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |A|  VALUE/ALT  |  ....                                         |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

    Figure A.3.1 -- Chapter C format
    """

    def __init__(self):
        self.highest = 0
        self.content = ""
        #COntroller format
        #((number, value), packet_num, encoded)
        self.controllers = []

    def header(self, length, marker_s=0):
        marker_s = marker_s << 7
        #L max 127

        return pack('!B', marker_s | length)

    def parse_header(self, header):
        header = unpack('!B', header)
        marker_s = header[0] >> 7
        length = header[0]&127
        return marker_s, length

    def update(self, controllers):

        for i in range(len(controllers)):
            controllers_ind = [ controller[0][0] for controller
                                in self.controllers ]
            #tmp
            pitch = controllers[i][0][1]
            vel = controllers[i][0][2]
            seq = controllers[i][1]

            if not pitch in controllers_ind:
                encoded = self.create_log_c(0, pitch, 0,vel)
                self.controllers.append(((pitch, vel), seq, encoded))

            else:
                ind = controllers_ind.index(pitch)
                encoded = self.create_log_c(0, pitch, 0,vel)
                self.controllers[ind] = ((pitch, vel), seq, encoded)

        #Update chapter and content
        self.update_highest()
        self.build()


    def build(self):
        """ChapterC creation from controllers list"""
        length = 0
        self.content = ""

        for controller in self.controllers:
            length += 1
            self.content += controller[2]
        header = self.header( length, 0)
        self.content = header + self.content


    def trim(self, checkpoint):
        if self.highest > 0:
            self.controllers = [controller for controller in self.controllers
                                if controller[1] > checkpoint]

            #Update chapter and content
            self.update_highest()
            self.build()

    def create_log_c(self, marker_s, number, marker_a, value):
        marker_s = marker_s << 7
        first = marker_s | number

        #TODO marker maagement (for toggle / pedal controllers)
        marker_a = marker_a << 7
        second = marker_a | value

        return pack('!BB', first, second)

    def parse_log_c(self,data):
        first, second = unpack('!BB', data)
        marker_s = first>>7
        number = first&127

        marker_a = second>>7
        value = second&127

        return marker_s, number, marker_a, value

    def parse(self, chapter):
        """Parsing chapterC"""
        marker_s, length = self.parse_header(chapter[:1])
        chap = chapter[1:]
        size = 1 + 2 * length
        midi_cmd = []

        for i in range(length):
            current = self.parse_log_c(chap[2*i:2*i+2])
            #TODO take care marker_s and A
            control_cmd = [176, current[1], current[3]]
            midi_cmd.append(control_cmd)

        return size, midi_cmd, marker_s

    def update_highest(self):
        #Getting higest from data list
        if len(self.controllers) > 0:
            decorate = [data[1] for data in self.controllers]
            decorate.sort(reverse=True)
            self.highest = decorate[0]

        else:
            self.highest = 0


class ChapterW(Chapter):
    """
    0                   1
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |S|     FIRST   |R|    SECOND   |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

    Figure A.5.1 -- Chapter W format
    Pitch Wheel information / midi => 0xE
    """

    def __init__(self):
        Chapter.__init__(self)
        #Format (wheel, seqnum)
        self.data_list = ((0, 0), (0, 0))

    def trim(self, checkpoint):
        if self.highest <= checkpoint:
            self.content = ""
            self.highest = 0
            self.data_list = ((0, 0), (0, 0))

        else:
            if self.data_list[0][1] <= checkpoint:
                self.data_list = ((0,0), \
                                      (self.data_list[1][0], self.data_list[1][1]))

            if self.data_list[1][1] <= checkpoint:
                self.data_list = ((self.data_list[0][0], self.data_list[0][1]), \
                                      (0, 0))
        #Update Highest
        self.update_highest()
        self.build()

    def update(self, wheels):
        #S inform that the recovery for packet I coded information
        #from packet I-1
        i = 0
        for wheel in wheels:
            #First wheel (TODO commen differencier wheel 1 / 2
            if i == 0:
                self.data_list = ((wheel[0][2], wheel[1]), \
                                      (self.data_list[1][0], self.data_list[1][1]))

            else:
                self.data_list = ((self.data_list[0][0], self.data_list[0][1]), \
                                      (wheel[0][2], wheel[1]))

            i += 1

        #Updating highest and content
        self.update_highest()
        self.build()

    def build(self):
        wheel_1 = self.data_list[0][0]
        if wheel_1 != 0:
            wheel_2 = self.data_list[1][0]
            single = 1
            mark_s = single << 7
            first = mark_s | wheel_1
        #R is for futur use Receiver must ignore it
            mark_r = 0 << 7
            second = mark_r | wheel_2
            self.content = pack('!BB', first, second)

        else:
            self.content = ""

    def parse(self, chapter_w):
        first, second = unpack('!BB', chapter_w[:2])
        midi_cmd = []
        mark_s = first&128 and 1 or 0
        wheel_1 = first&127
        wheel_2 = second&127

        #TODO verfi format
        midi_cmd.append( [224, 0,  wheel_1])
        midi_cmd.append( [224, 0,  wheel_2])

        return 2, midi_cmd, mark_s


    def update_highest(self):
        #Getting higest from data list
        if self.data_list[0][0]!=0 :
            if self.data_list[1][0]!=0:
                if self.data_list[0][1] >= self.data_list[1][1]:
                    self.highest = self.data_list[0][1]

                else:
                    self.highest = self.data_list[1][1]

            else:
                self.highest = self.data_list[0][1]

        else:
            self.highest = 0


class ChapterN(Chapter):
    def __init__(self):
        Chapter.__init__(self)
        #Keep up to date??
        self.state = 0
        #For header
        self.low = 0
        self.high = 0
        self.note_off_presence = 0

        #List of notes
        #((note_val, note_vel), packet_num, encoded)
        self.note_on = []
        #(note_val, packet_num)
        self.note_off = []

        self.note = Note()


    def header(self):
        """A.6.1 rfc 4695
        0                   1
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        |B|     LEN     |  LOW  | HIGH  |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

        Note log list obey the oldest-first ordering
        """
        length = len(self.note_on)
        low = self.low
        high = self.high

        #B is set to 0 if chapter contain NoteOff else 1
        #( si B == 0 , S upper level must be set to 0 )
        marker_b = 0 << 7
        #LEN number of notelog in the list jusque 127 notes

        first = marker_b | length
        #LOW et high sont la pour indique le nombre d'OFFBITS
        #if LOW <= HIGH there are HIGH - LOW + 1 OFFBITS
        #HIGH = biggest_notenum_of_noteoff_present
        #LOW = lowest_notenum_of_noteoff_present
        low = low << 4

        second = low | high
        if first > 255 or first < 0:
            print " problem with first " + str(first) + " length: " \
                + str(length)
        return pack('!BB', first, second)

    def parse_header(self, header):
        first, second = unpack('!BB', header)
        marker_b = first&128 and 1 or 0
        marker_l = first&127

        low = (second&240) >> 4
        high = second&15
        return (marker_b, marker_l, low, high)

    def eval_low_high(self):
        """
        Evaluate low and high marker for note off
        """
        #Getting list of noteOff => lowwest and highest noteOff
        note_off = [note[0] for note in self.note_off]

        #setting low and high for offbits
        if len(note_off) > 0:
            note_off.sort()

            #set high(+1 for the trick)
            if (note_off[-1]+1) % 8 == 0 :
                self.high = (note_off[-1]) / 8
            else:
                self.high = (note_off[-1]+1) / 8

            #set low
            self.low = note_off[0] / 8

        else:
            self.low = 0
            self.high = 0

    def update(self, notes):
        #Index of notes off
        note_off = [ note[0] for note in self.note_off ]

        #Splitting notes
        new_note_on =  [ (note[0][1], note) for note in notes
                         if note[0][0]&240 == 144
                         and note[0][2] > 0 ]

        new_note_off = [ (note[0][1], note[1]) for note in notes
                         if note[0][0]&240 == 128
                         or note[0][2] == 0 ]

        new_note_off_ind = [ note[0] for note in new_note_off ]

        #Checking notes (note off exclusion)
        new_valid_note_on =  [ note[1] for note in new_note_on
                               if not note[0] in note_off and
                               not note[0] in new_note_off_ind]

        #Updating note on of chapter based on new note off
        self.note_on = [ note for note in self.note_on
                         if not note[0][0] in note_off and
                         not note[0][0] in new_note_off_ind ]

        #Adding note on
        for note_on in new_valid_note_on:
            #Index of notes on
            note_on_l = [ note[0][0] for note in self.note_on ]

            #tmp
            note_num = note_on[0][1]
            velocity = note_on[0][2]
            #cmd = note_on[0][0]&240
            seq = note_on[1]

            if note_num in note_on_l:
                #Replacing Note
                ind = note_on_l.index(note_num)
                encoded = self.note.note_on(note_num, velocity)
                self.note_on[ind] = ((note_num, velocity), seq, encoded)
                self.state = 1

            else:
                #Add Newone
                encoded = self.note.note_on(note_num, velocity)
                self.note_on.append(((note_num, velocity), seq, encoded))
                self.state = 1

        #Adding note_off
        for note_off in new_note_off:
            note_off_l = [ note[0] for note in self.note_off ]
            if not note_off[0] in note_off_l:
                #Add note off

                self.note_off.append((note_off[0], note_off[1]))
                self.state = 1

            else:
                #Updating seq num
                ind = note_off_l.index(note_off[0])
                self.note_off[ind] = (note_off[0], note_off[1])
                self.state = 1


        #Update Highest
        self.update_highest()

        #Rebuilding the packet
        self.build()

    def trim(self, checkpoint):
        if self.highest > 0:
            self.note_on = [note for note in self.note_on if note[1] > checkpoint]
            self.note_off = [note for note in self.note_off if note[1] > checkpoint]
            self.state = 1

            #Update Highest
            self.update_highest()

            #Rebuilding content
            self.build()


    def build(self):
        """
        format waited for midiCmd :
        list of [[Event, Note, Velocity], Time]
        """
        chapter_note_on = ""
        chapter_note_off = ""
        note_off_presence = 0
	self.eval_low_high()

            #Note off part
        if len(self.note_off) > 0:
            note_off = [ note[0] for note in self.note_off ]
            chapter_note_off = self.note.note_off(note_off, self.low, self.high)
            note_off_presence = 1

        note_on = [ note[2] for note in self.note_on ]
        chapter_note_on = ''.join(note_on)

        #complete chapterN
        chapter_n = chapter_note_on + chapter_note_off
        #real_len = len(self.note_on) * 2 + ( self.high - self.low + 1 )

        #building chapter
        header = self.header()
        chapter_n = header + chapter_n

        #Save res
        self.content = chapter_n
        self.note_off_presence = note_off_presence

    def parse(self, chapter):
        note = Note()
        extract_header = chapter[:2]
        size = 2

        header = self.parse_header(extract_header)
        nb_note_on = header[1]
        size += 2 * nb_note_on

	#print "total len ???? ", str(2+2*nb_note_on+)
        #len in header of the chapter
        real_len = nb_note_on * 2 + ( header[3] - header[2] + 1 )

        #chapter
        extract_chapter = chapter[2:2+real_len+1]

        #Getting note On
        note_list = []

        for i in range(nb_note_on):
            note_n =  note.parse_note_on(extract_chapter[2*i:2+(i*2)])
            note_list.append([144, note_n[1], note_n[3]])

        #if there is note off
        if header[3] - header[2] >= 0 and header[3] != 0:
            size += header[3] - header[2] + 1
            note_off = note.parse_note_off(extract_chapter[nb_note_on*2:],
                                           header[2], header[3])
        else:
            note_off = []

        return size, note_list + note_off


    def update_highest(self):
        #Getting higest from data list
        data_list = self.note_on + self.note_off
        if len(data_list) > 0:
            decorate = [data[1] for data in data_list]
            decorate.sort(reverse=True)
            self.highest = decorate[0]

        else:
            self.highest = 0

class ChapterE(object):
    """Chapter E (note extras (double notes, ...))"""
    pass

class ChapterT(Chapter):
    """Chapter T (After Touch)
    0
    0 1 2 3 4 5 6 7
    +-+-+-+-+-+-+-+-+
    |S|   PRESSURE  |
    +-+-+-+-+-+-+-+-+
    Figure A.8.1 -- Chapter T format

    """

    def __init__(self):
        Chapter.__init__(self)

    def update(self, after):
        after = after[0]
        marker_s = 1
        pressure = after[0][1]
        self.highest = after[1]
        marker_s = marker_s << 7
        chap_t = marker_s | pressure

        res = pack('!B', chap_t)
        self.content = res

    def trim(self, checkpoint):
        if self.highest <= checkpoint:
            self.content = ""
            self.highest = 0

    def parse(self, chap_t):
        size = 1
        midi_cmd = []
        chap_t_parsed = unpack('!B', chap_t[0])
        #marker_s = chap_t_parsed[0] >> 7
        pressure = chap_t_parsed[0]&127
        midi_cmd.append([208, pressure, 0])
        return  size, midi_cmd

class ChapterA(Chapter):
    """Chapter A (Poly After Touch)
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 8 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |S|    LEN      |S|   NOTENUM   |X|  PRESSURE   |S|   NOTENUM   |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |X|  PRESSURE   |  ....                                         |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

    Figure A.9.1 -- Chapter A format
    """

    def __init__(self):
        Chapter.__init__(self)
        #Format ((pitch, velocity), seq_num, encoded)
        self.data_list = []

    def header(self, marker_s, length):
        """Header Creation for Chapter A
        Marker S is set to when encoding packetNum - 1 ???
        """

        #Marker S for packet - 1 encoding
        marker_s = marker_s << 7
        length -= 1
        chap_a = marker_s | length
        header = pack ('!B', chap_a)
        return header

    def parse_header(self, header):
        header_parsed = unpack('!B', header)
        marker_s = header_parsed[0] >> 7
        length = header_parsed[0]&127
        length += 1
        return marker_s, length

    def create_log_a(self, marker_s, notenum, marker_x, pressure):
        """Log Creation for Chapter A
        Marker X == 1, if the command coded by the log appears before one of the
        following commands in the session history: MIDI Control Change
        numbers 123-127 (numbers with All Notes Off semantics) or 120 (All
        Sound Off).
        """

        marker_s = marker_s << 7
        first = marker_s | notenum
        marker_x = marker_x << 7
        second = marker_x | pressure

        log_a = pack ('!BB', first, second)
        return log_a


    def parse_log_a(self, log_a):
        first, second = unpack('!BB', log_a)
        marker_s = first >> 7
        notenum = first&127
        marker_x = second >> 7
        pressure = second&127
        return marker_s, notenum, marker_x, pressure

    def update(self, midi_cmd):
        """Chapter A creation
        """
        #timestamp = 1 if marker X
        #timestamp = 1 << 1 marker S
        #chapter_p = ""
        known_pitch = [data[0][0] for data in self.data_list]

        for i in range(len(midi_cmd)):
            marker_x = 0
            marker_s = 0
            if (midi_cmd[i][1]>>1):
                marker_s = 1

            if (midi_cmd[i][1]&1):
                marker_x = 1

            #Encoding
            encoded = self.create_log_a(marker_s, midi_cmd[i][0][1], marker_x,
                                        midi_cmd[i][0][2])

            #Test existance
            if not midi_cmd[i][0][1] in known_pitch:
                #Adding
                self.data_list.append(((midi_cmd[i][0][1], midi_cmd[i][0][2],
                                        marker_s, marker_x), midi_cmd[i][1], encoded))

                known_pitch = [data[0][0] for data in self.data_list]

            else:
                #Replace
                ind = known_pitch.index(midi_cmd[i][0][1])
                self.data_list[ind] = ((midi_cmd[i][0][1], midi_cmd[i][0][2],
                                        marker_s, marker_x), midi_cmd[i][1], encoded)

                known_pitch = [data[0][0] for data in self.data_list]

        self.update_highest()
        self.build()

    def build(self):
        self.content = ""
        for data in self.data_list:
            self.content += data[2]

        marker_s = 1
        header = self.header(marker_s, len(self.data_list))
        self.content = header + self.content

    def trim(self, checkpoint):
        self.data_list =  [data for data in self.data_list if data[1] > checkpoint]

        if len(self.data_list) > 0:
            self.update_highest()
            self.build()

        else:
            self.content = ""
            self.highest = 0


    def update_highest(self):
        if len(self.data_list) > 0:
            decorate = [data[1] for data in self.data_list ]
            decorate.sort(reverse=True)
            self.highest = decorate[1]

        else:
            self.highest = 0

    def parse(self, chapter_a):
        """Parse function for Chapter A"""
        marker_s, length = self.parse_header(chapter_a[:1])
        midi_cmd = []
        size = 1
        chapter_a_parsed = chapter_a[1:2*length+1]
        for i in range(length):
            #TODO take care of marker X and Marker S
            marker_s_tmp, notenum, marker_x, pressure \
                = self.parse_log_a(chapter_a_parsed[2*i:2*i+2])

            midi_cmd.append( [160, notenum, pressure])
            size += 2
        return size, marker_s, midi_cmd



