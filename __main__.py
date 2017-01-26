#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
    Python-Raspberry-Contoll-Managment
    #######################################################

    Created by Ilja Grebel on 08.03.2016

    :| Copyright |: 2016, Ilja Grebel - igrebel@icloud.com
    :| license   |: GPLv3 (GNU General Public License Version 3)

    #######################################################
    TODO:
    - Web API
    - Set recording to pause - if its will work
    - Sys. configuration
    - Stop and start streaming
    - RTSP, RTMP and UDP
    - Record - JSON statistics
    - Network changes
    - Creating 'config.ini' if it is deleted
    - Image effects + params
    - Date - set time with POST request
    - If jpeg will be captured, creating a streaming folder with timestamp and save screenshot in this directory
    - Stream status and statistics
    - Overlays
    - jpgQuality
    - decoding
    - see recording and images from Web API
    - Playing stream/recording in Web API
    - GUI-APP for Linux, OS X, Windows
    - GUI-APP for iOS and Android
    - Save captures on USB or Raspberry Pi
    #######################################################
    :| Updates
    v1.01 - Some bug fixed
    v1.02 - Added more system information
    v1.03 - Added logging information, no print messages in console anymore
    v1.04 - Added Frame status while recording
    v1.05 - HD Video Processor OSD - Hex
    v1.06 - Upload BMP files
    v1.07 - New functions for V100 from Auvidea GmbH
    v1.08 - Added V100 HDMI Changes and debug messages
    v1.09 - Drag & Drop for HDMI Channels
    v1.10 - Set or Create new config Layout for V100

'''

# All print messages are only for debuggin/manual starting from console
# Set default encoding to UTF-8
# Flask, Flask-WTF, simplepam for Authentifaction
from flask import Flask, session, url_for, escape, request
from flask import json as flask_json
from simplepam import authenticate
from flask import render_template, redirect
from werkzeug.utils import secure_filename
import datetime
import time
import os
from threading import Lock
import picamera
import ConfigParser
import subprocess
# import netifaces
import collections
import RPi.GPIO as GPIO
# import psutil
import logging
from PIL import Image
import struct
from spi import *
import spi
import re

# import iptools


# create log file
logging.basicConfig(format=u'%(levelname)-8s [%(asctime)s] %(message)s', level=logging.DEBUG, filename=u'log.log')


app = Flask(__name__)
app.secret_key = os.urandom(24)


camera = None  # After starting, camera is offline
camlock = Lock()  # Needed to block access from multi responses
config = ConfigParser.RawConfigParser()
config.read('config.ini')
uptime = time.time()
firmware = 'v1.10'
version = 10
website = 'v1.10'
PIN_Number = ''
myrevision = ''
model_name = ''
record_dir = ''
img_dir = ''
_duration = ''


###################


# DEFAULT Configuration
default_video_fmt = '.h264'
default_img_fmt = '.jpeg'
default_width = 1920
default_heigth = 1080
default_framerate = 30
default_record_dir = ''
default_img_dir = ''
default_record_file = 'video'
default_img_file = 'image'
default_camera_effect = 'none'
default_annotate_text = ''


# Creating new config.ini if versions are different
def conf_version():
    config.read('config.ini')
    old_config = config.getint('INFO', 'version')
    if old_config < version:
        logging.info('Current config.ini version is %d (required %d)' % (old_config, version))
        logging.info('Created new config.ini version %d' % version)
        config.set('INFO', 'version', '%d' % version)
        config.set('ENCODER', 'video_fmt', '%s' % default_video_fmt)
        config.set('ENCODER', 'img_fmt', '%s' % default_img_fmt)
        config.set('ENCODER', 'width', '%d' % default_width)
        config.set('ENCODER', 'heigth', '%d' % default_heigth)
        config.set('ENCODER', 'framerate', '%d' % default_framerate)
        config.set('ENCODER', 'record_dir', '%s' % default_record_dir)
        config.set('ENCODER', 'img_dir', '%s' % default_img_dir)
        config.set('ENCODER', 'record_file', '%s' % default_record_file)
        config.set('ENCODER', 'img_file', '%s' % default_img_file)
        config.set('ENCODER', 'camera_effect', '%s' % default_camera_effect)
        config.set('ENCODER', 'camera_effect', '%s' % default_annotate_text)
        config.write(open('config.ini', 'w'))
    else:
        logging.info('No need to delete current config.ini version is %d (required %d)' % (old_config, version))
    return 'done'


# Set default configuration
@app.route('/default_conf', methods=['POST'])
def default_settings():
    if 'username' in session:
        logging.info("Setting default configuration")
        config.set('INFO', 'version', '%d' % version)
        config.set('ENCODER', 'video_fmt', '%s' % default_video_fmt)
        config.set('ENCODER', 'img_fmt', '%s' % default_img_fmt)
        config.set('ENCODER', 'width', '%s' % default_width)
        config.set('ENCODER', 'heigth', '%s' % default_heigth)
        config.set('ENCODER', 'framerate', '%s' % default_framerate)
        config.set('ENCODER', 'record_dir', '%s' % default_record_dir)
        config.set('ENCODER', 'img_dir', '%s' % default_img_dir)
        config.set('ENCODER', 'record_file', '%s' % default_record_file)
        config.set('ENCODER', 'img_file', '%s' % default_img_file)
        config.set('ENCODER', 'image_effect', '%s' % default_camera_effect)
        config.write(open('config.ini', 'w'))
        logging.info('Finished')
        d = collections.OrderedDict()
        d['status'] = 200
        d['version'] = version
        d['video_format'] = default_video_fmt
        d['width'] = default_width
        d['heigth'] = default_heigth
        d['framerate'] = default_framerate
        d['record_dir'] = default_record_dir
        d['record_file'] = default_record_file
        d['image_format'] = default_img_fmt
        d['image_dir'] = default_img_dir
        d['image_file'] = default_img_file
        d['image_effect'] = default_camera_effect
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
        logging.error("Not logged in")
        return render_template('login.html')


# GET/POST network configuration
@app.route('/network', methods=['GET', 'POST'])
def network():
    config.read('config.ini')
    interfaces = netifaces.interfaces()
    public_ip_address = []
    broadcast = []
    subnet = []
    hwaddr = []
    if 'username' in session:
        for interface in interfaces:
            # Only keep ethX interfaces.
            if not interface.startswith("eth0"):
                continue
            # Discard interfaces that are up but without any IPs.
            addrs = netifaces.ifaddresses(interface).get(netifaces.AF_INET)
            addrs1 = netifaces.ifaddresses(interface).get(netifaces.AF_LINK)
            if not (addrs and addrs1):
                continue
            bs = [addr.get("broadcast") for addr in addrs]
            ips = [addr.get("addr") for addr in addrs]
            mask = [addr.get("netmask") for addr in addrs]
            hw = [addr.get("addr") for addr in addrs1]
            try:
                public_ip_address.append(ips[0])
                broadcast.append(bs[0])
                subnet.append(mask[0])
                hwaddr.append(hw[0])
            except IndexError:
                pass
            if request.method == 'POST':
                # TODO write in config.ini
                return 'POST'
            d = collections.OrderedDict()
            d['ip_address'] = public_ip_address[0]
            d['subnet'] = subnet[0]
            d['mac'] = hwaddr[0]
            d['broadcast'] = broadcast[0]
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
        logging.error("Not logged in")
        return render_template('login.html')


# not worked yet
@app.route('/change_ip', methods=['POST'])
def change_ip():
    if 'username' in session:
        ipaddress = ''
        os.system("sudo ifconfig eth0 down")
        os.system("sudo ifconfig eth0 %s" % ipaddress)
        os.system("sudo ifconfig eth0 up")
        d = collections.OrderedDict()
        d['ip_address'] = ipaddress
        d['comment'] = 'IP Address was changed'
        logging.info("IP CHANGE %s" % ipaddress)
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
        logging.error("Not logged in")
        return render_template('login.html')


@app.route('/change_test', methods=['POST'])
def change_test():
    ipaddress = request.form['_ip_address_']
    os.system("sudo ifconfig eth0 down")
    os.system("sudo ifconfig eth0 %s" % ipaddress)
    os.system("sudo ifconfig eth0 up")
    d = collections.OrderedDict()
    d['ip_address'] = ipaddress
    d['comment'] = 'IP Address was changed'
    logging.info("IP CHANGE %s" % ipaddress)
    return flask_json.dumps(d, sort_keys=False, indent=True)


@app.route('/model', methods=['GET'])
def raspmodel():
    # Extract board revision from cpuinfo file
    global myrevision
    myrevision = "0000"
    try:
        f = open('/proc/cpuinfo', 'r')
        for line in f:
            if line[0:8] == 'Revision':
                length = len(line)
                myrevision = line[11:length - 1]
        f.close()
    except:
        myrevision = "0000"
    return 'Revision - %s' % myrevision


@app.route('/pin', methods=['GET'])
def pin():
    global PIN_Number
    # Pi 2 Model B
    if myrevision == 'a01041':
        PIN_Number = '21'
    elif myrevision == 'a21041':
        PIN_Number = '21'
    # Pi 3 Model B
    elif myrevision == 'a02082':
        PIN_Number = '21'
    elif myrevision == 'a22082':
        PIN_Number = '21'
    # Model B Revision 1.0
    elif myrevision == '0002':
        PIN_Number = '41'
    # Model B Revision 1.0 + ECN0001 (no fuses, D14 removed)
    elif myrevision == '0003':
        PIN_Number = '41'
    # Model B Revision 2.0
    elif myrevision == '0004' or '0005' or '0006':
        PIN_Number = '41'
    # Model A
    elif myrevision == '0007' or '0008' or '0009':
        PIN_Number = '41'
    # Model B Revision 2.0
    elif myrevision == '000d' or '000e' or '000f':
        PIN_Number = '41'
    # Model B+
    elif myrevision == '0010':
        PIN_Number = '41'
    # Compute Module
    elif myrevision == '0011':
        PIN_Number = '41'
    # Model A+
    elif myrevision == '0012':
        PIN_Number = '41'
    else:
        PIN_Number = '41'
    return 'Revision - %s and PIN %s' % (myrevision, PIN_Number)



@app.route('/raspname', methods=['GET'])
def raspiname():
    global model_name
    if myrevision == 'a01041' or 'a21041':
        model_name = 'Pi 2 Model B'
    elif myrevision == 'a02082' or 'a22082':
        model_name = 'Pi 3 Model B'
    elif myrevision == '0002':
        model_name = 'Model B Revision 1.0'
    elif myrevision == '0003':
        model_name = 'Model B Revision 1.0 + ECN0001'
    elif myrevision == '0004' or '0005' or '0006':
        model_name = 'Model B Revision 2.0'
    elif myrevision == '0007' or '0008' or '0009':
        model_name == 'Model A'
    elif myrevision == '000d' or '000e' or '000f':
        model_name = 'Model B Revision 2.0'
    elif myrevision == '0010':
        model_name = 'Model B+'
    elif myrevision == '0011':
        model_name = 'Compute Module'
    elif myrevision == '0012':
        model_name = 'Model A+'
    else:
        model_name = 'Raspberry Pi'
    return 'Model name - %s' % model_name


@app.route('/restart_gpio_test', methods=['POST'])  # need for testing
def rpiotest():
    if 'username' in session:
        logging.info("restarting gpio")
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_Number, GPIO.OUT)
        GPIO.output(PIN_Number, GPIO.LOW)
        GPIO.output(PIN_Number, GPIO.HIGH)
        d = collections.OrderedDict()
        d['status'] = 200
        d['comment'] = 'B101 (38126-2) has been restarted'
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
        logging.error('Not logged in')
        return render_template('login.html')


@app.route('/b101_test')
def rpib101():
    logging.info('restarting B101')
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_Number, GPIO.OUT)
    GPIO.output(PIN_Number, GPIO.LOW)
    GPIO.output(PIN_Number, GPIO.HIGH)
    d = collections.OrderedDict()
    d['status'] = 200
    d['comment'] = 'B101 (38126-2) has been restarted'
    return flask_json.dumps(d, sort_keys=False, indent=True)


# GET system info
@app.route('/system', methods=['GET'])
def system():
    if 'username' in session:
        hostname = subprocess.check_output('uname -n', shell=True).strip()
        linux = subprocess.check_output('uname -o', shell=True).strip()
        cpu_usage = psutil.cpu_percent()
        total_ram = psutil.virtual_memory()[0] / 1024 / 1024
        avaible_ram = psutil.virtual_memory()[1] / 1024 / 1024
        memory_used = psutil.virtual_memory()[3] / 1024 / 1024
        memory_free = psutil.virtual_memory()[4] / 1024 / 1024
        d = collections.OrderedDict()
        d['status'] = 200
        d['model'] = model_name
        d['revision'] = myrevision
        d['hostname'] = hostname
        d['firmware'] = firmware
        d['version'] = website
        d['hardware'] = '38126-2'  # hardcode
        d['linux'] = linux
        d['cpu'] = '%s ' % cpu_usage + '%'
        d['totalMemory'] = '%s MB' % total_ram
        d['avaibleMemory'] = '%s MB' % avaible_ram
        d['memoryUsed'] = '%s MB' % memory_used
        d['memoryFree'] = '%s MB' % memory_free
        d['systemUptime'] = time.clock()
        d['uptime'] = time.time() - uptime
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
        logging.error("Not logged in")
        return render_template('login.html')


# Encoder config
@app.route('/enc_config', methods=['GET', 'POST'])
def enc_config():
    config.read('config.ini')
    if 'username' in session:
        if request.method == 'GET':
            d = collections.OrderedDict()
            d['status'] = 200
            d['width'] = config.getint('ENCODER', 'width')
            d['heigth'] = config.getint('ENCODER', 'heigth')
            d['record_dir'] = config.get('ENCODER', 'record_dir')
            d['record_file'] = config.get('ENCODER', 'record_file')
            d['video_format'] = config.get('ENCODER', 'video_fmt')
            d['image_dir'] = config.get('ENCODER', 'img_dir')
            d['image_file'] = config.get('ENCODER', 'img_file')
            d['image_format'] = config.get('ENCODER', 'img_fmt')
            d['camera_effect'] = config.get('ENCODER', 'camera_effect')
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            _width = request.form['_width']
            _heigth = request.form['_heigth']
            _video_fmt = request.form['_video_fmt']
            _image_fmt = request.form['_image_fmt']
            _record_file = request.form['_record_file']
            _img_file = request.form['_img_file']
            _camera_effect = request.form['_camera_effect']
            _annotate_text = request.form['_annotate_text']
            config.set('ENCODER', 'width', '%s' % _width)
            config.set('ENCODER', 'heigth', '%s' % _heigth)
            config.set('ENCODER', 'video_fmt', '%s' % _video_fmt)
            config.set('ENCODER', 'img_fmt', '%s' % _image_fmt)
            config.set('ENCODER', 'record_file', '%s' % _record_file)
            config.set('ENCODER', 'img_file', '%s' % _img_file)
            config.set('ENCODER', 'camera_effect', '%s' % _camera_effect)
            config.set('ENCODER', 'annotate_text', '%s' % _annotate_text)
            config.write(open('config.ini', 'w'))
            d = collections.OrderedDict()
            d['status'] = 200
            d['width'] = config.getint('ENCODER', 'width')
            d['heigth'] = config.getint('ENCODER', 'heigth')
            d['record_dir'] = config.get('ENCODER', 'record_dir')
            d['record_file'] = config.get('ENCODER', 'record_file')
            d['video_format'] = config.get('ENCODER', 'video_fmt')
            d['image_dir'] = config.get('ENCODER', 'img_dir')
            d['image_file'] = config.get('ENCODER', 'img_file')
            d['image_format'] = config.get('ENCODER', 'img_fmt')
            d['camera_effect'] = config.get('ENCODER', 'camera_effect')
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
        logging.error("Not logged in")
        return render_template('login.html')


# Date
@app.route('/date', methods=['GET', 'POST'])
def date():
    if 'username' in session:
        now = datetime.datetime.now()
        if request.method == 'GET':
            d = collections.OrderedDict()
            d['status'] = 200
            d['isoTime'] = now.isoformat()
            d['year'] = now.year
            d['month'] = now.month
            d['day'] = now.day
            d['hour'] = now.hour
            d['minute'] = now.minute
            d['second'] = now.second
            d['weekday'] = now.weekday()
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            _year = request.form['_year']
            _month = request.form['_month']
            _day = request.form['_day']
            _hour = request.form['_hour']
            _minute = request.form['_minute']
            _second = request.form['_second']
            os.system('date -s "%s %s %s %s:%s:%s"' % (_day, _month, _year, _hour, _minute, _second))
            d = collections.OrderedDict()
            d['status'] = 200
            d['isoTime'] = now.isoformat()
            d['year'] = now.year
            d['month'] = now.month
            d['day'] = now.day
            d['hour'] = now.hour
            d['minute'] = now.minute
            d['second'] = now.second
            d['weekday'] = now.weekday()
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
        logging.error("Not logged in")
        return render_template('login.html')


# Timestamp
def timestamp():
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d_%H:%M:%S')
    return st


# TODO - Change path
@app.route('/path', methods=['POST', 'GET'])
def path():
    current_path = os.system('pwd')
    if 'username' in session:
        if request.method == 'GET':
            if current_path == '/home/pi/Recordings':
                d = collections.OrderedDict()
                d['status'] = 200
                d['path'] = current_path
                d['comment'] = 'saving on RPi'
            # current_path = os.system('pwd')
            else:
                d = collections.OrderedDict()
                d['status'] = 200
                d['path'] = current_path
                d['comment'] = 'savin on USB'
                return 0
            d = collections.OrderedDict()
            d['status'] = 200
            return flask_json.dumps(d, sort_keys=False, indent=True)


# Make directory
def mkdir():
    global record_dir, img_dir
    now = timestamp()
    record_dir = './record-%s/' % now
    img_dir = record_dir + 'images/'
    os.mkdir(record_dir)
    os.mkdir(img_dir)
    os.system("sudo chown -R pi:pi %s" % record_dir)
    logging.info('Creating directiories %s' % (record_dir + img_dir))
    return record_dir + img_dir


# Set GPIO4 to 0 and then to 1 (Restart B101)
@app.route('/restart_b101', methods=['POST'])
def reset_gpio():
    if 'username' in session:
        os.system('echo "0" > /sys/class/gpio/gpio4/value')
        os.system('echo "1" > /sys/class/gpio/gpio4/value')
        d = collections.OrderedDict()
        d['status'] = 200
        d['comment'] = 'B101 (38126-2) has been restarted'
        return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error("Not logged in")
    return render_template('login.html')


# START PREVIEW
@app.route('/start_preview', methods=['POST'])
def preview():
    config.read('config.ini')
    global camera
    with camlock:
        if 'username' in session:
            if camera:
                d = collections.OrderedDict()
                d['status'] = 200
                d['preview'] = 'started'
                d['comment'] = 'preview already started'
                return flask_json.dumps(d, sort_keys=False, indent=False)
            reset_gpio()
            camera = picamera.PiCamera()
            camera.resolution = (config.getint('ENCODER', 'width'), config.getint('ENCODER', 'heigth'))
            camera.framerate = config.getint('ENCODER', 'framerate')
            camera.image_effect = config.get('ENCODER', 'camera_effect')
            camera.annotate_text = config.get('ENCODER', 'annotate_text')
            camera.start_preview()
            d = collections.OrderedDict()
            d['status'] = 200
            d['preview'] = 'starting'
            d['resolution'] = '%s, %s' % (config.getint('ENCODER', 'width'), config.getint('ENCODER', 'heigth'))
            d['annotate_text'] = config.get('ENCODER', 'annotate_text')
            logging.info("start preview")
            return flask_json.dumps(d, sort_keys=False, indent=True)
        logging.error("Not logged in")
        return render_template('login.html')


# STOP PREVIEW
@app.route('/stop_preview', methods=['POST'])
def stop_preview():
    global camera
    with camlock:
        if 'username' in session:
            if not camera:
                d = collections.OrderedDict()
                d['status'] = 200
                d['preview'] = 'stopped'
                d['comment'] = 'already stopped'
                return flask_json.dumps(d, sort_keys=False, indent=True)
            camera.close()
            camera = None
            d = collections.OrderedDict()
            d['status'] = 200
            d['preview'] = 'stopping'
            logging.info("stop preview")
            return flask_json.dumps(d, sort_keys=False, indent=True)
        logging.error("Not logged in")
        return render_template('login.html')


# START RECORD
@app.route('/start_record', methods=['POST'])
def start_capture():
    config.read('config.ini')
    global _duration
    _duration = time.time()
    global camera
    with camlock:
        if 'username' in session:
            if camera:
                d = collections.OrderedDict()
                d['status'] = 200
                d['record'] = 'recording'
                d['comment'] = 'already started'
                logging.info("recording already started")
                return flask_json.dumps(d, sort_keys=False, indent=True)
            # reset_gpio()
            camera = picamera.PiCamera()
            camera.resolution = (config.getint('ENCODER', 'width'), config.getint('ENCODER', 'heigth'))
            camera.framerate = config.getint('ENCODER', 'framerate')
            camera.image_effect = config.get('ENCODER', 'camera_effect')
            camera.annotate_text = config.get('ENCODER', 'annotate_text')
            camera.start_preview()
            mkdir()
            camera.start_recording(
                record_dir + config.get('ENCODER', 'record_File') + config.get('ENCODER', 'video_fmt'))
            d = collections.OrderedDict()
            d['status'] = 200
            d['record'] = 'recording'
            d['record_dir'] = record_dir
            d['record_file'] = config.get('ENCODER', 'record_file') + config.get('ENCODER', 'video_fmt')
            d['comment'] = 'recording started'
            logging.info("recording has been started")
            return flask_json.dumps(d, sort_keys=False, indent=True)
        logging.error("Not logged in")
        return render_template('login.html')


# record status
@app.route('/status', methods=['GET'])
def rec_status():
    global camera
    with camlock:
        if 'username' in session:
            if camera:
                d = collections.OrderedDict()
                d['status'] = 200
                d['record'] = 'recording'
                d['file'] = record_dir + config.get('ENCODER', 'record_File') + config.get('ENCODER', 'video_fmt')
                d['resolution'] = '%s, %s' % (config.getint('ENCODER', 'width'), config.getint('ENCODER', 'heigth'))
                d['duration'] = '%d' % (time.time() - _duration)
                d['frame'] = camera._get_frame()
                return flask_json.dumps(d, sort_keys=False, indent=True)
            d = collections.OrderedDict()
            d['status'] = 200
            d['record'] = 'stopped'
            d['comment'] = 'no video connected'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        logging.error("Not logged in")
        return render_template('login.html')


@app.route('/status_preview', methods=['GET'])
def pre_status():
    global camera
    with camlock:
        if 'username' in session:
            if camera:
                d = collections.OrderedDict()
                d['status'] = 200
                d['preview'] = 'started'
                return flask_json.dumps(d, sort_keys=False, indent=True)
            d = collections.OrderedDict()
            d['status'] = 200
            d['preview'] = 'stopped'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        logging.error("Not logged in")
        return render_template('login.html')


# STOP RECODING
@app.route('/stop_record', methods=['POST'])
def stop_capture():
    print 'record stop'
    global camera
    with camlock:
        if 'username' in session:
            if not camera:
                d = collections.OrderedDict()
                d['status'] = 200
                d['record'] = 'stopped'
                d['comment'] = 'already stopped'
                return flask_json.dumps(d, sort_keys=False, indent=True)
            logging.info("stop recording")
            camera.stop_recording()
            camera.close()
            camera = None
            rec_video_to_mp4()
            d = collections.OrderedDict()
            d['status'] = 200
            d['record'] = 'stopped'
            d['comment'] = 'recording stopped'
            d['next'] = '.h264 to .mp4'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        logging.error("Not logged in")
        return render_template('login.html')


# START STREAM
@app.route('/start_stream', methods=['POST'])
def start_stream():
    global camera
    if 'username' in session:
        with camlock:
            logging.info("start stream")
            reset_gpio()
            os.system(
                'raspivid -t 0 -fps 25 -hf -b 2000000 -o - | ffmpeg -i - -vcodec copy -an -r 30 -g 30 -bufsize 2000000 -pix_fmt yuv420p -f mpegts udp://@239.239.2.1:1234')
            d = collections.OrderedDict()
            d['status'] = 200
            d['stream'] = 'streaming'
            d['startTime'] = time.time()
            d[
                'link'] = 'udp://@239.239.2.1:1234'  # udp://@239.239.2.1:1234 \ in future: rtsp, rtmp and udp (if it will working)
        return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error("Not logged in")
    return render_template('login.html')


@app.route('/stop_stream', methods=['POST'])
def stop_stream():
    global camera
    if 'username' in session:
        os.system('kill all ffmpeg')
        d = collections.OrderedDict()
        d['status'] = 200
        d['stream'] = 'stopped'
        return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error("Not logged in")
    return render_template('login.html')


# MP4
def rec_video_to_mp4():
    print 'video to .mp4'
    cmd = ('ffmpeg -i %s -vcodec copy -an -f mp4 %s.mp4') % (
        record_dir + config.get('ENCODER', 'record_File') + config.get('ENCODER', 'video_fmt'),
        config.get('ENCODER', 'record_dir') + config.get('ENCODER', 'record_File'))
    os.system(cmd)
    d = collections.OrderedDict()
    d['status'] = 200
    d['process'] = '.h264 to .mp4'
    d['h264File'] = record_dir + config.get('ENCODER', 'record_File') + config.get('ENCODER', 'video_fmt')
    d['mp4File'] = '%s %s.mp4'
    return 'Creating .MP4 File'


# FOR COUNTER
def static_var(varname, value):
    def decorate(func):
        setattr(func, varname, value)
        return func

    return decorate


# SCREENSHOT
@app.route('/screenshot', methods=['POST'])
@static_var("counter", 0)
def screenshot():
    with camlock:
        screenshot.counter += 1
        if 'username' in session:
            if not camera:
                d = collections.OrderedDict()
                d['status'] = 200
                d['comment'] = 'not recording or streaming'
                return flask_json.dumps(d, sort_keys=False, indent=True)
            camera.capture((img_dir + '%s-' + config.get('ENCODER', 'img_file') + config.get('ENCODER', 'img_fmt')) % (
                screenshot.counter), use_video_port=True)
            d = collections.OrderedDict()
            d['status'] = 200
            d['name'] = '%d-%s%s' % (
                screenshot.counter, config.get('ENCODER', 'img_file'), config.get('ENCODER', 'img_fmt'))
            d['path'] = img_dir
            logging.info('screenshot %d-%s%s captured' % (
                screenshot.counter, config.get('ENCODER', 'img_file'), config.get('ENCODER', 'img_fmt')))
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            logging.error("Not logged in")
            return render_template('login.html')


#################   WEB API   ##################
@app.route('/')
def index():
    if 'username' in session:
        logging.info('Logged in as "%s"' % escape(session['username']))
        return render_template('index.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/login.html', methods=['POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if authenticate(str(username), str(password)):
            session['username'] = request.form['username']
            return redirect(url_for('index'))
        else:
            return render_template('login.html')
    return render_template('login.html')


@app.route('/index.html')
def indexhtml():
    if 'username' in session:
        return render_template('index.html')
    logging.error('Not logged in')
    return render_template('login.html')


# System info
@app.route('/system.html')
def system_info():
    if 'username' in session:
        return render_template('system.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/settings.html')
def settings():
    if 'username' in session:
        return render_template('settings.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/faq.html')
def faq():
    if 'username' in session:
        return render_template('faq.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/preview.html')
def previewhtml():
    if 'username' in session:
        return render_template('preview.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/spi_tty.html')
def upload_html():
    if 'username' in session:
        return render_template('spi_tty.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/hdmi_channel.html')
def hdmi_channel():
    if 'username' in session:
        return render_template('hdmi_channel.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/osd.html')
def _osd_html():
    if 'username' in session:
        return render_template('osd.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/v100.html')
def _v100_html():
    if 'username' in session:
        return render_template('v100.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/dragndrop.html')
def _dragndrop():
    if 'username' in session:
        return render_template('dragndrop.html')
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    return redirect(url_for('index'))


######## UART/TTY #########
import serial

@app.route("/activate_tty", methods=['POST'])
def activate_tty():
    # os.system("sudo systemctl stop serial-getty@ttyAMA0.service")
    if myrevision == 'a01041':
        os.system("sudo systemctl stop serial-getty@ttyAMA0.service")
        d = collections.OrderedDict()
        d['status'] = 200
        d['action'] = '/dev/ttyAMA0 - is activated'
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
        os.system("sudo systemctl stop serial-getty@ttyS0.service")
        d = collections.OrderedDict()
        d['status'] = 200
        d['action'] = '/dev/ttyS0 - is activated'
        return flask_json.dumps(d, sort_keys=False, indent=True)


@app.route("/send_tty", methods=["POST"])
def send_tty():
    if 'username' in session:
        _serial = request.form['_serial']
        cmmd = '%s\r' % _serial
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = cmmd.replace('\r', '')
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = cmmd.replace('\r', '')
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


# TODO
'''
@app.route("/hdmi_settings_chnn_1", methods=['POST'])
def hdmi_settings_chnn_1():
    if 'username' in session:
        _radio_in = request.form.getlist['_radio_in']
        _radio_out = request.form.getlist['_radio_out']
        return 'Done'
    logging.error('Not logged in')
    return render_template('login.html')
'''


############# HDMI CH1 SETTINGS #############
@app.route('/chn1_out_swap', methods=['POST'])
def chn1_out_swap():
    if 'username' in session:
        cmmd = 'swap\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'HDMI Channels has beed swaped'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'HDMI Channels has beed swaped'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_out_full', methods=['POST'])
def _chn1_out_full():
    if 'username' in session:
        cmmd = 'full\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii', 'strict'))
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Channel 1 displayed in full size'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii', 'strict'))
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] =  'Channel 1 displayed in full size'
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_out_sbs', methods=['POST'])
def _chn1_out_sbs():
    if 'username' in session:
        cmmd = 'sbs\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Side by side'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Side by side'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_out_pip', methods=['POST'])
def chn1_out_pip():
    if 'username' in session:
        cmmd = 'pip\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Picture in picture'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Picture in picture'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_out_pip_tl', methods=['POST'])
def _chn1_out_pip_tl():
    if 'username' in session:
        cmmd = 'pip tl\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Top Left'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Top Left'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_out_pip_tr', methods=['POST'])
def _chn1_out_pip_tr():
    if 'username' in session:
        cmmd = 'pip tr\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Top Right'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Top Right'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_out_pip_bl', methods=['POST'])
def _chn1_out_pip_bl():
    if 'username' in session:
        cmmd = 'pip bl\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Bottom Left'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Bottom Left'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_out_pip_br', methods=['POST'])
def chn1_out_pip_br():
    if 'username' in session:
        cmmd = 'pip br\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Bottom Right'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['comment'] = 'Buttom Right'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_out_manual', methods=['POST'])
def _chn1_out_manual():
    if 'username' in session:
        _chn1_out_manual_param1 = 1
        _chn1_out_manual_param2 = request.form['_chn1_out_manual_param2']
        _chn1_out_manual_param3 = request.form['_chn1_out_manual_param3']
        _chn1_out_manual_param4 = request.form['_chn1_out_manual_param4']
        _chn1_out_manual_param5 = request.form['_chn1_out_manual_param5']
        cmmd = 'o %s %s %s %s %s\r' % (_chn1_out_manual_param1, int(_chn1_out_manual_param2), int(_chn1_out_manual_param3), int(_chn1_out_manual_param4), int(_chn1_out_manual_param5))
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_chn1_out_manual_param2)
            d['hsize'] = int(_chn1_out_manual_param3)
            d['vstart'] = int(_chn1_out_manual_param4)
            d['vsize'] = int(_chn1_out_manual_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_chn1_out_manual_param2)
            d['hsize'] = int(_chn1_out_manual_param3)
            d['vstart'] = int(_chn1_out_manual_param4)
            d['vsize'] = int(_chn1_out_manual_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_in_fill', methods=['POST'])
def _chn1_in_fill():
    if 'username' in session:
        cmmd = 'fill 1\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Fill'
            d['comment'] = 'Completely fills the output window'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Fill'
            d['comment'] = 'Completely fills the output window'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_in_fit', methods=['POST'])
def _chn1_in_fit():
    if 'username' in session:
        cmmd = 'fit 1\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Fit'
            d['comment'] = 'Preserves the original aspect ratio by adding black bars (letterbox / pillarbox)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Fit'
            d['comment'] = 'Preserves the original aspect ratio by adding black bars (letterbox / pillarbox)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_in_none', methods=['POST'])
def _chn1_in_none():
    if 'username' in session:
        cmmd = 'none 1\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'None'
            d['comment'] = 'Leaves the the size of the input video untouched'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'None'
            d['comment'] = 'Leaves the the size of the input video untouched'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn1_in_zoom', methods=['POST'])
def _chn1_in_zoom():
    if 'username' in session:
        cmmd = 'zoom 1\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Zoom'
            d['comment'] = 'Cuts off parts of the video while preserving the original aspect ratio'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Zoom'
            d['comment'] = 'Cuts off parts of the video while preserving the original aspect ratio'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return []


@app.route('/chn1_in_manual', methods=['POST'])
def _chn1_in_manual():
    if 'username' in session:
        _chn1_in_manual_param1 = 1
        _chn1_in_manual_param2 = request.form['_chn1_in_manual_param2']
        _chn1_in_manual_param3 = request.form['_chn1_in_manual_param3']
        _chn1_in_manual_param4 = request.form['_chn1_in_manual_param4']
        _chn1_in_manual_param5 = request.form['_chn1_in_manual_param5']
        cmmd = 'i %s %s %s %s %s\r' % (_chn1_in_manual_param1, int(_chn1_in_manual_param2), int(_chn1_in_manual_param3), int(_chn1_in_manual_param4), int(_chn1_in_manual_param5))
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_chn1_in_manual_param2)
            d['hsize'] = int(_chn1_in_manual_param3)
            d['vstart'] = int(_chn1_in_manual_param4)
            d['vsize'] = int(_chn1_in_manual_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_chn1_in_manual_param2)
            d['hsize'] = int(_chn1_in_manual_param3)
            d['vstart'] = int(_chn1_in_manual_param4)
            d['vsize'] = int(_chn1_in_manual_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


#######################
############# HDMI CH2 SETTINGS #############
@app.route('/chn2_out_full', methods=['POST'])
def _chn2_out_full():
    if 'username' in session:
        cmmd = 'full\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Channel 1 displayed full size'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Channel 1 displayed full size'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_out_sbs', methods=['POST'])
def _chn2_out_sbs():
    if 'username' in session:
        cmmd = 'sbs\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Side by side'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Side by side'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_out_pip', methods=['POST'])
def chn2_out_pip():
    if 'username' in session:
        cmmd = 'pip\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Picture in picture'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Picture in picture'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_out_pip_tl', methods=['POST'])
def _chn2_out_pip_tl():
    if 'username' in session:
        cmmd = 'pip tl\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Top Left'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Top Left'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_out_pip_tr', methods=['POST'])
def _chn2_out_pip_tr():
    if 'username' in session:
        cmmd = 'pip tr\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Top Right'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Top Right'
            return flask_json.dumps(d, sort_keys=False, indent=1)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_out_pip_bl', methods=['POST'])
def _chn2_out_pip_bl():
    if 'username' in session:
        cmmd = 'pip bl\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Buttom Left'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Buttom Left'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_out_pip_br', methods=['POST'])
def chn2_out_pip_br():
    if 'username' in session:
        cmmd = 'pip br\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', sort_keys=False, indent=True)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Buttom Right'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', sort_keys=False, indent=True)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['aciton'] = 'Butoom Right'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_out_manual', methods=['POST'])
def _chn2_out_manual():
    if 'username' in session:
        _chn2_out_manual_param1 = 2
        _chn2_out_manual_param2 = request.form['_chn2_out_manual_param2']
        _chn2_out_manual_param3 = request.form['_chn2_out_manual_param3']
        _chn2_out_manual_param4 = request.form['_chn2_out_manual_param4']
        _chn2_out_manual_param5 = request.form['_chn2_out_manual_param5']
        cmmd = 'o %s %s %s %s %s\r' % (
            _chn2_out_manual_param1, int(_chn2_out_manual_param2), int(_chn2_out_manual_param3),
            int(_chn2_out_manual_param4), int(_chn2_out_manual_param5))
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_chn2_out_manual_param2)
            d['hsize'] = int(_chn2_out_manual_param3)
            d['vstart'] = int(_chn2_out_manual_param4)
            d['vsize'] = int(_chn2_out_manual_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_chn2_out_manual_param2)
            d['hsize'] = int(_chn2_out_manual_param3)
            d['vstart'] = int(_chn2_out_manual_param4)
            d['vsize'] = int(_chn2_out_manual_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_in_fill', methods=['POST'])
def _chn2_in_fill():
    if 'username' in session:
        cmmd = 'fill 2\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Fill'
            d['comment'] = 'Completely fills the output window'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Fill'
            d['comment'] = 'Completely fills the output window'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_in_fit', methods=['POST'])
def _chn2_in_fit():
    if 'username' in session:
        cmmd = 'fit 2\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Fit'
            d['comment'] = 'Preserves the original aspect ratio by adding black bars (letterbox / pillarbox)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Fit'
            d['comment'] = 'Preserves the original aspect ratio by adding black bars (letterbox / pillarbox)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_in_none', methods=['POST'])
def _chn2_in_none():
    if 'username' in session:
        cmmd = 'none 2\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'None'
            d['comment'] = 'Leaves the the size of the input video untouched'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'None'
            d['comment'] = 'Leaves the the size of the input video untouched'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_in_zoom', methods=['POST'])
def _chn2_in_zoom():
    if 'username' in session:
        cmmd = 'zoom 2\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Zoom'
            d['comment'] = 'Cuts off parts of the video while preserving the original aspect ratio'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Zoom'
            d['comment'] = 'Cuts off parts of the video while preserving the original aspect ratio'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/chn2_in_manual', methods=['POST'])
def _chn2_in_manual():
    if 'username' in session:
        _chn2_in_manual_param1 = 2
        _chn2_in_manual_param2 = request.form['_chn2_in_manual_param2']
        _chn2_in_manual_param3 = request.form['_chn2_in_manual_param3']
        _chn2_in_manual_param4 = request.form['_chn2_in_manual_param4']
        _chn2_in_manual_param5 = request.form['_chn2_in_manual_param5']
        cmmd = 'i %s %s %s %s %s\r' % (
            _chn2_in_manual_param1, int(_chn2_in_manual_param2), int(_chn2_in_manual_param3),
            int(_chn2_in_manual_param4),
            int(_chn2_in_manual_param5))
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_chn2_in_manual_param2)
            d['hsize'] = int(_chn2_in_manual_param3)
            d['vstart'] = int(_chn2_in_manual_param4)
            d['vsize'] = int(_chn2_in_manual_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_chn2_in_manual_param2)
            d['hsize'] = int(_chn2_in_manual_param3)
            d['vstart'] = int(_chn2_in_manual_param4)
            d['vsize'] = int(_chn2_in_manual_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


########################

@app.route('/output_timing-576p50', methods=['POST'])
def _output_timing_576p50():
    if 'username' in session:
        cmmd = 'c 17\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 576p50'
            d['comment'] = '720x576 p (50 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 576p50'
            d['comment'] = '720x576 p (50 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/output_timing-720p50', methods=['POST'])
def _output_timing_720p50():
    if 'username' in session:
        cmmd = 'c 19\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 720p50'
            d['comment'] = '1280x720 p (50 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 720p50'
            d['comment'] = '1280x720 p (50 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/output_timing-720p60', methods=['POST'])
def _output_timing_720p60():
    if 'username' in session:
        cmmd = 'c 4\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 720p60'
            d['comment'] = '1280x720 p (60 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 720p60'
            d['comment'] = '1280x720 p (60 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/output_timing-1080p24', methods=['POST'])
def _output_timing_1080p24():
    if 'username' in session:
        cmmd = 'c 32\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p24'
            d['comment'] = '1920x1080 p (24 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p24'
            d['comment'] = '1920x1080 p (24 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/output_timing-1080p25', methods=['POST'])
def _output_timing_1080p25():
    if 'username' in session:
        cmmd = 'c 33\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p25'
            d['comment'] = '1920x1080 p (25 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p25'
            d['comment'] = '1920x1080 p (25 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/output_timing-1080p30', methods=['POST'])
def _output_timing_1080p30():
    if 'username' in session:
        cmmd = 'c 34\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p30'
            d['comment'] = '1920x1080 p (30 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p30'
            d['comment'] = '1920x1080 p (30 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/output_timing-1080p50', methods=['POST'])
def _output_timing_1080p50():
    if 'username' in session:
        cmmd = 'c 31\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p50'
            d['comment'] = '1920x1080 p (50 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p50'
            d['comment'] = '1920x1080 p (50 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/output_timing-1080p60', methods=['POST'])
def _output_timing_1080p60():
    if 'username' in session:
        cmmd = 'c 16\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p60'
            d['comment'] = '1920x1080 p (60 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'Resolution edited to 1080p60'
            d['comment'] = '1920x1080 p (60 Hz)'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


########################
@app.route('/osd_off', methods=['POST'])
def _osd_off():
    if 'username' in session:
        cmmd = 'osd off\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'OSD disabled'
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['action'] = 'OSD disabled'
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


@app.route('/paint', methods=['POST'])
def _osd_paint():
    if 'username' in session:
        _osd_paint_param1 = request.form['_osd_paint_param1']
        _osd_paint_param2 = request.form['_osd_paint_param2']
        _osd_paint_param3 = request.form['_osd_paint_param3']
        _osd_paint_param4 = request.form['_osd_paint_param4']
        _osd_paint_param5 = request.form['_osd_paint_param5']
        cmmd = 'paint %s %s %s %s %s\r' % (
            int(_osd_paint_param1), int(_osd_paint_param2), int(_osd_paint_param3), int(_osd_paint_param4),
            int(_osd_paint_param5))
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_osd_paint_param1)
            d['hsize'] = int(_osd_paint_param2)
            d['vstart'] = int(_osd_paint_param3)
            d['vsize'] = int(_osd_paint_param4)
            d['color'] = int(_osd_paint_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode())
            d = collections.OrderedDict()
            d['status'] = 200
            d['hstart'] = int(_osd_paint_param1)
            d['hsize'] = int(_osd_paint_param2)
            d['vstart'] = int(_osd_paint_param3)
            d['vsize'] = int(_osd_paint_param4)
            d['color'] = int(_osd_paint_param5)
            return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return render_template('login.html')


########### OSD Controll ###############
@app.route('/rmem_memory', methods=['POST'])
def _rmem_memory():
    if 'username' in session:
        cmmd = 'rmem\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('rmem', '').replace('>', '')
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('rmem', '').replace('>', '')
    return 'nothing'


@app.route('/v_memory', methods=['POST'])
def _v_memory():
    if 'username' in session:
        cmmd = 'v\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('v', '').replace('>', '')
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('v', '').replace('>', '')
    return 'nothing'


#@app.route('/h_memory', methods=['POST'])
#def _h_memory():
 #   if 'username' in session:
  #      cmmd = 'h\r'
   #     port.write(cmmd.encode('ascii'))
    #    output = port.read(9999)
     #   print output  # debug
      #  return output
   # return 'nothing'


@app.route('/t_memory', methods=['POST'])
def _t_memory():
    if 'username' in session:
        cmmd = 't\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('t', '').replace('>', '')
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('t', '').replace('>', '')
    return 'nothing'


@app.route('/td_memory', methods=['POST'])
def _td_memory():
    if 'username' in session:
        cmmd = 'td\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('td', '').replace('>', '')
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('td', '').replace('>', '')
    return 'nothing'


@app.route('/r_0x36_memory', methods=['POST'])
def _r_0x36_memory():
    if 'username' in session:
        cmmd = 'r 0x36\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('r 0x36', '').replace('>', '')
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('r 0x36', '').replace('>', '')
    return 'nothing'


@app.route('/r_0x37_memory', methods=['POST'])
def _r_0x37_memory():
    if 'username' in session:
        cmmd = 'r 0x37\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('r 0x37', '').replace('>', '')
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('r 0x37', '').replace('>', '')
    return 'nothing'


@app.route('/l_memory', methods=['POST'])
def _l_memory():
    if 'username' in session:
        cmmd = 'l\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output  # debug
            return output.replace('l', '').replace('>', '')
        else:
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output
            return output.replace('l', '').replace('>', '')
    return 'nothing'


'''
def how_many(s):
    numbers = [int(item) for item in s.split()[1:]]
    return 1 if len(numbers) == 1 else numbers[1] - numbers[0] + 1
'''


@app.route('/b_memory', methods=['POST'])
def _b_memory():
    if 'username' in session:
        user_input = request.form['_user_input']
        cmmd = 'b %s\r' % user_input
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
        # output = port.read(491 * how_many(user_input))
        # output = port.write(489 * how_many(cmmd))
            output = port.read(9999)
            print output  # debug
            return output.replace(cmmd, '').replace('>', '')
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output
            return output.replace(cmmd, '').replace('>', '')
    return 'nothing'


############### DRAG and DROP output Channel 1 and Channel 2 Settings ##############


def _dd_output_resolution():
    if 'username' in session:
        cmmd = 't\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output
            return output.replace('t', '').replace('>', '')
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cmmd.encode('ascii'))
            output = port.read(9999)
            print output
            return output.replace('t', '').replace('>', '')
    return 'nothing'


resolution = ''


@app.route('/dd_output_channels', methods=['POST'])
def _dd_output_channels():
    if 'username' in session:
        channel = request.form['channel']
        top = request.form['top']
        left = request.form['left']
        width = request.form['width']
        height = request.form['height']
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            if '1920' == resolution:
                cmmd = 'o %s %s %s %s %s\r' % (channel, int(float(left) * 2), int(float(width) * 2), int(float(top) * 2), int(float(height) * 2))
                port.write(cmmd.encode('ascii'))
                return cmmd
            elif '1280' == resolution:
                cmmd = 'o %s %s %s %s %s\r' % (channel, int(float(left) * 1.33333333), int(float(width) * 1.33333333), int(float(top) * 1.33333333), int(float(height)* 1.33333333))
                port.write(cmmd.encode('ascii'))
                return cmmd
            elif '720' == resolution:
                cmmd = 'o %s %s %s %s %s\r' % (channel, int(float(left) * 1.06666667), int(float(width) * 1.06666667), int(float(top) * 1.06666667), int(float(height)* 1.06666667))
                port.write(cmmd.encode('ascii'))
                return cmmd
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            if '1920' == resolution:
                cmmd = 'o %s %s %s %s %s\r' % (channel, int(float(left) * 2), int(float(width) * 2), int(float(top) * 2), int(float(height) * 2))
                port.write(cmmd.encode('ascii'))
                return cmmd
            elif '1280' == resolution:
                cmmd = 'o %s %s %s %s %s\r' % (channel, int(float(left) * 1.33333333), int(float(width) * 1.33333333), int(float(top) * 1.33333333), int(float(height)* 1.33333333))
                port.write(cmmd.encode('ascii'))
                return cmmd
            elif '720' == resolution:
                cmmd = 'o %s %s %s %s %s\r' % (channel, int(float(left) * 1.06666667), int(float(width) * 1.06666667), int(float(top) * 1.06666667), int(float(height)* 1.06666667))
                port.write(cmmd.encode('ascii'))
                return cmmd
    return 'False'


@app.route('/get_win_output', methods=['GET'])
def _win_output():
    global resolution
    if 'username' in session:
        cde = 'win\r'
        if myrevision == ' a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cde.encode('ascii'))
            result = re.findall(r'(\d+)', port.read(9999))
            resolution = result[1]
            print resolution
            return 'Done'
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cde.encode('ascii'))
            result = re.findall(r'(\d+)', port.read(9999))
            resolution = result[1]
            print resolution
            return 'Done'
    return 'False'


@app.route('/get_win1_output_1', methods=['GET'])
def _win1_output_1():
    if 'username' in session:
        cde = 'win 1\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cde.encode('ascii'))
            results = re.findall(r'(\d+)', port.read(9999))
            if resolution == '1920':
                left = int(float(results[1])) / 2
                width = int(float(results[2])) / 2
                top = int(float(results[3])) / 2
                height = int(float(results[4])) / 2
                d = collections.OrderedDict()
                d['status'] = 200
                d['channel'] = 1
                d['left'] = int(float(left))
                d['width'] = int(float(width))
                d['top'] = int(float(top))
                d['height'] = int(float(height))
                print d
                return flask_json.dumps(d, sort_keys=False, indent=True)
            elif resolution == '1280':
                left = int(float(results[1])) / 1.33333333
                width = int(float(results[2])) / 1.33333333
                top = int(float(results[3])) / 1.33333333
                height = int(float(results[4])) / 1.33333333
                d = collections.OrderedDict()
                d['status'] = 200
                d['channel'] = 1
                d['left'] = int(float(left))
                d['width'] = int(float(width))
                d['top'] = int(float(top))
                d['height'] = int(float(height))
                print d
                return flask_json.dumps(d, sort_keys=False, indent=True)
            elif resolution == '720':
                left = int(float(results[1])) / 1.06666667
                width = int(float(results[2])) / 1.06666667
                top = int(float(results[3])) / 1.06666667
                height = int(float(results[4])) / 1.06666667
                d = collections.OrderedDict()
                d['status'] = 200
                d['channel'] = 1
                d['left'] = int(float(left))
                d['width'] = int(float(width))
                d['top'] = int(float(top))
                d['height'] = int(float(height))
                print d
                return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cde.encode('ascii'))
            results = re.findall(r'(\d+)', port.read(9999))
            if resolution == '1920':
                left = int(float(results[1])) / 2
                width = int(float(results[2])) / 2
                top = int(float(results[3])) / 2
                height = int(float(results[4])) / 2
                d = collections.OrderedDict()
                d['status'] = 200
                d['channel'] = 1
                d['left'] = int(float(left))
                d['width'] = int(float(width))
                d['top'] = int(float(top))
                d['height'] = int(float(height))
                print d
                return flask_json.dumps(d, sort_keys=False, indent=True)
            elif resolution == '1280':
                left = int(float(results[1])) / 1.33333333
                width = int(float(results[2])) / 1.33333333
                top = int(float(results[3])) / 1.33333333
                height = int(float(results[4])) / 1.33333333
                d = collections.OrderedDict()
                d['status'] = 200
                d['channel'] = 1
                d['left'] = int(float(left))
                d['width'] = int(float(width))
                d['top'] = int(float(top))
                d['height'] = int(float(height))
                print d
                return flask_json.dumps(d, sort_keys=False, indent=True)
            elif resolution == '720':
                left = int(float(results[1])) / 1.06666667
                width = int(float(results[2])) / 1.06666667
                top = int(float(results[3])) / 1.06666667
                height = int(float(results[4])) / 1.06666667
                d = collections.OrderedDict()
                d['status'] = 200
                d['channel'] = 1
                d['left'] = int(float(left))
                d['width'] = int(float(width))
                d['top'] = int(float(top))
                d['height'] = int(float(height))
                print d
                return flask_json.dumps(d, sort_keys=False, indent=True)
    return 'false'


@app.route('/get_win2_output_2', methods=['GET'])
def _win2_output_2():
    if 'username' in session:
        cde = 'win 2\r'
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write(cde.encode('ascii'))
            results = re.findall(r'(\d+)', port.read(9999))
            if results != '2':
                if resolution == '1920':
                    left = int(float(results[1])) / 2
                    width = int(float(results[2])) / 2
                    top = int(float(results[3])) / 2
                    height = int(float(results[4])) / 2
                    d = collections.OrderedDict()
                    d['status'] = 200
                    d['channel'] = 2
                    d['left'] = int(float(left))
                    d['width'] = int(float(width))
                    d['top'] = int(float(top))
                    d['height'] = int(float(height))
                    print d
                    return flask_json.dumps(d, sort_keys=False, indent=True)
                elif resolution == '1280':
                    left = int(float(results[1])) / 1.33333333
                    width = int(float(results[2])) / 1.33333333
                    top = int(float(results[3])) / 1.33333333
                    height = int(float(results[4])) / 1.33333333
                    d = collections.OrderedDict()
                    d['status'] = 200
                    d['channel'] = 2
                    d['left'] = int(float(left))
                    d['width'] = int(float(width))
                    d['top'] = int(float(top))
                    d['height'] = int(float(height))
                    print d
                    return flask_json.dumps(d, sort_keys=False, indent=True)
                elif resolution == '720':
                    left = int(float(results[1])) / 1.06666667
                    width = int(float(results[2])) / 1.06666667
                    top = int(float(results[3])) / 1.06666667
                    height = int(float(results[4])) / 1.06666667
                    d = collections.OrderedDict()
                    d['status'] = 200
                    d['channel'] = 2
                    d['left'] = int(float(left))
                    d['width'] = int(float(width))
                    d['top'] = int(float(top))
                    d['height'] = int(float(height))
                    print d
                    return flask_json.dumps(d, sort_keys=False, indent=True)
            return 'no info'
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write(cde.encode('ascii'))
            results = re.findall(r'(\d+)', port.read(9999))
            if results != '2':
                if resolution == '1920':
                    left = int(float(results[1])) / 2
                    width = int(float(results[2])) / 2
                    top = int(float(results[3])) / 2
                    height = int(float(results[4])) / 2
                    d = collections.OrderedDict()
                    d['status'] = 200
                    d['channel'] = 2
                    d['left'] = int(float(left))
                    d['width'] = int(float(width))
                    d['top'] = int(float(top))
                    d['height'] = int(float(height))
                    print d
                    return flask_json.dumps(d, sort_keys=False, indent=True)
                elif resolution == '1280':
                    left = int(float(results[1])) / 1.33333333
                    width = int(float(results[2])) / 1.33333333
                    top = int(float(results[3])) / 1.33333333
                    height = int(float(results[4])) / 1.33333333
                    d = collections.OrderedDict()
                    d['status'] = 200
                    d['channel'] = 2
                    d['left'] = int(float(left))
                    d['width'] = int(float(width))
                    d['top'] = int(float(top))
                    d['height'] = int(float(height))
                    print d
                    return flask_json.dumps(d, sort_keys=False, indent=True)
                elif resolution == '720':
                    left = int(float(results[1])) / 1.06666667
                    width = int(float(results[2])) / 1.06666667
                    top = int(float(results[3])) / 1.06666667
                    height = int(float(results[4])) / 1.06666667
                    d = collections.OrderedDict()
                    d['status'] = 200
                    d['channel'] = 2
                    d['left'] = int(float(left))
                    d['width'] = int(float(width))
                    d['top'] = int(float(top))
                    d['height'] = int(float(height))
                    print d
                    return flask_json.dumps(d, sort_keys=False, indent=True)
            return 'no info'
    return 'false'


@app.route('/lmem_settings', methods=['POST'])
def _lmem_settings():
    if 'username' in session:
        number = request.form['_number']
        cde = 'lmem %s\r' % number
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, )
            port.write(cde.encode('ascii'))
            return 'lmem %s - set' % number
    return 'false'


def _lmem_how_many():
    if 'username' in session:
        list = []
        return 'so und so viele gibt es'
    return 'false'


######## V100 configuration file ########
import spidev
import serial


i = 0
ii = 0
j = 0
rdtgo = 0
rbusy = 0
rempty = 0
data = 0


SOH = '\x01'
ETX = '\x03'
EOT = '\x04'
ACK = '\x06'
NACK = '\x15'


def rdram():
    if 'username' in session:
        global j
        wad = 0x6A00000
        tx = [0x4f] * 1025
        tx = list(tx)
        f = open('config/conf' + str(j), 'w')
        j = j + 1
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 10000000
        for i in range(0, 2816):
            wad1 = wad & 0xff
            wad2 = (wad >> 8) & 0xff
            wad3 = (wad >> 16) & 0xff
            wad4 = (wad >> 24) & 0xff
            spi.xfer([0x80, 0x00])
            spi.xfer([0xC7, wad1, 0xC8, wad2, 0xC9, wad3, 0xCA, wad4])
            rdt = spi.xfer([0x50, 0xFF])
            rdtgo = (rdt[1] | 0x01)
            spi.xfer([0xD0, rdtgo])
            while True:
                rbusy = spi.xfer([0x50, 0xFF])
                if (rbusy[1] & 0x08) != 1:
                    break
            spi.xfer([0xD0, (rbusy[1] & 0xFE)])
            spi.xfer([0x80, 0x40])
            data = spi.xfer2(tx)
            del data[0]
            newFileByteArray = bytearray(data)
            f.write(newFileByteArray)
            wad = wad + 1024
        spi.xfer([0x80, 0x00, 0xC7, 0x00, 0xC8, 0x00, 0xC9, 0x00, 0xCA, 0x00])
        f.close()
    return 'False'


@app.route('/new_conf', methods=['POST'])
def new_conf():
    if 'username' in session:
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write('\x0e')
            port.readline()
            port.write('rdc\r')
            rx = port.read()
            while rx != EOT:
                if rx == ETX:
                    print "ACK"
                    rdram()
                    port.write(ACK)
                    rx = port.read()
                else:
                    print "CANCEL"
                    port.write('\x19')
                    return 'CANCEL'
            print "EOT"
            port.write('\x19')
            return 'CANCEL'
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write('\x0e')
            port.readline()
            port.write('rdc\r')
            rx = port.read()
            while rx != EOT:
                if rx == ETX:
                    print "ACK"
                    rdram()
                    port.write(ACK)
                    rx = port.read()
                else:
                    print "CANCEL"
                    port.write('\x19')
                    return 'CANCEL'
            print "EOT"
            port.write('\x19')
            return 'CANCEL'
    return 'False'


def wrram():
    if 'username' in session:
        global j
        f = open('config/conf' + str(j), 'rb')
        j = j + 1
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 10000000
        spi.xfer([0x80, 0x00])
        spi.xfer([0xCB, 0x00, 0xCC, 0x00, 0xCD, 0xA0, 0xCE, 0x06])
        rdt = spi.xfer([0x50, 0xFF])
        rdtgo = (rdt[1] | 0x01)
        spi.xfer([0xD0, rdtgo])
        while True:
            rbusy = spi.xfer([0x50, 0xFF])
            if (rbusy[1] & 0x08) != 1:
                break
        spi.xfer([0xD0, (rbusy[1] & 0xFE)])
        spi.xfer([0x80, 0x40])
        for i in range(0, 2816):
            tx = list(f.read(1024))
            tx = [ord(n) for n in tx]
            tx.insert(0, 0xCF)
            spi.xfer(tx)
        spi.xfer([0x80, 0x00, 0xCB, 0x00, 0xCC, 0x00, 0xCD, 0x00, 0xCE, 0x00])
        f.close()
    return 'False'


@app.route('/set_conf', methods=['POST'])
def read_conf():
    if 'username' in session:
        if myrevision == 'a01041':
            port = serial.Serial('/dev/ttyAMA0', baudrate=115800, timeout=1)
            port.write('\x0e')
            port.readline()
            port.write('wdc\r')
            rx = port.read()
            while rx != EOT:
                if rx == ETX:
                    wrram()
                    print 'ACK'
                    port.write(ACK)
                    rx = port.read()
                else:
                    print 'CANCEL'
                    port.write('\x19')
                    return 'CANCEL'
            print 'EOT'
            port.write('\x19')
            return 'DONE'
        else:
            port = serial.Serial('/dev/ttyS0', baudrate=115800, timeout=1)
            port.write('\x0e')
            port.readline()
            port.write('wdc\r')
            rx = port.read()
            while rx != EOT:
                if rx == ETX:
                    wrram()
                    print 'ACK'
                    port.write(ACK)
                    rx = port.read()
                else:
                    print 'CANCEL'
                    port.write('\x19')
                    return 'CANCEL'
            print 'EOT'
            port.write('\x19')
            return 'DONE'
    return 'False'


'''
@app.route('/osd_enable', methods=['POST'])
def _osd_enable():
    if 'username' in session:
        _osd_enable_param1 = request.form['_osd_enable_param1']
        _osd_enable_param2 = request.form['_osd_enable_param2']
        _osd_enable_param3 = request.form['_osd_enable_param3']
        _osd_enable_param4 = request.form['_osd_enable_param4']
        _osd_enable_param5 = request.form['_osd_enable_param5']
        _osd_enable_param6 = request.form['_osd_enable_param6']
        cmmd = 'osd %s %s %s %s %s %s\r' % (int(_osd_enable_param1), int(_osd_enable_param2), int(_osd_enable_param3), int(_osd_enable_param4), int(_osd_enable_param5), int(_osd_enable_param6))
        port.write(cmmd.encode('ascii', 'strict'))
        return []
    logging.error('Not logged in')
    return render_template('login.html')
'''
######## SPI ###########
'''
#TODO SPI Read - not finisched yet
spi = spidev.SpiDev()
spi.open(0,0)

def spi_read():
    resp = spi.xfer2([0x80, 0x02, 0x00, 0xFF, 0x01, 0xFF, 0x02, 0xFF, 0x03, 0xFF, 0x04, 0xFF, 0x05, 0xFF, 0x06, 0xFF, 0x07, 0xFF, 0x08, 0xFF, 0x09, 0xFF, 0x0A, 0xFF, 0x0B, 0xFF, 0x0C, 0xFF, 0x0D, 0xFF, 0x0E, 0xFF, 0x0F, 0xFF])
    print hex(resp[3])
    print hex(resp[5])
    print hex(resp[7])
    print hex(resp[9])
    print hex(resp[11])
    print hex(resp[13])
    print hex(resp[15])
    print hex(resp[17])
    print hex(resp[19])
    print hex(resp[21])
    print hex(resp[23])
    print hex(resp[25])
    print hex(resp[27])
    print hex(resp[29])
    print hex(resp[31])
    print hex(resp[33])
    return []
'''


spi_x = SPI("/dev/spidev0.0")
spi_x.mode = SPI.MODE_0
spi_x.bits_per_word = 8
spi_x.speed = 5000000


UPLOAD_FOLDER = '/home/pi/uploads/'
ALLOWED_EXTENSIONS = set(['bmp'])
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_filename(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['POST'])
def upload_image():
    if 'username' in session:
        if request.method == 'POST':
            if 'file' not in request.files:
                print('No file part')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                print('No selected file')
                return redirect(request.url)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.mkdir(app.config['UPLOAD_FOLDER'])
                os.system("sudo chown pi:pi -R %s" % app.config['UPLOAD_FOLDER'])
            if file and allowed_filename(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                return render_template('spi_tty.html')
    logging.error('Not logged in')
    return 'false'


path = ''


@app.route('/color_palett', methods=['GET'])
def color_palett():
    if 'username' in session:
        img = Image.open(path, 'r')
        img.load()
        color = img.getpalette()
        d = collections.OrderedDict()
        d['status'] = 200
        d['color_palette'] = color
        # d['palettGreen'] = []
        # d['palettBlue'] = []
    return flask_json.dumps(d, sort_keys=False, indent=True)


@app.route('/image_list', methods=['GET'])
def image_list():
    if 'username' in session:
        d = collections.OrderedDict()
        d['status'] = 200
        d['files'] = os.listdir(app.config['UPLOAD_FOLDER'])
        return flask_json.dumps(d, sort_keys=False, indent=True)
    logging.error('Not logged in')
    return


def chunks(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i + n]


@app.route('/spi_read', methods=['GET'])
def spi_read():
    spi_x.transfer([0x80, 0x00, 0xCB, 0x00, 0xCC, 0x00, 0xCD, 0xA0, 0xCE, 0x06])
    return


@app.route('/spi_send', methods=['POST'])
def spi_send():
    if 'username' in session:
        # load picture
        global path
        _filename = request.form['_filename']
        path = UPLOAD_FOLDER + _filename
        img = Image.open(path, 'r')
        img.load()
        width = img.size[0]
        heigth = img.size[1]
        pixel_bytes = list(img.getdata())
        color_palett = img.getpalette()

        # send color palette
        spi_x.transfer([0x80, 0x03])
        spi_x.transfer([0x80, 0x03, 0x9B, 0x00])
        spi_x.transfer([0x80, 0x03])
        color_address = [0x80, 0x43, 0x9C]
        spi_x.transfer(color_address + color_palett)

        # send picture bytes
        spi_x.transfer([0x80, 0x00])
        picb = ([0x80, 0x00])
        # address in new version: 0x06A00000 \ old: 0x00000003
        pic = ([0xCB, 0x00, 0xCC, 0x00, 0xCD, 0xA0, 0xCE,
                0x06])  # 0xCB, 0x00, 0xCC, 0x00, 0xCD, 0xA0, 0xCE, 0x06
        spi_x.transfer(picb + pic)
        for chunk in chunks(pixel_bytes, 4000):  # send every 4000 lines of bytes
            spi_x.transfer([0x80, 0x00])
            byte = ([0x80, 0x40, 0xCF])
            spi_x.transfer(byte + chunk)

        spi_x.transfer([0x80, 0x03])
            # address in new version: 0x06A00000 \ old: 0x00000003
        spi_x.transfer([0x80, 0x03, 0x96, 0x00])  # 00
        spi_x.transfer([0x80, 0x03, 0x97, 0x00])  # 00
        spi_x.transfer([0x80, 0x03, 0x98, 0xA0])  # A0
        spi_x.transfer([0x80, 0x03, 0x99, 0x06])  # 06

        osd_memory = [0x80, 0x03, 0x9A]
        value1 = width / 128
        send1 = osd_memory + [value1]
        spi_x.transfer(send1)

        # picture position heigth
        _osd_heigth = request.form["_osd_heigth"]
        heigth1 = [ord(item) for item in struct.pack('>i', int(_osd_heigth) + 187)]
        osd_heigth1 = ([0x80, 0x03, 0x8E])
        osd_send1 = osd_heigth1 + [heigth1[3]]
        spi_x.transfer(osd_send1)
        osd_heigth2 = ([0x80, 0x03, 0x8F])
        osd_send2 = osd_heigth2 + [heigth1[2]]
        spi_x.transfer(osd_send2)

        # picture heigth
        hwidth1 = [0x80, 0x03, 0x90]
        value2 = [ord(item) for item in struct.pack('>i', width)]
        send2 = hwidth1 + [value2[3]]
        spi_x.transfer(send2)
        hwidth2 = [0x80, 0x03, 0x91]
        send3 = hwidth2 + [value2[2]]
        spi_x.transfer(send3)

        # picture position - width
        _osd_width = request.form["_osd_width"]
        width1 = [ord(item) for item in struct.pack('>i', int(_osd_width) + 39)]
        osd_width1 = ([0x80, 0x03, 0x92])
        osd_send3 = osd_width1 + [width1[3]]
        spi_x.transfer(osd_send3)
        osd_width2 = ([0x80, 0x03, 0x93])
        osd_send4 = osd_width2 + [width1[2]]
        spi_x.transfer(osd_send4)

        # picture width
        vwidth1 = [0x80, 0x03, 0x94]
        value4 = [ord(item) for item in struct.pack('>i', heigth)]
        send4 = vwidth1 + [value4[3]]
        spi_x.transfer(send4)
        vwidth2 = [0x80, 0x03, 0x95]
        send5 = vwidth2 + [value4[2]]
        spi_x.transfer(send5)

        spi_x.transfer([0x80, 0x03, 0x89, 0x40])  # Enable color pallet
        _transparency = request.form['_transparency']
        if _transparency == 'yes':
            # TODO
            # not working well yet
            # first transparency color
            # if _first_color ==
            _first_color = request.form['_first_color']
            _first_color_send = 'osd %s %s %s %s 1 %s\r' % (
                int(_osd_heigth), width, int(_osd_width), heigth, _first_color)
            port.write(_first_color_send.encode('ascii', 'strict'))
            '''
            #second transparency color
            _second_color = request.form['_second_color']
            _second_color_send = 'osd %s %s %s %s 1 %s %s\r' % (int(_osd_heigth), width, int(_osd_width), heigth, _first_color, _second_color)
            port.write(_second_color_send.encode('ascii', 'strict', 'strict'))

            #third transparency color
            _third_color = request.form['_third_color']
            _third_color_send = 'osd %s %s %s %s 1 %s %s %s\r' % (int(_osd_heigth), width, int(_osd_width), heigth, _first_color, _second_color, _third_color)
            port.write(_third_color_send.encode('ascii', 'strict', 'strict'))

            #fourth transparency color
            _fourth_color = request.form['_fourth_color']
            _fourth_color_send = 'osd %s %s %s %s 1 %s %s %s %s\r' % (int(_osd_heigth), width, int(_osd_width), heigth, _first_color, _second_color, _third_color, _fourth_color)
            '''
        else:
            _first_color = 'nothing choosen'
            spi_x.transfer([0x80, 0x03, 0x88, 0x02])  # Bitmap OSD is displayed without transparency (0x02)
            d = collections.OrderedDict()
            d['status'] = 200
            d['Filename'] = _filename
            d['path'] = path
            d['height'] = width
            d['width'] = heigth
            d['hstart'] = _osd_heigth
            d['vstart'] = _osd_width
            d['transparency'] = _transparency
            d['color'] = _first_color
            return flask_json.dumps(d, sort_keys=False, indent=True)
            # return render_template('spi_tty.html')
    logging.error('Not logged in')
    return render_template('login.html')


if __name__ == "__main__":
    try:
        conf_version()
        raspmodel()
        pin()
        raspiname()
        # app.debug = True
        app.run(host='0.0.0.0', port=88)  # for port 80, you will need SUDO
    finally:
        # After http-server work is finished, shut off the camera
        with camlock:
            if camera:
                camera.close()
