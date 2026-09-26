"""
CyberVault — Password Manager & Encryption
-------------------------------------------
Securely stores passwords for different accounts using Fernet symmetric encryption.
Provides a modern Flask web interface with live password generator, strength meter,
and instant copy features.

Run:
    python password_manager.py
"""

import os
import json
import string
import secrets
import threading
import webbrowser
from pathlib import Path
from flask import Flask, request, render_template, jsonify
# pyrefly: ignore [missing-import]
from cryptography.fernet import Fernet

PROJECT_DIR = Path(__file__).resolve().parent
KEY_FILE = str(PROJECT_DIR / "secret.key")
DATA_FILE = str(PROJECT_DIR / "passwords.json")


def load_or_create_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(KEY_FILE, "xb") as f:
        f.write(key)
    return key


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"{DATA_FILE} must contain a JSON object")
        return data
    return {}


def save_data(data):
    temporary_file = f"{DATA_FILE}.tmp"
    with open(temporary_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(temporary_file, DATA_FILE)


def generate_password(length=16):
    if not isinstance(length, int) or isinstance(length, bool) or length < 1:
        raise ValueError("Password length must be a positive integer")
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(chars) for _ in range(length))


def add_password(fernet, data, account, password):
    if not account.strip():
        raise ValueError("Account name cannot be empty")
    if not password:
        raise ValueError("Password cannot be empty")
    encrypted = fernet.encrypt(password.encode()).decode()
    data[account] = encrypted
    save_data(data)


def get_password(fernet, data, account):
    encrypted = data.get(account)
    if not encrypted:
        return None
    return fernet.decrypt(encrypted.encode()).decode()


def delete_account(data, account):
    if account in data:
        del data[account]
        save_data(data)
        return True
    return False


app = Flask(__name__, template_folder=str(PROJECT_DIR))
key = load_or_create_key()
fernet = Fernet(key)


@app.route("/", methods=["GET"])
def index():
    return render_template("password_manager.html", accounts=sorted(load_data().keys()))


@app.route("/api/save", methods=["POST"])
def api_save():
    payload = request.get_json(silent=True) or request.form
    account = payload.get("account", "").strip()
    password = payload.get("password", "")
    try:
        add_password(fernet, load_data(), account, password)
        return jsonify({"success": True, "message": f"Saved password for {account}."})
    except ValueError as err:
        return jsonify({"success": False, "error": str(err)}), 400


@app.route("/api/decrypt", methods=["POST"])
def api_decrypt():
    payload = request.get_json(silent=True) or request.form
    account = payload.get("account", "").strip()
    password = get_password(fernet, load_data(), account)
    if password is not None:
        return jsonify({"success": True, "account": account, "password": password})
    return jsonify({"success": False, "error": "Account not found."}), 404


@app.route("/api/generate", methods=["POST"])
def api_generate():
    payload = request.get_json(silent=True) or {}
    length = payload.get("length", 16)
    try:
        password = generate_password(int(length))
        return jsonify({"success": True, "password": password})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/accounts", methods=["GET"])
def api_accounts():
    return jsonify({"success": True, "accounts": sorted(load_data().keys())})


@app.route("/api/delete/<account>", methods=["DELETE"])
def api_delete(account):
    if delete_account(load_data(), account):
        return jsonify({"success": True, "message": f"Account '{account}' deleted."})
    return jsonify({"success": False, "error": "Account not found."}), 404


def main():
    print("Starting CyberVault Password Manager at http://127.0.0.1:5001 ...")
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5001")).start()
    app.run(port=5001, debug=False)


if __name__ == "__main__":
    main()
