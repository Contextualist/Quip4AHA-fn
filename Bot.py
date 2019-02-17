from quip4aha import q4a, config

from urllib.request import urlopen, Request # py2, urllib2
import json

payload = {
    "currentNode": "",
    "complete": None,
    "context": {},
    "parameters": [],
    "extractedParameters": {},
    "speechResponse": "",
    "intent": {},
    "input": "",
    "missingParameters": []
}

def iky_relay(msg):
    payload['input'] = msg['text'].replace('https://quip.com/%s'%q4a.self_id, '')

    req = Request(config['iky_api'], json.dumps(payload))
    req.add_header("Content-Type", "application/json; charset=utf-8")
    rpl = json.loads(urlopen(req).read())

    q4a.new_message(thread_id=msg['thread_id'], parts='[["system","%s"]]'%rpl['speechResponse'])

class Chatbot(object):

    def run(self):
        q4a.message_feed(iky_relay)

    def quit(self):
        q4a.message_feed_close()


if __name__ == "__main__":
    Chatbot().run()
