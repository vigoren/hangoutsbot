# A Sync plugin for Telegram and Hangouts

import os, logging
import io
import asyncio
import hangups
import plugins
import aiohttp
import telepot
import telepot.async
from handlers import handler
from commands import command
import random

logger = logging.getLogger(__name__)


# TELEGRAM BOT

class TelegramBot(telepot.async.Bot):
    def __init__(self, token, hangupsbot):
        super(TelegramBot, self).__init__(token)
        self.commands = {}
        self.onMessageCallback = TelegramBot.on_message
        self.onPhotoCallback = TelegramBot.on_photo
        self.onUserJoinCallback = TelegramBot.on_user_join
        self.onUserLeaveCallback = TelegramBot.on_user_leave
        self.onLocationShareCallback = TelegramBot.on_location_share
        self.ho_bot = hangupsbot

    def add_command(self, cmd, func):
        self.commands[cmd] = func

    def remove_command(self, cmd):
        if cmd in self.commands:
            del self.commands[cmd]

    @staticmethod
    def is_command(msg):
        if 'text' in msg:
            if msg['text'].startswith('/'):
                return True
        return False

    @staticmethod
    def parse_command(cmd):
        txt_split = cmd.split()
        return txt_split[0].split("@")[0], txt_split[1:]

    @staticmethod
    def on_message(bot, chat_id, msg):
        print("[MSG] {uid} : {txt}".format(uid=msg['from']['id'], txt=msg['text']))

    @staticmethod
    def on_photo(bot, chat_id, msg):
        print("[PIC]{uid} : {photo_id}".format(uid=msg['from']['id'], photo_id=msg['photo'][0]['file_id']))

    @staticmethod
    def on_user_join(bot, chat_id, msg):
        print("New User: {name}".format(name=msg['left_chat_participant']['first_name']))

    @staticmethod
    def on_user_leave(bot, chat_id, msg):
        print("{name} Left the gorup".format(name=msg['left_chat_participant']['first_name']))

    @staticmethod
    def on_location_share(bot, chat_id, msg):
        print("{name} shared a location".format(name=msg['left_chat_participant']['first_name']))

    def set_on_message_callback(self, func):
        self.onMessageCallback = func

    def set_on_photo_callback(self, func):
        self.onPhotoCallback = func

    def set_on_user_join_callback(self, func):
        self.onUserJoinCallback = func

    def set_on_user_leave_callback(self, func):
        self.onUserLeaveCallback = func

    def set_on_location_share_callback(self, func):
        self.onLocationShareCallback = func

    @asyncio.coroutine
    def handle(self, msg):
        flavor = telepot.flavor(msg)

        if flavor == "normal":  # normal message
            content_type, chat_type, chat_id = telepot.glance2(msg)
            if content_type == 'text':
                if TelegramBot.is_command(msg):  # bot command
                    cmd, params = TelegramBot.parse_command(msg['text'])
                    if cmd in self.commands:
                        yield from self.commands[cmd](self, chat_id, params)
                    else:
                        yield from self.sendMessage(chat_id, "Unknown command: {cmd}".format(cmd=cmd))

                else:  # plain text message
                    yield from self.onMessageCallback(self, chat_id, msg)

            elif content_type == 'location':
                yield from self.onLocationShareCallback(self, chat_id, msg)

            elif content_type == 'new_chat_participant':
                yield from self.onUserJoinCallback(self, chat_id, msg)

            elif content_type == 'left_chat_participant':
                yield from self.onUserLeaveCallback(self, chat_id, msg)

            elif content_type == 'photo':
                yield from self.onPhotoCallback(self, chat_id, msg)

        elif flavor == "inline_query":  # inline query e.g. "@gif cute panda"
            query_id, from_id, query_string = telepot.glance2(msg, flavor=flavor)
            print("inline_query")

        elif flavor == "chosen_inline_result":
            result_id, from_id, query_string = telepot.glance2(msg, flavor=flavor)
            print("chosen_inline_result")

        else:
            raise telepot.BadFlavor(msg)


def tg_util_get_group_name(msg):
    """
    :param msg: msg object from telepot
    :return: if msg sent to a group, will return Groups name, return msg type otherwise
    """
    title = msg['chat']['type']
    if title == 'group':
        title = msg['chat']['title']
    return title


def tg_util_get_photo_caption(msg):
    caption = ""
    if 'caption' in msg:
        caption = msg['caption']

    return caption


def tg_util_get_photo_list(msg):
    photos = []
    if 'photo' in msg:
        photos = msg['photo']
        photos = sorted(photos, key=lambda k: k['width'])

    return photos


def tg_util_location_share_get_lat_long(msg):
    lat = ""
    long = ""
    if 'location' in msg:
        loc = msg['location']
        lat = loc['latitude']
        long = loc['longitude']

    return lat, long


def tg_util_create_gmaps_url(lat, long, https=True):
    return "{https}://maps.google.com/maps?q={lat},{long}".format(https='https' if https else 'http', lat=lat,
                                                                  long=long)


@asyncio.coroutine
def tg_on_message(tg_bot, tg_chat_id, msg):
    tg2ho_dict = tg_bot.ho_bot.memory.get_by_path(['telesync_tg2ho'])

    if str(tg_chat_id) in tg2ho_dict:
        text = "<b>{uname}</b> <b>({gname})</b>: {text}".format(uname=msg['from']['first_name'],
                                                                gname=tg_util_get_group_name(msg),
                                                                text=msg['text'])

        ho_conv_id = tg2ho_dict[str(tg_chat_id)]
        yield from tg_bot.ho_bot.coro_send_message(ho_conv_id, text)

        logger.info("[TELESYNC] Telegram message forwarded: {msg} to: {ho_conv_id}".format(msg=msg['text'],
                                                                                           ho_conv_id=ho_conv_id))


@asyncio.coroutine
def tg_on_photo(tg_bot, tg_chat_id, msg):
    tg2ho_dict = tg_bot.ho_bot.memory.get_by_path(['telesync_tg2ho'])

    if str(tg_chat_id) in tg2ho_dict:
        ho_conv_id = tg2ho_dict[str(tg_chat_id)]

        photos = tg_util_get_photo_list(msg)
        photo_caption = tg_util_get_photo_caption(msg)

        photo_id = photos[len(photos) - 1]['file_id']  # get photo id so we can download it

        # TODO: find a better way to handling file paths
        photo_path = 'hangupsbot/plugins/telesync/telesync_photos/' + photo_id + ".jpg"

        text = "Uploading photo from <b>{uname}</b> in <b>{gname}</b>...".format(uname=msg['from']['first_name'],
                                                                                 gname=tg_util_get_group_name(msg))
        yield from tg_bot.ho_bot.coro_send_message(ho_conv_id, text)

        file_dir = os.path.dirname(photo_path)
        if not os.path.exists(file_dir):
            os.makedirs(file_dir)

        yield from tg_bot.downloadFile(photo_id, photo_path)

        logger.info("[TELESYNC] Uploading photo...")
        with open(photo_path, "rb") as photo_file:
            ho_photo_id = yield from tg_bot.ho_bot._client.upload_image(photo_file,
                                                                        filename=os.path.basename(photo_path))

        yield from tg_bot.ho_bot.coro_send_message(ho_conv_id, photo_caption, image_id=ho_photo_id)

        logger.info("[TELESYNC] Upload succeed.")

        if tg_bot.ho_bot.config.get_by_path(['telesync_do_not_keep_photos']):
            os.remove(photo_path)  # don't use unnecessary space on disk


@asyncio.coroutine
def tg_on_user_join(tg_bot, tg_chat_id, msg):
    tg2ho_dict = tg_bot.ho_bot.memory.get_by_path(['telesync_tg2ho'])
    if str(tg_chat_id) in tg2ho_dict:
        text = "<b>{uname}</b> joined <b>{gname}</b>".format(uname=msg['new_chat_participant']['first_name'],
                                                             gname=tg_util_get_group_name(msg))

        ho_conv_id = tg2ho_dict[str(tg_chat_id)]
        yield from tg_bot.ho_bot.coro_send_message(ho_conv_id, text)

        # yield from tg_bot.sendMessage(tg_chat_id, text)

        logger.info("[TELESYNC] {text}".format(text=text))


@asyncio.coroutine
def tg_on_user_leave(tg_bot, tg_chat_id, msg):
    tg2ho_dict = tg_bot.ho_bot.memory.get_by_path(['telesync_tg2ho'])
    if str(tg_chat_id) in tg2ho_dict:
        text = "<b>{uname}</b> left <b>{gname}</b>".format(uname=msg['left_chat_participant']['first_name'],
                                                           gname=tg_util_get_group_name(msg))

        ho_conv_id = tg2ho_dict[str(tg_chat_id)]
        yield from tg_bot.ho_bot.coro_send_message(ho_conv_id, text)

        # yield from tg_bot.sendMessage(tg_chat_id, text)

        logger.info("[TELESYNC] {text}".format(text=text))


@asyncio.coroutine
def tg_on_location_share(tg_bot, tg_chat_id, msg):
    lat, long = tg_util_location_share_get_lat_long(msg)
    maps_url = tg_util_create_gmaps_url(lat, long)

    tg2ho_dict = tg_bot.ho_bot.memory.get_by_path(['telesync_tg2ho'])

    if str(tg_chat_id) in tg2ho_dict:
        text = "<b>{uname}</b> <b>({gname})</b>: {text}".format(uname=msg['from']['first_name'],
                                                                gname=tg_util_get_group_name(msg),
                                                                text=maps_url)

        ho_conv_id = tg2ho_dict[str(tg_chat_id)]
        yield from tg_bot.ho_bot.coro_send_message(ho_conv_id, text)

        logger.info("[TELESYNC] Telegram location forwarded: {msg} to: {ho_conv_id}".format(msg=maps_url,
                                                                                            ho_conv_id=ho_conv_id))


def tg_command_whereami(bot, chat_id, params):
    yield from bot.sendMessage(chat_id, "current group's id: {chat_id}".format(chat_id=chat_id))


def tg_command_set_sync_ho(bot, chat_id, params):  # /setsyncho <hangout conv_id>

    if len(params) != 1:
        yield from bot.sendMessage(chat_id, "Illegal or Missing arguments!!!")
        return

    tg2ho_dict = bot.ho_bot.memory.get_by_path(['telesync_tg2ho'])
    ho2tg_dict = bot.ho_bot.memory.get_by_path(['telesync_ho2tg'])

    tg2ho_dict[str(chat_id)] = str(params[0])
    ho2tg_dict[str(params[0])] = str(chat_id)

    bot.ho_bot.memory.set_by_path(['telesync_tg2ho'], tg2ho_dict)
    bot.ho_bot.memory.set_by_path(['telesync_ho2tg'], ho2tg_dict)

    yield from bot.sendMessage(chat_id, "Sync target set to {ho_conv_id}".format(ho_conv_id=str(params[0])))


def tg_command_clear_sync_ho(bot, chat_id, params):
    tg2ho_dict = bot.ho_bot.memory.get_by_path(['telesync_tg2ho'])
    ho2tg_dict = bot.ho_bot.memory.get_by_path(['telesync_ho2tg'])

    if str(chat_id) in tg2ho_dict:
        ho_conv_id = tg2ho_dict[str(chat_id)]
        del tg2ho_dict[str(chat_id)]
        del ho2tg_dict[ho_conv_id]

    bot.ho_bot.memory.set_by_path(['telesync_tg2ho'], tg2ho_dict)
    bot.ho_bot.memory.set_by_path(['telesync_ho2tg'], ho2tg_dict)

    yield from bot.sendMessage(chat_id, "Sync target cleared")


# TELEGRAM DEFINITIONS END

# HANGOUTSBOT

tg_bot = None


def _initialise(bot):
    print(os.getcwd())

    if not bot.config.exists(['telegram_bot_api_key']):
        bot.config.set_by_path(['telegram_bot_api_key'], "PUT_YOUR_TELEGRAM_API_KEY_HERE")

    # Don't keep photos on disk after sync done by default
    if not bot.config.exists(['telesync_do_not_keep_photos']):
        bot.config.set_by_path(['telesync_do_not_keep_photos'], True)

    if not bot.memory.exists(['telesync_ho2tg']):
        bot.memory.set_by_path(['telesync_ho2tg'], {})

    if not bot.memory.exists(['telesync_tg2ho']):
        bot.memory.set_by_path(['telesync_tg2ho'], {})

        # plugins.register_admin_command(["telesync"])

    global tg_bot
    tg_bot_token = bot.config.get_by_path(['telegram_bot_api_key'])

    loop = asyncio.get_event_loop()

    tg_bot = TelegramBot(tg_bot_token, bot)
    tg_bot.set_on_message_callback(tg_on_message)
    tg_bot.set_on_photo_callback(tg_on_photo)
    tg_bot.set_on_user_join_callback(tg_on_user_join)
    tg_bot.set_on_user_leave_callback(tg_on_user_leave)
    tg_bot.set_on_location_share_callback(tg_on_location_share)
    tg_bot.add_command("/whereami", tg_command_whereami)
    tg_bot.add_command("/setsyncho", tg_command_set_sync_ho)
    tg_bot.add_command("/clearsyncho", tg_command_clear_sync_ho)

    loop.create_task(tg_bot.messageLoop())


@command.register(admin=True)
def telesync(bot, event, *args):
    """
    /bot telesync <telegram chat id> - set sync with telegram group
    /bot telesync - disable sync and clear sync data from memory
    """
    parameters = list(args)

    tg2ho_dict = bot.memory.get_by_path(['telesync_tg2ho'])
    ho2tg_dict = bot.memory.get_by_path(['telesync_ho2tg'])

    if len(parameters) > 1:
        yield from bot.coro_send_message(event.conv_id, "Too many arguments")

    elif len(parameters) == 0:
        if str(event.conv_id) in ho2tg_dict:
            tg_chat_id = ho2tg_dict[str(event.conv_id)]
            del ho2tg_dict[str(event.conv_id)]
            del tg2ho_dict[str(tg_chat_id)]

        yield from bot.coro_send_message(event.conv_id, "Sync target cleared")

    elif len(parameters) == 1:
        tg_chat_id = str(parameters[0])
        tg2ho_dict[str(tg_chat_id)] = str(event.conv_id)
        ho2tg_dict[str(event.conv_id)] = str(tg_chat_id)
        yield from bot.coro_send_message(event.conv_id,
                                         "Sync target set to {tg_conv_id}".format(tg_conv_id=str(tg_chat_id)))

    else:
        raise RuntimeError("plugins/telesync: it seems something really went wrong, you should not see this error")

    bot.memory.set_by_path(['telesync_tg2ho'], tg2ho_dict)
    bot.memory.set_by_path(['telesync_ho2tg'], ho2tg_dict)


def is_valid_image_link(url):
    if ' ' in url:
        return False

    url = url.lower()
    if url.startswith('http://') or url.startswith('https://'):
        if url.endswith((".jpg", ".gif", ".gifv", ".webm", ".png", ".mp4")):
            return True
    else:
        return False


def get_photo_extension(file_name):
    return ".{}".format(file_name.rpartition('.')[-1])


def is_animated_photo(file_name):
    return True if get_photo_extension(file_name).endswith((".gif", ".gifv", ".webm", ".mp4")) else False


@handler.register(priority=5, event=hangups.ChatMessageEvent)
def _on_hangouts_message(bot, event, command=""):
    global tg_bot

    if event.text.startswith('/'):  # don't sync /bot commands
        return

    has_photo = False
    sync_text = event.text
    photo_url = ""

    if is_valid_image_link(sync_text):
        photo_url = sync_text
        sync_text = "(shared an image)"
        has_photo = True

    ho2tg_dict = bot.memory.get_by_path(['telesync_ho2tg'])

    if event.conv_id in ho2tg_dict:
        user_gplus = 'https://plus.google.com/u/0/{uid}/about'.format(uid=event.user_id.chat_id)
        text = "[{uname}]({user_gplus}) *({gname})*: {text}".format(uname=event.user.full_name,
                                                                    user_gplus=user_gplus,
                                                                    gname=event.conv.name, text=sync_text)
        yield from tg_bot.sendMessage(ho2tg_dict[event.conv_id], text, parse_mode='Markdown',
                                      disable_web_page_preview=True)
        if has_photo:
            photo_name = photo_url.rpartition('/')[-1]
            photo_ext = get_photo_extension(photo_url)
            photo_name = photo_name.replace(photo_ext, '-{rand}{ext}'.format(
                rand=random.randint(1, 100000), ext=photo_ext))
            photo_path = 'hangupsbot/plugins/telesync/telesync_photos/' + photo_name

            file_dir = os.path.dirname(photo_path)
            if not os.path.exists(file_dir):
                os.makedirs(file_dir)

            with aiohttp.ClientSession() as session:
                resp = yield from session.get(photo_url)
                raw_data = yield from resp.read()
                with open(photo_path, "wb") as f:
                    f.write(raw_data)

                if is_animated_photo(photo_path):
                    yield from tg_bot.sendDocument(ho2tg_dict[event.conv_id], open(photo_path, 'rb'))
                else:
                    yield from tg_bot.sendPhoto(ho2tg_dict[event.conv_id], open(photo_path, 'rb'))

            if tg_bot.ho_bot.config.get_by_path(['telesync_do_not_keep_photos']):
                os.remove(photo_path)  # don't use unnecessary space on disk


def create_membership_change_message(user_name, user_gplus, group_name, membership_event="left"):
    text = "[{uname}]({user_gplus}) {membership_event} *({gname})*".format(uname=user_name, user_gplus=user_gplus,
                                                                           gname=group_name,
                                                                           membership_event=membership_event)
    return text


@handler.register(priority=5, event=hangups.MembershipChangeEvent)
def _on_membership_change(bot, event, command=""):
    # Generate list of added or removed users
    event_users = [event.conv.get_user(user_id) for user_id
                   in event.conv_event.participant_ids]
    names = ', '.join([user.full_name for user in event_users])

    user_gplus = 'https://plus.google.com/u/0/{uid}/about'.format(uid=event.user_id.chat_id)

    membership_event = "joined" if event.conv_event.type_ == hangups.MembershipChangeType.JOIN else "left"
    text = create_membership_change_message(names, user_gplus, event.conv.name, membership_event)

    ho2tg_dict = bot.memory.get_by_path(['telesync_ho2tg'])

    if event.conv_id in ho2tg_dict:
        yield from tg_bot.sendMessage(ho2tg_dict[event.conv_id], text, parse_mode='Markdown',
                                      disable_web_page_preview=True)
