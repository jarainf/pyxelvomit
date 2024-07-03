#!/usr/bin/env python3

import threading
import socket
import numpy as np
import sched
import time
import mmap

# config

width = 1280
height = 800
bpp = 4
framerate = 60
fb_dev = '/dev/fb0'
byteswap = False
invert = False
alpha = True
keep_screen = True
ipv6 = True
ipv6_only = False
port = 42024
grab_size = 2048
da_mode = True

# grab screen, make a copy since numpy doesn't create a writeable array
if keep_screen:
    with open('/dev/fb0', 'rb') as fb:
        vbuffer = np.copy(np.frombuffer(fb.read(),dtype=np.uint32))
        vbuffer.shape = (height, width)
        vbuffer.setflags(write = 1)
else:
    vbuffer = np.zeros((height, width), dtype=np.uint32)

# handle socket traffic with a generator
def handle_buffer(connection):
    buffer = connection.recv(grab_size).decode('ascii')
    buffering = True
    while buffering:
        if '\n' in buffer:
            (line, buffer) = buffer.split('\n', 1)
            yield line
        else:
            rest = connection.recv(grab_size).decode('ascii')
            if not rest:
                buffering = False
            else:
                buffer += rest
    if buffer and '\n' in buffer:
        yield buffer

# Thread for each connection
def handle_client(connection, address):
    # Offsets to use with 'OFFSET'
    offset_x = 0
    offset_y = 0
    while True:
        for data in handle_buffer(connection):
            # if nothing has been send, we break
            if not data:
                break
            # Slice first for more performance. TODO: Check Length?.
            # Added 'benefit': PX<x> <y> <value> is still valid, saving 1 byte per transmission.
            if data[:2] == 'OF':
                data_split = data[6:].split()
                if data_split[0].isnumeric() and data_split[1].isnumeric():
                    if int(data_split[0]) < width - 1 and int(data_split[1]) < height - 1:
                        offset_x = int(data_split[0])
                        offset_y = int(data_split[1])
            # answer to SIZE
            elif data[:2] == 'SI':
                connection.sendall('SIZE {} {}'.format(width, height))
            # Meat of the thing
            elif data[:2] == 'PX':
                data_split = data[2:].split()
                # sanity check
                #if data_split[0].isnumeric() and data_split[1].isnumeric():
                # apply offset and parse coordinates
                if da_mode:
                    coordinates = (int(data_split[1]) + offset_y) * width * bpp + (int(data_split[0]) + offset_x) * bpp
                else:
                    coordinates = (int(data_split[1]) + offset_y, int(data_split[0]) + offset_x)
                # sanity check again
                #if coordinates[0] < height and coordinates[1] < width:
                # not a sanity check, but compliance with GET PX
                if data_split[2]:
                    # alpha blending, works but might not be correct.
                    # TODO: Optimise since it's horribly slow, probably.
                    if alpha and len(data_split[2]) > 6:
                        if da_mode:
                            alpha_value = int(data_split[2][-2:], 16)
                            cur = bin(vbuffer[coordinates:coordinates + 3])[2:].rjust(24,'0')
                            r = int(alpha_value * int(data_split[2].rjust(6, '0')[0:2], 16) + int(cur[0:8],2) * (1 - alpha_value))
                            g = int(alpha_value * int(data_split[2].rjust(6, '0')[2:4], 16) + int(cur[8:16],2) * (1 - alpha_value))
                            b = int(alpha_value * int(data_split[2].rjust(6, '0')[4:6], 16) + int(cur[16:24],2) * (1 - alpha_value))
                            vbuffer[coordinates:coordinates + 3] = (r << 16) + (g << 8) + b
                        else:
                            alpha_value = int(data_split[2][-2:], 16)
                            cur = bin(vbuffer[coordinates])[2:].rjust(32,'0')
                            r = int(alpha_value * int(data_split[2].rjust(6, '0')[0:2], 16) + int(cur[0:8],2) * (1 - alpha_value))
                            g = int(alpha_value * int(data_split[2].rjust(6, '0')[2:4], 16) + int(cur[8:16],2) * (1 - alpha_value))
                            b = int(alpha_value * int(data_split[2].rjust(6, '0')[4:6], 16) + int(cur[16:24],2) * (1 - alpha_value))
                            vbuffer[coordinates] = (r << 16) + (g << 8) + b
                    else:
                        # receive data.
                        if da_mode:
                            if len(data_split[2]) < 6:
                                vbuffer[coordinates:coordinates + 3] = bytes.fromhex(data_split[2].rjust(6,'0'))[::-1]
                            else:
                                vbuffer[coordinates:coordinates + 3] = bytes.fromhex(data_split[2])[::-1]
                        else:
                            vbuffer[coordinates] = int(data_split[2], 16)
                else:
                    if da_mode:
                        connection.sendall(f'PX {data_split[0]} {data_split[1]} {vbuffer[coordinates[0] * width * bpp + coordinates[1] * bpp:coordinates[0] * width * bpp + coordinates[1] * bpp + 6]}')
                    else:
                        connection.sendall(f'PX {data_split[0]} {data_split[1]} {vbuffer[coordinates]}')

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

bind_address = ('', port)
if ipv6 and socket.has_dualstack_ipv6():
    if ipv6_only:
        s = socket.create_server(bind_address, family=socket.AF_INET6)
    else:
        s = socket.create_server(bind_address, family=socket.AF_INET6, dualstack_ipv6=True)
else:
    s = socket.create_server(bind_address, family=socket.AF_INET)
s.listen()

threads = list()

# If we're not in direct access mode
if not da_mode:
    x = threading.Thread(target=gen_vbuffer_scheduler, daemon=True)
    threads.append(x)
    x.start()
else:
    # Direct access mode. preferably with mmap. np.memmap performs worse.
    fb_file = open('/dev/fb0', 'wb+')
    vbuffer = mmap.mmap(fb_file.fileno(), length=1280*800*4)

while True:
    conn, addr = s.accept()
    x = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
    threads.append(x)
    x.start()

fb_file.close()
s.close()
