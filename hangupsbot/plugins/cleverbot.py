import asyncio
import logging
import plugins
import requests
from random import randrange, randint


logger = logging.getLogger(__name__)

__cleverbots = dict()
_internal = {}


""" Cleverbot API adapted from https://github.com/folz/cleverbot.py """
class Cleverbot:
    """
    Wrapper over the Cleverbot API.
    """
    API_URL = "https://www.cleverbot.com/getreply"

    def __init__(self):
        """ The data that will get passed to Cleverbot's web API """
        self.data = {
            'key':  _internal["cleverbot_api_key"],
            'input': '',
            'cs': ''
        }

    def ask(self, question):
        """Asks Cleverbot a question.

        Maintains message history.

        Args:
            q (str): The question to ask
        Returns:
            Cleverbot's answer
        """
        # Set the current question
        question = question.strip()
        if not question:
            return

        if not question.endswith(("!", ",", ".", ")", "%", "*")):
            # end a sentence with a full stop
            question += "."

        question = question.encode("ascii", "xmlcharrefreplace")

        self.data['input'] = question

        # Connect to Cleverbot's API and remember the response
        resp = requests.get(self.API_URL, params=self.data)
        try:
            resp.raise_for_status()
            results = resp.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError, requests.exceptions.Timeout):
            logger.error('unable to connect with cleverbot.com: %d - %s', resp.status_code, resp.text)
            return None

        # Register the cs
        self.data['cs'] = results['cs']

        return results['output']


def _initialise(bot):
    api_key = bot.get_config_option('cleverbot_api_key')
    logger.info(bot.get_config_option('cleverbot_api_key'))
    if api_key:
        _internal["cleverbot_api_key"] = api_key
        plugins.register_handler(_handle_incoming_message, type="message")
        plugins.register_user_command(["chat"])
        plugins.register_admin_command(["chatreset"])
    else:
        logger.error('CLEVERBOT: config["celverbot_api_key"] required')


@asyncio.coroutine
def _handle_incoming_message(bot, event, command):
    """Handle random message intercepting"""

    if not event.text:
        return

    if not bot.get_config_suboption(event.conv_id, 'cleverbot_percentage_replies'):
        return

    percentage = bot.get_config_suboption(event.conv_id, 'cleverbot_percentage_replies')

    if randrange(0, 101, 1) < float(percentage):
        text = yield from cleverbot_ask(event.conv_id, event.text)
        if text:
            yield from bot.coro_send_message(event.conv_id, text)


def chat(bot, event, *args):
    """chat to Cleverbot"""
    if args:
        text = yield from cleverbot_ask(event.conv_id, ' '.join(args))
        if not text:
            text = _("<em>Cleverbot is silent</em>")

    else:
        text = _("<em>you have to say something to Cleverbot</em>")

    yield from bot.coro_send_message(event.conv_id, text)


def chatreset(bot, event, *args):
    if len(args) == 0:
        conv_id = event.conv_id
    else:
        conv_id = args[0]

    message = "no change"
    if conv_id in __cleverbots:
        del __cleverbots[conv_id]
        logger.debug("removed api instance for {}".format(conv_id))
        message = "removed {}".format(conv_id)

    yield from bot.coro_send_message(event.conv_id, message)


def cleverbot_ask(conv_id, message, filter_ads=True):
    if conv_id not in __cleverbots:
        __cleverbots[conv_id] = Cleverbot()
        logger.debug("added api instance for {}".format(conv_id))

    loop = asyncio.get_event_loop()

    text = False
    try:
        text = yield from loop.run_in_executor(None, __cleverbots[conv_id].ask, message)
        text = html.unescape(text)
        logger.debug("API returned: {}".format(text))
        if text:
            if filter_ads:
                if text.startswith("\n"):
                    # some ads appear to start with line breaks
                    text = False
                else:
                    # filter out specific ad-related keywords
                    ad_text = ["cleverscript", "cleverme", "clevertweet", "cleverenglish"]
                    for ad in ad_text:
                        if ad.lower() in text.lower():
                            logger.debug("ad-blocked")
                            text = False
                            break

    except:
        logger.exception("failed to get response")

    return text
