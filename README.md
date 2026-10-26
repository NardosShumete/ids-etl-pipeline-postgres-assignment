# Intrusion Detection System (IDS) Data Pipeline & PostgreSQL ETL

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 14+](https://img.shields.io/badge/postgresql-14+-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: PEP 8](https://img.shields.io/badge/code%20style-pep8-orange.svg)](https://peps.python.org/pep-0008/)

An enterprise-grade data pipeline and relational schema designed to extract, clean, transform, and load high-throughput network flow telemetry (~2.83 million records) from the **CIC-IDS-2017** benchmark dataset into a normalized **PostgreSQL** data warehouse.

---

## 1. Project Overview & Business Context

### Scenario: Security Operations Center (SOC) for Ethiopian Telecommunications / Banking Infrastructure
In high-throughput enterprise networks—such as an Ethiopian Internet Service Provider (e.g., **Ethio Telecom**) or national commercial banking networks (e.g., **Commercial Bank of Ethiopia**, **Awash Bank**)—network security analysts and NOC engineers must continuously monitor network perimeter boundaries. 

The primary business objective is to ingest and query bidirectional traffic flows to detect, investigate, and mitigate malicious intrusion campaigns, including:
- **Volumetric DDoS & DoS Attacks:** Hulk, GoldenEye, Slowloris, Slowhttptest.
- **Perimeter Reconnaissance:** Automated Port Scanning (`PortScan`).
- **Credential Stuffing & Brute Force:** `FTP-Patator` and `SSH-Patator`.
- **Application Exploits:** Web attacks (SQL Injection, Cross-Site Scripting [XSS], Brute Force).
- **Advanced Persistent Threats (APTs):** Ares Botnet command-and-control (`Bot`), lateral network staging (`Infiltration`), and cryptographic memory leakage (`Heartbleed`).

This repository provides the core data architecture, normalized PostgreSQL schema, migration tooling, and automated deployment scripts supporting this data pipeline.

---

## 2. Project Directory Structure

```text
ids-etl-pipeline-postgres/
│
├── data/
│   └── raw/               # Destination for extracted CIC-IDS-2017 CSV files (git-ignored)
│       └── .gitkeep
│
├── sql/
│   ├── 01_schema.sql      # DDL schema: tables, types, domain CHECK constraints, seed data
│   └── 02_indexes.sql     # Performance B-Tree & composite indexes (run post-bulk load)
│
├── src/
│   ├── __init__.py
│   └── create_database.py # Automated database provisioning and schema migration script
│
├── tests/
│   ├── __init__.py
│   └── test_schema.py     # Automated tests validating schema definitions and constraints
│
├── docs/
│   ├── er_diagram.mmd     # Mermaid entity-relationship diagram
│   └── schema_notes.md    # Technical report on normalization (1NF-3NF) & design choices
│
├── logs/                  # Application runtime logs (git-ignored)
│   └── .gitkeep
│
├── .env.example           # Template for PostgreSQL credentials
├── .gitignore             # Strict exclusion rules for datasets, logs, venvs, and secrets
├── requirements.txt       # Production & testing Python dependencies
└── README.md              # Project documentation and setup instructions
```

---

## 3. Dataset Section

### Source & Acquisition
- **Original Source:** Canadian Institute for Cybersecurity (UNB), [CIC-IDS-2017 Dataset](https://www.unb.ca/cic/datasets/ids-2017.html)
- **Kaggle Mirror:** [chethuhn/network-intrusion-dataset](https://www.kaggle.com/datasets/chethuhn/network-intrusion-dataset)
- **File Format:** Downloaded as `archive.zip` (~1.7 GB uncompressed).
- **Scale:** ~2.83 million labeled network flows, 79 columns (78 numerical network flow features extracted via CICFlowMeter + 1 string `Label` column).

The dataset comprises network traffic captured across 5 consecutive business days:
1. `Monday-WorkingHours.pcap_ISCX.csv` (Benign baseline traffic)
2. `Tuesday-WorkingHours.pcap_ISCX.csv` (FTP-Patator and SSH-Patator brute force)
3. `Wednesday-workingHours.pcap_ISCX.csv` (DoS attacks: Hulk, GoldenEye, Slowloris, Slowhttptest; Heartbleed)
4. `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` (Web attacks: Brute Force, XSS, SQLi)
5. `Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv` (Infiltration)
6. `Friday-WorkingHours-Morning.pcap_ISCX.csv` (Botnet traffic)
7. `Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv` (DDoS flood)
8. `Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv` (PortScan reconnaissance)

### Dataset Setup Instructions
1. Download `archive.zip` from the Kaggle link above.
2. Place `archive.zip` inside the `data/` directory.
3. Extract the contents so that the raw `.csv` files reside directly in `data/raw/`:
   ```bash
   # Example extraction (PowerShell on Windows)
   Expand-Archive -Path data/archive.zip -DestinationPath data/raw/
   ```
4. **Git Safety Warning:** The `.gitignore` is configured to ignore all `.csv` and `.zip` files under `data/raw/` and `data/`. The dataset exceeds 1.7 GB, and GitHub strictly rejects files over 100 MB. Do not force-add raw data files.

---

## 4. PostgreSQL Schema & Architecture Design

The database schema is strictly designed around relational database principles (Third Normal Form) and optimized for high-volume analytical workloads:

1. **`attack_types` (Dimension Table):**
   - Normalizes text labels into 15 discrete categories (Benign, DoS, DDoS, PortScan, Brute-Force, Web Attack, Bot, Infiltration, Heartbleed).
   - Maps each label to an `is_malicious` boolean flag for fast filtering.
2. **`source_files` (Audit & Lineage Table):**
   - Tracks ingested file names, capture days, row counts, and ingestion timestamps.
3. **`flows` (Core Telemetry Table):**
   - Stores operational flow records: ports, duration, packet/byte counts, flow rates, and TCP control flags (`FIN`, `SYN`, `RST`, `PSH`, `ACK`, `URG`, `CWE`, `ECE`).
4. **`flow_statistics` (1:1 Vertically Partitioned Table):**
   - Stores 56 granular distribution metrics (packet length min/max/mean/std/variance, directional IATs, subflow statistics, TCP window sizes, active/idle connection timing).
   - **Performance Benefit:** Separating detailed statistical metrics from operational telemetry reduces row width in `flows` by ~75%, allowing **3.7x more rows per 8 KB buffer cache page** and dramatically accelerating dashboard queries.
5. **Post-Load Indexing Strategy (`sql/02_indexes.sql`):**
   - To achieve maximum ingestion throughput during ETL bulk copying, indexes are created *after* the initial data load, eliminating B-Tree balancing overhead and WAL amplification.

Detailed rationale, ER diagrams, and normalization proofs are documented in:
- [docs/schema_notes.md](file:///c:/Users/hp/Desktop/Portfolio/CIC-IDS2017/docs/schema_notes.md)
- [docs/er_diagram.mmd](file:///c:/Users/hp/Desktop/Portfolio/CIC-IDS2017/docs/er_diagram.mmd)

---

## 5. Setup & Installation Guide

### Prerequisites
- **Python:** Version 3.10 or higher.
- **PostgreSQL:** Version 14 or higher installed and running locally or on a remote server.
- **Git:** For version control.

### Step 1: Set Up Python Virtual Environment
Clone the repository and create an isolated virtual environment:

```bash
# Navigate to the project root
cd ids-etl-pipeline-postgres

# Create virtual environment (.venv)
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Windows (cmd.exe):
.venv\Scripts\activate.bat
# On Linux / macOS:
source .venv/bin/activate
```

### Step 2: Install Required Dependencies
Install the required Python packages:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Install & Configure PostgreSQL
If PostgreSQL is not yet installed:
- **Windows:** Download the official installer from [EnterpriseDB](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads). Ensure the PostgreSQL service is running in Windows Services (`services.msc`).
- **Linux (Ubuntu/Debian):** `sudo apt update && sudo apt install postgresql postgresql-contrib`
- **macOS:** `brew install postgresql@16 && brew services start postgresql@16`

### Step 4: Configure Environment Variables
Copy the template environment configuration file and update it with your PostgreSQL credentials:

```bash
# Copy template
cp .env.example .env
```

Open `.env` in an editor and set your credentials:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ids_flows_db
DB_USER=postgres
DB_PASSWORD=your_actual_password
```

### Step 5: Provision Database and Deploy Schema
Run the automated deployment script:

```bash
python src/create_database.py
```

The script will:
1. Connect to the default PostgreSQL maintenance database.
2. Check if the database (`ids_flows_db`) exists and create it with UTF-8 encoding if not.
3. Connect to `ids_flows_db` and execute `sql/01_schema.sql` to deploy all tables, CHECK constraints, foreign keys, and seed the `attack_types` lookup table.

### Step 6: Run Automated Tests
Verify that all schema definitions and scripts satisfy project specifications:

```bash
pytest tests/ -v
```

---

## 6. Next Steps (Upcoming ETL Pipeline Implementation)
- **Data Ingestion Module:** Developing `src/extract.py` and `src/transform.py` to parse CSV chunks, clean NaN/infinite values, map column names to database identifiers, and handle whitespace quirks.
- **Bulk Loading Engine:** Implementing high-performance `COPY` streaming via `psycopg2` in `src/load.py`.
- **Post-Load Indexing:** Automatically executing `sql/02_indexes.sql` once all ~2.83M records are ingested.
- **Analytical Reporting:** Authoring SQL queries and dashboard metrics for SOC threat intelligence reports.
