import logging
import plugins
import requests

logger = logging.getLogger(__name__)
_internal = {}

def _initialize(bot):
    api_key = bot.get_config_option('forecast_api_key')
    if api_key:
        _internal['forecast_api_key'] = api_key
        plugins.register_user_command(['weather', 'forecast'])
        plugins.register_admin_command(['setweatherlocation'])
    else:
        logger.error('WEATHER: config["forecast_api_key"] required')

def setweatherlocation(bot, event, *args):
    """Sets the Lat Long default coordinates for this hangout when polling for weather data
    /ada setWeatherLocation <location>
    """
    location = ''.join(args).strip()
    if not location:
        yield from bot.coro_send_message(event.conv_id, _('No location was specified, please specify a location.'))
    
    location = _lookup_address(location)
    if not location:
        yield from bot.coro_send_message(event.conv_id, _('Unable to find the specified location.'))
    
    if bot.memory.exists(["conv_data", event.conv.id_]):
        bot.memory.set_by_path(["conv_data", event.conv.id_, "default_weather_location"], {'lat': location['lat'], 'lng': location['lng']})
        bot.memory.save()
        yield from bot.coro_send_message(event.conv_id, _('This hangouts default location has been set to {}.'.format(location)))

def weather(bot, event, *args):
    """Returns weather information from Forecast.io
    <b>/ada weather <location></b> Get location's current weather.
    <b>/ada weather</b> Get the hangouts default location's current weather. If the default location is not set talk to a hangout admin.
    """
    weather = _get_weather(bot, event, args)
    if weather:
        yield from bot.coro_send_message(event.conv_id, _format_current_weather(weather))
    else:
        yield from bot.coro_send_message(event.conv_id, 'There was an error retrieving the weather, guess you need to look outside.')

def forecast(bot, event, *args):
    """Returns a brief textual forecast from Forecast.io
    <b>/ada weather <location></b> Get location's current forecast.
    <b>/ada weather</b> Get the hangouts default location's forecast. If default location is not set talk to a hangout admin.
    """
    weather = _get_weather(bot, event, args)
    if weather:
        yield from bot.coro_send_message(event.conv_id, _format_forecast_weather(weather))
    else:
        yield from bot.coro_send_message(event.conv_id, 'There was an error retrieving the weather, guess you need to look outside.')
 
def _format_current_weather(weather):
    """
    Formats the current weather data for the user.
    """
    weatherStrings = []    
    if 'temperature' in weather:
        weatherStrings.append("It is currently: <b>{0}°{1}</b>".format(weather['temperature'],weather['units']['temperature']))
    if 'summary' in weather:
        weatherStrings.append("<i>{0}</i>".format(weather['summary']))
    if 'feelsLike' in weather:
        weatherStrings.append("Feels Like: {0}°{1}".format(weather['feelsLike'],weather['units']['temperature']))
    if 'windspeed' in weather:
        weatherStrings.append("Wind: {0} {1} from {2}".format(weather['windspeed'], weather['units']['windSpeed'], _get_wind_direction(weather['windbearing'])))
    if 'humidity' in weather:
        weatherStrings.append("Humidity: {0}%".format(weather['humidity']))
    if 'pressure' in weather:
        weatherStrings.append("Pressure: {0} {1}".format(weather['pressure'], weather['units']['pressure']))
        
    return "<br/>".join(weatherStrings)

def _format_forecast_weather(weather):
    """
    Formats the forecast data for the user.
    """
    weatherStrings = []
    if 'hourly' in weather:
        weatherStrings.append("<b>Next 24 Hours</b><br/>{}". format(weather['hourly']))
    if 'daily' in weather:
        weatherStrings.append("<b>Next 7 Days</b><br/>{}". format(weather['daily']))
        
    return "<br/>".join(weatherStrings)

def _lookup_address(location):
    """
    Retrieve the coordinates of the location.
    :params location: string argument passed by user.
    :returns: dictionary containing latitutde and longitude.
    """
    google_map_url = 'http://maps.googleapis.com/maps/api/geocode/json'
    payload = {'address': location.replace(' ', '')}
    r = requests.get(google_map_url, params=payload)

    try:
        coords = r.json()['results'][0]['geometry']['location']
    except:
        coords = {}

    return coords

def _lookup_weather(coords):
    """
    Retrieve the current forecast at the coordinates.
    :params coords: dictionary containing latitude and longitude.
    :returns: dictionary containing parsed current forecast.
    """

    forecast_io_url = 'https://api.forecast.io/forecast/{0}/{1},{2}?units=auto'.format(_internal['forecast_api_key'],coords['lat'], coords['lng'])
    logger.debug('Forecast.io GET %s' % (forecast_io_url))
    r = requests.get(forecast_io_url)
    logger.debug('Request status code: %i' % (r.status_code))

    try:
        j = r.json()
        current = {
            'time' : j['currently']['time'],
            'summary': j['currently']['summary'],
            'temperature': j['currently']['temperature'],
            'feelsLike': j['currently']['apparentTemperature'],
            'units': _get_forcast_units(j),
            'humidity': int(j['currently']['humidity']*100),
            'windspeed' : j['currently']['windSpeed'],
            'windbearing' : j['currently']['windBearing'],
            'pressure' : (j['currently']['pressure']/10)
        }
        if 'hourly' in j:
            current['hourly'] = j['hourly']['summary']
        if 'daily' in j:
            current['daily'] = j['daily']['summary']
        
    except Exception as e:
        logger.info("Forecast Error: {}".format(e))
        current = dict()

    return current

def _get_weather(bot,event,params):
    """ 
    Checks memory for a default location set for the current hangout.
    If one is not found and parameters were specified attempts to look up a location.    
    If it finds a location it then attempts to load the weather data
    """
    parameters = list(params)
    location = {}
     
    if not parameters:
        if bot.memory.exists(["conv_data", event.conv.id_]):
            if(bot.memory.exists(["conv_data", event.conv.id_, "default_weather_location"])):
                location = bot.memory.get_by_path(["conv_data", event.conv.id_, "default_weather_location"])
    else:
        address = ''.join(parameters).strip()
        location = _lookup_address(address)
    
    if location:
        return _lookup_weather(location)
    
    return {}

def _get_forcast_units(result):
    units = {
        'temperature': 'F',
        'distance': 'Miles',
        'percipIntensity': 'in./hr.',
        'precipAccumulation': 'inches',
        'windSpeed': 'mph',
        'pressure': 'millibars'
    }
    if result['flags']:
        unit = result['flags']['units']
        if unit != 'us':
            units['temperature'] = 'C'
            units['distance'] = 'KM'
            units['percipIntensity'] = 'milimeters per hour'
            units['precipAccumulation'] = 'centimeters'
            units['windSpeed'] = 'm/s'
            units['pressure'] = 'kPa'
            if unit == 'ca':
                units['windSpeed'] = 'km/h'
            if unit == 'uk2':
                units['windSpeed'] = 'mph'
                units['distance'] = 'Miles'
    return units

def _get_wind_direction(degrees):
    directionText = "N"
    if degrees >= 5 and degrees < 40:
        directionText = "NNE"
    elif degrees >= 40 and degrees < 50:
        directionText = "NE"
    elif degrees >= 50 and degrees < 85:
        directionText = "ENE"
    elif degrees >= 85 and degrees < 95:
        directionText = "E"
    elif degrees >= 95 and degrees < 130:
        directionText = "ESE"
    elif degrees >= 130 and degrees < 140:
        directionText = "SE"
    elif degrees >= 140 and degrees < 175:
        directionText = "SSE"
    elif degrees >= 175 and degrees < 185:
        directionText = "S"
    elif degrees >= 185 and degrees < 220:
        directionText = "SSW"
    elif degrees >= 220 and degrees < 230:
        directionText = "SW"
    elif degrees >= 230 and degrees < 265:
        directionText = "WSW"
    elif degrees >= 265 and degrees < 275:
        directionText = "W"
    elif degrees >= 275 and degrees < 310:
        directionText = "WNW"
    elif degrees >= 310 and degrees < 320:
        directionText = "NW"
    elif degrees >= 320 and degrees < 355:
        directionText = "NNW"
    
    return directionText
    