import sys
import requests
import socket
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

# --- [설정] ---
AURORA_IP = "127.0.0.1"
AURORA_PORT = 1130

AIRPORT_DB = {
    "RKSI": {"name": "Incheon (인천)", "runways": ["33L/34R (North)", "15R/16L (South)"]},
    "RKSS": {"name": "Gimpo (김포)", "runways": ["14L/14R", "32L/32R"]},
    "RKPK": {"name": "Gimhae (김해)", "runways": ["36L/36R", "18L/18R"]},
    "RKPC": {"name": "Jeju (제주)", "runways": ["07", "25"]}
}

class AuroraClientGUI:
    def __init__(self, root, vid, user_name):
        self.root = root
        self.vid = vid
        self.user_name = user_name
        self.root.title(f"RKSI Aurora Pro v5.1 - {user_name} ({vid})")
        self.root.geometry("500x450")
        self.root.resizable(False, False)

        # 스타일
        style = ttk.Style()
        style.configure("TButton", font=("Malgun Gothic", 10))
        style.configure("TLabel", font=("Malgun Gothic", 10))
        
        # 1. 사용자 정보 표시 프레임
        self.info_frame = ttk.LabelFrame(root, text="Controller Info", padding="15")
        self.info_frame.pack(fill=tk.X, padx=15, pady=10)
        
        self.lbl_status = ttk.Label(self.info_frame, text="IVAO 서버에서 등급 확인 중...", foreground="blue")
        self.lbl_status.pack(anchor='w')

        # 2. 공항 선택 프레임
        self.apt_frame = ttk.LabelFrame(root, text="Airport Selection", padding="15")
        self.apt_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        ttk.Label(self.apt_frame, text="관제할 공항을 선택하세요:").pack(anchor='w', pady=5)
        
        self.airport_var = tk.StringVar()
        self.airport_combo = ttk.Combobox(self.apt_frame, textvariable=self.airport_var, state="readonly")
        self.airport_combo.pack(fill=tk.X, pady=5)
        self.airport_combo.bind("<<ComboboxSelected>>", self.on_airport_select)

        # 3. 활주로 선택 프레임
        self.rwy_frame = ttk.LabelFrame(root, text="Active Runway", padding="15")
        self.rwy_frame.pack(fill=tk.X, padx=15, pady=10)
        
        self.rwy_var = tk.StringVar()
        self.rwy_combo = ttk.Combobox(self.rwy_frame, textvariable=self.rwy_var, state="readonly")
        self.rwy_combo.pack(fill=tk.X, pady=5)

        # 4. 실행 버튼 및 로그
        self.btn_start = ttk.Button(root, text="START CONTROL (Aurora Sync)", command=self.start_control_mode, state=tk.DISABLED)
        self.btn_start.pack(fill=tk.X, padx=15, pady=10)

        # 자동 등급 체크 시작
        threading.Thread(target=self.check_rating, daemon=True).start()

    def check_rating(self):
        # IVAO API로 등급 조회
        rating = 0
        callsign = "OBS"
        try:
            res = requests.get("https://api.ivao.aero/v2/tracker/whazzup", timeout=5).json()
            atcs = res.get("clients", {}).get("atcs", [])
            for atc in atcs:
                if str(atc.get("userId")) == self.vid:
                    rating = atc.get("rating", 0)
                    callsign = atc.get("callsign", "OBS")
                    break
        except: pass
        
        # 등급별 허용 공항 결정 로직
        self.allowed_airports = self.get_allowed_airports(rating, callsign)
        
        # UI 업데이트
        msg = f"Callsign: {callsign} | Rating: {rating} | Name: {self.user_name}"
        self.root.after(0, lambda: self.lbl_status.config(text=msg, foreground="black"))
        self.root.after(0, self.update_airport_list)

    def get_allowed_airports(self, rating, callsign):
        # [권한 로직]
        # Rating 2: ADC (Tower), 3: APC (Approach), 4: ACC (Center)
        # 예시 로직 (엄격하게 적용 가능)
        allowed = []
        cs = callsign.upper()
        
        # 1. Center / Senior Staff 등급 (모든 공항 오픈)
        if rating >= 4 or "CTR" in cs:
            return list(AIRPORT_DB.keys())

        # 2. Approach (관할 구역만)
        if "RKSS" in cs: allowed.extend(["RKSI", "RKSS"])
        if "RKPK" in cs: allowed.append("RKPK")
        if "RKPC" in cs: allowed.append("RKPC")
        
        # 3. Tower/GND (본인 공항만)
        for apt in AIRPORT_DB:
            if apt in cs: allowed.append(apt)
            
        # 만약 매칭되는 게 없으면(OBS 등) 기본적으로 다 보여주되 경고 (또는 빈 리스트)
        if not allowed: return list(AIRPORT_DB.keys()) # 테스트용으로 일단 다 오픈
        return list(set(allowed))

    def update_airport_list(self):
        display_values = []
        for code in self.allowed_airports:
            display_values.append(f"{code} - {AIRPORT_DB[code]['name']}")
        
        self.airport_combo['values'] = display_values
        if display_values:
            self.airport_combo.current(0)
            self.on_airport_select(None)
            self.btn_start.config(state=tk.NORMAL)
        else:
            self.airport_combo.set("관제 가능한 공항이 없습니다.")
            self.btn_start.config(state=tk.DISABLED)

    def on_airport_select(self, event):
        selection = self.airport_var.get()
        if not selection: return
        code = selection.split(" - ")[0]
        self.rwy_combo['values'] = AIRPORT_DB[code]['runways']
        self.rwy_combo.current(0)

    def start_control_mode(self):
        # 실제 관제 로직(process_deps 등)이 도는 창으로 전환하거나
        # 현재 창을 로그 뷰어로 변경
        sel_apt = self.airport_var.get().split(" - ")[0]
        sel_rwy = self.rwy_var.get()
        
        messagebox.showinfo("Ready", f"{sel_apt} ({sel_rwy}) 관제 모드를 시작합니다.\n\n[기능]\n- Enter: 자동 처리\n- Callsign 입력: 개별 처리")
        
        # 여기서부턴 기존 CMD 로직 대신 GUI 로그창을 띄우는 형태로 전환
        self.open_monitor_window(sel_apt, sel_rwy)

    def open_monitor_window(self, apt, rwy):
        # 기존 창 내용을 지우고 로그 화면으로 전환
        for widget in self.root.winfo_children():
            widget.destroy()
            
        self.root.geometry("600x400")
        ttk.Label(self.root, text=f"[{apt} - {rwy}] Monitoring...", font=("Arial", 12, "bold"), foreground="green").pack(pady=10)
        
        # 로그창
        self.log_area = tk.Text(self.root, height=15, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # 하단 입력창 (수동 콜사인 입력)
        input_frame = ttk.Frame(self.root)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.entry_cs = ttk.Entry(input_frame)
        self.entry_cs.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_cs.bind("<Return>", lambda e: self.manual_process(apt, rwy))
        
        btn_action = ttk.Button(input_frame, text="Re-SQK / Sync", command=lambda: self.manual_process(apt, rwy))
        btn_action.pack(side=tk.RIGHT, padx=5)
        
        # 자동 갱신 스레드 시작
        # threading.Thread(target=self.auto_loop, args=(apt, rwy), daemon=True).start()

    def log(self, text):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, text + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def manual_process(self, apt, rwy):
        cs = self.entry_cs.get().strip().upper()
        if cs:
            self.log(f"[Manual] Processing {cs}...")
            # 여기에 기존 process_deps(target_cs=cs) 로직 연결
            self.entry_cs.delete(0, tk.END)

if __name__ == "__main__":
    # 런처에서 넘어온 인자 받기 (없으면 테스트 모드)
    my_vid = sys.argv[1] if len(sys.argv) > 1 else "123456"
    my_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown User"

    root = tk.Tk()
    app = AuroraClientGUI(root, my_vid, my_name)
    root.mainloop()
