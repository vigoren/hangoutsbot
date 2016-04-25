import hangups, plugins, logging, config, os, time

logger = logging.getLogger(__name__)
_internal = {}


def _initialize(bot):
    settings = bot.get_config_option("analytics")
    if not settings["enabled"]:
        return
    if not settings["path"].endswith('/'):
        settings["path"] += "/"
    _internal['amp'] = AnalyticMessageParser(bot, settings["path"])
    if _internal['amp'].initialized:
        plugins.register_admin_command(['analytics'])
        plugins.register_handler(_internal['amp'].onMessage, type="allmessages")
        _internal['help'] = "Missing arguments to run the analytics command:<br/>/bot analytics <command|message> <all|hangout_id|user_id>"


def analytics(bot, event, *args):
    if not args or len(args) < 2:
        yield from bot.coro_send_message(event.conv_id, _internal['help'])
        return
    data = _internal["amp"].showData(bot, args)
    yield from bot.coro_send_message(event.conv_id, '<br/>'.join(data))


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

        # Internal methods

    def _loadAnalytics(self, name):
        filePath = self.analyticsFilePath + name
        data = config.Config(filePath, failsafe_backups=1, save_delay=1)
        if not os.path.isfile(filePath):
            try:
                logger.info("creating analytics file: {}".format(filePath))
                data.set_by_path(["startDate"], int(time.time()))
                data.force_taint()
                data.save()

            except (OSError, IOError) as e:
                logger.exception('Failed to create the analytics file: {}'.format(filePath))
                return None
        return data

    def _parseMessage(self, messageText):
        parts = {'commandName': "", 'args': "", 'text': ""}
        for alias in self.botAliases:
            if messageText[0] == alias and len(messageText) > 1:
                parts['commandName'] = messageText[1]
                parts['args'] = ' '.join(messageText[2:])
                break
        parts['text'] = ' '.join(messageText)
        return parts

    def _ensureJsonPathExists(self, path):
        currentPath = []
        for part in path:
            currentPath.append(part)
            if not self.allAnalytics.exists(currentPath):
                self.allAnalytics.set_by_path(currentPath, {})

    def _logCall(self, messageParts, convId, userId):
        hangoutUsage = 0
        userUsage = 0
        # If there is a command name set then a command was called
        if messageParts['commandName']:
            totalUsage = 0

            self._ensureJsonPathExists(["commands", messageParts['commandName'], "hangoutUsage"])
            self._ensureJsonPathExists(["commands", messageParts['commandName'], "userUsage"])

            # Set/Increment the total calls for this command
            if self.allAnalytics.exists(["commands", messageParts['commandName'], "totalUsage"]):
                totalUsage = self.allAnalytics.get_by_path(["commands", messageParts['commandName'], "totalUsage"])
            totalUsage += 1
            self.allAnalytics.set_by_path(["commands", messageParts['commandName'], "totalUsage"], totalUsage)

            # Set/Increment the hangout specific calls for this command
            if self.allAnalytics.exists(["commands", messageParts['commandName'], "hangoutUsage", convId]):
                hangoutUsage = self.allAnalytics.get_by_path(
                    ["commands", messageParts['commandName'], "hangoutUsage", convId])
            hangoutUsage += 1
            self.allAnalytics.set_by_path(["commands", messageParts['commandName'], "hangoutUsage", convId],
                                          hangoutUsage)

            # Set/Increment the user specific calls for this command
            if self.allAnalytics.exists(["commands", messageParts['commandName'], "userUsage", userId]):
                userUsage = self.allAnalytics.get_by_path(
                    ["commands", messageParts['commandName'], "userUsage", userId])
            userUsage += 1
            self.allAnalytics.set_by_path(["commands", messageParts['commandName'], "userUsage", userId], userUsage)
        else:
            hangoutUserUsage = 0
            # Log who talks the most and which hangout is the most talkative

            self._ensureJsonPathExists(['messages', "hangoutUsage", convId])
            self._ensureJsonPathExists(['messages', "userUsage"])

            if self.allAnalytics.exists(["messages", "hangoutUsage", convId, userId]):
                hangoutUsage = self.allAnalytics.get_by_path(["messages", "hangoutUsage", convId, userId])
            hangoutUsage += 1
            self.allAnalytics.set_by_path(["messages", "hangoutUsage", convId, userId], hangoutUsage)

            if self.allAnalytics.exists(["messages", "userUsage", userId]):
                userUsage = self.allAnalytics.get_by_path(["messages", "userUsage", userId])
            userUsage += 1
            self.allAnalytics.set_by_path(["messages", "userUsage", userId], userUsage)

        self.allAnalytics.save()

    def _parseCommandArgs(self, args):
        data = {'command': False, 'message': False, 'all':True, 'hangoutId': None, 'userId': None}
        dataType = args[0].strip().lower()
        if dataType == "command":
            data['command'] = True
        elif dataType == "message":
            data['message'] = True

        sType = args[1].strip()
        if sType.lower() != "all":
            data['all'] = False
            if sType.isdigit():
                data['userId'] = sType
            else:
                data['hangoutId'] = sType
        return data

    #Public methods
    def onMessage(self, bot, event, command):
        messageText = event.text.lower().split()
        if not messageText or event.user.is_self:
            return
        messageParts = self._parseMessage(messageText)
        self._logCall(messageParts, event.conv.id_, event.user.id_.chat_id)

    def showData(self, bot, args):
        response = []
        args = self._parseCommandArgs(args)

        if args["userId"] is not None:
            response.append("Showing the results for user {}".format(args["userId"]))
        elif args["hangoutId"] is not None:
            response.append("Showing the results for the hangout {}".format(args["hangoutId"]))

        if args["command"]:
            commands = self.allAnalytics.get_option("commands")
            filtered = []
            for command, data in commands.items():
                if args['all']:
                    filtered.append({'name': command, 'usage': data["totalUsage"]})
                elif args["userId"] is not None:
                    userData = data['userUsage']
                    if args["userId"] in userData:
                        filtered.append({'name': command, 'usage': userData[args["userId"]]})
                elif args["hangoutId"] is not None:
                    hangoutData = data['hangoutUsage']
                    if args["hangoutId"] in hangoutData:
                        filtered.append({'name': command, 'usage': hangoutData[args["hangoutId"]]})

            filtered = sorted(filtered, key=lambda x: (x["usage"], x["name"]))
            for command in filtered:
                response.append("<b>{}</b> has been run {} time(s)".format(command["name"], command["usage"]))

        elif args["message"]:
            messages = {}
            if (args["all"] or args["userId"] is not None) and self.allAnalytics.exists(["messages", "userUsage"]):
                messages = self.allAnalytics.get_by_path(["messages", "userUsage"])
            elif self.allAnalytics.exists(["messages", "hangoutUsage", args["hangoutId"]]):
                messages = self.allAnalytics.get_by_path(["messages", "hangoutUsage", args["hangoutId"]])
            filtered = []
            for userId, count in messages.items():
                user = userId
                if (args["userId"] is not None and userId != args["userId"]) or userId == 'usage':
                    continue
                if bot.memory.exists(["user_data", userId, "_hangups", "full_name"]):
                    user = bot.memory.get_by_path(["user_data", userId, "_hangups", "full_name"])
                filtered.append({'name': user, 'id': userId, 'usage': count})
            filtered = sorted(filtered, key=lambda x: (x["usage"], x["name"]))
            for user in filtered:
                response.append("<b><a href='https://plus.google.com/u/0/{}/about'>{}</a></b> has sent {} messages".format(user['id'], user['name'], user['usage']))
        else:
            response.append( _internal['help'])

        if len(response) == 0:
            response.append("No data was found.")
        return response
