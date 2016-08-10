import hangups, plugins, logging, os, time, pytz, re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

serverTimeZone = pytz.timezone("UTC")
hours_per_cycle = 175

def _initialise(bot):  
    plugins.register_user_command(["allcheckpoints", "allcp", "nextcp", "nextcheckpoint", "nextcycle", "mappin", "getdean"])
    plugins.register_admin_command(["settimezone", "addpasscodehangout", "removepasscodehangout", "pc", "whois"])
    os.environ['TZ'] = 'UTC'
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

def getdean(bot, event, *args):
    """Brings Dean, the bot master, into the chat"""
    yield from bot._client.adduser(event.conv_id, ["117841191535067089864"])

#####################
# Checkpoint stuff
#####################

def _getCycleData():
    t1 = serverTimeZone.localize(datetime.utcnow())
    t0 = serverTimeZone.localize(datetime(2015, 12, 31, 5, 0))
    tdelta = t1 - t0
    cycle = timedelta(hours=175)
    cycles = tdelta // cycle
    cycle_start = t0 + (cycles * cycle)
    return {"start": cycle_start, "now": t1}

def allcheckpoints(bot, event, *args):
    """Returns a list of every checkpoint for the current cycle. The next checkpoint will be bolded. The checkpoint times are shown for the time zone the hangout is set to."""
    tz = _getTimeZone(bot, event)
    data = _getCycleData()
    checkpoint_times = map(lambda x: data['start'] + timedelta(hours=x), range(0, hours_per_cycle, 5))

    currentcpfound = False
    text = []
    text.append('All checkpoints for the current cycle:')

    for num, checkpoint in enumerate(checkpoint_times):
        if currentcpfound is False and checkpoint > data['now']:
            text.append('<b><i>Checkpoint {}</i>: {:%I:%M%p %Y-%m-%d}</b>'.format(num + 1, checkpoint.astimezone(tz)))
            currentcpfound = True
        else:
            text.append('<i>Checkpoint {}</i>: {:%I:%M%p %Y-%m-%d}'.format(num + 1, checkpoint.astimezone(tz)))

    yield from bot.coro_send_message(event.conv, "<br />".join(text))

def allcp(bot, event, *args):
    """Returns a list of every checkpoint for the current cycle. The next checkpoint will be bolded. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from allcheckpoints(bot, event, *args)

def nextcp(bot, event, *args):
    """Returns the time that the next checkpoint will occur. The checkpoint times are shown for the time zone the hangout is set to."""
    tz = _getTimeZone(bot, event)
    data = _getCycleData()
    cdelta = data['now'] - data['start']
    checkpoint = timedelta(hours=5)
    checkpoints = (cdelta // checkpoint) + 1
    checkpoint_start = data['start'] + (checkpoint * checkpoints)
    yield from bot.coro_send_message(event.conv, "The next checkpoint is at {:%I:%M%p %Y-%m-%d}".format(checkpoint_start.astimezone(tz)))

def nextcheckpoint(bot,event,*args):
    """Returns the time that the next checkpoint will occur. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from nextcp(bot,event,*args)

def nextcycle(bot, event, *args):
    """Returns the time of the first checkpoint for the next cycle. The checkpoint times are shown for the time zone the hangout is set to."""
    tz = _getTimeZone(bot, event)
    data = _getCycleData()
    start = data['start'] + timedelta(hours=hours_per_cycle)
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
    res = re.match("-?[1-9]+\.[0-9]+,-?[1-9]+\.[0-9]+", coords[1])
    if not res:
        yield from bot.coro_send_message(event.conv, "Unable to parse the provided intel link. Make sure it is a link to a portal and try again.")
        return

    yield from bot.coro_send_message(event.conv, "https://maps.google.com/maps?q="+coords[1])

#####################
# Passcode stuff
#####################

def addpasscodehangout(bot, event, *args):
    """
    Adds a hangout to the list of hangouts to receive passcodes
    """
    if not bot.memory.exists(["passcode_hangouts"]):
        bot.memory["passcode_hangouts"] = []
    newHo = ''.join(args).strip()
    if not newHo:
        yield from bot.coro_send_message(event.conv_id, _('No hangout was specified.'))
        return
    hos = bot.memory.get("passcode_hangouts")
    hos.append(newHo)
    bot.memory["passcode_hangouts"] = hos
    bot.memory.save()
    yield from bot.coro_send_message(event.conv_id, _('The hangout has been added to the list to recieve passcodes.'))

def removepasscodehangout(bot,event,*args):
    """
    Removes a hangout to the list of hangouts to receive passcodes
    """
    if not bot.memory.exists(["passcode_hangouts"]):
        yield from bot.coro_send_message(event.conv_id, _('There are no passcode hangouts to remove.'))
        return
    oldHo = ''.join(args).strip()
    if not oldHo:
        yield from bot.coro_send_message(event.conv_id, _('No hangout was specified.'))
        return
    hos = bot.memory.get("passcode_hangouts")
    if oldHo in hos:
        hos.remove(oldHo)
        bot.memory["passcode_hangouts"] = hos
        bot.memory.save()
        yield from bot.coro_send_message(event.conv_id, _('The hangout has been removed from the list to recieve passcodes.'))

def pc(bot,event,*args):
    """
    Passes a passcode to the list of passcode hangouts
    """
    passcodes = ' '.join(args).strip()
    if not passcodes:
        yield from bot.coro_send_message(event.conv_id, _('No passcode was specified.'))
        return
    hos = bot.memory.get("passcode_hangouts")
    for ho in hos:
        yield from bot.coro_send_message(ho, passcodes)
        logger.info("Sent the pass code '{}' to hangout {}".format(passcodes,ho))
    
    yield from bot.coro_send_message(event.conv_id, _('The passcode(s) have been shared.'))

#####################
# Agent stuff
#####################

def whois(bot, event, *args):
    """
    Attempts to look for people related to a search term
    /ada whois <search term>
    """
    term = ' '.join(args).strip().lower()
    if not term or len(term) < 3:
        yield from bot.coro_send_message(event.conv_id, "No search term was provided or term was too short.")
        return
    found_users = []
    for chat_id, user_data in bot.memory["user_data"].items():
        curr_nick = ""
        if "nickname" in user_data:
            curr_nick = user_data['nickname']
        if term in curr_nick.lower() or term in user_data['_hangups']['full_name'].lower():
            text = "<a href='https://plus.google.com/u/0/{}/about'>{}</a>".format(user_data['_hangups']['gaia_id'], user_data['_hangups']['full_name'])
            if curr_nick:
                text += " aka @{}".format(curr_nick)
            found_users.append(text)

    if not found_users:
        yield from bot.coro_send_message(event.conv_id, "Unable to find anyone that matches the search terms!")
        return

    yield from bot.coro_send_message(event.conv_id, "<br/>".join(found_users))

#####################
# Distance Stuff
#####################

