import User
import uuid

def main():
    user = User.User(str(uuid.uuid4()), "Anonymous")
    x = int(input("Enter 1 to share, 2 to download, 3 to get scrape info of the file, 4 to stop peer with peer_id, 5 to stop all: "))
    if x == 1:
        path = input("Nhập vào đường dẫn đến file hoặc directory: ")
        magnet_link = user.share(path)
        print("Magnet link:", magnet_link)
    elif x == 2:
        file = input("Nhập vào torrent file hoặc magnet link: ")
        user.download(file)
    elif x == 3:
        file = input("Nhập vào torrent file hoặc magnet link: ")
        user.scrape_tracker(file)
    elif x == 4:
        peer_id = int(input("Enter peer ID: "))
        user.stop(peer_id)
    elif x == 5:
        user.stop_all()
    else:
        print("Invalid input")
main()
