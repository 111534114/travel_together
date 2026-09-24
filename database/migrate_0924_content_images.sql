-- 將 2026-09-24 隨專案提供的內容圖片連結到 static/images。
-- image_path 一律儲存相對於 Flask static 資料夾的路徑。

UPDATE attractions SET image_path = 'images/故宮.jpg' WHERE name = '國立故宮博物院';
UPDATE attractions SET image_path = 'images/士林夜市.jpg' WHERE name = '士林夜市';
UPDATE attractions SET image_path = 'images/西門町.jpg' WHERE name = '西門町';
UPDATE attractions SET image_path = 'images/中正紀念堂.jpg' WHERE name = '國立中正紀念堂';
UPDATE attractions SET image_path = 'images/大稻埕.jpg' WHERE name = '大稻埕碼頭貨櫃市集';
UPDATE attractions SET image_path = 'images/華山.jpg' WHERE name = '華山1914文化創意產業園區';
UPDATE attractions SET image_path = 'images/台北101.jpg' WHERE name = '台北101';

UPDATE restaurants SET image_path = 'images/鼎泰豐.jpg' WHERE name = '鼎泰豐 信義店';
UPDATE restaurants SET image_path = 'images/阿宗.jpg' WHERE name = '阿宗麵線';
UPDATE restaurants SET image_path = 'images/度小月.jpg' WHERE name = '度小月擔仔麵 台北忠孝店';
UPDATE restaurants SET image_path = 'images/春水堂.png' WHERE name = '春水堂 南港店';
UPDATE restaurants SET image_path = 'images/新頁.jpg' WHERE name = '欣葉台菜創始店';

UPDATE accommodations SET image_path = 'images/images.jpg' WHERE name = '台北君悅酒店';
UPDATE accommodations SET image_path = 'images/w.jpg' WHERE name = '台北W飯店';
UPDATE accommodations SET image_path = 'images/喜來登.jpg' WHERE name = '台北喜來登大飯店';
UPDATE accommodations SET image_path = 'images/美麗信.jpg' WHERE name = '美麗信花園酒店';
