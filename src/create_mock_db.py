"""
create_mock_db.py

Generates netsuite_mock.db — a SQLite database pre-populated with mock
NetSuite data. Open the .db file in VS Code with the SQLite Viewer extension.

Usage:
    venv/Scripts/python src/create_mock_db.py
"""

import sqlite3
import random
from pathlib import Path
from faker import Faker

fake = Faker()
random.seed(42)

DB_PATH = Path("netsuite_mock.db")

DDL = """
CREATE TABLE IF NOT EXISTS subsidiary (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS location (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    city          TEXT,
    country       TEXT,
    subsidiary_id INTEGER REFERENCES subsidiary(id)
);

CREATE TABLE IF NOT EXISTS department (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    subsidiary_id INTEGER REFERENCES subsidiary(id)
);

CREATE TABLE IF NOT EXISTS employee (
    id            INTEGER PRIMARY KEY,
    entityid      TEXT,
    firstname     TEXT,
    lastname      TEXT,
    email         TEXT,
    subsidiary_id INTEGER REFERENCES subsidiary(id),
    department_id INTEGER REFERENCES department(id),
    datecreated   TEXT
);

CREATE TABLE IF NOT EXISTS customer (
    id            INTEGER PRIMARY KEY,
    entityid      TEXT,
    companyname   TEXT,
    email         TEXT,
    subsidiary_id INTEGER REFERENCES subsidiary(id),
    location_id   INTEGER REFERENCES location(id),
    department_id INTEGER REFERENCES department(id),
    entitystatus  TEXT,
    externalid    TEXT,
    contract_ref  TEXT,
    datecreated   TEXT
);

CREATE TABLE IF NOT EXISTS vendor (
    id            INTEGER PRIMARY KEY,
    entityid      TEXT,
    companyname   TEXT,
    email         TEXT,
    subsidiary_id INTEGER REFERENCES subsidiary(id),
    currency_id   INTEGER,
    datecreated   TEXT
);

CREATE TABLE IF NOT EXISTS account (
    id            INTEGER PRIMARY KEY,
    acctnumber    TEXT,
    acctname      TEXT,
    accttype      TEXT,
    subsidiary_id INTEGER REFERENCES subsidiary(id)
);

CREATE TABLE IF NOT EXISTS item (
    id               INTEGER PRIMARY KEY,
    itemid           TEXT,
    salesdescription TEXT,
    itemtype         TEXT,
    rate             REAL,
    subsidiary_id    INTEGER REFERENCES subsidiary(id),
    department_id    INTEGER REFERENCES department(id),
    lastmodifieddate TEXT
);

-- ns_transaction covers Invoices, Payments, Journals, CreditMemos AND WorkOrders.
-- createdfrom links a child transaction (e.g. Invoice) back to its source (e.g. WorkOrd).
-- contract_ref is stored at transaction level (the billing / work contract reference).
CREATE TABLE IF NOT EXISTS ns_transaction (
    id            INTEGER PRIMARY KEY,
    tranid        TEXT,
    trandate      TEXT,
    type          TEXT,
    entity        INTEGER REFERENCES customer(id),
    subsidiary_id INTEGER REFERENCES subsidiary(id),
    department_id INTEGER REFERENCES department(id),
    amount        REAL,
    status        TEXT,
    memo          TEXT,
    createdfrom   INTEGER REFERENCES ns_transaction(id),
    contract_ref  TEXT
);

-- transactionline includes labour lines; employee_id links to the employee who
-- performed the work (populated for Service-type items, NULL for materials).
CREATE TABLE IF NOT EXISTS transactionline (
    id             INTEGER PRIMARY KEY,
    transaction_id INTEGER REFERENCES ns_transaction(id),
    line           INTEGER,
    item_id        INTEGER REFERENCES item(id),
    quantity       REAL,
    rate           REAL,
    amount         REAL,
    account_id     INTEGER REFERENCES account(id),
    employee_id    INTEGER REFERENCES employee(id)
);

CREATE TABLE IF NOT EXISTS salesorder (
    id            INTEGER PRIMARY KEY,
    tranid        TEXT,
    trandate      TEXT,
    entity        INTEGER REFERENCES customer(id),
    subsidiary_id INTEGER REFERENCES subsidiary(id),
    amount        REAL,
    status        TEXT
);

CREATE TABLE IF NOT EXISTS purchaseorder (
    id            INTEGER PRIMARY KEY,
    tranid        TEXT,
    trandate      TEXT,
    entity        INTEGER REFERENCES vendor(id),
    subsidiary_id INTEGER REFERENCES subsidiary(id),
    amount        REAL,
    status        TEXT
);
"""

STATUSES   = ["Customer", "Prospect", "Lead"]
ITEM_TYPES = ["InvtPart", "Service", "NonInvtPart"]
# WorkOrd added — work orders live in ns_transaction alongside financial types
TRAN_TYPES = ["Invoice", "Payment", "Journal", "CreditMemo", "WorkOrd"]
TRAN_STATS = ["Open", "Paid In Full", "Pending Approval"]
WO_STATS   = ["In Progress", "Pending", "Completed", "Cancelled"]


def seed(conn):
    c = conn.cursor()

    # --- Subsidiary (5) ---
    for i in range(1, 6):
        c.execute("INSERT INTO subsidiary VALUES (?,?)", (i, f"Subsidiary {i}"))

    # --- Location (20) — fixes customer.location_id FK target ---
    cities = ["Sydney","Melbourne","Brisbane","Perth","Adelaide",
              "London","Manchester","Edinburgh","Dublin","Birmingham",
              "New York","Chicago","Los Angeles","Houston","Phoenix",
              "Toronto","Vancouver","Auckland","Singapore","Dubai"]
    countries = ["Australia","Australia","Australia","Australia","Australia",
                 "UK","UK","UK","Ireland","UK",
                 "USA","USA","USA","USA","USA",
                 "Canada","Canada","New Zealand","Singapore","UAE"]
    for i, (city, country) in enumerate(zip(cities, countries), 1):
        c.execute("INSERT INTO location VALUES (?,?,?,?,?)",
                  (i, f"{city} Office", city, country, ((i - 1) % 5) + 1))

    # --- Department (10) ---
    dept_names = ["Finance","Sales","Operations","HR","IT",
                  "Marketing","Legal","Procurement","Engineering","Support"]
    for i, name in enumerate(dept_names, 1):
        c.execute("INSERT INTO department VALUES (?,?,?)", (i, name, random.randint(1, 5)))

    # --- Employee (150) ---
    for i in range(1, 151):
        c.execute("INSERT INTO employee VALUES (?,?,?,?,?,?,?,?)", (
            i, f"EMP-{i:04d}", fake.first_name(), fake.last_name(),
            fake.email() if random.random() > 0.1 else None,
            random.randint(1, 5), random.randint(1, 10),
            str(fake.date_between("-5y", "today")),
        ))

    # --- Customer (500) ---
    for i in range(1, 501):
        c.execute("INSERT INTO customer VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            i, f"CUST-{i:04d}", fake.company(),
            fake.email() if random.random() > 0.15 else None,
            random.randint(1, 5), random.randint(1, 20),
            random.randint(1, 10) if random.random() > 0.1 else None,
            random.choice(STATUSES), f"EXT-{i:05d}",
            f"CTR-{random.randint(1000, 9999)}" if random.random() > 0.3 else None,
            str(fake.date_between("-5y", "today")),
        ))

    # --- Vendor (200) ---
    for i in range(1, 201):
        c.execute("INSERT INTO vendor VALUES (?,?,?,?,?,?,?)", (
            i, f"VEND-{i:04d}", fake.company(),
            fake.email() if random.random() > 0.20 else None,
            random.randint(1, 5), random.randint(1, 3),
            str(fake.date_between("-5y", "today")),
        ))

    # --- Account (300) ---
    acct_types = ["Income","Expense","Asset","Liability","Equity"]
    for i in range(1, 301):
        c.execute("INSERT INTO account VALUES (?,?,?,?,?)", (
            i, f"{1000 + i}", fake.bs().title(),
            random.choice(acct_types), random.randint(1, 5),
        ))

    # --- Item (1000) ---
    for i in range(1, 1001):
        c.execute("INSERT INTO item VALUES (?,?,?,?,?,?,?,?)", (
            i, f"ITEM-{i:04d}",
            fake.catch_phrase() if random.random() > 0.08 else None,
            random.choice(ITEM_TYPES),
            round(random.uniform(1, 9999), 2) if random.random() > 0.05 else None,
            random.randint(1, 5), random.randint(1, 10),
            str(fake.date_between("-5y", "today")),
        ))

    # --- ns_transaction (5000) ---
    # Seed WorkOrders first (ids 1-1000) so Invoices can reference them via createdfrom.
    # Type distribution: WorkOrd=1000, Invoice=1500, Payment=1000, Journal=800, CreditMemo=700
    type_plan = (
        [(i, "WorkOrd") for i in range(1, 1001)] +
        [(i, "Invoice") for i in range(1001, 2501)] +
        [(i, "Payment") for i in range(2501, 3501)] +
        [(i, "Journal") for i in range(3501, 4301)] +
        [(i, "CreditMemo") for i in range(4301, 5001)]
    )
    wo_ids = list(range(1, 1001))

    for tran_id, ttype in type_plan:
        # createdfrom: ~70% of Invoices reference a WorkOrd; others NULL
        createdfrom = None
        if ttype == "Invoice" and random.random() < 0.70:
            createdfrom = random.choice(wo_ids)

        # contract_ref: present on WorkOrds and Invoices, sparse on others
        if ttype in ("WorkOrd", "Invoice"):
            contract_ref = f"CTR-{random.randint(1000, 9999)}" if random.random() > 0.15 else None
        else:
            contract_ref = None

        status = random.choice(WO_STATS) if ttype == "WorkOrd" else random.choice(TRAN_STATS)

        c.execute(
            "INSERT INTO ns_transaction VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                tran_id, f"TRAN-{tran_id:05d}",
                str(fake.date_between("-5y", "today")),
                ttype,
                random.randint(1, 500),
                random.randint(1, 5), random.randint(1, 10),
                round(random.uniform(100, 50000), 2),
                status,
                fake.sentence() if random.random() > 0.5 else None,
                createdfrom,
                contract_ref,
            )
        )

    # --- transactionline (2 per transaction = 10000) ---
    # Look up which items are Service type for employee linkage
    service_items = [row[0] for row in
                     c.execute("SELECT id FROM item WHERE itemtype='Service'").fetchall()]

    line_id = 1
    for tran_id in range(1, 5001):
        for line in range(1, 3):
            qty  = round(random.uniform(1, 50), 2)
            rate = round(random.uniform(10, 500), 2)
            item_id = random.randint(1, 1000)
            # employee_id populated for Service items (labour lines); NULL for materials
            employee_id = (random.randint(1, 150)
                           if item_id in service_items and random.random() > 0.1
                           else None)
            c.execute("INSERT INTO transactionline VALUES (?,?,?,?,?,?,?,?,?)", (
                line_id, tran_id, line,
                item_id, qty, rate,
                round(qty * rate, 2), random.randint(1, 300),
                employee_id,
            ))
            line_id += 1

    # --- SalesOrder (2500) ---
    for i in range(1, 2501):
        c.execute("INSERT INTO salesorder VALUES (?,?,?,?,?,?,?)", (
            i, f"SO-{i:05d}",
            str(fake.date_between("-5y", "today")),
            random.randint(1, 500), random.randint(1, 5),
            round(random.uniform(500, 100000), 2),
            random.choice(["Pending Fulfillment", "Closed", "Cancelled"]),
        ))

    # --- PurchaseOrder (800) ---
    for i in range(1, 801):
        c.execute("INSERT INTO purchaseorder VALUES (?,?,?,?,?,?,?)", (
            i, f"PO-{i:05d}",
            str(fake.date_between("-5y", "today")),
            random.randint(1, 200), random.randint(1, 5),
            round(random.uniform(200, 50000), 2),
            random.choice(["Pending Receipt", "Fully Billed", "Cancelled"]),
        ))

    conn.commit()


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)
    print("Seeding mock data...")
    seed(conn)
    conn.close()

    print(f"\nDatabase created: {DB_PATH.resolve()}")
    print("\nTable row counts:")
    conn = sqlite3.connect(DB_PATH)
    tables = ["subsidiary", "location", "department", "employee", "customer", "vendor",
              "account", "item", "ns_transaction", "transactionline", "salesorder", "purchaseorder"]
    for t in tables:
        count = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"  {t:<20} {count:>8,}")

    print("\nns_transaction type distribution:")
    for row in conn.execute("SELECT type, COUNT(*) FROM ns_transaction GROUP BY type ORDER BY 2 DESC").fetchall():
        print(f"  {row[0]:<15} {row[1]:>6,}")

    print("\ntransactionline employee_id coverage:")
    total = conn.execute("SELECT COUNT(*) FROM transactionline").fetchone()[0]
    with_emp = conn.execute("SELECT COUNT(*) FROM transactionline WHERE employee_id IS NOT NULL").fetchone()[0]
    print(f"  Labour lines (employee_id set): {with_emp:,} / {total:,} ({with_emp/total*100:.1f}%)")

    print("\nInvoice -> WorkOrd links (createdfrom):")
    inv = conn.execute("SELECT COUNT(*) FROM ns_transaction WHERE type='Invoice'").fetchone()[0]
    linked = conn.execute("SELECT COUNT(*) FROM ns_transaction WHERE type='Invoice' AND createdfrom IS NOT NULL").fetchone()[0]
    print(f"  Invoices with createdfrom set: {linked:,} / {inv:,} ({linked/inv*100:.1f}%)")

    conn.close()


if __name__ == "__main__":
    main()
