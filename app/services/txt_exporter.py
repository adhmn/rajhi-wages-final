from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from app.utils import money_for_txt, clean_text, make_file_reference, make_transaction_ref, date_yyyymmdd, normalize_number

class RajhiTxtExporter:
    """Generates tab-delimited Al Rajhi WPS TXT based on the client sample structure."""
    def __init__(self, settings: dict):
        self.settings = settings

    def _employee_payload(self, rows):
        out = []
        now = datetime.now()
        for idx, r in enumerate(rows, start=1):
            basic = normalize_number(r['basic_salary'])
            housing = normalize_number(r['housing_allowance'])
            other = normalize_number(r['other_earnings'])
            deductions = normalize_number(r['deductions'])
            net = basic + housing + other - deductions
            out.append({
                'id': r['id'],
                'name': clean_text(r['name']),
                'national_id': clean_text(r['national_id']),
                'iban': clean_text(r['iban']).replace(' ', '').upper(),
                'bank_code': clean_text(r['bank_code']) or self.settings.get('beneficiary_bank_code','RJHI'),
                'payment_description': clean_text(r['payment_description']) or self.settings.get('payment_description','Payroll'),
                'basic_salary': float(basic),
                'housing_allowance': float(housing),
                'other_earnings': float(other),
                'deductions': float(deductions),
                'net_amount': float(net),
                'transaction_ref': make_transaction_ref(idx, now)
            })
        return out

    def build_lines(self, employee_rows, value_date=None, debit_date=None, file_reference=None):
        value_date = date_yyyymmdd(value_date or datetime.now())
        debit_date = date_yyyymmdd(debit_date or datetime.now())
        file_reference = file_reference or make_file_reference()
        employees = self._employee_payload(employee_rows)
        total = sum(Decimal(str(e['net_amount'])) for e in employees)
        header = [
            clean_text(self.settings.get('establishment_bank')) or 'RJHI',
            clean_text(self.settings.get('establishment_id')),
            clean_text(self.settings.get('establishment_account')).replace(' ', '').upper(),
            clean_text(self.settings.get('currency')) or 'SAR',
            value_date,
            money_for_txt(total),
            debit_date,
            file_reference,
            'P000',
            clean_text(self.settings.get('mol_establishment_id')),
        ]
        lines = ['\t'.join(header)]
        for e in employees:
            row = [
                money_for_txt(e['net_amount']),
                e['iban'],
                e['name'],
                e['bank_code'],
                e['payment_description'],
                '',
                money_for_txt(e['basic_salary']),
                money_for_txt(e['housing_allowance']),
                money_for_txt(e['other_earnings']),
                money_for_txt(e['deductions']),
                e['national_id'],
                e['transaction_ref'],
            ]
            lines.append('\t'.join(row))
        return lines, employees, file_reference, value_date, debit_date

    def export(self, employee_rows, output_path: str, value_date=None, debit_date=None, file_reference=None):
        lines, employees, ref, vd, dd = self.build_lines(employee_rows, value_date, debit_date, file_reference)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text('\n'.join(lines), encoding='utf-8')
        return {'path': output_path, 'employees': employees, 'file_reference': ref, 'value_date': vd, 'debit_date': dd, 'lines': len(lines)}
