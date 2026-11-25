
import sys, json, time, cv2
sys.path.insert(0, '/Users/preetpatel/Documents/wallpapers/render')
import timeofday as T
for it in json.load(open(sys.argv[1])):
    t0 = time.time()
    img, st = T.render(T.parse_when(it["when"]), it["cover"], season=it["season"], weather=it["wx"], intensity=it["intensity"])
    cv2.imwrite(it["out"], T.to8(img))
    print(json.dumps(dict(id=it["id"], seconds=round(time.time() - t0, 2), sun_alt=round(st["sun_alt"], 1))), flush=True)
