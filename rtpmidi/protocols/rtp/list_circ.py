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
