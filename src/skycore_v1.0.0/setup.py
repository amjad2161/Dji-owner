"""
SkyCore Drone Operating System - Installer Package
==================================================

Quick Install:
1. Extract this package to your desired location
2. Run: pip install -r requirements.txt
3. Run: python setup.py install
4. Run: python run.py

For development:
1. pip install -e .
2. python run.py --dev
"""

from setuptools import setup, find_packages
import os

# Read version from package
VERSION = "1.0.0"

# Read requirements
def get_requirements():
    with open("requirements.txt", "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

# Read long description
def get_long_description():
    if os.path.exists("README.md"):
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    return "SkyCore - Autonomous Drone Operations Platform"

setup(
    name="skycore",
    version=VERSION,
    author="SkyCore Team",
    author_email="team@skycore.dev",
    description="Autonomous Drone Operations Platform with 22-State AUKF Navigation",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/skycore/skycore",
    packages=find_packages(exclude=["tests", "tests.*", "*.tests", "*.tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Robotics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=get_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
        "simulation": [
            "pygame>=2.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "skycore=run:main",
            "skycore-gcs=app:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)