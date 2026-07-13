# SkyCore - Protocol Integration Documentation

Version: 0.4.0
Date: 2026-05-17

## Research Sources

This document is based on analysis of 40+ GitHub repositories for drone technology:

### Protocol Documentation
- **o-gs/dji-firmware-tools** (2.1k stars) - DJI firmware analysis, DUML protocol
- **anthok/autel** (11 stars) - Autel EVO firmware extraction
- **ABHICHIRU/Elite-Drone-IDS** - FPGA-based RF detection patterns

### Flight Log Analysis
- **arpanghosh8453/open-dronelog** (1.4k stars) - DJI/Litchi flight log analysis

---

## 1. Drone RF Detection Patterns

### DJI Protocols

| Protocol | Pulse Interval | Frequency | Status |
|----------|---------------|-----------|--------|
| OcuSync | 10ms ± 0.5ms | 2.4/5.8 GHz | ✅ Implemented |
| Lightbridge | 10ms ± 0.5ms | 2.4 GHz | ✅ Implemented |
| OcuSync 2 | 10ms ± 0.5ms | 2.4/5.8 GHz | ✅ Implemented |
| DJI FPV | Variable | 5.8 GHz | 🔜 Future |

### Autel Protocols

| Protocol | Pulse Interval | Frequency | Status |
|----------|---------------|-----------|--------|
| Autel EVO | 12ms ± 0.5ms | 2.4 GHz | ✅ Implemented |
| Autel EVO II | 12ms ± 0.5ms | 2.4/5.8 GHz | ✅ Implemented |
| Autel EVO Nano | 12ms ± 0.5ms | 2.4 GHz | ✅ Implemented |

### Detection Confidence Chain

Based on Elite-Drone-IDS research:
- **100 consecutive valid pulses** required for target lock
- Lock time: 1.0s (DJI) / 1.2s (Autel)
- False positive rate: < 10⁻⁵³ (Wi-Fi interference)

---

## 2. Flight Log Formats

### DJI .txt Format

**Location:** `/Android/data/dji.go.v5/files/FlightRecord/`

**Structure:**
```
#Model: DJI Mavic 3
#SN: 1234567890
#Firmware: V01.02.03
#StartTime: 2024-01-15T10:30:00
#HOMELAT: 32.0855
#HOMELON: 34.7820
# Columns...
[TAB]separated[TAB]data[TAB]...
```

**Columns:** time, lat, lon, altitude, speed, heading, battery, voltage, satellites, distance, signal

### DJI DAT Format

**Binary DUML packets:**
- Start marker: `0x55`
- Header: `SOF(1) + Len(2) + Seq(2) + CRC(1)`
- Payload: varies by packet type
- Uses **comm_dat2pcap.py** for parsing

### Litchi CSV Format

**Export:** Litchi app → Export CSV

**Columns:** latitude, longitude, altitude, speed, heading, battery, timestamp

### Autel Format

**Similar to DJI** with XML-like `filetransfer` structure:
- 8-byte header: field_size (4 bytes) + unknown (4 bytes) + data
- Nested file structure
- JSON format also common

---

## 3. Integration with SkyCore

### Detection Pipeline

```
RF Signal → Energy Detection → Pulse Timing → Protocol ID → Confidence Chain → Target Lock
```

### SkyCore Integration Points

| Module | Integration | Purpose |
|--------|-------------|---------|
| `defense/rf_scanner.py` | ✅ Added | RF scanning for pulse detection |
| `awareness/adsb.py` | ✅ Added | Manned aircraft detection |
| `cuas/threat_prediction.py` | ✅ Added | Trajectory prediction |
| `protocol/drone_detector.py` | ✅ NEW | Drone protocol detection |
| `protocol/flight_log_parser.py` | ✅ NEW | Flight log analysis |

### API Endpoints

```python
# Drone detection
POST /api/defense/scan          # RF environment scan
POST /api/awareness/airspace     # Quick airspace check

# Drone protocol detection
GET  /api/protocol/drones        # List detected drones
GET  /api/protocol/drone/{id}    # Get specific drone details

# Flight log analysis  
POST /api/flightlogs/parse       # Parse flight log file
GET  /api/flightlogs/{id}/stats  # Get flight statistics
```

---

## 4. Security Considerations

### RF Detection (DEFENSIVE ONLY)

The system detects drone RF signatures but does NOT:
- ❌ Transmit jamming signals
- ❌ Interfere with drone control
- ❌ Attempt to hijack drones

This is compliant with Israeli law which prohibits jamming.

### Data Privacy

- Flight logs are analyzed locally
- No cloud upload required
- Sensitive location data protected

---

## 5. Future Enhancements

### v0.5.0
- [ ] FPV/ExpressLRS protocol detection
- [ ] Multi-drone simultaneous tracking
- [ ] Direction-of-arrival estimation

### v0.6.0
- [ ] AI-based drone type classification
- [ ] Integration with external SDR (RTL-SDR, HackRF)
- [ ] Real-time spectrum visualization

---

## References

1. **Elite-Drone-IDS**: FPGA-based 100-layer confidence chain
   - https://github.com/ABHICHIRU/Elite-Drone-IDS
   
2. **DJI Firmware Tools**: Protocol analysis
   - https://github.com/o-gs/dji-firmware-tools
   
3. **Open DroneLog**: Flight log format documentation
   - https://github.com/arpanghosh8453/open-dronelog
   
4. **Autel Extractor**: Firmware parsing
   - https://github.com/anthok/autel