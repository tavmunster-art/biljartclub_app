
# Biljart Club App

## Overview

The Biljart Club App is a local-network web application for managing and registering billiards competitions.

The application supports:

- Libre and Cushion/Band games
- Automatic and manual match creation
- Mobile score keeping for multiple tables
- Live match status tracking
- Rankings and historical statistics
- Season reports and database backups
- Coordinator approval workflow for match results

The system is designed for use inside a billiards club using:

- Local WiFi
- A personal hotspot
- A laptop as server
- Phones/tablets as scorekeeping devices

The app is optimized for practical club use with minimal network traffic and a simple touchscreen interface.

---

# Features

## Coordinator Functions

- Select active players
- Automatically generate matches
- Manually create matches
- Configure maximum turns per match
- Approve match results before saving to database
- Enter paper results manually when needed
- Create backups
- Restore backups
- Generate PDF reports
- Close a season and update starting averages

## Scorekeeper / Teller Functions

- View available matches
- Claim a match for scoring
- Register caramboles per turn
- Enter series scores
- Undo the last turn
- Finish matches
- Send results to the coordinator for approval

## Competition Features

- Smart automatic pairing algorithm
- Attempts to prevent players meeting more than twice per season
- Handles uneven numbers of players
- Tracks averages, points, rankings and match history

---

# Why This Project Is Useful

Many billiards clubs still use paper administration or spreadsheets.

This project provides a lightweight but powerful alternative specifically tailored for small and medium-sized billiards competitions.

Advantages include:

- Easy setup without internet dependency
- Works on phones and tablets
- Minimal network traffic
- Centralized control by the coordinator
- Reduced risk of scoring conflicts
- Automatic ranking and statistics
- Reliable local database backups
- Season reporting in PDF format

The application is intentionally designed to remain simple enough for non-technical club members.

---

# Technology Stack

- Python
- Flask
- SQLite
- HTML / CSS / JavaScript
- Flask-SocketIO
- Chart.js

---

# Project Structure

```text
biljartclub_app/
│
├── app/
│   ├── routes/
│   │   ├── main.py
│   │   ├── matches.py
│   │   ├── backup.py
│   │   └── reports.py
│   │
│   ├── templates/
│   │   ├── coordinator.html
│   │   ├── teller.html
│   │   ├── teller_list.html
│   │   ├── dashboard.html
│   │   ├── history.html
│   │   ├── ranking.html
│   │   └── help.html
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── common.css
│   │   │   ├── coordinator.css
│   │   │   ├── teller.css
│   │   │   ├── dashboard.css
│   │   │   ├── help.css
│   │   │   └── tables.css
│   │   │
│   │   └── js/
│   │       ├── coordinator.js
│   │       ├── teller.js
│   │       ├── teller_list.js
│   │       ├── dashboard.js
│   │       └── common.js
│   │
│   ├── sockets/
│   │   └── events.py
│   │
│   ├── database.py
│   └── __init__.py
│
├── backups/
├── reports/
├── instance/
│   └── biljart.db
│
├── run.py
├── requirements.txt
└── README.md
````

---

# Getting Started

## Requirements

* Python 3.11+
* Windows, Linux or macOS
* Devices connected to the same local network

---

## Installation

Clone the repository:

```bash
git clone https://github.com/tavmunster-art/biljartclub_app
cd biljartclub_app
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the server:

```bash
python run.py
```

By default the app runs locally on:

```text
http://127.0.0.1:5000
```

If you want to expose the app on the local network for phones/tablets, start it with:

```bash
set APP_HOST=0.0.0.0
python run.py
```

or on PowerShell:

```powershell
$env:APP_HOST = "0.0.0.0"
python run.py
```

Then open the app from another device using the laptop's hotspot IP address, for example:

```text
http://192.168.43.1:5000
```

> Note: `127.0.0.1:5000` only works on the laptop itself. Other devices must use the laptop's local hotspot IP.

---

# Using the Application

## Coordinator

Open in a desktop browser:

```text
http://SERVER-IP:5000/coordinator
```

Example:

```text
http://192.168.x.x:5000/coordinator
```

---

## Scorekeepers / Tellers

Open on phones or tablets:

```text
http://SERVER-IP:5000/teller
```

The teller interface allows users to:

* Select an available match
* Claim it
* Register scores
* Submit results

Results are only permanently stored after coordinator approval.

---

# Match Workflow

```text
Coordinator creates matches
        ↓
Teller claims match
        ↓
Scores are entered
        ↓
Result submitted
        ↓
Coordinator approves
        ↓
Result saved to database
```

This architecture prevents duplicate scoring and conflicting match results.

---

# Database

The application uses SQLite.

Default database location:

```text
instance/biljart.db
```

Backups and reports are stored separately.

---

# Reports and Backups

The application supports:

* Automatic PDF season reports
* Manual interim reports
* Database backups
* Backup restore functionality

Season closing automatically:

* Generates reports
* Creates backups
* Updates starting averages
* Purges seasonal results

---

# Network Usage

Network traffic is intentionally very small.

Typical usage:

* 4 scorekeepers
* 3 hours of play
* Approximately 2 MB total traffic

This makes the system suitable for:

* Local WiFi
* Mobile hotspots
* Small club environments

---

# Future Improvements

Potential future extensions:

* Live updates via WebSockets
* Progressive Web App (PWA)
* Multi-season statistics
* Export to Excel
* User authentication
* Cloud synchronization

---

# Getting Help

If you encounter issues or have suggestions:

* Open an issue on GitHub
* Describe the problem clearly
* Include screenshots or error messages if possible

For development questions:

* Review the route files in `app/routes`
* Check the templates in `app/templates`
* Review database logic in `database.py`

---

# Maintainers and Contributors

Project maintainer:

* Teun van Munster

Contributions are welcome.

Useful contributions include:

* Bug fixes
* UI improvements
* Tournament logic improvements
* Mobile usability improvements
* Documentation updates

Please create a pull request or open an issue before major architectural changes.

---

# License

This project is intended for educational and club-use purposes.

You may modify and adapt the software for your own billiards club or competition environment.

```
```
