from datetime import datetime
import os

from threading import Thread


from FileManager import FileManager
from info import *
from MetaInfo import MetaInfo
from TorrentUtils import TorrentUtils
from Peer import Peer
import socket

class Status:
    def __init__(self):
        self.connected = 1
        self.download_speed = 0.0
        self.upload_speed = 0.0
        self.peer_count = 0


class User:
    def __init__(self, userId, name: str = "Anonymous"):
        self.name = name
        self.peers: dict[str, Peer] = {}
        self.threads: dict[str, Thread] = {}
        self.userId = userId

    def download(self, file_path, save_path):
        # if self.isTorrent(file):
        info_torrent = TorrentUtils.get_info_from_file(file_path)
        # else:
        #     info = TorrentUtils.get_info_from_magnet(file)

        ip, port = self._get_ip_port()
        file_manager = FileManager(save_path, info_torrent[b'info'])

        with open(file_path, 'rb') as file:
            bencode_info = file.read()
        magnet = TorrentUtils.make_magnet_from_bencode(bencode_info)
        info = TorrentUtils.get_info_from_magnet(magnet)

        peer = Peer(ip, port, info, file_manager)
        print(f"Peer ID: {peer.peer_id}")
        thread = Thread(target=peer.download)

        self.peers.update({peer.peer_id: peer})
        self.threads.update({peer.peer_id: thread})

        thread.start()
        return peer.peer_id


    def share(self, path):

        file_manager = FileManager()

        if os.path.isdir(path):
            file_manager.split_dir(path)
            magnet_link = self._input_directory(path, file_manager)
        elif os.path.isfile(path):
            file_manager.split_file(path)
            magnet_link = self._input_file(path, file_manager)
        else:
            raise "Invalid path"

        print(f"Magnet link: {magnet_link}")

        info = TorrentUtils.get_info_from_magnet(magnet_link)
        ip, port = self._get_ip_port()

        peer = Peer(ip, port, info, file_manager)
        print(f"Peer ID: {peer.peer_id}")
        thread = Thread(target=peer.upload)

        self.peers.update({peer.peer_id: peer})
        self.threads.update({peer.peer_id: thread})

        thread.start()
        return peer.peer_id


    def scrape_tracker(self, file):

        # if self.isTorrent(file):
        info_torrent = TorrentUtils.get_info_from_file(file)
        # else:
        #     info = TorrentUtils.get_info_from_magnet(file)

        ip, port = self._get_ip_port()
        file_manager = FileManager(info=info_torrent[b'info'])

        with open(file, 'rb') as file:
            bencode_info = file.read()
        magnet = TorrentUtils.make_magnet_from_bencode(bencode_info)
        info = TorrentUtils.get_info_from_magnet(magnet)

        peer = Peer(ip, port, info, file_manager)
        thread = Thread(target=peer.scrape_tracker)


        self.peers.update({peer.peer_id: peer})
        self.threads.update({peer.peer_id: thread})

        thread.start()
        return peer.peer_id


    def stop(self, peer_id):
        self.peers[peer_id].stop()
        self.peers.pop(peer_id)

        self.threads[peer_id].join()
        self.threads.pop(peer_id)

    def stop_all(self):

        for peer_id in self.peers:
            self.peers[peer_id].stop()
            self.peers.pop(peer_id)

        for peer_id in self.threads:
            self.threads[peer_id].join()
            self.threads.pop(peer_id)


    def _input_directory(self, dir_path, file_manager):
        """
        Cho phép người dùng nhập vào một directory và chuyển nó thành bencode.
        """
        # Lấy các file trong directory và chuyển thành danh sách File
        directory_name = os.path.basename(os.path.normpath(dir_path))
        files = []
        for root, dirs, file_names in os.walk(dir_path):
            for file_name in file_names:
                file_path = os.path.join(root, file_name)
                file_size = os.path.getsize(file_path)
                file_relative_path = os.path.relpath(file_path, dir_path).split(os.sep)
                files.append(File(file_size, file_relative_path))

        # Tạo InfoMultiFile cho directory
        piece_length = file_manager.get_piece_length()
        pieces = file_manager.get_pieces_code()
        info = InfoMultiFile(piece_length, pieces, os.path.basename(dir_path), files)

        # Tạo MetaInfo cho torrent file
        meta_info = MetaInfo(info, 'http://localhost:5050', datetime.now(), 'No comment', self.name)
        encoded = meta_info.get_bencode()

        torrent_dir = "Torrents"
        full_path = os.path.join(torrent_dir, f'{directory_name}.torrent')
        if not os.path.exists(torrent_dir):
            os.makedirs(torrent_dir)
        TorrentUtils.create_torrent_file(encoded, full_path)

        magnet_link = TorrentUtils.make_magnet_from_bencode(encoded)

        return magnet_link



    def _input_file(self, file_path, file_manager):
        """
        Cho phép người dùng nhập vào một file và chuyển nó thành bencode.
        """
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # Tạo InfoSingleFile cho file
        piece_length = file_manager.get_piece_length()
        pieces = file_manager.get_pieces_code()
        info = InfoSingleFile(piece_length, pieces, file_name, file_size)

        # Tạo MetaInfo cho torrent file
        meta_info = MetaInfo(info, 'http://localhost:5050', datetime.now(), 'No comment', self.name)
        encoded = meta_info.get_bencode()

        torrent_dir = "Torrents"
        full_path = os.path.join(torrent_dir, f'{file_name}.torrent')
        if not os.path.exists(torrent_dir):
            os.makedirs(torrent_dir)
        TorrentUtils.create_torrent_file(encoded, full_path)

        magnet_link = TorrentUtils.make_magnet_from_bencode(encoded)

        return magnet_link


    def _get_ip_port(self):
        """Lấy địa chỉ IP và tìm một cổng trống cho Peer."""
        # Lấy địa chỉ IP của máy người dùng
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)

        # Tìm một port trống để dùng
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))  # Bind tới bất kỳ cổng trống nào (0 là chỉ định hệ thống tự tìm port)
            port = s.getsockname()[1]  # Lấy port đã bind
        return ip_address, port

    def isTorrent(self, file):
        if not file.endswith(".torrent"):
            return False

        try:
            with open(file, "rb") as f:
                content = f.read()
                # Kiểm tra các từ khóa Bencode đặc trưng
                if b"announce" in content and b"info" in content and b"pieces" in content:
                    return True
        except Exception as e:
            print("Error reading file:", e)

        return False

    def ban_peer(self, peer_id, peer_ip):
        pass

    def get_peers(self):
        return self.peers

    def get_statistics(self):
        """

        :return:
        {
        'connected': Boolean,
        'download_speed': float,
        'upload_speed': float,
        'peer_count': int
         }
        """
        status = Status()
        return status

    def get_transfer_information(self, peer_id):
        return self.peers[peer_id].get_transfer_information()

    def get_scrape_information(self, peer_id):
        return self.peers[peer_id].get_scrape_response()

    def get_file_size(self, transfer_id):
        """Get the total file size for a transfer"""
        # Return the file size in bytes
        return self.peers[transfer_id].total_length