@echo off
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --name "RajhiWages" run.py
pause
