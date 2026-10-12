-- 景點相簿支援一篇貼文多張照片：新增 attraction_post_images 子表，
-- 把原本 attraction_posts.image_path 的既有資料搬過去，再移除舊欄位。
CREATE TABLE attraction_post_images (
    image_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    post_id BIGINT UNSIGNED NOT NULL,
    image_path VARCHAR(255) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    FOREIGN KEY (post_id) REFERENCES attraction_posts(post_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO attraction_post_images (post_id, image_path, sort_order)
SELECT post_id, image_path, 0 FROM attraction_posts WHERE image_path IS NOT NULL;

ALTER TABLE attraction_posts DROP COLUMN image_path;
