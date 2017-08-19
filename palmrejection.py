#!/usr/local/bin/python

from __future__ import print_function



import subprocess
import re
import time
import sys
import atexit

import sys

if sys.version_info < (3, 0):
    try:
        FileNotFoundError
    except NameError:
        FileNotFoundError = IOError


# Configuration
touch_screen = ""
pen = ""
sleep_time_in_sec = 0.250


def find_device_name(udev_result, udev_device_flag):
    device_information = []

    found_i2c_device = False
    found_device_flag = False
    found_device_name = False

    device_name = ""

    for line in udev_result:

        # Found new device, process current device before adding a new one
        if line.startswith('P: ') and found_i2c_device:
            if found_device_flag:
                for line in device_information:
                    if "E: NAME=" in line:
                        found_device_name = True
                        device_name = line
                        break
            device_information.clear()
            found_i2c_device = False
            found_device_flag = False

        # Each device information starts with P in front in first line, touchscreen or wacom most likely will be connected via i2c
        if line.startswith('P: ') and "i2c" in line and not found_i2c_device:
            found_i2c_device = True
            device_information.append(line)
            continue

        if found_i2c_device:
            device_information.append(line)
            if udev_device_flag in line:
                found_device_flag = True

    if not found_device_name:
        print("Couldn't find device, please configure manually.")
        return None

    device_name = device_name.split(sep='=')[1]
    device_name = device_name.replace('"', '')
    return device_name

def auto_configure():
    udevadm_process = subprocess.Popen(['udevadm', 'info', '--export-db'], stdout=subprocess.PIPE)
    result = udevadm_process.communicate()[0].decode('UTF-8').splitlines()

    udev_touchscreen_flag = "ID_INPUT_TOUCHSCREEN=1"
    udev_wacom_flag = "ID_INPUT_TABLET=1"


    global touch_screen
    touch_screen = find_device_name(result, udev_touchscreen_flag)
    global pen
    pen = find_device_name(result, udev_wacom_flag)

    print("Autoconfiguration result: ")
    print("Touchscreen: ", touch_screen)
    print("Wacom pen: ", pen)

    if touch_screen != None and pen != None:
        return True
    return False

def find_id(device):
    """Extracts device id(s) from xinput. Parametr device is name of device.
        Returns a list of device id(s)"""
    result = ""
    try:
        p = subprocess.Popen(['xinput', '-list'], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(['grep', device], stdin=p.stdout,
                          stdout=subprocess.PIPE)
        p.stdout.close()
        result = p2.communicate()[0].decode('UTF-8')
        if not result:
            raise ValueError("[E1]: Couldn't find such device: {}. Recheck configuration.".format(touch_screen))

    except subprocess.CalledProcessError as e:
        print(e)
        sys.exit(1)
    except FileNotFoundError as e:
        print("[E2]: Check whether 'xinput' and/or 'grep' is installed")
        print(e)
        sys.exit(1)
    except ValueError as e:
        print(e)
        sys.exit(1)
    except:
        print("Unexpected error. Closing...")
        sys.exit(1)

    pattern = "\s+(id=\d+)"
    matches = re.findall(pattern, result)

    ids = [id.split("=")[1] for id in matches]

    print("Found {} device id(s) {}".format(device, ids))

    return ids



def pen_status(pen_ids):
    """Checks via xinput query-state whether pen is close to screen
        Returns list of statuses. There might be more than one status when pen does have eraser"""
    status = []
    result = ""
    pattern = "Absolute Proximity=(Out|In)"

    for id in pen_ids:
        cmd = ['xinput', 'query-state', id]
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            result = p.communicate()[0].decode('UTF-8')
            if not result:
                raise ValueError("[E4]: Can't find query state about pen with id: {}. Recheck configuration.".format(id))

            matches = re.findall(pattern, result)
            if not matches:
                raise ValueError("[E5]: Can't match proximity pattern")
            if "In" in matches:
                status.append(True)
            else:
                status.append(False)
        except subprocess.CalledProcessError as e:
            print(e)
            sys.exit(1)
        except FileNotFoundError as e:
            print("[E2]: Check whether 'xinput' is installed")
            print(e)
            sys.exit(1)
        except ValueError as e:
            print(e)
            sys.exit(1)
        except:
            print("Unexpected error. Closing...")
            sys.exit(1)

    return status

def disable_touchscreen(touch_screen_id):
    cmd = ['xinput', 'disable', touch_screen_id[0]]
    proc = subprocess.Popen(cmd)
    # print("Touchscreen disabled")

def enable_touchscreen(touch_screen_id):
    cmd = ['xinput', 'enable', touch_screen_id[0]]
    proc = subprocess.Popen(cmd)
    # print("Touchscreen enabled")



if __name__ == '__main__':

    if len(sys.argv) == 1:
        print("For auto configuration type: python ", sys.argv[0], "--auto")
        if not touch_screen and not pen:
            print("Empty configuration, autoconfiguration attempt.")
            auto_configure()
    elif len(sys.argv) == 2 and sys.argv[1]  == "--auto":
        auto_configure()

    devices_id = {touch_screen: find_id(touch_screen), pen: find_id(pen)}
    last_status = [False, False]
    while True:
        current_status = pen_status(devices_id[pen])
        try:
            if current_status == last_status:
                last_status = current_status
                time.sleep(sleep_time_in_sec)
                continue
            # If Pen or eraser is near disable touchscreen
            if any(current_status):
                disable_touchscreen(devices_id[touch_screen])
            elif not all(current_status): # Both pen and eraser is not near
                enable_touchscreen(devices_id[touch_screen])

            last_status = current_status
            time.sleep(sleep_time_in_sec)
        # Enables touchscreen at exception just in case, so we won't be left with disabled touchscreen
        except KeyboardInterrupt as e:
            print(e)
            enable_touchscreen(devices_id[touch_screen])
            sys.exit(1)
        except:
            print("Unexpected error. Closing...")
            enable_touchscreen(devices_id[touch_screen])
            sys.exit(1)
