from quip4aha import q4a, week, InvalidOperation
import re
import json
from urllib.request import urlopen # py2, urllib2
from collections import namedtuple

SIMP = {'Clear':'sunny',
        'Mostly Cloudy':'mostly cloudy', 'Partly Cloudy':'partly cloudy', 'Overcast':'cloudy',
        'Thunderstorm':'rainy', 'Chance of a Thunderstorm':'rainy', 'Rain':'rainy', 'Chance of Rain':'rainy'}

def precondition():
    dayn = week.DaysTo('next Wednesday')
    if dayn > 3:
        raise InvalidOperation("Unable to get the weather for Wednesday: "
                               "WunderStation only gives prediction for today and 3 days ahead. \n"
                              f"But it's {dayn} days to next Wednesday.")
    return dayn

def fetch_weather(next_nday):
    response = json.loads(urlopen(
        "http://api.wunderground.com/api/01702baefa3fbf8e/forecast/q/zmw:00000.1.59287.json").read())
    print(response)
    data = response['forecast']['simpleforecast']['forecastday'][next_nday]
    return namedtuple('weather', 'condition rain_percen tempC tempF')(
        condition=SIMP.get(data['conditions'], data['conditions'].lower()),
        rain_percen=data['pop'],
        tempC=data['high']['celsius'], tempF=data['high']['fahrenheit'],
    )

def compose(doc_id, w):
    html = q4a.get_thread(id=doc_id)['html']
    
    sid, host, date = re.search(
        r"<p id='([a-zA-Z0-9]{11})'.*?>(.*)Good Morning AHA.+?Wednesday\, ([\w ]+)\..+?<\/p>", html).group(1,2,3)
    return (
        sid,
        f"<p class='line'>{host}Good Morning AHA!<br/>"
        f"It is Wednesday, {date}. The weather for today is {w.condition}. "
        f"There is {'an' if w.rain_percen==80 else 'a'} {w.rain_percen}% chance of rain. "
        f"The high temperature today will be {w.tempC} degrees Celsius, which is {w.tempF} degrees Fahrenheit.</p>"
    )

def post_weather(doc_id, sid, p):
    q4a.edit_document(thread_id=doc_id, content=p, format="html",
                      operation=q4a.REPLACE_SECTION, section_id=sid)

def UpdateWeather():
    next_nday = precondition()
    weather = fetch_weather(next_nday)
    doc_id = q4a.latest_script_id
    sid, p = compose(doc_id, weather)
    print(next_nday, weather, doc_id, sid, p)
    #post_weather(doc_id, sid, p)
    return "Done!"

if __name__=='__main__':
    UpdateWeather()
