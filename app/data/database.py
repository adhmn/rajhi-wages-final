from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from app.utils import clean_text, normalize_number

SCHEMA = r'''
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT,
    name TEXT NOT NULL,
    national_id TEXT NOT NULL UNIQUE,
    iban TEXT NOT NULL,
    nationality TEXT,
    employee_type TEXT DEFAULT 'غير سعودي',
    basic_salary REAL DEFAULT 0,
    housing_allowance REAL DEFAULT 0,
    other_earnings REAL DEFAULT 0,
    deductions REAL DEFAULT 0,
    bank_code TEXT DEFAULT 'RJHI',
    payment_description TEXT DEFAULT 'Payroll',
    is_active INTEGER DEFAULT 1,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_employees_name ON employees(name);
CREATE INDEX IF NOT EXISTS idx_employees_nid ON employees(national_id);
CREATE INDEX IF NOT EXISTS idx_employees_iban ON employees(iban);

CREATE TABLE IF NOT EXISTS payroll_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_name TEXT NOT NULL,
    value_date TEXT NOT NULL,
    debit_date TEXT NOT NULL,
    file_reference TEXT NOT NULL,
    total_amount REAL NOT NULL,
    employees_count INTEGER NOT NULL,
    export_path TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS payroll_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    employee_id INTEGER,
    name TEXT,
    national_id TEXT,
    iban TEXT,
    net_amount REAL,
    basic_salary REAL,
    housing_allowance REAL,
    other_earnings REAL,
    deductions REAL,
    transaction_ref TEXT,
    FOREIGN KEY(run_id) REFERENCES payroll_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT
);
'''

class Database:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def log(self, action: str, details: str = ''):
        self.conn.execute("INSERT INTO audit_log(action, details, created_at) VALUES(?,?,?)", (action, details, datetime.now().isoformat(timespec='seconds')))
        self.conn.commit()

    def list_employees(self, q: str = '', active_only: bool = True, limit: int = 5000):
        sql = "SELECT * FROM employees WHERE 1=1"
        params = []
        if active_only:
            sql += " AND is_active=1"
        if q:
            like = f"%{q}%"
            sql += " AND (name LIKE ? OR national_id LIKE ? OR iban LIKE ? OR nationality LIKE ?)"
            params += [like, like, like, like]
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, params).fetchall()

    def count_employees(self):
        return self.conn.execute("SELECT COUNT(*) c FROM employees WHERE is_active=1").fetchone()["c"]

    def totals(self):
        row = self.conn.execute("""
            SELECT COUNT(*) c,
                   COALESCE(SUM(basic_salary),0) basic,
                   COALESCE(SUM(housing_allowance),0) house,
                   COALESCE(SUM(other_earnings),0) other,
                   COALESCE(SUM(deductions),0) ded
            FROM employees WHERE is_active=1
        """).fetchone()
        net = Decimal(str(row['basic'])) + Decimal(str(row['house'])) + Decimal(str(row['other'])) - Decimal(str(row['ded']))
        return dict(count=row['c'], basic=row['basic'], housing=row['house'], other=row['other'], deductions=row['ded'], net=float(net))

    def upsert_employee(self, data: dict):
        now = datetime.now().isoformat(timespec='seconds')
        fields = {
            'employee_code': clean_text(data.get('employee_code')),
            'name': clean_text(data.get('name')),
            'national_id': clean_text(data.get('national_id')),
            'iban': clean_text(data.get('iban')).replace(' ', '').upper(),
            'nationality': clean_text(data.get('nationality')),
            'employee_type': clean_text(data.get('employee_type')) or 'غير سعودي',
            'basic_salary': float(normalize_number(data.get('basic_salary'))),
            'housing_allowance': float(normalize_number(data.get('housing_allowance'))),
            'other_earnings': float(normalize_number(data.get('other_earnings'))),
            'deductions': float(normalize_number(data.get('deductions'))),
            'bank_code': clean_text(data.get('bank_code')) or 'RJHI',
            'payment_description': clean_text(data.get('payment_description')) or 'Payroll',
            'notes': clean_text(data.get('notes')),
        }
        existing = self.conn.execute("SELECT id FROM employees WHERE national_id=?", (fields['national_id'],)).fetchone()
        if existing:
            fields['updated_at'] = now
            sets = ', '.join([f"{k}=?" for k in fields.keys()] + ["is_active=1"])
            self.conn.execute(f"UPDATE employees SET {sets} WHERE id=?", list(fields.values()) + [existing['id']])
            emp_id = existing['id']
            self.log('update_employee', fields['national_id'])
        else:
            fields['created_at'] = now
            fields['updated_at'] = now
            cols = ','.join(fields.keys())
            ph = ','.join(['?'] * len(fields))
            cur = self.conn.execute(f"INSERT INTO employees({cols}) VALUES({ph})", list(fields.values()))
            emp_id = cur.lastrowid
            self.log('add_employee', fields['national_id'])
        self.conn.commit()
        return emp_id

    def delete_employee(self, emp_id: int):
        self.conn.execute("UPDATE employees SET is_active=0, updated_at=? WHERE id=?", (datetime.now().isoformat(timespec='seconds'), emp_id))
        self.conn.commit()
        self.log('delete_employee', str(emp_id))

    def get_employee(self, emp_id: int):
        return self.conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()

    def bulk_update_salary(self, mode: str, amount: float, field: str = 'basic_salary'):
        allowed = {'basic_salary', 'housing_allowance', 'other_earnings', 'deductions'}
        if field not in allowed:
            raise ValueError('Invalid field')
        if mode == 'set':
            self.conn.execute(f"UPDATE employees SET {field}=?, updated_at=? WHERE is_active=1", (amount, datetime.now().isoformat(timespec='seconds')))
        elif mode == 'add':
            self.conn.execute(f"UPDATE employees SET {field}={field}+?, updated_at=? WHERE is_active=1", (amount, datetime.now().isoformat(timespec='seconds')))
        elif mode == 'percent':
            self.conn.execute(f"UPDATE employees SET {field}=ROUND({field}+({field}*?/100),2), updated_at=? WHERE is_active=1", (amount, datetime.now().isoformat(timespec='seconds')))
        self.conn.commit()
        self.log('bulk_update_salary', f'{mode} {field} {amount}')

    def save_payroll_run(self, period_name, value_date, debit_date, file_reference, export_path, employees):
        total = sum(float(e['net_amount']) for e in employees)
        cur = self.conn.execute("""
            INSERT INTO payroll_runs(period_name,value_date,debit_date,file_reference,total_amount,employees_count,export_path,created_at)
            VALUES(?,?,?,?,?,?,?,?)
        """, (period_name, value_date, debit_date, file_reference, total, len(employees), export_path, datetime.now().isoformat(timespec='seconds')))
        run_id = cur.lastrowid
        for e in employees:
            self.conn.execute("""
                INSERT INTO payroll_items(run_id, employee_id, name, national_id, iban, net_amount, basic_salary, housing_allowance, other_earnings, deductions, transaction_ref)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (run_id, e.get('id'), e.get('name'), e.get('national_id'), e.get('iban'), e.get('net_amount'), e.get('basic_salary'), e.get('housing_allowance'), e.get('other_earnings'), e.get('deductions'), e.get('transaction_ref')))
        self.conn.commit()
        self.log('export_payroll', f'{period_name} - {export_path}')
        return run_id

    def list_runs(self, limit=100):
        return self.conn.execute("SELECT * FROM payroll_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
