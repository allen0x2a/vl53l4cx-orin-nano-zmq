#!/usr/bin/env python3
"""
VL53L4CX ZeroMQ Subscriber
"""

import zmq
import sys

TOPIC = "tof"

# ANSI Colors
CLR_G = "\033[92m" # Green
CLR_Y = "\033[93m" # Yellow
CLR_R = "\033[91m" # Red
CLR_0 = "\033[0m"  # Reset

ctx = zmq.Context()
sub = ctx.socket(zmq.SUB)
sub.connect("tcp://localhost:5555")
sub.setsockopt_string(zmq.SUBSCRIBE, TOPIC)

# Define column widths
W_DIST = 7
W_STAT = 7
W_SIG  = 10
W_BAR  = 40

# Create the header (Matching the data row widths)
header = f"{'DIST':<{W_DIST}} | {'STATUS':<{W_STAT}} | {'SIGNAL':<{W_SIG}} | {'VISUAL RANGE (1m)':<{W_BAR}}"
print(f"\nSubscribed to: {TOPIC}")
print(header)
print("-" * len(header))

try:
    while True:
        msg = sub.recv_string()
        parts = msg.split()
        
        # Parse
        dist   = int(parts[1])
        sig    = float(parts[2])
        status = int(parts[3])

        # Color logic
        if status == 0:
            color, status_txt = CLR_G, "OK"
        elif status in [1, 2]:
            color, status_txt = CLR_Y, "WEAK"
        else:
            color, status_txt = CLR_R, "ERR"

        # Build Bar
        bar_units = min(W_BAR, dist // 25)
        bar = "█" * bar_units
        spacer = " " * (W_BAR - bar_units)
        
        col_dist = f"{dist}mm".ljust(W_DIST)
        col_stat = f"{status_txt}".ljust(W_STAT)
        col_sig  = f"{sig:5.2f}".ljust(W_SIG)
        
        # Assemble the line with pipes OUTSIDE the color tags
        line = (
            f"\r{color}{col_dist}{CLR_0} | "
            f"{color}{col_stat}{CLR_0} | "
            f"{col_sig} | "
            f"{color}{bar}{spacer}{CLR_0} |"
        )
        
        sys.stdout.write(line)
        sys.stdout.flush()

except KeyboardInterrupt:
    print("\n\nStopping...")
finally:
    sub.close()
    ctx.term()
