"""OpenDroneMap (ODM) integration for photogrammetry processing.

Runs ODM in a Docker container to process drone images into:
- Orthomosaic (GeoTIFF)
- Digital surface model (DSM, GeoTIFF)
- 3D point cloud (LAS / LAZ)
- Textured 3D mesh (OBJ)

Requires Docker. The Docker image is `opendronemap/odm:latest` (~5 GB).
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class ODMResult:
    output_dir: Path
    orthophoto: Optional[Path] = None
    dsm: Optional[Path] = None
    point_cloud: Optional[Path] = None
    mesh: Optional[Path] = None

    @classmethod
    def from_output(cls, output_dir: Path) -> "ODMResult":
        ortho = output_dir / "odm_orthophoto" / "odm_orthophoto.tif"
        dsm = output_dir / "odm_dem" / "dsm.tif"
        las = output_dir / "odm_georeferencing" / "odm_georeferenced_model.laz"
        mesh = output_dir / "odm_texturing" / "odm_textured_model_geo.obj"
        return cls(
            output_dir=output_dir,
            orthophoto=ortho if ortho.exists() else None,
            dsm=dsm if dsm.exists() else None,
            point_cloud=las if las.exists() else None,
            mesh=mesh if mesh.exists() else None,
        )


def run_odm_docker(
    images_dir: Path | str,
    orthophoto_resolution: int = 5,
    dsm: bool = True,
    fast: bool = False,
    image: str = "opendronemap/odm:latest",
) -> ODMResult:
    """Run ODM via Docker against a directory of drone images.

    ODM places its output as subdirectories alongside the images.
    Returns an ODMResult pointing to the produced artifacts.
    """
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is required. Install Docker Desktop or Docker CE.")
    images = Path(images_dir).resolve()
    if not images.exists():
        raise FileNotFoundError(images)
    parent = images.parent

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{parent}:/datasets",
        image,
        "--project-path", "/datasets",
        images.name,
        "--orthophoto-resolution", str(orthophoto_resolution),
    ]
    if dsm:
        cmd.append("--dsm")
    if fast:
        cmd.append("--fast-orthophoto")

    log.info("Running ODM: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return ODMResult.from_output(images)
