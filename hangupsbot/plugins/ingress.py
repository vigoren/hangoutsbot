import hangups, plugins, logging, os, time, pytz, re, math
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

serverTimeZone = pytz.timezone("UTC")
hours_per_cycle = 175


def _initialise(bot):
    plugins.register_user_command(
        ["allcheckpoints", "allcp", "nextcp", "nextcheckpoint", "nextcycle", "mappin", "getdean", "dist", "distance"])
    plugins.register_admin_command(["settimezone", "addpasscodehangout", "removepasscodehangout", "pc", "whois"])
    os.environ['TZ'] = 'UTC'
    time.tzset()


def _getTimeZone(bot, event):
    timezone = 'America/Edmonton'
    if bot.memory.exists(["conv_data", event.conv.id_]):
        if (bot.memory.exists(["conv_data", event.conv.id_, "timezone"])):
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
# Get Admin stuff
#####################

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
    yield from bot.coro_send_message(event.conv, "The next checkpoint is at {:%I:%M%p %Y-%m-%d}".format(
        checkpoint_start.astimezone(tz)))


def nextcheckpoint(bot, event, *args):
    """Returns the time that the next checkpoint will occur. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from nextcp(bot, event, *args)


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

def mappin(bot, event, *args):
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
        yield from bot.coro_send_message(event.conv,"Unable to parse the provided intel link. Make sure it is a link to a portal and try again.")
        return

    yield from bot.coro_send_message(event.conv, "https://maps.google.com/maps?q=" + coords[1])


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


def removepasscodehangout(bot, event, *args):
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
        yield from bot.coro_send_message(event.conv_id,
                                         _('The hangout has been removed from the list to recieve passcodes.'))


def pc(bot, event, *args):
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
        logger.info("Sent the pass code '{}' to hangout {}".format(passcodes, ho))

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
            text = "<a href='https://plus.google.com/u/0/{}/about'>{}</a>".format(user_data['_hangups']['gaia_id'],
                                                                                  user_data['_hangups']['full_name'])
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

def dist(bot, event, *args):
    """
    Calculates the distance in KM between 2 portals by using the intel links to those portals. Will also give the minimum requirements to make the link.
    /ada dist <portal link 1> <portal link 2>
    """
    yield from distance(bot, event, *args)

def distance(bot, event, *args):
    """
    Calculates the distance in KM between 2 portals by using the intel links to those portals. Will also give the minimum requirements to make the link.
    /ada distance <portal link 1> <portal link 2>
    """
    if not args or len(args) < 2:
        yield from bot.coro_send_message(event.conv_id,"Not enough portal links were provided. Requires 2 links to calculate the distance.")
        return

    coord1 = _getCoordsFromUrl(args[0])
    coord2 = _getCoordsFromUrl(args[1])

    if not coord1 or not coord2:
        yield from bot.coro_send_message(event.conv_id, "Links provided are not valid intel links.")
        return

    earthRadius = 6371e3
    theta1 = math.radians(float(coord1[0]))
    theta2 = math.radians(float(coord2[0]))
    delta1 = math.radians(float(coord2[0]) - float(coord1[0]))
    delta2 = math.radians(float(coord2[1]) - float(coord1[1]))

    a = math.sin(delta1/2) * math.sin(delta1/2) + math.cos(theta1) * math.cos(theta2) * math.sin(delta2/2) * math.sin(delta2/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = earthRadius * c
    linkReq = _getLinkRequirements(d)

    yield from bot.coro_send_message(event.conv_id, "The portals are <b>{0:.2f} km</b> apart.<br/>{1}".format(d/1000, linkReq))

def _getCoordsFromUrl(url):
    coords = url.split("pll=")
    if len(coords) != 2:
        return False
    latlng = re.match("-?[1-9]+\.[0-9]+,-?[1-9]+\.[0-9]+", coords[1])
    if not latlng:
        return False
    return coords[1].split(",")

def _getLinkRequirements(distance):
    minPortalLevel = math.ceil(math.pow(distance/160,1/4))
    l5Max = 160 * math.pow(5, 4)
    l6Max = 160 * math.pow(6, 4)
    l7Max = 160 * math.pow(7, 4)
    l8Max = 160 * math.pow(8, 4)
    result = "<br/>Minimum Link Requirements:<br/>"

    if minPortalLevel <= 8:
        result += "<b>Level {} portal</b> no mods.".format(minPortalLevel)

    if minPortalLevel > 5 and distance <= (l5Max * 8.75):
        mods = ""
        ratio = round(distance/l5Max, 2)
        if ratio <= 2:
            mods = "1 Rare Link Amp"
        elif ratio <= 2.5:
            mods = "2 Rare Link Amps"
        elif ratio <= 5:
            mods = "1 Softbank Ultra Link Amp"
        elif ratio <= 6.25:
            mods = "2 Softbank Ultra Link Amps"
        elif ratio <= 7:
            mods = "1 Very Rare Link Amp"
        elif ratio <= 8.75:
            mods = "2 Very Rare Link Amps"

        result += "<br/><b>Level 5 portal</b> with {}.".format(mods)

    if minPortalLevel > 6 and distance <= (l6Max * 10.5):
        result += _portalMods2People(distance, 6, l6Max)
    if minPortalLevel > 7 and distance <= (l7Max * 10.5):
        result += _portalMods2People(distance, 7, l7Max)
    if minPortalLevel > 8 and distance <= (l8Max * 10.5):
        result += _portalMods2People(distance, 8, l8Max)
    if minPortalLevel > 8 and distance > (l8Max * 10.5):
        result += "Portals are too far apart to link together."

    return result

def _portalMods2People(distance, portalLevel, maxDistance):
    mods = ""
    ratio = round(distance / maxDistance, 2)
    if ratio <= 2:
        mods = "1 Rare Link Amp"
    elif ratio <= 2.5:
        mods = "2 Rare Link Amps"
    elif ratio <= 2.75:
        mods = "3 Rare Link Amps"
    elif ratio <= 3:
        mods = "4 Rare Link Amps"
    elif ratio <= 5:
        mods = "1 Softbank Ultra Link Amp"
    elif ratio <= 6.25:
        mods = "2 Softbank Ultra Link Amps"
    elif ratio <= 6.825:
        mods = "3 Softbank Ultra Link Amps"
    elif ratio <= 7:
        mods = "1 Very Rare Link Amp or 4 Softbank Ultra Link Amps"
    elif ratio <= 7.5:
        mods = "4 Softbank Ultra Link Amps"
    elif ratio <= 8.75:
        mods = "2 Very Rare Link Amps"
    elif ratio <= 9.625:
        mods = "3 Very Rare Link Amps"
    elif ratio <= 10.5:
        mods = "4 Very Rare Link Amps"

    if portalLevel > 8:
        portalLevel = 8

    return "<br/><b>Level {} portal</b> with {}.".format(portalLevel, mods)