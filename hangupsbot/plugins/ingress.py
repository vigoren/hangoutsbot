import hangups, plugins, logging, os, time, pytz, re, math
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

serverTimeZone = pytz.timezone("UTC")
hours_per_cycle = 175


def _initialise(bot):
    plugins.register_user_command(["allcheckpoints", "allcp", "nextcp", "nextcheckpoint", "nextcycle", "mappin", "getdean", "dist", "distance", "opr"])
    plugins.register_admin_command(["settimezone", "addpasscodehangout", "removepasscodehangout", "pc", "whois"])
    bot.register_shared("plugin_ingress_allcp", allcp_shared)
    bot.register_shared("plugin_ingress_nextcp", nextcp_shared)
    bot.register_shared("plugin_ingress_nextcycle", nextcycle_shared)
    bot.register_shared("plugin_ingress_mappin", mappin_shared)
    bot.register_shared("plugin_ingress_dist", dist_shared)
    bot.register_shared("plugin_ingress_opr", opr_shared)
    os.environ['TZ'] = 'UTC'
    time.tzset()



############################
# Shared functions
############################

def allcp_shared(bot, args):
    if not isinstance(args, dict):
        raise TypeError("args must be a dictionary")

    if 'params' not in args:
        raise KeyError("'params' key missing in args")

    if 'conv_id' not in args:
        raise KeyError("'conv_id' key missing in args")

    params = args['params']
    conv_id = args['conv_id']

    return _allcp(bot, conv_id, params)

def nextcp_shared(bot, args):
    if not isinstance(args, dict):
        raise TypeError("args must be a dictionary")

    if 'params' not in args:
        raise KeyError("'params' key missing in args")

    if 'conv_id' not in args:
        raise KeyError("'conv_id' key missing in args")

    params = args['params']
    conv_id = args['conv_id']

    return _nextcp(bot, conv_id, params)\

def nextcycle_shared(bot, args):
    if not isinstance(args, dict):
        raise TypeError("args must be a dictionary")

    if 'params' not in args:
        raise KeyError("'params' key missing in args")

    if 'conv_id' not in args:
        raise KeyError("'conv_id' key missing in args")

    params = args['params']
    conv_id = args['conv_id']

    return _nextcycle(bot, conv_id, params)

def mappin_shared(bot, args):
    if not isinstance(args, dict):
        raise TypeError("args must be a dictionary")

    if 'params' not in args:
        raise KeyError("'params' key missing in args")

    if 'conv_id' not in args:
        raise KeyError("'conv_id' key missing in args")

    params = args['params']
    conv_id = args['conv_id']

    return _mappin(bot, conv_id, params)

def dist_shared(bot, args):
    if not isinstance(args, dict):
        raise TypeError("args must be a dictionary")

    if 'params' not in args:
        raise KeyError("'params' key missing in args")

    if 'conv_id' not in args:
        raise KeyError("'conv_id' key missing in args")

    params = args['params']
    conv_id = args['conv_id']

    return _dist(bot, conv_id, params)

def opr_shared(bot, args):
    if not isinstance(args, dict):
        raise TypeError("args must be a dictionary")

    if 'params' not in args:
        raise KeyError("'params' key missing in args")

    if 'conv_id' not in args:
        raise KeyError("'conv_id' key missing in args")

    params = args['params']
    conv_id = args['conv_id']

    return _opr(bot, conv_id, params)


def _getTimeZone(bot, conv_id):
    timezone = 'America/Edmonton'
    if bot.memory.exists(["conv_data", conv_id]):
        if (bot.memory.exists(["conv_data", conv_id, "timezone"])):
            timezone = bot.memory.get_by_path(["conv_data", conv_id, "timezone"])

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

def _allcp(bot, conv_id, args):
    tz = _getTimeZone(bot, conv_id)
    data = _getCycleData()
    checkpoint_times = map(lambda x: data['start'] + timedelta(hours=x), range(0, hours_per_cycle, 5))

    currentcpfound = False
    text = []
    text.append('All checkpoints for the current cycle:')

    for num, checkpoint in enumerate(checkpoint_times):
        if currentcpfound is False and checkpoint > data['now']:
            text.append('<b>Checkpoint {}: {:%I:%M%p %Y-%m-%d}</b>'.format(num + 1, checkpoint.astimezone(tz)))
            currentcpfound = True
        else:
            text.append('<i>Checkpoint {}</i>: {:%I:%M%p %Y-%m-%d}'.format(num + 1, checkpoint.astimezone(tz)))
    return "\n".join(text)


def allcheckpoints(bot, event, *args):
    """Returns a list of every checkpoint for the current cycle. The next checkpoint will be bolded. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from bot.coro_send_message(event.conv, _allcp(bot, event.conv_id, args))


def allcp(bot, event, *args):
    """Returns a list of every checkpoint for the current cycle. The next checkpoint will be bolded. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from bot.coro_send_message(event.conv, _allcp(bot, event.conv_id, args))


def _nextcp(bot, conv_id, args):
    tz = _getTimeZone(bot, conv_id)
    data = _getCycleData()
    cdelta = data['now'] - data['start']
    checkpoint = timedelta(hours=5)
    checkpoints = (cdelta // checkpoint) + 1
    checkpoint_start = data['start'] + (checkpoint * checkpoints)
    return "The next checkpoint is at {:%I:%M%p %Y-%m-%d}".format(checkpoint_start.astimezone(tz))

def nextcp(bot, event, *args):
    """Returns the time that the next checkpoint will occur. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from bot.coro_send_message(event.conv, _nextcp(bot, event.conv_id, args))


def nextcheckpoint(bot, event, *args):
    """Returns the time that the next checkpoint will occur. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from bot.coro_send_message(event.conv, _nextcp(bot, event.conv_id, args))


def _nextcycle(bot, conv_id, args):
    tz = _getTimeZone(bot, conv_id)
    data = _getCycleData()
    start = data['start'] + timedelta(hours=hours_per_cycle)
    return 'The first checkpoint of the next cycle is at {:%I:%M%p %Y-%m-%d}'.format(start.astimezone(tz))

def nextcycle(bot, event, *args):
    """Returns the time of the first checkpoint for the next cycle. The checkpoint times are shown for the time zone the hangout is set to."""
    yield from bot.coro_send_message(event.conv, _nextcycle(bot, event.conv_id, args))


#####################
# Maps stuff
#####################
def _mappin(bot, conv_id, args):
    url = ''.join(args).strip()
    coords = url.split("pll=")
    if not url or len(coords) != 2:
        return  "You need to provide an intel url for a portal."
    res = re.match("-?[0-9]+\.[0-9]+,-?[0-9]+\.[0-9]+", coords[1])
    if not res:
        return "Unable to parse the provided intel link. Make sure it is a link to a portal and try again."

    return "https://maps.google.com/maps?q=" + coords[1]

def mappin(bot, event, *args):
    """
    Takes an Ingress intel link for a portal and creates a Google maps pin to that location
    <b>/ada mappin <url></b>
    """
    text = _mappin(bot, event.conv_id, list(args))
    yield from bot.coro_send_message(event.conv, text)


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

    yield from bot.coro_send_message(event.conv_id, "\n".join(found_users))

#####################
# Distance Stuff
#####################
def _dist(bot, conv_id, args):
    if not args or len(args) < 2:
        return "Not enough portal links were provided. Requires 2 links to calculate the distance."

    coord1 = _getCoordsFromUrl(args[0])
    coord2 = _getCoordsFromUrl(args[1])

    if not coord1 or not coord2:
        return "Links provided are not valid intel links."

    earthRadius = 6371e3
    theta1 = math.radians(float(coord1[0]))
    theta2 = math.radians(float(coord2[0]))
    delta1 = math.radians(float(coord2[0]) - float(coord1[0]))
    delta2 = math.radians(float(coord2[1]) - float(coord1[1]))

    a = math.sin(delta1/2) * math.sin(delta1/2) + math.cos(theta1) * math.cos(theta2) * math.sin(delta2/2) * math.sin(delta2/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = earthRadius * c
    linkReq = _getLinkRequirements(d)

    return "The portals are <b>{0:.2f} km</b> apart.\n{1}".format(d/1000, linkReq)


def dist(bot, event, *args):
    """
    Calculates the distance in KM between 2 portals by using the intel links to those portals. Will also give the minimum requirements to make the link.
    /ada dist <portal link 1> <portal link 2>
    """
    yield from bot.coro_send_message(event.conv_id, _dist(bot, event.conv_id, list(args)))


def distance(bot, event, *args):
    """
    Calculates the distance in KM between 2 portals by using the intel links to those portals. Will also give the minimum requirements to make the link.
    /ada distance <portal link 1> <portal link 2>
    """
    yield from bot.coro_send_message(event.conv_id, _dist(bot, event.conv_id, list(args)))


def _getCoordsFromUrl(url):
    coords = url.split("pll=")
    if len(coords) != 2:
        return False
    latlng = re.match("-?[0-9]+\.[0-9]+,-?[0-9]+\.[0-9]+", coords[1])
    if not latlng:
        return False
    return coords[1].split(",")


def _getLinkRequirements(distance):
    minPortalLevel = math.ceil(math.pow(distance/160,1/4))
    l5Max = 160 * math.pow(5, 4)
    l6Max = 160 * math.pow(6, 4)
    l7Max = 160 * math.pow(7, 4)
    l8Max = 160 * math.pow(8, 4)
    result = "\nMinimum Link Requirements:\n"

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

        result += "\n<b>Level 5 portal</b> with {}.".format(mods)
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

    return "\n<b>Level {} portal</b> with {}.".format(portalLevel, mods)

#####################
# OPR Stuff
#####################
def _opr(bot, conv_id, args):
    if not args or len(args) < 1:
        return "No candidate name provided. Please provide the full or partial name of a candidate to see Niantics recomendations"
    term = ' '.join(args).strip().lower()
    data = [
        {
            "name": "Antique/Rustic Farm Equipment",
            "text": "<b>Antique/Rustic Farm Equipment</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT if on private residential property or a farm. ACCEPT if on display in a public park or museum and is visually unique or historic."
        },
        {
            "name": "Apartment/Development Sign",
            "text": "<b>Apartment/Development Sign</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless they are historic or have some significance."
        },
        {
            "name": "Cairn (Stacked Stone Monument)",
            "text": "<b>Cairn (Stacked Stone Monument)</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT if significant in size and unique and meets other criteria in terms of being publicly accessible and safe to access. Falls under the criteria of adventurous tourist attractions."
        },
        {
            "name": "Cemetery",
            "text": "<b>Cemetery</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless the cemetery is historical or has special significance in the community (see guidelines for gravestones/markers). "
        },
        {
            "name": "City/Street Sign",
            "text": "<b>City/Street Sign</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT regular street signs/city signs that have no historical significance"
        },
        {
            "name": "Exercise Equipment",
            "text": "<b>Exercise Equipment</b>\nPolicy: Accept\nSuggested Vote:<b>★★★</b>\nACCEPT if the candidate is in a park or community gathering place; falls under the criteria of public spaces that encourage walk and exercise. If there are multiple pieces of exercise equipment, ACCEPT one submission for the whole group and not for each individual piece of equipment."
        },
        {
            "name": "Fire Department",
            "text": "<b>Fire Department</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless the candidate is a memorial/museum that does not obstruct the path of the emergency vehicles. ACCEPT candidates in low density areas if it does not obstruct the path of the emergency vehicles."
        },
        {
            "name": "Fire Lookout Tower",
            "text": "<b>Fire Lookout Tower</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT if open to the public. Falls under the criteria of adventurous tourist attractions. REJECT lookout towers being used as private residences."
        },
        {
            "name": "Fountain",
            "text": "<b>Fountain</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT if it has pedestrian access, i.e. agents can walk up to it. REJECT spouts in the middle of the lake with no access."
        },
        {
            "name": "Gazebo",
            "text": "<b>Gazebo</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT if the candidate is in a park or community gathering place; falls under the criteria of public spaces that encourage walk and exercise. "
        },
        {
            "name": "Golf Course",
            "text": "<b>Golf Course</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT hole markers and other locations ON THE COURSE. ACCEPT if in areas where agents can sit and socialize (like cafes or club areas)."
        },
        {
            "name": "Gravestone",
            "text": "<b>Gravestone</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless the gravestone belongs to a famous/historic person or notable member of the local community and is more than 50 years old and community norms for use of the cemetery are open to historic visits and other uses."
        },
        {
            "name": "Highway Rest Area",
            "text": "<b>Highway Rest Area</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless the rest stop has any significance like being a popular tourist spot or a historic location. ACCEPT in low density areas if it has character or amenities."
        },
        {
            "name": "Historic home",
            "text": "<b>Historic home</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless the home is not a private residence and is open to the public."
        },
        {
            "name": "Hospital",
            "text": "<b>Hospital</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT if the candidate is on or inside the hospital building or is in any location where it could obstruct emergency services and access to the building. ACCEPT candidates in hospital gardens if they are not in the path of emergency vehicles."
        },
        {
            "name": "Hotel/Inn",
            "text": "<b>Hotel/Inn</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless the hotel/inn is historical, has an interesting story or is a unique local business."
        },
        {
            "name": "Mass Produced Corporate Art",
            "text": "<b>Mass Produced Corporate Art</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless the candidate has some significance such as being the first or having an interesting story behind it."
        },
        {
            "name": "Memorial Bench",
            "text": "<b>Memorial Bench</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless for a notable member of the community or in a low density area."
        },
        {
            "name": "Memorial/Dedication Plaque",
            "text": "<b>Memorial/Dedication Plaque</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless for a notable member of the community."
        },
        {
            "name": "Mountain Top Marker",
            "text": "<b>Mountain Top Marker</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT permanently attached logbooks, structures, or signs."
        },
        {
            "name": "Playground",
            "text": "<b>Playground</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT if the candidate is in a park or community gathering place; falls under the criteria of public spaces that encourage walk and exercise."
        },
        {
            "name": "Post Office",
            "text": "<b>Post Office</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT. Connects and unites people around the world."
        },
        {
            "name": "Ruin",
            "text": "<b>Ruin</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT. Falls under the criteria of tourist spots that showcase local flavor and culture and that make your city/neighborhood unique provided that the site is open and accessible to the public or can be accessed from an open sidewalk or viewing area."
        },
        {
            "name": "RV/Mobile Park",
            "text": "<b>RV/Mobile Park</b>\nPolicy: Reject\nSuggested Vote:<b>★</b>\nREJECT unless it is historical, a community gathering spot, has an interesting story or is a unique local business."
        },
        {
            "name": "Survey Marker",
            "text": "<b>Survey Marker</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT if on a trail or helps you explore the location. Falls under the criteria of off-the-beaten-path tourist attractions."
        },
        {
            "name": "Trail Marker",
            "text": "<b>Trail Marker</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT. Falls under the criteria of adventurous tourist attractions and encourages walk and exercise. "
        },
        {
            "name": "Water Tower",
            "text": "<b>Water Tower</b>\nPolicy: Accept\nSuggested Vote:<b>★★★★★</b>\nACCEPT if accessible without entering a restricted area, is uniquely decorated, or are otherwise a notable monument."
        }
    ]
    name = term.split(' ')
    result = []

    for n in name:
        for guide in data:
            if n.lower() in guide["name"].lower() and guide["text"] not in result:
                result.append(guide["text"])
    if len(result) == 0:
        result.append("No guideline matches found for <b>"+term+"</b>")

    return "\n\n".join(result)
    
    
def opr(bot, event, *args):
    """
    Returns information from Niantics OPR Guide about entries that match the entered text
    /ada opr <candidate name>
    """
    yield from bot.coro_send_message(event.conv_id, _opr(bot, event.conv_id, list(args)))