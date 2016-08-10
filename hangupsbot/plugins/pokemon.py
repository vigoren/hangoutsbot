'''
pokemon.py -- a hangoutsbot plugin for retrieving information about pokemon, given a name
This uses the pokeapi.co API to retrieve the information.

Because Pokéapi limits requests to 300 requests per method, we store cached data for each Pokémon for 5 days - this should be sufficient for up to 1500 Pokémon overall. Currently there are approximately 811 Pokémon accessible through the Pokéapi so this should be more than enough.
'''
import hangups, plugins, asyncio, logging, datetime
import urllib.request
import json
import aiohttp, os, io

logger = logging.getLogger(__name__)


def _initialise(bot):
    plugins.register_admin_command(["clearpokedex"])
    plugins.register_user_command(["pokedex"])


@asyncio.coroutine
def pokedex(bot, event, *args):
    '''Returns the number, types, weaknesses and image of a pokemon
    Usage /ada pokedex <pokemon name|pokemon number>
    '''

    pokemon = ''.join(args).strip().lower()
    if not pokemon:
        yield from bot.coro_send_message(event.conv_id, 'No pokedex number or pokemon name was specified.')
        return

    data = None
    cache = getfromcache(bot, pokemon)

    if cache:
        data = cache
    else:
        try:
            url = "http://pokeapi.co/api/v2/pokemon/{}/".format(pokemon)
            request = urllib.request.Request(url, headers={"User-agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(request).read().decode("utf-8"))
            data["species"] = getPokemonSpecies(pokemon)
            data = cachePokemon(bot, data)
        except urllib.error.URLError:
            data = None

    if data is None:
        yield from bot.coro_send_message(event.conv, "Unable to find pokedex information about {}".format(pokemon))
        return


    typeNames = []
    types = []
    for type in data["types"]:
        typeNames.append(type["name"].capitalize())
        types.append(gettype(bot, type["name"]))

    pkmn = "<b><a href='http://pokemondb.net/pokedex/{}'>{}</a></b> (#{})<br><b><i>Type</i></b>: {}<br>".format(data["name"].lower(), data["name"].capitalize(), data["id"], ", ".join(typeNames))

    if "habitat" in data["species"]:
        pkmn += "<b><i>Habitat</i></b>: {}<br/>".format(data["species"]["habitat"].capitalize())

    type1 = types[0] if len(types) > 0 else None
    type2 = types[1] if len(types) > 1 else None
    if type1 and type2:
        matchups = comparetypes(type1, type2)
    else:
        if type1:
            matchups = [{'title': 'Weak to', 'data': type1['damage_relations']['double_damage_from']},
                        {'title': 'Resistant to', 'data': type1['damage_relations']['half_damage_from']},
                        {'title': 'Immune to', 'data': type1['damage_relations']['no_damage_from']}]
    matches = ""

    if matchups:
        for x in matchups:
            if len(x["data"]) > 0:
                t = []
                for y in x["data"]:
                    if isinstance(y, dict):
                        t.append(y['name'].capitalize())
                    else:
                        t.append(y.capitalize())
                matches = matches + "<br><b><i>{}</i></b>: {}".format(x["title"].capitalize(), ", ".join(t))

    pkmn = pkmn + matches

    evoData = getPokemonEvolution(data["species"]["evolution_chain"], data["name"].lower())
    pkmn += "<br/><br/><b><i>Evolutions</i></b>:"
    if len(evoData["evolvedFrom"]) > 0:
        pkmn += "<br/>Evolves From: {}".format(" or ".join(evoData["evolvedFrom"]))
    if len(evoData["evolvesTo"]) > 0:
        pkmn += "<br/>Evolves To: {}".format(" or ".join(evoData["evolvesTo"]))



    link_image = "http://img.pokemondb.net/artwork/{}.jpg".format(data["name"].lower())
    filename = os.path.basename(link_image)
    r = yield from aiohttp.request('get', link_image)
    raw = yield from r.read()
    image_data = io.BytesIO(raw)
    image_id = yield from bot._client.upload_image(image_data, filename=filename)
    yield from bot.coro_send_message(event.conv, pkmn, image_id=image_id)

@asyncio.coroutine
def clearpokedex(bot, event):
    '''Clear the cached pokedex'''
    bot.memory.set_by_path(["pokedex"], {})
    bot.memory.save()
    yield from bot.coro_send_message(event.conv, "Pokedex cache cleared")

def getfromcache(bot, pokemonname):
    if not bot.memory.exists(["pokedex"]):
        bot.memory.set_by_path(["pokedex"], {})

    if pokemonname.isdigit():
        allCache = bot.memory.get_by_path(["pokedex"])
        for name, data in allCache.items():
            if name == "pokemontypes":
                continue
            if int(data["id"]) == int(pokemonname):
                pokemonname = data["name"]
                break

    if bot.memory.exists(["pokedex", pokemonname]):
        if bot.memory.get_by_path(["pokedex", pokemonname, "expires"]) > str(datetime.datetime.now()):
            return bot.memory.get_by_path(["pokedex", pokemonname])
    return None

def cachePokemon(bot, data):
    if not bot.memory.exists(["pokedex"]):
        bot.memory.set_by_path(["pokedex"], {})

    pTypes = []
    sortedTypes = sorted(data["types"], key=lambda k: k["slot"])
    for type in sortedTypes:
        if type["type"]:
            pTypes.append(type["type"])

    data = {"name": data["name"], "id": data["id"], "types": pTypes, "species": data["species"], "expires": str(datetime.datetime.now() + datetime.timedelta(days=5))}

    bot.memory.set_by_path(["pokedex", data["name"].lower()], data)
    bot.memory.save()
    return data

def getPokemonEvolution(evos, pokemonName):
    data = {"evolvesTo":[], "evolvedFrom":[]}
    for evo in evos:
        if evo["name"] == pokemonName:
            if "evolutions" in evo:
                for e in evo["evolutions"]:
                    data["evolvesTo"].append("<a href='http://pokemondb.net/pokedex/{}'>{}</a>".format(e["name"], e["name"].capitalize()))
        else:
            if "evolutions" in evo:
                data = getPokemonEvolution(evo["evolutions"], pokemonName)
                if len(data["evolvedFrom"]) == 0:
                    data["evolvedFrom"].append("<a href='http://pokemondb.net/pokedex/{}'>{}</a>".format(evo["name"], evo["name"].capitalize()))
    return data

###################
# Types
###################

def getpkmntype(bot, pkmntype):
    url = "http://pokeapi.co/api/v2/type/{}".format(pkmntype.lower())
    request = urllib.request.Request(url, headers={"User-agent": "Mozilla/5.0"})
    try:
        data = json.loads(urllib.request.urlopen(request).read().decode("utf-8"))
    except:
        return None

    return data

def gettype(bot, pkmntype):
    cache = gettypefromcache(bot, pkmntype)
    if cache:
        return cache
    else:
        typedata = getpkmntype(bot, pkmntype)
        if typedata:
            cachepkmntype(bot, typedata)

        return typedata

def gettypefromcache(bot, pkmntype):
    if not bot.memory.exists(["pokedex", "pokemontypes"]):
        bot.memory.set_by_path(["pokedex", "pokemontypes"], {})
        return None
    else:
        if not bot.memory.exists(["pokedex", "pokemontypes", pkmntype]):
            return None
        elif bot.get_by_path(["pokedex", "pokemontypes", pkmntype, "expires"]) < str(datetime.datetime.now()):
            logger.info("Cached data for {} type expired.".format(pkmntype))
            return None
        else:
            return bot.get_by_path(["pokedex", "pokemontypes", pkmntype])

@asyncio.coroutine
def cachepkmntype(bot, pkmntypedata):
    if not bot.memory.exists(["pokedex", "pokemontypes"]):
        bot.memory.set_by_path(["pokedex", "pokemontypes"], {})

    bot.memory.set_by_path(["pokedex", "pokemontypes", pkmntypedata["name"]],
                           {"name": pkmntypedata["name"], "damage_relations": pkmntypedata['damage_relations'],
                            'expires': str(datetime.datetime.now() + datetime.timedelta(days=5))})
    bot.memory.save()

def comparetypes(data1, data2):
    weak1 = [x['name'] for x in data1['damage_relations']['double_damage_from']]
    weak2 = [x['name'] for x in data2['damage_relations']['double_damage_from']]
    resist1 = [x['name'] for x in data1['damage_relations']['half_damage_from']]
    resist2 = [x['name'] for x in data2['damage_relations']['half_damage_from']]
    immune1 = [x['name'] for x in data1['damage_relations']['no_damage_from']]
    immune2 = [x['name'] for x in data2['damage_relations']['no_damage_from']]
    immune = set(immune1).union(immune2)
    four = set(weak1).intersection(weak2).difference(immune)
    quarter = set(resist1).intersection(resist2).difference(immune)
    two = set(weak1).symmetric_difference(weak2).difference(set(resist1).symmetric_difference(resist2)).difference(
        immune)
    half = ((set(resist1).symmetric_difference(resist2)).difference(set(weak1).symmetric_difference(weak2))).difference(
        immune)

    matchup = []
    matchup.append({'title': 'Very weak to', 'data': four})
    matchup.append({'title': 'Weak to', 'data': two})
    matchup.append({'title': 'Resistant to', 'data': half})
    matchup.append({'title': 'Very resistant to', 'data': quarter})
    matchup.append({'title': 'Immune to', 'data': immune})
    return matchup


###################
# Species
###################

def getPokemonSpecies(type):
    url = "http://pokeapi.co/api/v2/pokemon-species/{}/".format(type.lower())
    request = urllib.request.Request(url, headers={"User-agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(request).read().decode("utf-8"))

    returnData = {}

    if "habitat" in data and data["habitat"] is not None:
        returnData["habitat"] = data["habitat"]["name"]

    if "evolution_chain" in data and data["evolution_chain"] is not None:
        returnData["evolution_chain"] = getPokemonEvolutionChain(data["evolution_chain"]["url"])

    return returnData

###################
# Evolution
###################
def getPokemonEvolutionChain(url):
    request = urllib.request.Request(url, headers={"User-agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(request).read().decode("utf-8"))
    return parseEvlovesTo([data["chain"]])

def parseEvlovesTo(eData):
    data = []
    for stage in eData:
        logger.info("{}".format(stage))
        s = {"name": stage["species"]["name"]}
        if "evolves_to" in stage and stage["evolves_to"] is not None and len(stage["evolves_to"]) > 0:
            s["evolutions"] = parseEvlovesTo(stage["evolves_to"])
        data.append(s)

    return data

