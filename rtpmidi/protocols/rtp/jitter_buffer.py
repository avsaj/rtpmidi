from threading import Lock

def packet_seq_compare(x, y):
    if x.header.seq>y.header.seq:
        return 1
    elif x.header.seq==y.header.seq:
        return 0
    else: # x<y
        return -1


class JitterBuffer(object):
    """Jitter buffer auto-resize by the jitter"""

    def __init__(self):
        self.buffer = []
        self.lock = Lock()

    def add(self, to_add):
        """Adding a packet to the buffer (insertion sort)"""
        place = 0

        self.lock.acquire()

        for i in range(len(self.buffer)):
            #Order by seq number
            if self.buffer[i][0].header.seq < to_add[0].header.seq:
                pass
            else:
                place = i
                break

        if place != 0:
            #Insert new element
            self.buffer.insert(place, to_add)
        else:
            if len(self.buffer) >= 1:
                if self.buffer[i][0].header.seq > to_add[0].header.seq:
                    self.buffer.insert(0, to_add)
                else:
                    self.buffer.append(to_add)
            else:
                self.buffer.append(to_add)

        self.lock.release()


    def has_seq(self, seq):
        """Looking for a special seqNum"""
        res = False
        for i in range(len(self.buffer)):
            if self.buffer[i][0].header.seq == seq:
                res = True
                break
        return res

    def get_packets(self, time):
        """Getting all the packet with continus seq num from packet seq"""
        to_send = []
        i = 0
        last_time = 0
        self.lock.acquire()
        while ( i < len(self.buffer)):
            #if buffer time passed or
            if self.buffer[i][1] <= time:
                to_send.append(self.buffer[i][0])
                del self.buffer[i]
            else:
                break

        self.lock.release()

        return to_send


if __name__ == "__main__":
    j = JitterBuffer()
