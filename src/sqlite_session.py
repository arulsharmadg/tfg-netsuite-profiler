"""
sqlite_session.py

Spins up an in-memory SQLite database pre-populated with mock NetSuite tables
and opens an interactive SQL shell. Type your SuiteQL-style queries directly.

Usage:
    venv/Scripts/python src/sqlite_session.py
"""

import sqlite3
import random
from faker import Faker

fake = Faker()
random.seed(42)

# ---------------------------------------------------------------------------
# Schema + seed data
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE subsidiary (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE location (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    city          TEXT,
    country       TEXT,
    subsidiary_id INTEGER REFERENCES subsidiary(id)
);

CREATE TABLE department (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    subsidiary_id INTEGER REFERENCES subsidiary(id)
);

CREATE TABLE employee (
    id            INTEGER PRIMARY KEY,
    entityid      TEXT,
    firstname     TEXT,
    lastname      TEXT,
    email         TEXT,
    subsidiary_id INTEGER REFERENCES subsidiary(id),
    department_id INTEGER REFERENCES department(id),
    datecreated   TEXT
);

CREATE TABLE customer (
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

CREATE TABLE vendor (
    id            INTEGER PRIMARY KEY,
    entityid      TEXT,
    companyname   TEXT,
    email         TEXT,
    subsidiary_id INTEGER REFERENCES subsidiary(id),
    currency_id   INTEGER,
    datecreated   TEXT
);

CREATE TABLE account (
    id            INTEGER PRIMARY KEY,
    acctnumber    TEXT,
    acctname      TEXT,
    accttype      TEXT,
    subsidiary_id INTEGER REFERENCES subsidiary(id)
);

CREATE TABLE item (
    id               INTEGER PRIMARY KEY,
    itemid           TEXT,
    salesdescription TEXT,
    itemtype         TEXT,
    rate             REAL,
    subsidiary_id    INTEGER REFERENCES subsidiary(id),
    department_id    INTEGER REFERENCES department(id),
    lastmodifieddate TEXT
);

-- ns_transaction covers WorkOrd, Invoice, Payment, Journal, CreditMemo.
-- createdfrom links a child transaction back to its source (e.g. Invoice -> WorkOrd).
-- contract_ref is the billing/work contract reference at transaction level.
CREATE TABLE ns_transaction (
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

-- employee_id is populated for Service (labour) lines; NULL for material lines.
CREATE TABLE transactionline (
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

CREATE TABLE salesorder (
    id            INTEGER PRIMARY KEY,
    tranid        TEXT,
    trandate      TEXT,
    entity        INTEGER REFERENCES customer(id),
    subsidiary_id INTEGER REFERENCES subsidiary(id),
    amount        REAL,
    status        TEXT
);

CREATE TABLE purchaseorder (
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
TRAN_STATS = ["Open", "Paid In Full", "Pending Approval"]
WO_STATS   = ["In Progress", "Pending", "Completed", "Cancelled"]


def seed(conn):
    c = conn.cursor()

    # subsidiaries (5)
    for i in range(1, 6):
        c.execute("INSERT INTO subsidiary VALUES (?,?)", (i, f"Subsidiary {i}"))

    # locations (20)
    cities = ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide",
              "London", "Manchester", "Edinburgh", "Dublin", "Birmingham",
              "New York", "Chicago", "Los Angeles", "Houston", "Phoenix",
              "Toronto", "Vancouver", "Auckland", "Singapore", "Dubai"]
    countries = ["Australia", "Australia", "Australia", "Australia", "Australia",
                 "UK", "UK", "UK", "Ireland", "UK",
                 "USA", "USA", "USA", "USA", "USA",
                 "Canada", "Canada", "New Zealand", "Singapore", "UAE"]
    for i, (city, country) in enumerate(zip(cities, countries), 1):
        c.execute("INSERT INTO location VALUES (?,?,?,?,?)",
                  (i, f"{city} Office", city, country, ((i - 1) % 5) + 1))

    # departments (10)
    dept_names = ["Finance", "Sales", "Operations", "HR", "IT",
                  "Marketing", "Legal", "Procurement", "Engineering", "Support"]
    for i, name in enumerate(dept_names, 1):
        c.execute("INSERT INTO department VALUES (?,?,?)", (i, name, random.randint(1, 5)))

    # employees (150)
    for i in range(1, 151):
        c.execute("INSERT INTO employee VALUES (?,?,?,?,?,?,?,?)", (
            i, f"EMP-{i:04d}", fake.first_name(), fake.last_name(),
            fake.email() if random.random() > 0.1 else None,
            random.randint(1, 5), random.randint(1, 10),
            str(fake.date_between("-5y", "today")),
        ))

    # customers (500) — location_id references location(id) 1-20
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

    # vendors (200)
    for i in range(1, 201):
        c.execute("INSERT INTO vendor VALUES (?,?,?,?,?,?,?)", (
            i, f"VEND-{i:04d}", fake.company(),
            fake.email() if random.random() > 0.20 else None,
            random.randint(1, 5), random.randint(1, 3),
            str(fake.date_between("-5y", "today")),
        ))

    # accounts (300)
    acct_types = ["Income", "Expense", "Asset", "Liability", "Equity"]
    for i in range(1, 301):
        c.execute("INSERT INTO account VALUES (?,?,?,?,?)", (
            i, f"{1000 + i}", fake.bs().title(),
            random.choice(acct_types), random.randint(1, 5),
        ))

    # items (1000)
    for i in range(1, 1001):
        c.execute("INSERT INTO item VALUES (?,?,?,?,?,?,?,?)", (
            i, f"ITEM-{i:04d}",
            fake.catch_phrase() if random.random() > 0.08 else None,
            random.choice(ITEM_TYPES),
            round(random.uniform(1, 9999), 2) if random.random() > 0.05 else None,
            random.randint(1, 5), random.randint(1, 10),
            str(fake.date_between("-5y", "today")),
        ))

    # ns_transaction (5000): WorkOrd=1000, Invoice=1500, Payment=1000, Journal=800, CreditMemo=700
    # Seed WorkOrds first so Invoices can reference them via createdfrom
    type_plan = (
        [(i, "WorkOrd")   for i in range(1, 1001)] +
        [(i, "Invoice")   for i in range(1001, 2501)] +
        [(i, "Payment")   for i in range(2501, 3501)] +
        [(i, "Journal")   for i in range(3501, 4301)] +
        [(i, "CreditMemo") for i in range(4301, 5001)]
    )
    wo_ids = list(range(1, 1001))

    for tran_id, ttype in type_plan:
        # ~70% of Invoices reference a WorkOrd via createdfrom
        createdfrom = None
        if ttype == "Invoice" and random.random() < 0.70:
            createdfrom = random.choice(wo_ids)

        # contract_ref on WorkOrds and Invoices; sparse on others
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

    # transactionline (2 per transaction = 10000)
    # employee_id populated for Service items (labour lines); NULL for materials
    service_items = [row[0] for row in
                     c.execute("SELECT id FROM item WHERE itemtype='Service'").fetchall()]
    line_id = 1
    for tran_id in range(1, 5001):
        for line in range(1, 3):
            qty  = round(random.uniform(1, 50), 2)
            rate = round(random.uniform(10, 500), 2)
            item_id = random.randint(1, 1000)
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

    # sales orders (2500)
    for i in range(1, 2501):
        c.execute("INSERT INTO salesorder VALUES (?,?,?,?,?,?,?)", (
            i, f"SO-{i:05d}",
            str(fake.date_between("-5y", "today")),
            random.randint(1, 500), random.randint(1, 5),
            round(random.uniform(500, 100000), 2),
            random.choice(["Pending Fulfillment", "Closed", "Cancelled"]),
        ))

    # purchase orders (800)
    for i in range(1, 801):
        c.execute("INSERT INTO purchaseorder VALUES (?,?,?,?,?,?,?)", (
            i, f"PO-{i:05d}",
            str(fake.date_between("-5y", "today")),
            random.randint(1, 200), random.randint(1, 5),
            round(random.uniform(200, 50000), 2),
            random.choice(["Pending Receipt", "Fully Billed", "Cancelled"]),
        ))

    conn.commit()
    print("Database seeded successfully.\n")


# ---------------------------------------------------------------------------
# Interactive shell
# ---------------------------------------------------------------------------

HELP_TEXT = """
Commands:
  .tables                — list all tables
  .schema <table>        — show CREATE statement for a table
  .rowcount              — show row counts for all tables
  .query [name]          — run predefined named query (omit name to list)
  .quit / .exit          — exit the session
  Any SQL                — execute directly (end multi-line with ;)
"""

PREDEFINED_QUERIES = {
    "revenue_by_customer": """
SELECT
    s.name                      AS subsidiary,
    c.companyname               AS customer_name,
    COUNT(t.id)                 AS invoice_count,
    SUM(t.amount)               AS total_revenue,
    MIN(t.trandate)             AS first_invoice_date,
    MAX(t.trandate)             AS last_invoice_date
FROM
    ns_transaction t
    JOIN customer c   ON t.entity        = c.id
    JOIN subsidiary s ON t.subsidiary_id = s.id
WHERE
    t.type = 'Invoice'
    AND t.status != 'Voided'
GROUP BY
    s.name, c.companyname
ORDER BY
    total_revenue DESC
LIMIT 100;""",

    "transactionline_missing_account": """
SELECT
    tl.id AS transactionline_id,
    tl.transaction_id,
    tl.line,
    t.tranid AS transaction_ref,
    tl.amount,
    tl.account_id
FROM
    transactionline tl
    JOIN ns_transaction t ON tl.transaction_id = t.id
WHERE
    tl.account_id IS NULL
ORDER BY
    tl.transaction_id, tl.line
LIMIT 100;""",

    "workorder_invoice_links": """
SELECT
    wo.tranid   AS workorder_ref,
    wo.status   AS wo_status,
    inv.tranid  AS invoice_ref,
    inv.trandate AS invoice_date,
    inv.amount  AS invoice_amount,
    inv.contract_ref
FROM
    ns_transaction inv
    JOIN ns_transaction wo ON inv.createdfrom = wo.id
WHERE
    inv.type = 'Invoice'
    AND wo.type  = 'WorkOrd'
ORDER BY
    inv.trandate DESC
LIMIT 100;""",

    "labour_lines": """
SELECT
    tl.id            AS line_id,
    t.tranid         AS transaction_ref,
    t.type           AS tran_type,
    i.itemid         AS item_ref,
    i.itemtype,
    tl.quantity,
    tl.rate,
    tl.amount,
    e.entityid       AS employee_ref,
    e.firstname || ' ' || e.lastname AS employee_name
FROM
    transactionline tl
    JOIN ns_transaction t ON tl.transaction_id = t.id
    JOIN item i           ON tl.item_id        = i.id
    JOIN employee e       ON tl.employee_id    = e.id
WHERE
    tl.employee_id IS NOT NULL
ORDER BY
    tl.amount DESC
LIMIT 100;""",
}


def show_tables(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print("\n".join(f"  {r[0]}" for r in rows))


def show_schema(conn, table):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    print(row[0] if row else f"Table '{table}' not found.")


def show_rowcount(conn):
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"  {'Table':<20} {'Rows':>8}")
    print("  " + "-" * 30)
    for (name,) in tables:
        count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        print(f"  {name:<20} {count:>8,}")


def run_predefined_query(conn, name=None):
    if not name:
        print("Predefined queries:")
        for key in sorted(PREDEFINED_QUERIES.keys()):
            print(f"  {key}")
        return

    sql = PREDEFINED_QUERIES.get(name)
    if not sql:
        print(f"Unknown predefined query: {name}")
        print("Use '.query' to list available queries")
        return

    print(f"Running predefined query '{name}'...\n")
    run_query(conn, sql)


def run_query(conn, sql):
    try:
        cur = conn.execute(sql)
        rows = cur.fetchall()
        if cur.description:
            headers = [d[0] for d in cur.description]
            col_widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
                          for i, h in enumerate(headers)]
            fmt = "  " + "  ".join(f"{{:<{w}}}" for w in col_widths)
            print(fmt.format(*headers))
            print("  " + "  ".join("-" * w for w in col_widths))
            for row in rows:
                print(fmt.format(*[str(v) if v is not None else "NULL" for v in row]))
            print(f"\n  ({len(rows)} row{'s' if len(rows) != 1 else ''})")
        else:
            print(f"  OK — {conn.total_changes} row(s) affected.")
    except Exception as e:
        print(f"  ERROR: {e}")


def repl(conn):
    print("NetSuite Mock SQLite Session")
    print("Type .help for commands, .quit to exit.\n")
    buffer = []
    while True:
        prompt = "sql> " if not buffer else "   > "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = line.strip()

        if stripped.lower() in (".quit", ".exit"):
            break
        elif stripped.lower() == ".help":
            print(HELP_TEXT)
        elif stripped.lower() == ".tables":
            show_tables(conn)
        elif stripped.lower().startswith(".schema"):
            parts = stripped.split()
            show_schema(conn, parts[1] if len(parts) > 1 else "")
        elif stripped.lower() == ".rowcount":
            show_rowcount(conn)
        elif stripped.lower().startswith(".query"):
            parts = stripped.split()
            if len(parts) == 1:
                run_predefined_query(conn)
            else:
                run_predefined_query(conn, parts[1])
        elif stripped == "":
            continue
        else:
            buffer.append(line)
            if stripped.endswith(";"):
                run_query(conn, " ".join(buffer))
                buffer = []


if __name__ == "__main__":
    conn = sqlite3.connect(":memory:")
    conn.executescript(DDL)
    print("Seeding mock data (this takes a few seconds)...")
    seed(conn)
    repl(conn)
    conn.close()
    print("Session closed.")
