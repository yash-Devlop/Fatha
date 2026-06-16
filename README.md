# Fatha Billing & Account Management System

## Overview

Fatha is a lightweight Billing and Account Management application built using Python. The application is fully portable and can operate without requiring any database installation. All data is stored locally using CSV files, making deployment simple and maintenance-free.

### Key Features

* Billing and invoice management
* Account and customer record management
* CSV-based storage (No database required)
* Fully portable and plug-and-play deployment
* Customizable data storage location
* Native Windows Share integration support
* Easy executable generation using PyInstaller
* Lightweight and fast startup

---

# Requirements

Before running the application, ensure the following software is installed:

### Required Software

* Python 3.10 or later
* .NET 8 SDK (Required only for Native Share functionality)

Verify installation:

```bash
python --version
dotnet --version
```

---

# Data Storage Configuration

The application's data storage directory can be customized.

File:

```text
common.py
```

Modify the storage path inside this file according to your deployment requirements.

---

# Running the Application from Source

## Step 1: Create Virtual Environment

```bash
python -m venv .venv
```

## Step 2: Activate Virtual Environment

Windows:

```bash
.venv\Scripts\activate
```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 4: Run Application

```bash
python main.py
```

---

# Building Native Share Support

The application supports the Windows Native Share dialog through the ShareBridge component.

## Step 1: Navigate to ShareBridge Project

```bash
cd ShareBridge
```

## Step 2: Build Release Version

```bash
dotnet build -c Release
```

## Output Location

After a successful build, the executable will be available at:

```text
ShareBridge\bin\Release\net8.0-windows10.0.19041.0\win-x64\publish\ShareBridge.exe
```

## Step 3: Copy Executable

Create the following directory structure:

```text
Project Root
│
├── Share_executable
│   └── ShareBridge.exe
│
├── assets
├── main.py
└── ...
```

Place the generated `ShareBridge.exe` inside the `Share_executable` folder.

---

# Building a Standalone Executable

To package the application as a single executable:

## Step 1: Activate Virtual Environment

```bash
.venv\Scripts\activate
```

## Step 2: Build Using PyInstaller

```bash
pyinstaller --onefile --windowed --icon=assets/fatha_icon.ico --name Fatha main.py
```

## Output

The generated executable will be available in:

```text
dist/Fatha.exe
```

---

# Deployment Structure

For all features to function correctly, keep the following files and folders together:

```text
Fatha Deployment
│
├── Fatha.exe
├── assets
│   ├── ...
│
├── Share_executable
│   └── ShareBridge.exe
│
└── Data Files
```

### Required Items

| Item                    | Purpose                      |
| ----------------------- | ---------------------------- |
| Fatha.exe               | Main application             |
| assets folder           | Icons, images, and resources |
| Share_executable folder | Native Share integration     |
| CSV data files          | Application data storage     |

---

# Storage System

This version of Fatha does not require:

* MySQL
* PostgreSQL
* SQLite
* SQL Server
* Any external database

All application data is stored locally using CSV files.

### Benefits

* Zero database setup
* Easy backup and restore
* Portable deployment
* Simple migration between systems
* Lower resource consumption

---

# Troubleshooting

### Application Does Not Start

Verify:

```bash
python --version
```

Python must be installed and added to PATH.

---

### Native Share Feature Not Working

Verify:

1. .NET build completed successfully.
2. `ShareBridge.exe` exists.
3. `ShareBridge.exe` is placed inside:

```text
Share_executable/ShareBridge.exe
```

---

### Missing Icons or Images

Ensure the `assets` folder is located beside the executable.

---

# Recommended Deployment

For production use:

```text
Fatha/
│
├── Fatha.exe
├── assets/
├── Share_executable/
│   └── ShareBridge.exe
└── Data/
```

This structure ensures all features operate correctly while keeping the application fully portable.
