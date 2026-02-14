#!/usr/bin/env python3
"""
VL53L4CX Python Driver + ZeroMQ Publisher
Optimized for: NVIDIA Jetson Orin Nano
Hardware: 4-wire I2C Breakout (VCC, GND, SDA, SCL)
"""

import time
import smbus2
import zmq
import sys

# Registers
REG_SOFT_RESET    = 0x0000
REG_GPIO_MUX      = 0x0030
REG_GPIO_STATUS   = 0x0031
REG_TIMEOUT_A     = 0x005E
REG_VCSEL_A       = 0x0060
REG_TIMEOUT_B     = 0x0061
REG_VCSEL_B       = 0x0063
REG_SIGMA_THRESH  = 0x0064
REG_MIN_COUNT     = 0x0066
REG_INT_CLEAR     = 0x0086
REG_MODE_START    = 0x0087
REG_RANGE_STATUS  = 0x0089
REG_SIGNAL_RATE   = 0x008E
REG_RANGE_MM      = 0x0096
REG_FW_STATUS     = 0x00E5
REG_MODEL_ID      = 0x010F

SENSOR_ID = 0xEBAA
TOPIC = "tof"

class VL53L4CX:
    def __init__(self, bus=1, address=0x29):
        """
        Initializes the driver for Jetson Orin Nano.
        Default I2C Bus: 1
        Default Address: 0x29
        """
        self.bus = bus
        self.addr = address
        self.i2c = None

    def init(self):
        try:
            self.i2c = smbus2.SMBus(self.bus)
        except PermissionError:
            print("Error: Permission denied accessing I2C. Try running with sudo.")
            return False

        # Soft Reset
        self._wb(REG_SOFT_RESET, 0x00)
        time.sleep(0.001)
        self._wb(REG_SOFT_RESET, 0x01)
        time.sleep(0.002)

        # Wait for Firmware Boot
        for _ in range(100):
            if self._rb(REG_FW_STATUS) & 0x01:
                break
            time.sleep(0.01)
        else:
            return False

        if self._rw(REG_MODEL_ID) != SENSOR_ID:
            return False

        # Static Configuration (Optimized for 4-wire I2C setups)
        self._wb(0x0008, 0x09)
        self._wb(REG_GPIO_MUX, 0x10)
        self._wb(REG_VCSEL_A, 0x0B)
        self._wb(REG_VCSEL_B, 0x09)
        self._ww(0x0044, 0x0A00)
        self._ww(REG_TIMEOUT_A, 0x00B1)
        self._ww(REG_TIMEOUT_B, 0x0099)
        self._ww(REG_SIGMA_THRESH, 0x00C0)
        self._ww(REG_MIN_COUNT, 0x0040)
        self._wd(0x006C, 0x00000BB8)
        
        return True

    def start(self):
        self._wb(REG_INT_CLEAR, 0x01)
        self._wb(REG_MODE_START, 0x40)

    def stop(self):
        self._wb(REG_MODE_START, 0x00)

    def read(self):
        """Returns (distance_mm, signal_rate, status) or None if no data ready."""
        if not (self._rb(REG_GPIO_STATUS) & 0x01):
            return None
        
        status = self._rb(REG_RANGE_STATUS) & 0x1F
        distance = self._rw(REG_RANGE_MM)
        signal = self._rw(REG_SIGNAL_RATE) / 128.0
        
        self._wb(REG_INT_CLEAR, 0x01)
        return (distance, signal, status)

    def close(self):
        if self.i2c:
            self.stop()
            self.i2c.close()

    # --- Low Level I2C Helpers ---
    def _wb(self, reg, val):
        self.i2c.write_i2c_block_data(self.addr, reg >> 8, [reg & 0xFF, val])

    def _ww(self, reg, val):
        self.i2c.write_i2c_block_data(self.addr, reg >> 8, [reg & 0xFF, val >> 8, val & 0xFF])

    def _wd(self, reg, val):
        self.i2c.write_i2c_block_data(self.addr, reg >> 8, [reg & 0xFF, (val >> 24) & 0xFF, (val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF])

    def _rb(self, reg):
        w = smbus2.i2c_msg.write(self.addr, [reg >> 8, reg & 0xFF])
        r = smbus2.i2c_msg.read(self.addr, 1)
        self.i2c.i2c_rdwr(w, r)
        return list(r)[0]

    def _rw(self, reg):
        w = smbus2.i2c_msg.write(self.addr, [reg >> 8, reg & 0xFF])
        r = smbus2.i2c_msg.read(self.addr, 2)
        self.i2c.i2c_rdwr(w, r)
        d = list(r)
        return (d[0] << 8) | d[1]

if __name__ == "__main__":
    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB)
    pub.bind("tcp://*:5555")
    
    sensor = VL53L4CX(bus=1) # Orin Nano default I2C bus 1
    
    if not sensor.init():
        print("Sensor initialization failed. Check wiring (VCC, GND, SDA, SCL).")
        sys.exit(1)
    
    print(f"Jetson Orin Nano VL53L4CX Publisher")
    print(f"Publishing to: tcp://*:5555 | Topic: {TOPIC}")
    
    sensor.start()
    
    try:
        while True:
            result = sensor.read()
            if result:
                dist, sig, status = result
                msg = f"{TOPIC} {dist} {sig:.2f} {status}"
                pub.send_string(msg)
                print(f"Dist: {dist:4}mm | Signal: {sig:6.2f} | Status: {status}", end="\r")
            
            time.sleep(0.01) # 100Hz max polling
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        sensor.close()
        pub.close()
        ctx.term()