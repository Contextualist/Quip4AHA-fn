from flask import Flask

app = Flask(__name__)

@app.route('/', methods=['POST'])
def home():
    return "Everything's 200 OK."

@app.route('/config', methods=['GET'])
def getconfig():
    from flask import jsonify
    from quip4aha import config
    return jsonify(config)
@app.route('/config', methods=['POST'])
def updateconfig():
    from flask import request
    from quip4aha import config, dump_config
    for k, v in request.json.items():
        config[k] = v
    dump_config()
    return "Done!"

@app.route('/assign', methods=['POST'])
def assign():
    from AssignHost import AssignHost
    return AssignHost().do()

@app.route('/newdoc', methods=['POST'])
def newdoc():
    from NewDoc import NewDoc
    return NewDoc()

@app.route('/updateweather', methods=['POST'])
def updateweather():
    from UpdateWeather import UpdateWeather
    return UpdateWeather()

@app.errorhandler(Exception)
def handle_exception(e):
    from flask import jsonify
    return jsonify(message=str(e)), getattr(e,'code',500)
