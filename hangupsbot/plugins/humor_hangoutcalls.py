import time
import plugins
import hangups
import aiohttp, io, logging, os, re

def _initialise(bot):
    plugins.register_handler(on_hangout_call, type="call")


def on_hangout_call(bot, event, command):
    if event.conv_event._event.hangout_event.event_type == hangups.schemas.ClientHangoutEventType.END_HANGOUT:
        lastcall = bot.conversation_memory_get(event.conv_id, "lastcall")

        if lastcall:
            lastcaller = lastcall["caller"]
            since = int(time.time() - lastcall["timestamp"])
            image_id = yield from _getOnyxCallerImageId(bot,since)

            if since < 120:
                humantime = "{} seconds".format(since)
            elif since < 7200:
                humantime = "{} minutes".format(since // 60)
            elif since < 172800:
                humantime = "{} hours".format(since // 3600)
            else:
                humantime = "{} days".format(since // 86400)

            if bot.conversations.catalog[event.conv_id]["type"] == "ONE_TO_ONE":
                """subsequent calls for a ONE_TO_ONE"""
                yield from bot.coro_send_message(event.conv_id,
                    _("It's been <b>{}</b> since the last call.<br/>Lonely? I can't reply you as I don't have speech synthesis (or speech recognition either!)").format(humantime),image_id=image_id)

            else:
                """subsequent calls for a GROUP"""
                yield from bot.coro_send_message(event.conv_id,
                    _("It's been <b>{}</b> since the last call. The last caller was <i>{}</i>. They earned a nice shiny badge!").format(humantime, lastcaller),image_id=image_id)

        else:
            """first ever call for any conversation"""
            yield from bot.coro_send_message(event.conv_id,
                _("First caller? No prizes for you, better luck next time."))

        bot.conversation_memory_set(event.conv_id, "lastcall", { "caller": event.user.full_name, "timestamp": time.time() })

def _getOnyxCallerImageId(bot, time):
    medal = _chooseImageMedal(time)
    filename = os.path.basename("https://edmontonresistance.com/image/{}-video-caller.png".format(medal))
    r = yield from aiohttp.request('get', "https://edmontonresistance.com/image/{}-video-caller.png".format(medal))
    raw = yield from r.read()
    image_data = io.BytesIO(raw)
    image_id = yield from bot._client.upload_image(image_data, filename=filename)
    return image_id

def _chooseImageMedal(time):
    if time < 864000:
        return "bronze"
    elif time < 1728000:
        return "silver"
    elif time < 7776000:
        return "gold"
    elif time < 129600000:
        return "plat"
    else:
        return "onyx"
