# AI-Based Accident Prevention in Modular Manufacturing System (MMS)

🚧 This project is the final Capstone of the **Intel® AI for Manufacturing** program. It presents a real-time accident prevention system using AI-powered computer vision for Modular Manufacturing Systems (MMS). The system is deployed in an industrial environment at the **International Automobile Centre of Excellence (IACE), Ahmedabad**.

---

## 🧠 Objective

To build a real-time safety monitoring system that:
- Detects humans in hazardous zones of a factory
- Stops the machine immediately upon detection
- Restarts the system safely when the zone is clear
- Logs all detections and violations with timestamps

---

## 🏭 Real-World Problem Statement

Accidents in modular manufacturing systems are often due to delayed human reaction or lack of real-time supervision. This project aims to eliminate that delay through AI-based automation using computer vision models.

---

## 🎯 Key Features

- 🔍 **Helmet + Person Detection**
  - Uses YOLOv8 to identify if a worker is present and whether they are wearing a helmet.

- 🛑 **Automatic Machine Stop**
  - Sends a signal to stop operations within milliseconds of detecting a safety violation.

- 🔁 **Timed Restart**
  - Automatically restarts the machine 10 seconds after the area is safe.

- 🧾 **Event Logging**
  - Every detection event is logged in MySQL with timestamp, worker ID (optional), and status (safe/unsafe).

- 🌐 **Email Alerts**
  - Sends automated alerts via email in case of repeated safety violations.

---

## 🛠️ Tech Stack

- **AI Model:** YOLOv8 (Ultralytics)
- **Language:** Python
- **GUI:** Tkinter (for dashboard and controls)
- **Database:** MySQL (PyMySQL for interfacing)
- **Video Processing:** OpenCV
- **Email Service:** SMTP (SSL-based alerts)
- **Model Training:** Custom dataset annotated & trained with Roboflow + Ultralytics YOLO

---

## 🧪 Performance Metrics

- **Helmet Detection Accuracy:** ~93%
- **Person Detection Accuracy:** ~96%
- **Machine Response Time:** < 1 second
- **Auto Restart Delay:** 10 seconds
- **Event Logging Accuracy:** 100%

---

## 📦 Folder Structure
AI_Accident_Prevention_MMS/
├── README.md
├── vision_ai_mms_mysql.py # Main application file
├── yolov8_training/ # Training scripts + weights
│ ├── train.py
│ ├── config.yaml
│ └── runs/
├── gui/ # GUI modules (Tkinter-based)
├── database/
│ ├── setup.sql # MySQL DB schema
│ └── logs_table.sql
├── email_service/
│ └── email_utils.py
└── images/
└── demo_screenshots.png

---

## 🚀 How to Run

1. Clone the repo  
2. Setup the MySQL database using the `setup.sql` file  
3. Run the main program:

``bash
python vision_ai_mms_mysql.py

🧑‍💻 Contributors
Name	GitHub Profile
Kushang Akshay Shukla	@kushangshukla
Dhruvi Karu	          @dpkaru 
Rutu Pansaniya	      @rutupansaniya 


🏢 Organization
International Automobile Centre of Excellence (IACE), Ahmedabad
Capstone conducted as part of the Intel® AI for Manufacturing Program

Group ID: G00126
Institution: SAL College of Engineering
Faculty Mentor: Mikin Dagli Sir

📌 License
This project is for educational and demonstration purposes under the Intel® AI for Manufacturing initiative. Please request permission before using in production.

🌟 Acknowledgments
Intel® AI for Manufacturing Faculty & Program Mentors

Ultralytics YOLO Team

Roboflow for dataset preprocessing

IACE Ahmedabad for access to industrial MMS environment



