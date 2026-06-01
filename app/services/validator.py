from app.utils import validate_iban, validate_sa_id, normalize_number

def validate_employee(data: dict):
    errors = []
    if not str(data.get('name','')).strip(): errors.append('اسم العامل مطلوب')
    if not validate_sa_id(str(data.get('national_id',''))): errors.append('رقم الهوية/الإقامة يجب أن يكون 10 أرقام')
    if not validate_iban(str(data.get('iban',''))): errors.append('الآيبان يجب أن يبدأ بـ SA ويتكون من 24 خانة')
    if normalize_number(data.get('basic_salary')) < 0: errors.append('الراتب لا يمكن أن يكون بالسالب')
    return errors
