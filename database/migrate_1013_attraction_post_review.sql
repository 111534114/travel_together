-- 景點相簿加上審核機制：新貼文預設「待審核」，要內容管理員核准後其他人才看得到，
-- 避免有人上傳不當（例如色情）圖片時其他會員會直接看到。
ALTER TABLE attraction_posts
    ADD COLUMN review_status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending' AFTER caption,
    ADD COLUMN reviewed_by BIGINT UNSIGNED NULL AFTER review_status,
    ADD COLUMN reviewed_at DATETIME NULL AFTER reviewed_by,
    ADD COLUMN review_note VARCHAR(255) NULL AFTER reviewed_at,
    ADD CONSTRAINT fk_attraction_posts_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES users(user_id) ON DELETE SET NULL;

-- 這個功能上線前就已經存在的貼文直接視為已核准，避免使用者原本看得到的照片突然消失不見
UPDATE attraction_posts SET review_status='approved', reviewed_at=NOW() WHERE review_status='pending';
