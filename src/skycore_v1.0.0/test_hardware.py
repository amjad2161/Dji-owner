"""SkyCore Real Hardware Test"""
import sys
sys.path.insert(0, 'C:/Users/Mobar/Downloads/drone flycore/package/user_input_files')

print("=== SkyCore Hardware Check ===\n")

# Check libraries
print("Libraries:")
try:
    from pymavlink import mavutil
    print("  pymavlink: OK")
except:
    print("  pymavlink: MISSING - pip install pymavlink")

try:
    import serial
    print("  pyserial: OK")
except:
    print("  pyserial: MISSING - pip install pyserial")

try:
    import pynmea2
    print("  pynmea2: OK")
except:
    print("  pynmea2: MISSING - pip install pynmea2")

try:
    import cv2
    print("  opencv-python: OK")
except:
    print("  opencv-python: MISSING - pip install opencv-python")

try:
    import numpy
    print("  numpy: OK")
except:
    print("  numpy: MISSING")

# Check serial ports
print("\nSerial Ports:")
try:
    import serial.tools.list_ports
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        print(f"  {p.device}: {p.description}")
    if not ports:
        print("  No ports found")
except:
    print("  pyserial not available")

# Check cameras
print("\nCameras:")
import cv2
cameras = []
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, _ = cap.read()
        if ret:
            cameras.append(i)
            print(f"  Camera {i}: Available")
    cap.release()
if not cameras:
    print("  No cameras found")

print("\nMAVLink Test:")
try:
    from pymavlink import mavutil
    
    # List connection examples
    print("\nConnection string examples:")
    print("  serial:/dev/ttyUSB0:921600")
    print("  serial:COM3:115200")
    print("  tcp:localhost:5760")
    print("  tcp:192.168.1.100:5760")
    print("  udp:localhost:14550")
    print("  udpb:192.168.1.255:14550")
    
    print("\nUse: RealMAVLinkConnection('connection_string')")
    
except Exception as e:
    print(f"  pymavlink error: {e}")

print("\n=== Done ===")
input("\nPress Enter to exit...")