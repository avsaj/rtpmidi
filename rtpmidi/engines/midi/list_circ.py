import time

#motherclass
class ListCirc(object):

	def __init__(self, listeSize):
		self.index = 0
		self.list = []
		self.round = 0
		self.listeSize = listeSize

	def to_list(self, note):
		if self.round == 1:
			self._replace_note(note)
		else:
			self._add_note(note)

	def _add_note(self, note):
		self.list.append(note)

		if self.index == self.listeSize-1:
			self.round = 1
			self.index = 0
		else:
			self.index += 1

	def _replace_note(self, note):
		if (self.index == self.listeSize):
			self.index = 0
			self.list[self.index] = note
		else:
			self.list[self.index] = note
		self.index += 1

	def flush(self):
		self.list = []
		self.round = 0
		self.index = 0

    	def __getitem__(self,key):
        	return self.list[key]

	def __len__(self):
		return len(self.list)

class PacketCirc(ListCirc):

	#Recupere une note avec son compteur (numero)
	def find_packet(self, seqNo):
		"""Return emplacement of selected packet index the list"""
		res = -1

		for i in range(len(self.list)):
			if (self.list[i].seqNo == seqNo):
				res = i
				break

		return res

	def get_packets(self, checkpoint, act_seq ):
		"""Get packets from checkpoint to act seq
		this function is for simplify create_recovery_journal"""
		midi_cmd = []
		#getting pos of element
		checkpoint_pos = self.find_packet(checkpoint)
		act_seq_pos = self.find_packet(act_seq)

		#Take care of wrap around in seqNo

		if checkpoint >= act_seq:
			if checkpoint_pos < act_seq_pos:
				midi_cmd = self.list[checkpoint_pos+1:act_seq_pos+1]
			else:
				#getting checkpoint -> 0
				midi_cmd = self.list[checkpoint_pos+1:]

                                #getting 0 -> act_seq
				midi_cmd += self.list[:act_seq_pos+1]
		else:
			#getting checkpoint -> act_seq
			[midi_cmd.append(self.list[i]) \
				 for i in range(len(self.list)) \
				 if self.list[i].seqNo > checkpoint and \
				 self.list[i].seqNo <= act_seq]


		return midi_cmd



#list circ to stock time
class DelayCirc(ListCirc):

	def __init__(self, listeSize):
		ListCirc.__init__(self, listeSize)
		self.lastSync = 0

	def to_list(self,note):
		ListCirc.to_list(self,note)
		self.lastSync = time.time()

	def average(self):
		if (len(self.list)>0):
			average = float(sum(self.list)/len(self.list))
			return average

	def __repr__(self):
		return str(self.list)

#list circ to stock last miditime difference
class MidiTimeCirc(DelayCirc):

	def split(self):
		if ( len(self.list)>0):
			split =  max(self.list) - min(self.list)
      			return abs(split)
		else:
			return 0
