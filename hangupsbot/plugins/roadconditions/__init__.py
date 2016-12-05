import plugins, logging, requests, json, os, time, aiohttp, io, datetime, pytz

logger = logging.getLogger(__name__)
_internal = {
    'highway_names': {
        "queen elizabeth ii highway": ["qe2","qeii"]
    }
}

def _initialize(bot):
    _internal['plugin_dir'] = os.path.dirname(os.path.realpath(__file__))
    plugins.register_user_command(["roadconditions"])


def roadconditions(bot, event, *args):
    """
        Returns details about Alberta Highway conditions
        Commands are:<br/>/ada roadconditions <highway_name> - to see road conditions<br/>/ada roadconditions highways - to see a list of highway names<br/>/ada roadconditions camera - to see a list of camera names<br/>/ada roadconditions camera <camera_name> - to see pictures and details from a highway camera
    """
    if not args:
        yield from bot.coro_send_message(event.conv_id, "No parameters provided. Commands are:<br/>/ada roadconditions <highway_name> - to see road conditions<br/>/ada roadconditions highways - to see a list of highway names<br/>/ada roadconditions camera - to see a list of camera names<br/>/ada roadconditions camera <camera_name> - to see pictures and details from a highway camera")
        return

    section = args[0]
    if section == "camera":
        if len(args) == 1:
            s = _get_camera_list()
            if s is None:
                yield from bot.coro_send_message(event.conv_id, "No camera data returned from the service. Please try again later.")
                return
            yield from bot.coro_send_message(event.conv_id, "Names of camera locations to view the images for.<br/>Type /ada roadconditions camera <name> to see the image.<br/><br/><b>Camera Names</b><br/>{}".format(s))
        else:
            s = _get_camera_data(args[1])
            if s is None:
                yield from bot.coro_send_message(event.conv_id, "No camera data returned from the service. Please try again later.")
                return

            for img in s["pictures"]:
                filename = os.path.basename(img)
                r = yield from aiohttp.request('get', img)
                raw = yield from r.read()
                image_data = io.BytesIO(raw)
                logger.debug("uploading: {}".format(filename))
                image_id = yield from bot._client.upload_image(image_data, filename=filename)
                yield from bot.coro_send_message(event.conv.id_, None, image_id=image_id)
            yield from bot.coro_send_message(event.conv_id, "<b>{} near {}</b><br/>{}<br/><br/>Air Temperature: {}<br/>Pavement Temperature: {}<br/>Wind: {}km/h {}<br/><i>Taken {}</i>".format(s["highway_name"], s["town"], s["name"], s["air_temp"],s["ground_temp"],s["wind_speed"],s["wind_direction"],s["time"]))
    elif section == "highways":
        data = _get_ama_segments()
        if data is None:
            yield from bot.coro_send_message(event.conv_id,"No condition data returned from the service. Please try again later.")
            return
        names = []
        for section in data:
            if not section["highway"] in names:
                names.append(section["highway"])
        names.sort()
        yield from bot.coro_send_message(event.conv_id, "<b>Highway Names</b><br/>{}".format("<br/>".join(names)))
    else:
        road = " ".join(args).lower()
        data = _get_ama_segments()
        if data is None:
            yield from bot.coro_send_message(event.conv_id,"No condition data returned from the service. Please try again later.")
            return
        parts = []
        for section in data:
            if _compare_road_name(road, section["highway"].lower()):
                parts.append("<b>{} from {} to {}</b><br/>Road conditions are <b><i>{}</i></b>. {}<br/><i>Updated: {}</i>".format(section["highway"],section["start"],section["end"],section["condition_type"],section["condition"],section["time"]))

        if len(parts) > 0:
            yield from bot.coro_send_message(event.conv_id, "<br/><br/>".join(parts))
        else:
            yield from bot.coro_send_message(event.conv_id, "Unable to find the highway specified. Try to be more specific or to see a list of all highways type /ada roadconditions highways")


def _get_camera_list():
    data = _api_call("camera", "http://www.amaroadreports.ca/cameras.json")
    if not data or len(data) == 0:
        return None
    s = []
    for d in data:
        s.append(d["camera_station"]["slug"])
    s.sort()
    return '<br/>'.join(s)

def _get_camera_data(name):
    data = _api_call("camera_"+name, "http://www.amaroadreports.ca/cameras/preview/"+name+".json")
    if not data or len(data) == 0:
        return None
    d = {"name": data["camera_station"]["location"],
         "highway_name": data["camera_station"]["highway"]["title"],
         "town": data["camera_station"]["town"],
         "time": data["camera_station"]["timestamp"],
         "air_temp": data["camera_station"]["camera_station_condition"]["air_temperature"].replace("&deg;", "°"),
         "ground_temp": data["camera_station"]["camera_station_condition"]["pavement_temperature"].replace("&deg;","°"),
         "wind_speed": data["camera_station"]["camera_station_condition"]["wind_speed"],
         "wind_direction": data["camera_station"]["camera_station_condition"]["wind_direction"],
         "pictures": []
         }
    for img in data["camera_station"]["camera_images"]:
        d["pictures"].append(img["url"])
    return d

def _get_ama_segments():
    data = _api_call("segments", "http://www.amaroadreports.ca/api/segments.geojson")
    if not data or len(data) == 0:
        return None
    d = []
    for item in data["features"]:
        p = item["properties"]
        d.append({
            "highway": p["highway_title"],
            "start": p["start_point"],
            "end": p["end_point"],
            "condition": p["report_conditions"],
            "condition_type": p["report_conditions_type"],
            "time": datetime.datetime.strptime(p["reported_at"], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc).astimezone(tz=pytz.timezone('America/Edmonton')).strftime("%b %d, %Y at %H:%M:%S")
        })

    return d

def _api_call(filename, url):
    path = os.path.join(_internal['plugin_dir'], filename+".json")
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
            f.close()
            if time.time() < (os.path.getmtime(path) + 600):
                return data

    r = requests.get(url)
    try:
        j = r.json()
        with open(path, 'w') as f:
            json.dump(j, f)
            f.close()
        return j

    except Exception as e:
        logger.error("There was an issue communicating with the AMA Segments API. {}".format(e))
        return []

def _compare_road_name(user,api):
    # If direct match return true
    if api == user:
        return True

    # If one word of the user input matches words from the api, return true
    user_input_words = user.split()
    api_words = api.split()

    if "highway" in user_input_words:
        user_input_words.remove("highway")
        if user_input_words is None:
            user_input_words = []

    c = [item for item in user_input_words if item in api_words]
    if len(c) > 0:
        return True

    # Check list of road slang names
    if api in _internal["highway_names"]:
        slang = _internal["highway_names"][api]
        if user in slang:
            return True

    # No match found return false
    return False