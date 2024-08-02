import os
from datetime import datetime

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(logs_dir, exist_ok=True)

def log_error(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] ERROR: {message}\n"

    log_file_path = os.path.join(logs_dir, 'error_log.txt')

    with open(log_file_path, 'a', encoding='utf-8') as log_file:
        log_file.write(log_message)

    print(log_message.strip())  # Also print to the console

def log_debug(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] DEBUG: {message}\n"

    log_file_path = os.path.join(logs_dir, 'debug_log.txt')

    with open(log_file_path, 'a', encoding='utf-8') as log_file:
        log_file.write(log_message)

    print(log_message.strip())  # Also print to the console
