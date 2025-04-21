# Assignment 1: Network Application Development

## Getting Started

### Prerequisites

To set up the project environment, please install the required libraries by running:
```bash
pip install -r requirements.txt
```

## Running the application
### 1. Start the tracker server by executing:
```bash
python TrackerServer.py
```
### 2. Launch the main application with:
```bash
python app.py
```
This way requires manually path input (for choosing torrent, and for choosing download location)
## Features
- Share and download file or folder (contains many files) via .torrent file
- Get scrape info about any .torrent file
## Notes
Currently the app can only run on localhost, or between peer within a machine with TrackerServer hosted in another machine. The reason are firewall rules, haven't figured out how to bypass them to make peers from different networks can communicate.
