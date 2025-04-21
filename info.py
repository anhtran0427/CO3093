from typing import List
from abc import ABC, abstractmethod

class Info(ABC):
    def __init__(self, pieceLength: int, pieces):
        self.pieceLength = pieceLength  #number of bytes in each piece
        self.pieces = pieces            #string consisting of the concatenation of all 20-byte SHA1 hash values, one per piece (byte string, i.e. not urlencoded)

    @abstractmethod
    def get_all_info(self) -> dict:
        return {'pieceLength':self.pieceLength, 'pieces':self.pieces}

class InfoSingleFile(Info):
    def __init__(self, pieceLength, pieces, name: str, length: int):
        super().__init__(pieceLength, pieces)
        self.name = name                #the filename
        self.length = length            #length of the file in bytes

    def get_all_info(self) -> dict:
        dic = super().get_all_info()
        dic.update({'name':self.name, 'length':self.length})
        return dic

    def get_total_length(self) -> int:
        return self.length

class File:
    def __init__(self, length, path):
        self.length = length            #length of the file in bytes
        self.path = path                #a list containing one or more string elements that together represent the path and filename
                                        #"dir1/dir2/file.ext" -> l4:dir14:dir28:file.exte

    def get_all_info(self) -> dict:
        return {'length':self.length, 'path':self.path}

class InfoMultiFile(Info):
    def __init__(self, pieceLength, pieces, name, files: List[File]):
        super().__init__(pieceLength, pieces)
        self.name = name                #the name of the directory
        self.files = files              #a list of dictionaries

    def get_total_length(self):
        total_length = 0
        for file in self.files:
            total_length += file.length

        return total_length

    def get_all_info(self) -> dict:
        dic = super().get_all_info()
        length = self.get_total_length()
        dic.update({'name':self.name, 'length': length, 'files':[file.get_all_info() for file in self.files]})
        return dic

