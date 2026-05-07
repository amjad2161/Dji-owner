"""MCAP telemetry recording.

MCAP (https://mcap.dev) is the modern format for time-series robotics data,
used by ROS 2, Foxglove, and many others. Recording telemetry as MCAP lets
you:
  - Replay flights in Foxglove with full chart and 3D-path support
  - Mix in other channels (vision detections, video frames) on the same
    timeline
  - Hand the file to a research team without writing a converter

We expose a single channel today: `/skycore/telemetry` carrying JSON
frames. Add new channels by calling `add_channel`.

Named `mcap_recording` instead of `mcap` to avoid colliding with the PyPI
`mcap` package name when imported.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class McapRecorder:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._writer = None
        self._file = None
        self._channel_id: Optional[int] = None
        self._extra_channels: dict[str, int] = {}

    def open(self) -> None:
        try:
            from mcap.writer import Writer
        except ImportError as e:
            raise ImportError("mcap is required. pip install mcap") from e
        self._file = self.path.open("wb")
        self._writer = Writer(self._file)
        self._writer.start()
        schema_id = self._writer.register_schema(
            name="skycore.Telemetry",
            encoding="jsonschema",
            data=json.dumps({
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string"},
                    "position": {"type": "object"},
                    "battery": {"type": "object"},
                    "yaw": {"type": "number"},
                    "mode": {"type": "string"},
                },
            }).encode("utf-8"),
        )
        self._channel_id = self._writer.register_channel(
            schema_id=schema_id,
            topic="/skycore/telemetry",
            message_encoding="json",
        )

    def close(self) -> None:
        if self._writer:
            self._writer.finish()
            self._writer = None
        if self._file:
            self._file.close()
            self._file = None

    def __enter__(self) -> "McapRecorder":
        self.open()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def add_channel(self, topic: str, schema_name: str = "skycore.Generic") -> int:
        if not self._writer:
            raise RuntimeError("Recorder not open")
        schema_id = self._writer.register_schema(
            name=schema_name,
            encoding="jsonschema",
            data=json.dumps({"type": "object"}).encode("utf-8"),
        )
        ch_id = self._writer.register_channel(
            schema_id=schema_id, topic=topic, message_encoding="json"
        )
        self._extra_channels[topic] = ch_id
        return ch_id

    def write(self, telemetry: dict) -> None:
        """Write a telemetry frame."""
        if not self._writer or self._channel_id is None:
            raise RuntimeError("Recorder not open")
        ts_ns = int(time.time() * 1e9)
        self._writer.add_message(
            channel_id=self._channel_id,
            log_time=ts_ns,
            publish_time=ts_ns,
            data=json.dumps(telemetry).encode("utf-8"),
        )

    def write_to(self, topic: str, payload: dict) -> None:
        """Write a message to an additional channel."""
        ch_id = self._extra_channels.get(topic)
        if ch_id is None:
            ch_id = self.add_channel(topic)
        ts_ns = int(time.time() * 1e9)
        self._writer.add_message(
            channel_id=ch_id,
            log_time=ts_ns,
            publish_time=ts_ns,
            data=json.dumps(payload).encode("utf-8"),
        )
