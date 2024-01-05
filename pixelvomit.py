#!/usr/bin/env python3

import threading
import subprocess
import socket
import numpy as np
import sched
import time

width = 1280
height = 800
bpp = 4

vbuffer = np.zeros(width * height * bpp, dtype=np.uint8)

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
    while True:
        for data in handle_buffer(connection):
            if not data:
                break
            data_split = data.split()
            if data_split[0] == 'SIZE':
                connection.sendall('SIZE {} {}'.format(width, height)
            if data_split[0] == 'PX':
                if data_split[1].isnumeric() and data_split[2].isnumeric():
                    if int(data_split[1]) < 1280 and int(data_split[2]) < 800:
                        if data_split[3]:
                            data_split[3]=str(data_split[3]).rjust(6,'0')
                            vbuffer[int(data_split[2]) * width * bpp + int(data_split[1]) * bpp] = int(data_split[3][4:6], 16)
                            vbuffer[int(data_split[2]) * width * bpp + int(data_split[1]) * bpp + 1] = int(data_split[3][2:4], 16)
                            vbuffer[int(data_split[2]) * width * bpp + int(data_split[1]) * bpp + 2] = int(data_split[3][0:2], 16)
                            #vbuffer[int(data_split[2]) * width * bpp + int(data_split[1]) * bpp + 3] = int('FF', 16)
                        else:
                            connection.sendall('PX {} {} {}'.format(data_split[1], data_split[2], vbuffer[int(data_split[2]) * width * bpp + int(data_split[1]):int(data_split[2]) * width * bpp + int(data_split[1]) + 2]))





def write_vbuffer(fb, scheduler):
    scheduler.enter(1/60, 1, write_vbuffer, (fb, scheduler,))
    fb.write(vbuffer.tobytes())
    fb.seek(0)

def gen_vbuffer_scheduler():
    fb_file = open('/dev/fb0', 'wb')

    vbuffer_writer = sched.scheduler(time.time, time.sleep)
    vbuffer_writer.enter(1/60, 1, write_vbuffer, (fb_file, vbuffer_writer,))
    vbuffer_writer.run()

s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.bind(('0.0.0.0',42024))
s.listen()

threads = list()

x = threading.Thread(target=gen_vbuffer_scheduler, daemon=True)
threads.append(x)
x.start()

while True:
    conn, addr = s.accept()
    x = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
    threads.append(x)
    x.start()

fb_file.close()
s.close()
