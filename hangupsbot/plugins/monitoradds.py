"""
Plugin for monitoring new adds to HOs and alerting if users were not added by an admin or mod.
Add mods to the config.json file either globally or on an individual HO basis.
Add a "watch_new_adds": true  parameter to individual HOs in the config.json file.

Author: @Riptides

Changed the shit out of this so that moderators are defined on a per hangout level.
If a hangout is being monitored is also done on a per hangout level rather then globally
Added some stuff so admins can specify which hangouts are moderated and users can pull a list of mods
"""
import logging

import hangups

import plugins


logger = logging.getLogger(__name__)


def _initialise(bot):
    plugins.register_handler(_watch_new_adds, type="membership")
    plugins.register_user_command(["getmoderators","getmods"])
    plugins.register_admin_command(["addmod", "delmod", "setmoderated"])


def _watch_new_adds(bot, event, command):
    # Check if watching for new adds is enabled
    if not bot.memory.exists(["conv_data", event.conv.id_]):
        return
    if not bot.memory.exists(["conv_data", event.conv.id_, 'watch_new_adds']):
        return
    if bot.memory.get_by_path(["conv_data", event.conv.id_, 'watch_new_adds']) is False:
        return

    # Generate list of added or removed users
    event_users = [event.conv.get_user(user_id) for user_id
                   in event.conv_event.participant_ids]
    names = ', '.join([user.full_name for user in event_users])

    # JOIN
    if event.conv_event.type_ == hangups.MembershipChangeType.JOIN:
        # Check if the user who added people is a mod or admin

        admins_list = bot.get_config_suboption(event.conv_id, 'admins')
        if event.user_id.chat_id in admins_list:
            return

        if not bot.memory.exists(["conv_data", event.conv.id_, 'mods']):
            return
        mods_list = bot.memory.get_by_path(["conv_data", event.conv.id_, 'mods']) or []

        try:
            if event.user_id.chat_id in mods_list:
                return
        except TypeError:
            # The mods are likely not configured. Continuing...
            pass

        modUsers = _getModerators(event, mods_list)
        html = _("<b>!!! WARNING !!!</b><br /><br /><b>{0}</b> invited <b>{1}</b> to the hangout <b>{2}</b> without authorization.<br />").format(event.user.full_name, names,bot.conversations.get_name(event.conv))
        print(modUsers)
        for user in modUsers:
           yield from _sendNotification(bot, html, user)

def _getModerators(event, mod_list):
    modUsers = []
    for user in event.conv.users:
        if user.id_.chat_id in mod_list:
            modUsers.append(user)
    return modUsers

def _sendNotification(bot, phrase, user):
    conv_1on1 = yield from bot.get_1to1(user.id_.chat_id)
    if conv_1on1:
        try:
            user_has_dnd = bot.call_shared("dnd.user_check", user.id_.chat_id)
        except KeyError:
            user_has_dnd = False
        if not user_has_dnd: # shared dnd check
            yield from bot.coro_send_message(
                conv_1on1,
                phrase)
            logger.info("{} ({}) alerted via 1on1 ({})".format(user.full_name, user.id_.chat_id, conv_1on1.id_))
        else:
            logger.info("{} ({}) has dnd".format(user.full_name, user.id_.chat_id))
    else:
        logger.warning("user {} ({}) could not be alerted via 1on1".format(user.full_name, user.id_.chat_id))

def setmoderated(bot, event, *args):
    """
Sets if the current hangout will be moderated or not, which means the bot will monitor people being added to the hangout and if they were not added by a moderator alert the moderators<br/>
<b>Parameters</b>:<br/> <i>[set]</i> Sets if it will be moderated: true for yes, false for no
    """
    #if bot.memory.get_by_path(['conv_data', event.conv.id_,'type']) == "ONE_TO_ONE":
    #    yield from bot.coro_send_message(event.conv,"Can not have moderators for a one to one message.")
    #    return
    if not bot.memory.exists(["conv_data", event.conv.id_]):
        bot.memory.set_by_path(['conv_data', event.conv.id_], {})

    watchNewAdds = ''.join(args).strip().lower()
    if watchNewAdds == "true":
        bot.memory.set_by_path(['conv_data', event.conv.id_,'watch_new_adds'], True)
        yield from bot.coro_send_message(event.conv, "This hangout is now being moderated, all people added must be done so by a mod.")
    else:
        bot.memory.set_by_path(['conv_data', event.conv.id_,'watch_new_adds'], False)
        yield from bot.coro_send_message(event.conv, "This hangout is no longer being moderated.")
    bot.memory.save()

def addmod(bot, event, *args):
    """add user id(s) to the whitelist of who can add to a hangout"""
    mod_ids = list(args)
    if not bot.memory.exists(["conv_data", event.conv.id_]):
        yield from bot.coro_send_message(event.conv,"This conversation doesn't exists...")
        return

    #if bot.memory.get_by_path(['conv_data', event.conv.id_,'type']) == "ONE_TO_ONE":
    #    yield from bot.coro_send_message(event.conv,"Can not have moderators for a one to one message.")
    #    return

    if not bot.memory.exists(["conv_data", event.conv.id_,'mods']):
        bot.memory.set_by_path(['conv_data', event.conv.id_,'mods'], {})

    curMods = bot.memory.get_by_path(['conv_data', event.conv.id_,'mods'])
    for mod in curMods:
        mod_ids.append(mod)
    bot.memory.set_by_path(['conv_data', event.conv.id_,'mods'], mod_ids)
    bot.memory.save()
    html_message = _("<i>Moderators updated: {} added</i>")
    yield from bot.coro_send_message(event.conv, html_message.format(args[0]))

def delmod(bot, event, *args):
    """remove user id(s) from the whitelist of who can add to a hangout"""
    if not bot.memory.exists(["conv_data", event.conv.id_]):
        return
    if not bot.memory.exists(["conv_data", event.conv.id_,'mods']):
        return

    mods = bot.memory.get_by_path(['conv_data', event.conv.id_,'mods'])
    mods_new = []
    for mod in mods:
        if args[0] != mod:
            mods_new.append(mod)

    bot.memory.set_by_path(['conv_data', event.conv.id_,'mods'], mods_new)
    bot.memory.save()
    html_message = _("<i>Moderators updated: {} removed</i>")
    yield from bot.coro_send_message(event.conv, html_message.format(args[0]))

def getmoderators(bot, event, *args):
    """Gets a list of moderators, with links to their G+ profile, for the current hangout"""
    mod_list = []
    if bot.memory.exists(["conv_data", event.conv.id_]):
        if bot.memory.exists(["conv_data", event.conv.id_, 'mods']):
            mod_list = bot.memory.get_by_path(["conv_data", event.conv.id_, 'mods'])

    if len(mod_list) > 0:
        modUsers = _getModerators(event,mod_list)
        modLinks = []
        for user in modUsers:
            line = '<b><a href="https://plus.google.com/u/0/{}/about">{}</a></b>'.format(user.id_.chat_id, user.full_name)
            modLinks.append(line)
        yield from bot.coro_send_message(event.conv, "Here are the moderators for this hangout:<br/>{}".format("<br />".join(modLinks)))
    else:
        yield from bot.coro_send_message(event.conv, "There are no moderators for this hangout")

def getmods(bot,event,*args):
    """Gets a list of moderators, with links to their G+ profile, for the current hangout"""
    yield from getmoderators(bot,event,args)
