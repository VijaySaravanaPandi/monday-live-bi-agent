"""
Packaging script to generate a clean submission ZIP file.
Excludes venv, __pycache__, .git, and temporary files.
"""

import os
import zipfile

OUTPUT_ZIP = "monday_live_bi_agent_submission.zip"
EXCLUDE_DIRS = {"venv", ".git", "__pycache__", ".idea", ".vscode", ".agents", ".gemini"}
EXCLUDE_FILES = {OUTPUT_ZIP, ".env"}


def create_zip():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    with zipfile.ZipFile(os.path.join(root_dir, OUTPUT_ZIP), "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(root_dir):
            # Filter directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for file in files:
                if file in EXCLUDE_FILES or file.endswith((".pyc", ".pyo", ".pyd")):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, root_dir)
                zf.write(full_path, rel_path)
    print(f"Created clean submission package: {OUTPUT_ZIP}")


if __name__ == "__main__":
    create_zip()
