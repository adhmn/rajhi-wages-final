from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
from decimal import Decimal

from app.config import APP_AR_NAME, load_settings, save_settings
from app.data.database import Database
from app.services.excel_importer import read_rajhi_excel
from app.services.txt_exporter import RajhiTxtExporter
from app.services.validator import validate_employee
from app.utils import clean_text, normalize_number, make_file_reference

class RajhiWagesApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_AR_NAME)
        self.geometry('1280x760')
        self.minsize(1100, 680)
        self.configure(bg='#0f172a')
        self.settings = load_settings()
        self.db = Database(self.settings['db_path'])
        self.selected_id = None
        self._build_styles()
        self._build_layout()
        self.refresh_all()

    def _build_styles(self):
        style = ttk.Style(self)
        try: style.theme_use('clam')
        except Exception: pass
        style.configure('Treeview', rowheight=30, font=('Segoe UI', 10), background='#ffffff', fieldbackground='#ffffff', foreground='#111827')
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), background='#e5e7eb', foreground='#111827')
        style.configure('TNotebook', background='#0f172a', borderwidth=0)
        style.configure('TNotebook.Tab', font=('Segoe UI', 10, 'bold'), padding=(18,8))

    def _btn(self, parent, text, cmd, bg='#2563eb'):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg='white', activebackground=bg, activeforeground='white', relief='flat', padx=14, pady=8, font=('Segoe UI', 10, 'bold'), cursor='hand2')

    def _entry(self, parent, width=18):
        return tk.Entry(parent, width=width, font=('Segoe UI', 10), relief='flat', bg='white', fg='#111827', insertbackground='#111827')

    def _label(self, parent, text, fg='#e5e7eb', font=('Segoe UI', 10)):
        return tk.Label(parent, text=text, fg=fg, bg=parent['bg'], font=font, anchor='e')

    def _build_layout(self):
        header = tk.Frame(self, bg='#111827', height=72)
        header.pack(fill='x')
        tk.Label(header, text='برنامج أجور الراجحي', bg='#111827', fg='white', font=('Segoe UI', 18, 'bold')).pack(side='right', padx=24, pady=16)
        self.stats_label = tk.Label(header, text='', bg='#111827', fg='#fbbf24', font=('Segoe UI', 11, 'bold'))
        self.stats_label.pack(side='left', padx=24)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', expand=True, padx=14, pady=14)
        self.tab_employees = tk.Frame(self.tabs, bg='#0f172a')
        self.tab_export = tk.Frame(self.tabs, bg='#0f172a')
        self.tab_settings = tk.Frame(self.tabs, bg='#0f172a')
        self.tab_history = tk.Frame(self.tabs, bg='#0f172a')
        self.tabs.add(self.tab_employees, text='العمال والرواتب')
        self.tabs.add(self.tab_export, text='توليد ملف TXT')
        self.tabs.add(self.tab_settings, text='إعدادات المنشأة والشبكة')
        self.tabs.add(self.tab_history, text='المسيرات السابقة')
        self._build_employees_tab()
        self._build_export_tab()
        self._build_settings_tab()
        self._build_history_tab()

    def _build_employees_tab(self):
        top = tk.Frame(self.tab_employees, bg='#0f172a')
        top.pack(fill='x', pady=(0,10))
        self.search_var = tk.StringVar()
        tk.Label(top, text='بحث:', bg='#0f172a', fg='white', font=('Segoe UI', 11, 'bold')).pack(side='right', padx=8)
        search = self._entry(top, 35)
        search.configure(textvariable=self.search_var)
        search.pack(side='right', padx=8, ipady=8)
        search.bind('<KeyRelease>', lambda e: self.load_employees())
        self._btn(top, 'استيراد Excel العميل', self.import_excel, '#16a34a').pack(side='right', padx=5)
        self._btn(top, 'تعديل جماعي', self.bulk_update_dialog, '#9333ea').pack(side='right', padx=5)
        self._btn(top, 'تحديث', self.refresh_all, '#475569').pack(side='right', padx=5)

        form = tk.LabelFrame(self.tab_employees, text='بيانات العامل', bg='#111827', fg='white', font=('Segoe UI', 11, 'bold'), padx=10, pady=10)
        form.pack(fill='x', pady=(0,10))
        self.fields = {}
        labels = [
            ('name','اسم العامل'), ('national_id','رقم الهوية/الإقامة'), ('iban','الآيبان'), ('nationality','الجنسية'),
            ('employee_type','سعودي/غير سعودي'), ('basic_salary','الراتب'), ('housing_allowance','بدل السكن'), ('other_earnings','بدلات أخرى'), ('deductions','خصومات')
        ]
        for idx,(key,label) in enumerate(labels):
            r = idx//3; c=(idx%3)*2
            tk.Label(form, text=label, bg='#111827', fg='#cbd5e1', font=('Segoe UI', 10, 'bold')).grid(row=r, column=c+1, sticky='e', padx=6, pady=6)
            if key == 'employee_type':
                v = tk.StringVar(value='غير سعودي')
                cb = ttk.Combobox(form, textvariable=v, values=['سعودي','غير سعودي'], width=20, state='readonly')
                cb.grid(row=r, column=c, sticky='ew', padx=6, pady=6, ipady=4)
                self.fields[key] = v
            else:
                ent = self._entry(form, 24)
                ent.grid(row=r, column=c, sticky='ew', padx=6, pady=6, ipady=6)
                self.fields[key] = ent
        for i in range(6): form.grid_columnconfigure(i, weight=1)
        actions = tk.Frame(form, bg='#111827')
        actions.grid(row=4, column=0, columnspan=6, sticky='w', pady=8)
        self._btn(actions, 'حفظ / تحديث العامل', self.save_employee, '#2563eb').pack(side='right', padx=5)
        self._btn(actions, 'جديد', self.clear_form, '#64748b').pack(side='right', padx=5)
        self._btn(actions, 'حذف المحدد', self.delete_selected, '#dc2626').pack(side='right', padx=5)

        table_frame = tk.Frame(self.tab_employees, bg='#0f172a')
        table_frame.pack(fill='both', expand=True)
        cols = ('id','name','national_id','iban','type','basic','housing','other','deductions','net')
        self.tree = ttk.Treeview(table_frame, columns=cols, show='headings', selectmode='browse')
        headings = {'id':'#','name':'الاسم','national_id':'الهوية/الإقامة','iban':'الآيبان','type':'النوع','basic':'الراتب','housing':'السكن','other':'بدلات','deductions':'خصومات','net':'الصافي'}
        widths = {'id':50,'name':180,'national_id':120,'iban':230,'type':95,'basic':90,'housing':90,'other':90,'deductions':90,'net':100}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor='center')
        y = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side='left', fill='both', expand=True)
        y.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self.on_select_employee)
        self.tree.bind('<Double-1>', self.on_select_employee)

    def _build_export_tab(self):
        box = tk.LabelFrame(self.tab_export, text='توليد ملف حماية الأجور TXT لبنك الراجحي', bg='#111827', fg='white', font=('Segoe UI', 12, 'bold'), padx=18, pady=18)
        box.pack(fill='x', padx=10, pady=10)
        self.export_period = tk.StringVar(value=datetime.now().strftime('%Y-%m'))
        self.export_value_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        self.export_debit_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        self.export_ref = tk.StringVar(value=make_file_reference())
        items = [('اسم المسير',self.export_period),('تاريخ القيمة',self.export_value_date),('تاريخ الخصم',self.export_debit_date),('رقم مرجع الملف',self.export_ref)]
        for i,(label,var) in enumerate(items):
            tk.Label(box, text=label, bg='#111827', fg='#cbd5e1', font=('Segoe UI', 10, 'bold')).grid(row=0,column=i*2+1, padx=8, pady=8, sticky='e')
            e = self._entry(box, 20); e.configure(textvariable=var); e.grid(row=0,column=i*2, padx=8, pady=8, ipady=8)
        self._btn(box, 'توليد ملف TXT الآن', self.export_txt, '#16a34a').grid(row=1,column=0,columnspan=8,pady=16, sticky='ew')
        self.export_info = tk.Text(self.tab_export, height=18, bg='#020617', fg='#e5e7eb', relief='flat', font=('Consolas', 11), wrap='word')
        self.export_info.pack(fill='both', expand=True, padx=10, pady=10)

    def _build_settings_tab(self):
        box = tk.LabelFrame(self.tab_settings, text='إعدادات الشركة والحساب المشترك', bg='#111827', fg='white', font=('Segoe UI', 12, 'bold'), padx=18, pady=18)
        box.pack(fill='x', padx=10, pady=10)
        self.setting_fields = {}
        labels = [
            ('establishment_name','اسم المنشأة'), ('establishment_bank','بنك المنشأة'), ('establishment_id','رقم المنشأة في البنك'),
            ('establishment_account','حساب المنشأة IBAN'), ('currency','العملة'), ('mol_establishment_id','رقم منشأة وزارة العمل'),
            ('payment_description','وصف الدفع'), ('beneficiary_bank_code','كود بنك المستفيد'), ('db_path','مسار قاعدة البيانات المشتركة')
        ]
        for idx,(key,label) in enumerate(labels):
            r=idx; tk.Label(box,text=label,bg='#111827',fg='#cbd5e1',font=('Segoe UI',10,'bold')).grid(row=r,column=1,sticky='e',padx=6,pady=5)
            e=self._entry(box,70); e.insert(0, self.settings.get(key,'')); e.grid(row=r,column=0,sticky='ew',padx=6,pady=5,ipady=6)
            self.setting_fields[key]=e
        box.grid_columnconfigure(0, weight=1)
        act=tk.Frame(box,bg='#111827'); act.grid(row=len(labels),column=0,columnspan=2,sticky='w',pady=10)
        self._btn(act,'حفظ الإعدادات',self.save_settings_action,'#2563eb').pack(side='right',padx=5)
        self._btn(act,'اختيار قاعدة بيانات مشتركة',self.choose_db_path,'#9333ea').pack(side='right',padx=5)
        help_text = (
            'تشغيل أكثر من جهاز:\n'
            '1) على الجهاز الرئيسي اعمل فولدر مشترك Shared Folder.\n'
            '2) حط فيه ملف قاعدة البيانات rajhi_wages_shared.db.\n'
            '3) على كل جهاز افتح البرنامج واختر نفس مسار قاعدة البيانات من الإعدادات.\n'
            '4) لازم الأجهزة تكون على نفس الشبكة ونفس صلاحيات الوصول للفولدر.\n'
        )
        tk.Label(self.tab_settings,text=help_text,bg='#0f172a',fg='#fbbf24',font=('Segoe UI',12,'bold'),justify='right').pack(fill='x',padx=20,pady=20)

    def _build_history_tab(self):
        self.runs_tree = ttk.Treeview(self.tab_history, columns=('id','period','date','total','count','path'), show='headings')
        for c,t,w in [('id','#',60),('period','المسير',150),('date','تاريخ الإنشاء',180),('total','الإجمالي',120),('count','عدد العمال',100),('path','مسار الملف',520)]:
            self.runs_tree.heading(c,text=t); self.runs_tree.column(c,width=w,anchor='center')
        self.runs_tree.pack(fill='both',expand=True,padx=10,pady=10)

    def refresh_all(self):
        self.load_employees(); self.load_history(); self.update_stats()

    def update_stats(self):
        t=self.db.totals()
        self.stats_label.config(text=f"عدد العمال: {t['count']} | صافي الرواتب: {t['net']:,.2f} ريال")

    def load_employees(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in self.db.list_employees(self.search_var.get()):
            net = Decimal(str(r['basic_salary'])) + Decimal(str(r['housing_allowance'])) + Decimal(str(r['other_earnings'])) - Decimal(str(r['deductions']))
            self.tree.insert('', 'end', values=(r['id'], r['name'], r['national_id'], r['iban'], r['employee_type'], f"{r['basic_salary']:.2f}", f"{r['housing_allowance']:.2f}", f"{r['other_earnings']:.2f}", f"{r['deductions']:.2f}", f"{net:.2f}"))

    def load_history(self):
        for i in self.runs_tree.get_children(): self.runs_tree.delete(i)
        for r in self.db.list_runs():
            self.runs_tree.insert('', 'end', values=(r['id'],r['period_name'],r['created_at'],f"{r['total_amount']:.2f}",r['employees_count'],r['export_path']))

    def form_data(self):
        data={}
        for k,w in self.fields.items():
            data[k]=w.get() if not isinstance(w, tk.StringVar) else w.get()
        return data

    def set_form(self, row):
        self.clear_form(False); self.selected_id=row['id']
        for k,w in self.fields.items():
            val=str(row[k]) if k in row.keys() and row[k] is not None else ''
            if isinstance(w, tk.StringVar): w.set(val or 'غير سعودي')
            else: w.insert(0,val)

    def clear_form(self, reset=True):
        self.selected_id=None
        for k,w in self.fields.items():
            if isinstance(w, tk.StringVar): w.set('غير سعودي')
            else: w.delete(0,'end')

    def on_select_employee(self, event=None):
        sel=self.tree.selection()
        if not sel: return
        emp_id=int(self.tree.item(sel[0])['values'][0])
        row=self.db.get_employee(emp_id)
        if row: self.set_form(row)

    def save_employee(self):
        data=self.form_data()
        errs=validate_employee(data)
        if errs:
            messagebox.showerror('خطأ في البيانات','\n'.join(errs)); return
        self.db.upsert_employee(data)
        self.clear_form(); self.refresh_all(); messagebox.showinfo('تم','تم حفظ العامل بنجاح')

    def delete_selected(self):
        if not self.selected_id: messagebox.showwarning('تنبيه','اختر عامل أولًا'); return
        if messagebox.askyesno('تأكيد','هل تريد حذف العامل المحدد؟'):
            self.db.delete_employee(self.selected_id); self.clear_form(); self.refresh_all()

    def import_excel(self):
        path=filedialog.askopenfilename(title='اختر ملف Excel', filetypes=[('Excel files','*.xlsx *.xls'),('All files','*.*')])
        if not path: return
        try:
            employees, header_settings = read_rajhi_excel(path)
            if not employees:
                messagebox.showwarning('تنبيه','لم يتم العثور على عمال داخل الملف'); return
            for k,v in header_settings.items():
                if v and k in self.settings:
                    self.settings[k]=str(v)
                    if k in self.setting_fields:
                        self.setting_fields[k].delete(0,'end'); self.setting_fields[k].insert(0,str(v))
            save_settings(self.settings)
            for e in employees:
                self.db.upsert_employee(e)
            self.refresh_all()
            messagebox.showinfo('تم الاستيراد', f'تم استيراد/تحديث {len(employees)} عامل من ملف العميل')
        except Exception as e:
            messagebox.showerror('خطأ استيراد', str(e))

    def bulk_update_dialog(self):
        win=tk.Toplevel(self); win.title('تعديل جماعي'); win.geometry('420x260'); win.configure(bg='#111827'); win.grab_set()
        field=tk.StringVar(value='basic_salary'); mode=tk.StringVar(value='add'); amount=tk.StringVar(value='0')
        tk.Label(win,text='الحقل',bg='#111827',fg='white').pack(pady=5)
        ttk.Combobox(win,textvariable=field,values=['basic_salary','housing_allowance','other_earnings','deductions'],state='readonly').pack(pady=5)
        tk.Label(win,text='طريقة التعديل',bg='#111827',fg='white').pack(pady=5)
        ttk.Combobox(win,textvariable=mode,values=['set','add','percent'],state='readonly').pack(pady=5)
        tk.Label(win,text='القيمة',bg='#111827',fg='white').pack(pady=5)
        tk.Entry(win,textvariable=amount).pack(pady=5)
        def apply():
            self.db.bulk_update_salary(mode.get(), float(normalize_number(amount.get())), field.get()); self.refresh_all(); win.destroy(); messagebox.showinfo('تم','تم تطبيق التعديل الجماعي')
        self._btn(win,'تطبيق',apply,'#16a34a').pack(pady=12)

    def choose_db_path(self):
        path=filedialog.asksaveasfilename(title='اختر/أنشئ قاعدة البيانات المشتركة', defaultextension='.db', filetypes=[('SQLite DB','*.db'),('All files','*.*')])
        if path:
            self.setting_fields['db_path'].delete(0,'end'); self.setting_fields['db_path'].insert(0,path)

    def save_settings_action(self):
        for k,e in self.setting_fields.items(): self.settings[k]=e.get()
        save_settings(self.settings)
        messagebox.showinfo('تم','تم حفظ الإعدادات. إذا غيرت مسار قاعدة البيانات، أغلق البرنامج وافتحه مرة أخرى.')

    def export_txt(self):
        rows=self.db.list_employees('', True, 100000)
        if not rows:
            messagebox.showwarning('تنبيه','لا يوجد عمال للتصدير'); return
        missing=[k for k in ['establishment_account','establishment_id','mol_establishment_id'] if not self.settings.get(k)]
        if missing:
            if not messagebox.askyesno('تنبيه','يوجد إعدادات ناقصة للمنشأة. هل تريد المتابعة؟'):
                return
        default_name=f"RJHI_WAGES_{self.export_period.get().replace('-','')}_{self.export_ref.get()}.txt"
        path=filedialog.asksaveasfilename(title='حفظ ملف TXT', initialfile=default_name, defaultextension='.txt', filetypes=[('TXT','*.txt')])
        if not path: return
        try:
            # refresh settings from fields before export
            for k,e in getattr(self,'setting_fields',{}).items(): self.settings[k]=e.get()
            save_settings(self.settings)
            exporter=RajhiTxtExporter(self.settings)
            result=exporter.export(rows, path, self.export_value_date.get(), self.export_debit_date.get(), self.export_ref.get())
            self.db.save_payroll_run(self.export_period.get(), result['value_date'], result['debit_date'], result['file_reference'], path, result['employees'])
            self.refresh_all()
            self.export_info.delete('1.0','end')
            self.export_info.insert('end', f"تم توليد الملف بنجاح\nالمسار: {path}\nعدد العمال: {len(result['employees'])}\nعدد السطور: {result['lines']}\nمرجع الملف: {result['file_reference']}\n")
            messagebox.showinfo('تم','تم توليد ملف TXT بنجاح')
        except Exception as e:
            messagebox.showerror('خطأ التصدير', str(e))

    def destroy(self):
        try: self.db.close()
        except Exception: pass
        super().destroy()

def main():
    app=RajhiWagesApp()
    app.mainloop()
