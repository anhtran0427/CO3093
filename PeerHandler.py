import socket
import struct
import threading
import time
from enum import IntEnum
from threading import Event


class MessageType(IntEnum):
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    NOT_INTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    PIECE = 7
    CANCEL = 8


class PeerHandler:
    def __init__(self, conn, addr, info_hash, peer_id, callback):
        self.conn = conn
        self.addr = addr
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.callback = callback
        self.client_id = None

        # State flags
        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False

        # Threading control
        self.running = True
        self.stopped_externally = False  # New flag to track if stop was called externally
        self.listen_thread = None
        self.request_thread = None

        # Peer state
        self.bitfield = None
        self.pending_requests = {}
        self.max_pending_requests = 5

        # Lock for thread safety
        self.cleanup_lock = threading.Lock()
        self.cleanup_done = False

    def run(self):
        if self.two_way_handshake():
            self.send_bitfield()

            # Start listening thread
            self.listen_thread = threading.Thread(target=self.listen)
            self.listen_thread.start()

            self.request_thread = threading.Thread(target=self.request)
            self.request_thread.start()

            self.listen_thread.join()
            self.request_thread.join()
        else:
            self._cleanup()
            self.callback(self.peer_id, "stop", {"addr": self.addr})

    def listen(self):
        try:
            while self.running:
                # First read the message length (4 bytes)
                length_prefix = self.conn.recv(4)
                if not length_prefix:
                    break

                # Unpack the length
                length = struct.unpack(">I", length_prefix)[0]

                # Keep-alive message
                if length == 0:
                    continue

                # Read the message type
                message_type = struct.unpack("B", self.conn.recv(1))[0]

                # Read the payload
                payload = b""
                remaining = length - 1
                while remaining > 0:
                    chunk = self.conn.recv(min(remaining, 16384))
                    if not chunk:
                        break
                    payload += chunk
                    remaining -= len(chunk)

                self.handle_message(message_type, payload)

        except Exception as e:
            print(f"Error in listen loop: {e}")
        finally:
            self._cleanup()
            self.callback(self.peer_id, "stop", {"addr": self.addr})

    def request(self):
        while self.running:
            time.sleep(1)

    def stop(self):
        """Called by parent to stop the peer handler"""
        self._cleanup()

    def _cleanup(self):
        """Internal cleanup method with thread safety"""
        with self.cleanup_lock:
            if not self.cleanup_done:
                self.running = False
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.cleanup_done = True

    def handle_message(self, message_type, payload):
        try:
            if message_type == MessageType.CHOKE:
                self.peer_choking = 1
                print(f"Peer {self.addr} choked us")

            elif message_type == MessageType.UNCHOKE:
                self.peer_choking = 0
                print(f"Peer {self.addr} unchoked us")

                if self.am_interested:
                    data = self.callback(self.client_id, "request_piece_index")
                    print(data)
                    self.send_request(data['index'], data['begin'], data['length'])

            elif message_type == MessageType.INTERESTED:
                self.peer_interested = 1
                print(f"Peer {self.addr} is interested")
                self.send_unchoke()

            elif message_type == MessageType.NOT_INTERESTED:
                self.peer_interested = 0
                print(f"Peer {self.addr} is not interested")

            elif message_type == MessageType.HAVE:
                piece_index = struct.unpack(">I", payload)[0]
                print(f"Peer {self.addr} has piece {piece_index}")
                if self.bitfield:
                    self.bitfield[piece_index] = 1

            elif message_type == MessageType.BITFIELD:
                bitfield = bytearray(payload)
                print(f"Received bitfield from {self.addr}, bitfield: {bitfield}")
                data = self.callback(self.client_id, "bitfield_received", {'bitfield':bitfield})
                print(data)
                if data['interested']:
                    self.send_interested()
                else:
                    self.send_not_interested()

            elif message_type == MessageType.REQUEST:
                print(f"Received request from {self.addr}")

                if self.am_choking:
                    print(f"Ignoring request from {self.addr}")
                    return

                index, begin, length = self.validate_request(payload)
                print(f"Receive from {self.addr}, index: {index}, begin: {begin}, length: {length}")

                piece = self.callback(self.client_id, "request_piece", {'index':index, 'begin':begin, 'length':length})
                self.send_piece({'index' : index, 'begin': begin, 'block': piece.get_data()})

            elif message_type == MessageType.PIECE:
                # Handle received piece data
                if len(payload) < 8:
                    return
                index = struct.unpack(">I", payload[0:4])[0]
                begin = struct.unpack(">I", payload[4:8])[0]
                block = payload[8:]
                print(f"Received piece {index} at offset {begin}, length {len(block)}")
                # Call callback to handle the received piece
                is_complete = self.callback(self.client_id, "piece_received", {'index' : index,'begin': begin,'block': block})
                if is_complete:
                    self.send_not_interested()
                else:
                    data = self.callback(self.client_id, "request_piece_index")
                    print(data)
                    self.send_request(data['index'], data['begin'], data['length'])

        except Exception as e:
            print(f"Error handling message type {message_type}: {e}")


    def two_way_handshake(self):

        # Gửi thông điệp handshake tới peer client
        self.send_handshake()
        # Nhận response từ peer (handshake message)
        response = self.conn.recv(1024)  # Receive the handshake message

        # Phân tích thông điệp handshake nhận được
        if self.parse_handshake(response):
            return True
        else:
            return False

    def parse_handshake(self, response):
        """
        Parse the handshake message from a peer.
        Check the info_hash and return True if valid, False otherwise.
        """
        try:
            print(f"handshake response: {response}")
            # Handshake message format:
            # <pstrlen><pstr><reserved><info_hash><peer_id>
            pstrlen = struct.unpack("B", response[0:1])[0]  # Length of the protocol string
            pstr = response[1:20].decode("utf-8")  # Protocol string (BitTorrent protocol)
            reserved = response[20:28]  # 8 bytes reserved
            received_info_hash = response[28:48]  # 20 bytes info_hash (raw bytes)
            received_peer_id = response[48:68].decode("utf-8")  # 20 bytes peer_id (raw bytes)
            self.client_id = received_peer_id
            # Check protocol string and info_hash (compare raw bytes, no decoding)
            if pstr == "BitTorrent protocol" and received_info_hash == self.info_hash:
                print(f"Handshake received successfully from {self.addr}")
                print(f"Peer ID: {received_peer_id}")
                return True
            else:
                print("Handshake invalid")
                return False
        except Exception as e:
            print(f"Handshake parsing failed: {e}")
            return False

    def send_handshake(self):
        """
        Send handshake message to the peer.
        """
        try:
            pstr = "BitTorrent protocol"
            pstrlen = len(pstr)
            reserved = b'\x00' * 8  # 8 bytes reserved (all zeros)

            # Ensure info_hash and peer_id are bytes (SHA-1 hash is 20 bytes)
            if isinstance(self.info_hash, str):
                raise ValueError("info_hash must be in bytes, not a string.")

            # Ensure info_hash and peer_id are exactly 20 bytes
            info_hash_bytes = self.info_hash if len(self.info_hash) == 20 else None
            if isinstance(self.peer_id, str):
                self.peer_id = self.peer_id.encode('utf-8')

            if info_hash_bytes is None:
                raise ValueError("info_hash must be exactly 20 bytes.")

            # Construct the handshake message:
            # <pstrlen><pstr><reserved><info_hash><peer_id>
            handshake_message = struct.pack(
                f"B{pstrlen}s8s20s20s",
                pstrlen,
                pstr.encode('utf-8'),  # pstr needs to be encoded as text
                reserved,
                info_hash_bytes,
                self.peer_id
            )

            print(f"handshake message: {handshake_message}")
            # Send the handshake message
            self.conn.send(handshake_message)
            print(f"Handshake sent to {self.addr}")
        except Exception as e:
            print(f"Handshake send failed: {e}")

    def send_interested(self):

        """Send interested message to peer"""
        self.send_message(MessageType.INTERESTED)
        self.am_interested = 1
        print(f"Sent interested message to {self.addr}")

    def send_not_interested(self):
        """Send not interested message to peer"""
        self.send_message(MessageType.NOT_INTERESTED)
        self.am_interested = 0
        print(f"Sent not interested message to {self.addr}")

    def listen_for_unchoke(self):
        """
        Lắng nghe và chờ thông điệp 'unchoke' từ peer để bắt đầu yêu cầu dữ liệu.
        """
        try:
            while True:
                message = self.conn.recv(1024)
                if len(message) < 5:
                    continue

                # Phân tích message
                length = struct.unpack(">I", message[:4])[0]
                msg_id = struct.unpack("B", message[4:5])[0]

                if msg_id == 1:  # Unchoke
                    print(f"Nhận thông điệp 'unchoke' từ peer {self.addr}")
                    self.peer_choking = 0
                    break
        except Exception as e:
            print(f"Lắng nghe 'unchoke' thất bại: {e}")

    def send_bitfield(self):
        """Send bitfield message to the peer."""
        data = self.callback(self.peer_id, "request_bitfield")
        bitfield = data['bitfield']
        print(f"My bitfield: {bitfield}")
        self.send_message(MessageType.BITFIELD, payload=bitfield)
        print(f"Sent bitfield message to {self.addr}")

    def send_message(self, message_type, payload=b''):
        """Utility method to send a message with proper length prefix"""
        try:
            # Convert message_type to integer
            if not isinstance(message_type, MessageType):
                raise TypeError(f"Expected MessageType, got {type(message_type)}")

            message_type_int = message_type.value
            message_length = len(payload) + 1  # +1 for message type
            message = struct.pack('>IB', message_length, message_type_int) + payload
            if message_type != MessageType.PIECE:
                print("Packed message:", message)  # Debug packed message

            self.conn.send(message)
        except Exception as e:
            print(f"Error sending message type {message_type}: {e}")

    def send_request(self,index, begin, length):

        """Send request for a specific block"""
        payload = struct.pack('>III', index, begin, length)
        self.send_message(MessageType.REQUEST, payload)
        print(f"Requested block - index: {index}, begin: {begin}, length: {length}")

    def send_unchoke(self):
        """Send unchoke message to the peer."""
        self.send_message(MessageType.UNCHOKE)
        self.am_choking = False

    def validate_request(self, payload):
        index, begin, length = struct.unpack('>III', payload)
        return index, begin, length

    def send_piece(self, piece):
        try:
            # Đảm bảo piece chứa các trường cần thiết
            index = piece['index']
            begin = piece['begin']
            block = piece['block']

            # Đóng gói payload
            payload = struct.pack('>II', index, begin) + block

            # Gửi message với message_type là 7 (ID cho piece message)
            self.send_message(MessageType.PIECE, payload)

        except KeyError as e:
            print(f"Missing piece field: {e}")
        except Exception as e:
            print(f"Error in send_piece: {e}")


    def close(self):
        """Clean shutdown of peer connection"""
        self.running = False
        if self.conn:
            self.conn.close()