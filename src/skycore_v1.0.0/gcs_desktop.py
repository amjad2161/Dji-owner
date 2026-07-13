#!/usr/bin/env python3
"""
SkyCore Desktop Ground Control Station v2.0
A complete desktop application for autonomous drone operations.
Enhanced with mission planning, flight logs, simulation, and more.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import time
import json
import math
import random
import csv
from datetime import datetime
from collections import deque
from typing import List, Dict, Tuple, Optional

try:
    from skycore import SkyCoreSystem, FlightState, SafetyLevel
    SKYCORE_AVAILABLE = True
except ImportError:
    SKYCORE_AVAILABLE = False


class TelemetryPoint:
    """A single telemetry data point for logging"""
    def __init__(self, timestamp: float, lat: float, lon: float, alt: float, 
                 speed: float, roll: float, pitch: float, yaw: float, 
                 battery: float, satellites: int):
        self.timestamp = timestamp
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.speed = speed
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        self.battery = battery
        self.satellites = satellites
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "lat": self.lat,
            "lon": self.lon,
            "alt": self.alt,
            "speed": self.speed,
            "roll": self.roll,
            "pitch": self.pitch,
            "yaw": self.yaw,
            "battery": self.battery,
            "satellites": self.satellites
        }
    
    @staticmethod
    def from_dict(d: dict) -> 'TelemetryPoint':
        return TelemetryPoint(
            d["timestamp"], d["lat"], d["lon"], d["alt"],
            d["speed"], d["roll"], d["pitch"], d["yaw"],
            d["battery"], d["satellites"]
        )


class WaypointEditor(tk.Toplevel):
    """Mission waypoint editor dialog"""
    def __init__(self, parent, waypoints: List[Dict]):
        super().__init__(parent)
        self.title("Mission Waypoint Editor")
        self.geometry("600x500")
        self.waypoints = waypoints
        
        self._create_ui()
        
        # Load existing waypoints
        for wp in waypoints:
            self._add_waypoint_row(wp)
    
    def _create_ui(self):
        # Headers
        headers = ["#", "Lat", "Lon", "Alt (m)", "Action"]
        for i, h in enumerate(headers):
            tk.Label(self, text=h, font=("Segoe UI", 10, "bold"),
                   bg="#162a47", fg="#00d4ff").grid(row=0, column=i, padx=5, pady=2)
        
        self.waypoint_frame = tk.Frame(self, bg="#162a47")
        self.waypoint_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.waypoint_widgets = []
        
        # Buttons
        btn_frame = tk.Frame(self, bg="#0f1f38")
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Button(btn_frame, text="Add Waypoint", 
                 command=self._add_new_waypoint,
                 bg="#00ff88", fg="#000").pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="Add From Map", 
                 command=self._add_from_map,
                 bg="#00d4ff", fg="#000").pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="Clear All", 
                 command=self._clear_all,
                 bg="#ff4444", fg="#fff").pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="Import CSV", 
                 command=self._import_csv,
                 bg="#ffaa00", fg="#000").pack(side='left', padx=5)
        
        # Ok/Cancel
        action_frame = tk.Frame(self, bg="#0f1f38")
        action_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(action_frame, text="OK", width=10,
                 command=self.destroy,
                 bg="#00ff88", fg="#000").pack(side='right', padx=5)
        
        tk.Button(action_frame, text="Cancel", width=10,
                 command=self._cancel,
                 bg="#ff4444", fg="#fff").pack(side='right', padx=5)
    
    def _add_waypoint_row(self, wp: Dict):
        row = len(self.waypoint_widgets)
        
        num_label = tk.Label(self.waypoint_frame, text=f"{row+1}", 
                            font=("Consolas", 10), bg="#162a47", fg="#fff", width=3)
        num_label.grid(row=row, column=0, padx=2, pady=2)
        
        lat_entry = tk.Entry(self.waypoint_frame, width=12, font=("Consolas", 10))
        lat_entry.insert(0, f"{wp.get('lat', 0):.6f}")
        lat_entry.grid(row=row, column=1, padx=2, pady=2)
        
        lon_entry = tk.Entry(self.waypoint_frame, width=12, font=("Consolas", 10))
        lon_entry.insert(0, f"{wp.get('lon', 0):.6f}")
        lon_entry.grid(row=row, column=2, padx=2, pady=2)
        
        alt_entry = tk.Entry(self.waypoint_frame, width=10, font=("Consolas", 10))
        alt_entry.insert(0, str(wp.get('alt', 20)))
        alt_entry.grid(row=row, column=3, padx=2, pady=2)
        
        del_btn = tk.Button(self.waypoint_frame, text="X", width=3,
                          bg="#ff4444", fg="#fff",
                          command=lambda r=row: self._delete_row(r))
        del_btn.grid(row=row, column=4, padx=2, pady=2)
        
        self.waypoint_widgets.append({
            'lat': lat_entry, 'lon': lon_entry, 'alt': alt_entry
        })
    
    def _add_new_waypoint(self):
        wp = {"lat": 32.0853 + random.uniform(-0.01, 0.01),
              "lon": 34.7818 + random.uniform(-0.01, 0.01),
              "alt": 20}
        self._add_waypoint_row(wp)
    
    def _add_from_map(self):
        # Get current position from parent
        if hasattr(self.master, 'sim_position'):
            pos = self.master.sim_position
            wp = {"lat": pos['lat'], "lon": pos['lon'], "alt": pos['alt'] + 10}
            self._add_waypoint_row(wp)
    
    def _delete_row(self, row: int):
        for widget in self.waypoint_frame.grid_slaves():
            if int(widget.grid_info()['row']) == row:
                widget.destroy()
        # Rebuild
        self.waypoint_widgets.pop(row)
        self._refresh_rows()
    
    def _refresh_rows(self):
        for i, w in enumerate(self.waypoint_widgets):
            w['lat'].grid(row=i, column=1)
            w['lon'].grid(row=i, column=2)
            w['alt'].grid(row=i, column=3)
    
    def _clear_all(self):
        for widget in self.waypoint_frame.winfo_children():
            widget.destroy()
        self.waypoint_widgets.clear()
    
    def _import_csv(self):
        path = filedialog.askopenfilename(title="Import Waypoints CSV",
                                          filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            try:
                with open(path, 'r') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        if len(row) >= 3:
                            wp = {"lat": float(row[0]), "lon": float(row[1]), "alt": float(row[2])}
                            self._add_waypoint_row(wp)
            except Exception as e:
                messagebox.showerror("Import Error", str(e))
    
    def _cancel(self):
        self.waypoints.clear()
        self.destroy()
    
    def get_waypoints(self) -> List[Dict]:
        wps = []
        for w in self.waypoint_widgets:
            try:
                wp = {
                    "lat": float(w['lat'].get()),
                    "lon": float(w['lon'].get()),
                    "alt": float(w['alt'].get())
                }
                wps.append(wp)
            except:
                pass
        return wps


class SkyCoreDesktopGCS(tk.Tk):
    """
    SkyCore Desktop Ground Control Station v2.0
    A complete desktop application for autonomous drone operations.
    """
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.title("SkyCore GCS v2.0 - Autonomous Drone Control")
        self.geometry("1500x950")
        self.minsize(1400, 900)
        
        # Color scheme
        self.colors = {
            'bg_primary': '#0a1628',
            'bg_secondary': '#0f1f38',
            'bg_tertiary': '#162a47',
            'accent': '#00d4ff',
            'success': '#00ff88',
            'warning': '#ffaa00',
            'danger': '#ff4444',
            'text': '#ffffff',
            'text_secondary': 'rgba(255,255,255,0.7)',
            'border': 'rgba(255,255,255,0.1)'
        }
        
        self.configure(bg=self.colors['bg_primary'])
        
        # System state
        self.system = None
        self.is_running = False
        self.simulated = True
        
        # Telemetry data
        self.sim_position = {"lat": 32.0853, "lon": 34.7818, "alt": 0.0}
        self.sim_battery = 100.0
        self.sim_speed = 0.0
        self.sim_attitude = {"roll": 0.0, "pitch": 0.0, "yaw": 120.0}
        
        # Flight path history
        self.flight_path: List[Tuple[float, float]] = []
        self.max_path_points = 500
        
        # Mission waypoints
        self.mission_waypoints: List[Dict] = []
        self.current_wp = 0
        
        # Flight log
        self.flight_log: List[TelemetryPoint] = []
        self.is_logging = False
        self.flight_start_time = None
        
        # Simulation settings
        self.sim_speed_multiplier = 1.0
        
        # Telemetry history for charts
        self.altitude_history = deque(maxlen=100)
        self.battery_history = deque(maxlen=100)
        self.speed_history = deque(maxlen=100)
        
        # Create UI
        self._create_header()
        self._create_notebook()
        self._create_status_bar()
        
        # Initialize system
        self._init_system()
        
        # Start telemetry update
        self._start_telemetry()
    
    def _create_header(self):
        """Create header with logo and navigation"""
        header = tk.Frame(self, bg=self.colors['bg_secondary'], height=60)
        header.pack(fill='x', padx=0, pady=0)
        header.pack_propagate(False)
        
        # Logo
        logo = tk.Label(
            header, 
            text="SKYCORE GCS v2.0", 
            font=("Segoe UI", 18, "bold"),
            fg=self.colors['accent'],
            bg=self.colors['bg_secondary']
        )
        logo.pack(side='left', padx=15)
        
        # Simulation indicator
        self.sim_indicator = tk.Label(
            header,
            text="[SIMULATION]",
            font=("Segoe UI", 10, "bold"),
            fg=self.colors['warning'],
            bg=self.colors['bg_secondary']
        )
        self.sim_indicator.pack(side='left', padx=10)
        
        # Status indicator
        self.status_indicator = tk.Label(
            header,
            text="● DISARMED",
            font=("Segoe UI", 12),
            fg=self.colors['danger'],
            bg=self.colors['bg_secondary']
        )
        self.status_indicator.pack(side='left', padx=20)
        
        # Control buttons
        btn_frame = tk.Frame(header, bg=self.colors['bg_secondary'])
        btn_frame.pack(side='right', padx=10)
        
        tk.Button(btn_frame, text="ARM", width=7,
            bg=self.colors['success'], fg='#000',
            font=("Segoe UI", 9, "bold"),
            command=self._arm_drone
        ).pack(side='left', padx=1)
        
        tk.Button(btn_frame, text="TAKEOFF", width=7,
            bg=self.colors['accent'], fg='#000',
            font=("Segoe UI", 9, "bold"),
            command=self._takeoff
        ).pack(side='left', padx=1)
        
        tk.Button(btn_frame, text="LAND", width=6,
            bg=self.colors['warning'], fg='#000',
            font=("Segoe UI", 9, "bold"),
            command=self._land
        ).pack(side='left', padx=1)
        
        tk.Button(btn_frame, text="RTL", width=6,
            bg='#ff8800', fg='#fff',
            font=("Segoe UI", 9, "bold"),
            command=self._rtl
        ).pack(side='left', padx=1)
        
        tk.Button(btn_frame, text="E-STOP", width=6,
            bg='#ff0000', fg='#fff',
            font=("Segoe UI", 9, "bold"),
            command=self._emergency_stop
        ).pack(side='left', padx=1)
        
        tk.Button(btn_frame, text="LOG", width=5,
            bg='#666', fg='#fff',
            font=("Segoe UI", 9, "bold"),
            command=self._toggle_logging
        ).pack(side='left', padx=1)
    
    def _create_notebook(self):
        """Create tabbed interface"""
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab 1: Flight Control (main view)
        self._create_flight_tab()
        
        # Tab 2: Mission Planner
        self._create_mission_tab()
        
        # Tab 3: Flight Logs
        self._create_logs_tab()
        
        # Tab 4: Settings
        self._create_settings_tab()
    
    def _create_flight_tab(self):
        """Main flight control tab"""
        flight_frame = tk.Frame(self.notebook, bg=self.colors['bg_primary'])
        self.notebook.add(flight_frame, text="  Flight Control  ")
        
        # Left panel - Map
        left_frame = tk.Frame(flight_frame, bg=self.colors['bg_primary'])
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Map frame
        map_frame = tk.LabelFrame(
            left_frame, 
            text="FLIGHT MAP",
            font=("Segoe UI", 11),
            fg=self.colors['accent'],
            bg=self.colors['bg_secondary'],
            padx=5
        )
        map_frame.pack(fill='both', expand=True, padx=(0, 5), pady=(0, 5))
        
        self.map_canvas = tk.Canvas(
            map_frame, 
            bg='#0d1b2a',
            highlightthickness=0
        )
        self.map_canvas.pack(fill='both', expand=True)
        
        # Map click handler
        self.map_canvas.bind('<Button-1>', self._on_map_click)
        
        # Charts frame
        charts_frame = tk.Frame(left_frame, bg=self.colors['bg_primary'])
        charts_frame.pack(fill='x', pady=(5, 0))
        
        # Altitude chart
        alt_frame = tk.LabelFrame(
            charts_frame, text="ALTITUDE (m)",
            font=("Segoe UI", 9), fg=self.colors['accent'],
            bg=self.colors['bg_secondary'], padx=3
        )
        alt_frame.pack(side='left', fill='both', expand=True, padx=(0, 2))
        self.alt_canvas = tk.Canvas(alt_frame, height=80, bg=self.colors['bg_tertiary'], highlightthickness=0)
        self.alt_canvas.pack(fill='x')
        
        # Battery chart
        batt_frame = tk.LabelFrame(
            charts_frame, text="BATTERY (%)",
            font=("Segoe UI", 9), fg=self.colors['success'],
            bg=self.colors['bg_secondary'], padx=3
        )
        batt_frame.pack(side='left', fill='both', expand=True, padx=(2, 0))
        self.batt_canvas = tk.Canvas(batt_frame, height=80, bg=self.colors['bg_tertiary'], highlightthickness=0)
        self.batt_canvas.pack(fill='x')
        
        # Right panel - Telemetry
        right_frame = tk.Frame(flight_frame, bg=self.colors['bg_primary'])
        right_frame.pack(side='right', fill='both', padx=(5, 0))
        
        # Position info
        pos_frame = tk.LabelFrame(
            right_frame, text="POSITION",
            font=("Segoe UI", 10), fg=self.colors['accent'],
            bg=self.colors['bg_secondary'], padx=8
        )
        pos_frame.pack(fill='x', pady=(0, 3))
        
        self.pos_labels = {}
        for key, label, fmt in [("LAT", "Latitude", "{:.6f}°N"),
                                 ("LON", "Longitude", "{:.6f}°E"),
                                 ("ALT", "Altitude", "{:.1f} m"),
                                 ("SPD", "Speed", "{:.1f} m/s")]:
            row = tk.Frame(pos_frame, bg=self.colors['bg_secondary'])
            row.pack(fill='x', pady=1)
            tk.Label(row, text=f"{label}:", font=("Segoe UI", 9),
                    fg=self.colors['text_secondary'], bg=self.colors['bg_secondary'],
                    width=12, anchor='w').pack(side='left')
            val_label = tk.Label(row, text=fmt.format(0),
                               font=("Segoe UI", 10, "bold"),
                               fg=self.colors['text'], bg=self.colors['bg_secondary'])
            val_label.pack(side='left')
            self.pos_labels[key] = {'label': val_label, 'fmt': fmt}
        
        # Attitude info
        att_frame = tk.LabelFrame(
            right_frame, text="ATTITUDE",
            font=("Segoe UI", 10), fg=self.colors['accent'],
            bg=self.colors['bg_secondary'], padx=8
        )
        att_frame.pack(fill='x', pady=(0, 3))
        
        self.att_labels = {}
        for key, label in [("ROLL", "Roll"), ("PITCH", "Pitch"), ("YAW", "Yaw")]:
            row = tk.Frame(att_frame, bg=self.colors['bg_secondary'])
            row.pack(fill='x', pady=1)
            tk.Label(row, text=f"{label}:", font=("Segoe UI", 9),
                    fg=self.colors['text_secondary'], bg=self.colors['bg_secondary'],
                    width=12, anchor='w').pack(side='left')
            val_label = tk.Label(row, text="0.0°",
                               font=("Segoe UI", 10, "bold"),
                               fg=self.colors['text'], bg=self.colors['bg_secondary'])
            val_label.pack(side='left')
            self.att_labels[key] = val_label
        
        # Battery info
        batt_info_frame = tk.LabelFrame(
            right_frame, text="BATTERY",
            font=("Segoe UI", 10), fg=self.colors['success'],
            bg=self.colors['bg_secondary'], padx=8
        )
        batt_info_frame.pack(fill='x', pady=(0, 3))
        
        self.batt_percent_label = tk.Label(
            batt_info_frame, text="100%",
            font=("Segoe UI", 22, "bold"),
            fg=self.colors['success'],
            bg=self.colors['bg_secondary']
        )
        self.batt_percent_label.pack()
        self.batt_voltage_label = tk.Label(
            batt_info_frame, text="16.8V",
            font=("Segoe UI", 10),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary']
        )
        self.batt_voltage_label.pack()
        
        # Battery bar
        self.batt_bar = tk.Canvas(batt_info_frame, height=10, bg=self.colors['bg_tertiary'], highlightthickness=0)
        self.batt_bar.pack(fill='x', padx=5, pady=2)
        
        # GPS info
        gps_frame = tk.LabelFrame(
            right_frame, text="GPS",
            font=("Segoe UI", 10), fg=self.colors['accent'],
            bg=self.colors['bg_secondary'], padx=8
        )
        gps_frame.pack(fill='x', pady=(0, 3))
        
        self.gps_sats_label = tk.Label(
            gps_frame, text="0 satellites",
            font=("Segoe UI", 12),
            fg=self.colors['text'],
            bg=self.colors['bg_secondary']
        )
        self.gps_sats_label.pack()
        self.gps_hdop_label = tk.Label(
            gps_frame, text="HDOP: --",
            font=("Segoe UI", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary']
        )
        self.gps_hdop_label.pack()
        
        # Home info
        home_frame = tk.LabelFrame(
            right_frame, text="HOME",
            font=("Segoe UI", 10), fg=self.colors['warning'],
            bg=self.colors['bg_secondary'], padx=8
        )
        home_frame.pack(fill='x', pady=(0, 3))
        
        self.home_label = tk.Label(
            home_frame, text="32.0853°N, 34.7818°E",
            font=("Segoe UI", 9),
            fg=self.colors['text'],
            bg=self.colors['bg_secondary']
        )
        self.home_label.pack()
        
        tk.Button(home_frame, text="Set Home Here", 
                 command=self._set_home_from_position,
                 bg=self.colors['accent'], fg='#000'
        ).pack(pady=2)
        
        # Mission progress
        mission_frame = tk.LabelFrame(
            right_frame, text="MISSION",
            font=("Segoe UI", 10), fg=self.colors['warning'],
            bg=self.colors['bg_secondary'], padx=8
        )
        mission_frame.pack(fill='both', expand=True)
        
        self.mission_label = tk.Label(
            mission_frame, text="No mission loaded",
            font=("Segoe UI", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary']
        )
        self.mission_label.pack()
        
        self.wp_progress = tk.Label(
            mission_frame, text="WP: 0/0",
            font=("Segoe UI", 11, "bold"),
            fg=self.colors['accent'],
            bg=self.colors['bg_secondary']
        )
        self.wp_progress.pack()
        
        btn_row = tk.Frame(mission_frame, bg=self.colors['bg_secondary'])
        btn_row.pack(pady=5)
        
        tk.Button(btn_row, text="Load", width=6,
                 command=self._load_mission
        ).pack(side='left', padx=1)
        
        tk.Button(btn_row, text="Start", width=6,
                 bg=self.colors['success'], fg='#000',
                 command=self._start_mission
        ).pack(side='left', padx=1)
        
        tk.Button(btn_row, text="Pause", width=6,
                 command=self._pause_mission
        ).pack(side='left', padx=1)
        
        tk.Button(btn_row, text="Clear", width=6,
                 bg=self.colors['danger'], fg='#fff',
                 command=self._clear_mission
        ).pack(side='left', padx=1)
    
    def _create_mission_tab(self):
        """Mission planning tab"""
        mission_tab = tk.Frame(self.notebook, bg=self.colors['bg_primary'])
        self.notebook.add(mission_tab, text="  Mission Planner  ")
        
        # Waypoint list
        wp_frame = tk.LabelFrame(
            mission_tab, text="WAYPOINTS",
            font=("Segoe UI", 11), fg=self.colors['accent'],
            bg=self.colors['bg_secondary'], padx=10
        )
        wp_frame.pack(side='left', fill='both', expand=True, padx=(0, 5), pady=10)
        
        # Treeview for waypoints
        columns = ("#", "Latitude", "Longitude", "Altitude", "Action")
        self.wp_tree = ttk.Treeview(wp_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.wp_tree.heading(col, text=col)
            self.wp_tree.column(col, width=100, anchor='center')
        
        scrollbar = tk.Scrollbar(wp_frame, orient='vertical', command=self.wp_tree.yview)
        self.wp_tree.configure(yscrollcommand=scrollbar.set)
        
        self.wp_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Waypoint buttons
        wp_btn_frame = tk.Frame(mission_tab, bg=self.colors['bg_primary'])
        wp_btn_frame.pack(side='right', fill='y', padx=5, pady=10)
        
        tk.Button(wp_btn_frame, text="Add Waypoint", width=15,
                 bg=self.colors['success'], fg='#000',
                 command=self._add_waypoint
        ).pack(pady=2)
        
        tk.Button(wp_btn_frame, text="Add Current Position", width=15,
                 bg=self.colors['accent'], fg='#000',
                 command=self._add_current_position
        ).pack(pady=2)
        
        tk.Button(wp_btn_frame, text="Edit Selected", width=15,
                 bg=self.colors['warning'], fg='#000',
                 command=self._edit_waypoint
        ).pack(pady=2)
        
        tk.Button(wp_btn_frame, text="Delete Selected", width=15,
                 bg=self.colors['danger'], fg='#fff',
                 command=self._delete_waypoint
        ).pack(pady=2)
        
        tk.Button(wp_btn_frame, text="Move Up", width=15,
                 command=lambda: self._move_waypoint(-1)
        ).pack(pady=2)
        
        tk.Button(wp_btn_frame, text="Move Down", width=15,
                 command=lambda: self._move_waypoint(1)
        ).pack(pady=2)
        
        tk.Button(wp_btn_frame, text="Clear All", width=15,
                 bg=self.colors['danger'], fg='#fff',
                 command=self._clear_all_waypoints
        ).pack(pady=10)
        
        tk.Button(wp_btn_frame, text="Import from CSV", width=15,
                 bg='#888', fg='#fff',
                 command=self._import_waypoints_csv
        ).pack(pady=2)
        
        tk.Button(wp_btn_frame, text="Export to CSV", width=15,
                 bg='#888', fg='#fff',
                 command=self._export_waypoints_csv
        ).pack(pady=2)
    
    def _create_logs_tab(self):
        """Flight logs tab"""
        logs_tab = tk.Frame(self.notebook, bg=self.colors['bg_primary'])
        self.notebook.add(logs_tab, text="  Flight Logs  ")
        
        # Log controls
        ctrl_frame = tk.LabelFrame(
            logs_tab, text="LOGGING",
            font=("Segoe UI", 10), fg=self.colors['accent'],
            bg=self.colors['bg_secondary'], padx=10
        )
        ctrl_frame.pack(fill='x', padx=10, pady=5)
        
        self.logging_status = tk.Label(
            ctrl_frame, text="Logging: OFF",
            font=("Segoe UI", 11, "bold"),
            fg=self.colors['danger'],
            bg=self.colors['bg_secondary']
        )
        self.logging_status.pack(side='left', padx=10)
        
        self.log_duration = tk.Label(
            ctrl_frame, text="Duration: 00:00:00",
            font=("Segoe UI", 11),
            fg=self.colors['text'],
            bg=self.colors['bg_secondary']
        )
        self.log_duration.pack(side='left', padx=20)
        
        tk.Button(ctrl_frame, text="Start Logging", width=12,
                 bg=self.colors['success'], fg='#000',
                 command=self._toggle_logging
        ).pack(side='left', padx=5)
        
        tk.Button(ctrl_frame, text="Export Log", width=12,
                 bg=self.colors['accent'], fg='#000',
                 command=self._export_flight_log
        ).pack(side='left', padx=5)
        
        tk.Button(ctrl_frame, text="Import Log", width=12,
                 bg='#888', fg='#fff',
                 command=self._import_flight_log
        ).pack(side='left', padx=5)
        
        tk.Button(ctrl_frame, text="Clear Log", width=12,
                 bg=self.colors['danger'], fg='#fff',
                 command=self._clear_flight_log
        ).pack(side='left', padx=5)
        
        # Flight log text
        log_frame = tk.LabelFrame(
            logs_tab, text="FLIGHT LOG",
            font=("Segoe UI", 10), fg=self.colors['accent'],
            bg=self.colors['bg_secondary'], padx=5
        )
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(
            log_frame,
            bg=self.colors['bg_tertiary'],
            fg=self.colors['text'],
            font=("Consolas", 9),
            relief='flat',
            state='disabled'
        )
        
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
    def _create_settings_tab(self):
        """Settings tab"""
        settings_tab = tk.Frame(self.notebook, bg=self.colors['bg_primary'])
        self.notebook.add(settings_tab, text="  Settings  ")
        
        # Simulation settings
        sim_frame = tk.LabelFrame(
            settings_tab, text="SIMULATION SETTINGS",
            font=("Segoe UI", 11), fg=self.colors['warning'],
            bg=self.colors['bg_secondary'], padx=15
        )
        sim_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(sim_frame, text="Speed Multiplier:",
                bg=self.colors['bg_secondary'], fg=self.colors['text']
        ).pack(anchor='w', pady=2)
        
        self.sim_speed_var = tk.DoubleVar(value=1.0)
        sim_scale = tk.Scale(sim_frame, from_=0.1, to=10.0, orient='horizontal',
                           variable=self.sim_speed_var, length=300,
                           command=self._update_sim_speed)
        sim_scale.pack(anchor='w', pady=5)
        
        tk.Label(sim_frame, text="(0.1x - 10x speed)",
                bg=self.colors['bg_secondary'], fg=self.colors['text_secondary']
        ).pack(anchor='w')
        
        # Home position
        home_frame = tk.LabelFrame(
            settings_tab, text="HOME POSITION",
            font=("Segoe UI", 11), fg=self.colors['accent'],
            bg=self.colors['bg_secondary'], padx=15
        )
        home_frame.pack(fill='x', padx=10, pady=5)
        
        self.home_lat_var = tk.StringVar(value="32.0853")
        self.home_lon_var = tk.StringVar(value="34.7818")
        
        tk.Label(home_frame, text="Latitude:", bg=self.colors['bg_secondary']
        ).grid(row=0, column=0, sticky='w', pady=2)
        tk.Entry(home_frame, textvariable=self.home_lat_var, width=15
        ).grid(row=0, column=1, padx=5, pady=2)
        
        tk.Label(home_frame, text="Longitude:", bg=self.colors['bg_secondary']
        ).grid(row=1, column=0, sticky='w', pady=2)
        tk.Entry(home_frame, textvariable=self.home_lon_var, width=15
        ).grid(row=1, column=1, padx=5, pady=2)
        
        tk.Button(home_frame, text="Set Home", bg=self.colors['accent'], fg='#000',
                 command=self._set_home_from_entries
        ).grid(row=0, column=2, rowspan=2, padx=10)
        
        # Alerts
        alert_frame = tk.LabelFrame(
            settings_tab, text="SYSTEM ALERTS",
            font=("Segoe UI", 11), fg=self.colors['danger'],
            bg=self.colors['bg_secondary'], padx=15
        )
        alert_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.alerts_text = tk.Text(
            alert_frame,
            bg=self.colors['bg_tertiary'],
            fg=self.colors['text'],
            font=("Consolas", 9),
            relief='flat',
            state='disabled',
            height=15
        )
        self.alerts_text.pack(fill='both', expand=True)
    
    def _create_status_bar(self):
        """Create bottom status bar"""
        status = tk.Frame(self, bg=self.colors['bg_secondary'], height=25)
        status.pack(fill='x', side='bottom')
        status.pack_propagate(False)
        
        self.status_label = tk.Label(
            status,
            text="SkyCore GCS v2.0 | Simulation Mode | Press ARM to begin",
            font=("Segoe UI", 8),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary'],
            anchor='w'
        )
        self.status_label.pack(side='left', padx=10)
        
        self.time_label = tk.Label(
            status,
            text=datetime.now().strftime("%H:%M:%S"),
            font=("Segoe UI", 8),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary']
        )
        self.time_label.pack(side='right', padx=10)
        
        self._update_clock()
    
    def _init_system(self):
        """Initialize SkyCore system"""
        if SKYCORE_AVAILABLE:
            try:
                self.system = SkyCoreSystem()
                self.system.initialize()
                self._add_alert("INFO", "SkyCore system initialized")
                self._add_log("System initialized successfully")
            except Exception as e:
                self._add_alert("WARN", f"Could not initialize SkyCore: {e}")
        
        self._add_log("GCS Desktop v2.0 started")
    
    def _start_telemetry(self):
        """Start telemetry update loop"""
        self.is_running = True
        self._update_telemetry()
    
    def _update_telemetry(self):
        """Update telemetry display"""
        if not self.is_running:
            return
        
        try:
            self._update_simulated_telemetry()
            self._draw_charts()
            self._draw_map()
            self._update_notebook_tab_colors()
        except Exception as e:
            pass
        
        self.after(100, self._update_telemetry)
    
    def _update_simulated_telemetry(self):
        """Update simulated telemetry data"""
        # Simulate based on state
        if self.sim_position['alt'] > 0:
            # In flight
            self.sim_position['lat'] += random.uniform(-0.00002, 0.00002) * self.sim_speed_multiplier
            self.sim_position['lon'] += random.uniform(-0.00002, 0.00002) * self.sim_speed_multiplier
            
            # Altitude changes
            if self.sim_speed != 0:
                self.sim_position['alt'] += random.uniform(-0.5, 0.5)
                self.sim_position['alt'] = max(0, min(150, self.sim_position['alt']))
            
            self.sim_speed = 5.0 + random.uniform(-1, 1) * self.sim_speed_multiplier
            self.sim_battery -= 0.005 * self.sim_speed_multiplier
            
            # Attitude variation
            self.sim_attitude['roll'] = random.uniform(-3, 3)
            self.sim_attitude['pitch'] = random.uniform(-3, 3)
            self.sim_attitude['yaw'] = (self.sim_attitude['yaw'] + random.uniform(-1, 1)) % 360
            
            # Record flight path
            if len(self.flight_path) < self.max_path_points:
                self.flight_path.append((self.sim_position['lat'], self.sim_position['lon']))
            
            # Log telemetry point
            if self.is_logging:
                self._log_telemetry_point()
        else:
            self.sim_speed = 0
        
        self.sim_battery = max(0, min(100, self.sim_battery))
        
        # Update displays
        self.pos_labels['LAT']['label'].config(text=self.pos_labels['LAT']['fmt'].format(self.sim_position['lat']))
        self.pos_labels['LON']['label'].config(text=self.pos_labels['LON']['fmt'].format(self.sim_position['lon']))
        self.pos_labels['ALT']['label'].config(text=self.pos_labels['ALT']['fmt'].format(self.sim_position['alt']))
        self.pos_labels['SPD']['label'].config(text=self.pos_labels['SPD']['fmt'].format(self.sim_speed))
        
        self.att_labels['ROLL'].config(text=f"{self.sim_attitude['roll']:.1f}°")
        self.att_labels['PITCH'].config(text=f"{self.sim_attitude['pitch']:.1f}°")
        self.att_labels['YAW'].config(text=f"{self.sim_attitude['yaw']:.1f}°")
        
        # Battery
        self.batt_percent_label.config(text=f"{self.sim_battery:.0f}%")
        self.batt_voltage_label.config(text=f"{12.4 + self.sim_battery/100 * 4.4:.1f}V")
        
        if self.sim_battery > 50:
            color = self.colors['success']
        elif self.sim_battery > 20:
            color = self.colors['warning']
        else:
            color = self.colors['danger']
        
        self.batt_percent_label.config(fg=color)
        self._update_battery_bar()
        
        # GPS
        sat_count = random.randint(8, 16) if self.sim_position['alt'] >= 0 else 0
        self.gps_sats_label.config(text=f"{sat_count} satellites")
        self.gps_hdop_label.config(text=f"HDOP: {random.uniform(0.8, 1.5):.1f}")
        
        # Store history
        self.altitude_history.append(self.sim_position['alt'])
        self.battery_history.append(self.sim_battery)
        self.speed_history.append(self.sim_speed)
        
        # Update mission label
        if self.mission_waypoints:
            self.mission_label.config(text=f"Mission: {len(self.mission_waypoints)} waypoints")
            self.wp_progress.config(text=f"WP: {self.current_wp}/{len(self.mission_waypoints)}")
    
    def _update_battery_bar(self):
        """Update battery visual bar"""
        self.batt_bar.delete('all')
        width = self.batt_bar.winfo_width() or 150
        height = 10
        
        fill_width = int((self.sim_battery / 100) * width)
        
        color = self.colors['success']
        if self.sim_battery < 50:
            color = self.colors['warning']
        if self.sim_battery < 20:
            color = self.colors['danger']
        
        self.batt_bar.create_rectangle(0, 0, fill_width, height, fill=color, outline='')
    
    def _draw_charts(self):
        """Draw telemetry charts"""
        # Altitude chart
        self.alt_canvas.delete('all')
        w = self.alt_canvas.winfo_width() or 200
        h = self.alt_canvas.winfo_height() or 80
        
        if len(self.altitude_history) > 1:
            max_alt = max(max(self.altitude_history), 1)
            points = []
            for i, alt in enumerate(self.altitude_history):
                x = (i / (len(self.altitude_history) - 1)) * w
                y = h - (alt / max_alt) * (h - 5)
                points.append((x, y))
            
            for i in range(len(points) - 1):
                self.alt_canvas.create_line(
                    points[i][0], points[i][1],
                    points[i+1][0], points[i+1][1],
                    fill=self.colors['accent'], width=2
                )
        
        # Battery chart
        self.batt_canvas.delete('all')
        w = self.batt_canvas.winfo_width() or 200
        h = self.batt_canvas.winfo_height() or 80
        
        if len(self.battery_history) > 1:
            points = []
            for i, batt in enumerate(self.battery_history):
                x = (i / (len(self.battery_history) - 1)) * w
                y = h - (batt / 100) * (h - 5)
                points.append((x, y))
            
            for i in range(len(points) - 1):
                y = points[i+1][1]
                if y < h * 0.2:
                    color = self.colors['danger']
                elif y < h * 0.5:
                    color = self.colors['warning']
                else:
                    color = self.colors['success']
                
                self.batt_canvas.create_line(
                    points[i][0], points[i][1],
                    points[i+1][0], points[i+1][1],
                    fill=color, width=2
                )
    
    def _draw_map(self):
        """Draw map with drone position and flight path"""
        self.map_canvas.delete('all')
        w = self.map_canvas.winfo_width() or 600
        h = self.map_canvas.winfo_height() or 400
        
        # Draw grid
        for i in range(0, w, 40):
            self.map_canvas.create_line(i, 0, i, h, fill='#1a2a4a', width=1)
        for i in range(0, h, 40):
            self.map_canvas.create_line(0, i, w, i, fill='#1a2a4a', width=1)
        
        # Draw home position (center)
        cx, cy = w // 2, h // 2
        self.map_canvas.create_oval(cx-12, cy-12, cx+12, cy+12, fill='#ff8800', outline='#ffaa00', width=2)
        self.map_canvas.create_text(cx, cy+22, text="HOME", fill='#ffaa00', font=("Segoe UI", 9, "bold"))
        
        # Draw mission waypoints
        home_lat, home_lon = 32.0853, 34.7818
        for i, wp in enumerate(self.mission_waypoints):
            px = cx + (wp['lon'] - home_lon) * 50000
            py = cy - (wp['lat'] - home_lat) * 50000
            
            # Waypoint circle
            is_current = (i == self.current_wp)
            color = self.colors['success'] if is_current else self.colors['accent']
            radius = 10 if is_current else 6
            
            self.map_canvas.create_oval(px-radius, py-radius, px+radius, py+radius, 
                                       fill=color, outline='#fff', width=2)
            self.map_canvas.create_text(px, py-15, text=f"WP{i+1}", fill=color, font=("Segoe UI", 8, "bold"))
            
            # Connect to next waypoint
            if i < len(self.mission_waypoints) - 1:
                next_wp = self.mission_waypoints[i + 1]
                npx = cx + (next_wp['lon'] - home_lon) * 50000
                npy = cy - (next_wp['lat'] - home_lat) * 50000
                self.map_canvas.create_line(px, py, npx, npy, fill=self.colors['accent'], width=1, dash=(4, 2))
        
        # Draw flight path
        if len(self.flight_path) > 1:
            path_points = []
            for lat, lon in self.flight_path:
                px = cx + (lon - home_lon) * 50000
                py = cy - (lat - home_lat) * 50000
                path_points.append((px, py))
            
            for i in range(len(path_points) - 1):
                alpha = i / len(path_points)
                color = f"#{int(255*alpha):02x}{int(255*(1-alpha)):02x}{int(255*(1-alpha)):02x}"
                self.map_canvas.create_line(
                    path_points[i][0], path_points[i][1],
                    path_points[i+1][0], path_points[i+1][1],
                    fill=color, width=2
                )
        
        # Draw current drone position
        if self.sim_position['alt'] > 0:
            px = cx + (self.sim_position['lon'] - home_lon) * 50000
            py = cy - (self.sim_position['lat'] - home_lat) * 50000
            
            # Drone triangle
            yaw_rad = math.radians(self.sim_attitude['yaw'])
            points = [
                (px, py-20),
                (px - 12, py + 10),
                (px + 12, py + 10)
            ]
            self.map_canvas.create_polygon(points, fill=self.colors['success'], outline='#fff', width=2)
            
            # Direction indicator
            dir_x = px + math.sin(yaw_rad) * 25
            dir_y = py - math.cos(yaw_rad) * 25
            self.map_canvas.create_line(px, py, dir_x, dir_y, fill=self.colors['accent'], width=3)
    
    def _update_clock(self):
        """Update status bar clock"""
        self.time_label.config(text=datetime.now().strftime("%H:%M:%S"))
        
        if self.is_logging and self.flight_start_time:
            duration = int(time.time() - self.flight_start_time)
            hrs = duration // 3600
            mins = (duration % 3600) // 60
            secs = duration % 60
            self.log_duration.config(text=f"Duration: {hrs:02d}:{mins:02d}:{secs:02d}")
        
        self.after(1000, self._update_clock)
    
    def _update_notebook_tab_colors(self):
        """Update notebook tab colors based on state"""
        if self.sim_position['alt'] > 0:
            self.notebook.tab(0, foreground=self.colors['success'])
        else:
            self.notebook.tab(0, foreground=self.colors['text'])
    
    def _update_sim_speed(self, val):
        """Update simulation speed"""
        self.sim_speed_multiplier = float(val)
    
    # Control methods
    def _arm_drone(self):
        self._add_alert("INFO", "ARM command sent")
        self._add_log("Drone ARMED")
        self.sim_position['alt'] = 0.1
        self.status_indicator.config(text="● ARMED", fg=self.colors['warning'])
        self.flight_path.clear()
    
    def _takeoff(self):
        self._add_alert("INFO", "TAKEOFF command sent")
        self._add_log("TAKEOFF initiated - altitude: 20m")
        self.sim_position['alt'] = 20.0
        self.status_indicator.config(text="● AUTO", fg=self.colors['success'])
    
    def _land(self):
        self._add_alert("INFO", "LAND command sent")
        self._add_log("LANDING initiated")
        self.sim_position['alt'] = 0.0
        self.sim_speed = 0.0
        self.status_indicator.config(text="● LANDING", fg=self.colors['warning'])
        self.after(2000, lambda: self.status_indicator.config(text="● ARMED", fg=self.colors['warning']))
    
    def _rtl(self):
        self._add_alert("WARN", "RTL - Returning to launch")
        self._add_log("RTL - Returning to home")
        self.sim_position['lat'] = 32.0853
        self.sim_position['lon'] = 34.7818
        self.status_indicator.config(text="● RTL", fg=self.colors['warning'])
    
    def _emergency_stop(self):
        self._add_alert("ERROR", "EMERGENCY STOP!")
        self._add_log("EMERGENCY STOP ACTIVATED")
        self.sim_position['alt'] = 0.0
        self.sim_speed = 0.0
        self.status_indicator.config(text="● ESTOP", fg='#ff0000')
        messagebox.showerror("Emergency Stop", "Emergency stop activated!")
    
    def _toggle_logging(self):
        if self.is_logging:
            self.is_logging = False
            self.logging_status.config(text="Logging: OFF", fg=self.colors['danger'])
            self._add_log("Logging stopped")
        else:
            self.is_logging = True
            self.flight_start_time = time.time()
            self.flight_log.clear()
            self.logging_status.config(text="Logging: ON", fg=self.colors['success'])
            self._add_log("Logging started")
    
    def _log_telemetry_point(self):
        point = TelemetryPoint(
            time.time(),
            self.sim_position['lat'],
            self.sim_position['lon'],
            self.sim_position['alt'],
            self.sim_speed,
            self.sim_attitude['roll'],
            self.sim_attitude['pitch'],
            self.sim_attitude['yaw'],
            self.sim_battery,
            random.randint(8, 16)
        )
        self.flight_log.append(point)
    
    def _export_flight_log(self):
        if not self.flight_log:
            messagebox.showinfo("Export", "No flight log to export")
            return
        
        path = filedialog.asksaveasfilename(
            title="Export Flight Log",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")]
        )
        
        if path:
            try:
                if path.endswith('.json'):
                    with open(path, 'w') as f:
                        json.dump([p.to_dict() for p in self.flight_log], f, indent=2)
                else:
                    with open(path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['timestamp', 'lat', 'lon', 'alt', 'speed', 'roll', 'pitch', 'yaw', 'battery', 'satellites'])
                        for p in self.flight_log:
                            writer.writerow([p.timestamp, p.lat, p.lon, p.alt, p.speed, p.roll, p.pitch, p.yaw, p.battery, p.satellites])
                
                self._add_log(f"Flight log exported to {path}")
                messagebox.showinfo("Export", f"Exported {len(self.flight_log)} points")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def _import_flight_log(self):
        path = filedialog.askopenfilename(
            title="Import Flight Log",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if path:
            try:
                self.flight_log.clear()
                if path.endswith('.json'):
                    with open(path, 'r') as f:
                        data = json.load(f)
                        self.flight_log = [TelemetryPoint.from_dict(d) for d in data]
                else:
                    with open(path, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            p = TelemetryPoint(
                                float(row['timestamp']), float(row['lat']), float(row['lon']),
                                float(row['alt']), float(row['speed']), float(row['roll']),
                                float(row['pitch']), float(row['yaw']), float(row['battery']),
                                int(row['satellites'])
                            )
                            self.flight_log.append(p)
                
                self._add_log(f"Imported {len(self.flight_log)} points")
                messagebox.showinfo("Import", f"Imported {len(self.flight_log)} points")
            except Exception as e:
                messagebox.showerror("Import Error", str(e))
    
    def _clear_flight_log(self):
        self.flight_log.clear()
        self._add_log("Flight log cleared")
    
    def _add_waypoint(self):
        """Add a new waypoint"""
        lat = simpledialog.askfloat("Waypoint", "Latitude:", initialvalue=32.0853)
        if lat is None:
            return
        lon = simpledialog.askfloat("Waypoint", "Longitude:", initialvalue=34.7818)
        if lon is None:
            return
        alt = simpledialog.askfloat("Waypoint", "Altitude (m):", initialvalue=20)
        if alt is None:
            return
        
        wp = {"lat": lat, "lon": lon, "alt": alt}
        self.mission_waypoints.append(wp)
        self._update_waypoint_tree()
        self._add_log(f"Waypoint added: {lat:.6f}, {lon:.6f}, {alt}m")
    
    def _add_current_position(self):
        """Add current position as waypoint"""
        wp = {
            "lat": self.sim_position['lat'],
            "lon": self.sim_position['lon'],
            "alt": max(20, self.sim_position['alt'] + 10)
        }
        self.mission_waypoints.append(wp)
        self._update_waypoint_tree()
        self._add_log(f"Waypoint added at current position")
    
    def _edit_waypoint(self):
        """Edit selected waypoint"""
        selection = self.wp_tree.selection()
        if not selection:
            messagebox.showinfo("Edit", "Select a waypoint to edit")
            return
        
        idx = int(selection[0].split('I')[1]) - 1
        wp = self.mission_waypoints[idx]
        
        lat = simpledialog.askfloat("Edit Waypoint", "Latitude:", initialvalue=wp['lat'])
        if lat is None:
            return
        lon = simpledialog.askfloat("Edit Waypoint", "Longitude:", initialvalue=wp['lon'])
        if lon is None:
            return
        alt = simpledialog.askfloat("Edit Waypoint", "Altitude:", initialvalue=wp['alt'])
        if alt is None:
            return
        
        self.mission_waypoints[idx] = {"lat": lat, "lon": lon, "alt": alt}
        self._update_waypoint_tree()
    
    def _delete_waypoint(self):
        """Delete selected waypoint"""
        selection = self.wp_tree.selection()
        if not selection:
            return
        
        idx = int(selection[0].split('I')[1]) - 1
        self.mission_waypoints.pop(idx)
        self._update_waypoint_tree()
    
    def _move_waypoint(self, direction):
        """Move waypoint up or down"""
        selection = self.wp_tree.selection()
        if not selection:
            return
        
        idx = int(selection[0].split('I')[1]) - 1
        new_idx = idx + direction
        
        if 0 <= new_idx < len(self.mission_waypoints):
            self.mission_waypoints[idx], self.mission_waypoints[new_idx] = \
                self.mission_waypoints[new_idx], self.mission_waypoints[idx]
            self._update_waypoint_tree()
    
    def _clear_all_waypoints(self):
        """Clear all waypoints"""
        self.mission_waypoints.clear()
        self._update_waypoint_tree()
        self.current_wp = 0
    
    def _import_waypoints_csv(self):
        """Import waypoints from CSV"""
        path = filedialog.askopenfilename(
            title="Import Waypoints",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if path:
            try:
                with open(path, 'r') as f:
                    reader = csv.reader(f)
                    next(reader, None)  # skip header
                    for row in reader:
                        if len(row) >= 3:
                            self.mission_waypoints.append({
                                "lat": float(row[0]),
                                "lon": float(row[1]),
                                "alt": float(row[2])
                            })
                self._update_waypoint_tree()
                self._add_log(f"Imported {len(self.mission_waypoints)} waypoints")
            except Exception as e:
                messagebox.showerror("Import Error", str(e))
    
    def _export_waypoints_csv(self):
        """Export waypoints to CSV"""
        if not self.mission_waypoints:
            messagebox.showinfo("Export", "No waypoints to export")
            return
        
        path = filedialog.asksaveasfilename(
            title="Export Waypoints",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        
        if path:
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['lat', 'lon', 'alt'])
                    for wp in self.mission_waypoints:
                        writer.writerow([wp['lat'], wp['lon'], wp['alt']])
                self._add_log(f"Exported waypoints to {path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def _update_waypoint_tree(self):
        """Update waypoint treeview"""
        self.wp_tree.delete(*self.wp_tree.get_children())
        for i, wp in enumerate(self.mission_waypoints):
            self.wp_tree.insert('', 'end', iid=f'I{i+1}', values=(
                i+1, f"{wp['lat']:.6f}", f"{wp['lon']:.6f}", 
                f"{wp['alt']:.1f}", "Delete"
            ))
    
    def _load_mission(self):
        """Load mission from waypoint list"""
        if not self.mission_waypoints:
            messagebox.showinfo("Load Mission", "No waypoints defined")
            return
        
        self.current_wp = 0
        self._add_log(f"Mission loaded: {len(self.mission_waypoints)} waypoints")
    
    def _start_mission(self):
        """Start mission execution"""
        if not self.mission_waypoints:
            messagebox.showinfo("Start Mission", "No mission loaded")
            return
        
        self._add_log("Mission started")
        self.sim_position['alt'] = 20.0
        self.status_indicator.config(text="● AUTO", fg=self.colors['success'])
        self._execute_mission_step()
    
    def _execute_mission_step(self):
        """Execute current mission step"""
        if self.current_wp >= len(self.mission_waypoints):
            self._add_log("Mission complete!")
            self._land()
            return
        
        wp = self.mission_waypoints[self.current_wp]
        self._add_log(f"Flying to WP{self.current_wp + 1}: {wp['lat']:.5f}, {wp['lon']:.5f}")
        
        # Move towards waypoint
        self.sim_position['lat'] = wp['lat']
        self.sim_position['lon'] = wp['lon']
        
        self.after(3000, self._next_waypoint)
    
    def _next_waypoint(self):
        self.current_wp += 1
        if self.current_wp < len(self.mission_waypoints):
            self._execute_mission_step()
        else:
            self._add_log("All waypoints reached")
            self._land()
    
    def _pause_mission(self):
        """Pause mission"""
        self._add_log("Mission paused")
        self.status_indicator.config(text="● HOLD", fg=self.colors['warning'])
    
    def _clear_mission(self):
        """Clear current mission"""
        self.mission_waypoints.clear()
        self.current_wp = 0
        self._update_waypoint_tree()
        self._add_log("Mission cleared")
    
    def _set_home_from_position(self):
        """Set home to current position"""
        self.home_lat_var.set(f"{self.sim_position['lat']:.6f}")
        self.home_lon_var.set(f"{self.sim_position['lon']:.6f}")
        self._add_log(f"Home set to: {self.sim_position['lat']:.6f}, {self.sim_position['lon']:.6f}")
    
    def _set_home_from_entries(self):
        """Set home from entry fields"""
        try:
            lat = float(self.home_lat_var.get())
            lon = float(self.home_lon_var.get())
            self._add_log(f"Home set to: {lat}, {lon}")
        except:
            messagebox.showerror("Invalid", "Enter valid coordinates")
    
    def _on_map_click(self, event):
        """Handle map click - add waypoint"""
        w = self.map_canvas.winfo_width()
        h = self.map_canvas.winfo_height()
        
        cx, cy = w // 2, h // 2
        home_lat, home_lon = 32.0853, 34.7818
        
        # Convert click to lat/lon
        click_lon = home_lon + (event.x - cx) / 50000
        click_lat = home_lat - (event.y - cy) / 50000
        
        alt = simpledialog.askfloat("Add Waypoint", "Altitude (m):", initialvalue=20)
        if alt is not None:
            self.mission_waypoints.append({"lat": click_lat, "lon": click_lon, "alt": alt})
            self._update_waypoint_tree()
            self._add_log(f"Waypoint added from map")
    
    def _add_alert(self, level, message):
        """Add system alert"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.alerts_text.config(state='normal')
        self.alerts_text.insert('end', f"[{timestamp}] {level}: {message}\n")
        self.alerts_text.see('end')
        self.alerts_text.config(state='disabled')
    
    def _add_log(self, message):
        """Add to flight log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.log_text.config(state='normal')
        self.log_text.insert('end', f"[{timestamp}] {message}\n")
        self.log_text.see('end')
        self.log_text.config(state='disabled')


def main():
    """Main entry point"""
    app = SkyCoreDesktopGCS()
    app.mainloop()


if __name__ == "__main__":
    main()