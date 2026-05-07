"""Click-based command-line interface."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

try:
    import click
except ImportError:
    print("click is required. pip install click", file=sys.stderr)
    sys.exit(1)

from skycore.adapters.simulator import SimulatorDrone
from skycore.core.types import GeoPoint, GeofenceConfig
from skycore.missions.orbit import orbit_mission
from skycore.missions.mapping import lawnmower_mission
from skycore.missions.litchi import import_litchi_csv, export_litchi_csv
from skycore.analytics.log_analyzer import analyze_csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@click.group()
@click.version_option("0.2.0")
def cli():
    """SkyCore — unified drone operations CLI."""


@cli.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8080, type=int)
@click.option("--backend", type=click.Choice(["simulator", "tello", "mavlink", "dji-bridge"]), default="simulator")
@click.option("--connection-url", default=None)
@click.option("--home", default="37.7749,-122.4194")
def serve(host, port, backend, connection_url, home):
    """Start the HTTP + WebSocket server (web dashboard at /)."""
    try:
        import uvicorn
    except ImportError:
        click.echo("uvicorn required. pip install uvicorn", err=True)
        sys.exit(1)
    from skycore.api.app import create_app

    lat, lon = (float(x) for x in home.split(","))
    drone = _make_drone(backend, connection_url, GeoPoint(lat, lon))
    geofence = GeofenceConfig(home=GeoPoint(lat, lon))
    app = create_app(drone, geofence)
    uvicorn.run(app, host=host, port=port)


@cli.command()
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
def analyze(csv_path):
    """Analyze a flight log CSV (Airdata / DatCon format)."""
    summary = analyze_csv(Path(csv_path))
    click.echo("=" * 60)
    click.echo(f"Flight summary  —  {Path(csv_path).name}")
    click.echo("=" * 60)
    if summary.duration_min is not None:
        click.echo(f"Duration:        {summary.duration_min:6.2f} min")
    if summary.max_height_m is not None:
        click.echo(f"Max height AGL:  {summary.max_height_m:6.1f} m")
    if summary.max_distance_m is not None:
        click.echo(f"Max distance:    {summary.max_distance_m:6.1f} m")
    if summary.battery_start is not None:
        click.echo(f"Battery:         {summary.battery_start:5.0f}% → {summary.battery_end:.0f}%")
    if summary.gps_avg is not None:
        click.echo(f"GPS satellites:  avg {summary.gps_avg:5.1f}, min {summary.gps_min:.0f}")
    if summary.warnings:
        click.echo("")
        click.echo("WARNINGS:")
        for w in summary.warnings:
            click.echo(f"  ! {w}")
    click.echo("=" * 60)


@cli.command()
@click.option("--lat", required=True, type=float)
@click.option("--lon", required=True, type=float)
@click.option("--max-wind", default=36.0, type=float, help="Max sustained wind kph")
@click.option("--max-gust", default=50.0, type=float, help="Max gust kph")
def weather(lat, lon, max_wind, max_gust):
    """Pre-flight weather check via Open-Meteo (no API key needed)."""
    from skycore.weather import preflight_check
    ok, issues, snap = preflight_check(lat, lon, max_wind_kph=max_wind, max_gust_kph=max_gust)
    click.echo(f"Conditions at ({lat:.4f}, {lon:.4f}):")
    click.echo(f"  Temperature:   {snap.temperature_c:5.1f} °C")
    click.echo(f"  Wind:          {snap.wind_speed_kph:5.1f} kph @ {snap.wind_direction_deg:.0f}°")
    click.echo(f"  Gust:          {snap.wind_gust_kph:5.1f} kph")
    click.echo(f"  Precipitation: {snap.precipitation_mm_h:5.2f} mm/h")
    click.echo(f"  Cloud cover:   {snap.cloud_cover_pct:5.0f} %")
    click.echo("")
    if ok:
        click.secho("✓ Safe to fly", fg="green")
    else:
        click.secho("✗ NOT safe to fly:", fg="red")
        for issue in issues:
            click.echo(f"  - {issue}")
        sys.exit(2)


@cli.command()
@click.option("--lat", required=True, type=float)
@click.option("--lon", required=True, type=float)
def elevation(lat, lon):
    """Look up terrain elevation at a point (Open-Elevation)."""
    from skycore.terrain import get_elevation
    e = get_elevation(lat, lon)
    click.echo(f"Elevation at ({lat:.4f}, {lon:.4f}): {e:.1f} m AMSL")


@cli.command(name="golden-hour")
@click.option("--lat", required=True, type=float)
@click.option("--lon", required=True, type=float)
def golden_hour(lat, lon):
    """Compute today's golden-hour windows for a location."""
    from skycore.scheduler import golden_hour_at
    sunrise, m_end, e_start, sunset = golden_hour_at(lat, lon)
    click.echo(f"Sunrise:        {sunrise.strftime('%H:%M UTC')}")
    click.echo(f"Morning ends:   {m_end.strftime('%H:%M UTC')}")
    click.echo(f"Evening begins: {e_start.strftime('%H:%M UTC')}")
    click.echo(f"Sunset:         {sunset.strftime('%H:%M UTC')}")


@cli.group()
def mission():
    """Mission planning & generation."""


@mission.command("orbit")
@click.option("--center", required=True, help="lat,lon[,alt]")
@click.option("--radius", default=50.0, type=float)
@click.option("--altitude", default=30.0, type=float)
@click.option("--waypoints", default=12, type=int)
@click.option("--out", default="orbit.csv", help="Output Litchi CSV path")
def mission_orbit(center, radius, altitude, waypoints, out):
    """Generate an orbit mission as a Litchi-compatible CSV."""
    parts = [float(x) for x in center.split(",")]
    lat, lon = parts[0], parts[1]
    alt = parts[2] if len(parts) > 2 else 0.0
    poi = GeoPoint(lat, lon, alt)
    m = orbit_mission(poi, radius_m=radius, altitude_m=altitude, waypoints=waypoints)
    export_litchi_csv(m, out, poi=poi)
    click.echo(f"Wrote {len(m)} waypoints to {out}")


@mission.command("survey")
@click.option("--sw", required=True, help="south-west corner lat,lon")
@click.option("--ne", required=True, help="north-east corner lat,lon")
@click.option("--altitude", default=50.0, type=float)
@click.option("--out", default="survey.csv")
def mission_survey(sw, ne, altitude, out):
    """Generate a lawnmower survey mission."""
    sw_pt = GeoPoint(*[float(x) for x in sw.split(",")])
    ne_pt = GeoPoint(*[float(x) for x in ne.split(",")])
    m = lawnmower_mission(sw_pt, ne_pt, altitude_m=altitude)
    export_litchi_csv(m, out)
    click.echo(f"Wrote {len(m)} waypoints to {out}")


@mission.command("run")
@click.argument("csv_path", type=click.Path(exists=True))
@click.option("--backend", type=click.Choice(["simulator", "tello", "mavlink"]), default="simulator")
@click.option("--connection-url", default=None)
def mission_run(csv_path, backend, connection_url):
    """Execute a Litchi CSV mission against any backend."""
    async def go():
        m = import_litchi_csv(csv_path)
        click.echo(f"Loaded {len(m)} waypoints")
        first = m.steps[0].target if m.steps else None
        drone = _make_drone(backend, connection_url, first)
        async with drone:
            await m.execute(drone)
    asyncio.run(go())


@cli.group()
def flights():
    """Flight history (SQLite)."""


@flights.command("list")
@click.option("--db", default="skycore.db", type=click.Path())
@click.option("--limit", default=20, type=int)
def flights_list(db, limit):
    """List recent flights from the local database."""
    from skycore.storage import FlightDatabase
    with FlightDatabase(db) as fdb:
        rows = fdb.list_flights(limit)
    if not rows:
        click.echo("No flights recorded.")
        return
    for r in rows:
        click.echo(f"#{r['id']:>4}  {r['drone']:<12}  {r['started_at']}  →  {r['ended_at'] or '...'}")


def _make_drone(backend: str, connection_url: str | None, home: GeoPoint | None):
    if backend == "simulator":
        return SimulatorDrone(home=home)
    if backend == "tello":
        from skycore.adapters.tello import TelloDrone
        return TelloDrone(home=home)
    if backend == "mavlink":
        from skycore.adapters.mavlink import MavlinkDrone
        return MavlinkDrone(connection_url=connection_url or "udp://:14540")
    if backend == "dji-bridge":
        from skycore.adapters.dji_msdk import DjiBridgeDrone
        return DjiBridgeDrone(bridge_url=connection_url or "ws://192.168.1.100:8765")
    raise ValueError(f"Unknown backend: {backend}")


if __name__ == "__main__":
    cli()
