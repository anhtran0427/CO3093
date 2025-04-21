import urllib.parse
import socket

TRACKER_PORT = 5050
TRACKER_HOST = 'localhost'
EVENT_STATE = ['STARTED', 'STOPPED', 'COMPLETED']

"""
Class dùng để communicate với server
"""

class PeerServer:
    def __init__(self, peer_id, peer_ip, peer_port, info_hash):
        self.peer_ip = peer_ip
        self.peer_port = peer_port
        self.info_hash = info_hash
        self.is_running = False
        self.peer_id = peer_id
        self.peer_ip = peer_ip
        self.peer_port = peer_port
        self.uploaded = 0
        self.downloaded = 0
        self.left = 0
        self.compact = 0
        self.no_peer_id = 0
        self.event = EVENT_STATE[0]

    def announce_request(self, event_state):
        self.event = event_state
        params = {
            'info_hash': self.info_hash,
            'peer_id': self.peer_id,
            'ip': self.peer_ip,
            'port': self.peer_port,
            'uploaded': str(self.uploaded),
            'downloaded': str(self.downloaded),
            'left': str(self.left),
            'compact': str(self.compact),
            'event': self.event,
        }

        query_string = urllib.parse.urlencode(params)
        # Tạo thông điệp GET request
        request = f"GET /announce?{query_string} HTTP/1.1\r\n"
        request += f"Host: {TRACKER_HOST}\r\n"
        request += "Connection: close\r\n\r\n"

        response = self.send_request(request)
        return response

    def scrape_request(self):
        # Mã hóa info_hash
        encoded_info_hash = urllib.parse.quote(self.info_hash)
        request = f"GET /scrape?info_hash={encoded_info_hash} HTTP/1.1\r\nHost: {TRACKER_HOST}\r\n\r\n"

        response = self.send_request(request)
        return response

    def send_request(self, request):
        # Mở kết nối TCP tới tracker

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((TRACKER_HOST, TRACKER_PORT))
        server_socket.sendall(request.encode('utf-8'))
        response = b""
        while True:
            data = server_socket.recv(4096)
            if not data:
                break
            response += data

        return response.decode('utf-8')