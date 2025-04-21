import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import uuid
from User import User
from typing import Optional
import logging
from datetime import datetime
import json
import os
from dataclasses import dataclass
from enum import Enum
import json as js
import time
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='bittorrent_app.log'
)


class TransferStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class ScrapeRecord:
    id: str
    path: str
    start_time: datetime


@dataclass
class TransferRecord:
    id: str
    type: str  # 'upload' or 'download'
    path: str
    status: TransferStatus
    start_time: datetime
    completion_time: Optional[datetime] = None
    progress: float = 0.0
    peers: int = 0
    speed: float = 0.0
    elapsed_time: str = "00:00:00"


class BitTorrentApp:
    def __init__(self, root):
        self.scrapes_tree = None
        self.status_labels = None
        self.peers_tree = None
        self.status_tab = None
        self.peers_tab = None
        self.transfers_tab = None
        self.notebook = None
        self.main_container = None
        self.password_entry = None
        self.username_entry = None
        self.login_frame = None
        self.help_menu = None
        self.view_menu = None
        self.file_menu = None
        self.menubar = None
        self.style = None
        self.transfers_tree = None
        self.user: Optional[User] = None
        self.root = root
        self.transfers: dict[str, TransferRecord] = {}
        self.scrapes: dict[str, ScrapeRecord] = {}
        self.current_theme = "light"
        self.setup_window()
        self.load_settings()
        self.create_login_screen()

    def setup_window(self):
        """Initialize main window settings"""
        self.root.title("BitTorrent Application")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)

        # Create styles
        self.style = ttk.Style()
        self.create_styles()

        # Add menu bar
        self.create_menu_bar()

    def create_styles(self):
        """Set up custom styles for the application"""
        self.style.configure(
            "Custom.TButton",
            padding=10,
            font=("Arial", 10)
        )
        self.style.configure(
            "Header.TLabel",
            font=("Arial", 16, "bold"),
            padding=10
        )

    def create_menu_bar(self):
        """Create the application menu bar"""
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        # File menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Settings", command=self.show_settings_dialog)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.quit_application)

        # View menu
        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="View", menu=self.view_menu)
        self.view_menu.add_command(label="Toggle Theme", command=self.toggle_theme)

        # Help menu
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="About", command=self.show_about_dialog)
        self.help_menu.add_command(label="View Logs", command=self.show_logs_dialog)

    def show_settings_dialog(self):
        """Show settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)

        # Create settings form
        form = ttk.Frame(settings_window, padding="10")
        form.pack(fill="both", expand=True)

        # Download speed limit
        ttk.Label(form, text="Max Download Speed (KB/s):").grid(row=0, column=0, pady=5)
        download_speed = ttk.Entry(form)
        download_speed.insert(0, str(self.settings["max_download_speed"]))
        download_speed.grid(row=0, column=1, pady=5)

        # Upload speed limit
        ttk.Label(form, text="Max Upload Speed (KB/s):").grid(row=1, column=0, pady=5)
        upload_speed = ttk.Entry(form)
        upload_speed.insert(0, str(self.settings["max_upload_speed"]))
        upload_speed.grid(row=1, column=1, pady=5)

        # Port
        ttk.Label(form, text="Port:").grid(row=2, column=0, pady=5)
        port = ttk.Entry(form)
        port.insert(0, str(self.settings["port"]))
        port.grid(row=2, column=1, pady=5)

        def save_settings():
            try:
                self.settings.update({
                    "max_download_speed": int(download_speed.get()),
                    "max_upload_speed": int(upload_speed.get()),
                    "port": int(port.get()),
                })
                self.save_settings()
                settings_window.destroy()
                messagebox.showinfo("Success", "Settings saved successfully")
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers")

        ttk.Button(form, text="Save", command=save_settings).grid(row=4, column=0, columnspan=2, pady=20)

    def show_about_dialog(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About",
            "BitTorrent Application\nVersion 1.0.0\n\nA modern BitTorrent client with advanced features."
        )

    def show_logs_dialog(self):
        """Show log viewer window"""
        log_window = tk.Toplevel(self.root)
        log_window.title("Logs")
        log_window.geometry("600x400")

        # Create text widget with scrollbar
        text_widget = tk.Text(log_window, wrap="word")
        scrollbar = ttk.Scrollbar(log_window, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        # Pack widgets
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        try:
            with open('bittorrent_app.log', 'r') as f:
                text_widget.insert("1.0", f.read())
            text_widget.configure(state="disabled")
        except Exception as e:
            text_widget.insert("1.0", f"Failed to load log file: {str(e)}")
            text_widget.configure(state="disabled")

    def quit_application(self):
        """Safely quit the application"""
        if messagebox.askyesno("Quit", "Are you sure you want to quit?"):
            try:
                self.save_settings()
                if self.user:
                    self.user.stop_all()
            except Exception as e:
                logging.error(f"Error during shutdown: {e}")
            finally:
                self.root.quit()

    def save_login_state(self, username: str):
        """Save login state for 'remember me' functionality"""
        try:
            with open('login_state.json', 'w') as f:
                json.dump({"username": username}, f)
        except Exception as e:
            logging.error(f"Failed to save login state: {e}")

    def load_login_state(self) -> Optional[str]:
        """Load saved login state"""
        try:
            if os.path.exists('login_state.json'):
                with open('login_state.json', 'r') as f:
                    data = json.load(f)
                    return data.get("username")
        except Exception as e:
            logging.error(f"Failed to load login state: {e}")
        return None

    def load_settings(self):
        """Load application settings from file"""
        try:
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    self.settings = json.load(f)
            else:
                self.settings = self.get_default_settings()
                self.save_settings()
        except Exception as e:
            logging.error(f"Failed to load settings: {e}")
            self.settings = self.get_default_settings()

    def get_default_settings(self):
        """Return default application settings"""
        return {
            "theme": "light",
            "max_upload_speed": 0,  # 0 means unlimited
            "max_download_speed": 0,
            "default_save_path": os.path.expanduser("~/Downloads"),
            "max_connections": 200,
            "port": 6881
        }

    def save_settings(self):
        """Save current settings to file"""
        try:
            with open('settings.json', 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")
            messagebox.showerror("Error", "Failed to save settings")

    def create_login_screen(self):
        """Create enhanced login screen"""
        self.login_frame = ttk.Frame(self.root)
        self.login_frame.pack(fill="both", expand=True)

        # Center frame for login elements
        center_frame = ttk.Frame(self.login_frame)
        center_frame.place(relx=0.5, rely=0.5, anchor="center")

        # Login header
        login_label = ttk.Label(
            center_frame,
            text="BitTorrent Login",
            style="Header.TLabel"
        )
        login_label.pack(pady=20)

        # Username field
        username_frame = ttk.Frame(center_frame)
        username_frame.pack(fill="x", pady=5)
        username_label = ttk.Label(username_frame, text="Username:")
        username_label.pack(side="left")
        self.username_entry = ttk.Entry(username_frame)
        self.username_entry.pack(side="left", padx=5)

        # Password field
        password_frame = ttk.Frame(center_frame)
        password_frame.pack(fill="x", pady=5)
        password_label = ttk.Label(password_frame, text="Password:")
        password_label.pack(side="left")
        self.password_entry = ttk.Entry(password_frame, show="*")
        self.password_entry.pack(side="left", padx=5)

        # Remember me checkbox
        self.remember_var = tk.BooleanVar()
        remember_checkbox = ttk.Checkbutton(
            center_frame,
            text="Remember me",
            variable=self.remember_var
        )
        remember_checkbox.pack(pady=10)

        # Login button
        login_button = ttk.Button(
            center_frame,
            text="Login",
            command=self.login,
            style="Custom.TButton"
        )
        login_button.pack(pady=20)

        # Bind Enter key to login
        self.root.bind('<Return>', lambda e: self.login())

    def login(self):
        """Handle login with improved error handling"""
        password = self.password_entry.get()

        try:

            username = self.username_entry.get().strip()
            if not username or not password:
                raise ValueError("Username and password are required")

            # Here you would typically verify credentials with your User library
            self.user = User(str(uuid.uuid4()), username)

            # Save login state if remember me is checked
            if self.remember_var.get():
                self.save_login_state(username)

            logging.info(f"User {username} logged in successfully")
            messagebox.showinfo("Success", f"Welcome back, {username}!")

            self.login_frame.destroy()
            self.create_main_interface()

        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            logging.error(f"Login failed: {e}")
            messagebox.showerror("Error", "Login failed. Please try again.")

    def create_main_interface(self):
        """Create enhanced main interface"""
        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True)

        # Create and pack the notebook
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Create tabs
        self.transfers_tab = self.create_transfers_tab()
        self.peers_tab = self.create_peers_tab()
        self.status_tab = self.create_status_tab()
        self.scrape_tab = self.create_scrape_tab()
        # Add tabs to notebook
        self.notebook.add(self.transfers_tab, text="Transfers")
        self.notebook.add(self.peers_tab, text="Peers")
        self.notebook.add(self.status_tab, text="Status")
        self.notebook.add(self.scrape_tab, text="Scrape")
        # Create status bar
        self.create_status_bar()

    def create_transfers_tab(self):
        """Create enhanced transfers tab with table view"""
        frame = ttk.Frame(self.notebook)

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=5, pady=5)

        ttk.Button(
            toolbar,
            text="Share",
            command=self.share
        ).pack(side="left", padx=2)

        ttk.Button(
            toolbar,
            text="Add Torrent",
            command=self.add_torrent
        ).pack(side="left", padx=2)

        # Transfers table
        columns = ("Name", "Status", "Progress", "Speed", "Peers", "Time")
        self.transfers_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings"
        )

        # Set column headings
        for col in columns:
            self.transfers_tree.heading(col, text=col)
            self.transfers_tree.column(col, width=100)

        # Add scrollbars
        y_scroll = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.transfers_tree.yview
        )
        x_scroll = ttk.Scrollbar(
            frame,
            orient="horizontal",
            command=self.transfers_tree.xview
        )

        self.transfers_tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        # Pack elements
        self.transfers_tree.pack(fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")
        x_scroll.pack(side="bottom", fill="x")

        return frame

    def create_scrape_tab(self):
        frame = ttk.Frame(self.notebook)

        # Peers list
        columns = ("ID", "Name", "Tracker Server", "Peers")
        self.scrapes_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings"
        )

        for col in columns:
            self.scrapes_tree.heading(col, text=col)
            self.scrapes_tree.column(col, width=100)

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=5, pady=5)

        ttk.Button(
            toolbar,
            text="Scrape",
            command=self.scrape
        ).pack(side="left", padx=2)


        # Pack elements
        self.scrapes_tree.pack(fill="both", expand=True)

        return frame

    def create_peers_tab(self):
        """Create enhanced peers management tab"""
        frame = ttk.Frame(self.notebook)

        # Peers list
        columns = ("ID", "IP", "Port", "Client", "Flags", "Progress")
        self.peers_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings"
        )

        for col in columns:
            self.peers_tree.heading(col, text=col)
            self.peers_tree.column(col, width=100)

        # Control buttons
        controls = ttk.Frame(frame)
        controls.pack(fill="x", padx=5, pady=5)

        ttk.Button(
            controls,
            text="Disconnect Peer",
            command=self.disconnect_peer
        ).pack(side="left", padx=2)

        ttk.Button(
            controls,
            text="Ban Peer",
            command=self.ban_peer
        ).pack(side="left", padx=2)

        # Pack elements
        self.peers_tree.pack(fill="both", expand=True)

        return frame

    def create_status_tab(self):
        """Create enhanced status and history tab"""
        frame = ttk.Frame(self.notebook)

        # Statistics panel
        stats_frame = ttk.LabelFrame(frame, text="Statistics")
        stats_frame.pack(fill="x", padx=5, pady=5)

        self.stats_labels = {}
        stats = [
            "Download Speed", "Upload Speed",
            "Downloaded", "Uploaded",
            "Peers Connected", "Share Ratio"
        ]

        for i, stat in enumerate(stats):
            row = i // 2
            col = i % 2
            ttk.Label(
                stats_frame,
                text=f"{stat}:"
            ).grid(row=row, column=col * 2, padx=5, pady=2, sticky="e")

            self.stats_labels[stat] = ttk.Label(stats_frame, text="0")
            self.stats_labels[stat].grid(
                row=row,
                column=col * 2 + 1,
                padx=5,
                pady=2,
                sticky="w"
            )

        # Activity log
        log_frame = ttk.LabelFrame(frame, text="Activity Log")
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.log_text = tk.Text(
            log_frame,
            height=10,
            wrap="word",
            state="disabled"
        )
        log_scroll = ttk.Scrollbar(
            log_frame,
            command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        return frame

    def create_status_bar(self):
        """Create status bar with key information"""
        self.status_bar = ttk.Frame(self.main_container)
        self.status_bar.pack(fill="x", side="bottom")

        # Status labels
        self.status_labels = {}
        status_items = [
            "Connection Status",
            "Download Speed",
            "Upload Speed",
            "Peers"
        ]

        for item in status_items:
            frame = ttk.Frame(self.status_bar)
            frame.pack(side="left", padx=5)

            ttk.Label(
                frame,
                text=f"{item}:"
            ).pack(side="left", padx=2)

            self.status_labels[item] = ttk.Label(frame, text="--")
            self.status_labels[item].pack(side="left")

    def share(self):
        """Start to share a file or folder"""

        # Tạo cửa sổ con
        popup = tk.Toplevel(self.root)
        popup.title("Share File or Folder")
        popup.geometry("250x150")

        # Danh sách các lựa chọn cho combobox
        options = ["Share file", "Share Folder"]

        # Tạo combobox trong popup
        combobox = ttk.Combobox(popup, values=options)
        combobox.pack(pady=10)
        combobox.current(0)  # Thiết lập giá trị mặc định

        def get_selection():
            selected_value = combobox.get()

            popup.destroy()

            if selected_value == "Share file":
                path = filedialog.askopenfilename(
                    title="Select File",
                )
            else:
                path = filedialog.askdirectory(
                    title="Select Directory",
                )

            # Start the download using User library
            peer_id = self.user.share(path)

            self.transfers[peer_id] = TransferRecord(
                id=peer_id,
                type="upload",
                path=path,
                status=TransferStatus.PENDING,
                start_time=datetime.now()
            )


            self.update_transfers_view()
            self.log_activity(f"Started sharing {os.path.basename(path)}")


        # Nút để xác nhận lựa chọn
        confirm_button = tk.Button(popup, text="Confirm", command=get_selection)
        confirm_button.pack(pady=10)

    def scrape(self):

        try:
            file_path = filedialog.askopenfilename(
                title="Select Torrent File",
                filetypes=[("Torrent files", "*.torrent")]
            )

            scrape_id = self.user.scrape_tracker(file_path)

            self.scrapes[scrape_id] = ScrapeRecord(
                id=scrape_id,
                path=file_path,
                start_time=datetime.now()
            )

            self.update_scrape_view()
            self.update_transfers_view()
            self.log_activity(f"Started scraping {os.path.basename(file_path)}")
        except Exception as e:
            logging.error(f"Failed to scrape: {e}")
            messagebox.showerror("Error", "Failed to scrape")

    def add_torrent(self):
        """Add a new torrent file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Select Torrent File",
                filetypes=[("Torrent files", "*.torrent")]
            )

            if file_path:
                save_path = filedialog.askdirectory(
                    title="Select Save Location",
                    initialdir=self.settings["default_save_path"]
                )

                if save_path:
                    # Start the download using User library
                    transfer_id = self.user.download(file_path, save_path)

                    self.transfers[transfer_id] = TransferRecord(
                        id=transfer_id,
                        type="download",
                        path=file_path,
                        status=TransferStatus.PENDING,
                        start_time=datetime.now()
                    )


                    self.update_transfers_view()
                    self.log_activity(f"Started downloading {os.path.basename(file_path)}")

        except Exception as e:
            logging.error(f"Failed to add torrent: {e}")
            messagebox.showerror("Error", "Failed to add torrent")

    # def add_magnet(self):
    #     """Add a new magnet link"""
    #     try:
    #         magnet_link = simpledialog.askstring(
    #             "Add Magnet Link",
    #             "Enter magnet link:",
    #             parent=self.root
    #         )
    #
    #         if magnet_link:
    #             save_path = filedialog.askdirectory(
    #                 title="Select Save Location",
    #                 initialdir=self.settings["default_save_path"]
    #             )
    #
    #             if save_path:
    #                 transfer_id = str(uuid.uuid4())
    #                 self.transfers[transfer_id] = TransferRecord(
    #                     id=transfer_id,
    #                     type="download",
    #                     path=magnet_link,
    #                     status=TransferStatus.PENDING,
    #                     start_time=datetime.now()
    #                 )
    #
    #                 # Start the download using User library
    #                 self.user.download(magnet_link, save_path)
    #                 self.update_transfers_view()
    #                 self.log_activity("Started downloading from magnet link")
    #
    #     except Exception as e:
    #         logging.error(f"Failed to add magnet link: {e}")
    #         messagebox.showerror("Error", "Failed to add magnet link")

    def update_transfers_view(self):
        """Update the transfers treeview with current transfer information"""
        if self.transfers_tree is None:
            return
        try:
            # Clear existing items
            for item in self.transfers_tree.get_children():
                self.transfers_tree.delete(item)

            # Add current transfers
            for transfer in self.transfers.values():
                value = self.user.get_transfer_information(transfer.id)
                
                # Calculate elapsed time only if transfer is not complete
                if value['progress'] >= 100.0 and transfer.completion_time is None:
                    transfer.completion_time = datetime.now()
                    transfer.status = TransferStatus.COMPLETED
                
                if transfer.completion_time:
                    # Use the final elapsed time for completed transfers
                    elapsed = transfer.completion_time - transfer.start_time
                    speed = 0.0  # Speed is 0 for completed transfers
                else:
                    # Calculate current elapsed time and speed for ongoing transfers
                    elapsed = datetime.now() - transfer.start_time
                    
                    # Initialize speed tracking attributes if they don't exist
                    if not hasattr(transfer, 'last_progress_check'):
                        transfer.last_progress_check = time.time()
                        transfer.last_progress = value['progress']
                        transfer.current_speed = 0.0
                    
                    # Calculate speed
                    current_time = time.time()
                    time_diff = current_time - transfer.last_progress_check
                    
                    if time_diff >= 1.0:  # Update speed every second
                        try:
                            progress_diff = value['progress'] - transfer.last_progress
                            # Convert progress difference to bytes and then to KB/s
                            bytes_transferred = (progress_diff / 100.0) * self.user.get_file_size(transfer.id)
                            transfer.current_speed = (bytes_transferred / 1024) / time_diff
                        except (AttributeError, TypeError):
                            # If there's any error calculating speed, use 0
                            transfer.current_speed = 0.0
                        
                        # Update progress tracking
                        transfer.last_progress_check = current_time
                        transfer.last_progress = value['progress']
                
                hours = int(elapsed.total_seconds() // 3600)
                minutes = int((elapsed.total_seconds() % 3600) // 60)
                seconds = int(elapsed.total_seconds() % 60)
                elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                
                # Get speed value safely
                speed_value = getattr(transfer, 'current_speed', 0.0)
                
                self.transfers_tree.insert(
                    "",
                    "end",
                    values=(
                        os.path.basename(transfer.path),
                        transfer.status.value,
                        f"{value['progress']:.1f}%",
                        f"{speed_value:.1f} KB/s",  # Display speed in KB/s
                        value['peers'] + 1,
                        elapsed_str
                    )
                )
        except Exception as e:
            logging.error(f"Failed to update transfers view: {e}")
    def disconnect_peer(self):
        """Disconnect selected peer"""
        try:
            selected = self.peers_tree.selection()

            if not selected:
                messagebox.showwarning(
                    "Warning",
                    "Please select a peer to disconnect"
                )
                return

            peer_id = self.peers_tree.item(selected[0])['values'][0]

            if peer_id in self.transfers:
                self.transfers.pop(peer_id)
            elif peer_id in self.scrapes:
                self.scrapes.pop(peer_id)

            self.user.stop(peer_id)

            self.log_activity(f"Disconnected peer: {peer_id}")
            self.update_peers_view()
            self.update_transfers_view()

        except Exception as e:
            logging.error(f"Failed to disconnect peer: {e}")
            messagebox.showerror("Error", "Failed to disconnect peer")

    def ban_peer(self):
        """Ban selected peer"""
        try:
            selected = self.peers_tree.selection()
            if not selected:
                messagebox.showwarning(
                    "Warning",
                    "Please select a peer to ban"
                )
                return

            peer_info = self.peers_tree.item(selected[0])['values']
            peer_id = peer_info[0]
            peer_ip = peer_info[1]

            if messagebox.askyesno(
                    "Confirm Ban",
                    f"Are you sure you want to ban peer {peer_ip}?"
            ):
                # Add to banned peers list (implement in User library)
                self.user.ban_peer(peer_id, peer_ip)
                self.log_activity(f"Banned peer: {peer_ip}")
                self.update_peers_view()

        except Exception as e:
            logging.error(f"Failed to ban peer: {e}")
            messagebox.showerror("Error", "Failed to ban peer")

    def update_peers_view(self):
        """Update the peers treeview with current peer information"""
        if self.peers_tree is None:
            return

        try:
            selected_peer_ids = [
                self.peers_tree.item(item)['values'][0]  # Lấy peer_id từ cột đầu tiên (giả sử là cột đầu tiên)
                for item in self.peers_tree.selection()
            ]

            # Clear existing items
            for item in self.peers_tree.get_children():
                self.peers_tree.delete(item)

            # Get current peers from User library
            peers = self.user.get_peers()  # Implement this in User library

            # Add current peers
            for peer_id in peers:
                value = peers[peer_id].get_transfer_information()
                new_item = self.peers_tree.insert(
                    "",
                    "end",
                    values=(
                        peer_id,
                        peers[peer_id].peer_ip,
                        peers[peer_id].peer_port,
                        value['peers'],
                        # peers[peer_id].flags,
                        "STARTED",
                        f"{value['progress']:.1f}%"
                    ),

                )
                if peer_id in selected_peer_ids:
                    self.peers_tree.selection_add(new_item)

        except Exception as e:
            logging.error(f"Failed to update peers view: {e}")

    def log_activity(self, message: str):
        """Add message to activity log with timestamp"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"[{timestamp}] {message}\n"

            self.log_text.configure(state="normal")
            self.log_text.insert("end", log_message)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

            # Also log to file
            logging.info(message)

        except Exception as e:
            logging.error(f"Failed to log activity: {e}")

    def update_status_bar(self):
        """Update status bar information"""
        if self.user is None:
            return
        try:
            # Get current statistics from User library
            stats = self.user.get_statistics()  # Implement this in User library

            self.status_labels["Connection Status"].config(
                text="Connected" if stats.connected else "Disconnected"
            )
            self.status_labels["Download Speed"].config(
                text=f"{stats.download_speed:.1f} KB/s"
            )
            self.status_labels["Upload Speed"].config(
                text=f"{stats.upload_speed:.1f} KB/s"
            )
            self.status_labels["Peers"].config(
                text=str(stats.peer_count)
            )

        except Exception as e:
            logging.error(f"Failed to update status bar: {e}")

    def update_scrape_view(self):
        if self.scrapes_tree is None:
            return
        try:
            # Clear existing items
            for item in self.scrapes_tree.get_children():
                self.scrapes_tree.delete(item)

            # Add current transfers
            for scrape in self.scrapes.values():
                value = self.user.get_scrape_information(scrape.id)
                if value == "No information":
                    continue
                else:
                    value = js.loads(value)
                    self.scrapes_tree.insert(
                        "",
                        "end",
                        values=(
                            scrape.id,
                            os.path.basename(scrape.path),
                            value["tracker_id"],
                            value["total_peers"]
                        )
                    )
        except Exception as e:
            logging.error(f"Failed to update transfers view: {e}")




    def show_settings(self):
        """Show settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)

        # Create settings form
        form = ttk.Frame(settings_window, padding="10")
        form.pack(fill="both", expand=True)

        # Download speed limit
        ttk.Label(form, text="Max Download Speed (KB/s):").grid(row=0, column=0, pady=5)
        download_speed = ttk.Entry(form)
        download_speed.insert(0, str(self.settings["max_download_speed"]))
        download_speed.grid(row=0, column=1, pady=5)

        # Upload speed limit
        ttk.Label(form, text="Max Upload Speed (KB/s):").grid(row=1, column=0, pady=5)
        upload_speed = ttk.Entry(form)
        upload_speed.insert(0, str(self.settings["max_upload_speed"]))
        upload_speed.grid(row=1, column=1, pady=5)

        # Port
        ttk.Label(form, text="Port:").grid(row=2, column=0, pady=5)
        port = ttk.Entry(form)
        port.insert(0, str(self.settings["port"]))
        port.grid(row=2, column=1, pady=5)

        # Save location
        ttk.Label(form, text="Default Save Location:").grid(row=3, column=0, pady=5)
        save_path = ttk.Entry(form)
        save_path.insert(0, self.settings["default_save_path"])
        save_path.grid(row=3, column=1, pady=5)

        # Browse button
        ttk.Button(
            form,
            text="Browse",
            command=lambda: save_path.insert(0, filedialog.askdirectory())
        ).grid(row=3, column=2, pady=5)

        # Save button
        def save_settings():
            try:
                self.settings.update({
                    "max_download_speed": int(download_speed.get()),
                    "max_upload_speed": int(upload_speed.get()),
                    "port": int(port.get()),
                    "default_save_path": save_path.get()
                })
                self.save_settings()
                settings_window.destroy()
                messagebox.showinfo("Success", "Settings saved successfully")
            except ValueError as e:
                messagebox.showerror("Error", "Invalid input values")
            except Exception as e:
                messagebox.showerror("Error", "Failed to save settings")

        ttk.Button(
            form,
            text="Save",
            command=save_settings
        ).grid(row=4, column=0, columnspan=3, pady=20)

    def toggle_theme(self):
        """Toggle between light and dark theme"""
        if self.current_theme == "light":
            self.style.theme_use("clam")  # or any dark theme available
            self.current_theme = "dark"
        else:
            self.style.theme_use("default")
            self.current_theme = "light"

    def show_about(self):
        """Show about dialog"""
        about_text = """
        BitTorrent Application
        Version 1.0.0

        A modern BitTorrent client with advanced features.
        """
        messagebox.showinfo("About", about_text)

    def show_logs(self):
        """Show log viewer window"""
        log_window = tk.Toplevel(self.root)
        log_window.title("Logs")
        log_window.geometry("600x400")

        # Create text widget with scrollbar
        text_widget = tk.Text(log_window, wrap="word")
        scrollbar = ttk.Scrollbar(log_window, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        # Pack widgets
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Load log file content
        try:
            with open('bittorrent_app.log', 'r') as f:
                text_widget.insert("1.0", f.read())
            text_widget.configure(state="disabled")
        except Exception as e:
            text_widget.insert("1.0", "Failed to load log file")
            text_widget.configure(state="disabled")

def main():
    """Main entry point of the application"""
    try:
        root = tk.Tk()
        app = BitTorrentApp(root)

        # Set up periodic updates
        def update():
            app.update_transfers_view()
            app.update_peers_view()
            app.update_status_bar()
            app.update_scrape_view()
            root.after(1000, update)  # Update every second

        root.after(1000, update)
        root.mainloop()

    except Exception as e:
        logging.critical(f"Application failed to start: {e}")
        messagebox.showerror(
            "Critical Error",
            "Application failed to start. Please check the logs."
        )

if __name__ == "__main__":
    main()