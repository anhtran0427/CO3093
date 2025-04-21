import socket
import json
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Optional
import uuid
import threading
class TrackerServer:
    def __init__(self, host: str = 'localhost', port: int = 5050):
        self.host = host
        self.port = port
        self.peers: Dict[str, List[Dict[str, str]]] = {}  # {info_hash: [peer_info, ...]}
        self.tracker_id = str(uuid.uuid4())

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', self.port))
            s.listen()
            print(f"Tracker server listening on {self.host}:{self.port}")
            while True:
                conn, addr = s.accept()
                """ with conn: """
                print(f"Connected by {addr}")
                threading.Thread(target=self.handle_connection, args=(conn, addr)).start()
                

    def handle_connection(self, conn, addr):
        with conn:
            data = conn.recv(1024).decode('utf-8')
            print(f"Data received: {data} from {addr}")
            # Data received
            response = self.handle_request(data)
            conn.sendall(response.encode('utf-8'))
        
    def handle_request(self, request: str) -> str:
        # Split the request into lines
        request_lines = request.split('\r\n')
        
        # Parse the first line to get the method and full path
        method, full_path, _ = request_lines[0].split(' ')
        
        if method != 'GET':
            return self.create_error_response("Only GET requests are supported")
        
        # Parse the URL and query parameters
        parsed_url = urlparse(full_path)
        params = parse_qs(parsed_url.query)
        request_type = parsed_url.path

        info_hash = params.get('info_hash', [None])[0]

        if request_type == '/announce':
            # Extract params
            peer_id = params.get('peer_id', [None])[0]
            ip = params.get('ip', [None])[0]
            port = params.get('port', [None])[0]
            event = params.get('event', [None])[0]
            downloaded = params.get('downloaded', [None])[0]

            print(f"Test {info_hash} {peer_id} {ip} {port} {event} {downloaded}")

            if not all([info_hash, peer_id, ip, port]):
                return self.create_error_response("Missing required parameters")

            # Handle different events
            if event == 'STARTED':
                self.add_peer(info_hash, peer_id, ip, port, downloaded)
            elif event == 'STOPPED':
                self.remove_peer(info_hash, peer_id)
            elif event == 'COMPLETED':
                self.update_peer(info_hash, peer_id, completed=True)

        # Create and return the response
        response = self.create_response(info_hash, request_type)
                
        print(response)
        return response

    def add_peer(self, info_hash: str, peer_id: str, ip: str, port: str, downloaded: str):
        if info_hash not in self.peers:
            self.peers[info_hash] = []
        self.peers[info_hash].append({
            'peer_id': peer_id,
            'ip': ip,
            'port': port,
            'downloaded': downloaded
        })

    def remove_peer(self, info_hash: str, peer_id: str):
        if info_hash in self.peers:
            self.peers[info_hash] = [p for p in self.peers[info_hash] if p['peer_id'] != peer_id]

    def update_peer(self, info_hash: str, peer_id: str, completed: bool = False):
        if info_hash in self.peers:
            for peer in self.peers[info_hash]:
                if peer['peer_id'] == peer_id:
                    peer['completed'] = completed
                    break

    def create_response(self, info_hash: str, type: str) -> str:
        if type == '/announce':
            response = {
                'tracker_id': self.tracker_id,
                'info_hash': info_hash,
                'peers': self.peers.get(info_hash, [])
            }
        elif type == '/scrape':
            response = {
                'tracker_id': self.tracker_id,
                'info_hash': info_hash,
                'total_peers': len(self.peers.get(info_hash, []))
            }
        return json.dumps(response)

    def create_error_response(self, reason: str) -> str:
        return json.dumps({'failure reason': reason})

if __name__ == "__main__":
    tracker = TrackerServer()
    tracker.start()
