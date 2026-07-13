"""
SkyCore Photogrammetry
OpenDroneMap wrapper for 3D model generation from images
"""

import subprocess
import os

class PhotogrammetryProcessor:
    def process_images(self, image_folder: str, output_folder: str = "odm_output"):
        print(f"🗺️ Starting OpenDroneMap processing on {image_folder}...")
        # Real command would be: docker run -ti --rm -v $(pwd)/images:/datasets opendronemap/odm
        os.makedirs(output_folder, exist_ok=True)
        print(f"✅ 3D model would be generated in {output_folder}")
        return output_folder
