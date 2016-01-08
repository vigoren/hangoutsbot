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
            image_id = yield from _getOnyxCallerImageId(bot,event)

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
                    _("Badge earned!<br/>It's been <b>{}</b> since the last call. The last caller was <i>{}</i>.").format(humantime, lastcaller),image_id=image_id)

        else:
            """first ever call for any conversation"""
            yield from bot.coro_send_message(event.conv_id,
                _("First caller? No prizes for you, better luck next time."))

        bot.conversation_memory_set(event.conv_id, "lastcall", { "caller": event.user.full_name, "timestamp": time.time() })

def _getOnyxCallerImageId(bot,event):
    if bot.memory.exists(["conv_data", event.conv.id_, "onyx_call_image_id"]):
        return bot.memory.get_by_path(["conv_data", event.conv.id_, "onyx_call_image_id"])
    else:
        filename = os.path.basename("https://edmontonresistance.com/image/onyx-video-caller.jpg")
        r = yield from aiohttp.request('get', "https://edmontonresistance.com/image/onyx-video-caller.jpg")
        raw = yield from r.read()
        image_data = io.BytesIO(raw)
        image_id = yield from bot._client.upload_image(image_data, filename=filename)
        bot.memory.set_by_path(["conv_data", event.conv.id_, "onyx_call_image_id"], image_id)
        bot.memory.save()
        return image_id

