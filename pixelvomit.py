#!/usr/bin/env python3

import threading
import subprocess
import socket

buffer = []

width = 1280
height = 800
bpp = 4

def handle_buffer(connection):
    buffer = connection.recv(4096).decode('ascii')
    buffering = True
    while buffering:
        if '\n' in buffer:
            (line, buffer) = buffer.split('\n', 1)
            yield line + '\n'
        else:
            rest = connection.recv(4096).decode('ascii')
            if not rest:
                buffering = False
            else:
                buffer += rest
    if buffer and '\n' in buffer:
        yield buffer

def handle_client(connection, address):
    with open('/dev/fb0', 'wb') as fb_file:
        while True:
            for data in handle_buffer(connection):
                if not data:
                    break
                data_split = data.split()
                if data_split[0] == 'PX':
                    if data_split[1].isnumeric() and data_split[2].isnumeric():
                        if int(data_split[1]) < 1280 and int(data_split[2]) < 800:
                            if data_split[3]:
                                data_split[3]=str(data_split[3]).rjust(6,'0')
                                fb_file.seek(int(data_split[2]) * width * bpp + int(data_split[1]) * bpp)
                                fb_file.write(bytes.fromhex(data_split[3][4:6]) + bytes.fromhex(data_split[3][2:4]) + bytes.fromhex(data_split[3][0:2]) + bytes.fromhex('FF'))


s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.bind(('0.0.0.0',42024))
s.listen()

threads = list()

while True:
    conn, addr = s.accept()
    x = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
    threads.append(x)
    x.start()

s.close()
