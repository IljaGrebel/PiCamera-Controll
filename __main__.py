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
    - auto-updater
    #######################################################
    :| Updates
    v1.01 - Some bug fixed
    v1.02 - Added more system information
    v1.03 - Added logging information, no print messages in console anymore
    v1.04 - Added Frame status while recording
    '''

# All print messages are only for debuggin/manual starting from console
# Set default encoding to UTF-8
# Flask, Flask-WTF, simplepam for Authentifaction
from flask import Flask, session, url_for, escape, request
from flask import json as flask_json
from simplepam import authenticate
from flask import render_template, redirect
import datetime
import time
import os
from threading import Lock
import picamera
import ConfigParser
import subprocess
import netifaces
import collections
import RPi.GPIO as GPIO
import psutil
#import iptools
import logging
import config
import serial
import spidev


#create log file
logging.basicConfig(format = u'%(levelname)-8s [%(asctime)s] %(message)s', level = logging.DEBUG, filename = u'log.log')

app = Flask(__name__)
app.secret_key = os.urandom(24)

camera = None  # After starting, camera is offline
camlock = Lock()  # Needed to block access from multi responses
config = ConfigParser.RawConfigParser()
config.read('config.ini')
uptime = time.time()
firmware = 'v1.04'
version = 4
website = 'v1.02'
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
                #TODO write in config.ini
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

@app.route('/change_ip', methods=['POST'])
def change_ip():
    if 'username' in session:
        ipaddress = ''
        broadcast = ''
        subnet = ''
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
    f = open('/proc/cpuinfo','r')
    for line in f:
      if line[0:8]=='Revision':
        length=len(line)
        myrevision = line[11:length-1]
    f.close()
  except:
    myrevision = "0000"
  return 'Revision - %s' % myrevision

@app.route('/pin', methods=['GET'])
def pin():
    global PIN_Number
    #Pi 2 Model B
    if myrevision == 'a01041':
        PIN_Number = '21'
    elif myrevision == 'a21041':
        PIN_Number = '21'
    #Pi 3 Model B
    elif myrevision == 'a02082':
        PIN_Number = '21'
    elif myrevision == 'a22082':
        PIN_Number = '21'
    #Model B Revision 1.0
    elif myrevision == '0002':
        PIN_Number = '42'
    #Model B Revision 1.0 + ECN0001 (no fuses, D14 removed)
    elif myrevision == '0003':
        PIN_Number = '42'
    #Model B Revision 2.0
    elif myrevision == '0004' or '0005' or '0006':
        PIN_Number = '42'
    #Model A
    elif myrevision == '0007' or '0008' or '0009':
        PIN_Number = '42'
    #Model B Revision 2.0
    elif myrevision == '000d' or '000e' or '000f':
        PIN_Number = '42'
    #Model B+
    elif myrevision == '0010':
        PIN_Number = '42'
    #Compute Module
    elif myrevision == '0011':
        PIN_Number = '42'
    #Model A+
    elif myrevision == '0012':
        PIN_Number = '42'
    else:
        PIN_Number = '42'
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

@app.route('/restart_gpio_test', methods=['POST']) # need for testing
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
        d['hardware'] = '38126-2' #hardcode
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
            d['image_file'] = config.get('ENCODER' , 'img_file')
            d['image_format'] = config.get('ENCODER', 'img_fmt')
            d['camera_effect'] = config.get('ENCODER' , 'camera_effect')
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

#TODO Change path
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
    logging.info('Creating directiories %s' % (record_dir + img_dir))
    return record_dir + img_dir

#Set GPIO4 to 0 and then to 1 (Restart B101)
@app.route('/restart_b101', methods=['POST'])
def reset_gpio():
    if 'username' in session:
        os.system('echo "0" > /sys/class/gpio/gpio4/value')
        os.system('echo "1" > /sys/class/gpio/gpio4/value')
        d = collections.OrderedDict()
        d['status'] = 200
        d['comment'] = 'B101 (38126-2) has been restarted'
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
        logging.error("Not logged in")
        return render_template('login.html')

@app.route('/edid', methods=['GET'])
def edid():
    return 0

@app.route('/camera_t', methods=['GET'])
def camera_t():
    global camera
    with camlock:
        camera = picamera.PiCamera()
        test = camera._get_camera_settings()
        return test

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
        else:
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
        else:
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
            #reset_gpio()
            camera = picamera.PiCamera()
            camera.resolution = (config.getint('ENCODER', 'width'), config.getint('ENCODER', 'heigth'))
            camera.framerate = config.getint('ENCODER', 'framerate')
            camera.image_effect = config.get('ENCODER', 'camera_effect')
            camera.annotate_text = config.get('ENCODER', 'annotate_text')
            camera.start_preview()
            mkdir()
            camera.start_recording(record_dir + config.get('ENCODER', 'record_File') + config.get('ENCODER', 'video_fmt'))
            d = collections.OrderedDict()
            d['status'] = 200
            d['record'] = 'recording'
            d['record_dir'] = record_dir
            d['record_file'] = config.get('ENCODER', 'record_file') + config.get('ENCODER', 'video_fmt')
            d['comment'] = 'recording started'
            logging.info("recording has been started")
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
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
        else:
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
        else:
            logging.error("Not logged in")
            return render_template('login.html')

'''
# PAUSE RECORD - NOT WORKING AT MOMENT + JSON REQUEST/RESPONSE
@app.route('/pause_record', methods=['POST'])
def pause_record():
    global camera
    with camlock:
        if 'username' in session:
            if camera:
                d = collections.OrderedDict()
                d['status'] = 200
                return 'already paused ' + config.get('ENCODER', 'record_file') + config.get('ENCODER', 'video_fmt')
            logging.info("pause record")
            camera = picamera.PiCamera()
            time.sleep(900000)
            return 'Recording to ' + config.get('ENCODER', 'record_file') + config.get('ENCODER', 'video_fmt') + ' paused'
        else:
            logging.error("Not logged in")
            return render_template('login.html')
'''

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
        else:
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
            os.system('raspivid -t 0 -fps 25 -hf -b 2000000 -o - | ffmpeg -i - -vcodec copy -an -r 30 -g 30 -bufsize 2000000 -pix_fmt yuv420p -f mpegts udp://@239.239.2.1:1234')
            d = collections.OrderedDict()
            d['status'] = 200
            d['stream'] = 'streaming'
            d['startTime'] = time.time()
            d['link'] = 'udp://@239.239.2.1:1234' #udp://@239.239.2.1:1234 \ in future: rtsp, rtmp and udp (if it will working)
        return flask_json.dumps(d, sort_keys=False, indent=True)
    else:
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
    else:
        logging.error("Not logged in")
        return render_template('login.html')

# MP4
def rec_video_to_mp4():
    print 'video to .mp4'
    cmd = ('ffmpeg -i %s -vcodec copy -an -f mp4 %s.mp4') % (record_dir + config.get('ENCODER', 'record_File') + config.get('ENCODER', 'video_fmt'), config.get('ENCODER', 'record_dir') + config.get('ENCODER', 'record_File'))
    os.system(cmd)
    d = collections.OrderedDict()
    d['status'] = 200
    d['process'] = '.h264 to .mp4'
    d['h264File'] = record_dir + config.get('ENCODER', 'record_File') + config.get('ENCODER', 'video_fmt')
    d['mp4File'] = '%s %s.mp4'
    return 'Creating .MP4 File'
#os.remove(record_dir + record_file + ".h264")
#return '.h264 File deleted'

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
            camera.capture((img_dir + '%s-' + config.get('ENCODER', 'img_file') + config.get('ENCODER', 'img_fmt')) % (screenshot.counter), use_video_port=True)
            d = collections.OrderedDict()
            d['status'] = 200
            d['name'] = '%d-%s%s' % (screenshot.counter, config.get('ENCODER', 'img_file'),config.get('ENCODER', 'img_fmt'))
            d['path'] = img_dir
            logging.info('screenshot %d-%s%s captured' % (screenshot.counter, config.get('ENCODER', 'img_file'), config.get('ENCODER', 'img_fmt')))
            return flask_json.dumps(d, sort_keys=False, indent=True)
        else:
            logging.error("Not logged in")
            return render_template('login.html')

#TODO
@app.route('/get_video', methods=['GET'])
def get_video():
    if 'username' in session:
        return 0
    else:
        return 0

#TODO
@app.route('/get_images', methods=['GET'])
def get_images():
    if 'username' in session:
        return 0
    else:
        return 0

'''
#SPI
@app.route('/spi_b1', methods=['GET', 'POST'])
def spi_b1():
    spi.spidev.SpiDev()
    spi.open(0,1)
    to_send = []
    spi.xfer(to_send)
    print 'send %s' % to_send
    return 'sned %s' % to_send
'''

#UART - Steuerung
'''
@app.route('/serial_b1', methods=['GET', 'POST'])
def serial_b1():
    port = serial.Serial(bytesize=8, ) #open serial port
    print (port.name) #check which port was really used
    port.write(b '') #write a string
    port.close() #close port
    return 'port closed'

@app.route('/serial_b2', methods=['GET', 'POST'])
def serial_b2():
    port = serial.Serial('')
    print (port.name)
    port.write(b '')
    port.close()
    return 'port closed'

@app.route('/serial_b3', methods=['GET', 'POST'])
def serial_b3():
    port = serial.Serial('')
    print (port.name)
    port.write(b '')
    port.close()
    return 'port closed'
'''

#################   WEB API   ##################

#@app.route('/get_recordings', methods=['GET'])
#def get_recordings():

#@app.route('/get_screenshots', methonds=['GET])
#def get_screenshots():

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
            #add fail_login.html
            #return render_template('error.html') <-- redirect in error.html
            #return render_template('f_login.html')
            #return 'Invalid username/password'
            return render_template('f_login.html')
    return render_template('login.html')

@app.route('/index.html')
def indexhtml():
    if 'username' in session:
        return render_template('index.html')
    logging.error('Not logged in')
    return render_template('login.html')

#System info
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

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    return redirect(url_for('index'))

if __name__ == "__main__":
    try:
        conf_version()
        raspmodel()
        pin()
        raspiname()
        #app.debug = True
        app.run(host='0.0.0.0', port=80)
    finally:
        # After http-server work is finished, shut off the camera
        with camlock:
            if camera:
                camera.close()