"""Test configuration for shared module tests."""

import os
import sys
from pathlib import Path

# Setup paths - add the services directory to the path
SERVICE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = SERVICE_DIR.parent

# Add services directory to path so we can import shared
services_path = str(ROOT_DIR)
if services_path not in sys.path:
    sys.path.insert(0, services_path)

# Ensure Redis URL is not set to avoid actual connections
os.environ["REDIS_URL"] = ""
