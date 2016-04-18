import hangups, plugins, logging, config, os

logger = logging.getLogger(__name__)

def _initialize(bot):
    settings = bot.get_config_option("analytics")
    if not settings["enabled"]:
        return
    if not settings["path"].endswith('/'):
        settings["path"] += "/"
    amp = AnalyticMessageParser(bot, settings["path"])
    if amp.initialized:
        plugins.register_handler(amp.on_message, type="allmessages")

class AnalyticMessageParser():
    initialized = False
    analyticsFilePath = ""
    botAliases = None
    allAnalytics = None

    def __init__(self, bot, filePath):
        self.botAliases = bot._handlers.bot_command
        self.analyticsFilePath = filePath
        if not self.analyticsFilePath:
            logger.warning("Missing config entry. \"analytics\"->\"path\":\"<Path to file folder>\"")
            return

        directory = os.path.dirname(self.analyticsFilePath)
        if directory and not os.path.isdir(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                logger.exception('cannot create path: {}'.format(self.analyticsFilePath))
                return
        self.allAnalytics = self._loadAnalytics("analytics.json")
        if self.allAnalytics is not None:
            self.initialized = True

    def _loadAnalytics(self, name):
        filePath = self.analyticsFilePath + name
        data = config.Config(filePath, failsafe_backups=1, save_delay=1)
        if not os.path.isfile(filePath):
            try:
                logger.info("creating analytics file: {}".format(filePath))
                data.force_taint()
                data.save()

            except (OSError, IOError) as e:
                logger.exception('Failed to create the analytics file: {}'.format(filePath))
                return None
        return data

    def on_message(self, bot, event, command):
        messageText = event.text.lower().split()
        if not messageText or event.user.is_self:
            return
        messageParts = self._parseMessage(messageText)
        self._logCall(messageParts, event.conv.id_, event.user.id_.chat_id)

    def _parseMessage(self, messageText):
        parts = {'commandName': "", 'args': "", 'text': ""}
        for alias in self.botAliases:
            if messageText[0] == alias and len(messageText) > 1:
                parts['commandName'] = messageText[1]
                parts['args'] = ' '.join(messageText[2:])
                break
        parts['text'] = ' '.join(messageText)
        return parts

    def _logCall(self, messageParts, convId, userId):
        hangoutUsage = 0
        userUsage = 0
        #If there is a command name set then a command was called
        if messageParts['commandName']:
            totalUsage = 0
            
            if not self.allAnalytics.exists(["commands"]):
                self.allAnalytics.set_by_path(['commands'], {})

            if not self.allAnalytics.exists(["commands", messageParts['commandName']]):
                self.allAnalytics.set_by_path(['commands', messageParts['commandName']], {})

            #Set/Increment the total calls for this command
            if self.allAnalytics.exists(["commands", messageParts['commandName'], "totalUsage"]):
                totalUsage = self.allAnalytics.get_by_path(["commands", messageParts['commandName'], "totalUsage"])
            totalUsage += 1
            self.allAnalytics.set_by_path(["commands", messageParts['commandName'], "totalUsage"], totalUsage)

            #Set/Increment the hangout specific calls for this command
            if not self.allAnalytics.exists(["commands", messageParts['commandName'], "hangoutUsage"]):
                self.allAnalytics.set_by_path(['commands', messageParts['commandName'], "hangoutUsage"], {})
            if self.allAnalytics.exists(["commands", messageParts['commandName'], "hangoutUsage", convId]):
                hangoutUsage = self.allAnalytics.get_by_path(["commands", messageParts['commandName'], "hangoutUsage", convId])
            hangoutUsage += 1
            self.allAnalytics.set_by_path(["commands", messageParts['commandName'], "hangoutUsage", convId], hangoutUsage)

            #Set/Increment the user specific calls for this command
            if not self.allAnalytics.exists(["commands", messageParts['commandName'], "userUsage"]):
                self.allAnalytics.set_by_path(['commands', messageParts['commandName'], "userUsage"], {})
            if self.allAnalytics.exists(["commands", messageParts['commandName'], "userUsage", userId]):
                userUsage = self.allAnalytics.get_by_path(["commands", messageParts['commandName'], "userUsage", userId])
            userUsage += 1
            self.allAnalytics.set_by_path(["commands", messageParts['commandName'], "userUsage", userId], userUsage)
        else:
            hangoutUserUsage = 0
            #Log who talks the most and which hangout is the most talkative
            if not self.allAnalytics.exists(["messages"]):
                self.allAnalytics.set_by_path(['messages'], {})

            if not self.allAnalytics.exists(["messages", "hangoutUsage"]):
                self.allAnalytics.set_by_path(['messages', "hangoutUsage"], {})
            if not self.allAnalytics.exists(["messages", "hangoutUsage", convId]):
                self.allAnalytics.set_by_path(['messages', "hangoutUsage", convId], {})
            if self.allAnalytics.exists(["messages", "hangoutUsage", convId, "usage"]):
                hangoutUsage = self.allAnalytics.get_by_path(["messages", "hangoutUsage", convId, "usage"])
            if self.allAnalytics.exists(["messages", "hangoutUsage", convId, userId]):
                hangoutUserUsage = self.allAnalytics.get_by_path(["messages", "hangoutUsage", convId, userId])
            hangoutUsage += 1
            hangoutUserUsage += 1
            self.allAnalytics.set_by_path(["messages", "hangoutUsage", convId, "usage"], hangoutUsage)
            self.allAnalytics.set_by_path(["messages", "hangoutUsage", convId, userId], hangoutUserUsage)

            if not self.allAnalytics.exists(["messages", "userUsage"]):
                self.allAnalytics.set_by_path(['messages', "userUsage"], {})
            if self.allAnalytics.exists(["messages", "userUsage", userId]):
                userUsage = self.allAnalytics.get_by_path(["messages", "userUsage", userId])
            userUsage += 1
            self.allAnalytics.set_by_path(["messages", "userUsage", userId], userUsage)

        self.allAnalytics.save()