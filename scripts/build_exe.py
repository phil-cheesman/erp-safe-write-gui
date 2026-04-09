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
        "--windowed",
        "--name=EstShipUploader",
        f"--add-data={config_example};config",
    ]

    icon_path = project_root / "assets" / "icon.ico"
    if icon_path.exists():
        cmd.append(f"--icon={icon_path}")

    # Hidden imports — these modules are imported lazily inside functions,
    # so PyInstaller won't discover them via static analysis.
    hidden = [
        "estship_uploader.tabbed_gui",
        "estship_uploader.pipeline",
        "estship_uploader.itemclass_pipeline",
        "estship_uploader.itemclass_csv_parser",
        "estship_uploader.itemclass_validators",
        "estship_uploader.itemclass_updater",
        "estship_uploader.mfglt_pipeline",
        "estship_uploader.mfglt_csv_parser",
        "estship_uploader.mfglt_validators",
        "estship_uploader.mfglt_updater",
        "estship_uploader.reordpt_pipeline",
        "estship_uploader.reordpt_csv_parser",
        "estship_uploader.reordpt_validators",
        "estship_uploader.reordpt_updater",
        "estship_uploader.reordqty_pipeline",
        "estship_uploader.reordqty_csv_parser",
        "estship_uploader.reordqty_validators",
        "estship_uploader.reordqty_updater",
        "estship_uploader.backup",
        "estship_uploader.connection",
    ]
    for mod in hidden:
        cmd.append(f"--hidden-import={mod}")

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
