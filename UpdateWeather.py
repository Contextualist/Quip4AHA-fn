from quip4aha import q4a, week
import re
import requests
from datetime import datetime, timedelta
from collections import namedtuple

SIMP = {'Clear':'sunny',
        'Heavy Cloud':'mostly cloudy', 'Light Cloud':'partly cloudy',
        'Thunderstorm':'rainy', 'Heavy Rain':'rainy', 'Light Rain':'rainy', 'Showers':'rainy'}

def precondition():
    return week.DaysTo('next Wednesday')

def fetch_weather(next_nday):
    r_wb = requests.get("https://api.weatherbit.io/v2.0/forecast/daily",
           params={'city': 'Guangzhou', 'days': next_nday+1, 'key': '8a5c6384bc4e45d5bba4fb0015d96c6f'}) \
           .json()['data'][-1] # Weatherbit: for rain_percen only
    wnd = (datetime.today().date() + timedelta(next_nday)).strftime("%Y/%m/%d")
    r = requests.get(f"https://www.metaweather.com/api/location/2161838/{wnd}/") \
        .json()[0]
    return namedtuple('weather', 'condition rain_percen tempC tempF')(
        condition=SIMP.get(r['weather_state_name'], r['weather_state_name'].lower()),
        rain_percen=r_wb['pop'],
        tempC=round(r['max_temp']), tempF=round(r['max_temp']*9/5+32),
    )

def compose(doc_id, w):
    html = q4a.get_latest_script()['html']
    
    sid, host, date = re.search(
        r"<p id='([a-zA-Z0-9]{11})'.*?>(.*)Good Morning AHA.+?Wednesday\, ([\w ]+)\..+?<\/p>", html).group(1,2,3)
    return (
        sid,
        f"<p class='line'>{host}Good Morning AHA!<br/>"
        f"It is Wednesday, {date}. The weather for today is {w.condition}. "
        f"There is {'an' if w.rain_percen in [18,*range(80,90)] else 'a'} {w.rain_percen}% chance of rain. "
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
    post_weather(doc_id, sid, p)
    return "Done!"

if __name__=='__main__':
    UpdateWeather()
