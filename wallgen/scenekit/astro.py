"""Low-precision sun & moon positions (Schlyter's method, ~0.5 deg) for any latitude/longitude.
Copied from render/astro.py with the location made a parameter."""
import math
import datetime as dt


rad, deg = math.radians, math.degrees


def _rev(x):
    return x % 360.0


def _days(when_utc):
    jd = when_utc.timestamp() / 86400.0 + 2440587.5
    return jd - 2451543.5


def _sun_ecl(d):
    w = 282.9404 + 4.70935e-5 * d
    e = 0.016709 - 1.151e-9 * d
    M = _rev(356.0470 + 0.9856002585 * d)
    E = M + deg(e * math.sin(rad(M)) * (1 + e * math.cos(rad(M))))
    xv = math.cos(rad(E)) - e
    yv = math.sqrt(1 - e * e) * math.sin(rad(E))
    v = deg(math.atan2(yv, xv))
    lon = _rev(v + w)
    return lon, M, w


def _moon_ecl(d, Ms, ws):
    N = _rev(125.1228 - 0.0529538083 * d)
    i = 5.1454
    w = _rev(318.0634 + 0.1643573223 * d)
    e = 0.054900
    M = _rev(115.3654 + 13.0649929509 * d)
    E = M + deg(e * math.sin(rad(M)) * (1 + e * math.cos(rad(M))))
    for _ in range(5):
        E = E - (E - deg(e * math.sin(rad(E))) - M) / (1 - e * math.cos(rad(E)))
    xv = math.cos(rad(E)) - e
    yv = math.sqrt(1 - e * e) * math.sin(rad(E))
    v = deg(math.atan2(yv, xv))
    r = math.hypot(xv, yv)
    xh = r * (math.cos(rad(N)) * math.cos(rad(v + w)) - math.sin(rad(N)) * math.sin(rad(v + w)) * math.cos(rad(i)))
    yh = r * (math.sin(rad(N)) * math.cos(rad(v + w)) + math.cos(rad(N)) * math.sin(rad(v + w)) * math.cos(rad(i)))
    zh = r * math.sin(rad(v + w)) * math.sin(rad(i))
    lon = _rev(deg(math.atan2(yh, xh)))
    lat = deg(math.atan2(zh, math.hypot(xh, yh)))
    # main perturbations
    Ls = _rev(Ms + ws); Lm = _rev(M + w + N)
    D = _rev(Lm - Ls); F = _rev(Lm - N)
    s = lambda a: math.sin(rad(a))
    lon += (-1.274 * s(M - 2 * D) + 0.658 * s(2 * D) - 0.186 * s(Ms) - 0.059 * s(2 * M - 2 * D)
            - 0.057 * s(M - 2 * D + Ms) + 0.053 * s(M + 2 * D) + 0.046 * s(2 * D - Ms)
            + 0.041 * s(M - Ms) - 0.035 * s(D) - 0.031 * s(M + Ms) - 0.015 * s(2 * F - 2 * D)
            + 0.011 * s(M - 4 * D))
    lat += (-0.173 * s(F - 2 * D) - 0.055 * s(M - F - 2 * D) - 0.046 * s(M + F - 2 * D)
            + 0.033 * s(F + 2 * D) + 0.017 * s(2 * M + F))
    return _rev(lon), lat


def _altaz(lon_ecl, lat_ecl, d, when_utc, Ms, ws, LAT, LON):
    ecl = 23.4393 - 3.563e-7 * d
    xe = math.cos(rad(lon_ecl)) * math.cos(rad(lat_ecl))
    ye = math.sin(rad(lon_ecl)) * math.cos(rad(lat_ecl))
    ze = math.sin(rad(lat_ecl))
    yq = ye * math.cos(rad(ecl)) - ze * math.sin(rad(ecl))
    zq = ye * math.sin(rad(ecl)) + ze * math.cos(rad(ecl))
    ra = _rev(deg(math.atan2(yq, xe)))
    dec = deg(math.atan2(zq, math.hypot(xe, yq)))
    ut = when_utc.hour + when_utc.minute / 60 + when_utc.second / 3600
    gmst0 = _rev(Ms + ws + 180)
    lst = _rev(gmst0 + ut * 15 + LON)
    ha = rad(lst - ra)
    la, de = rad(LAT), rad(dec)
    alt = math.asin(math.sin(la) * math.sin(de) + math.cos(la) * math.cos(de) * math.cos(ha))
    az = math.atan2(math.sin(ha), math.cos(ha) * math.sin(la) - math.tan(de) * math.cos(la))
    return deg(alt), _rev(deg(az) + 180)


def sky_state(when, lat, lon):
    """when: aware datetime. Returns dict with sun/moon alt-az (deg, az from north clockwise),
    moon illuminated fraction and whether it is waxing."""
    u = when.astimezone(dt.timezone.utc)
    d = _days(u) + (u.hour + u.minute / 60) / 24.0 * 0  # _days already includes time of day
    slon, Ms, ws = _sun_ecl(d)
    salt, saz = _altaz(slon, 0.0, d, u, Ms, ws, lat, lon)
    mlon, mlat = _moon_ecl(d, Ms, ws)
    malt, maz = _altaz(mlon, mlat, d, u, Ms, ws, lat, lon)
    malt -= 0.95 * math.cos(rad(malt))  # topocentric parallax (moon appears lower)
    elong = _rev(mlon - slon)
    phase_angle = 180 - elong if elong <= 180 else elong - 180  # 0 = full, 180 = new
    illum = (1 + math.cos(rad(phase_angle))) / 2
    return dict(sun_alt=salt, sun_az=saz, moon_alt=malt, moon_az=maz,
                moon_phase_angle=phase_angle, moon_illum=illum, waxing=elong < 180)


