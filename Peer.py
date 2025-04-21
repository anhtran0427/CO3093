import hashlib

import threading
import socket
from threading import Thread
import random
import string
import json



from PeerHandler import PeerHandler
from FileManager import FileManager, Piece

from PeerServer import PeerServer
EVENT_STATE = ['STARTED', 'STOPPED', 'COMPLETED']

class Peer:
    def __init__(self, peer_ip, peer_port, info, file_manager):
        self.peer_id = self.generate_peer_id()

        self.peer_ip = peer_ip
        self.peer_port = peer_port

        self.info_hash = info['info_hash']
        self.total_length = info['length']
        self.name = info['name']
        self.trackers = info['trackers']

        self.peer_server = PeerServer(self.peer_id, peer_ip, peer_port, self.info_hash)

        self.is_running = False
        self.peer_handlers: dict[(str, int), PeerHandler] = {}
        self.threads: dict[(str, int), Thread] = {}
        self.peer_server_thread = None
        self.file_manager = file_manager

        self.bitfields = {}  # Lưu trữ bitfield từ mỗi peer (peer_id -> bitfield)
        self.piece_frequencies = {}  # Đếm tần suất xuất hiện của mỗi piece
        self.lock = threading.Lock()

        self.scrape_response = ""
    def generate_peer_id(self):
        client_id = "PY"  # Two characters for client id (e.g., PY for Python)
        version = "0001"  # Four ascii digits for version number
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        return f"-{client_id}{version}-{random_chars}"

    def download(self):
        """
        Hàm sẽ tạo một thread cho việc lắng nghe yêu cầu từ các peer qua hàm start_server
        Sau đó nhận peer list từ Tracker Server
        Với mỗi peer sẽ tạo một thread chạy PeerHandler để communicate
        :return: void
        """
        # Tạo server để lắng nghe và phản hồi yêu cầu từ các peer khác
        self.start_server()
        # Gửi request và nhận về peer list từ tracker server
        response = self.peer_server.announce_request("STARTED")
        response = json.loads(response)
        print(response)

        peers = response['peers']

        # Tạo PeerHandler để communicate với các peer khác
        for peer in peers:

            ip = peer["ip"]
            port = int(peer["port"])

            if ip == self.peer_ip and port == self.peer_port:
                continue

            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((ip, port))
            peer_handler = PeerHandler(conn, (ip, port), self.info_hash, self.peer_id, self.callback)
            thread = Thread(target=peer_handler.run)

            with self.lock:
                self.peer_handlers.update({(ip, port): peer_handler})
                self.threads.update({(ip, port): thread})

                thread.start()


    def upload(self):

        self.start_server()
        respond = self.peer_server.announce_request("STARTED")
        print(respond)

    def scrape_tracker(self):
        response = self.peer_server.scrape_request()
        print("Scrape tracker: ", response)
        self.scrape_response = response

    def get_scrape_response(self):
        if self.scrape_response != "":
            return self.scrape_response
        else:
            return "No information"

    def stop(self):
        self.is_running = False

        self.peer_server.announce_request("STOPPED")

        for (ip, port) in list(self.peer_handlers.keys()):
            self.peer_handlers[(ip, port)].stop()
            self.peer_handlers.pop((ip, port))

        for (ip, port) in list(self.threads.keys()):
            self.threads[(ip, port)].join()
            self.threads.pop((ip, port))

        if self.peer_server_thread:
            self.peer_server_thread.join()

    def stop_peer_handler(self, addr):
        """Stop and clean up a peer handler and its thread"""
        addr_key = (addr[0], addr[1])

        with self.lock:
            # Only proceed if the peer handler exists
            if addr_key not in self.peer_handlers:
                return

            print(f"Stopping connection to {addr}")

            # Get the handler and thread
            handler = self.peer_handlers[addr_key]
            thread = self.threads.get(addr_key)

            # Stop the handler first
            handler.stop()

            # Remove from dictionaries
            self.peer_handlers.pop(addr_key)

            # If there's a thread and it's not the current thread
            if thread and thread != threading.current_thread():
                self.threads.pop(addr_key)
                thread.join(timeout=5)


    def callback(self, peer_id, event_type, data=None)->dict:
        """
        Callback function để xử lý các sự kiện từ PeerHandler
        """
        if event_type == 'bitfield_received':
            bitfield = bytes(data['bitfield'])
            with self.lock:
                # Lưu lại bitfield nhận được từ PeerHandler
                self.bitfields[peer_id] = bitfield
                self.update_piece_frequencies(bitfield)
                interested = self.file_manager.is_interested(bitfield)
                return {'interested' : interested}

        elif event_type == 'request_bitfield':
            return  {'bitfield' : self.file_manager.get_bitfield()}

        elif event_type == 'request_piece_index':
            index = self.get_rarest_piece()
            print("Piece index: ", index)
            length = self.file_manager.get_exact_piece_length(index)

            return {'index': index, 'begin': 0, 'length': length}

        elif event_type == 'request_piece':
            index = int(data['index'])
            return self.file_manager.get_piece(index)

        elif event_type == 'piece_received':
            index = int(data['index'])
            begin = int(data['begin'])
            data = data['block']
            hash_value = hashlib.sha256(data).hexdigest()
            piece = Piece(index, data, hash_value)

            self.file_manager.add_piece(piece)

            is_complete = self.file_manager.check_complete()

            if is_complete:
                self.file_manager.export()

                self.peer_server.announce_request("COMPLETED")
            return is_complete
        elif event_type == 'stop':
            addr = data['addr']
            self.stop_peer_handler(addr)


    def start_server(self):
        """Khởi chạy server để lắng nghe các yêu cầu từ peer khác."""
        if not self.is_running:
            self.is_running = True
            self.peer_server_thread = threading.Thread(target=self.listen)
            self.peer_server_thread.start()

    def listen(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.peer_port))
        server_socket.listen(5)
        server_socket.settimeout(1)  # Đặt timeout cho socket

        while self.is_running:
            try:
                conn, addr = server_socket.accept()
                ip, port = addr
                peer_handler = PeerHandler(conn, addr, self.info_hash, self.peer_id, self.callback)
                thread = threading.Thread(target=peer_handler.run)
                with self.lock:
                    self.peer_handlers[(ip, port)] = peer_handler
                    self.threads[(ip, port)] = thread

                    thread.start()

            except socket.timeout:
                continue  # Kiểm tra lại `is_running` mỗi khi hết timeout

        server_socket.close()


    def update_piece_frequencies(self, bitfield):
        """
        Cập nhật tần suất xuất hiện của mỗi piece dựa trên bitfield nhận được
        """

        for piece_index in range(self.file_manager.get_total_pieces()):
            byte_index = piece_index // 8
            bit_index = piece_index % 8

            # Check if the bit is set (indicating the piece is available)
            if bitfield[byte_index] & (1 << (7 - bit_index)):
                if piece_index not in self.piece_frequencies:
                    self.piece_frequencies[piece_index] = 0
                self.piece_frequencies[piece_index] += 1

    def get_rarest_piece(self):
        """
        Tìm ra piece hiếm nhất dựa trên tần suất xuất hiện trong các bitfield
        """
        rarest_piece = None
        min_frequency = float('inf')

        for piece_index, frequency in self.piece_frequencies.items():
            if frequency < min_frequency and not self.file_manager.has_piece(piece_index):
                min_frequency = frequency
                rarest_piece = piece_index

        return rarest_piece

    def get_transfer_information(self):
        progress = len(self.file_manager)/ self.file_manager.get_total_pieces() * 100
        return {"progress": progress, "peers": len(self.peer_handlers), "speed": 0}