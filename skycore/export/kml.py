"""KML export for missions and recorded tracks.

KML opens directly in Google Earth, QGIS, ArcGIS, and most GIS tools.
Produces both 2D placemarks (mission waypoints with photos / actions)
and 3D LineString tracks (with absolute or relative-to-ground altitude).
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable

from skycore.missions.waypoint import WaypointMission


def mission_to_kml(mission: WaypointMission, output_path: Path | str) -> None:
    p = Path(output_path)
    placemarks = []
    coords_lines = []
    for i, step in enumerate(mission.steps):
        coords_lines.append(f"{step.target.lon},{step.target.lat},{step.target.alt}")
        actions = ",".join(step.actions) if step.actions else ""
        placemarks.append(f"""
    <Placemark>
      <name>{html.escape(f'WP {i+1}')}</name>
      <description><![CDATA[
        speed: {step.speed_mps} m/s<br/>
        yaw: {step.yaw_deg}<br/>
        gimbal: {step.gimbal_pitch_deg}<br/>
        actions: {html.escape(actions)}
      ]]></description>
      <Point>
        <altitudeMode>relativeToGround</altitudeMode>
        <coordinates>{step.target.lon},{step.target.lat},{step.target.alt}</coordinates>
      </Point>
    </Placemark>""")
    track = "\n".join(coords_lines)
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{html.escape(mission.name)}</name>
    <Style id="track">
      <LineStyle><color>ff7bd46c</color><width>3</width></LineStyle>
    </Style>
    <Placemark>
      <name>Path</name>
      <styleUrl>#track</styleUrl>
      <LineString>
        <tessellate>1</tessellate>
        <altitudeMode>relativeToGround</altitudeMode>
        <coordinates>
{track}
        </coordinates>
      </LineString>
    </Placemark>{''.join(placemarks)}
  </Document>
</kml>
"""
    p.write_text(body, encoding="utf-8")


def telemetry_to_kml(
    samples: Iterable[dict],
    output_path: Path | str,
    name: str = "flight",
) -> None:
    """Recorded flight track as a KML LineString.

    Each sample must have keys: lat, lon, alt (relative-to-ground meters).
    """
    p = Path(output_path)
    coords = "\n".join(f"{s['lon']},{s['lat']},{s.get('alt', 0)}" for s in samples)
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{html.escape(name)}</name>
    <Placemark>
      <Style><LineStyle><color>ff7bd46c</color><width>3</width></LineStyle></Style>
      <LineString>
        <altitudeMode>relativeToGround</altitudeMode>
        <coordinates>
{coords}
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""
    p.write_text(body, encoding="utf-8")
