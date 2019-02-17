from flask import Flask

app = Flask(__name__)

@app.route('/', methods=['POST'])
def home():
    return "Everything's 200 OK."

@app.route('/getconfig', methods=['POST'])
def getconfig():
    from flask import jsonify
    from quip4aha import config
    return jsonify(config)

@app.route('/assign', methods=['POST'])
def assign():
    from AssignHost import AssignHost
    return AssignHost().do()

@app.route('/newdoc', methods=['POST'])
def newdoc():
    from NewDoc import NewDoc
    return NewDoc().do()

@app.route('/updateweather', methods=['POST'])
def updateweather():
    from UpdateWeather import UpdateWeather
    return UpdateWeather().do()

@app.errorhandler(Exception)
def handle_exception(e):
    from flask import jsonify
    return jsonify(message=str(e)), getattr(e,'code',500)
