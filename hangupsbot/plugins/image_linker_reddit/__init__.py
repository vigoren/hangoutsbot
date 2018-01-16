"""trigger popular reddit meme images
based on the word/image list for the image linker bot on reddit
sauce: http://www.reddit.com/r/image_linker_bot/comments/2znbrg/image_suggestion_thread_20/
"""
import aiohttp, io, logging, os, random, re, json, ftplib, time

import plugins


logger = logging.getLogger(__name__)


_lookup = {}


def _initialise(bot):
    _load_triggers()
    plugins.register_admin_command(["redditmemeword", "addredditimage", "uploadimage"])
    plugins.register_handler(_scan_for_triggers)
    bot.register_shared("plugin_image_linker_reddit_shared", tldr_shared)


def redditmemeword(bot, event, *args):
    """trigger popular reddit meme images (eg. type 'slowclap.gif').
    Full list at http://goo.gl/ORmisN"""
    if len(args) == 1:
        image_link = _get_a_link(args[0])
    yield from bot.coro_send_message(event.conv_id, "this one? {}".format(image_link))

def scan_shared(bot, args):
    if not isinstance(args, dict):
        raise TypeError("args must be a dictionary")

    if 'params' not in args:
        raise KeyError("'params' key missing in args")

    if 'conv_id' not in args:
        raise KeyError("'conv_id' key missing in args")

    params = args['params']
    conv_id = args['conv_id']

    return_data = _scan(bot, conv_id, params)

    return return_data

def _scan(bot, conv_id, args):
    limit = 3
    count = 0
    lctext = event.text.lower()
    image_links = []
    for trigger in _lookup:
        pattern = '\\b' + trigger + '\.(jpg|png|gif|bmp)\\b'
        if re.search(pattern, lctext):
            image_links.append(_get_a_link(trigger))
            count = count + 1
            if count >= limit:
                break

    image_links = list(set(image_links))  # make unique
    if len(image_links) > 0:
        for image_link in image_links:
            if "gfycat.com/" in image_link:
                r = aiohttp.request('get', image_link)
                raw = r.read()
                image_link = re.search("href=\"(.*?)\">GIF</a>", str(raw, 'utf-8')).group(1)
            filename = os.path.basename(image_link)
            r = aiohttp.request('get', image_link)
            raw = r.read()
            image_data = io.BytesIO(raw)
            logger.debug("uploading: {}".format(filename))
            image_id = bot._client.upload_image(image_data, filename=filename)
            return image_id
    return  None

def _scan_for_triggers(bot, event, command):
    image_id = _scan(bot, event.conv_id, command)
    if image_id is not None:
            yield from bot.coro_send_message(event.conv.id_, None, image_id=image_id)


def _get_a_link(trigger):
    if trigger in _lookup:
        return random.choice(_lookup[trigger])
    return False

def _load_triggers():
    plugin_dir = os.path.dirname(os.path.realpath(__file__))
    source_file = os.path.join(plugin_dir, "sauce.json")
    with open(source_file) as f:
        data = json.load(f)
        for group in data:
            triggers = group["triggers"]
            images = group["images"]
            for trigger in triggers:
                if trigger in _lookup:
                    _lookup[trigger].extend(images)
                else:
                    _lookup[trigger] = images
    logger.info("{} trigger(s) loaded".format(len(_lookup)))


def addredditimage(bot, event, *args):
    """
    Adds an image to the bot for the image linker.
     /ada addredditimage <trigger> <image url>
    """
    if len(args) < 2:
        yield from bot.coro_send_message(event.conv_id, "You must supply a trigger word and a link to the image to be added.")
        return
    if not re.match('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', args[1]):
        yield from bot.coro_send_message(event.conv_id, "The second argument is not a valid URL.")
        return

    triggerWord = args[0].lower()
    imageUrl = args[1]

    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "sauce.json"), "r+") as json_data:
        data = json.load(json_data)
        found = False
        for i, group in enumerate(data):
            if group["triggers"]:
                for trigger in group["triggers"]:
                    if trigger == args[0].lower():
                        found = True
                        break
                if found:
                    data[i]["images"].append(imageUrl)
                    break
        if not found:
            data.append({"triggers": [triggerWord], "images": [imageUrl]})

        if triggerWord in _lookup:
            _lookup[triggerWord].extend([imageUrl])
        else:
            _lookup[triggerWord] = [imageUrl]

        json_data.seek(0)
        json.dump(data, json_data)
        json_data.close()
        yield from bot.coro_send_message(event.conv_id, "Trigger Count: {}".format(len(_lookup)))

def uploadimage(bot, event, *args):
    if not args:
        yield from bot.coro_send_message(event.conv_id, "No image url specified.")
        return
    config = bot.get_config_option('image_linker_reddit')
    if not config or not "ftp_url" in config or not "ftp_user" in config or not "ftp_pass" in config or not "upload_url_prefix" in config:
        yield from bot.coro_send_message(event.conv_id, "Config is not set up for uploading images.")
        return
    image_link = args[0]
    filename = str(int(time.time())) + "_" + os.path.basename(image_link)
    r = yield from aiohttp.request('get', image_link)
    raw = yield from r.read()
    image_data = io.BytesIO(raw)
    session = ftplib.FTP(config["ftp_url"],config["ftp_user"],config["ftp_pass"])
    session.storbinary('STOR ' + filename, image_data)
    image_data.close()
    session.quit()
    yield from bot.coro_send_message(event.conv_id, "Link: {}{}".format(config["upload_url_prefix"],filename))