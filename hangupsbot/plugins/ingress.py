import hangups
import os
from datetime import datetime, timedelta
import time
import pytz

serverTimeZone = pytz.timezone("US/Pacific")
hours_per_cycle = 175

def _initialise(Handlers, bot=None):  
    Handlers.register_user_command(["allcheckpoints", "allcp", "nextcp", "nextcheckpoint", "nextcycle"])
    Handlers.register_admin_command(["settimezone", "setcity", "ihacked"])
    os.environ['TZ'] = 'US/Pacific'
    time.tzset()

def _getTimeZone(bot,event):
    timezone = 'America/Edmonton'    
    if bot.memory.exists(["conv_data", event.conv.id_]):
        if(bot.memory.exists(["conv_data", event.conv.id_, "timezone"])):
            timezone = bot.memory.get_by_path(["conv_data", event.conv.id_, "timezone"])
    
    return pytz.timezone(timezone)

def settimezone(bot, event, *args):
    """Sets the time zone that should be used for this hangout in calculating all checkpoint times. The time zone name needs to be official from this list https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"""
    timezone = ''.join(args).strip()
    if not bot.memory.exists(["conv_data", event.conv.id_]):
        bot.memory.set_by_path(['conv_data', event.conv.id_], {})
    bot.memory.set_by_path(["conv_data", event.conv.id_, "timezone"], timezone)
    bot.memory.save()
    yield from bot.coro_send_message(event.conv, "The time zone for this hangout has been set to {}".format(timezone))

#####################
# Checkpoint stuff
#####################

# Calculation code borrowed and adapted from https://github.com/jdanlewis/ingress-checkpoints/blob/master/calc.py
def _getCycleStartTime():
    t0 = datetime.strptime('2015-12-30 21', '%Y-%m-%d %H')
    t = datetime.now()
    seconds = time.mktime(t.timetuple()) - time.mktime(t0.timetuple())
    cycles = seconds // (3600 * hours_per_cycle)
    start = t0 + timedelta(hours=cycles * hours_per_cycle)
    return start

def allcheckpoints(bot, event, *args):
    """Returns a list of every checkpoint for the current cycle. The next checkpoint will be bolded. The checkpoint times are shown for the time zone the hangout is set to."""
    tz = _getTimeZone(bot, event)
    start = _getCycleStartTime()
    checkpoints = map(lambda x: start + timedelta(hours=x), range(0, hours_per_cycle, 5))

    currentcpfound = False
    text = []
    text.append('All checkpoints for the current cycle:')
    
    for num, checkpoint in enumerate(checkpoints):
        cp = serverTimeZone.localize(checkpoint)
        if currentcpfound is False and checkpoint > datetime.now():
            text.append('<b><i>Checkpoint {}</i>: {:%I:%M%p %Y-%m-%d}</b>'.format(num+1,cp.astimezone(tz)))
            currentcpfound = True
        else:
            text.append('<i>Checkpoint {}</i>: {:%I:%M%p %Y-%m-%d}'.format(num+1,cp.astimezone(tz)))
        
    
    yield from bot.coro_send_message(event.conv, "<br />".join(text))

def allcp(bot, event, *args):
    """Returns a list of every checkpoint for the current cycle. The next checkpoint will be bolded. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from allcheckpoints(bot, event, *args)

def nextcp(bot, event, *args):
    """Returns the time that the next checkpoint will occur. The checkpoint times are shown for the time zone the hangout is set to."""
    tz = _getTimeZone(bot, event)
    start = _getCycleStartTime()
    checkpoints = map(lambda x: start + timedelta(hours=x), range(0, hours_per_cycle, 5))
    text = 'The next checkpoint is at '
    
    for num, checkpoint in enumerate(checkpoints):
        if checkpoint > datetime.now():
            cp = serverTimeZone.localize(checkpoint)
            text += '{:%I:%M%p %Y-%m-%d}'.format(cp.astimezone(tz))
            break
    
    yield from bot.coro_send_message(event.conv, text)

def nextcheckpoint(bot,event,*args):
    """Returns the time that the next checkpoint will occur. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from nextcp(bot,event,*args)

def nextcycle(bot, event, *args):
    """Returns the time of the first checkpoint for the next cycle. The checkpoint times are shown for the time zone the hangout is set to."""
    tz = _getTimeZone(bot, event)
    start = _getCycleStartTime()
    start = start + timedelta(hours=hours_per_cycle)
    start = serverTimeZone.localize(start)
    text = 'The first checkpoint of the next cycle is at {:%I:%M%p %Y-%m-%d}'.format(start.astimezone(tz))
    yield from bot.coro_send_message(event.conv, text)

#####################
# Sojourner stuff
#####################

def ihacked(bot,event,*args):
    if not bot.memory.exists(["user_data", event.user_id.chat_id]):
        bot.memory.set_by_path(['user_data', event.user_id.chat_id], {})
    if not bot.memory.exists(["user_data", event.user_id.chat_id,"sojourner"]):
        bot.memory.set_by_path(['user_data', event.user_id.chat_id,"sojourner"], {})
    bot.memory.set_by_path(['user_data', event.user_id.chat_id,"sojourner","last_hack_time"], time.time())
    bot.memory.save()
    yield from bot.coro_send_message(event.conv, "Nice work! {}".format(time.time()))


