import getopt
import SocketServer
import socket
import struct
import sys
"""
DNS Header
0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5  6
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                       ID                      |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|QR| Opcode |AA|TC|RD|RA|    Z   |     RCODE    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    QDCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ANCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    NSCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ARCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
DNS Query
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
/                      QNAME                    /
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      QTYPE                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      QCLASS                   |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
DNS Answer
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
/                       NAME                    /
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                       TYPE                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      CLASS                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                       TTL                     |
|                                               |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                     RDLENGTH                  |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--|
/                      RDATA                    /
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
"""

RECORD={'www.abc.com':'1.1.1.1',
        'www.def.com':'2.2.2.2'}


class DNSPacket:

    def __init__(self, raw_packet):
        [self.id, self.flags, self.qcount, self.acount, self.nscount,
         self.arcount] = struct.unpack('>HHHHHH', raw_packet[:12])
        self.query = DNSQuery(raw_packet[12:])
        self.answer = None

    def build(self):
        packet = struct.pack('>HHHHHH', self.id, self.flags,
                            self.qcount, self.acount,
                            self.nscount, self.arcount)
        if self.qcount > 0:
            domain = self.query.qname
            packet += self.query.create(domain)
        if self.acount > 0:
            packet += self.answer.create()

        return packet

    def setip(self, ip):
        self.answer = DNSAnswer(ip)
        self.acount = 1
        self.flags = 0x8180

    def debug_print(self):
        print 'ID: %X\tFlags:%.4X' % (self.id, self.flags)
        print 'Query Count:%d\tAnswer Count:%d' % (self.qcount, self.acount)
        if self.qcount > 0:
            self.query.debug_print()
        if self.acount > 0:
            self.answer.debug_print()


class DNSQuery:
    def __init__(self, raw):
        self.parse(raw)

    def create(self, domain):
        self.qname = domain
        query = ''.join(chr(len(x)) + x for x in domain.split('.'))
        query += '\x00'  # add end symbol
        return query + struct.pack('>HH', self.qtype, self.qclass)

    def parse(self, data):
        s = data[:-4]
        ptr = 0
        temp=[]
        while(True):
            count = ord(s[ptr])
            if count == 0:
                break
            ptr += 1
            temp.append(s[ptr:ptr+count])
            ptr += count
        self.qname = '.'.join(temp)
        [self.qtype, self.qclass] = struct.unpack('>HH', data[-4:])

    def debug_print(self):
        print '[DEBUG]DNS QUERY'
        print 'Request:', self.qname
        print 'Type: %d\tClass: %d' % (self.qtype, self.qclass)

class DNSAnswer:
    def __init__(self, ip):
        self.aname = 0xC00C
        self.atype = 0x0001
        self.aclass = 0x0001
        self.ttl = 60  # time to live
        self.data = ip
        self.len = 4

    def create(self):
        ans = struct.pack('>HHHLH4s', self.aname, self.atype, self.aclass, self.ttl, self.len, socket.inet_aton(self.data))
        return ans

    def debug_print(self):
        print '[DEBUG]DNS ANSWER'
        print 'Query:', self.name
        print 'Type: %d\tClass: %d' % (self.qtype, self.qclass)
        print 'TTL: %d\tLength: %d' % (self.ttl, self.len)
        print self.ip

class DNSUDPHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        data = self.request[0].strip()
        sock = self.request[1]
        packet = DNSPacket(data)
        print '[DEBUG] Receive Request'
        packet.debug_print()

        if packet.query.qtype == 1:
            domain = packet.query.qname
            if RECORD.__contains__(domain):
                packet.setip(RECORD[domain])
                print '[DEBUG] Send Answer'
                packet.debug_print()
                sock.sendto(packet.build(), self.client_address)
            else:
                sock.sendto(data, self.client_address)
        else:
            sock.sendto(data, self.client_address)


class SimpleDNSServer:
    def __init__(self, port=53):
        self.name2ip = {}
        self.port = port

    def start(self):
        HOST, PORT = 'localhost', self.port
        server = SocketServer.UDPServer((HOST, PORT), DNSUDPHandler)
        server.serve_forever()


def parse(argvs):
    port = 0
    name = ''

    opts, args = getopt.getopt(argvs[1:],'p:n:')
    for o, a in opts:
        if o == '-p':
            port = int(a)
        elif o == '-n':
            name = a
        else:
            print 'Usage: %s -p <port> -n <name>' % argvs[0]
    return port, name

if __name__ == '__main__':
    port, domain = parse(sys.argv)
    server = SimpleDNSServer(port)
    server.start()