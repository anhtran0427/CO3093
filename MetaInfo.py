from datetime import datetime
from info import *
import bencodepy
class MetaInfo:
    def __init__(self, info: Info,
                 announce: str,
                 creation_date: datetime,
                 comment: str,
                 author: str) -> None:

        self.info = info
        self.announce = announce
        self.creationDate = creation_date
        self.comment = comment
        self.author = author

    def get_all_info(self) -> dict:
        return {'info': self.info.get_all_info(),
                'announce': self.announce,
                'creationDate': str(self.creationDate),
                'comment': self.comment,
                'author': self.author}

    def get_bencode(self):
        """
        Create encoded bencode object.
        :return: encoded bencode object
        """
        info_dict = self.get_all_info()
        encoded = bencodepy.encode(info_dict)
        return encoded


