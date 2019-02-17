from quip4aha import q4a, week, InvalidOperation
import re
import json
from urllib.request import urlopen # py2, urllib2

class UpdateWeather(object):

    SIMP = {'Clear':'sunny',
            'Mostly Cloudy':'mostly cloudy', 'Partly Cloudy':'partly cloudy', 'Overcast':'cloudy',
            'Thunderstorm':'rainy', 'Chance of a Thunderstorm':'rainy', 'Rain':'rainy', 'Chance of Rain':'rainy'}
    
    def __init__(self):
        self.NextNDay = 0
        self.Condition = ''
        self.RainPercentage = ''
        self.TemperatureC = ''
        self.TemperatureF = ''
        self.client = q4a
        
    def do(self):
        '''
        ==================FORECAST DATA==================
        '''
        self.NextNDay = week.DaysTo('next Wednesday')
        if self.NextNDay > 3:
            raise InvalidOperation("Unable to get the weather for Wednesday: "
                                   "WunderStation only gives prediction for today and 3 days ahead. \n"
                                   "But it's {} days to next Wednesday.".format(self.NextNDay))
        response = json.loads(urlopen(
            "http://api.wunderground.com/api/01702baefa3fbf8e/forecast/q/zmw:00000.1.59287.json").read())
        data = response['forecast']['simpleforecast']['forecastday'][self.NextNDay]
        self.Condition = self.SIMP.get(data['conditions'], data['conditions'].lower())
        self.RainPercentage = data['pop']
        self.TemperatureC = data['high']['celsius']
        self.TemperatureF = data['high']['fahrenheit']
        
        '''
        ====================DOC CATCHER====================
        '''
        docID = self.client.latest_script_id
        html = self.client.get_thread(id=docID)['html']
        
        '''
        ====================DATA EMBED====================
        '''
        SID, host, date = re.search(
            r"<p id='([a-zA-Z0-9]{11})'.*?>(.*)Good Morning AHA.+?Wednesday\, ([\w ]+)\..+?<\/p>", html).group(1,2,3)
        ctx = ("<p class='line'>{host}Good Morning AHA!<br/>"
               "It is Wednesday, {date}. "
               "The weather for today is {condition}. "
               "There is {rain_pc}% chance of rain. "
               "The high temperature today will be {t_c} degrees Celsius, which is {t_f} degrees Fahrenheit.</p>").format(
                   host=host, date=date, condition=self.Condition,
                   rain_pc='{} {}'.format('an' if self.RainPercentage==80 else 'a', self.RainPercentage),
                   t_c=self.TemperatureC, t_f=self.TemperatureF)
        
        '''
        ====================POST DATA====================
        '''
        self.client.edit_document(thread_id=docID, content=ctx, format="html",
                                  operation=self.client.REPLACE_SECTION, section_id=SID)
        return "Done!"


if __name__=='__main__':
    UpdateAction = UpdateWeather()
    UpdateAction.do()
