"""Build standalone .exe with PyInstaller."""

import subprocess
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent.parent
    entry_point = project_root / "src" / "estship_uploader" / "__main__.py"
    config_example = project_root / "config" / "config.example.ini"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--name=EstShipUploader",
        f"--add-data={config_example};config",
    ]

    icon_path = project_root / "assets" / "icon.ico"
    if icon_path.exists():
        cmd.append(f"--icon={icon_path}")

    # Set paths so PyInstaller can find the package
    cmd.extend([
        f"--paths={project_root / 'src'}",
        str(entry_point),
    ])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(project_root))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
