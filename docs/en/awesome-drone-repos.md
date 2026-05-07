# Awesome Drone Repos

A curated list of open-source GitHub projects relevant to DJI Mavic pilots and the wider drone ecosystem. Every entry here is **legal**, actively maintained or historically important, and integrates with workflows in this project.

If you're a developer, the [`scripts/windows/clone-dev-repos.ps1`](../../scripts/windows/clone-dev-repos.ps1) one-liner clones the major SDKs and frameworks into `~/dji-dev/` for you.

---

## 📱 Official DJI SDKs

| Repo | Purpose | Used in this project |
|------|---------|----------------------|
| [`dji-sdk/Mobile-SDK-Android`](https://github.com/dji-sdk/Mobile-SDK-Android) | Java/Kotlin SDK for Android. Virtual Sticks, video feed, missions. | Tracks 1, 2, 4 |
| [`dji-sdk/Mobile-SDK-iOS`](https://github.com/dji-sdk/Mobile-SDK-iOS) | Objective-C / Swift SDK for iOS. | Same scope as Android counterpart |
| [`dji-sdk/Mobile-UXSDK-Open-Android`](https://github.com/dji-sdk/Mobile-UXSDK-Open-Android) | Pre-built UI components on top of MSDK. | Quick app prototypes |
| [`dji-sdk/Mobile-UXSDK-Open-iOS`](https://github.com/dji-sdk/Mobile-UXSDK-Open-iOS) | iOS UI library. | iOS prototypes |
| [`dji-sdk/Onboard-SDK`](https://github.com/dji-sdk/Onboard-SDK) | C++ SDK for Linux companion computers on Enterprise / Matrice drones. | Track 2 (advanced) |
| [`dji-sdk/Onboard-SDK-ROS`](https://github.com/dji-sdk/Onboard-SDK-ROS) | ROS bindings for Onboard SDK. | Robotics integrations |
| [`dji-sdk/Payload-SDK`](https://github.com/dji-sdk/Payload-SDK) | Custom payload integration on Matrice / Mavic 3 Enterprise. | Hardware extensions |
| [`dji-sdk/Tello-Python`](https://github.com/dji-sdk/Tello-Python) | Python SDK for Tello (DJI's beginner drone). Great learning sandbox. | Education |

## 🔭 Open-source flight stacks (non-DJI)

These run on Pixhawk / custom hardware, not on DJI drones. Listed because the broader drone-development community uses them and many tutorials apply.

| Repo | Purpose |
|------|---------|
| [`PX4/PX4-Autopilot`](https://github.com/PX4/PX4-Autopilot) | Modern flight stack. Used by Skydio, Auterion, Yuneec H520. |
| [`ArduPilot/ardupilot`](https://github.com/ArduPilot/ardupilot) | Mature flight stack. Multirotor, fixed-wing, rover, sub. |
| [`betaflight/betaflight`](https://github.com/betaflight/betaflight) | FPV racing firmware. |
| [`iNavFlight/inav`](https://github.com/iNavFlight/inav) | Navigation-focused fork of Cleanflight. |
| [`emuflight/EmuFlight`](https://github.com/emuflight/EmuFlight) | FPV freestyle-tuned firmware. |

## 🖥️ Ground stations / mission planners

| Repo | Purpose | Works with DJI? |
|------|---------|-----------------|
| [`mavlink/qgroundcontrol`](https://github.com/mavlink/qgroundcontrol) | Cross-platform GCS. | No (MAVLink only) |
| [`ArduPilot/MissionPlanner`](https://github.com/ArduPilot/MissionPlanner) | Windows GCS. | No |
| [`mavlink/MAVSDK`](https://github.com/mavlink/MAVSDK) | Multi-language SDK (C++, Python, Swift, Go) for MAVLink. | No |
| [`mavlink/MAVLink`](https://github.com/mavlink/mavlink) | The protocol itself. | No |
| [`ArduPilot/MAVProxy`](https://github.com/ArduPilot/MAVProxy) | Terminal GCS. | No |

## 🎥 Video / post-production

| Repo | Purpose | Used in this project |
|------|---------|----------------------|
| [`gyroflow/gyroflow`](https://github.com/gyroflow/gyroflow) | Gimbal stabilization in post using gyro telemetry. Excellent for DJI footage. | Track 3 |
| [`gyroflow/gyroflow-camera-presets`](https://github.com/gyroflow/gyroflow-camera-presets) | Camera profiles for Gyroflow, including Mavic models. | Track 3 |
| [`gyroflow/gyroflow-ofx`](https://github.com/gyroflow/gyroflow-ofx) | OpenFX plugin for DaVinci Resolve / Nuke. | Track 3 |
| [`mifi/lossless-cut`](https://github.com/mifi/lossless-cut) | Lossless video cutting GUI. | Footage triage |
| [`kkroening/ffmpeg-python`](https://github.com/kkroening/ffmpeg-python) | Python bindings for FFmpeg. | Automation |
| [`xinntao/Real-ESRGAN`](https://github.com/xinntao/Real-ESRGAN) | Free image / video upscaling. | Track 3 (optional) |
| [`upscayl/upscayl`](https://github.com/upscayl/upscayl) | GUI for Real-ESRGAN. | Track 3 (optional) |
| [`n00mkrad/flowframes`](https://github.com/n00mkrad/flowframes) | Frame interpolation for slow-mo. | Track 3 (optional) |

## 👁️ Computer vision / tracking

| Repo | Purpose | Used in this project |
|------|---------|----------------------|
| [`ultralytics/ultralytics`](https://github.com/ultralytics/ultralytics) | YOLOv8 / v11 detection & segmentation. | Track 2 |
| [`WongKinYiu/yolov9`](https://github.com/WongKinYiu/yolov9) | YOLOv9 reference implementation. | Track 2 |
| [`mikel-brostrom/boxmot`](https://github.com/mikel-brostrom/boxmot) | Multi-object tracking (BoT-SORT, ByteTrack, OC-SORT). | Track 2 |
| [`roboflow/supervision`](https://github.com/roboflow/supervision) | CV utilities and dataset tooling. | Track 2 |
| [`microsoft/AirSim`](https://github.com/microsoft/AirSim) | Photoreal drone simulator on Unreal Engine. (Project archived but widely used.) | Simulation |
| [`PX4/PX4-SITL_gazebo`](https://github.com/PX4/PX4-SITL_gazebo) | PX4 Software-in-the-Loop with Gazebo. | Simulation |

## 🗺️ Mapping / photogrammetry

| Repo | Purpose |
|------|---------|
| [`OpenDroneMap/ODM`](https://github.com/OpenDroneMap/ODM) | Photogrammetry pipeline. Builds orthos, point clouds, 3D meshes from drone photos. |
| [`OpenDroneMap/WebODM`](https://github.com/OpenDroneMap/WebODM) | Web UI for ODM. |
| [`OpenDroneMap/NodeODM`](https://github.com/OpenDroneMap/NodeODM) | API server for ODM. |
| [`alicevision/Meshroom`](https://github.com/alicevision/Meshroom) | General-purpose photogrammetry GUI. |
| [`openMVG/openMVG`](https://github.com/openMVG/openMVG) | Multi-view geometry library. |

## 🤖 ROS integrations

| Repo | Purpose |
|------|---------|
| [`mavlink/mavros`](https://github.com/mavlink/mavros) | MAVLink ↔ ROS bridge. |
| [`dji-sdk/Onboard-SDK-ROS`](https://github.com/dji-sdk/Onboard-SDK-ROS) | DJI Onboard SDK ↔ ROS. |
| [`HKUST-Aerial-Robotics/Fast-Planner`](https://github.com/HKUST-Aerial-Robotics/Fast-Planner) | Fast trajectory planning for quadrotors. Academic, well-cited. |

## 🎓 Educational / Tello (great entry point)

Tello is DJI's beginner drone (≈$100). Programmable in Python. Worth knowing if you're learning before touching a Mavic SDK.

| Repo | Purpose |
|------|---------|
| [`damiafuentes/DJITelloPy`](https://github.com/damiafuentes/DJITelloPy) | Pythonic Tello SDK. Most popular community wrapper. |
| [`dji-sdk/Tello-Python`](https://github.com/dji-sdk/Tello-Python) | DJI's official sample code. |
| [`fvilmos/tello_object_tracking`](https://github.com/fvilmos/tello_object_tracking) | Object tracking demo on Tello. |

## 📊 Telemetry / log analysis

| Resource | Type | Purpose |
|----------|------|---------|
| [Airdata UAV](https://airdata.com) | Web service (closed source, free tier) | Reads DJI flight records, full visualization. |
| [DatCon](https://datfile.net/CsvView/intro.html) | Windows GUI (free) | Decodes encrypted `.DAT` flight logs. |
| [`tools/log-analyzer/`](../../tools/log-analyzer/) (this project) | Python CLI | Quick health summary from Airdata CSV exports. |

## 🔗 Useful protocol / hardware references

| Repo | Purpose |
|------|---------|
| [`mavlink/MAVLink`](https://github.com/mavlink/mavlink) | Drone protocol spec. |
| [`Auterion/notebooks`](https://github.com/Auterion/notebooks) | Drone data Jupyter notebooks. |

---

## How we vet entries

Every repo in this list:

1. Has a permissive open-source license (MIT, Apache 2, BSD, GPL).
2. Operates within manufacturer SDKs and aviation regulations.
3. Has been published or maintained within the last few years, **or** is historically significant (e.g. AirSim).
4. Does **not** focus on bypassing geofencing, exceeding transmit power, or evading Remote ID.

If you'd like to add a repo, open a PR. See [CONTRIBUTING.md](../../CONTRIBUTING.md).

## What we deliberately exclude

The DJI hacking community has produced repos that focus on:

- Removing No-Fly Zones / geofencing
- Increasing transmit power beyond legal limits
- Bypassing Remote ID broadcast
- Region locking circumvention beyond what DJI's official region selector exposes

We do **not** link to those, even when they exist. See [legal-and-safety.md](legal-and-safety.md) for the rationale.
