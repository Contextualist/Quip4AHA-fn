'''
Include a customized Quip client, some utilities, and timezone setting.
'''

"""Override the local timezone in the process environment"""
import os
os.environ['TZ'] = 'CST-08'
import time
try:
    time.tzset() # for UNIX only
except AttributeError:
    pass
import ssl # disable SSL cert verification for now
ssl._create_default_https_context = ssl._create_unverified_context
import datetime
import sys
import argparse
import json
from urllib.request import urlopen, Request
import threading
import websocket

from quip import QuipClient


class cache(object):
    """A decorator to cache functions based on the expiration date
    given by the callback next_expr each time
    """

    def __init__(self, next_expr):
        self.__c = None
        self.__next_expr = next_expr
        self.__bestbefore = datetime.date.min

    def __call__(self, fn):

        def cached_fn(*args, **kwargs):
            if datetime.datetime.today().date() > self.__bestbefore:
                self.__c = fn(*args, **kwargs)
                self.__bestbefore = self.__next_expr()
            return self.__c

        return cached_fn


class QuipClient4AHA(QuipClient):
    """A customized Quip client dedicated for AHA Broadcast."""
    
    def __init__(self, conf):
        QuipClient.__init__(self, access_token=os.environ['token'])
        self.AHABC_ID = conf["folder_id"]
        self.__ws = None
        self.__ws_retry = 0
    
    @property
    @cache(lambda:datetime.date.max)
    def self_id(self):
        return self.get_authenticated_user()['id']

    @property
    def folder_AHABC(self):
        return self.get_folder(id=self.AHABC_ID)

    @property
    @cache(lambda:week.RecentWeekDay('next Wednesday'))
    def latest_script_id(self):
        AHABC = self.folder_AHABC
        nxtwed = week.RecentWeekDay('next Wednesday')
        title = nxtwed.strftime('%m%d')
        #lstfri = [int(time.mktime(
        #    time.strptime('%s 16:10:00' % (week.RecentWeekday('last Friday')), "%Y-%m-%d %H:%M:%S")))]
        docID = []
        for td in AHABC['children']:
            if (('thread_id' in td) and (self.get_thread(td['thread_id'])['thread']['title']==title)):
                docID.append(td['thread_id'])
        if docID == []:
            raise InvalidOperation("Script not found: There's no legitimate host script for next week's broadcast.")
        if len(docID) > 1:
            raise InvalidOperation("Redundancy Error: More than one scripts for the next broadcast are found!", 409)
        return docID[0]

    def message_feed(self, msg_handler):
        """message_feed maintains a blocking websocket connection 
        with Quip real-time API, and pass Quip messages with thread ID
        over to `msg_handler`.
        """

        self.__ws_retry = 3
        HEARTBEAT_INTERVAL = 20
        HEARTBEAT_MSG = json.dumps({"type": "heartbeat"})

        #TODO: log
        def on_error(ws, err): print("websocket error:", err)

        def on_close(ws):
            ev.set()
            print("websocket disconnected")

        def on_open(ws):

            def run():
                while not ev.wait(HEARTBEAT_INTERVAL):
                    ws.send(HEARTBEAT_MSG)

            startd(run, ev.set)
            print("websocket connected")

        def on_message(ws, rawmsg):
            m = json.loads(rawmsg)
            if (m['type']!='message' or m['thread']['id']!=self.latest_script_id 
                or self.self_id not in m['message'].get('mention_user_ids', [])):
                return
            m['message'].update({'thread_id':m['thread']['id']})
            try:
                msg_handler(m['message'])
            except Exception as e:
                print(e)

        while self.__ws_retry > 0:
            websocket_info = self.new_websocket()
            ev = threading.Event()
            #websocket.enableTrace(True)
            self.__ws = websocket.WebSocketApp(websocket_info["url"],
                on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open)
            self.__ws.run_forever()
            self.__ws_retry -= 1

    def message_feed_close(self):
        self.__ws_retry = 0
        if self.__ws:
            self.__ws.close()
            self.__ws = None


def parse_config():
    psr = argparse.ArgumentParser()
    psr.add_argument('-c', '--config')
    psr.add_argument('-l', '--listen', default=':')
    args = psr.parse_args()

    l = args.listen.split(':')
    sysconf = {
        'host': l[0] or '0.0.0.0',
        'port': int(l[1] or '80')
    }

    if args.config:
        if os.path.exists(args.config):
            print("config file '%s' not found, exit." % args.config)
            sys.exit(1)
        with open(args.config, "rb") as f:
            try:
                config = json.loads(f.read().decode('utf8'))
            except ValueError as e:
                print('found an error while parsing the config: %s' % e.message)
                sys.exit(1)
    else:
        try:
            config = json.loads(urlopen(Request(os.environ['config_json']+'/latest',
                                                headers={'User-Agent':'python-requests'}
                                                )).read())
        except Exception as e:
            print('found an error while parsing the config: %s' % e)
            sys.exit(1)

    tplfile = config.get("template", "./template.html")
    if not os.path.exists(tplfile):
        print("template file not found, exit.")
        sys.exit(1)
    with open(tplfile, "rb") as f:
        template = f.read().decode('utf8')

    return sysconf, config, template

def dump_config():
    url = os.environ.get('config_json')
    if not url:
        return
    urlopen(Request(url, json.dumps(config).encode('utf-8'),
                    {'Content-Type': 'application/json',
                     'User-Agent': 'python-requests'}, method='PUT'))


class ThreadManager(object):
    """ThreadManager starts new threads for blocking functions.
    `cleanup` should be called at program exit to call the 
    clean-ups for each thread LIFO.
    """

    def __init__(self):
        self.__cleanup = []

    def add(self, fn, cfn=None):
        d = threading.Thread(target=fn)
        d.setDaemon(True)
        d.start()
        if cfn:
            self.__cleanup.append(cfn)

    def cleanup(self):
        while self.__cleanup:
            self.__cleanup.pop()()

tm = ThreadManager()
startd, cleanupd = tm.add, tm.cleanup


class week(object):
    
    @classmethod
    def DaysTo(cls, TheDay, IgnoreToday=False):
        """Return the days to a specific day of last/next week.
        e.g. (assume today is May 24, Wed. IgnoreToday=False):
          >>> week.DaysTo('last Friday')
          -5
          >>> week.DaysTo('next Wednesday')
          0
        """
        argu = TheDay.split(' ')
        rel = {'last':-1, 'next':1}[argu[0].lower()]
        weekday = {'Monday':1, 'Tuesday':2, 'Wednesday':3, 'Thursday':4,
                   'Friday':5, 'Saturday':6, 'Sunday':7}[argu[1]]
        today = datetime.datetime.today().isoweekday()
        if IgnoreToday:
            return weekday - today + (rel*weekday<=rel*today) * rel * 7
        else:
            return weekday - today + (rel*weekday<rel*today) * rel * 7
    
    @classmethod
    def RecentWeekDay(cls, TheDay, IgnoreToday=False):
        '''Return the date object for a specific day of last/next week.
        e.g. (assume today is May 24, Wed. IgnoreToday=False):
          >>> repr(week.RecentWeekDay('last Friday'))
          datetime.date(2017, 5, 19)
          >>> repr(week.RecentWeekDay('next Wednesday'))
          datetime.date(2017, 5, 24)
        '''
        return datetime.datetime.today().date() + datetime.timedelta(cls.DaysTo(TheDay,IgnoreToday))


class InvalidOperation(Exception):
    """Exception for all actions that take place when the conditions are not fulfilled."""
    def __init__(self, message, http_code=202):
        Exception.__init__(self, message)
        self.code = http_code

sysconf, config, template = parse_config()
q4a = QuipClient4AHA(config)
