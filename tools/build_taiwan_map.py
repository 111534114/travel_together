# 把 npm 套件 taiwan-atlas 的縣市 TopoJSON(counties-10t.json)轉成「目的地天氣」頁面用的 SVG 地圖 partial
import json, math, sys
src, out = sys.argv[1], sys.argv[2]
t = json.load(open(src, encoding='utf-8'))
NAMES = {'Lienchiang County':'連江縣','Yilan County':'宜蘭縣','Changhua County':'彰化縣','Nantou County':'南投縣','Yunlin County':'雲林縣','Keelung City':'基隆市','Taipei City':'台北市','New Taipei City':'新北市','Taichung City':'台中市','Tainan City':'台南市','Taoyuan City':'桃園市','Miaoli County':'苗栗縣','Chiayi City':'嘉義市','Chiayi County':'嘉義縣','Kinmen County':'金門縣','Kaohsiung City':'高雄市','Taitung County':'台東縣','Hualien County':'花蓮縣','Penghu County':'澎湖縣','Hsinchu City':'新竹市','Hsinchu County':'新竹縣','Pingtung County':'屏東縣'}
sx, sy = t['transform']['scale']; tx, ty = t['transform']['translate']
arcs = []
for arc in t['arcs']:
    x = y = 0; pts = []
    for dx, dy in arc:
        x += dx; y += dy; pts.append((x*sx+tx, y*sy+ty))
    arcs.append(pts)
def ring(idx):
    pts = []
    for i in idx:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts
# 金門、馬祖離本島太遠：平移到台灣海峽左上角的空白處，並畫框標示
# (原中心經度, 原中心緯度, 新中心經度, 新中心緯度, 放大倍率)
SHIFT = {'金門縣': (118.35, 24.45, 119.62, 24.22, 1.3), '連江縣': (120.2, 26.17, 119.82, 24.98, 1.4)}
def move(name, lon, lat):
    if name not in SHIFT: return lon, lat
    a, b, c, d, f = SHIFT[name]
    return c + (lon - a) * f, d + (lat - b) * f
LON0, LON1, LAT0, LAT1 = 119.25, 122.1, 21.85, 25.45
K = math.cos(math.radians(23.7)); W = 360.0
scale = W / ((LON1 - LON0) * K)
H = (LAT1 - LAT0) * scale
def proj(lon, lat): return ((lon - LON0) * K * scale, (LAT1 - lat) * scale)
paths = {}; boxes = {}
for g in t['objects']['counties']['geometries']:
    name = NAMES[g['properties']['COUNTYENG']]
    polys = g['arcs'] if g['type'] == 'MultiPolygon' else [g['arcs']]
    d = []
    for poly in polys:
        rings = [ring(r) for r in poly]
        clon = sum(p[0] for p in rings[0]) / len(rings[0]); clat = sum(p[1] for p in rings[0]) / len(rings[0])
        if name == '金門縣' and clon > 119: continue  # 烏坵太遠，不畫
        clon, clat = move(name, clon, clat)
        if not (LON0 < clon < LON1 and LAT0 < clat < LAT1): continue  # 東沙、南沙等遠方島嶼不畫
        for r in rings:
            pts = []; last = None
            for lon, lat in r:
                p = proj(*move(name, lon, lat))
                if last is None or math.hypot(p[0]-last[0], p[1]-last[1]) >= 0.6:
                    pts.append(p); last = p
            if len(pts) < 3: continue
            d.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in pts) + 'Z')
            if name in SHIFT or name == '澎湖縣':
                xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
                b=boxes.setdefault(name,[1e9,1e9,-1e9,-1e9]); b[0]=min(b[0],*xs); b[1]=min(b[1],*ys); b[2]=max(b[2],*xs); b[3]=max(b[3],*ys)
    paths[name] = ''.join(d)
lines = ['{# 台灣縣市地圖(由 npm 套件 taiwan-atlas 的縣市邊界資料轉成 SVG，原始資料：內政部國土測繪中心)。',
         '   金門、馬祖已平移並放大到左上角的框內；東沙、南沙等遠方島嶼不顯示。',
         '   每個縣市是一個 path，data-county 為縣市名稱；離島外框(rect)也帶 data-county，整個框都能點。',
         '   重新產生：python tools/build_taiwan_map.py <counties-10t.json> templates/partials/taiwan_map.html #}',
         f'<svg class="tw-map" viewBox="0 0 {W:.0f} {H:.0f}" role="group" aria-label="台灣縣市地圖">']
for name, (x0, y0, x1, y1) in boxes.items():
    pad = 6
    lines.append(f'  <rect class="tw-map-inset" data-county="{name}" x="{x0-pad:.1f}" y="{y0-pad-12:.1f}" width="{x1-x0+2*pad:.1f}" height="{y1-y0+2*pad+12:.1f}" rx="6"></rect>')
    lines.append(f'  <text class="tw-map-inset-label" x="{x0-pad+5:.1f}" y="{y0-pad-2:.1f}">{name}</text>')
for name, d in paths.items():
    lines.append(f'  <path class="tw-county" data-county="{name}" d="{d}"><title>{name}</title></path>')
lines.append('</svg>')
open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print(len(paths), 'counties', round(sum(map(len, paths.values()))/1024), 'KB', 'H=', round(H))
