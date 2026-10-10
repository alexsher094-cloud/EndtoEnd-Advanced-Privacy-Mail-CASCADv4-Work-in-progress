import subprocess
import sys
import os

# Определяем папку, где находится этот скрипт
base_dir = os.path.dirname(os.path.abspath(__file__))

# Папка с сервером (там лежит main.py сервера)
server_folder = os.path.join(base_dir, "КАСКАД Dedicated server")
# Папка с клиентом (текущая папка, где лежит main.py клиента)
client_folder = base_dir

# Запускаем сервер в своей директории
server = subprocess.Popen(
    [sys.executable, "main.py"],
    cwd=server_folder,
    shell=True
)

# Запускаем клиент в своей директории
client = subprocess.Popen(
    [sys.executable, "main.py"],
    cwd=client_folder,
    shell=True
)

try:
    server.wait()
    client.wait()
except KeyboardInterrupt:
    server.terminate()
    client.terminate()