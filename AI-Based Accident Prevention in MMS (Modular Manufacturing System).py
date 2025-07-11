#!/usr/bin/env python
# coding: utf-8

# In[1]:


# vision_ai_mms_mysql.py
# AI-Based Accident Prevention System for MMS with helmet & temperature detection

# --- Imports ---
import os, time, datetime, ssl, smtplib, threading, sqlite3
from email.message import EmailMessage
import pymysql
from ultralytics import YOLO
import cv2, random
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
from playsound import playsound

# Set working directory (adjust as per deployment)
os.chdir(r"C:\\Users\\kusha\\OneDrive\\Desktop\\Kushang's Files\\Intel AI Course\\Capstone Project")

# --- Configs: Email, MySQL, Device Paths ---
EMAIL_SENDER = "kushangshukla7@gmail.com"
EMAIL_PASSWORD = "ekmz wypb iwqh egzw"
EMAIL_RECEIVER = "kushangshukla7@gmail.com"
SMTP_SERVER, SMTP_PORT = "smtp.gmail.com", 587

MYSQL_HOST      = "localhost"
MYSQL_USER      = "root"
MYSQL_PASSWORD  = ""                       
MYSQL_DB        = "vision_ai"

# Optional: PLC config if using hardware relay or gateway
HW_MODE   = "modbus"     
PLC_HOST  = "192.168.0.50"
START_COIL = 1
STOP_COIL  = 0

# Assets & constants
SIREN_SOUND="siren-alert-96052.mp3"
START_SOUND = "beep-329314.mp3"
TEMP_THRESHOLD = 45.0      # Max allowed temp in °C

# Normalize PPE label variations for robust detection
PPE_NORMALIZED = {
    "helmet": ["helmet", "kask", "hard_hat"],
    "gloves": ["gloves", "glove"],
    "googles": ["googles", "goggles"],
    "jacket": ["jacket", "vest", "safety vest"]
}

class VisionAIApp:
    def __init__(self, root):
        # Initialize the main app window
        self.root = root
        self.root.title("VisionAI – Accident Prevention in MMS")
        self.root.geometry("1300x750")
        self.theme = "dark"
        
        # Load YOLOv8 models
        helmet_path = r"C:\YOLO_MODELS\helmet_model.pt"
        ppe_path = r"C:\YOLO_MODELS\ppe_model.pt"

        assert os.path.exists(helmet_path), f"{helmet_path} not found!"
        assert os.path.exists(ppe_path), f"{ppe_path} not found!"

        self.helmet_model = YOLO(helmet_path)
        self.ppe_model = YOLO(ppe_path)
        
        self.helmet_model = YOLO(r"C:\YOLO_MODELS\helmet_model.pt")
        self.ppe_model = YOLO(r"C:\YOLO_MODELS\ppe_model.pt")

       # Initialize internal state
        self.running = False
        self.cap = None
        self.frame_count = 0
        self.total_frames = 0
        self.last_beep = 0
        self.beep_interval = 3
        self.restart_delay_s = 10
        self.machine_stopped = False
        self.restart_countdown = 0
        self.countdown_active = False
        self.blinking = False
        self.log_text = ""

        # Setup MySQL logging (auto-table per session)
        try:
            self.mysql = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER,
                                         password=MYSQL_PASSWORD, database=MYSQL_DB,
                                         charset="utf8mb4", autocommit=True)
            self.mysql_cursor = self.mysql.cursor()
            timestamp_str = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            self.mysql_table = f"event_logs_{timestamp_str}"

            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.mysql_table} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME,
                frame_number INT,
                message TEXT,
                machine_stopped BOOLEAN,
                temperature FLOAT,
                helmet_present BOOLEAN,
                gloves_present BOOLEAN,
                googles_present BOOLEAN,
                jacket_present BOOLEAN
            )
            """
            self.mysql_cursor.execute(create_table_sql)

        except Exception as e:
            print("❌ MySQL connection failed:", e)
            self.mysql = None

        # SQLite fallback for basic logging
        self.init_sqlite()

        # UI setup
        self.build_ui()
        self.apply_theme()
        self.blink_machine_status()
        
        # Handle exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def normalize_ppe_presence(self, detected_labels):
        # Check for presence of specific PPE categories
        def check_presence(targets):
            return any(label.lower() in targets for label in detected_labels)

        return {
            "helmet_present": check_presence(PPE_NORMALIZED["helmet"]),
            "gloves_present": check_presence(PPE_NORMALIZED["gloves"]),
            "googles_present": check_presence(PPE_NORMALIZED["googles"]),
            "jacket_present": check_presence(PPE_NORMALIZED["jacket"]),
    }


    def init_sqlite(self):
        # Local DB used if MySQL isn't reachable
        with sqlite3.connect("machine_status.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS status_log(ts TEXT, status TEXT)")

    def save_status_sqlite(self, status):
        # Record current machine status in local DB
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        with sqlite3.connect("machine_status.db") as conn:
            conn.execute("INSERT INTO status_log VALUES (?, ?)", (ts, status))

    def build_ui(self):
        # Build complete GUI layout
        # (Top bar, sidebar, video panel, info section, status bar)
        # Top bar
        self.top_bar = tk.Frame(self.root, height=60, bg="#1f1f1f")
        self.top_bar.pack(fill=tk.X, side=tk.TOP)
        tk.Label(self.top_bar,
                 text="VisionAI – Accident Prevention in MMS",
                 font=("Segoe UI", 18, "bold"), fg="white", bg="#1f1f1f"
        ).pack(side=tk.LEFT, padx=20)
        tk.Button(self.top_bar, text="🌓 Toggle Theme",
                  command=self.toggle_theme, font=("Segoe UI", 10), bg="#333", fg="white"
        ).pack(side=tk.RIGHT, padx=20)

        # Sidebar buttons
        self.sidebar = tk.Frame(self.root, width=200)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        buttons = [
            ("📂 Select Video", self.select_video, {}),
            ("📷 Live Camera", self.start_camera, {}),
            ("⛔ Stop Video", self.stop_video, {"bg": "#ff4c4c", "fg": "white"}),
            ("▶️ Start Machine", self.manual_start, {"bg": "#4caf50", "fg": "white"}),
            ("🛑 Stop Machine", self.manual_stop, {"bg": "#f44336", "fg": "white"}),
            ("📧 Email Logs", self.email_current_log, {"bg": "#1976d2", "fg": "white"}),
        ]
        for txt, cmd, kw in buttons:
            tk.Button(self.sidebar, text=txt, command=cmd,
                      font=("Segoe UI", 12), padx=10, pady=5, **kw
            ).pack(pady=10, fill=tk.X)

        # Main video panel
        self.main_panel = tk.Frame(self.root)
        self.main_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.video_label = tk.Label(self.main_panel)
        self.video_label.pack(pady=10)

        # Info panel
        self.info_panel = tk.Frame(self.root, width=260)
        self.info_panel.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(self.info_panel, text="Live Object Count", font=("Segoe UI", 12, "bold")).pack(pady=10)
        self.count_var = tk.StringVar(value="Objects: 0")
        tk.Label(self.info_panel, textvariable=self.count_var, font=("Segoe UI", 12), fg="#00ffcc").pack()

        tk.Label(self.info_panel, text="Machine Status", font=("Segoe UI", 12, "bold")).pack(pady=(20, 5))
        self.machine_status_var = tk.StringVar(value="🟢 RUNNING")
        self.machine_status_label = tk.Label(self.info_panel, textvariable=self.machine_status_var,
                                             font=("Segoe UI", 12, "bold"), fg="green")
        self.machine_status_label.pack()

        tk.Label(self.info_panel, text="Temperature", font=("Segoe UI", 12, "bold")).pack(pady=(10, 5))
        #self.temp_var = tk.StringVar(value="-- °C")
        #tk.Label(self.info_panel, textvariable=self.temp_var, font=("Segoe UI", 12)).pack()
        self.temp_var = tk.StringVar(value="Temperature: --°C")
        tk.Label(self.info_panel, textvariable=self.temp_var, font=("Segoe UI", 12), fg="cyan").pack()

        self.countdown_var = tk.StringVar(value="")
        tk.Label(self.info_panel, textvariable=self.countdown_var, font=("Segoe UI", 12), fg="orange").pack(pady=5)

        tk.Label(self.info_panel, text="Event Log", font=("Segoe UI", 12, "bold")).pack(pady=(20, 5))
        self.log_box = tk.Text(self.info_panel, height=15, wrap=tk.WORD)
        self.log_box.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        tk.Button(self.info_panel, text="📁 Export Log & E-mail", command=self.export_and_email_log,
                  font=("Segoe UI", 11), bg="#007acc", fg="white"
        ).pack(pady=15, fill=tk.X, padx=10)

        # Bottom status bar
        self.bottom_bar = tk.Frame(self.root, height=40)
        self.bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.progress = ttk.Progressbar(self.bottom_bar, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X, padx=20, pady=10)
        self.frame_info = tk.Label(self.bottom_bar, text="Frame: 0/0", font=("Segoe UI", 10))
        self.frame_info.pack(side=tk.RIGHT, padx=20)

    def apply_theme(self):
        # Toggle light/dark UI theme
        styles = {
            "dark": dict(bg="#121212", fg="white", sidebar_bg="#1f1f1f", info_bg="#1c1c1c"),
            "light": dict(bg="#f5f5f5", fg="#000", sidebar_bg="#e0e0e0", info_bg="#f0f0f0"),
        }
        s = styles[self.theme]
        self.root.configure(bg=s["bg"])
        for w in (self.sidebar, self.top_bar, self.bottom_bar):
            w.configure(bg=s["sidebar_bg"])
        self.main_panel.configure(bg=s["bg"])
        self.info_panel.configure(bg=s["info_bg"])
        self.video_label.configure(bg=s["bg"])
        self.log_box.configure(bg=s["info_bg"], fg=s["fg"])

    def toggle_theme(self):
        # Switch theme on button click
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()

    def blink_machine_status(self):
        # Animate red blinking for STOPPED status
        if self.blinking:
            fg = self.machine_status_label.cget("fg")
            bg = self.info_panel.cget("bg")
            self.machine_status_label.config(fg=bg if fg == "red" else "red")
        self.root.after(500, self.blink_machine_status)

    def select_video(self):
        # Load video from disk
        path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv")])
        if path:
            self.stop_video()
            self.cap = cv2.VideoCapture(path)
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.running = True
            self.stream_video()

    def start_camera(self):
        # Start live camera stream
        self.stop_video()
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.total_frames = 0
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Cannot access camera.")
            return
        self.running = True
        self.stream_video()


    def stop_video(self):
        # Stop video stream & cleanup
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.video_label.config(image="")
        self.count_var.set("Objects: 0")
        self.progress["value"] = 0
        self.frame_info.config(text="Frame: 0/0")
        self.frame_count = 0
        self.temp_var.set("-- °C")
        self.countdown_var.set("")
        self.countdown_active = False
        if self.machine_stopped:
            self.start_machine()
            self.machine_stopped = False
            self.log_event("🔄 Machine auto-restarted (video stopped)")

    def plc_write_coil(self, coil, val):
        # Write to PLC if Modbus mode is used
        if HW_MODE == "modbus":
            from pymodbus.client import ModbusTcpClient
            client = ModbusTcpClient(PLC_HOST, port=502)
            client.connect()
            client.write_coil(coil, val, unit=1)
            client.close()
        # (OPC UA or HTTP modes can be added if needed)

    def stop_machine(self):
        # Stop logic: update status, log, and trigger relay if enabled
        self.machine_status_var.set("🔴 STOPPED")
        self.machine_status_label.config(fg="red")
        self.blinking = True
        try:
            self.plc_write_coil(STOP_COIL, True)
        except Exception as e:
            self.log_event(f"❌ PLC stop failed: {e}")
        self.save_status_sqlite("STOPPED")
        self.log_event("⚠️ MACHINE STOP command sent")

    def start_machine(self):
         # Start logic: status reset, countdown stop, sound buzzer
        self.machine_status_var.set("🟢 RUNNING")
        self.machine_status_label.config(fg="green")
        self.blinking = False
        self.countdown_var.set("")
        self.countdown_active = False
        try:
            self.plc_write_coil(START_COIL, True)
        except Exception as e:
            self.log_event(f"❌ PLC start failed: {e}")
        self.save_status_sqlite("RUNNING")
        self.log_event("✅ MACHINE START command sent")
        try:
            threading.Thread(target=playsound, args=(SIREN_SOUND,), daemon=True).start()
        except Exception as e:
            print(f"❌ Siren failed: {e}")


    def manual_start(self):
        # Manual override to start machine
        if not self.machine_stopped:
            messagebox.showinfo("Info", "Machine already running.")
        elif messagebox.askyesno("Start Machine", "Confirm restart?"):
            self.start_machine()
            self.machine_stopped = False

    def manual_stop(self):
        # Manual override to stop machine
        if self.machine_stopped:
            messagebox.showinfo("Info", "Machine already stopped.")
        elif messagebox.askyesno("Stop Machine", "Confirm STOP?"):
            self.stop_machine()
            self.machine_stopped = True
            self.last_hazard = time.time()

    def log_event(self, message, helmet_present=None, temperature=None,
              gloves_present=None, googles_present=None, jacket_present=None):
        # Store detection logs in UI + MySQL
        ts = datetime.datetime.now().isoformat()
        log_text = f"{ts} | {message}"

        if helmet_present is not None:
            log_text += f" | helmet={'YES' if helmet_present else 'NO'}"
        if gloves_present is not None:
            log_text += f" | gloves={'YES' if gloves_present else 'NO'}"
        if googles_present is not None:
            log_text += f" | googles={'YES' if googles_present else 'NO'}"
        if jacket_present is not None:
            log_text += f" | jacket={'YES' if jacket_present else 'NO'}"
        if temperature is not None:
            log_text += f" | temp={temperature:.1f}°C"

        self.log_box.insert(tk.END, log_text + "\n")
        self.log_box.see(tk.END)
        self.log_text += log_text + "\n"

        if self.mysql:
            try:
                self.mysql_cursor.execute(
                    f"""INSERT INTO {self.mysql_table} 
                    (timestamp, frame_number, message, machine_stopped, temperature, helmet_present,
                     gloves_present, googles_present, jacket_present)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (ts, self.frame_count, message, int(self.machine_stopped),
                     temperature,
                     int(helmet_present) if helmet_present is not None else None,
                     int(gloves_present) if gloves_present is not None else None,
                     int(googles_present) if googles_present is not None else None,
                     int(jacket_present) if jacket_present is not None else None)
                )
            except Exception as e:
                print("❌ MySQL insert failed:", e)


    def send_email(self, subject, body):
        # Basic SMTP email function
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = EMAIL_SENDER
            msg["To"] = EMAIL_RECEIVER
            msg.set_content(body)
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as srv:
                srv.starttls(context=ssl.create_default_context())
                srv.login(EMAIL_SENDER, EMAIL_PASSWORD)
                srv.send_message(msg)
            self.log_event("📧 Email sent")
        except Exception as e:
            self.log_event(f"❌ Email failed: {e}")

    def email_current_log(self):
        # Trigger threaded email dispatch
        threading.Thread(target=self.send_email,
                         args=("VisionAI Log", self.log_text),
                         daemon=True).start()

    def export_and_email_log(self):
        # Save log to .txt and email it
        fp = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files","*.txt")])
        if fp:
            with open(fp, "w") as f: f.write(self.log_text)
            self.email_current_log()
            messagebox.showinfo("Exported", f"Log saved and email sent:\n{fp}")

    def update_countdown(self):
        # Handles countdown for auto-restart
        if self.countdown_active and self.restart_countdown > 0:
            self.restart_countdown -= 1
            self.countdown_var.set(f"Restart in {self.restart_countdown}s")
            if self.restart_countdown == 0:
                self.start_machine()
                self.machine_stopped = False
            else:
                self.root.after(1000, self.update_countdown)

    def stream_video(self):
        # Main function to process each frame from stream:
        try:
            if not (self.running and self.cap):
                print("[DEBUG] Stream not running or cap is None")
                return

            ret, frame = self.cap.read()
            if not ret:
                print("[ERROR] Failed to read frame")
                self.stop_video()
                return

            self.frame_count += 1
            disp = cv2.resize(frame, (800, 500))

           # Helmet & PPE detection
            results = self.helmet_model.predict(
                source=disp, imgsz=640, conf=0.25, device="cpu", verbose=False
            )[0]

            names = results.names if hasattr(results, "names") else self.helmet_model.names
            detected = [names[int(c)] for c in results.boxes.cls]

            # Draw boxes
            for box, cls in zip(results.boxes.xyxy, results.boxes.cls):
                x1, y1, x2, y2 = map(int, box)
                label = names[int(cls)]
                cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(disp, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (255, 255, 0), 2)

            helmet_labels = [names[int(cls)] for cls in results.boxes.cls]
            
            results_ppe = self.ppe_model.predict(disp, imgsz=640, conf=0.25, device="cpu", verbose=False)[0]

            ppe_names = results_ppe.names if hasattr(results_ppe, "names") else self.ppe_model.names
            
            # Draw boxes
            for box, cls in zip(results_ppe.boxes.xyxy, results_ppe.boxes.cls):
                x1, y1, x2, y2 = map(int, box)
                label = ppe_names[int(cls)]
                cv2.rectangle(disp, (x1, y1), (x2, y2), (255, 0, 255), 2)  # magenta for PPE
                cv2.putText(disp, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (255, 0, 255), 2)

            # Collect labels for logic
            ppe_labels = [ppe_names[int(cls)] for cls in results_ppe.boxes.cls]
            ppe_flags = self.normalize_ppe_presence(ppe_labels)

            helmet_on = "helmet" in helmet_labels
            gear_on = "vest" in ppe_labels or "safety vest" in ppe_labels

            if not helmet_on or not gear_on:
                if not self.machine_stopped:
                    self.stop_machine()
                    self.machine_stopped = True
                    self.log_event(f"[Frame {self.frame_count}] 🚨 Hazard: Missing {'helmet' if not helmet_on else ''} {'gear' if not gear_on else ''}")

            # Temp monitoring
            temp = self.get_temperature()
            self.temp_var.set(f"{temp:.1f} °C")

            self.count_var.set(f"Objects: {len(detected)}")
            person = "person" in detected
            helmet = "helmet" in detected or "vest" in detected

            now = time.time()
            stop_due = False
            reason = ""

            # Machine control decisions
            if person:
                if temp > TEMP_THRESHOLD:
                    stop_due = True
                    reason = "Person + High Temp"
                elif not helmet:
                    stop_due = True
                    reason = "Person without Helmet/Gear"
            else:
                if temp > TEMP_THRESHOLD:
                    reason = "High Temp"

            if stop_due:
                if not self.machine_stopped:
                    self.stop_machine()
                    self.machine_stopped = True
                    self.log_event(f"[Frame {self.frame_count}] 🚨 {reason}",
                                   helmet_present=helmet, temperature=temp)

                if now - self.last_beep > self.beep_interval:
                    self.last_beep = now
                    try:
                        playsound(SIREN_SOUND, block=False)
                    except:
                        pass

                self.countdown_active = False
                self.countdown_var.set("")
            else:
                if self.machine_stopped and not self.countdown_active:
                    self.restart_countdown = self.restart_delay_s
                    self.countdown_active = True
                    self.countdown_var.set(f"Restart in {self.restart_countdown}s")
                    self.root.after(1000, self.update_countdown)

                # Always log temperature status if machine is running
                if temp > TEMP_THRESHOLD:
                    self.log_event(f"[Frame {self.frame_count}] 🚨 Temperature NOT OK",
                    temperature=temp, **ppe_flags)
                else:
                    self.log_event(f"[Frame {self.frame_count}] Normal - Temp OK",
                    temperature=temp, **ppe_flags)

                
            # Logging & UI update
            imgtk = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)))
            self.video_label.imgtk = imgtk
            self.video_label.image = imgtk  
            self.video_label.configure(image=imgtk)

            if self.total_frames:
                pct = (self.frame_count / self.total_frames) * 100
                self.progress["value"] = pct
                self.frame_info.config(text=f"Frame: {self.frame_count}/{self.total_frames}")
            else:
                self.frame_info.config(text=f"Frame: {self.frame_count}")

            self.root.after(10, self.stream_video)

        except Exception as e:
            print(f"[CRITICAL ERROR in stream_video]: {e}")

    def on_close(self):
        # Exit and close connections
        threading.Thread(target=self.send_email,
                         args=("VisionAI Session Log", self.log_text), daemon=True).start()
        if self.mysql: self.mysql.close()
        self.root.destroy()
    
    def get_temperature(self):
    # Simulated sensor reading
        return 30 + random.random() * 20

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = VisionAIApp(root)
    root.mainloop()


# In[ ]:




