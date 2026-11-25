"""Location lookups (free Open-Meteo APIs, no key): geocoding, a few years of daily history summarised into
monthly climate normals for the planner, and the live weather the runtime needs."""
import datetime as dt
import json
import urllib.parse
import urllib.request

UA = {"User-Agent": "dynamic-wallpaper-gen/1.0"}


def _get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def geocode(query):
    """'Chicago' / 'Chicago, US' / '41.88,-87.63' -> dict(name, lat, lon, timezone, elevation, country)."""
    q = query.strip()
    try:
        lat, lon = [float(v) for v in q.split(",")]
        tz = _get("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&timezone=auto&current=temperature_2m"
                  % (lat, lon))["timezone"]
        return dict(name=q, lat=lat, lon=lon, timezone=tz, elevation=None, country="")
    except ValueError:
        pass
    name = q.split(",")[0].strip()
    res = _get("https://geocoding-api.open-meteo.com/v1/search?count=5&name=" + urllib.parse.quote(name)).get("results")
    if not res:
        raise ValueError("location not found: %s" % query)
    hint = q.split(",")[1].strip().lower() if "," in q else ""
    pick = next((r for r in res if hint and hint in (r.get("country_code", "").lower(), r.get("country", "").lower(),
                                                       r.get("admin1", "").lower())), res[0])
    return dict(name="%s, %s" % (pick["name"], pick.get("country", pick.get("country_code", ""))),
                lat=pick["latitude"], lon=pick["longitude"], timezone=pick["timezone"],
                elevation=pick.get("elevation"), country=pick.get("country_code", ""))


def climate_normals(lat, lon, years=3):
    """Monthly means from the last `years` full years of daily reanalysis data."""
    end = dt.date(dt.date.today().year - 1, 12, 31)
    start = dt.date(end.year - years + 1, 1, 1)
    d = _get("https://archive-api.open-meteo.com/v1/archive?latitude=%s&longitude=%s&start_date=%s&end_date=%s"
             "&daily=temperature_2m_mean,temperature_2m_min,precipitation_sum,snowfall_sum,snow_depth_max,"
             "daylight_duration&timezone=auto" % (lat, lon, start, end), timeout=60)["daily"]
    months = {m: dict(t=[], tmin=[], p=[], snow=[], depth=[], day=[]) for m in range(1, 13)}
    for i, day in enumerate(d["time"]):
        m = int(day[5:7])
        for key, src in (("t", "temperature_2m_mean"), ("tmin", "temperature_2m_min"), ("p", "precipitation_sum"),
                         ("snow", "snowfall_sum"), ("depth", "snow_depth_max"), ("day", "daylight_duration")):
            v = d[src][i]
            if v is not None:
                months[m][key].append(v)
    out = []
    for m in range(1, 13):
        v = months[m]
        n_years = max(1, years)
        mean = lambda a: round(sum(a) / len(a), 1) if a else None
        out.append(dict(month=m, temp_mean_c=mean(v["t"]), temp_min_c=mean(v["tmin"]),
                        precip_mm=round(sum(v["p"]) / n_years, 1), snowfall_cm=round(sum(v["snow"]) / n_years, 1),
                        snow_cover_days=round(sum(1 for x in v["depth"] if x >= 0.02) / n_years, 1),
                        daylight_h=round(mean(v["day"]) / 3600, 1) if v["day"] else None))
    return out


def current_weather(lat, lon):
    return _get("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                "&current=weather_code,cloud_cover,temperature_2m,snow_depth&timezone=auto" % (lat, lon), 15)["current"]
