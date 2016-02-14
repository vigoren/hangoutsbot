import asyncio, importlib, inspect, logging, os, sys

from inspect import getmembers, isfunction

import handlers

from commands import command


logger = logging.getLogger(__name__)


def recursive_tag_format(array, **kwargs):
    for index, tags in enumerate(array):
        if isinstance(tags, list):
            recursive_tag_format(tags, **kwargs)
        else:
            array[index] = array[index].format(**kwargs)

class tracker:
    """used by the plugin loader to keep track of loaded commands
    designed to accommodate the dual command registration model (via function or decorator)
    registration might be called repeatedly depending on the "path" a command registration takes
    """
    def __init__(self):
        self.bot = None
        self.list = {}
        self.reset()

    def set_bot(self, bot):
        self.bot = bot

    def reset(self):
        self._current = {
            "commands": {
                "admin": [],
                "user": [],
                "all": None,
                "tagged": {}
            },
            "handlers": [],
            "shared": [],
            "metadata": None,
            "threads": [],
            "asyncio.task": [],
            "aiohttp.web": []
        }

    def start(self, metadata):
        self.reset()
        self._current["metadata"] = metadata

    def current(self):
        self._current["commands"]["all"] = list(
            set(self._current["commands"]["admin"] +
                self._current["commands"]["user"]))
        return self._current

    def end(self):
        current_module = self.current()
        self.list[current_module["metadata"]["module.path"]] = current_module

        # sync tagged commands to the command dispatcher
        if self._current["commands"]["tagged"]:
            for command_name, type_tags in self._current["commands"]["tagged"].items():
                for type in ["admin", "user"]: # prioritse admin-linked tags if both exist
                    if type in type_tags:
                        command.register_tags(command_name, type_tags[type])
                        break

    def register_command(self, type, command_names, tags=None):
        """call during plugin init to register commands"""
        self._current["commands"][type].extend(command_names)
        self._current["commands"][type] = list(set(self._current["commands"][type]))

        config_plugins_tags_autoregister = self.bot.get_config_option('plugins.tags.auto-register')
        if config_plugins_tags_autoregister is None:
            config_plugins_tags_autoregister = True

        if not tags and not config_plugins_tags_autoregister:
            return

        if not tags:
            # assumes config["plugins.tags.auto-register"] == True
            tags = []
        elif isinstance(tags, str):
            tags = [tags]

        if config_plugins_tags_autoregister is True:
            presets = [ "{plugin}-{command}", "{plugin}-{type}" ]
        elif config_plugins_tags_autoregister:
            presets = config_plugins_tags_autoregister
            if isinstance(presets, str):
                presets = [ presets ]
        else:
            presets = []

        for command_name in command_names:
            command_tags = list(tags) + list(presets) # use copies

            recursive_tag_format( command_tags,
                                  command=command_name,
                                  type=type,
                                  plugin=self._current["metadata"]["module"] )

            self.register_tags(type, command_name, command_tags)

    def register_tags(self, type, command_name, tags):
        if command_name not in self._current["commands"]["tagged"]:
            self._current["commands"]["tagged"][command_name] = {}

        if type not in self._current["commands"]["tagged"][command_name]:
            self._current["commands"]["tagged"][command_name][type] = set()

        tagsets = set([ frozenset(item if isinstance(item, list) else [item]) for item in tags ])

        # registration might be called repeatedly, so only add the tagsets if it doesnt exist
        if tagsets > self._current["commands"]["tagged"][command_name][type]:
            self._current["commands"]["tagged"][command_name][type] |= tagsets

        logger.debug("{} - [{}] tags: {}".format(command_name, type, tags))

    def register_handler(self, function, type, priority):
        self._current["handlers"].append((function, type, priority))

    def register_shared(self, id, objectref, forgiving):
        self._current["shared"].append((id, objectref, forgiving))

    def register_thread(self, thread):
        self._current["threads"].append(thread)

    def register_aiohttp_web(self, group):
        # don't register actual references to the web listeners as they are asyncronously started
        #   instead, just track their group(name) so we can find them later
        if group not in self._current["aiohttp.web"]:
            self._current["aiohttp.web"].append(group)

    def register_asyncio_task(self, task):
        self._current["asyncio.task"].append(task)


tracking = tracker()


def asyncio_task_ended(future):
    if future.cancelled():
        logger.debug("task cancelled {}".format(future))
    else:
        future.result()


"""helpers, used by loaded plugins to register commands"""


def register_user_command(command_names, tags=None):
    """user command registration"""
    if not isinstance(command_names, list):
        command_names = [command_names]
    tracking.register_command("user", command_names, tags=tags)

def register_admin_command(command_names, tags=None):
    """admin command registration, overrides user command registration"""
    if not isinstance(command_names, list):
        command_names = [command_names]
    tracking.register_command("admin", command_names, tags=tags)

def register_handler(function, type="message", priority=50):
    """register external handler"""
    bot_handlers = tracking.bot._handlers
    bot_handlers.register_handler(function, type, priority)

def register_shared(id, objectref, forgiving=True):
    """register shared object"""
    bot = tracking.bot
    bot.register_shared(id, objectref, forgiving=forgiving)

def start_asyncio_task(coroutine_function, *args, **kwargs):
    if asyncio.iscoroutinefunction(coroutine_function):
        loop = asyncio.get_event_loop()
        task = loop.create_task(coroutine_function(tracking.bot, *args, **kwargs))

        asyncio.async(task).add_done_callback(asyncio_task_ended)

        tracking.register_asyncio_task(task)

    else:
        raise RuntimeError("coroutine function must be supplied")


"""plugin loader"""


def retrieve_all_plugins(plugin_path=None, must_start_with=False):
    """recursively loads all plugins from the standard plugins path
    * a plugin file or folder must not begin with . or _
    * a subfolder containing a plugin must have an __init__.py file
    * sub-plugin files (additional plugins inside a subfolder) must be prefixed with the 
      plugin/folder name for it to be automatically loaded
    """

    if not plugin_path:
        plugin_path = os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + "plugins"

    plugin_list = []

    nodes = os.listdir(plugin_path)

    for node_name in nodes:
        full_path = os.path.join(plugin_path, node_name)
        module_names = [ os.path.splitext(node_name)[0] ] # node_name without .py extension

        if node_name.startswith(("_", ".")):
            continue

        if must_start_with and not node_name.startswith(must_start_with):
            continue

        if os.path.isfile(full_path):
            if not node_name.endswith(".py"):
                continue
        else:
            if not os.path.isfile(os.path.join(full_path, "__init__.py")):
                continue

            for sm in retrieve_all_plugins(full_path, must_start_with=node_name):
                module_names.append(module_names[0] + "." + sm)

        plugin_list.extend(module_names)

    logger.debug("retrieved {}: {}.{}".format(len(plugin_list), must_start_with or "plugins", plugin_list))
    return plugin_list


def get_configured_plugins(bot):
    all_plugins = retrieve_all_plugins()
    config_plugins = bot.get_config_option('plugins')

    if config_plugins is None: # must be unset in config or null
        logger.info("plugins is not defined, using ALL")
        plugin_list = all_plugins

    else:
        """perform fuzzy matching with actual retrieved plugins, e.g. "abc" matches "xyz.abc"
        if more than one match found, don't load plugin
        """
        plugins_included = []
        plugins_excluded = all_plugins

        plugin_name_ambiguous = []
        plugin_name_not_found = []

        for configured in config_plugins:
            dotconfigured = "." + configured

            matches = []
            for found in plugins_excluded:
                fullfound = "plugins." + found
                if fullfound.endswith(dotconfigured):
                    matches.append(found)
            num_matches = len(matches)

            if num_matches <= 0:
                logger.debug("{} no match".format(configured))
                plugin_name_not_found.append(configured)
            elif num_matches == 1:
                logger.debug("{} matched to {}".format(configured, matches[0]))
                plugins_included.append(matches[0])
                plugins_excluded.remove(matches[0])
            else:
                logger.debug("{} ambiguous, matches {}".format(configured, matches))
                plugin_name_ambiguous.append(configured)

        if plugins_excluded:
            logger.info("excluded {}: {}".format(len(plugins_excluded), plugins_excluded))

        if plugin_name_ambiguous:
            logger.warning("ambiguous plugin names: {}".format(plugin_name_ambiguous))

        if plugin_name_not_found:
            logger.warning("plugin not found: {}".format(plugin_name_not_found))

        plugin_list = plugins_included

    logger.info("included {}: {}".format(len(plugin_list), plugin_list))

    return plugin_list


def load_user_plugins(bot):
    """loads all user plugins"""

    plugin_list = get_configured_plugins(bot)

    for module in plugin_list:
        module_path = "plugins.{}".format(module)
        load(bot, module_path)


@asyncio.coroutine
def unload_all(bot):
    module_paths = list(tracking.list.keys())
    for module_path in module_paths:
        try:
            yield from unload(bot, module_path)

        except RuntimeError as e:
            logger.exception("{} could not be unloaded".format(module_path))


def load(bot, module_path, module_name=None):
    """loads a single plugin-like object as identified by module_path, and initialise it"""

    if module_name is None:
        module_name = module_path.split(".")[-1]

    if module_path in tracking.list:
        raise RuntimeError("{} already loaded".format(module_path))

    tracking.start({ "module": module_name, "module.path": module_path })

    try:
        if module_path in sys.modules:
            importlib.reload(sys.modules[module_path])
            logger.debug("reloading {}".format(module_path))

        else:
            importlib.import_module(module_path)
            logger.debug("importing {}".format(module_path))

    except Exception as e:
        logger.exception("EXCEPTION during plugin import: {}".format(module_path))
        return

    public_functions = [o for o in getmembers(sys.modules[module_path], isfunction)]

    candidate_commands = []

    """pass 1: run optional callable: _initialise, _initialize
    * performs house-keeping tasks (e.g. migration, tear-up, pre-init, etc)
    * registers user and/or admin commands
    """
    available_commands = False # default: ALL
    try:
        for function_name, the_function in public_functions:
            if function_name ==  "_initialise" or function_name ==  "_initialize":
                """accepted function signatures:
                CURRENT
                version >= 2.4 | function()
                version >= 2.4 | function(bot) - parameter must be named "bot"
                LEGACY
                version <= 2.4 | function(handlers, bot)
                ancient        | function(handlers)
                """
                _expected = list(inspect.signature(the_function).parameters)
                if len(_expected) == 0:
                    the_function()
                    _return = []
                elif len(_expected) == 1 and _expected[0] == "bot":
                    the_function(bot)
                    _return = []
                else:
                    try:
                        # legacy support, pre-2.4
                        logger.info("[LEGACY] upgrade {1}.{0}(handlers, bot) to {0}(bot) and use bot._handlers internally"
                            .format(the_function.__name__, module_path))

                        _return = the_function(bot._handlers, bot)
                    except TypeError as e:
                        # DEPRECATED: ancient plugins
                        logger.warning("[DEPRECATED] upgrade {1}.{0}(handlers) to {0}(bot) and use bot._handlers internally"
                            .format(the_function.__name__, module_path))

                        _return = the_function(bot._handlers)
                if type(_return) is list:
                    available_commands = _return
            elif function_name.startswith("_"):
                pass
            else:
                candidate_commands.append((function_name, the_function))
        if available_commands is False:
            # implicit init, legacy support: assume all candidate_commands are user-available
            register_user_command([function_name for function_name, function in candidate_commands])
        elif available_commands is []:
            # explicit init, no user-available commands
            pass
        else:
            # explicit init, legacy support: _initialise() returned user-available commands
            register_user_command(available_commands)
    except Exception as e:
        logger.exception("EXCEPTION during plugin init: {}".format(module_path))
        return # skip this, attempt next plugin

    """
    pass 2: register filtered functions
    tracking.current() and the CommandDispatcher registers might be out of sync if a 
    combination of decorators and register_user_command/register_admin_command is used since
    decorators execute immediately upon import
    """
    plugin_tracking = tracking.current()

    explicit_admin_commands = plugin_tracking["commands"]["admin"]
    all_commands = plugin_tracking["commands"]["all"]
    registered_commands = []
    for function_name, the_function in candidate_commands:
        if function_name in all_commands:
            is_admin = False
            text_function_name = function_name
            if function_name in explicit_admin_commands:
                is_admin = True
                text_function_name = "*" + text_function_name

            command.register(the_function, admin=is_admin, final=True)

            registered_commands.append(text_function_name)

    if registered_commands:
        logger.info("{} - {}".format(module_name, ", ".join(registered_commands)))
    else:
        logger.info("{} - no commands".format(module_name))

    tracking.end()

    return True


@asyncio.coroutine
def unload(bot, module_path):
    if module_path in tracking.list:
        plugin = tracking.list[module_path]
        loop = asyncio.get_event_loop()

        if len(plugin["threads"]) == 0:
            all_commands = plugin["commands"]["all"]
            for command_name in all_commands:
                if command_name in command.commands:
                    logger.debug("removing function {}".format(command_name))
                    del command.commands[command_name]
                if command_name in command.admin_commands:
                    logger.debug("deregistering admin command {}".format(command_name))
                    command.admin_commands.remove(command_name)

            for type in plugin["commands"]["tagged"]:
                for command_name in plugin["commands"]["tagged"][type]:
                    if command_name in command.command_tagsets:
                        logger.debug("deregistering tagged command {}".format(command_name))
                        del command.command_tagsets[command_name]

            for type in bot._handlers.pluggables:
                for handler in bot._handlers.pluggables[type]:
                    if handler[2]["module.path"] == module_path:
                        logger.debug("removing handler {} {}".format(type, handler))
                        bot._handlers.pluggables[type].remove(handler)

            shared = plugin["shared"]
            for shared_def in shared:
                id = shared_def[0]
                if id in bot.shared:
                    logger.debug("removing shared {}".format(id))
                    del bot.shared[id]

            if len(plugin["asyncio.task"]) > 0:
                for task in plugin["asyncio.task"]:
                    logger.info("cancelling task: {}".format(task))
                    loop.call_soon_threadsafe(task.cancel)

            if len(plugin["aiohttp.web"]) > 0:
                from sinks import aiohttp_terminate # XXX: needs to be late-imported
                for group in plugin["aiohttp.web"]:
                    yield from aiohttp_terminate(group)

            logger.info("{} unloaded".format(module_path))

            del tracking.list[module_path]

            return True

        else:
            raise RuntimeError("{} has {} thread(s)".format(module_path, len(plugin["threads"])))

    else:
        raise KeyError("{} not found".format(module_path))
