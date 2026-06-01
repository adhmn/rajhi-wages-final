from __future__ import annotations
import pandas as pd
from app.utils import clean_text, normalize_number

EXPECTED_FIELDS = {
    'net_amount': ['Net amount to be paid to the individual laborer', 'net amount', 'الصافي', 'صافي'],
    'iban': ["Beneficiary's account number", 'iban', 'الآيبان', 'ايبان'],
    'name': ["Beneficiary customer's name", 'name', 'الاسم', 'اسم العامل'],
    'bank_code': ["Bank Code where the Beneficiary's account is held", 'bank code', 'كود البنك'],
    'payment_description': ['Payment Description', 'description', 'الوصف'],
    'basic_salary': ['Laborer Basic Salary for the current month', 'basic salary', 'الراتب الأساسي', 'راتب'],
    'housing_allowance': ['Laborer Housing Allowance for the current month', 'housing', 'بدل السكن'],
    'other_earnings': ['Laborer Other Earnings for the current month', 'other earnings', 'بدلات', 'بدل'],
    'deductions': ['Laborer Deductions for the current month', 'deductions', 'خصومات'],
    'national_id': ['Laborer (Government) ID', 'government id', 'laborer id', 'الهوية', 'الإقامة', 'اقامة'],
    'transaction_ref': ['Transaction Reference number', 'transaction']
}

HEADER_FIELDS = {
    'establishment_bank': ["Establishment's Bank"],
    'establishment_id': ["Establishment's Id"],
    'establishment_account': ['Establishments Bank Account Number'],
    'currency': ['Currency Code'],
    'total_amount': ['Total Amount'],
    'mol_establishment_id': ['MOL Establishment Id'],
}

def _find_header_row(df):
    for i in range(len(df)):
        row = ' | '.join(clean_text(x).lower() for x in df.iloc[i].tolist())
        if 'beneficiary' in row and 'laborer' in row:
            return i
    return None

def _match_col(header_values, names):
    for idx, val in enumerate(header_values):
        txt = clean_text(val).lower()
        if not txt:
            continue
        for n in names:
            needle = clean_text(n).lower()
            if needle and (needle in txt or txt in needle):
                return idx
    return None

def read_rajhi_excel(path: str):
    # Read all rows no header to support official Wage Details file.
    xl = pd.ExcelFile(path)
    sheet = 'Wage Details' if 'Wage Details' in xl.sheet_names else xl.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet, header=None)

    header_settings = {}
    # Official header values are in row 7 for sample.
    try:
        for i in range(len(df)):
            row = [clean_text(x) for x in df.iloc[i].tolist()]
            if "Establishment's Bank" in row:
                labels = row
                values = [clean_text(x) for x in df.iloc[i+2].tolist()] if i+2 < len(df) else []
                for key, names in HEADER_FIELDS.items():
                    col = _match_col(labels, names)
                    if col is not None and col < len(values):
                        header_settings[key] = values[col]
                break
    except Exception:
        pass

    header_row = _find_header_row(df)
    if header_row is None:
        return read_generic_excel(path), header_settings

    labels = df.iloc[header_row].tolist()
    colmap = {key: _match_col(labels, names) for key, names in EXPECTED_FIELDS.items()}
    employees = []
    for i in range(header_row + 2, len(df)):
        row = df.iloc[i].tolist()
        if all(clean_text(x) == '' for x in row):
            continue
        def get(key):
            c = colmap.get(key)
            return row[c] if c is not None and c < len(row) else ''
        national_id = clean_text(get('national_id'))
        iban = clean_text(get('iban')).replace(' ', '').upper()
        name = clean_text(get('name'))
        if not national_id or not iban or not name:
            continue
        basic = normalize_number(get('basic_salary'))
        housing = normalize_number(get('housing_allowance'))
        other = normalize_number(get('other_earnings'))
        deductions = normalize_number(get('deductions'))
        employees.append({
            'employee_code': '',
            'name': name,
            'national_id': national_id,
            'iban': iban,
            'nationality': '',
            'employee_type': 'سعودي' if national_id.startswith('1') else 'غير سعودي',
            'basic_salary': basic,
            'housing_allowance': housing,
            'other_earnings': other,
            'deductions': deductions,
            'bank_code': clean_text(get('bank_code')) or 'RJHI',
            'payment_description': clean_text(get('payment_description')) or 'Payroll',
            'notes': '',
        })
    return employees, header_settings


def read_generic_excel(path: str):
    df = pd.read_excel(path)
    normalized_cols = {clean_text(c).lower(): c for c in df.columns}
    def find(*names):
        for n in names:
            n = clean_text(n).lower()
            for k, c in normalized_cols.items():
                if n in k or k in n:
                    return c
        return None
    cols = {
        'name': find('name', 'الاسم', 'اسم العامل'),
        'national_id': find('id', 'هوية', 'اقامة', 'الإقامة'),
        'iban': find('iban', 'ايبان', 'آيبان'),
        'nationality': find('nationality', 'الجنسية'),
        'basic_salary': find('basic', 'salary', 'راتب', 'الراتب'),
        'housing_allowance': find('housing', 'سكن'),
        'other_earnings': find('other', 'allowance', 'بدل', 'بدلات'),
        'deductions': find('deduction', 'خصم', 'خصومات'),
    }
    employees = []
    for _, row in df.iterrows():
        name = clean_text(row.get(cols['name'])) if cols['name'] else ''
        nid = clean_text(row.get(cols['national_id'])) if cols['national_id'] else ''
        iban = clean_text(row.get(cols['iban'])).replace(' ', '').upper() if cols['iban'] else ''
        if not name or not nid or not iban:
            continue
        employees.append({
            'employee_code': '', 'name': name, 'national_id': nid, 'iban': iban,
            'nationality': clean_text(row.get(cols['nationality'])) if cols['nationality'] else '',
            'employee_type': 'سعودي' if nid.startswith('1') else 'غير سعودي',
            'basic_salary': normalize_number(row.get(cols['basic_salary'])) if cols['basic_salary'] else 0,
            'housing_allowance': normalize_number(row.get(cols['housing_allowance'])) if cols['housing_allowance'] else 0,
            'other_earnings': normalize_number(row.get(cols['other_earnings'])) if cols['other_earnings'] else 0,
            'deductions': normalize_number(row.get(cols['deductions'])) if cols['deductions'] else 0,
            'bank_code': 'RJHI', 'payment_description': 'Payroll', 'notes': ''
        })
    return employees
