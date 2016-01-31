import hangups, plugins, os, time, pytz, re
from datetime import datetime, timedelta

serverTimeZone = pytz.timezone("US/Pacific")
hours_per_cycle = 175

def _initialise(bot):  
    plugins.register_user_command(["allcheckpoints", "allcp", "nextcp", "nextcheckpoint", "nextcycle", "mappin"])
    plugins.register_admin_command(["settimezone", "setcity", "ihacked", "startfarm", "clearfarm", "farmlocation"])
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
# Maps stuff
#####################

def mappin(bot,event,*args):
    """
    Takes an Ingress intel link for a portal and creates a Google maps pin to that location
    <b>/ada mappin <url></b>
    """
    url = ''.join(args).strip()
    coords = url.split("pll=")
    if not url or len(coords) != 2:
        yield from bot.coro_send_message(event.conv, "You need to provide an intel url for a portal.")
        return
    res = re.match("-?[1-8]+\.[0-9]+,-?[1-8]+\.[0-9]+", coords[1])
    if not res:
        yield from bot.coro_send_message(event.conv, "Unable to parse the provided intel link. Make sure it is a link to a portal and try again.")
        return

    yield from bot.coro_send_message(event.conv, "https://maps.google.com/maps?q="+coords[1])
    
#####################
# Farm stuff
#####################

def startfarm(bot, event, *args):
    """
    Starts up a farm for the hangout. Currently only 1 farm supported at a time.
    <b>/ada startfarm</b>
    """
    if not bot.memory.exists(["conv_data", event.conv.id_]):
        bot.memory.set_by_path(['conv_data', event.conv.id_], {})
    if bot.memory.exists(["conv_data", event.conv.id_, "farm"]):
        farm = bot.memory.get_by_path(["conv_data", event.conv.id_, "farm"])
        if farm:
            yield from bot.coro_send_message(event.conv, "A farm is all ready set up for this hangout, if it is over please clear it before starting a new one.")
            return
    bot.memory.set_by_path(["conv_data", event.conv.id_, "farm"], {'location': 'unknown', 'time': 'unknown', 'participants': [], 'notes':''})
    bot.memory.save()
    yield from bot.coro_send_message(event.conv, "A farm has been started, use <b><i>/ada farmlocation</i></b> to set a location<br/><b><i>/ada farmtime</i></b> to set a time<br/><b><i>/ada farmnotes</i></b> to add notes<br/><b><i>/ada joinfarm</i></b> to join up!")

def farmlocation(bot, event, *args):
    """
    If a farm has been started this will set the location for that farm.
    <b>/ada farmlocation <location></b>
    """
    # TODO: Accept lat lng, portal link or attempt to look up address (maybe?) to be able to generate a google maps link to the farm
    if not args:
        yield from bot.coro_send_message(event.conv, "You must supply a location to set the location....")
        return
    
    if bot.memory.exists(["conv_data", event.conv.id_]):
        if bot.memory.exists(["conv_data", event.conv.id_, "farm"]):
            if bot.memory.exists(["conv_data", event.conv.id_, "farm", "location"]):
                location = " ".join(args)
                bot.memory.set_by_path(["conv_data", event.conv.id_, "farm", "location"], location)
                bot.memory.save()
                yield from bot.coro_send_message(event.conv, "The location for the farm has been set to {}.".format(location))
                return
    yield from bot.coro_send_message(event.conv, "There is not farm started to set a location for, please start a farm with /ada startfarm first.")
    
def farm(bot,event,*args):
    """
    If there is a farm this will list the details and participants.
    <b>/ada farm</b>
    """
    if not bot.memory.exists(["conv_data", event.conv.id_]):
        if(bot.memory.exists(["conv_data", event.conv.id_, "farm"])):
            bot.coro_send_message(event.conv, "There is currently a farm set for x")
            return
    bot.coro_send_message(event.conv, "There is currently no farm set up or being set up.")
    
def clearfarm(bot, event, *args):
    """
    Removes the farm.
    <b>/ada clearfarm</b>
    """
    if bot.memory.exists(["conv_data", event.conv.id_, "farm"]):
        bot.memory.set_by_path(["conv_data", event.conv.id_, "farm"],{})
        bot.memory.save()
    yield from bot.coro_send_message(event.conv, "The farm has been removed.")
   
def joinfarm(bot, event, *args):
    """
    If there is a farm active in the hangout you will join it.
    <b>/ada joinfarm</b>
    """
    
def leavefarm(bot, event, *args):
    """
    If there is a farm active in the hangout you will leave it.
    <b>/ada leavefarm</b>
    """
   
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


