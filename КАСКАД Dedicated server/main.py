# main.py
import sys
import os

# Добавляем путь к текущей папке, чтобы импорты работали
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server_gui import ServerGUI

if __name__ == "__main__":
    app = ServerGUI()
    app.mainloop()