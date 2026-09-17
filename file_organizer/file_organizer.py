"""
OrganizeIt — Smart File Organizer
---------------------------------
Scans target directories and organizes loose files into subfolders based on
file type (Images, Documents, Videos, Audio, Archives, Others).
Provides a modern Flask web interface with live scan inspection.

Run:
    python file_organizer.py
"""

import os
import shutil
import threading
import webbrowser
from pathlib import Path
from flask import Flask, request, render_template, jsonify

FILE_CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".xlsx", ".pptx", ".csv"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv", ".wmv"},
    "Audio": {".mp3", ".wav", ".flac", ".aac"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
}


def categorize(filename):
    ext = os.path.splitext(filename)[1].lower()
    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category
    return "Others"


def scan_directory(directory):
    if not os.path.isdir(directory):
        raise ValueError(f"'{directory}' is not a valid directory.")

    categories = {cat: 0 for cat in list(FILE_CATEGORIES.keys()) + ["Others"]}
    unorganized_count = 0
    total_files = 0
    managed_categories = set(FILE_CATEGORIES.keys()) | {"Others"}

    for entry in os.listdir(directory):
        full_path = os.path.join(directory, entry)
        if entry.startswith("."):
            continue

        if os.path.isfile(full_path):
            cat = categorize(entry)
            categories[cat] += 1
            unorganized_count += 1
            total_files += 1
        elif os.path.isdir(full_path) and entry in managed_categories:
            try:
                for sub_entry in os.listdir(full_path):
                    sub_path = os.path.join(full_path, sub_entry)
                    if os.path.isfile(sub_path) and not sub_entry.startswith("."):
                        cat = categorize(sub_entry)
                        categories[cat] += 1
                        total_files += 1
            except PermissionError:
                pass

    return categories, unorganized_count, total_files


def organize_directory(directory):
    if not os.path.isdir(directory):
        raise ValueError(f"'{directory}' is not a valid directory.")

    moved_count = 0
    logs = []

    for entry in os.listdir(directory):
        full_path = os.path.join(directory, entry)
        if os.path.isdir(full_path) or entry.startswith("."):
            continue

        category = categorize(entry)
        target_dir = os.path.join(directory, category)
        os.makedirs(target_dir, exist_ok=True)

        destination = os.path.join(target_dir, entry)
        if os.path.exists(destination):
            base, ext = os.path.splitext(entry)
            counter = 1
            while os.path.exists(destination):
                destination = os.path.join(target_dir, f"{base}_{counter}{ext}")
                counter += 1

        shutil.move(full_path, destination)
        # Keep logs ASCII-compatible for Windows consoles using CP1252.
        log_entry = f"Moved: {entry} -> {category}/"
        logs.append(log_entry)
        moved_count += 1

    return moved_count, logs


app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent))


@app.route("/", methods=["GET"])
def index():
    return render_template("file_organizer.html")


@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json(silent=True) or request.form
    directory = data.get("directory", "").strip()
    try:
        categories, unorganized_count, total_files = scan_directory(directory)
        return jsonify({
            "success": True, 
            "categories": categories, 
            "unorganized_count": unorganized_count,
            "total_files": total_files
        })
    except (OSError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/organize", methods=["POST"])
def api_organize():
    data = request.get_json(silent=True) or request.form
    directory = data.get("directory", "").strip()
    try:
        moved_count, logs = organize_directory(directory)
        return jsonify({"success": True, "moved_count": moved_count, "logs": logs})
    except (OSError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400


def main():
    print("Starting OrganizeIt App at http://127.0.0.1:5003 ...")
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5003")).start()
    app.run(port=5003, debug=False)


if __name__ == "__main__":
    main()
