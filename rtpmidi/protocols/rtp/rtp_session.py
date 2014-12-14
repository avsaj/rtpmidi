#utils import
import re
import subprocess

#rtp import
from rtpmidi.protocols.rtp.rtp_control import RTPControl

class RTPSession(object):
    """RTP Session prototype
    """
    def __init__(self, peerAddress, sport, rport, payload,
                 jitter_buffer_size, tool_name="", fqdn="", user_name=""):
        #RTP utils
        self.sport = sport
        self.rport = rport

        self.payload = payload
        self.host = peerAddress
        self.jitter_buffer_size = jitter_buffer_size

        if tool_name == "":
            self.tool_name = "Unknown tool"
        else:
            self.tool_name = tool_name

        if fqdn == "":
            self.fqdn = get_fqdn()
        else:
            self.fqdn = fqdn

        if user_name == "":
            self.user_name = get_name()
        else:
            self.user_name = user_name

        self.cookie = None

        #checkpoint received
        #A dict of that link with member table
        self.checkpoint = 0

        #checkpoint sent
        self.last_checkpoint = 0
        self.seq = 0

        #stat
        self.last_send = 0

    def start(self):
        """If override by daughters must call:
        """
        RTPControl().start_session(self.cookie)

    def stop(self):
        """If override by daughters must call:
        """
        RTPControl().stop_session(self.cookie)

    def incoming_rtp(self, cookie, timestamp, packet,
                     read_recovery_journal = 0):
        """Function called by RTPProtocol when incoming
        data coming out from jitter buffer
        """
        raise NotImplementedError

    def send_empty_packet(self, chunk=0):
        RTPControl().send_empty_packet(self.cookie, chunk)


    def send_data(self, data, ts):
        #Selecting RTP session
        RTPControl().send_data_packet(self.cookie, data, ts)


    def drop_call(self, cookie=0):
        #Rename drop connection
        raise NotImplementedError


#Utilities
def get_first_cmd_answer(cmd):
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
    (child_stdin, child_stdout_and_stderr) = (proc.stdin, proc.stdout)
    p = re.compile('\\n')

    for line in child_stdout_and_stderr.readlines():
        print(line)
        res = p.sub('', line)
        return str(res)

def get_fqdn():
    login = get_first_cmd_answer("whoami")
    hostname = get_first_cmd_answer("hostname")
    return login + "@" + hostname

def get_name():
    login = get_first_cmd_answer("whoami")
    return login
