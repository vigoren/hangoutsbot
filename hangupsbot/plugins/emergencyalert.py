import hangups, plugins, logging, feedparser, asyncio, time

logger = logging.getLogger(__name__)


def _initialise(bot):
    if not bot.memory.exists(['emergency_alerts']):
        return
    config = bot.memory.get('emergency_alerts')
    if not config:
        return
    plugins.start_asyncio_task(_check_emergency_alerts, config)


@asyncio.coroutine
def _check_emergency_alerts(bot, config):
    last_run = 0
    emergency_alert(bot, config)
    while True:
        timestamp = time.time()
        yield from asyncio.sleep(15)
        if timestamp - last_run > 900:
            yield from emergency_alert(bot, config)
            last_run = timestamp


def emergency_alert(bot, config):
    change = False
    idx = 0
    for source in config:
        alerts = feedparser.parse(source['feed_url'])
        if not alerts:
            logger.error("There was an error getting the emergency alert feed '{}' for the '{}' reporting region.".format(source['feed_url'], source['alert_reporting_region']))
        text = []
        alert_list = _create_alert_list(alerts.entries, source)
        for alert in alert_list:
            if alert["show"]:
                text.append("<b>{}</b><br /><b><i>{}</i></b><br />{}".format(alert['title'], alert['author'], alert['summary']))
                change = True

        if change:
            config[idx]['alerts'] = alert_list

        if not text:
            logger.info("There were no new alerts or updates to existing alerts.")

        for ho in source['hangouts']:
            conv = bot.get_hangups_conversation(ho)
            if conv:
                yield from bot.coro_send_message(conv, "<br /><br />".join(text))
            else:
                logger.info("Can't find the conversation {}".format(ho))
        idx += 1
    if change:
        bot.memory["emergency_alerts"] = config
        bot.memory.save()


def _create_alert_list(alerts,source):
    alert_list = []
    for alert in alerts:
        if "critical" not in alert.title.lower():
            continue
        found = False
        geo = ""
        if "where" in alert:
            if "coordinates" in alert.where:
                geo = alert.where.coordinates
        for saved_alert in source['alerts']:
            if saved_alert['id'] == alert.id:
                # This alert has been seen, check if updated
                found = True
                if saved_alert['updated'] != alert.updated:
                    alert_list.append({
                        "id": alert.id,
                        "title": alert.title,
                        "author": alert.author,
                        "summary": alert.summary,
                        "updated": alert.updated,
                        "link": alert.link,
                        "geo": geo,
                        "show": True
                    })
                else:
                    saved_alert["show"] = False
                    alert_list.append(saved_alert)
        if not found:
            # New Alert
            alert_list.append({
                "id": alert.id,
                "title": alert.title,
                "author": alert.author,
                "summary": alert.summary,
                "updated": alert.updated,
                "link": alert.link,
                "geo": geo,
                "show": True
            })
    return alert_list
