import json
import statistics
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, filedialog

import customtkinter as ctk

from diagnostics.network_tests import (
    check_ip_reachability, ping_host, check_dns, check_https, measure_throughput,
)
from engine.diagnosis import generate_diagnosis

try:
    import psutil  # optional
except ImportError:
    psutil = None

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

HISTORY_FILE = Path.home() / ".netdetect_history.json"

GOOD, WARN, IDLE, RUN = "#22c55e", "#f59e0b", "#64748b", "#3b82f6"
STATUS_COLOR = {"GOOD": GOOD, "MEASURED": GOOD, "NORMAL": GOOD, "WARNING": WARN,
                "UNKNOWN": IDLE, "PENDING": IDLE, "SKIPPED": IDLE, "RUNNING": RUN}
CARD = ("#ffffff", "#1e293b")
CARD_ALT = ("#f1f5f9", "#273449")
MUTED = ("#64748b", "#94a3b8")

TESTS = [
    ("reachability", "Internet reachability", check_ip_reachability),
    ("ping", "Latency / packet loss", ping_host),
    ("dns", "DNS resolution", check_dns),
    ("https", "HTTPS connectivity", check_https),
    ("throughput", "Download / Upload speed", measure_throughput),
]


# ---- helpers ---------------------------------------------------------------
def detect_profile():
    if psutil is None:
        return "Unknown", "pip install psutil"
    try:
        best = None
        for name, st in psutil.net_if_stats().items():
            low = name.lower()
            if not st.isup or low.startswith(("lo", "loopback")):
                continue
            if any(v in low for v in ("vbox", "vmware", "docker", "veth", "virtual", "tun", "tap")):
                continue
            if best is None or st.speed > best[1].speed:
                best = (name, st)
        if not best:
            return "Offline", "-"
        name, st = best
        kind = "Wi-Fi" if any(k in name.lower() for k in ("wi-fi", "wifi", "wlan", "wl", "en0")) else "Ethernet"
        return kind, (f"{st.speed} Mbps" if st.speed else "N/A")
    except Exception:
        return "Unknown", "N/A"


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return []


def save_history(entries):
    try:
        HISTORY_FILE.write_text(json.dumps(entries[-100:], indent=2))
    except Exception:
        pass


def fmt(v, suffix="", digits=1):
    return "--" if v is None else f"{v:.{digits}f}{suffix}"


# ---- widgets ---------------------------------------------------------------
class Tile(ctk.CTkFrame):
    def __init__(self, parent, title, unit="", big=True):
        super().__init__(parent, corner_radius=14, fg_color=CARD)
        ctk.CTkLabel(self, text=title.upper(), text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=16, pady=(12, 0))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", padx=16, pady=(2, 12))
        self.value = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(size=28 if big else 18, weight="bold"))
        self.value.pack(side="left")
        if unit:
            ctk.CTkLabel(row, text=" " + unit, text_color=MUTED,
                         font=ctk.CTkFont(size=12)).pack(side="left", anchor="s", pady=(0, 4))

    def set(self, text):
        self.value.configure(text=text)


class TestRow(ctk.CTkFrame):
    def __init__(self, parent, title):
        super().__init__(parent, fg_color="transparent")
        self.columnconfigure(1, weight=1)
        self.dot = ctk.CTkLabel(self, text="●", text_color=IDLE, font=ctk.CTkFont(size=18), width=28)
        self.dot.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=8)
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=1, sticky="w", pady=(8, 0))
        self.detail = ctk.CTkLabel(self, text="Waiting...", text_color=MUTED, anchor="w",
                                   justify="left", wraplength=560, font=ctk.CTkFont(size=12))
        self.detail.grid(row=1, column=1, sticky="w", pady=(0, 8))
        self.badge = ctk.CTkLabel(self, text="PENDING", fg_color=IDLE, text_color="white",
                                  corner_radius=10, width=84, height=24,
                                  font=ctk.CTkFont(size=10, weight="bold"))
        self.badge.grid(row=0, column=2, rowspan=2, padx=12)

    def set(self, status, detail=None):
        color = STATUS_COLOR.get(status, IDLE)
        self.dot.configure(text_color=color)
        self.badge.configure(text=status, fg_color=color)
        if detail is not None:
            self.detail.configure(text=detail)


# ---- app -------------------------------------------------------------------
class NetDetectApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NetDetect - Home Network Diagnosis")
        self.geometry("1000x760")
        self.minsize(820, 600)

        self.history = load_history()
        self.last_report = ""

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.columnconfigure(0, weight=1)
        self.body = body

        self._header()
        self._banner()
        self._tiles()
        self._tests()
        self._tabs()
        self._update_baseline()
        threading.Thread(target=self._detect_worker, daemon=True).start()

    # -- layout
    def _header(self):
        f = ctk.CTkFrame(self.body, fg_color="transparent")
        f.grid(row=0, column=0, sticky="ew", padx=8, pady=(4, 10))
        f.columnconfigure(0, weight=1)
        ctk.CTkLabel(f, text="NetDetect", font=ctk.CTkFont(size=30, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(f, text="Explainable home and last-mile connectivity diagnosis",
                     text_color=MUTED, anchor="w").grid(row=1, column=0, sticky="w")
        ctk.CTkSegmentedButton(f, values=["Dark", "Light"], width=140,
                               command=lambda v: ctk.set_appearance_mode(v.lower())
                               ).grid(row=0, column=1, rowspan=2, sticky="e")
        # segmented button default
        f.winfo_children()[-1].set("Dark")

    def _banner(self):
        self.banner = ctk.CTkFrame(self.body, corner_radius=16, fg_color=CARD)
        self.banner.grid(row=1, column=0, sticky="ew", padx=8, pady=6)
        self.banner.columnconfigure(0, weight=1)
        self.banner_title = ctk.CTkLabel(self.banner, text="Ready to diagnose",
                                         font=ctk.CTkFont(size=22, weight="bold"), anchor="w")
        self.banner_title.grid(row=0, column=0, sticky="w", padx=20, pady=(16, 0))
        self.status = ctk.CTkLabel(self.banner, text="Click Start to test your connection.",
                                   text_color=MUTED, anchor="w")
        self.status.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 14))

        btns = ctk.CTkFrame(self.banner, fg_color="transparent")
        btns.grid(row=0, column=1, rowspan=2, padx=16)
        self.start_button = ctk.CTkButton(btns, text="Start Diagnosis", height=44, width=160,
                                          corner_radius=22, font=ctk.CTkFont(size=14, weight="bold"),
                                          command=self.start_diagnosis)
        self.start_button.pack(side="left", padx=4)
        self.export_button = ctk.CTkButton(btns, text="Export", height=44, width=90, corner_radius=22,
                                           fg_color=CARD_ALT, text_color=("#0f172a", "#e2e8f0"),
                                           hover_color=("#e2e8f0", "#334155"),
                                           state="disabled", command=self.export_report)
        self.export_button.pack(side="left", padx=4)

        self.progress = ctk.CTkProgressBar(self.banner, height=6)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 14))

        self.include_speed = ctk.CTkSwitch(self.banner, text="Include speed test (slower)")
        self.include_speed.select()
        self.include_speed.grid(row=3, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 14))

    def _tiles(self):
        f = ctk.CTkFrame(self.body, fg_color="transparent")
        f.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        self.m = {
            "dl": Tile(f, "Download", "Mbps"), "ul": Tile(f, "Upload", "Mbps"),
            "lat": Tile(f, "Latency", "ms"), "jit": Tile(f, "Jitter", "ms"),
            "loss": Tile(f, "Packet loss", "%"),
        }
        for i, t in enumerate(self.m.values()):
            f.columnconfigure(i, weight=1, uniform="m")
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))

        p = ctk.CTkFrame(self.body, fg_color="transparent")
        p.grid(row=3, column=0, sticky="ew", padx=8, pady=(8, 4))
        self.p_type = Tile(p, "Connection", big=False)
        self.p_speed = Tile(p, "Link speed", big=False)
        self.p_base = Tile(p, "Latency baseline", big=False)
        for i, t in enumerate((self.p_type, self.p_speed, self.p_base)):
            p.columnconfigure(i, weight=1, uniform="p")
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))

    def _tests(self):
        ctk.CTkLabel(self.body, text="Test results", font=ctk.CTkFont(size=15, weight="bold"),
                     anchor="w").grid(row=4, column=0, sticky="w", padx=12, pady=(14, 4))
        card = ctk.CTkFrame(self.body, corner_radius=14, fg_color=CARD)
        card.grid(row=5, column=0, sticky="ew", padx=8)
        card.columnconfigure(0, weight=1)
        self.rows = {}
        for i, (key, title, _) in enumerate(TESTS):
            r = TestRow(card, title)
            r.grid(row=i, column=0, sticky="ew", padx=4, pady=(4 if i == 0 else 0, 4 if i == len(TESTS) - 1 else 0))
            self.rows[key] = r

    def _tabs(self):
        tabs = ctk.CTkTabview(self.body, corner_radius=14, height=330)
        tabs.grid(row=6, column=0, sticky="ew", padx=8, pady=(14, 8))
        tabs.add("Diagnosis")
        tabs.add("History")
        self.output = ctk.CTkTextbox(tabs.tab("Diagnosis"), wrap="word", font=ctk.CTkFont(size=13))
        self.output.pack(fill="both", expand=True)
        self.history_box = ctk.CTkTextbox(tabs.tab("History"), wrap="none",
                                          font=ctk.CTkFont(family="Consolas", size=12))
        self.history_box.pack(fill="both", expand=True)
        for tag, color in (("title", None), ("h", RUN), ("muted", "#94a3b8"),
                           ("NORMAL", GOOD), ("WARNING", WARN)):
            if color:
                self.output._textbox.tag_config(tag, foreground=color)
        self.set_output([("Your diagnostic results will appear here.", "muted")])
        self._render_history()

    # -- profile
    def _detect_worker(self):
        kind, speed = detect_profile()
        self.after(0, lambda: (self.p_type.set(kind), self.p_speed.set(speed)))

    def _baseline(self):
        vals = [h["latency_ms"] for h in self.history[-10:] if h.get("latency_ms") is not None]
        return (statistics.median(vals), len(vals)) if vals else (None, 0)

    def _update_baseline(self):
        base, n = self._baseline()
        self.p_base.set(f"{base:.0f} ms ({n} runs)" if base else "Not established")

    def _render_history(self):
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        head = f"{'Time':<20}{'Result':<9}{'Lat ms':>8}{'Loss %':>8}{'Down':>9}{'Up':>9}\n"
        self.history_box.insert("end", head + "-" * len(head) + "\n")
        for h in reversed(self.history[-30:]):
            self.history_box.insert(
                "end",
                f"{h['time'].replace('T', ' '):<20}{h['level']:<9}{fmt(h.get('latency_ms')):>8}"
                f"{fmt(h.get('loss')):>8}{fmt(h.get('download_mbps')):>9}{fmt(h.get('upload_mbps')):>9}\n")
        self.history_box.configure(state="disabled")

    # -- run
    def start_diagnosis(self):
        self.start_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.progress.set(0)
        self.banner.configure(fg_color=CARD)
        self.banner_title.configure(text="Running diagnosis...", text_color=("#0f172a", "#e2e8f0"))
        self.status.configure(text="Please wait.", text_color=MUTED)
        for t in self.m.values():
            t.set("--")
        for key, _, _ in TESTS:
            self.rows[key].set("PENDING", "Waiting...")
        self.set_output([("Running tests...", "muted")])
        threading.Thread(target=self._worker, daemon=True).start()

    def _ui(self, fn, *a, **k):
        self.after(0, lambda: fn(*a, **k))

    def _worker(self):
        try:
            results = {}
            for i, (key, title, fn) in enumerate(TESTS):
                if key == "throughput" and not self.include_speed.get():
                    results[key] = {"status": "SKIPPED", "details": "Skipped by user.",
                                    "download_mbps": None, "upload_mbps": None}
                else:
                    self._ui(self.rows[key].set, "RUNNING", "Testing...")
                    self._ui(self.status.configure, text=f"Running: {title}...")
                    results[key] = fn()
                r = results[key]
                self._ui(self.rows[key].set, r["status"], r["details"])
                self._ui(self.progress.set, (i + 1) / len(TESTS))
            self._ui(self.show_results, results, generate_diagnosis(results))
        except Exception as exc:
            self._ui(self.show_error, str(exc))

    def show_results(self, results, d):
        ping, thr = results["ping"], results["throughput"]
        self.m["dl"].set(fmt(thr.get("download_mbps")))
        self.m["ul"].set(fmt(thr.get("upload_mbps")))
        self.m["lat"].set(fmt(ping.get("latency_ms")))
        self.m["jit"].set(fmt(ping.get("jitter_ms")))
        self.m["loss"].set(fmt(ping.get("packet_loss_pct")))

        base, n = self._baseline()
        lat = ping.get("latency_ms")
        extra = None
        if base and lat and n >= 3 and lat > base * 2:
            extra = (f"Latency ({lat} ms) is more than double your usual baseline "
                     f"({base:.0f} ms) - this looks like a recent degradation.")

        self.history.append({
            "time": datetime.now().isoformat(timespec="seconds"), "level": d["level"],
            "latency_ms": lat, "loss": ping.get("packet_loss_pct"),
            "jitter_ms": ping.get("jitter_ms"),
            "download_mbps": thr.get("download_mbps"), "upload_mbps": thr.get("upload_mbps"),
        })
        save_history(self.history)
        self._update_baseline()
        self._render_history()

        color = STATUS_COLOR.get(d["level"], IDLE)
        self.banner.configure(fg_color=color)
        self.banner_title.configure(text=d["title"], text_color="white")
        self.status.configure(text=f"Assessment: {d['level']}", text_color="white")

        parts = [(d["title"] + "\n", "title"), (f"Assessment: {d['level']}\n", d["level"]),
                 ("\nEVIDENCE\n", "h")]
        parts += [(f"  •  {e}\n", None) for e in d["evidence"]]
        if extra:
            parts.append((f"  •  {extra}\n", None))
        parts += [("\nEXPLANATION\n", "h"), (d["explanation"] + "\n", None),
                  ("\nRECOMMENDED NEXT STEPS\n", "h")]
        parts += [(f"  •  {a}\n", None) for a in d["actions"]]
        parts.append(("\nThese checks identify symptoms and likely problem areas. They do not "
                      "prove which organization or physical device is responsible.", "muted"))
        self.set_output(parts)

        lines = [f"NetDetect report - {datetime.now():%Y-%m-%d %H:%M:%S}", ""]
        for key, title, _ in TESTS:
            lines.append(f"[{results[key]['status']}] {title}: {results[key]['details']}")
        lines += ["", d["title"], f"Assessment: {d['level']}", "", "Evidence:"]
        lines += [f" - {e}" for e in d["evidence"]]
        lines += ["", "Explanation:", d["explanation"], "", "Next steps:"]
        lines += [f" - {a}" for a in d["actions"]]
        self.last_report = "\n".join(lines)

        self.start_button.configure(state="normal")
        self.export_button.configure(state="normal")

    def show_error(self, error):
        self.banner_title.configure(text="A test could not be completed")
        self.status.configure(text=error)
        self.set_output([(f"Error: {error}", None)])
        self.start_button.configure(state="normal")
        messagebox.showerror("NetDetect error", error)

    def export_report(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text file", "*.txt")],
            initialfile=f"netdetect_{time.strftime('%Y%m%d_%H%M%S')}.txt")
        if path:
            Path(path).write_text(self.last_report, encoding="utf-8")
            self.status.configure(text=f"Report saved to {path}")

    def set_output(self, parts):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        for text, tag in parts:
            if tag:
                self.output._textbox.insert("end", text, tag)
            else:
                self.output._textbox.insert("end", text)
        self.output.configure(state="disabled")


if __name__ == "__main__":
    NetDetectApp().mainloop()

