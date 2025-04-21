import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import threading
import logging
import json
from web_scraper import (
    scrape_login_page,
    generate_ini_file,
    generate_au3_script,
    test_ps_automate,
    capture_user_interaction
)
import webbrowser

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class UILogHandler(logging.Handler):
    def __init__(self, ui_log_func):
        super().__init__()
        self.ui_log_func = ui_log_func

    def emit(self, record):
        msg = self.format(record)
        self.ui_log_func(msg)

class WebScraperUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Automation Suite")
        self.geometry("880x720")
        self.resizable(False, True)
        try:
            self.iconbitmap("C:\Dhananjay Projects\py-script\opsymb.ico")
        except Exception:
            pass  # If icon not found, use default

        # Variables
        self.url_var = tk.StringVar()
        self.browser_var = tk.StringVar(value="chrome")
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.ini_file_var = tk.StringVar()
        self.au3_file_var = tk.StringVar()
        self.url_history = self.load_url_history()

        self.setup_logging()
        self.create_widgets()

    def load_url_history(self):
        try:
            with open("urls_history.json", "r") as f:
                return json.load(f)
        except Exception:
            return []

    def save_url_history(self):
        url = self.url_var.get().strip()
        if url and url not in self.url_history:
            self.url_history.insert(0, url)
            self.url_history = self.url_history[:20]
            with open("urls_history.json", "w") as f:
                json.dump(self.url_history, f)

    def setup_logging(self):
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        ui_handler = UILogHandler(self.log)
        ui_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ui_handler.setFormatter(formatter)
        logging.root.addHandler(ui_handler)
        logging.root.setLevel(logging.INFO)

    def create_widgets(self):
        pad = 14
        # Top bar with title and website button
        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.pack(fill="x", padx=pad, pady=(pad,0))
        ctk.CTkLabel(topbar, text="Web Scraper & Automation Suite", font=("Segoe UI", 26, "bold")).pack(side="left", pady=0)
        self.create_visit_website_button(topbar)

        # Main input frame
        main_frame = ctk.CTkFrame(self, corner_radius=12)
        main_frame.pack(pady=pad, padx=pad, fill="x")

        def label_entry(label_text, row, col, variable, width=220, show=None):
            ctk.CTkLabel(main_frame, text=label_text, font=("Segoe UI", 13)).grid(row=row, column=col, sticky="e", padx=6, pady=6)
            ctk.CTkEntry(main_frame, textvariable=variable, width=width, show=show, font=("Segoe UI", 12)).grid(row=row, column=col+1, sticky="w", padx=6, pady=6)

        # URL
        ctk.CTkLabel(main_frame, text="Target URL:", font=("Segoe UI", 13)).grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.url_combo = ttk.Combobox(main_frame, textvariable=self.url_var, values=self.url_history, width=60, font=("Segoe UI", 12))
        self.url_combo.grid(row=0, column=1, columnspan=3, sticky="w", padx=6, pady=6)
        self.url_combo.bind("<Button-1>", lambda e: self.url_combo.config(values=self.url_history))

        # Browser selector
        ctk.CTkLabel(main_frame, text="Browser:", font=("Segoe UI", 13)).grid(row=1, column=0, sticky="e", padx=6, pady=6)
        ctk.CTkOptionMenu(main_frame, variable=self.browser_var, values=["chrome", "firefox", "edge"]).grid(row=1, column=1, sticky="w", padx=6, pady=6)

        # Credentials
        label_entry("Username:", 2, 0, self.username_var)
        label_entry("Password:", 2, 2, self.password_var, show="*")

        # INI file
        ctk.CTkLabel(main_frame, text="INI File:", font=("Segoe UI", 13)).grid(row=3, column=0, sticky="e", padx=6, pady=6)
        ctk.CTkEntry(main_frame, textvariable=self.ini_file_var, width=340, font=("Segoe UI", 12)).grid(row=3, column=1, sticky="w", padx=6, pady=6)
        ctk.CTkButton(main_frame, text="Browse", command=self.browse_ini).grid(row=3, column=2, padx=6)
        ctk.CTkButton(main_frame, text="Generate INI", command=self.run_generate_ini).grid(row=3, column=3, padx=6)

        # AU3 file
        ctk.CTkLabel(main_frame, text="AU3 File:", font=("Segoe UI", 13)).grid(row=4, column=0, sticky="e", padx=6, pady=6)
        ctk.CTkEntry(main_frame, textvariable=self.au3_file_var, width=340, font=("Segoe UI", 12)).grid(row=4, column=1, sticky="w", padx=6, pady=6)
        ctk.CTkButton(main_frame, text="Browse", command=self.browse_au3).grid(row=4, column=2, padx=6)
        ctk.CTkButton(main_frame, text="Generate AU3", command=self.run_generate_au3).grid(row=4, column=3, padx=6)

        # Action buttons
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(padx=pad, pady=(0, pad), fill="x")

        btn_specs = [
            ("Scrape Login Page", self.run_scrape_login, "#0984e3"),
            ("Test ps_automate", self.run_test_ps_automate, "#e17055"),
            ("Capture User Interaction", self.run_capture_user_interaction, "#00cec9"),
            ("Clear Form", self.clear_form, "#636e72")
        ]
        for text, command, color in btn_specs:
            ctk.CTkButton(action_frame, text=text, command=command, fg_color=color).pack(side="left", padx=10, pady=10)

        # Log output
        log_title_frame = ctk.CTkFrame(self, fg_color="transparent")
        log_title_frame.pack(padx=pad, fill="x")
        ctk.CTkLabel(log_title_frame, text="Log / Output", font=("Segoe UI", 13, "bold")).pack(side="left")
        ctk.CTkButton(log_title_frame, text="Clear Log", command=self.clear_log, fg_color="#d63031").pack(side="right", padx=10)

        self.log_text = scrolledtext.ScrolledText(self, height=16, font=("Consolas", 12), bg="#f1f2f6", fg="#2d3436", wrap="word")
        self.log_text.pack(padx=pad, pady=(0, pad), fill="both", expand=True)

        # Footer with gradient
        self.create_footer_with_gradient()

    def log(self, msg):
        self.log_text.insert(tk.END, str(msg) + "\n")
        self.log_text.see(tk.END)
        self.update()

    def clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def clear_form(self):
        self.url_var.set("")
        self.browser_var.set("chrome")
        self.username_var.set("")
        self.password_var.set("")
        self.ini_file_var.set("")
        self.au3_file_var.set("")
        self.url_combo.config(values=self.url_history)

    def browse_ini(self):
        file = filedialog.asksaveasfilename(defaultextension=".ini", filetypes=[("INI files", "*.ini")])
        if file:
            self.ini_file_var.set(file)

    def browse_au3(self):
        file = filedialog.asksaveasfilename(defaultextension=".au3", filetypes=[("AU3 files", "*.au3")])
        if file:
            self.au3_file_var.set(file)

    # Threaded Execution Wrappers
    def threaded(self, func):
        threading.Thread(target=func).start()

    def run_scrape_login(self):
        self.save_url_history()
        self.log("[INFO] Scraping login page...")
        self.threaded(self._scrape_login)

    def _scrape_login(self):
        try:
            url, browser = self.url_var.get().strip(), self.browser_var.get().strip()
            if not url:
                return self.log("[ERROR] URL is required.")
            elements = scrape_login_page(url, browser)
            self.log(f"[SUCCESS] Scraped login elements: {elements}")
        except Exception as e:
            self.log(f"[ERROR] {e}")

    def run_generate_ini(self):
        self.save_url_history()
        self.log("[INFO] Generating INI file...")
        self.threaded(self._generate_ini)

    def _generate_ini(self):
        try:
            url, browser, ini_file = self.url_var.get().strip(), self.browser_var.get().strip(), self.ini_file_var.get().strip()
            if not (url and ini_file):
                return self.log("[ERROR] URL and INI file path required.")
            elements = scrape_login_page(url, browser)
            generate_ini_file(url, elements, browser, ini_file)
            self.log(f"[SUCCESS] INI file generated at {ini_file}")
        except Exception as e:
            self.log(f"[ERROR] {e}")

    def run_generate_au3(self):
        self.save_url_history()
        self.log("[INFO] Generating AU3 script...")
        self.threaded(self._generate_au3)

    def _generate_au3(self):
        try:
            url, browser, au3_file = self.url_var.get().strip(), self.browser_var.get().strip(), self.au3_file_var.get().strip()
            if not (url and au3_file):
                return self.log("[ERROR] URL and AU3 file path required.")
            elements = scrape_login_page(url, browser)
            generate_au3_script(url, elements, browser, au3_file)
            self.log(f"[SUCCESS] AU3 script generated at {au3_file}")
        except Exception as e:
            self.log(f"[ERROR] {e}")

    def run_test_ps_automate(self):
        self.save_url_history()
        self.log("[INFO] Testing ps_automate...")
        self.threaded(self._test_ps_automate)

    def _test_ps_automate(self):
        try:
            ini, url, browser, user, pwd = map(lambda var: var.get().strip(), 
                                               [self.ini_file_var, self.url_var, self.browser_var, self.username_var, self.password_var])
            if not all([ini, url, user, pwd]):
                return self.log("[ERROR] Fill all fields for testing.")
            test_ps_automate(ini, url, browser, user, pwd)
            self.log("[SUCCESS] ps_automate test completed.")
        except Exception as e:
            self.log(f"[ERROR] {e}")

    def run_capture_user_interaction(self):
        self.save_url_history()
        self.log("[INFO] Capturing user interaction...")
        self.threaded(self._capture_user_interaction)

    def _capture_user_interaction(self):
        try:
            url, browser = self.url_var.get().strip(), self.browser_var.get().strip()
            if not url:
                return self.log("[ERROR] URL is required.")
            result = capture_user_interaction(url, browser)
            self.log(f"[SUCCESS] Captured user interaction: {result}")
        except Exception as e:
            self.log(f"[ERROR] {e}")

    def create_visit_website_button(self, parent):
        # Simulate a gradient by using a solid color close to the midpoint of the gradient
        btn_color = "#a259f7"  # Midpoint between violet and light blue
        hover_color = "#74ebd5"
        ctk.CTkButton(
            parent,
            text="Visit Website",
            fg_color=btn_color,
            hover_color=hover_color,
            text_color="#fff",
            font=("Segoe UI", 13, "bold"),
            corner_radius=16,
            command=lambda: webbrowser.open_new_tab("https://www.opshells.com")
        ).pack(side="right", padx=8, pady=0)

    def create_footer_with_gradient(self):
        # Remove any previous footer
        if hasattr(self, 'footer_canvas') and self.footer_canvas.winfo_exists():
            self.footer_canvas.destroy()
        width = 860
        height = 32
        self.footer_canvas = tk.Canvas(self, width=width, height=height, highlightthickness=0, bd=0)
        self.footer_canvas.pack(fill="x", side="bottom", pady=(0,6))
        # Gradient from violet (#8f00ff) to light blue (#74ebd5)
        steps = width
        for i in range(steps):
            r1, g1, b1 = (143, 0, 255)  # violet
            r2, g2, b2 = (116, 235, 213)  # light blue
            r = int(r1 + (r2 - r1) * i / steps)
            g = int(g1 + (g2 - g1) * i / steps)
            b = int(b1 + (b2 - b1) * i / steps)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.footer_canvas.create_line(i, 0, i, height, fill=color)
        self.footer_canvas.create_text(
            width//2, height//2,
            text="Developed and maintained by Opshells | contactus@opshells.com",
            font=("Segoe UI", 11, "italic"),
            fill="#fff",
            anchor="center"
        )

if __name__ == "__main__":
    app = WebScraperUI()
    app.mainloop()
