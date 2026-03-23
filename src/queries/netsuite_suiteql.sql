-- netsuite_suiteql.sql
-- SuiteQL extraction queries for TFG Discovery — NetSuite Analytics Data Store
--
-- Usage: Execute each block via SuiteAnalytics Connect (JDBC) or REST API
--   REST endpoint: POST /services/rest/query/v1/suiteql
--   JDBC:          jdbc:ns://account_id.suiteanalytics.com;ServerDataSource=NetSuite.com
--
-- Assumptions (verify with TFG NetSuite operator on Day 1):
--   - Analytics Data Store is enabled (separate from standard SuiteQL)
--   - Read-only role has SELECT on all tables below
--   - DEPARTMENT and LOCATION fields may be NULL if those modules are inactive
--   - Custom fields (CUSTBODY_, CUSTCOL_, CUSTENTITY_) populated only if
--     the relevant custom form is in use — confirm with operator
--
-- Field name assumptions are based on NetSuite ADS schema documentation.
-- Flag any column that does not exist — it may be module-dependent or
-- named differently in TFG's account.
-- ============================================================================


-- ============================================================================
-- 1. SUBSIDIARY
--    Reference table. Small — fetch all rows. Establishes which subsidiaries
--    are active and confirms multi-subsidiary setup.
-- ============================================================================
SELECT
    id                AS subsidiary_id,
    name              AS subsidiary_name,
    country           AS country,
    currency          AS currency,
    iselimination     AS is_elimination,
    isinactive        AS is_inactive
FROM
    subsidiary
ORDER BY id;


-- ============================================================================
-- 2. DEPARTMENT
--    Reference table. Flag any rows where subsidiary IS NULL (orphan dept).
-- ============================================================================
SELECT
    id                AS department_id,
    name              AS department_name,
    subsidiary        AS subsidiary_id,
    isinactive        AS is_inactive,
    parent            AS parent_department_id
FROM
    department
ORDER BY id;


-- ============================================================================
-- 3. ACCOUNT  (Chart of accounts)
--    Used to validate GL entries and transaction line postings.
--    Check: how many accounts have no type assigned?
-- ============================================================================
SELECT
    id                AS account_id,
    acctnumber        AS account_number,
    fullname          AS account_full_name,
    type              AS account_type,
    subsidiary        AS subsidiary_id,
    isinactive        AS is_inactive,
    description       AS description
FROM
    account
WHERE
    isinactive = 'F'
ORDER BY acctnumber;


-- ============================================================================
-- 4. LOCATION  (service locations — module-dependent)
--    EXTERNALID is critical for entity resolution against WinTeam/Jan-IT.
--    Check: what % of locations have a null EXTERNALID?
-- ============================================================================
SELECT
    id                AS location_id,
    name              AS location_name,
    subsidiary        AS subsidiary_id,
    externalid        AS external_id,
    city              AS city,
    state             AS state,
    country           AS country,
    isinactive        AS is_inactive
FROM
    location
ORDER BY id;


-- ============================================================================
-- 5. ENTITY  (parent entity table — all entity types)
--    Filtered downstream to Customer, Employee, Vendor.
--    Check: RECORDTYPE distribution — how many are Customer vs other types?
-- ============================================================================
SELECT
    id                AS entity_id,
    entityid          AS entity_code,
    altname           AS entity_name,
    type              AS entity_type,
    email             AS email,
    subsidiary        AS subsidiary_id,
    isinactive        AS is_inactive
FROM
    entity
ORDER BY id;


-- ============================================================================
-- 6. CUSTOMER  (filtered view of ENTITY — type = CustJob or Customer)
--    Key canonical target: CLIENT entity.
--    Custom field CUSTENTITY_CONTRACT_REF links to Ironclad/contract system.
--    Check: STATUS value distribution — expect mixed casing from migration.
-- ============================================================================
SELECT
    id                          AS customer_id,
    entityid                    AS customer_code,
    companyname                 AS company_name,
    email                       AS email,
    subsidiary                  AS subsidiary_id,
    location                    AS location_id,
    department                  AS department_id,
    entitystatus                AS status,
    externalid                  AS external_id,
    -- Custom field: contract reference (verify field name with operator)
    custentity_contract_ref     AS contract_ref
FROM
    customer
ORDER BY id;


-- ============================================================================
-- 7. EMPLOYEE
--    Canonical target: EMPLOYEE entity (joined with ADP for payroll).
--    HIREDATE is the join key for ADP-WinTeam employee resolution.
--    Check: how many employees are missing HIREDATE or DEPARTMENT?
-- ============================================================================
SELECT
    id                AS employee_id,
    entityid          AS employee_code,
    firstname         AS first_name,
    lastname          AS last_name,
    email             AS email,
    hiredate          AS hire_date,
    department        AS department_id,
    subsidiary        AS subsidiary_id,
    isinactive        AS is_inactive
FROM
    employee
ORDER BY id;


-- ============================================================================
-- 8. TRANSACTION  (header-level — invoices, credit memos, journals, bills)
--    RECORDTYPE distribution is the first query to run on live data.
--    Identifies all transaction types active in TFG's account.
--    Check: what % of CustInvc transactions have no ENTITY (customer)?
-- ============================================================================

-- 8a. RECORDTYPE distribution (run this first)
SELECT
    recordtype,
    COUNT(*)          AS transaction_count,
    MIN(trandate)     AS earliest_date,
    MAX(trandate)     AS latest_date
FROM
    transaction
GROUP BY recordtype
ORDER BY transaction_count DESC;

-- 8b. Full transaction extract (revenue-relevant records)
SELECT
    id                          AS transaction_id,
    tranid                      AS transaction_ref,
    recordtype                  AS record_type,
    trandate                    AS transaction_date,
    postingperiod               AS posting_period,
    status                      AS status,
    entity                      AS customer_id,
    subsidiary                  AS subsidiary_id,
    department                  AS department_id,
    location                    AS location_id,
    foreigntotal                AS gross_amount,
    foreignamountunpaid         AS amount_unpaid,
    memo                        AS memo,
    -- Custom field: division tag (verify field name with operator)
    custbody_division_tag       AS division_tag
FROM
    transaction
WHERE
    recordtype IN ('CustInvc', 'CustCred', 'Journal')
ORDER BY trandate DESC;


-- ============================================================================
-- 9. TRANSACTIONLINE  (line-level detail)
--    Canonical target: INVOICE_LINE entity.
--    Custom field CUSTCOL_SERVICE_PERIOD identifies the facility billing period.
--    Check: what % of lines have null ACCOUNT? Breaks GL reconciliation.
-- ============================================================================
SELECT
    transaction                 AS transaction_id,
    line                        AS line_id,
    item                        AS item_id,
    account                     AS account_id,
    netamount                   AS net_amount,
    quantity                    AS quantity,
    department                  AS department_id,
    location                    AS location_id,
    memo                        AS memo,
    -- Custom field: service period for facility billing
    custcol_service_period      AS service_period
FROM
    transactionLine
ORDER BY transaction, line;


-- ============================================================================
-- 10. TRANSACTIONACCOUNTINGLINE  (accounting entries — debit/credit pairs)
--     Feeds the GL_ENTRY canonical entity in the financial domain.
--     POSTING_PERIOD null rate is the key check for period-close completeness.
--     Check: for each posting period, do debits = credits? (basic TB check)
-- ============================================================================
SELECT
    transaction                 AS transaction_id,
    account                     AS account_id,
    debit                       AS debit_amount,
    credit                      AS credit_amount,
    postingperiod               AS posting_period,
    subsidiary                  AS subsidiary_id
FROM
    transactionAccountingLine
ORDER BY transaction, account;

-- Trial balance check — run after full extract
-- SELECT
--     posting_period,
--     SUM(debit_amount)  AS total_debit,
--     SUM(credit_amount) AS total_credit,
--     SUM(debit_amount) - SUM(credit_amount) AS variance
-- FROM transactionAccountingLine
-- GROUP BY posting_period
-- ORDER BY posting_period;


-- ============================================================================
-- Coverage cascade query
-- "Revenue by customer across all divisions"
-- Run on Day 1 of live access — produces the ERP coverage number
-- ============================================================================
SELECT
    s.name                      AS subsidiary,
    c.companyname               AS customer_name,
    COUNT(t.id)                 AS invoice_count,
    SUM(t.foreigntotal)         AS total_revenue,
    MIN(t.trandate)             AS first_invoice_date,
    MAX(t.trandate)             AS last_invoice_date
FROM
    transaction         t
    JOIN customer       c ON t.entity    = c.id
    JOIN subsidiary     s ON t.subsidiary = s.id
WHERE
    t.recordtype = 'CustInvc'
    AND t.status != 'Voided'
GROUP BY
    s.name, c.companyname
ORDER BY
    total_revenue DESC;