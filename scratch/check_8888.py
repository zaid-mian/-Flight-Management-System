import socket
import sys

def check_port_8888():
    print("Testing connection to localhost:8888...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    res = s.connect_ex(('127.0.0.1', 8888))
    if res == 0:
        print("SUCCESS: Port 8888 is open and accepting TCP connections!")
    else:
        print(f"FAILED: Connection to 127.0.0.1:8888 returned code {res}")
    s.close()

if __name__ == "__main__":
    check_port_8888()
