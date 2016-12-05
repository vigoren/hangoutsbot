import plugins, logging, requests, os, csv, urllib, lxml, gmusicapi, json

logger = logging.getLogger(__name__)

_internal = {}

def _initialize(bot):
    api_key = bot.get_config_option('youtube_data_api_key')
    if api_key:
        _internal['api_key'] = api_key
        _internal['plugin_dir'] = os.path.dirname(os.path.realpath(__file__))
        plugins.register_admin_command(["xkito"])
    else:
        logger.error('config["youtube_data_api_key"] required')


def _call_youtube_api(api, parameters, next_page_key = None):
    if 'key' not in parameters:
        parameters['key'] = _internal['api_key']
    if next_page_key is not None:
        parameters['pageToken'] = next_page_key
    query_string = "&".join("{}={}".format(k,v) for(k,v) in parameters.items())
    url = "https://www.googleapis.com/youtube/v3/{}?{}".format(api,query_string)
    videos = []
    r = requests.get(url)
    try:
        j = r.json()
        if 'items' in j:
            for item in j['items']:
                d = {
                    'id': item['id'],
                    'etag': item['etag']
                }
                if 'snippet' in item:
                    d['name'] = _clean_title(item['snippet']['title'])
                    d['description'] = _parse_description(item['snippet']['description'])
                    d['channelId'] = item['snippet']['channelId']
                    if 'resourceId' in item['snippet']:
                        d['videoId'] = item['snippet']['resourceId']['videoId']

                if 'contentDetails' in item:
                    d['videoCount'] = item['contentDetails']['itemCount']

                videos.append(d)

        if 'nextPageToken' in j:
            videos = videos + _call_youtube_api(api, parameters, j['nextPageToken'])
        if 'error' in j:
            logger.error("Error with the youtube API: {}".format(j['error']['message']))

    except Exception as e:
        logger.error("There was an issue communicating with the Google Youtube API. {}".format(e))
    return videos


def _clean_title(title):
    if u"\u3011" in title:
        p = title.split(u"\u3011")
        title = p[1]
    if "[" in title:
        p = title.split("[")
        title = p[0]
    return title.strip()

def _parse_description(description):
    res = {"free_download": "", "google_play": ""}
    if description:
        desc_lower = description.lower()
        if "free download" in desc_lower:
            sliced_desc = description[desc_lower.find("free download"):]
            eol_pos = sliced_desc.find("\n")
            if eol_pos == -1:
                eol_pos = len(sliced_desc)
            sliced_desc = sliced_desc[:eol_pos]
            res["free_download"] = sliced_desc
        elif "download link" in desc_lower:
            sliced_desc = description[desc_lower.find("download link"):]
            eol_pos = sliced_desc.find("\n")
            if eol_pos == -1:
                eol_pos = len(sliced_desc)
            sliced_desc = sliced_desc[:eol_pos]
            res["free_download"] = sliced_desc

        if "google play" in desc_lower:
            sliced_desc = description[desc_lower.find("google play"):]
            eol_pos = sliced_desc.find("\n")
            if eol_pos == -1:
                eol_pos = len(sliced_desc)
            sliced_desc = sliced_desc[:eol_pos]
            res["google_play"] = sliced_desc
    return res


def _update_playlist_file(playlist):
    path = os.path.join(_internal['plugin_dir'], playlist['id'] + ".txt")
    etag = playlist['etag'].split('/')[0].replace('"','')
    identifier = "{}|{}|{}".format(etag,playlist['videoCount'],playlist['name'])
    if os.path.exists(path):
        with open(path, 'r') as f:
            line = f.readline()
            f.close()
            if identifier in line:
                return False

    f = open(path, 'w')
    f.write(identifier)
    f.write('\n')
    f.close()
    return True


def _add_videos_playlist_file(playlist, video_lines):
    path = os.path.join(_internal['plugin_dir'], playlist['id'] + ".txt")
    if os.path.exists(path):
        with open(path, 'a') as f:
            f.writelines(video_lines)
            f.close()


def _get_videos_from_playlist_files():
    uniqueVideoList = {}
    for file in os.listdir(_internal["plugin_dir"]):
        if file.endswith(".txt"):
            path = os.path.join(_internal['plugin_dir'], file)
            with open(path, 'r') as f:
                lines = f.readlines()
                playlistId = file.replace('.txt','')
                name = lines[0].split('|')[2]
                lines = [x.strip('\n') for x in lines[1:]]
                res = csv.DictReader(lines, fieldnames=("id", "name", "free_download", "google_play"))
                uniqueVideoList[playlistId] = {'name': name, 'videos': res}

    return uniqueVideoList


def _search_google_play_for_song(title):
    headers = {
        "User-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.94 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    query_string = {
        "c": "music",
        "docType": "4",
        "q": title
    }
    url = "https://play.google.com/store/search?{}".format(urllib.parse.urlencode(query_string))
    return url
    req = urllib.request.Request(url, None, headers)
    conn = urllib.request.urlopen(req)
    resp = conn.read()
    if "We couldn't find anything for your search" in resp:
        return {}
    html_tree = lxml.html.fromstring(resp)
    cards = html_tree.xpath("//*[contains(@class,'card-list')]")
    return cards



def xkito(bot, event, *args):
    if not args:
        yield from bot.coro_send_message(event.conv_id, "No parameters provided. /ada xkito <get|search> <playlist_ids(optional)>")
        return
    if args[0].lower() == "get":
        channelId = "UCMOgdURr7d8pOVlc-alkfRg"
        playlists = []
        youtubeApiVideoCount = 0


        if len(args) > 1:
            playlists = _call_youtube_api("playlists", {"part": "snippet%2CcontentDetails", "maxResults": "50", "id": args[1]})
        else:
            playlists = _call_youtube_api("playlists", {"part": "snippet%2CcontentDetails", "maxResults": "50", "channelId": channelId})

        for pl in playlists:
            # If the playlist file(s) needs to be updated from Youtube
            if _update_playlist_file(pl):
                videos = _call_youtube_api("playlistItems", {"part": "snippet", "maxResults": "50", "playlistId": pl['id']})
                lines = []
                for v in videos:
                    video_details = _call_youtube_api("videos", {"part": "snippet", "maxResults": "1", "id": v['videoId'], "fields": "items(etag%2Cid%2Csnippet)"})
                    if video_details:
                        video_details = video_details[0]
                        if video_details['channelId'] == channelId:
                            lines.append("\"{}\",\"{}\",\"{}\",\"{}\"\n".format(video_details['id'], video_details['name'], video_details['description']['free_download'], video_details['description']['google_play']))
                            youtubeApiVideoCount += 1
                if lines:
                    _add_videos_playlist_file(pl, lines)

        yield from bot.coro_send_message(event.conv_id, "Number of videos: {}".format(youtubeApiVideoCount))

    elif args[0].lower() == "search":
        if not bot.memory.exists(["google_music_search_credentials"]):
            yield from bot.coro_send_message(event.conv_id, "No credentials specified to log into Google Music")
            return
        creds = bot.memory["google_music_search_credentials"]

        # TODO: When writing the found song, include playlist link/title and link to the video itself, better organization. Look into saving in google drive????

        # Flatten all videos into a single list
        playlists = _get_videos_from_playlist_files()
        # Look in google play store for the song
        # search_results = _search_google_play_for_song("Maxximo Callas ft. Lisa Rowe - Naked")

        # Look in google music for the song "vdoxvmiazituvthv"
        gm = gmusicapi.Mobileclient()
        if not gm.login(creds["email"], creds["pass"], gmusicapi.Mobileclient.FROM_MAC_ADDRESS):
            yield from bot.coro_send_message(event.conv_id, "Could not log into Google Music")
            return

        newPlaylist = {}
        for id, playlist in playlists.items():
            found_songs = []
            for video in playlist['videos']:
                newVideo = video
                if video['google_play']:
                    found_songs.append(newVideo)
                    continue

                search_results = gm.search(video['name'])

                if not search_results or not search_results["song_hits"]:
                    if not video['free_download']:
                        newVideo['google_play'] = "Could not find any songs in Google Music"
                    found_songs.append(newVideo)
                    continue

                newVideo['google_play'] = []

                for song in search_results['song_hits']:
                    newVideo['google_play'].append("https://play.google.com/music/m/{}".format(song['track']['nid']))

                found_songs.append(newVideo)
            newPlaylist[id] = {'name': playlist['name'], 'videos': found_songs}

        path = os.path.join(_internal['plugin_dir'], "music_results.txt")
        with open(path, 'w') as f:
            json.dump(newPlaylist, f)
            f.close()

        yield from bot.coro_send_message(event.conv_id, "Updated songs for <b><i>{}</i></b> playlists".format(len(newPlaylist)))
