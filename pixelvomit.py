#!/usr/bin/env python3

import threading
import subprocess
import socket
import numpy as np
import sched
import time
import sys

width = 1280
height = 800
framerate = 60
fb_dev = '/dev/fb0'
byteswap = False
invert = False
alpha = True
keep_screen = True

if keep_screen:
    with open('/dev/fb0', 'rb') as fb:
        vbuffer = np.copy(np.frombuffer(fb.read(),dtype=np.uint32))
        vbuffer.shape = (800, 1280)
        vbuffer.setflags(write = 1)
else:
    vbuffer = np.zeros((height, width), dtype=np.uint32)

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
    offset_x = 0
    offset_y = 0
    while True:
        for data in handle_buffer(connection):
            if not data:
                break
            if data[:2] == 'OF':
                data_split = data[6:].split()
                if data_split[0].isnumeric() and data_split[1].isnumeric():
                    if int(data_split[0]) < width - 1 and int(data_split[1]) < height - 1:
                        offset_x = int(data_split[0])
                        offset_y = int(data_split[1])
            elif data[:2] == 'SI':
                connection.sendall('SIZE {} {}'.format(width, height))
            elif data[:2] == 'PX':
                data_split = data[2:].split()
                if data_split[0].isnumeric() and data_split[1].isnumeric():
                    coordinates = (int(data_split[1]) + offset_y, int(data_split[0]) + offset_x)
                    if coordinates[0] < height and coordinates[1] < width:
                        if data_split[2]:
                            if alpha and len(data_split[2]) == 8:
                                alpha_value = int(data_split[2][-2:], 16)
                                cur = bin(vbuffer[coordinates])[2:].rjust(32,'0')
                                r = int(alpha_value * int(data_split[2].rjust(6, '0')[0:2], 16) + int(cur[0:8],2) * (1 - alpha_value))
                                g = int(alpha_value * int(data_split[2].rjust(6, '0')[2:4], 16) + int(cur[8:16],2) * (1 - alpha_value))
                                b = int(alpha_value * int(data_split[2].rjust(6, '0')[4:6], 16) + int(cur[16:24],2) * (1 - alpha_value))
                                vbuffer[coordinates] = (r << 16) + (g << 8) + b
                            else:
                                vbuffer[coordinates] = int(data_split[2].rjust(6,'0')[:6], 16)
                        else:
                            connection.sendall(f'PX {data_split[0]} {data_split[1]} {vbuffer[data_split[0], data_split[1]]}')

def write_vbuffer(fb, scheduler):
    scheduler.enter(1/framerate, 1, write_vbuffer, (fb, scheduler,))
    if byteswap:
        fb.write(vbuffer.byteswap().tobytes())
        fb.seek(0)
        return
    if invert:
        fb.write(np.invert(vbuffer))
        fb.seek(0)
        return
    fb.write(vbuffer.tobytes())
    fb.seek(0)

def gen_vbuffer_scheduler():
    fb_file = open(fb_dev, 'wb')

    vbuffer_writer = sched.scheduler(time.time, time.sleep)
    vbuffer_writer.enter(1/framerate, 1, write_vbuffer, (fb_file, vbuffer_writer,))
    vbuffer_writer.run()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('0.0.0.0', 42024))
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
