import subprocess
import sys
from pathlib import Path

dashboard = Path(__file__).parent / "dashboard_itbi.py"
subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard)])
