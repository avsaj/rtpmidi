#utils
from struct import pack
from struct import unpack
import time

#data
from rtpmidi.engines.midi.midi_object import OldPacket

#Recovery Chapters
from rtpmidi.engines.midi.recovery_journal_chapters import ChapterP
from rtpmidi.engines.midi.recovery_journal_chapters import ChapterC
from rtpmidi.engines.midi.recovery_journal_chapters import ChapterW
from rtpmidi.engines.midi.recovery_journal_chapters import ChapterN
from rtpmidi.engines.midi.recovery_journal_chapters import ChapterT
from rtpmidi.engines.midi.recovery_journal_chapters import ChapterA

HISTORY_SIZE = 1024

def timestamp_compare(x, y):
    if x[1]>y[1]:
        return 1
    elif x[1]==y[1]:
        return 0
    else: # x[1]<y[1]
        return -1

def reverse_timestamp(x, y):
    return y[1]-x[1]

##
#Channel
##
class ChannelJournal(object):
    """
    Figure 9 rfc4695
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |S| CHAN  |H|      LENGTH       |P|C|M|W|N|E|T|A|  Chapters ... |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """

    #Channel Journal
    def __init__(self, chanNum=0, packets={}, standard=0):

        self.chan_num = chanNum

        #Chapters
        self.chapters = {'controllers':[ChapterC(), ""],
                         'programs':[ChapterP(), ""],
                         'p_system': [None, ""],
                         'wheels':[ChapterW(), ""],
                         'notes':[ChapterN(), ""],
                         'extras':[None, ""],
                         'afters':[ChapterT(), ""],
                         'poly_afters':[ChapterA(), ""]}

        self.extras = []
        self.afters = []
        self.poly_afters = []
        self.content = ""
        self.highest = 0
        self.follow_standard = standard

        #Building channel journal with initial data
        if len(packets) > 0:
            self.update(packets)



    def header(self, chan_num, length, marker_p=0, marker_c=0, marker_m=0,
               marker_w=0, marker_n=0, marker_e=0, marker_t=0,
               marker_a=0, marker_s=1, marker_h=0 ):
        """Each channel has its own header"""

        #S==0 means code informations for packet I-1 according that this recovery
        #will be for packet I
        marker_s = marker_s << 15

        #chan = num of the channel.
        chan_num  = chan_num << 11

        #if using enhanced control change (a voir)
        marker_h = marker_h << 10

        #len of the channel journal 10 bits
        #TODO faire un test sur length

        #All in 16 bits
        if length > 1023:
            print "!!! Gerer si lenght of channel > 1024"
            return

        first = marker_s | chan_num | marker_h | length

        #ENcode presence of chapter in recovery journal 8 bits
        #( MUST be 1 or 0 )
        #pour NoteOn NoteOff N
        marker_p = marker_p << 7
        marker_c = marker_c << 6
        marker_m = marker_m << 5
        marker_w = marker_w << 4

        marker_n = marker_n << 3
        marker_e = marker_e << 2
        marker_t = marker_t << 1
        marker_a = marker_a

        second = marker_p | marker_c | marker_m | marker_w | marker_n | \
            marker_e | marker_t | marker_a
        return pack('!HB', first, second)

    def dispatch_data(self, data):
        """Build the channel journal of a given channel,
        based on data passed from create_recovery_journal
        option standard is for some command standardize to
        designate a special command"""
        standard = self.follow_standard

        #Chapters list
        controllers = []
        programs = []
        system_p = []
        wheels = []
        notes = []
        extras = []
        afters = []
        poly_afters = []

        #witness
        special_consideration = 0
        note_off_presence = 0
        bank_msb = (0, 0)
        bank_lsb = (0, 0)
        reset_all = (0, 0)
        omni_on = (0, 0)
        omni_off = (0, 0)
        poly = (0, 0)
        mono = (0, 0)
        #Order by seqNo and timestamps (only getting last notes if doublon)
        #for each seq (beginning with last one (upper priority))

        zap = 0

        seq_nums = data.keys()

        for seq in seq_nums:
            #for each midicmd get note type
            for i in range(len(data[seq])):
                command = data[seq][i][0][0]
                pitch = data[seq][i][0][1]
                velocity = data[seq][i][0][2]
                time = data[seq][i][1]
                data[seq][i][1] = seq

                #Note
                if (command&240 == 128 or
                    command&240 == 144):
                    #if not already in add it
                    if not data[seq][i][0] in notes:
                        notes.append((data[seq][i], seq))
                    else:
                        #replace with a most recent one
                        #deleting old one to conserve order in choice
                        res = notes.index(data[seq][i])
                        del notes[res]
                        notes.append((data[seq][i], seq))

                #program change 0xC (!! si change seulement program change une
                #note 12 sinon (bank + prog change) 2 note 11 (bank) puis
                #une note 12 pour le prog
                elif (command>>4) == 12:
                    if not pitch in programs:
                        #looking for eventual 0xB link to program change
                        if bank_msb != (0, 0):
                            if bank_lsb != (0, 0):
                                #adding lsb
                                programs.append(bank_lsb[0])
                                bank_lsb = (0, 0)
                            #adding msb
                            programs.append(bank_msb[0])

                            if reset_all != (0, 0):
                                if bank_msb[1] < reset_all[1]:
                                    #Passing marker_x to chapter p
                                    programs.append([[0,0,0,0], 0])
                            bank_msb = (0, 0)
                        #adding program
                        programs.append(data[seq][i])


                #controller change 0xB (!! take care of prog+bank change)
                elif (command>>4) == 11:
                    #Checking specials controllers
                    #(if standardized, else will not taking care)

                    if not pitch in controllers:

                        #special commands link to chapterP
                        #TODO review MSB LSB
                        if pitch == 0:
                            bank_msb = (data[seq][i], time)
                        elif pitch == 32:
                            bank_lsb = (data[seq][i], time)
                        elif pitch == 121:
                            #Cas du reset all (possible to forget prec
                            #cmds for controllers, but take care if not standardized)
                            reset_all = (data[seq][i], time)
                        #Mutual exculsive by pair(Off/On and Mono/Poly)
                        elif pitch == 124:
                            #Omni Off
                            omni_off = (data[seq][i], time)
                        elif pitch == 125:
                            #Omni On
                            omni_on = (data[seq][i], time)
                        elif pitch == 126:
                            #Mono
                            mono = (data[seq][i], time)
                        elif pitch == 127:
                            #Poly
                            poly = (data[seq][i], time)
                        else:
                            controllers.append((data[seq][i], time))


                #wheel action 0xE
                elif (command>>4) == 14:
                    wheels_action = [ wheel[0][0][1] for wheel in wheels ]
                    if not pitch in wheels_action:
                        wheels.append((data[seq][i], time))

                    else:
                        res = wheels_action.index(pitch)
                        wheels[res] = (data[seq][i], time)

                #channel afther touch 0xD
                elif (command>>4) == 13:
                    afters_action = [ after[0][0][1] for after in afters ]
                    if not pitch in afters_action:
                        afters.append((data[seq][i], time))

                    else:
                        res = afters_action.index(pitch)
                        afters[res] = (data[seq][i], time)

                #note afters 0xA
                elif (command>>4) == 10:
                    poly_afters_action = [ poly_after[0][0][1]
                                           for poly_after in poly_afters ]
                    if not pitch in poly_afters_action:
                        poly_afters.append((data[seq][i], time))

                    else:
                        res = poly_afters_action.index(pitch)
                        poly[res] = (data[seq][i], time)

                #else log unknown notes
                else:
                    print "Unrecognize command => " + str(command>>4)

        #Checking reset all
        #COnfigurable standard take care ????
        if standard:
            if reset_all != (0,0):
                special_consideration = 1

                wheels = [wheel[0] for wheel in wheels_action
                      if not reset_all[1] > wheel[1]]

                afters = [after[0] for after in afters
                      if not reset_all[1] > afters[1]]

                poly_afters = [poly_after[0] for poly_after in poly_afters
                      if not reset_all[1] > poly_afters[1]]

            #Checking if some command haven't been
            #completed(when msb/lsb not standardize)
            if bank_msb != (0,0):
                controllers.append(bank_msb[0])

            if bank_lsb != (0,0):
                controllers.append(bank_lsb[0])


            #Checking mutual exclusive omniOff omniOn
            if omni_off != (0,0) and omni_on != (0,0):
                if omni_off[1] > omni_on[1]:
                    controllers.append(omni_off[0])
                    #Removing previews notes

                else:
                    controllers.append(omni_on[0])
            else:
                if omni_off !=(0,0):
                #Log special consideration ( we have to rebuild the channel
                #to be sure )
                    special_consideration = 1
                    controllers.append(omni_off[0])
                    #Removing previews notes

                elif omni_on != (0,0):
                    controllers.append(omni_on[0])
                    #Removing previews notes


            #Checking mutual exclusive Mono/Poly
            if poly != (0, 0) and mono != (0, 0):
            #Log special consideration ( we have to rebuild the channel
            #to be sure )
                special_consideration = 1
                if poly[1] > mono[1]:
                    controllers.append(poly[0])
                else:
                    controllers.append(mono[0])
            else:
                if poly != (0, 0):
                    controllers.append(poly[0])
                elif mono != (0, 0):
                    controllers.append(mono[0])


        else:
            wheels = [wheel[0] for wheel in wheels]
            afters = [after[0] for after in afters]
            poly_afters = [poly_after[0] for poly_after in poly_afters]
            notes = [note[0] for note in notes]

            controllers = [controller[0] for controller in controllers]

            if reset_all != (0,0):
                controllers.append(reset_all[0])

            if poly != (0, 0):
                controllers.append(poly[0])

            if mono != (0, 0):
                controllers.append(mono[0])

            if omni_off != (0, 0):
                controllers.append(omni_off[0])

            if omni_on != (0, 0):
                controllers.append(omni_on[0])

            if bank_msb != (0, 0):
                controllers.append(bank_msb[0])

            if bank_lsb != (0, 0):
                controllers.append(bank_lsb[0])

        return (special_consideration, controllers, programs, system_p,
                wheels, notes, extras, afters, poly_afters)


    def update(self, data):
        #dispatch data in there chapters
        (special_consideration, controllers, programs, p_system, wheels,
         notes, extras, afters, poly_afters ) = self.dispatch_data(data)

        special_consideration = 0
        if special_consideration:
            #Rebuild all the channel we have to take care about a special case
            #Dispatch data on all packets of the channel
            #encode it
            #Stock packets
            print "special consideration"

        else:
            for chapter in self.chapters:
                #New data
                current_chap = self.chapters[chapter][0]
                #Testing len of new data
                if len(eval(chapter)) > 0:
                    if hasattr(current_chap, "update"):
                        getattr(current_chap, "update")(eval(chapter))

        #Encoding new data
        self.content, self.note_off_presence = self.encode_channel_journal()

    def trim(self, new_checkpoint):
        for chapter in self.chapters:
                current_chap = self.chapters[chapter][0]
                if current_chap != None:
                    current_chap.trim(new_checkpoint)

        #Rencoding data
        self.content, self.note_off_presence = self.encode_channel_journal()


    def encode_channel_journal(self):
        """Build the channel journal of a given channel,
        based on data passed from create_recovery_journal"""
        marker_p = marker_c = marker_w = marker_n =  marker_t = marker_a = 0
        length = 0

        note_off_presence = 0
        for chapter in self.chapters:
            current_chap = current_chap = self.chapters[chapter][0]
            if hasattr(current_chap, "content"):
                encoded = getattr(current_chap, "content")
                if len(encoded) > 0:
                    init = ""
                    if chapter == "poly_afters":
                        init = "a"

                    elif chapter == "afters":
                        init = "t"

                    else:
                        init = chapter[0]

                    var_name = "marker_%s" % init
                    exec(var_name + "=1")
                    chap_name = "chapter_%s" % chapter[0]

                    self.chapters[chapter][1] = encoded
                    length += len(encoded)



        chunk = self.chapters['programs'][1] + self.chapters['controllers'][1] \
            + self.chapters['wheels'][1] + self.chapters['notes'][1] \
            + self.chapters['afters'][1] + self.chapters['poly_afters'][1]

        #generate header
        header = self.header(self.chan_num, length, marker_s=note_off_presence,
                             marker_p=marker_p, marker_c=marker_c,
                             marker_w=marker_w, marker_n=marker_n,
                             marker_t=marker_t, marker_a=marker_a)

        #Building channel
        chunk = header + chunk

        return  chunk, note_off_presence



    def parse_channel_journal(self, journal, marker_p, marker_c, marker_m,
                              marker_w, marker_n, marker_e, marker_t,
                              marker_a ):
        #Needed
        channel = []
        j = 0

        #ChapterP
        if marker_p:
            #Parsing
            size, midi_cmd, marker_s, marker_x, marker_b \
                = self.chapters["programs"][0].parse(journal[:3])

            #Increment iterator
            j += size

            #adding notes
            channel.extend(midi_cmd)

        #ChapterC
        if marker_c:
            size, chapter_c_parsed, marker_s \
                = self.chapters["controllers"][0].parse(journal[j:])
            j += size
            channel.extend(chapter_c_parsed)

        #ChapterW
        if marker_w:
            size, chapter_w_parsed, marker_s \
                = self.chapters["wheels"][0].parse(journal[j:])
            j += size
            channel.extend(chapter_w_parsed)

        #ChapterN
        if marker_n:
            size, chapter_n_parsed \
                = self.chapters["notes"][0].parse(journal[j:])
            j += size
            channel.extend(chapter_n_parsed)

        #ChapterT
        if marker_t:
            size, chapter_t_parsed \
                = self.chapters["afters"][0].parse(journal[j:])
            j += size
            channel.extend(chapter_t_parsed)

        #Chapter A
        if marker_a:
            size, marker_s, chapter_a_parsed \
                = self.chapters["poly_afters"][0].parse(journal[j:])
            j += size
            channel.extend(chapter_a_parsed)

        return channel



    def parse_header(self, chapter):
        """|S| CHAN  |H|      LENGTH       |P|C|M|W|N|E|T|A|  Chapters ..|
        """
        first = chapter[:2]
        first = unpack('!H', first)

        marker_s = first[0]&32768 and 1 or 0
        chan = (first[0]&30720) >> 11
        marker_h = first[0]&1024 and 1 or 0
        length = first[0]&1023

        second = chapter[2]
        second = unpack('!B', second)

        marker_p = second[0]&128 and 1 or 0
        marker_c = second[0]&64 and 1 or 0
        marker_m = second[0]&32 and 1 or 0
        marker_w = second[0]&16 and 1 or 0

        marker_n = second[0]&8 and 1 or 0
        marker_e = second[0]&4 and 1 or 0
        marker_t = second[0]&2 and 1 or 0
        marker_a = second[0]&1 and 1 or 0

        return (marker_s, chan, marker_h, length, marker_p, marker_c,
                marker_m, marker_w, marker_n, marker_e, marker_t,
                marker_a)


class RecoveryJournal(object):
    """
    Figure 8 rfc 4695
              0                   1                   2
              0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3
             +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
             |S|Y|A|H|TOTCHAN|   Checkpoint Packet Seqnum    |
             +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

    """

    def __init__(self, standard=0):
        self.channels = {}
        self.checkpoint = 0
        self.act_seq = 0
        self.tot_chan = 0
        self.content = ""
	self.highest = 0
        self.follow_standard = standard

    def update(self, new_packet):
        """Comparing channel content with content of packets between
        checkpoint and act_seq, updating rj thanks to this compare"""
        channels = {}
        midi_cmd = new_packet.packet

        #for each midi_cmd get chan present
        for j in range(len(midi_cmd)):
            chan = midi_cmd[j][0][0]&15

            #getting seq no list
            if channels.has_key(chan):

                if channels[chan].has_key(new_packet.seqNo):
                    channels[chan][new_packet.seqNo].append(midi_cmd[j])

                else:
                    #creation nouveau seq for channel chan et ajout notes
                    channels[chan][new_packet.seqNo] = []
                    channels[chan][new_packet.seqNo].append(midi_cmd[j])

            else:
                #list des seq num
                seqs = {}
                channels[chan] = seqs
                channels[chan][new_packet.seqNo] = []
                channels[chan][new_packet.seqNo].append(midi_cmd[j])

        #Comparing new dict with old dict
        for channel in channels:
            if self.channels.has_key(channel):
                if len(channels[channel]) > 0:
                    #Updating channel
                    self.channels[channel].update(channels[channel])

            else:
                #Creation of new channel
                self.tot_chan += 1
                self.channels[channel] = ChannelJournal(channel, channels[channel], self.follow_standard)

        #Updating values
        #self.checkpoint = checkpoint
        self.highest = new_packet.seqNo
        self.build()

    def build(self):
        chunk = ""
        marker_a = 0
        for channel in self.channels:
            #print len(self.channels[channel].content)
            chunk += self.channels[channel].content


        #TODO check empty recovery
        if len(chunk) == 13:
            marker_a = 1
        header = self.header(self.tot_chan, self.highest, marker_a=marker_a)

        if header != -1:
            self.content = header + chunk

        else:
            self.content = ""

    def trim(self, new_checkpoint):
        for channel in self.channels:
            self.channels[channel].trim(new_checkpoint)

        self.build()


    def header(self, nb_channel, checkpoint, marker_s=0, marker_a=0):

        #S marke note off presence
        marker_s = marker_s << 7
        #if system journal appear
        marker_y = 0 << 6
        #if channel journal appear
        marker_a = marker_a << 5
        #if using enhanced control change (a voir)
        marker_h = 0 << 4
        #num of chan present dans le journal ( a faire a la vole )
        #4bits ( l'interpreter TOTCHAN + 1)
        #ici 9 channel
        if nb_channel <= 0 or nb_channel > 15:
            #Too much or to less channel , there is a problem
            return -1

        nb_channel = nb_channel - 1

        #All in 8 bits
        first = marker_s | marker_y | marker_a | marker_h | nb_channel

        #checkpoint packet num 16 bits
        #faire un test sur check point
        header = pack('!BH', first, checkpoint)
        return header

    def parse_header(self, journal_header):

        header = unpack('!B', journal_header[0])

        #S
        marker_s = header[0]&128 and 1 or 0
        #if system journal appear
        marker_y = header[0]&64 and 1 or 0
        #if channel journal appear
        marker_a = header[0]&32 and 1 or 0
        #if using enhanced control change (a voir)
        marker_h = header[0]&16 and 1 or 0
        #num of chan present dans le journal 4bits ( l'interpreter TOTCHAN + 1)
        totchan = (header[0]&15) + 1

        header = unpack('!H', journal_header[1:])
        #checkpoint packet num 16 bits
        ch_packet = header[0]

        return (marker_s, marker_y, marker_a, marker_h , totchan, ch_packet)

    def parse(self, recovery_journal):

        #List of note that will be return
        cmd_list = []

        #Parsing header of recovery journal
        journal_header = recovery_journal[:3]
        (marker_s, marker_y, marker_a, marker_h,
         totchan, ch_packet) = self.parse_header(journal_header)

        #Empty recovery journal
        if marker_a == 1:
            return []

        journal = recovery_journal[3:]

        cj = ChannelJournal()
        #iterator
        j = 0
        #if channel is present in the recovery journal

            #Parse Channels journal
        for i in range(totchan):

            #Parse each channel header to get information
            channel_header = cj.parse_header(journal[j:3+j])
            j += 3

            #Get size of channel
            channel_size = channel_header[3] + j

            #Get chan num
            channel_num = channel_header[1]

            #Extract channel
            channel = journal[j:j+channel_size]

            #Getting field present in the channel
            #P=0, C=0, M=0, W=0, N=0, E=0, T=0, A=0
            (marker_s, chan, marker_h, length, marker_p, marker_c,
             marker_m, marker_w, marker_n, marker_e, marker_t,
             marker_a) = channel_header

            #parsing channel
            channel_content = cj.parse_channel_journal(channel,
                                                       marker_p, marker_c,
                                                       marker_m, marker_w,
                                                       marker_n, marker_e,
                                                       marker_t, marker_a )

            ##formating contenu to return content
            #Chan num story
            cmd_list = [[[channel_content[i][0]+
                          channel_num,channel_content[i][1],
                          channel_content[i][2]],0]
                        for i in range(len(channel_content))]

            #push iterator
            j = channel_size

        return cmd_list


def compare_history_with_recovery(recovery, feed_history):
    """Compare recovery journal content with notes received
    from the last checkpoint"""

    #list of note that will be played in order to repare the stream
    repared_list = []

    #Order history by channels midi command and pitch
    decorate =  [((x[0][0]&15), (x[0][0]&240), x[0][1], x) for x in feed_history]
    decorate.sort()
    feed_history = [x[3] for x in decorate]

    #recuperation des notes en enlevant celles du feed history
    found = False
    for i in range(len(recovery)):
        #if notes present in recovery and history
        #(don't take care about TS)
        #putting it out except for note off and last for the pitch is a on
        for j in range(len(feed_history)-1, -1, -1):
            #if same command and if same pitch and if same channel
            if ((recovery[i][0][0]&240 == feed_history[j][0][0]&240)
                and (recovery[i][0][1] == feed_history[j][0][1])
                and (recovery[i][0][0]&15 == feed_history[j][0][0]&15)):
                found = True
                break

        if not found:
            repared_list.append(recovery[i])

        else:
            #If found
            #If a note off
            if feed_history[j][0][0]&240 == 128:
                #Checking that the last note for this pitch in history is a off
                ahh = False
                for o in range(j, len(feed_history)):
                    if (feed_history[o][0][1] == feed_history[j][0][1]
                        and feed_history[o][0][0]&240 == 144):
                        #the last is a note on so keep the note off from recovery
                        ahh = True
                        break
                if ahh:
                    #Not sure I got to keep this??
                    repared_list.append(recovery[i])

            #Init found flag
            found = False

    if len(repared_list) < 1:
        #cas ou les notes dans le recovery sont aussi present dans le flux
        #Attention possibilite de note perdus (les meme que celle presente dans recovery et feed
        #recuperation des notes off afin de les jouer pour eviter tout indefinite artefact.
        repared_list = [recovery[i] for i in range(len(recovery))
                        if recovery[i][0][0]&240 == 128]

    return repared_list


if __name__ == "__main__":
    partition_on = []
    partition_off = []


    for i in range(128):
        partition_on.append( [[144, i, 100], 1000])


    for i in range(128):
        partition_off.append( [[128, i, 0], 1000])


    progs =  [[[192, 120, 0], 1000]]
    for prog in progs:
        partition_on.append(prog)
        partition_off.append(prog)

    #Wheels
    wheels =  [[[224, 120, 1], 1000]]
    for wheel in wheels:
        partition_on.append(wheel)
        partition_off.append(wheel)


    #Controllers
    for i in range(128):
        partition_on.append( [[176, i, 100], 1000])
        partition_off.append( [[176, i, 100], 1000])


    #Aftertouch
    partition_on.append( [[208, 1, 100], 1000])
    partition_off.append( [[208, 1, 100], 1000])

    #Poly-aftertouch
    for i in range(128):
        partition_on.append( [[160, i, 100], 1000])
        partition_off.append( [[160, i, 100], 1000])



    recovery = RecoveryJournal()
    packy = OldPacket(6, partition_on, 0)
    ref = time.time()*1000
    recovery.update(packy)
    print "time update chrono ", str( (time.time()*1000 - ref))
    ref = time.time()*1000
    res = recovery.parse(recovery.content)
    print "time parse chrono ", str( (time.time()*1000 - ref))
    print "len cmp// res: ", str(len(res)), " // ref: ", str(len( partition_on))

