# AIORI-3-HACKATHON-PROJECTS
This repository will contain the code and resources for the AIORI-3 hackathon that will be developed during the AIORI-3
youtube link: https://youtu.be/CRCWuSsh7EQ?si=1tGhr-LLL5UGYQ1Y 

# NetDetect - Starter Prototype

A Windows-friendly desktop prototype for explainable home-network diagnosis.

## 1. Requirements
- Windows 10/11
- Python 3.10 or newer
- Internet connection for live network tests

## 2. Setup (Windows PowerShell)

Open PowerShell in this folder and run:

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python main.py
```

If PowerShell blocks activation, run this once in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

You can also run without activating the environment:

```powershell
.\.venv\Scripts\python.exe main.py
```

## 3. What the starter version tests
- TCP reachability to 1.1.1.1:443
- Ping latency and packet loss to 1.1.1.1
- DNS resolution for example.com
- TCP HTTPS connectivity to example.com:443
- Rule-based explanation of findings

## 4. Important limitations
- The starter version does not yet measure download/upload throughput.
- It does not yet measure jitter or loaded latency.
- Ping parsing can vary by operating system and language.
- A failed test may be caused by firewall policy or network restrictions.
- The thresholds in `engine/diagnosis.py` are prototype defaults, not universal standards.
- A successful test to one destination does not prove that all internet services work.

## 5. Project structure

```text
NetDetect/
├── main.py
├── diagnostics/
│   └── network_tests.py
├── engine/
│   └── diagnosis.py
├── requirements.txt
└── README.md
```

## 6. Next development milestones
1. Add test history and JSON storage.
2. Add throughput measurement.
3. Add idle-vs-loaded latency measurement.
4. Add safe, controlled fault-injection lab tests.
5. Generate an evidence-based PDF report.




