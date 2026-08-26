# Echo

Echo is a small local Windows utility for storing and quickly copying reusable customer-service response templates, creating streamlined responses and cutting response-times. 

The goal is as simple as the method: **search → select → copy → paste**.

Echo is designed as a keyboard-first tool for repetitive, generic replies. 

**It does not connect to or interact with any work system. You always paste the copied response yourself.**

## Features

- Search templates by title and keywords
- Keyboard-first workflow
- `Enter` → select, `Enter` → copy
- Add, edit and delete templates directly in the app
- Global hotkey: `Ctrl + Shift + .`
- Runs in the system tray
- Dark, minimal interface
- Templates can be synchronized through Git

## Requirements

- Windows
- Python 3.10+

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
