-- 多人協作旅遊行程規劃系統：完整 MySQL 資料庫
DROP DATABASE IF EXISTS `travel_together`;
CREATE DATABASE `travel_together` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `travel_together`;
SET FOREIGN_KEY_CHECKS=0;

CREATE TABLE users (
 user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 username VARCHAR(50) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL,
 full_name VARCHAR(100) NOT NULL,
 nickname VARCHAR(100),
 email VARCHAR(150) NOT NULL UNIQUE,
 phone VARCHAR(30),
 avatar_path VARCHAR(255),
 role ENUM('member','content_admin','system_admin') NOT NULL DEFAULT 'member',
 status ENUM('active','disabled','deleted') NOT NULL DEFAULT 'active',
 last_login_at DATETIME,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE categories (
 category_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 category_type ENUM('trip','attraction','restaurant','accommodation','expense') NOT NULL,
 category_name VARCHAR(100) NOT NULL,
 description VARCHAR(255),
 status ENUM('active','hidden') NOT NULL DEFAULT 'active',
 created_by BIGINT UNSIGNED,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE(category_type,category_name),
 FOREIGN KEY(created_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE countries (
 country_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 name VARCHAR(100) NOT NULL UNIQUE,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE cities (
 city_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 country_id BIGINT UNSIGNED NOT NULL,
 name VARCHAR(100) NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE(country_id,name),
 FOREIGN KEY(country_id) REFERENCES countries(country_id)
) ENGINE=InnoDB;

CREATE TABLE attractions (
 attraction_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 category_id BIGINT UNSIGNED,
 name VARCHAR(150) NOT NULL,
 country_id BIGINT UNSIGNED NOT NULL,
 city_id BIGINT UNSIGNED NOT NULL,
 address VARCHAR(255),
 latitude DECIMAL(10,7),
 longitude DECIMAL(10,7),
 opening_hours VARCHAR(255),
 ticket_price DECIMAL(12,2) NOT NULL DEFAULT 0,
 suggested_duration_minutes INT UNSIGNED,
 description TEXT,
 website_url VARCHAR(500),
 image_path VARCHAR(255),
 is_popular BOOLEAN NOT NULL DEFAULT FALSE,
 status ENUM('active','hidden','pending') NOT NULL DEFAULT 'active',
 ai_verified_at DATETIME,
 ai_verified_by BIGINT UNSIGNED,
 created_by BIGINT UNSIGNED,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(category_id) REFERENCES categories(category_id) ON DELETE SET NULL,
 FOREIGN KEY(country_id) REFERENCES countries(country_id),
 FOREIGN KEY(city_id) REFERENCES cities(city_id),
 FOREIGN KEY(ai_verified_by) REFERENCES users(user_id) ON DELETE SET NULL,
 FOREIGN KEY(created_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE restaurants (
 restaurant_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 category_id BIGINT UNSIGNED,
 name VARCHAR(150) NOT NULL,
 country_id BIGINT UNSIGNED NOT NULL,
 city_id BIGINT UNSIGNED NOT NULL,
 address VARCHAR(255),
 cuisine_type VARCHAR(100),
 price_level ENUM('low','medium','high','luxury') DEFAULT 'medium',
 opening_hours VARCHAR(255),
 description TEXT,
 website_url VARCHAR(500),
 image_path VARCHAR(255),
 status ENUM('active','hidden','pending') NOT NULL DEFAULT 'active',
 ai_verified_at DATETIME,
 ai_verified_by BIGINT UNSIGNED,
 created_by BIGINT UNSIGNED,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(category_id) REFERENCES categories(category_id) ON DELETE SET NULL,
 FOREIGN KEY(country_id) REFERENCES countries(country_id),
 FOREIGN KEY(city_id) REFERENCES cities(city_id),
 FOREIGN KEY(ai_verified_by) REFERENCES users(user_id) ON DELETE SET NULL,
 FOREIGN KEY(created_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE accommodations (
 accommodation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 category_id BIGINT UNSIGNED,
 name VARCHAR(150) NOT NULL,
 country_id BIGINT UNSIGNED NOT NULL,
 city_id BIGINT UNSIGNED NOT NULL,
 address VARCHAR(255),
 accommodation_type VARCHAR(100),
 price_per_night DECIMAL(12,2) NOT NULL DEFAULT 0,
 check_in_time TIME,
 check_out_time TIME,
 description TEXT,
 website_url VARCHAR(500),
 image_path VARCHAR(255),
 status ENUM('active','hidden','pending') NOT NULL DEFAULT 'active',
 ai_verified_at DATETIME,
 ai_verified_by BIGINT UNSIGNED,
 created_by BIGINT UNSIGNED,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(category_id) REFERENCES categories(category_id) ON DELETE SET NULL,
 FOREIGN KEY(country_id) REFERENCES countries(country_id),
 FOREIGN KEY(city_id) REFERENCES cities(city_id),
 FOREIGN KEY(ai_verified_by) REFERENCES users(user_id) ON DELETE SET NULL,
 FOREIGN KEY(created_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE trips (
 trip_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 owner_id BIGINT UNSIGNED NOT NULL,
 category_id BIGINT UNSIGNED,
 trip_name VARCHAR(150) NOT NULL,
 cover_image_path VARCHAR(255),
 country VARCHAR(100),
 city VARCHAR(100),
 start_date DATE NOT NULL,
 end_date DATE NOT NULL,
 people_count INT UNSIGNED NOT NULL DEFAULT 1,
 total_budget DECIMAL(14,2) NOT NULL DEFAULT 0,
 currency CHAR(3) NOT NULL DEFAULT 'TWD',
 introduction TEXT,
 visibility ENUM('private','public','link_only') NOT NULL DEFAULT 'private',
 status ENUM('planning','upcoming','completed','cancelled') NOT NULL DEFAULT 'planning',
 share_token VARCHAR(100) UNIQUE,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(owner_id) REFERENCES users(user_id),
 FOREIGN KEY(category_id) REFERENCES categories(category_id) ON DELETE SET NULL,
 CHECK(end_date>=start_date), CHECK(people_count>=1), CHECK(total_budget>=0)
) ENGINE=InnoDB;

CREATE TABLE trip_members (
 trip_member_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 trip_id BIGINT UNSIGNED NOT NULL,
 user_id BIGINT UNSIGNED NOT NULL,
 member_role ENUM('owner','editor','viewer') NOT NULL DEFAULT 'viewer',
 join_status ENUM('invited','accepted','rejected','left','removed') NOT NULL DEFAULT 'invited',
 joined_at DATETIME,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(trip_id,user_id),
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE trip_invitations (
 invitation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 trip_id BIGINT UNSIGNED NOT NULL,
 inviter_id BIGINT UNSIGNED NOT NULL,
 invitee_id BIGINT UNSIGNED,
 invitee_email VARCHAR(150),
 invite_code VARCHAR(50) NOT NULL UNIQUE,
 invite_token VARCHAR(120) UNIQUE,
 assigned_role ENUM('editor','viewer') NOT NULL DEFAULT 'viewer',
 status ENUM('pending','accepted','rejected','expired','cancelled') NOT NULL DEFAULT 'pending',
 expires_at DATETIME,
 responded_at DATETIME,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(inviter_id) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY(invitee_id) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE itineraries (
 itinerary_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 trip_id BIGINT UNSIGNED NOT NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 itinerary_date DATE NOT NULL,
 item_type ENUM('attraction','restaurant','accommodation','transport','shopping','meeting','free_time','other') NOT NULL,
 title VARCHAR(150) NOT NULL,
 start_time TIME,
 end_time TIME,
 address VARCHAR(255),
 transport_method VARCHAR(100),
 transport_minutes INT UNSIGNED DEFAULT 0,
 estimated_cost DECIMAL(12,2) NOT NULL DEFAULT 0,
 notes TEXT,
 attraction_id BIGINT UNSIGNED,
 restaurant_id BIGINT UNSIGNED,
 accommodation_id BIGINT UNSIGNED,
 sort_order INT UNSIGNED NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(created_by) REFERENCES users(user_id),
 FOREIGN KEY(attraction_id) REFERENCES attractions(attraction_id) ON DELETE SET NULL,
 FOREIGN KEY(restaurant_id) REFERENCES restaurants(restaurant_id) ON DELETE SET NULL,
 FOREIGN KEY(accommodation_id) REFERENCES accommodations(accommodation_id) ON DELETE SET NULL,
 CHECK(estimated_cost>=0)
) ENGINE=InnoDB;

CREATE TABLE proposals (
 proposal_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 trip_id BIGINT UNSIGNED NOT NULL,
 proposer_id BIGINT UNSIGNED NOT NULL,
 proposal_type ENUM('attraction','restaurant','accommodation','activity','transport','date','other') NOT NULL,
 title VARCHAR(150) NOT NULL,
 location VARCHAR(255),
 description TEXT,
 estimated_cost DECIMAL(12,2) NOT NULL DEFAULT 0,
 proposed_date DATE,
 website_url VARCHAR(500),
 image_path VARCHAR(255),
 status ENUM('discussing','voting','approved','rejected','added') NOT NULL DEFAULT 'discussing',
 content_review_status ENUM('not_required','pending','approved','returned') NOT NULL DEFAULT 'not_required',
 reviewed_by BIGINT UNSIGNED,
 reviewed_at DATETIME,
 review_note VARCHAR(500),
 deadline_at DATETIME,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(proposer_id) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY(reviewed_by) REFERENCES users(user_id) ON DELETE SET NULL,
 CHECK(estimated_cost>=0)
) ENGINE=InnoDB;

CREATE TABLE votes (
 vote_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 trip_id BIGINT UNSIGNED NOT NULL,
 proposal_id BIGINT UNSIGNED,
 created_by BIGINT UNSIGNED NOT NULL,
 title VARCHAR(150) NOT NULL,
 vote_type ENUM('approval','multiple_choice','single_choice') NOT NULL DEFAULT 'approval',
 status ENUM('open','closed','cancelled') NOT NULL DEFAULT 'open',
 allow_change BOOLEAN NOT NULL DEFAULT TRUE,
 deadline_at DATETIME NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(proposal_id) REFERENCES proposals(proposal_id) ON DELETE SET NULL,
 FOREIGN KEY(created_by) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE vote_options (
 option_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 vote_id BIGINT UNSIGNED NOT NULL,
 option_text VARCHAR(255) NOT NULL,
 sort_order INT UNSIGNED NOT NULL DEFAULT 1,
 UNIQUE(vote_id,option_text),
 FOREIGN KEY(vote_id) REFERENCES votes(vote_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE vote_records (
 vote_record_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 vote_id BIGINT UNSIGNED NOT NULL,
 option_id BIGINT UNSIGNED,
 user_id BIGINT UNSIGNED NOT NULL,
 approval_choice ENUM('agree','disagree','neutral'),
 voted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE(vote_id,user_id),
 FOREIGN KEY(vote_id) REFERENCES votes(vote_id) ON DELETE CASCADE,
 FOREIGN KEY(option_id) REFERENCES vote_options(option_id) ON DELETE CASCADE,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE comments (
 comment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 trip_id BIGINT UNSIGNED NOT NULL,
 itinerary_id BIGINT UNSIGNED,
 proposal_id BIGINT UNSIGNED,
 user_id BIGINT UNSIGNED NOT NULL,
 parent_comment_id BIGINT UNSIGNED,
 content TEXT NOT NULL,
 status ENUM('visible','hidden','deleted') NOT NULL DEFAULT 'visible',
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(itinerary_id) REFERENCES itineraries(itinerary_id) ON DELETE CASCADE,
 FOREIGN KEY(proposal_id) REFERENCES proposals(proposal_id) ON DELETE CASCADE,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY(parent_comment_id) REFERENCES comments(comment_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE expenses (
 expense_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 trip_id BIGINT UNSIGNED NOT NULL,
 category_id BIGINT UNSIGNED,
 created_by BIGINT UNSIGNED NOT NULL,
 payer_id BIGINT UNSIGNED NOT NULL,
 expense_name VARCHAR(150) NOT NULL,
 expense_type ENUM('estimated','actual') NOT NULL DEFAULT 'actual',
 scope ENUM('shared','personal') NOT NULL DEFAULT 'shared',
 amount DECIMAL(14,2) NOT NULL,
 currency CHAR(3) NOT NULL DEFAULT 'TWD',
 expense_date DATE NOT NULL,
 note TEXT,
 receipt_path VARCHAR(255),
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(category_id) REFERENCES categories(category_id) ON DELETE SET NULL,
 FOREIGN KEY(created_by) REFERENCES users(user_id),
 FOREIGN KEY(payer_id) REFERENCES users(user_id),
 CHECK(amount>=0)
) ENGINE=InnoDB;

CREATE TABLE expense_splits (
 split_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 expense_id BIGINT UNSIGNED NOT NULL,
 user_id BIGINT UNSIGNED NOT NULL,
 split_amount DECIMAL(14,2) NOT NULL,
 settlement_status ENUM('unpaid','paid','waived') NOT NULL DEFAULT 'unpaid',
 paid_at DATETIME,
 UNIQUE(expense_id,user_id),
 FOREIGN KEY(expense_id) REFERENCES expenses(expense_id) ON DELETE CASCADE,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
 CHECK(split_amount>=0)
) ENGINE=InnoDB;

CREATE TABLE favorites (
 favorite_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 user_id BIGINT UNSIGNED NOT NULL,
 target_type ENUM('trip','attraction') NOT NULL,
 trip_id BIGINT UNSIGNED,
 attraction_id BIGINT UNSIGNED,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(user_id,trip_id),
 UNIQUE(user_id,attraction_id),
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(attraction_id) REFERENCES attractions(attraction_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE notifications (
 notification_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 user_id BIGINT UNSIGNED NOT NULL,
 trip_id BIGINT UNSIGNED,
 notification_type ENUM('invitation','trip_edit','comment','vote','permission','departure','system') NOT NULL,
 title VARCHAR(150) NOT NULL,
 message TEXT NOT NULL,
 target_url VARCHAR(500),
 is_read BOOLEAN NOT NULL DEFAULT FALSE,
 read_at DATETIME,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE edit_logs (
 edit_log_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 trip_id BIGINT UNSIGNED NOT NULL,
 user_id BIGINT UNSIGNED NOT NULL,
 target_table VARCHAR(100) NOT NULL,
 target_id BIGINT UNSIGNED NOT NULL,
 action ENUM('create','update','delete','restore') NOT NULL,
 before_data JSON,
 after_data JSON,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE reports (
 report_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 reporter_id BIGINT UNSIGNED NOT NULL,
 target_type ENUM('trip','comment','proposal','user','other') NOT NULL,
 target_id BIGINT UNSIGNED NOT NULL,
 reason VARCHAR(255) NOT NULL,
 description TEXT,
 status ENUM('pending','processing','resolved','rejected') NOT NULL DEFAULT 'pending',
 handled_by BIGINT UNSIGNED,
 handling_result TEXT,
 handled_at DATETIME,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(reporter_id) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY(handled_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE announcements (
 announcement_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 created_by BIGINT UNSIGNED NOT NULL,
 title VARCHAR(150) NOT NULL,
 content TEXT NOT NULL,
 is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
 status ENUM('draft','published','hidden') NOT NULL DEFAULT 'draft',
 publish_at DATETIME,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY(created_by) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE admin_logs (
 admin_log_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 admin_id BIGINT UNSIGNED NOT NULL,
 action VARCHAR(100) NOT NULL,
 target_type VARCHAR(100),
 target_id BIGINT UNSIGNED,
 description TEXT,
 ip_address VARCHAR(45),
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(admin_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE attachments (
 attachment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 uploaded_by BIGINT UNSIGNED NOT NULL,
 trip_id BIGINT UNSIGNED,
 itinerary_id BIGINT UNSIGNED,
 proposal_id BIGINT UNSIGNED,
 file_name VARCHAR(255) NOT NULL,
 stored_name VARCHAR(255) NOT NULL,
 file_path VARCHAR(500) NOT NULL,
 file_type VARCHAR(100) NOT NULL,
 file_size BIGINT UNSIGNED NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(uploaded_by) REFERENCES users(user_id) ON DELETE CASCADE,
 FOREIGN KEY(trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
 FOREIGN KEY(itinerary_id) REFERENCES itineraries(itinerary_id) ON DELETE CASCADE,
 FOREIGN KEY(proposal_id) REFERENCES proposals(proposal_id) ON DELETE CASCADE
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS=1;

-- 測試帳號，密碼皆為 123456
INSERT INTO users(username,password_hash,full_name,nickname,email,role) VALUES
('member01','pbkdf2:sha256:600000$67d6646475fb2904$439c40d8eb4f1f1e9de61f14cc0abafae1f4b88c3766c55cdf8827b959c106e9','一般會員測試','旅遊小幫手','member01@example.com','member'),
('contentadmin','pbkdf2:sha256:600000$67d6646475fb2904$439c40d8eb4f1f1e9de61f14cc0abafae1f4b88c3766c55cdf8827b959c106e9','旅遊內容管理員','內容管理員','contentadmin@example.com','content_admin'),
('admin','pbkdf2:sha256:600000$67d6646475fb2904$439c40d8eb4f1f1e9de61f14cc0abafae1f4b88c3766c55cdf8827b959c106e9','系統管理員','系統管理員','admin@example.com','system_admin');

INSERT INTO categories(category_type,category_name,description,created_by) VALUES
('trip','自由行','一般自由行程',3),
('trip','畢業旅行','學生畢業旅行',3),
('attraction','景點','一般觀光景點',2),
('restaurant','日式料理','日本料理',2),
('accommodation','飯店','一般旅館及飯店',2),
('expense','交通','交通相關費用',3),
('expense','餐飲','餐飲相關費用',3),
('expense','住宿','住宿相關費用',3);

INSERT INTO countries(name) VALUES
('台灣'),
('日本');

INSERT INTO cities(country_id,name) VALUES
(1,'台北市'),
(1,'高雄市'),
(2,'東京都');

INSERT INTO attractions(category_id,name,country_id,city_id,address,ticket_price,suggested_duration_minutes,description,is_popular,created_by)
VALUES(3,'台北101',1,1,'台北市信義區信義路五段7號',600,120,'台北代表性地標與觀景台',TRUE,2);

INSERT INTO trips(owner_id,category_id,trip_name,country,city,start_date,end_date,people_count,total_budget,currency,introduction,visibility,status,share_token)
VALUES(1,1,'台北三天兩夜','台灣','台北市','2026-08-10','2026-08-12',3,15000,'TWD','測試用多人協作旅遊行程','private','planning','demo-taipei-2026');

INSERT INTO trip_members(trip_id,user_id,member_role,join_status,joined_at)
VALUES(1,1,'owner','accepted',NOW());

INSERT INTO itineraries(trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,address,estimated_cost,attraction_id,sort_order)
VALUES(1,1,'2026-08-10','attraction','參觀台北101','10:00','12:00','台北市信義區信義路五段7號',600,1,1);

INSERT INTO proposals(trip_id,proposer_id,proposal_type,title,location,description,estimated_cost,proposed_date,status,content_review_status)
VALUES(1,1,'attraction','貓空纜車','台北市文山區','會員提議加入貓空纜車景點，可俯瞰台北市景',300,'2026-08-11','discussing','pending');

INSERT INTO announcements(created_by,title,content,is_pinned,status,publish_at)
VALUES(3,'歡迎使用 Travel Together','歡迎使用多人協作旅遊行程規劃系統',TRUE,'published',NOW());

CREATE VIEW vw_trip_expense_summary AS
SELECT t.trip_id,t.trip_name,t.total_budget,t.currency,
COALESCE(SUM(CASE WHEN e.expense_type='actual' THEN e.amount ELSE 0 END),0) actual_expense,
t.total_budget-COALESCE(SUM(CASE WHEN e.expense_type='actual' THEN e.amount ELSE 0 END),0) remaining_budget
FROM trips t LEFT JOIN expenses e ON e.trip_id=t.trip_id
GROUP BY t.trip_id,t.trip_name,t.total_budget,t.currency;

CREATE VIEW vw_popular_attractions AS
SELECT a.attraction_id,a.name,c.name AS country,ci.name AS city,
COUNT(DISTINCT f.favorite_id) favorite_count,
COUNT(DISTINCT i.itinerary_id) itinerary_count
FROM attractions a
JOIN countries c ON c.country_id=a.country_id
JOIN cities ci ON ci.city_id=a.city_id
LEFT JOIN favorites f ON f.attraction_id=a.attraction_id
LEFT JOIN itineraries i ON i.attraction_id=a.attraction_id
GROUP BY a.attraction_id,a.name,c.name,ci.name;

SELECT '資料庫建立完成' AS message;
