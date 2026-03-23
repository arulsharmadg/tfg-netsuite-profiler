# CLAUDE.md — TFG NetSuite Profiler
# Instruction file for Claude Code CLI
# Place this file at: .claude/CLAUDE.md in your project root

## System Intent
This project builds a NetSuite data profiler for TFG Discovery.
It generates mock data for 10 NetSuite Analytics Data Store tables,
profiles them for data quality, and writes a RAG-coloured Excel report.
It does NOT connect to live systems — mock mode only until credentials arrive.

## Project Structure
```
tfg-netsuite-profiler/
├── src/
│   ├── __init__.py
│   ├── netsuite_mock_data.py      ← Task 1: mock data for 10 tables
│   ├── netsuite_profiler.py       ← Task 2: profiler + Excel writer
│   └── queries/
│       └── netsuite_suiteql.sql   ← Task 3: SuiteQL extraction queries
├── output/                        ← Excel output lands here (gitignored)
├── tests/
│   ├── __init__.py
│   └── test_profiler.py           ← Task 4: smoke tests
├── .claude/
│   └── CLAUDE.md                  ← This file
├── requirements.txt
└── .gitignore
```

## Fixed Stack
- Python 3.10+
- openpyxl — Excel writing
- faker — mock data generation
- venv at ./venv — always use venv/bin/python, never system python
- No database connections, no API calls, no external dependencies

## Hard Rules (never break these)
1. All Python runs inside venv — never system python
2. output/ directory must exist before profiler writes — create it if missing
3. Profiler must assert at least 1 RED and 1 AMBER field exist in output
4. One file per task — do not combine tasks into one file
5. Do not modify .gitignore or requirements.txt unless explicitly asked
6. Do not create files outside src/, tests/, output/ — nowhere else
7. If a task conflicts with these rules — stop and flag it, never resolve silently

## Tasks — execute in order

### Task 1: netsuite_mock_data.py
File: src/netsuite_mock_data.py
Build mock data for these 10 tables:
  TRANSACTION, TRANSACTIONLINE, TRANSACTIONACCOUNTINGLINE,
  CUSTOMER, ENTITY, LOCATION, ACCOUNT, DEPARTMENT, EMPLOYEE, SUBSIDIARY

Requirements:
- Each table returns a list of dicts (same shape as SuiteQL results)
- Seed intentional quality issues: null EXTERNALID on LOCATION (40% null rate),
  mixed STATUS casing on CUSTOMER, orphan DEPARTMENT with null SUBSIDIARY_ID,
  corrupt sentinel values ("N/A", "TBD") in at least 2 tables
- Include custom field prefixes: CUSTBODY_, CUSTCOL_, CUSTENTITY_
- Expose get_all_tables() → dict and get_table(name) → list
- Script must run standalone: python src/netsuite_mock_data.py
  and print a row count summary for all 10 tables

Verification: python src/netsuite_mock_data.py — all 10 tables print with row counts

### Task 2: netsuite_profiler.py
File: src/netsuite_profiler.py
Profile all 10 tables and write output/TFG_DataProfiling_NetSuite.xlsx

Requirements:
- One Excel tab per table + a SUMMARY tab (index 0)
- Per-column stats: row_count, null_count, null_rate, distinct_count,
  sample_values, is_critical, has_corrupt, rag_rating, notes
- RAG thresholds:
    GREEN  = null rate < 10%
    AMBER  = null rate 10–30%
    RED    = null rate > 30% OR corrupt sentinels found
             OR critical field with null rate > 5%
- Critical fields per table (stricter 5% threshold):
    TRANSACTION:               ID, TRANID, RECORDTYPE, TRANDATE, ENTITY_ID
    TRANSACTIONLINE:           TRANSACTION_ID, LINE_ID, ACCOUNT_ID, AMOUNT
    TRANSACTIONACCOUNTINGLINE: TRANSACTION_ID, ACCOUNT_ID
    CUSTOMER:                  ID, ENTITYID, COMPANYNAME, SUBSIDIARY_ID
    ENTITY:                    ID, ENTITYID, TYPE
    LOCATION:                  ID, NAME, SUBSIDIARY_ID
    ACCOUNT:                   ID, ACCTNUMBER, TYPE
    DEPARTMENT:                ID, NAME
    EMPLOYEE:                  ID, ENTITYID, FIRSTNAME, LASTNAME, HIREDATE
    SUBSIDIARY:                ID, NAME, CURRENCY
- RAG fill colours: GREEN=#C6EFCE, AMBER=#FFEB9C, RED=#FFC7CE
- Header row fill: #1F4E79 (dark navy), white bold font
- Freeze panes at row 3 on every sheet
- Assert: total RED > 0 AND total AMBER > 0 — fail loudly if not
- Accept --output flag for output path override

Verification: python src/netsuite_profiler.py
  → prints table summary with RED/AMBER/GREEN counts
  → writes output/TFG_DataProfiling_NetSuite.xlsx
  → prints "Verification passed"

### Task 3: netsuite_suiteql.sql
File: src/queries/netsuite_suiteql.sql
Write SuiteQL extraction queries for all 10 ADS tables

Requirements:
- One query block per table with a comment header explaining purpose
- Include RECORDTYPE distribution query for TRANSACTION (run this first on live data)
- Include the Day 1 coverage cascade query:
    "Revenue by customer across all divisions"
    JOIN: transaction → customer → subsidiary
    GROUP BY: subsidiary name, customer name
    OUTPUT: invoice_count, total_revenue, date range
- Add inline comments for: module-dependent fields, custom field name assumptions,
  fields critical for cross-system joins
- Flag EXTERNALID on LOCATION as critical for entity resolution

Verification: file exists, readable, contains all 10 table queries + coverage cascade

### Task 4: test_profiler.py
File: tests/test_profiler.py
Write smoke tests covering:
- All 10 tables return non-empty lists from get_all_tables()
- Each table's rows are dicts with at least one key
- Profiler runs without error and output file is created
- At least 1 RED and 1 AMBER field exist in profiler output
- get_table() raises ValueError for unknown table names

Verification: venv/bin/python -m pytest tests/ -v
  → all tests pass

## Git Discipline
- Branch: feature/netsuite-profiler (already created — never commit to main)
- One commit per task after verification passes
- Commit message format: "task-N: <description>"
- Never batch multiple tasks into one commit
- Never commit output/*.xlsx files (gitignored)