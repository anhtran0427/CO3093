import hashlib
import math
import os
from pathlib import Path
from typing import List, Dict, Any

class Piece:
    def __init__(self, piece_id: int, data: bytes, hash_value):
        self.piece_id = piece_id
        self.data = data
        self.hash_value = hash_value
        self.length = len(data)

    def get_length(self):
        return self.length

    def get_data(self):
        return self.data

class FileManager:
    def __init__(self, save_path= None, info= None):
        if info:
            print(info)
            self.piece_length = info[b'pieceLength']
            self.total_length = info[b'length']
            self.piece_file_map = self.build_piece_file_map_from_torrent(info)
            pieces = info[b'pieces']
            self.total_pieces = len(pieces) // 40
            self.name = info[b'name'].decode('utf-8')

        else:
            self.piece_length = 524288
            self.total_length = 0
            self.piece_file_map = {}
            self.total_pieces = 0
            self.name = ''

        if save_path:
            if "." in os.path.basename(self.name):
                self.save_path = save_path
            else:
                self.save_path = f'{save_path}/{self.name}'
        else:
            if os.path.isdir(self.name):
                self.save_path = 'download'
            else:
                self.save_path = f'download/{self.name}'
        self.pieces = []

    def __len__(self):
        return len(self.pieces)

    def get_piece_length(self):
        return self.piece_length

    def get_exact_piece_length(self, index):
        total_pieces = self.get_total_pieces()
        if index < total_pieces - 1:
            return self.piece_length
        else:
            return self.total_length - (total_pieces - 1) * self.piece_length

    def split_file(self, file_path):
        self.total_length = os.path.getsize(file_path)

        try:
            with open(file_path, 'rb') as f:
                piece_id = 0
                while data := f.read(self.piece_length):
                    hash_value = hashlib.sha1(data).digest()
                    piece = Piece(piece_id=piece_id, data=data, hash_value=hash_value)
                    self.pieces.append(piece)
                    piece_id += 1
            self.total_pieces = len(self.pieces)
        except OSError:
            raise FileNotFoundError(f"Unable to open file: {file_path}")

    def split_dir(self, dir_path):

        self.total_length = os.path.getsize(dir_path)


        piece_id = 0
        buffer = b''

        try:
            # Duyệt qua tất cả các file trong thư mục theo thứ tự
            for file_path in sorted(Path(dir_path).rglob('*')):
                if file_path.is_file():
                    with open(file_path, 'rb') as f:
                        while data := f.read(self.piece_length - len(buffer)):
                            buffer += data
                            # Nếu buffer đạt kích thước piece_length, tạo mảnh mới
                            if len(buffer) == self.piece_length:
                                hash_value = hashlib.sha1(buffer).digest()  # SHA-1 với độ dài 20 bytes
                                piece = Piece(piece_id=piece_id, data=buffer, hash_value=hash_value)
                                self.pieces.append(piece)
                                piece_id += 1
                                buffer = b''  # Reset buffer

            # Xử lý phần dữ liệu còn lại nếu có
            if buffer:
                hash_value = hashlib.sha1(buffer).digest()  # Dùng SHA-1 cho mảnh cuối
                piece = Piece(piece_id=piece_id, data=buffer, hash_value=hash_value)
                self.pieces.append(piece)

            self.total_pieces = len(self.pieces)
        except OSError:
            raise FileNotFoundError(f"Unable to open directory: {dir_path}")

    def get_piece(self, index) -> Piece:
        for piece in self.pieces:
            if piece.piece_id == index:
                return piece

    def has_piece(self, piece_id):
        for piece in self.pieces:
            if piece.piece_id == piece_id:
                return True

        return False

    def get_pieces_code(self):
        result = ""
        for piece in self.pieces:
            result += f"{piece.hash_value.hex()}"

        return result

    def get_bitfield(self):

        # Calculate the number of bytes required for the bitfield
        num_bytes = (self.total_pieces + 7) // 8
        bitfield = [0] * num_bytes  # Initialize as list of zeroed bytes

        # Set each downloaded piece in the bitfield
        for piece in self.pieces:
            byte_index = piece.piece_id // 8
            bit_index = piece.piece_id % 8
            bitfield[byte_index] |= (1 << (7 - bit_index))

        # Ensure spare bits in the last byte are cleared if not a full byte
        remaining_bits = self.total_pieces % 8
        if remaining_bits != 0:
            bitfield[-1] &= (0xFF << (8 - remaining_bits))

        # Convert list to bytes
        return bytes(bitfield)

    def get_total_pieces(self):
        return self.total_pieces

    def is_interested(self, bitfield):
        num_pieces = math.ceil(self.total_length / self.piece_length)
        current_piece_ids = {piece.piece_id for piece in self.pieces}

        for piece_id in range(num_pieces):
            byte_index = piece_id // 8
            bit_index = piece_id % 8
            # Check if the piece is available in the bitfield
            if bitfield[byte_index] & (1 << (7 - bit_index)):
                # Check if we don't have this piece
                if piece_id not in current_piece_ids:
                    return True

        return False

    def add_piece(self, piece: Piece):
        for has_piece in self.pieces:
            if has_piece.piece_id == piece.piece_id:
                return
        self.pieces.append(piece)

    def check_complete(self):
        if len(self.pieces) == self.total_pieces:
            return True
        return False

    def export(self):
        # Tạo thư mục 'download' nếu chưa tồn tại

        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

        # Khởi tạo bộ đệm cho mỗi file
        file_buffers = {}
        for piece in self.pieces:
            piece_data = piece.get_data()
            piece_id = piece.piece_id

            # Lấy danh sách các file liên quan đến piece hiện tại

            mappings = self.piece_file_map[piece_id]

            for mapping in mappings:
                file_name = mapping['file']
                offset = mapping['offset']
                length = mapping['length']

                # Đảm bảo file buffer được mở và sẵn sàng để ghi
                if file_name not in file_buffers:
                    path = os.path.join(self.save_path, file_name)
                    dir_path = os.path.dirname(path)
                    if not os.path.exists(dir_path):
                        os.makedirs(dir_path)
                    file_buffers[file_name] = open(path, 'wb')

                # Ghi dữ liệu của piece vào file đích tại vị trí offset
                file_buffers[file_name].seek(offset)
                file_buffers[file_name].write(piece_data[:length])

                # Cắt dữ liệu đã ghi xong nếu còn lại trong piece
                piece_data = piece_data[length:]

        # Đóng tất cả các file buffer
        for file in file_buffers.values():
            file.close()

        print("Export completed successfully.")

    def build_piece_file_map_from_torrent(self, torrent_info):

        piece_length = torrent_info[b'pieceLength']
        pieces = torrent_info[b'pieces']
        total_pieces = len(pieces) // 40  # Mỗi piece có một SHA1 hash dài 20 bytes
        print(f"Length of pieces: {len(pieces)}")
        print(f"Total pieces calculated: {total_pieces}")
        print(f"Pieces (hex): {pieces.hex()}")
        print(f"Piece length: {piece_length}")
        piece_file_map = []

        # Kiểm tra nếu có 'files' thì là multi-file, ngược lại là single-file
        if b'files' in torrent_info:
            # Multi-file torrent
            files = [
                {'length': file[b'length'], 'path': [part.decode() for part in file[b'path']]}
                for file in torrent_info[b'files']
            ]
            print(f"Files: {files}")
            current_file_index = 0
            current_file_offset = 0

            for piece_index in range(total_pieces):
                piece_data = []
                piece_remaining = piece_length

                while piece_remaining > 0 and current_file_index < len(files):
                    current_file = files[current_file_index]
                    current_file_remaining = current_file['length'] - current_file_offset

                    if piece_remaining <= current_file_remaining:
                        piece_data.append({
                            'file': '/'.join(current_file['path']),
                            'offset': current_file_offset,
                            'length': piece_remaining
                        })
                        current_file_offset += piece_remaining
                        piece_remaining = 0
                    else:
                        piece_data.append({
                            'file': '/'.join(current_file['path']),
                            'offset': current_file_offset,
                            'length': current_file_remaining
                        })
                        piece_remaining -= current_file_remaining
                        current_file_index += 1
                        current_file_offset = 0

                piece_file_map.append(piece_data)

        else:
            # Single-file torrent
            file_name = torrent_info[b'name'].decode()
            file_length = torrent_info[b'length']
            current_file_offset = 0

            for piece_index in range(total_pieces):
                piece_data = []
                piece_remaining = piece_length

                if piece_remaining <= (file_length - current_file_offset):
                    piece_data.append({
                        'file': file_name,
                        'offset': current_file_offset,
                        'length': piece_remaining
                    })
                    current_file_offset += piece_remaining
                else:
                    piece_data.append({
                        'file': file_name,
                        'offset': current_file_offset,
                        'length': file_length - current_file_offset
                    })
                    current_file_offset += file_length - current_file_offset

                piece_file_map.append(piece_data)

        return piece_file_map