#!/usr/bin/env python3
"""
SkyCore - Autonomous Drone Platform
Main entry point for the complete autonomous drone system.

Usage:
    python main.py                    # Start with default config
    python main.py --config config.json # Start with custom config
    python main.py --simulate         # Run in simulation mode
    python main.py --test             # Run system tests
    python main.py --gcs              # Start GCS web interface
    python main.py --desktop          # Start desktop GCS application
"""

import argparse
import sys
import os
import time
import json
import signal
from typing import Optional

# Add package to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skycore.system import SkyCoreSystem, create_system


class SkyCoreCLI:
    """
    Command-line interface for SkyCore autonomous drone platform.
    """
    
    def __init__(self):
        self.system: Optional[SkyCoreSystem] = None
        self.running = False
        self.parser = self._setup_argument_parser()
    
    def _setup_argument_parser(self) -> argparse.ArgumentParser:
        """Setup command-line argument parser"""
        parser = argparse.ArgumentParser(
            description="SkyCore Autonomous Drone Platform",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s                      Start with default configuration
  %(prog)s --config custom.json Start with custom configuration
  %(prog)s --simulate           Run in simulation mode
  %(prog)s --gcs                 Start GCS web interface
  %(prog)s --test               Run system tests
  %(prog)s --info               Display system information

For more information, visit: https://github.com/skycore/drone
            """
        )
        
        parser.add_argument(
            "--config", "-c",
            type=str,
            default="config/default.json",
            help="Path to configuration file (default: config/default.json)"
        )
        
        parser.add_argument(
            "--simulate", "-s",
            action="store_true",
            help="Run in simulation mode"
        )
        
        parser.add_argument(
            "--gcs", "-g",
            action="store_true",
            help="Start GCS web interface"
        )
        
        parser.add_argument(
            "--gcs-port",
            type=int,
            default=8000,
            help="GCS web server port (default: 8000)"
        )
        
        parser.add_argument(
            "--test", "-t",
            action="store_true",
            help="Run system tests and exit"
        )
        
        parser.add_argument(
            "--info", "-i",
            action="store_true",
            help="Display system information"
        )
        
        parser.add_argument(
            "--log-level",
            type=str,
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            help="Set logging level (default: INFO)"
        )
        
        parser.add_argument(
            "--version", "-v",
            action="store_true",
            help="Display version information"
        )
        
        parser.add_argument(
            "--desktop", "-d",
            action="store_true",
            help="Start desktop GCS application (Tkinter)"
        )
        
        return parser
    
    def run(self, args: Optional[list] = None):
        """Run CLI with given arguments"""
        parsed_args = self.parser.parse_args(args)
        
        # Handle version
        if parsed_args.version:
            self.print_version()
            return 0
        
        # Handle info
        if parsed_args.info:
            self.print_info()
            return 0
        
        # Handle tests
        if parsed_args.test:
            return self.run_tests()
        
        # Handle GCS mode
        if parsed_args.gcs:
            return self.start_gcs(parsed_args.gcs_port)
        
        # Handle desktop mode
        if parsed_args.desktop:
            return self.start_desktop()
        
        # Normal mode - start the system
        return self.start_system(parsed_args)
    
    def start_system(self, args) -> int:
        """Start the drone system"""
        print("=" * 60)
        print("  SKYCORE AUTONOMOUS DRONE PLATFORM")
        print("=" * 60)
        print()
        
        # Check config file exists
        if not os.path.exists(args.config):
            print(f"[ERROR] Configuration file not found: {args.config}")
            print("        Using default configuration...")
            args.config = None
        
        # Create and initialize system
        print("[CLI] Creating SkyCore system...")
        self.system = create_system(args.config)
        
        if not self.system:
            print("[CLI] Failed to create system")
            return 1
        
        print("[CLI] Initializing system...")
        if not self.system.initialize():
            print("[CLI] System initialization failed")
            return 1
        
        print()
        print("[CLI] System ready!")
        print()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Start system
        self.system.start()
        self.running = True
        
        print("[CLI] SkyCore is running. Press Ctrl+C to stop.")
        print()
        
        # Main loop
        try:
            while self.running:
                self._print_status()
                time.sleep(5)  # Print status every 5 seconds
        except KeyboardInterrupt:
            pass
        
        # Stop system
        self.stop_system()
        
        return 0
    
    def start_gcs(self, port: int) -> int:
        """Start GCS web interface"""
        print("=" * 60)
        print("  SKYCORE GCS WEB INTERFACE")
        print("=" * 60)
        print()
        
        # Change to package directory
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        # Start HTTP server
        try:
            import http.server
            import socketserver
            
            os.chdir("gcs")
            
            class QuietHandler(http.server.SimpleHTTPRequestHandler):
                def log_message(self, format, *args):
                    pass  # Suppress logging
            
            with socketserver.TCPServer(("", port), QuietHandler) as httpd:
                print(f"[GCS] Server running at http://localhost:{port}")
                print(f"[GCS] Press Ctrl+C to stop")
                print()
                httpd.serve_forever()
                
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"[ERROR] Port {port} is already in use")
                return 1
            raise
        
        return 0
    
    def start_desktop(self) -> int:
        """Start desktop GCS application"""
        print("=" * 60)
        print("  SKYCORE DESKTOP GCS")
        print("=" * 60)
        print()
        
        try:
            # Import the desktop app
            from gcs_desktop import main as desktop_main
            print("[DESKTOP] Launching desktop GCS application...")
            print()
            # Run the desktop app (blocking)
            desktop_main()
            return 0
        except ImportError as e:
            print(f"[ERROR] Failed to import desktop app: {e}")
            return 1
        except Exception as e:
            print(f"[ERROR] Failed to start desktop app: {e}")
            return 1
    
    def run_tests(self) -> int:
        """Run system tests"""
        print("=" * 60)
        print("  SKYCORE SYSTEM TESTS")
        print("=" * 60)
        print()
        
        try:
            import pytest
            print("[TEST] Running pytest...")
            print()
            
            # Run pytest
            exit_code = pytest.main([
                "-v",
                "--tb=short",
                "tests/"
            ])
            
            print()
            if exit_code == 0:
                print("[TEST] All tests passed!")
            else:
                print(f"[TEST] Tests failed with exit code: {exit_code}")
            
            return exit_code
            
        except ImportError:
            print("[ERROR] pytest not installed. Run: pip install pytest")
            return 1
    
    def stop_system(self):
        """Stop the drone system"""
        print()
        print("[CLI] Stopping SkyCore...")
        
        if self.system:
            self.system.stop()
        
        self.running = False
        print("[CLI] SkyCore stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print()
        print("[CLI] Received shutdown signal...")
        self.running = False
    
    def _print_status(self):
        """Print current system status"""
        if not self.system:
            return
        
        state = self.system.get_state()
        
        # Clear screen and print header
        print("\033[2J\033[H")  # Clear screen
        print("=" * 60)
        print("  SKYCORE STATUS")
        print("=" * 60)
        print()
        
        # System info
        sys_info = state.get("system", {})
        print(f"  Uptime:     {self._format_uptime(sys_info.get('uptime_sec', 0))}")
        print(f"  Cycles:     {sys_info.get('cycle_count', 0):,}")
        print(f"  Errors:     {sys_info.get('error_count', 0)}")
        print()
        
        # Flight state
        flight = state.get("flight", {})
        print(f"  State:      {flight.get('current_state', 'unknown').upper()}")
        print(f"  Mode:       {flight.get('mode', 'unknown')}")
        print()
        
        # Position
        pos = state.get("position", {})
        print(f"  Position:")
        print(f"    Lat:      {pos.get('lat', 0):.7f}°N")
        print(f"    Lon:      {pos.get('lon', 0):.7f}°E")
        print(f"    Alt:      {pos.get('alt', 0):.1f}m")
        print()
        
        # Battery
        batt = state.get("battery", {})
        batt_pct = batt.get("percent", 0)
        batt_bar = self._make_battery_bar(batt_pct)
        print(f"  Battery:    {batt_bar} {batt_pct:.1f}%")
        print()
        
        # GPS
        gps = state.get("gps", {})
        print(f"  GPS:")
        print(f"    Satellites: {gps.get('satellites', 0)}")
        print(f"    Fix Type:   {gps.get('fix_type', 'none').upper()}")
        print()
        
        # Safety
        safety = state.get("safety", {})
        level = safety.get("level", "unknown").upper()
        level_color = self._get_level_color(level)
        print(f"  Safety:     {level_color}{level}{self._reset_color()}")
        
        # Mission
        mission = state.get("mission", {})
        if mission.get("active"):
            print(f"  Mission:    WP {mission.get('waypoint', 0)}/{mission.get('total_waypoints', 0)}")
        
        print()
        print("=" * 60)
        print("  Press Ctrl+C to stop")
        print("=" * 60)
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime string"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _make_battery_bar(self, percent: float) -> str:
        """Make battery bar visualization"""
        filled = int(percent / 5)
        empty = 20 - filled
        
        if percent > 50:
            color = self._green()
        elif percent > 20:
            color = self._yellow()
        else:
            color = self._red()
        
        return f"{color}[{'#' * filled}{'.' * empty}]{self._reset_color()}"
    
    def _get_level_color(self, level: str) -> str:
        """Get color for safety level"""
        if level == "OK":
            return self._green()
        elif level == "WARNING":
            return self._yellow()
        elif level in ["CAUTION", "CRITICAL"]:
            return self._red()
        else:
            return self._red()  # Default to red for unknown
    
    def _green(self) -> str:
        return "\033[92m"
    
    def _yellow(self) -> str:
        return "\033[93m"
    
    def _red(self) -> str:
        return "\033[91m"
    
    def _reset_color(self) -> str:
        return "\033[0m"
    
    def print_version(self):
        """Print version information"""
        print("SkyCore Autonomous Drone Platform")
        print("Version: 1.0.0")
        print()
    
    def print_info(self):
        """Print system information"""
        print("=" * 60)
        print("  SKYCORE SYSTEM INFORMATION")
        print("=" * 60)
        print()
        
        print("Architecture:")
        print("  - 43 modules across 8 layers")
        print("  - 22-state Adaptive UKF navigation")
        print("  - Multi-controller support (PID, Geometric, LQR, MPC)")
        print("  - Full C-UAS threat detection")
        print("  - Swarm coordination up to 10 drones")
        print("  - Digital twin physics simulation")
        print()
        
        print("Desktop Application:")
        print("  - python main.py --desktop  (Tkinter-based GCS)")
        print()
        
        print("Modules:")
        print("  Navigation (8): Kalman, EKF, UKF, AUKF, INS, A*, RRT*, Geofence")
        print("  Control (6): PID, Geometric, LQR, MPC, Mixer, Trajectory")
        print("  Sensors (5): IMU, GNSS, Barometer, Compass, LIDAR")
        print("  Communication (4): MAVLink, ExpressLRS, Satellite, MQTT")
        print("  Perception (2): Obstacle, Depth")
        print("  C-UAS (1): Detector")
        print("  Voice (1): Control")
        print("  Twin (1): Physics")
        print("  API (3): OpenSky, Weather, OpenRouter")
        print()
        
        print("GCS Pages:")
        print("  - Login")
        print("  - Dashboard")
        print("  - Missions")
        print("  - Threats")
        print("  - Video Feed")
        print("  - Commands")
        print("  - Telemetry")
        print()
        
        print("For more information, visit the project documentation.")


def main():
    """Main entry point"""
    cli = SkyCoreCLI()
    
    try:
        exit_code = cli.run()
        sys.exit(exit_code)
    except Exception as e:
        print(f"[FATAL] Unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()