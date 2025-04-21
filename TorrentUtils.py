import bencodepy
import hashlib
import base64
import urllib.parse


class TorrentUtils:

    @staticmethod
    def get_info_from_file(torrent_file):
        with open(torrent_file, 'rb') as file:
            torrent_content = bencodepy.decode(file.read())
        return torrent_content

    @staticmethod
    def get_info_from_magnet(magnet_link):
        # Phân tích URL từ magnet link
        parsed_url = urllib.parse.urlparse(magnet_link)
        # if parsed_url.scheme != 'magnet':
        #     raise ValueError("Link không phải là magnet link hợp lệ.")

        # Tách các tham số từ magnet link
        params = urllib.parse.parse_qs(parsed_url.query)

        # Trích xuất từng thông tin
        info_hash = bytes.fromhex(params.get('xt', [''])[0].split(':')[-1])  # Thông tin hash
        name = params.get('dn', [''])[0]  # Tên file/torrent
        length = int(params.get('xl', [''])[0])  # Kích thước file
        trackers = params.get('tr', [])  # Danh sách trackers

        # Đưa ra các thông tin đã trích xuất
        return {
            "info_hash": info_hash,
            "name": name,
            "length": int(length) if length else None,
            "trackers": trackers
        }

    @staticmethod
    def create_torrent_file(encoded_data, file_path):

        with open(file_path, 'wb') as f:
            f.write(encoded_data)

    @staticmethod
    def make_magnet_from_file(file_path):
        with open(file_path, 'rb') as f:
            file_data = f.read()
        return TorrentUtils.make_magnet_from_bencode(file_data)

    @staticmethod
    def make_magnet_from_bencode(bencode_data):
        """
        Create magnet link from torrent file.
        :param bencode_data: bencoded torrent file data
        :return: magnet_link
        """
        # Decode the bencoded data
        metadata = bencodepy.decode(bencode_data)
        subj = metadata[b'info']
        
        # If torrent is a directory, 'files' will exist instead of 'length'
        if b'files' in subj:
            # Calculate the total length of all files in the directory
            total_length = sum(file[b'length'] for file in subj[b'files'])
        else:
            # If it's not a directory, use the 'length' of the single file
            total_length = subj[b'length']

        # Encode the 'info' part and generate the SHA-1 hash
        hash_contents = bencodepy.encode(subj)
        info_hash = hashlib.sha1(hash_contents).digest()
        print(f"info_hash from magnet: {info_hash}")
        info_hash_hex = info_hash.hex()

        # Get the name of the directory or file
        name = subj[b'name'].decode()

        # Handle multiple trackers if present, and build tracker parameters
        trackers = metadata.get(b'announce-list', [[metadata.get(b'announce', b'')]])
        tracker_params = ''
        for tracker_group in trackers:
            for tracker in tracker_group:
                tracker_url = tracker.decode()
                tracker_params += '&tr=' + urllib.parse.quote(tracker_url)
        
        # Return the final magnet link
        # NOTE: info_hash_hex is NOT URL-encoded
        return 'magnet:?' \
            + 'xt=urn:btih:' + info_hash_hex \
            + '&dn=' + urllib.parse.quote(name) \
            + tracker_params \
            + '&xl=' + str(total_length)
