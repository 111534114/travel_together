-- Restore image links for attractions whose uploaded files are no longer present.
-- Paths are relative to the Flask static directory. Leave other images untouched.
UPDATE attractions SET image_path = 'images/美堤河濱公園.jpg' WHERE name = '美堤河濱公園' AND image_path LIKE 'uploads/attractions/%';
UPDATE attractions SET image_path = 'images/碧湖公園 兒童遊戲場.jpg' WHERE name = '碧湖公園 兒童遊戲場' AND image_path LIKE 'uploads/attractions/%';
UPDATE attractions SET image_path = 'images/石潭公園.jpg' WHERE name = '石潭公園' AND image_path LIKE 'uploads/attractions/%';
UPDATE attractions SET image_path = 'images/紫陽公園.jpg' WHERE name = '紫陽公園' AND image_path LIKE 'uploads/attractions/%';
UPDATE attractions SET image_path = 'images/成功公園.jpg' WHERE name = '成功公園' AND image_path LIKE 'uploads/attractions/%';
UPDATE attractions SET image_path = 'images/港墘公園.jpg' WHERE name = '港墘公園' AND image_path LIKE 'uploads/attractions/%';
UPDATE attractions SET image_path = 'images/東京鐵塔.jpg' WHERE name = '東京鐵塔' AND image_path LIKE 'uploads/attractions/%';
UPDATE attractions SET image_path = 'images/晴空塔.jpg' WHERE name = '東京晴空塔' AND image_path LIKE 'uploads/attractions/%';
UPDATE attractions SET image_path = 'images/涉谷sky.jpg' WHERE name = '澀谷 SKY' AND image_path LIKE 'uploads/attractions/%';
UPDATE attractions SET image_path = 'images/新宿御苑.jpg' WHERE name = '新宿御苑' AND image_path LIKE 'uploads/attractions/%';
