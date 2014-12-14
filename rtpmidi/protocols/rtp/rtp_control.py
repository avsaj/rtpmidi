#utils import
import time

#data import
from rtpmidi.protocols.rtp.utils import Singleton

#rtp import
from rtpmidi.protocols.rtp.protocol import RTPProtocol

#RTP Timeout is 60
RTP_TIME_OUT = 40

class RTPControl(Singleton):
    """Control rtp for a payload to implement
    """
    currentRecordings = {}
    cookies = 0

    def add_session(self, session):
        #Test type
        if (not(hasattr(session, "incoming_rtp")
            and hasattr(session, "payload")
            and hasattr(session, "host")
            and hasattr(session, "rport")
            and hasattr(session, "drop_call")
            and hasattr(session, "start")
            and hasattr(session, "stop"))):
            raise Exception, "This session type is not supported"
            return

        #Cookie related to the rtp session
        cookie = self.make_cookie()
        session.cookie = cookie

        #Creating RTP
        self._create_rtp_socket(cookie, session)
        return cookie

    def del_session(self, cookie):
        rtp, o = self.currentRecordings[cookie]
        rtp.stopSendingAndReceiving()
        del self.currentRecordings[cookie]

    def start_session(self, cookie):
        rtp, session = self.currentRecordings[cookie]
        rtp.start(session.host)
        session.start()

    def start(self):
        for cookie in self.currentRecordings:
            self.start_session(cookie)

    def _create_rtp_socket(self, cookie, session):

        #Init RTPProtocol
        rtp = RTPProtocol(self, cookie, session.payload,
                          session.jitter_buffer_size, verbose=session.verbose)

        #Creating socket
        rtp.createRTPSocket(session.host, session.rport, session.sport, False)

        #Register the session
        self.currentRecordings[cookie] = (rtp, session)

        #Registering host and port in used(if default port is in used by another
        #application it will choose another
        if rtp.rport > 0:
            session.host = (session.host, rtp.rport)

        else:
            session.host = (session.host, rtp.sport)

    def incoming_rtp(self, cookie, timestamp, packet,
                     read_recovery_journal = 0):
        """Function called by RTPProtocol when incoming
        data coming out from jitter buffer
        """
        rtp, session = self.currentRecordings[cookie]
        session.incoming_rtp(cookie, timestamp, packet,
                             read_recovery_journal)


    def send_empty_packet(self, cookie, chunk):
        #Selecting RTP session
        rtp, session = self.currentRecordings[cookie]

        #sending silent packet with recovery journal
        rtp.handle_data(session.payload, 0 , chunk, 1)
        self.last_send = time.time()


    def send_data_packet(self, cookie, data, ts):
        #Selecting RTP session
        rtp, session = self.currentRecordings[cookie]
        rtp.handle_data(session.payload, ts , data, 0)
        self.last_send = time.time()


    def stop_session(self, cookie):
        #Selecting RTP
        rtp, session = self.currentRecordings[cookie]
        rtp.stopSendingAndReceiving()
        session.stop()

    def stop(self):
        #Selecting RTP
        for cookie in self.currentRecordings:
            self.stop_session(cookie)

    def selectDefaultFormat(self, what):
        """link to sdp??"""
        #TODO pass SDP parameter for the session here ????
        pass

    def drop_connection(self, cookie):
        #Selecting RTP session
        rtp, session = self.currentRecordings[cookie]
        session.drop_connection()


    def get_session(self, cookie):
        rtp, session = self.currentRecordings[cookie]
        return session

    def make_cookie(self):
        self.cookies += 1
        return "cookie%s" % (self.cookies,)



