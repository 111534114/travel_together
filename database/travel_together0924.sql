-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- 主機： 127.0.0.1
-- 產生時間： 2026-09-24 03:58:48
-- 伺服器版本： 10.4.32-MariaDB
-- PHP 版本： 8.0.30

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- 資料庫： `travel_together`
--

-- --------------------------------------------------------

--
-- 資料表結構 `accommodations`
--

CREATE TABLE `accommodations` (
  `accommodation_id` bigint(20) UNSIGNED NOT NULL,
  `category_id` bigint(20) UNSIGNED DEFAULT NULL,
  `name` varchar(150) NOT NULL,
  `country_id` bigint(20) UNSIGNED NOT NULL,
  `city_id` bigint(20) UNSIGNED NOT NULL,
  `address` varchar(255) DEFAULT NULL,
  `accommodation_type` varchar(100) DEFAULT NULL,
  `price_per_night` decimal(12,2) NOT NULL DEFAULT 0.00,
  `check_in_time` time DEFAULT NULL,
  `check_out_time` time DEFAULT NULL,
  `description` text DEFAULT NULL,
  `website_url` varchar(500) DEFAULT NULL,
  `image_path` varchar(255) DEFAULT NULL,
  `status` enum('active','hidden','pending') NOT NULL DEFAULT 'active',
  `deleted_at` datetime DEFAULT NULL,
  `ai_verified_at` datetime DEFAULT NULL,
  `ai_verified_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `accommodations`
--

INSERT INTO `accommodations` (`accommodation_id`, `category_id`, `name`, `country_id`, `city_id`, `address`, `accommodation_type`, `price_per_night`, `check_in_time`, `check_out_time`, `description`, `website_url`, `image_path`, `status`, `deleted_at`, `ai_verified_at`, `ai_verified_by`, `created_by`, `created_at`, `updated_at`) VALUES
(1, 15, '台北君悅酒店', 1, 1, '110061台灣臺北市信義區西村里松壽路2號', '度假酒店', 0.00, NULL, NULL, '鄰近台北 101 大樓的新潮飯店，附設室外泳池、健身中心、8 間餐廳和酒吧。', 'https://www.hyatt.com/grand-hyatt/en-US/taigh-grand-hyatt-taipei?src=corp_lclb_google_seo_taigh&utm_source=google&utm_medium=organic&utm_campaign=lmr', 'images/images.jpg', 'active', NULL, NULL, NULL, 2, '2026-09-08 18:24:14', '2026-09-23 21:07:37'),
(2, 5, '台北W飯店', 1, 1, '110台灣臺北市信義區興雅里忠孝東路五段10號', '飯店', 0.00, NULL, NULL, '內有奇趣客房的時尚高樓飯店，附設餐廳、水療中心和位於 10 樓的戶外泳池。', 'https://www.marriott.com/en-us/hotels/tpewh-w-taipei/overview/?scid=f2ae0541-1279-4f24-b197-a979c79310b0', 'images/w.jpg', 'active', NULL, NULL, NULL, 2, '2026-09-08 18:24:15', '2026-09-23 21:06:52'),
(3, 5, '台北喜來登大飯店', 1, 1, '100台灣臺北市中正區幸福里忠孝東路一段12號', '飯店', 0.00, NULL, NULL, '高級飯店提供溫馨客房和豪華套房，設有 SPA、屋頂泳池和 9 種餐飲選擇。', 'https://www.marriott.com/en-us/hotels/tpest-sheraton-grand-taipei-hotel/overview/?scid=f2ae0541-1279-4f24-b197-a979c79310b0', 'images/喜來登.jpg', 'active', NULL, NULL, NULL, 2, '2026-09-08 18:24:16', '2026-09-23 21:06:15'),
(4, 5, '美麗信花園酒店', 1, 1, '104台灣臺北市中山區市民大道三段83號', '飯店', 0.00, NULL, NULL, '高級的住宿環境有現代風格的客房，附設餐廳和健身中心，並提供免費早餐。', 'http://www.miramargarden.com.tw/zh-tw/%E5%8F%B0%E5%8C%97%E7%BE%8E%E9%BA%97%E4%BF%A1', 'images/美麗信.jpg', 'active', NULL, NULL, NULL, 2, '2026-09-08 18:24:16', '2026-09-23 21:05:27');

-- --------------------------------------------------------

--
-- 資料表結構 `admin_logs`
--

CREATE TABLE `admin_logs` (
  `admin_log_id` bigint(20) UNSIGNED NOT NULL,
  `admin_id` bigint(20) UNSIGNED NOT NULL,
  `action` varchar(100) NOT NULL,
  `target_type` varchar(100) DEFAULT NULL,
  `target_id` bigint(20) UNSIGNED DEFAULT NULL,
  `description` text DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `admin_logs`
--

INSERT INTO `admin_logs` (`admin_log_id`, `admin_id`, `action`, `target_type`, `target_id`, `description`, `ip_address`, `created_at`) VALUES
(1, 2, 'import_attractions_google', 'attraction', NULL, '從 Google 地圖匯入景點，成功 0 筆，失敗 6 筆', '127.0.0.1', '2026-09-08 18:23:41'),
(2, 2, 'import_attractions_google', 'attraction', NULL, '從 Google 地圖匯入景點，成功 4 筆，失敗 2 筆', '127.0.0.1', '2026-09-08 18:24:10'),
(3, 2, 'import_restaurants_google', 'restaurant', NULL, '從 Google 地圖匯入餐廳，成功 5 筆，失敗 0 筆', '127.0.0.1', '2026-09-08 18:24:14'),
(4, 2, 'import_accommodations_google', 'accommodation', NULL, '從 Google 地圖匯入住宿，成功 4 筆，失敗 0 筆', '127.0.0.1', '2026-09-08 18:24:16'),
(5, 2, 'import_attractions_google', 'attraction', NULL, '從 Google 地圖匯入景點，成功 4 筆，失敗 2 筆', '127.0.0.1', '2026-09-08 18:24:40'),
(6, 2, 'import_attractions_google', 'attraction', NULL, '從 Google 地圖匯入景點，成功 2 筆，失敗 0 筆', '127.0.0.1', '2026-09-08 18:25:17'),
(7, 2, 'approve_proposal', 'proposal', 1, '核准提案', '127.0.0.1', '2026-09-10 10:11:13'),
(8, 2, 'delete_attraction', 'attraction', 1, '刪除景點：台北101', '127.0.0.1', '2026-09-16 09:33:30'),
(9, 2, 'restore_attraction', 'attraction', 1, '從回收桶復原景點：台北101', '127.0.0.1', '2026-09-16 09:33:30'),
(10, 2, 'delete_attraction', 'attraction', 1, '刪除景點：台北101', '127.0.0.1', '2026-09-16 09:33:46'),
(11, 2, 'permanent_delete_attraction', 'attraction', 1, '永久刪除景點：台北101', '127.0.0.1', '2026-09-16 09:33:46'),
(12, 2, 'delete_restaurant', 'restaurant', 1, '刪除餐廳：鼎泰豐 信義店', '127.0.0.1', '2026-09-16 09:39:27'),
(13, 2, 'restore_restaurant', 'restaurant', 1, '從回收桶復原餐廳：鼎泰豐 信義店', '127.0.0.1', '2026-09-16 09:39:27'),
(14, 2, 'delete_accommodation', 'accommodation', 1, '刪除住宿：Grand Hyatt Taipei', '127.0.0.1', '2026-09-16 09:39:27'),
(15, 2, 'restore_accommodation', 'accommodation', 1, '從回收桶復原住宿：Grand Hyatt Taipei', '127.0.0.1', '2026-09-16 09:39:27'),
(16, 2, 'bulk_activate_attractions', 'attraction', NULL, '批次啟用 2 筆景點', '127.0.0.1', '2026-09-17 10:01:53'),
(17, 2, 'bulk_activate_attractions', 'attraction', NULL, '批次啟用 1 筆景點', '127.0.0.1', '2026-09-17 10:01:57'),
(18, 2, 'delete_attraction', 'attraction', 13, '刪除景點：台北101', '127.0.0.1', '2026-09-17 10:02:19'),
(19, 2, 'restore_attraction', 'attraction', 13, '從回收桶復原景點：台北101', '127.0.0.1', '2026-09-17 10:02:21'),
(20, 2, 'import_preset_cities', 'country', 1, '一鍵匯入 台灣 城市 20 筆', '127.0.0.1', '2026-09-17 10:08:45'),
(21, 2, 'import_preset_cities', 'country', 1, '一鍵匯入 台灣 城市 0 筆', '127.0.0.1', '2026-09-17 10:08:56'),
(22, 2, 'import_preset_cities', 'country', 2, '一鍵匯入 日本 城市 46 筆', '127.0.0.1', '2026-09-17 10:08:56'),
(23, 2, 'delete_city', 'city', 21, '刪除城市：南投縣', '127.0.0.1', '2026-09-17 10:09:12'),
(24, 2, 'import_preset_cities', 'country', 1, '一鍵匯入 台灣 城市 20 筆', '127.0.0.1', '2026-09-17 10:10:56'),
(25, 2, 'import_preset_cities', 'country', 2, '一鍵匯入 日本 城市 46 筆', '127.0.0.1', '2026-09-17 10:10:59'),
(26, 2, 'import_preset_cities', 'country', 4, '一鍵匯入 泰國 城市 76 筆', '127.0.0.1', '2026-09-17 10:16:49'),
(27, 2, 'import_preset_cities', 'country', 3, '一鍵匯入 韓國 城市 15 筆', '127.0.0.1', '2026-09-17 10:16:49'),
(28, 2, 'import_preset_cities', 'country', 3, '一鍵匯入 韓國 城市 15 筆', '127.0.0.1', '2026-09-17 10:23:15'),
(29, 2, 'import_preset_cities', 'country', 4, '一鍵匯入 泰國 城市 76 筆', '127.0.0.1', '2026-09-17 10:23:17'),
(30, 2, 'import_preset_cities', 'country', 6, '一鍵匯入 香港 城市 18 筆', '127.0.0.1', '2026-09-17 10:46:42'),
(31, 2, 'create_country', 'country', 8, '新增國家：測試不存在的地方xyz123', '127.0.0.1', '2026-09-17 10:46:52'),
(32, 2, 'import_preset_cities', 'country', 6, '一鍵匯入 香港 城市 18 筆', '127.0.0.1', '2026-09-17 10:54:53'),
(33, 2, 'create_country', 'country', 9, '新增國家：越南', '127.0.0.1', '2026-09-17 10:55:10'),
(34, 2, 'import_preset_cities', 'country', 9, '一鍵匯入 越南 城市 34 筆', '127.0.0.1', '2026-09-17 10:55:30'),
(35, 2, 'verify_ai_data', 'attraction', 13, '標記景點資料已確認', '127.0.0.1', '2026-09-17 10:59:57'),
(36, 2, 'verify_ai_data', 'attraction', 4, '標記景點資料已確認', '127.0.0.1', '2026-09-17 11:00:09'),
(37, 2, 'create_city', 'city', 395, '新增城市：測試新城市', '127.0.0.1', '2026-09-17 11:11:13'),
(38, 2, 'verify_ai_data', 'attraction', 5, '標記景點資料已確認', '127.0.0.1', '2026-09-23 09:15:34'),
(39, 2, 'verify_ai_data', 'attraction', 3, '標記景點資料已確認', '127.0.0.1', '2026-09-23 09:15:36'),
(40, 2, 'verify_ai_data', 'attraction', 2, '標記景點資料已確認', '127.0.0.1', '2026-09-23 09:15:37'),
(41, 2, 'verify_ai_data', 'attraction', 11, '標記景點資料已確認', '127.0.0.1', '2026-09-23 09:15:38'),
(42, 2, 'verify_ai_data', 'attraction', 10, '標記景點資料已確認', '127.0.0.1', '2026-09-23 09:15:38'),
(44, 2, 'update_restaurant', 'restaurant', 4, '更新餐廳：春水堂 南港店', '127.0.0.1', '2026-09-23 20:57:41'),
(45, 2, 'auto_verify_ai_data', 'restaurant', 4, '系統自動審核通過餐廳資料(欄位皆已填寫)', '127.0.0.1', '2026-09-23 20:57:45'),
(46, 2, 'update_attraction', 'attraction', 13, '更新景點：台北101', '127.0.0.1', '2026-09-23 20:59:50'),
(47, 2, 'update_attraction', 'attraction', 11, '更新景點：華山1914文化創意產業園區', '127.0.0.1', '2026-09-23 21:00:32'),
(48, 2, 'update_attraction', 'attraction', 10, '更新景點：大稻埕碼頭貨櫃市集', '127.0.0.1', '2026-09-23 21:01:09'),
(49, 2, 'update_attraction', 'attraction', 5, '更新景點：國立中正紀念堂', '127.0.0.1', '2026-09-23 21:01:36'),
(50, 2, 'update_attraction', 'attraction', 4, '更新景點：西門町', '127.0.0.1', '2026-09-23 21:02:04'),
(51, 2, 'update_attraction', 'attraction', 3, '更新景點：士林夜市', '127.0.0.1', '2026-09-23 21:02:27'),
(52, 2, 'update_attraction', 'attraction', 2, '更新景點：國立故宮博物院', '127.0.0.1', '2026-09-23 21:02:46'),
(53, 2, 'update_restaurant', 'restaurant', 5, '更新餐廳：欣葉台菜創始店', '127.0.0.1', '2026-09-23 21:03:16'),
(54, 2, 'update_restaurant', 'restaurant', 4, '更新餐廳：春水堂 南港店', '127.0.0.1', '2026-09-23 21:03:42'),
(55, 2, 'update_restaurant', 'restaurant', 3, '更新餐廳：度小月擔仔麵 台北忠孝店', '127.0.0.1', '2026-09-23 21:04:10'),
(56, 2, 'update_restaurant', 'restaurant', 2, '更新餐廳：阿宗麵線', '127.0.0.1', '2026-09-23 21:04:34'),
(57, 2, 'update_restaurant', 'restaurant', 1, '更新餐廳：鼎泰豐 信義店', '127.0.0.1', '2026-09-23 21:04:56'),
(58, 2, 'update_accommodation', 'accommodation', 4, '更新住宿：美麗信花園酒店', '127.0.0.1', '2026-09-23 21:05:27'),
(59, 2, 'update_accommodation', 'accommodation', 3, '更新住宿：台北喜來登大飯店', '127.0.0.1', '2026-09-23 21:06:15'),
(60, 2, 'update_accommodation', 'accommodation', 2, '更新住宿：台北W飯店', '127.0.0.1', '2026-09-23 21:06:52'),
(61, 2, 'update_accommodation', 'accommodation', 1, '更新住宿：台北君悅酒店', '127.0.0.1', '2026-09-23 21:07:37');

-- --------------------------------------------------------

--
-- 資料表結構 `announcements`
--

CREATE TABLE `announcements` (
  `announcement_id` bigint(20) UNSIGNED NOT NULL,
  `created_by` bigint(20) UNSIGNED NOT NULL,
  `title` varchar(150) NOT NULL,
  `content` text NOT NULL,
  `is_pinned` tinyint(1) NOT NULL DEFAULT 0,
  `status` enum('draft','published','hidden') NOT NULL DEFAULT 'draft',
  `publish_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `announcements`
--

INSERT INTO `announcements` (`announcement_id`, `created_by`, `title`, `content`, `is_pinned`, `status`, `publish_at`, `created_at`, `updated_at`) VALUES
(1, 3, '歡迎使用 Travel Together', '歡迎使用多人協作旅遊行程規劃系統', 1, 'published', '2026-09-08 18:17:45', '2026-09-08 18:17:45', '2026-09-08 18:17:45');

-- --------------------------------------------------------

--
-- 資料表結構 `attachments`
--

CREATE TABLE `attachments` (
  `attachment_id` bigint(20) UNSIGNED NOT NULL,
  `uploaded_by` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED DEFAULT NULL,
  `itinerary_id` bigint(20) UNSIGNED DEFAULT NULL,
  `proposal_id` bigint(20) UNSIGNED DEFAULT NULL,
  `file_name` varchar(255) NOT NULL,
  `stored_name` varchar(255) NOT NULL,
  `file_path` varchar(500) NOT NULL,
  `file_type` varchar(100) NOT NULL,
  `file_size` bigint(20) UNSIGNED NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- 資料表結構 `attractions`
--

CREATE TABLE `attractions` (
  `attraction_id` bigint(20) UNSIGNED NOT NULL,
  `category_id` bigint(20) UNSIGNED DEFAULT NULL,
  `name` varchar(150) NOT NULL,
  `country_id` bigint(20) UNSIGNED NOT NULL,
  `city_id` bigint(20) UNSIGNED NOT NULL,
  `address` varchar(255) DEFAULT NULL,
  `latitude` decimal(10,7) DEFAULT NULL,
  `longitude` decimal(10,7) DEFAULT NULL,
  `opening_hours` varchar(255) DEFAULT NULL,
  `ticket_price` decimal(12,2) NOT NULL DEFAULT 0.00,
  `suggested_duration_minutes` int(10) UNSIGNED DEFAULT NULL,
  `description` text DEFAULT NULL,
  `website_url` varchar(500) DEFAULT NULL,
  `image_path` varchar(255) DEFAULT NULL,
  `is_popular` tinyint(1) NOT NULL DEFAULT 0,
  `status` enum('active','hidden','pending') NOT NULL DEFAULT 'active',
  `deleted_at` datetime DEFAULT NULL,
  `ai_verified_at` datetime DEFAULT NULL,
  `ai_verified_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `attractions`
--

INSERT INTO `attractions` (`attraction_id`, `category_id`, `name`, `country_id`, `city_id`, `address`, `latitude`, `longitude`, `opening_hours`, `ticket_price`, `suggested_duration_minutes`, `description`, `website_url`, `image_path`, `is_popular`, `status`, `deleted_at`, `ai_verified_at`, `ai_verified_by`, `created_by`, `created_at`, `updated_at`) VALUES
(2, 9, '國立故宮博物院', 1, 1, '111台灣臺北市士林區至善路二段221號', 25.1023554, 121.5484925, '星期一: 休息；星期二: 09:00 – 19:00；星期三: 09:00 – 19:00；星期四: 09:00 – 19:00；星期五: 09:00 – 19:00；星期六: 09:00 – 19:00；星期日: 09:00 – 19:00', 0.00, NULL, '人潮絡繹不絕的博物館，擁有世界上最龐大的中國藝術品和文物收藏。', 'https://www.npm.gov.tw/', 'images/故宮.jpg', 0, 'active', NULL, '2026-09-23 09:15:37', 2, 2, '2026-09-08 18:24:07', '2026-09-23 21:02:46'),
(3, 10, '士林夜市', 1, 1, '111台灣臺北市士林區義信里基河路101號', 25.0884972, 121.5243504, '星期一: 16:00 – 00:00；星期二: 16:00 – 00:00；星期三: 16:00 – 00:00；星期四: 16:00 – 00:00；星期五: 16:00 – 00:00；星期六: 16:00 – 00:00；星期日: 16:00 – 00:00', 0.00, NULL, '這座攤販雲集的傳統夜市售有街頭小吃、服飾和珠寶。', 'https://www.travel.taipei/zh-tw/attraction/details/1536', 'images/士林夜市.jpg', 0, 'active', NULL, '2026-09-23 09:15:36', 2, 2, '2026-09-08 18:24:07', '2026-09-23 21:02:27'),
(4, NULL, '西門町', 1, 1, '108台灣臺北市萬華區西門町', 25.0446664, 121.5063096, NULL, 0.00, NULL, '人聲鼎沸的街區，林立著全市最高檔的商店、酒吧和餐廳。', 'https://maps.google.com/?cid=14696636719173915895&g_mp=Cidnb29nbGUubWFwcy5wbGFjZXMudjEuUGxhY2VzLlNlYXJjaFRleHQQAhgEIAA', 'images/西門町.jpg', 0, 'active', NULL, '2026-09-17 11:00:09', 2, 2, '2026-09-08 18:24:09', '2026-09-23 21:02:04'),
(5, 11, '國立中正紀念堂', 1, 1, '100台灣臺北市中正區', 25.0355020, 121.5201832, '星期一: 09:00 – 18:00；星期二: 09:00 – 18:00；星期三: 09:00 – 18:00；星期四: 09:00 – 18:00；星期五: 09:00 – 18:00；星期六: 09:00 – 18:00；星期日: 09:00 – 18:00', 0.00, NULL, '著名的紀念堂，周圍是一個大型公園，園內有魚塘和花園。', 'https://www.cksmh.gov.tw/', 'images/中正紀念堂.jpg', 0, 'active', NULL, '2026-09-23 09:15:34', 2, 2, '2026-09-08 18:24:10', '2026-09-23 21:01:36'),
(10, NULL, '大稻埕碼頭貨櫃市集', 1, 1, '103台灣臺北市大同區永樂里民生西路底，五號水門', 25.0565135, 121.5075150, '星期一: 16:00 – 22:00；星期二: 16:00 – 22:00；星期三: 16:00 – 22:00；星期四: 16:00 – 22:00；星期五: 16:00 – 22:00；星期六: 12:00 – 22:00；星期日: 12:00 – 22:00', 0.00, NULL, '坐落碼頭的熱門夜生活景點，有水岸咖啡廳、小販，周末則有樂團演出和木偶秀。', 'https://www.mediasphere.com.tw/venues/1', 'images/大稻埕.jpg', 0, 'active', NULL, '2026-09-23 09:15:38', 2, 2, '2026-09-08 18:25:17', '2026-09-23 21:01:09'),
(11, NULL, '華山1914文化創意產業園區', 1, 1, '100台灣臺北市中正區梅花里八德路一段1號', 25.0440698, 121.5293583, '星期一: 11:00 – 21:00；星期二: 11:00 – 21:00；星期三: 11:00 – 21:00；星期四: 11:00 – 21:00；星期五: 11:00 – 21:00；星期六: 11:00 – 21:00；星期日: 11:00 – 21:00', 0.00, NULL, '這間藏身舊酒廠的文化樞紐有不少商家進駐，還有當地藝術、電影、工藝展覽與活動。', 'http://www.huashan1914.com/', 'images/華山.jpg', 0, 'active', NULL, '2026-09-23 09:15:38', 2, 2, '2026-09-08 18:25:17', '2026-09-23 21:00:32'),
(13, 3, '台北101', 1, 1, '台北市信義區信義路五段7號', NULL, NULL, NULL, 600.00, 120, '台北代表性地標與觀景台', NULL, 'images/台北101.jpg', 1, 'active', NULL, '2026-09-17 10:59:57', 2, 2, '2026-09-16 09:34:32', '2026-09-23 20:59:50');

-- --------------------------------------------------------

--
-- 資料表結構 `categories`
--

CREATE TABLE `categories` (
  `category_id` bigint(20) UNSIGNED NOT NULL,
  `category_type` enum('trip','attraction','restaurant','accommodation','expense') NOT NULL,
  `category_name` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `status` enum('active','hidden') NOT NULL DEFAULT 'active',
  `created_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `categories`
--

INSERT INTO `categories` (`category_id`, `category_type`, `category_name`, `description`, `status`, `created_by`, `created_at`, `updated_at`) VALUES
(1, 'trip', '自由行', '一般自由行程', 'active', 3, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(2, 'trip', '畢業旅行', '學生畢業旅行', 'active', 3, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(3, 'attraction', '景點', '一般觀光景點', 'active', 2, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(4, 'restaurant', '日式料理', '日本料理', 'active', 2, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(5, 'accommodation', '飯店', '一般旅館及飯店', 'active', 2, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(6, 'expense', '交通', '交通相關費用', 'active', 3, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(7, 'expense', '餐飲', '餐飲相關費用', 'active', 3, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(8, 'expense', '住宿', '住宿相關費用', 'active', 3, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(9, 'attraction', '歷史博物館', NULL, 'active', NULL, '2026-09-08 18:24:07', '2026-09-08 18:24:07'),
(10, 'attraction', '市場', NULL, 'active', NULL, '2026-09-08 18:24:07', '2026-09-08 18:24:07'),
(11, 'attraction', '文化地標', NULL, 'active', NULL, '2026-09-08 18:24:10', '2026-09-08 18:24:10'),
(12, 'restaurant', '外賣餐廳', NULL, 'active', NULL, '2026-09-08 18:24:11', '2026-09-08 18:24:11'),
(13, 'restaurant', '麵店', NULL, 'active', NULL, '2026-09-08 18:24:12', '2026-09-08 18:24:12'),
(14, 'restaurant', '台式餐廳', NULL, 'active', NULL, '2026-09-08 18:24:13', '2026-09-08 18:24:13'),
(15, 'accommodation', '度假酒店', NULL, 'active', NULL, '2026-09-08 18:24:14', '2026-09-08 18:24:14');

-- --------------------------------------------------------

--
-- 資料表結構 `cities`
--

CREATE TABLE `cities` (
  `city_id` bigint(20) UNSIGNED NOT NULL,
  `country_id` bigint(20) UNSIGNED NOT NULL,
  `name` varchar(100) NOT NULL,
  `region` varchar(50) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `cities`
--

INSERT INTO `cities` (`city_id`, `country_id`, `name`, `region`, `created_at`, `updated_at`) VALUES
(1, 1, '台北市', '北部', '2026-09-08 18:17:45', '2026-09-17 11:07:57'),
(2, 1, '高雄市', '南部', '2026-09-08 18:17:45', '2026-09-17 11:07:57'),
(3, 2, '東京都', '關東', '2026-09-08 18:17:45', '2026-09-17 11:07:57'),
(4, 5, '新加坡', NULL, '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(5, 2, '大阪市', NULL, '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(6, 4, '曼谷', NULL, '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(7, 3, '首爾特別市', NULL, '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(8, 6, '香港', NULL, '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(77, 1, '新北市', '北部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(78, 1, '桃園市', '北部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(79, 1, '台中市', '中部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(80, 1, '台南市', '南部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(81, 1, '基隆市', '北部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(82, 1, '新竹市', '北部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(83, 1, '嘉義市', '南部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(84, 1, '新竹縣', '北部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(85, 1, '苗栗縣', '中部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(86, 1, '彰化縣', '中部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(87, 1, '南投縣', '中部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(88, 1, '雲林縣', '中部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(89, 1, '嘉義縣', '南部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(90, 1, '屏東縣', '南部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(91, 1, '宜蘭縣', '北部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(92, 1, '花蓮縣', '東部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(93, 1, '台東縣', '東部', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(94, 1, '澎湖縣', '離島', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(95, 1, '金門縣', '離島', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(96, 1, '連江縣', '離島', '2026-09-17 10:10:56', '2026-09-17 11:07:57'),
(97, 2, '北海道', '北海道', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(98, 2, '青森縣', '東北地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(99, 2, '岩手縣', '東北地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(100, 2, '宮城縣', '東北地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(101, 2, '秋田縣', '東北地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(102, 2, '山形縣', '東北地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(103, 2, '福島縣', '東北地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(104, 2, '茨城縣', '關東', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(105, 2, '栃木縣', '關東', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(106, 2, '群馬縣', '關東', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(107, 2, '埼玉縣', '關東', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(108, 2, '千葉縣', '關東', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(109, 2, '神奈川縣', '關東', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(110, 2, '新潟縣', '中部地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(111, 2, '富山縣', '中部地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(112, 2, '石川縣', '中部地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(113, 2, '福井縣', '中部地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(114, 2, '山梨縣', '中部地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(115, 2, '長野縣', '中部地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(116, 2, '岐阜縣', '中部地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(117, 2, '靜岡縣', '中部地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(118, 2, '愛知縣', '中部地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(119, 2, '三重縣', '關西', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(120, 2, '滋賀縣', '關西', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(121, 2, '京都府', '關西', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(122, 2, '大阪府', '關西', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(123, 2, '兵庫縣', '關西', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(124, 2, '奈良縣', '關西', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(125, 2, '和歌山縣', '關西', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(126, 2, '鳥取縣', '中國地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(127, 2, '島根縣', '中國地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(128, 2, '岡山縣', '中國地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(129, 2, '廣島縣', '中國地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(130, 2, '山口縣', '中國地方', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(131, 2, '德島縣', '四國', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(132, 2, '香川縣', '四國', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(133, 2, '愛媛縣', '四國', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(134, 2, '高知縣', '四國', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(135, 2, '福岡縣', '九州', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(136, 2, '佐賀縣', '九州', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(137, 2, '長崎縣', '九州', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(138, 2, '熊本縣', '九州', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(139, 2, '大分縣', '九州', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(140, 2, '宮崎縣', '九州', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(141, 2, '鹿兒島縣', '九州', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(142, 2, '沖繩縣', '九州', '2026-09-17 10:10:59', '2026-09-17 11:07:57'),
(234, 3, '全南光州統合特別市', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(235, 3, '世宗特別自治市', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(236, 3, '釜山廣域市', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(237, 3, '大邱廣域市', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(238, 3, '仁川廣域市', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(239, 3, '大田廣域市', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(240, 3, '蔚山廣域市', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(241, 3, '京畿道', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(242, 3, '江原特別自治道', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(243, 3, '忠清北道', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(244, 3, '忠清南道', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(245, 3, '全北特別自治道', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(246, 3, '慶尚北道', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(247, 3, '慶尚南道', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(248, 3, '濟州特別自治道', NULL, '2026-09-17 10:23:15', '2026-09-17 10:23:15'),
(249, 4, '安納乍倫府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(250, 4, '紅統府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(251, 4, '汶干府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(252, 4, '武里南府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(253, 4, '差春騷府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(254, 4, '猜納府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(255, 4, '猜也蓬府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(256, 4, '莊他武里府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(257, 4, '清邁府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(258, 4, '清萊府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(259, 4, '春武里府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(260, 4, '春蓬府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(261, 4, '加拉信府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(262, 4, '甘烹碧府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(263, 4, '北碧府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(264, 4, '孔敬府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(265, 4, '甲米府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(266, 4, '南邦府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(267, 4, '南奔府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(268, 4, '黎府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(269, 4, '華富里府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(270, 4, '夜豐頌府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(271, 4, '馬哈沙拉堪府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(272, 4, '穆達漢府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(273, 4, '那空那育府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(274, 4, '佛統府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(275, 4, '那空拍儂府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(276, 4, '那空叻差是瑪府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(277, 4, '那空沙旺府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(278, 4, '那空是貪瑪叻府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(279, 4, '難府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(280, 4, '那拉提瓦府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(281, 4, '農磨蘭普府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(282, 4, '廊開府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(283, 4, '暖武里府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(284, 4, '巴吞他尼府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(285, 4, '北大年府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(286, 4, '攀牙府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(287, 4, '博他侖府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(288, 4, '帕堯府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(289, 4, '碧差汶府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(290, 4, '碧武里府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(291, 4, '披集府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(292, 4, '彭世洛府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(293, 4, '大城府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(294, 4, '帕府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(295, 4, '普吉府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(296, 4, '巴真府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(297, 4, '巴蜀府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(298, 4, '拉廊府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(299, 4, '叻武里府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(300, 4, '羅勇府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(301, 4, '黎逸府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(302, 4, '沙繳府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(303, 4, '沙功那空府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(304, 4, '沙沒巴干府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(305, 4, '沙沒沙空府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(306, 4, '沙沒頌堪府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(307, 4, '沙拉武里府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(308, 4, '沙敦府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(309, 4, '信武里府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(310, 4, '四色菊府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(311, 4, '宋卡府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(312, 4, '素可泰府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(313, 4, '素攀府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(314, 4, '素叻他尼府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(315, 4, '素林府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(316, 4, '達府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(317, 4, '董里府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(318, 4, '達叻府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(319, 4, '烏汶府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(320, 4, '烏隆府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(321, 4, '烏泰他尼府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(322, 4, '程逸府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(323, 4, '也拉府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(324, 4, '益梭通府', NULL, '2026-09-17 10:23:17', '2026-09-17 10:23:17'),
(343, 6, '中西區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(344, 6, '九龍城區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(345, 6, '元朗區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(346, 6, '北區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(347, 6, '南區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(348, 6, '大埔區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(349, 6, '屯門區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(350, 6, '東區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(351, 6, '沙田區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(352, 6, '油尖旺區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(353, 6, '深水埗區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(354, 6, '灣仔區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(355, 6, '荃灣區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(356, 6, '葵青區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(357, 6, '西貢區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(358, 6, '觀塘區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(359, 6, '離島區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(360, 6, '黃大仙區', NULL, '2026-09-17 10:54:53', '2026-09-17 10:54:53'),
(361, 9, '乂安省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(362, 9, '北寧省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(363, 9, '同塔省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(364, 9, '同奈市', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(365, 9, '嘉萊省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(366, 9, '多乐省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(367, 9, '太原省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(368, 9, '奠邊省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(369, 9, '安江省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(370, 9, '宣光省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(371, 9, '富壽省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(372, 9, '寧平省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(373, 9, '山羅省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(374, 9, '峴港市', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(375, 9, '廣寧市', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(376, 9, '廣治省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(377, 9, '廣義省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(378, 9, '慶和省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(379, 9, '林同省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(380, 9, '永隆省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(381, 9, '河內', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(382, 9, '河靜省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(383, 9, '海防市', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(384, 9, '清化省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(385, 9, '老街省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(386, 9, '胡志明市', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(387, 9, '興安省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(388, 9, '芹苴市', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(389, 9, '萊州省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(390, 9, '西寧省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(391, 9, '諒山省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(392, 9, '金甌省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(393, 9, '順化市', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30'),
(394, 9, '高平省', NULL, '2026-09-17 10:55:30', '2026-09-17 10:55:30');

-- --------------------------------------------------------

--
-- 資料表結構 `comments`
--

CREATE TABLE `comments` (
  `comment_id` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `itinerary_id` bigint(20) UNSIGNED DEFAULT NULL,
  `proposal_id` bigint(20) UNSIGNED DEFAULT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `parent_comment_id` bigint(20) UNSIGNED DEFAULT NULL,
  `content` text NOT NULL,
  `status` enum('visible','hidden','deleted') NOT NULL DEFAULT 'visible',
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- 資料表結構 `countries`
--

CREATE TABLE `countries` (
  `country_id` bigint(20) UNSIGNED NOT NULL,
  `name` varchar(100) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `countries`
--

INSERT INTO `countries` (`country_id`, `name`, `created_at`, `updated_at`) VALUES
(1, '台灣', '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(2, '日本', '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(3, '韓國', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(4, '泰國', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(5, '新加坡', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(6, '香港', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(9, '越南', '2026-09-17 10:55:10', '2026-09-17 10:55:10');

-- --------------------------------------------------------

--
-- 資料表結構 `edit_logs`
--

CREATE TABLE `edit_logs` (
  `edit_log_id` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `target_table` varchar(100) NOT NULL,
  `target_id` bigint(20) UNSIGNED NOT NULL,
  `action` enum('create','update','delete','restore') NOT NULL,
  `before_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`before_data`)),
  `after_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`after_data`)),
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- 資料表結構 `expenses`
--

CREATE TABLE `expenses` (
  `expense_id` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `category_id` bigint(20) UNSIGNED DEFAULT NULL,
  `created_by` bigint(20) UNSIGNED NOT NULL,
  `payer_id` bigint(20) UNSIGNED NOT NULL,
  `expense_name` varchar(150) NOT NULL,
  `expense_type` enum('estimated','actual') NOT NULL DEFAULT 'actual',
  `scope` enum('shared','personal') NOT NULL DEFAULT 'shared',
  `amount` decimal(14,2) NOT NULL,
  `currency` char(3) NOT NULL DEFAULT 'TWD',
  `expense_date` date NOT NULL,
  `note` text DEFAULT NULL,
  `receipt_path` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ;

-- --------------------------------------------------------

--
-- 資料表結構 `expense_splits`
--

CREATE TABLE `expense_splits` (
  `split_id` bigint(20) UNSIGNED NOT NULL,
  `expense_id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `split_amount` decimal(14,2) NOT NULL,
  `settlement_status` enum('unpaid','paid','waived') NOT NULL DEFAULT 'unpaid',
  `paid_at` datetime DEFAULT NULL
) ;

-- --------------------------------------------------------

--
-- 資料表結構 `favorites`
--

CREATE TABLE `favorites` (
  `favorite_id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `target_type` enum('trip','attraction') NOT NULL,
  `trip_id` bigint(20) UNSIGNED DEFAULT NULL,
  `attraction_id` bigint(20) UNSIGNED DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- 資料表結構 `flights`
--

CREATE TABLE `flights` (
  `flight_id` bigint(20) UNSIGNED NOT NULL,
  `airline_name` varchar(100) NOT NULL,
  `flight_number` varchar(20) NOT NULL,
  `origin_country_id` bigint(20) UNSIGNED NOT NULL,
  `origin_city_id` bigint(20) UNSIGNED NOT NULL,
  `destination_country_id` bigint(20) UNSIGNED NOT NULL,
  `destination_city_id` bigint(20) UNSIGNED NOT NULL,
  `departure_time` time NOT NULL,
  `arrival_time` time NOT NULL,
  `duration_minutes` int(11) NOT NULL,
  `price` decimal(10,2) NOT NULL DEFAULT 0.00,
  `cabin_class` varchar(50) NOT NULL DEFAULT '經濟艙',
  `seats_available` int(11) NOT NULL DEFAULT 9,
  `status` enum('active','hidden') NOT NULL DEFAULT 'active',
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `flights`
--

INSERT INTO `flights` (`flight_id`, `airline_name`, `flight_number`, `origin_country_id`, `origin_city_id`, `destination_country_id`, `destination_city_id`, `departure_time`, `arrival_time`, `duration_minutes`, `price`, `cabin_class`, `seats_available`, `status`, `created_at`, `updated_at`) VALUES
(1, '中華航空', 'CI161', 2, 5, 1, 1, '20:00:00', '22:35:00', 215, 8300.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(2, '星宇航空', 'JX821', 2, 5, 1, 1, '15:00:00', '17:35:00', 215, 7800.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(3, '日本航空', 'JL810', 2, 3, 1, 1, '19:30:00', '23:15:00', 225, 10500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(4, '長榮航空', 'BR199', 2, 3, 1, 1, '14:00:00', '17:45:00', 225, 9200.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(5, '中華航空', 'CI101', 2, 3, 1, 1, '09:00:00', '12:45:00', 225, 8500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(6, '大韓航空', 'KE186', 3, 7, 1, 1, '20:00:00', '22:35:00', 155, 10200.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(7, '長榮航空', 'BR170', 3, 7, 1, 1, '13:00:00', '15:35:00', 155, 9800.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(8, '泰國航空', 'TG636', 4, 6, 1, 1, '19:00:00', '23:35:00', 275, 12000.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(9, '中華航空', 'CI836', 4, 6, 1, 1, '09:00:00', '13:35:00', 275, 11500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(10, '新加坡航空', 'SQ880', 5, 4, 1, 1, '15:00:00', '19:50:00', 290, 14200.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(11, '長榮航空', 'BR226', 5, 4, 1, 1, '08:00:00', '12:50:00', 290, 13500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(12, '中華航空', 'CI606', 6, 8, 1, 1, '21:00:00', '22:45:00', 105, 6500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(13, '國泰航空', 'CX452', 6, 8, 1, 1, '10:30:00', '12:15:00', 105, 6200.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(14, '中華航空', 'CI160', 1, 1, 2, 5, '14:20:00', '18:05:00', 225, 8300.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(15, '星宇航空', 'JX820', 1, 1, 2, 5, '09:15:00', '13:00:00', 225, 7800.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(16, '日本航空', 'JL809', 1, 1, 2, 3, '19:00:00', '23:05:00', 245, 10500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(17, '長榮航空', 'BR198', 1, 1, 2, 3, '13:30:00', '17:35:00', 245, 9200.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(18, '中華航空', 'CI100', 1, 1, 2, 3, '08:00:00', '12:10:00', 250, 8500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(19, '大韓航空', 'KE185', 1, 1, 3, 7, '15:10:00', '18:35:00', 205, 10200.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(20, '長榮航空', 'BR169', 1, 1, 3, 7, '07:50:00', '11:15:00', 205, 9800.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(21, '泰國航空', 'TG635', 1, 1, 4, 6, '21:00:00', '23:45:00', 225, 12000.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(22, '中華航空', 'CI835', 1, 1, 4, 6, '08:30:00', '11:15:00', 225, 11500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(23, '新加坡航空', 'SQ879', 1, 1, 5, 4, '17:15:00', '21:30:00', 255, 14200.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(24, '長榮航空', 'BR225', 1, 1, 5, 4, '09:40:00', '13:55:00', 255, 13500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(25, '中華航空', 'CI605', 1, 1, 6, 8, '18:20:00', '20:05:00', 105, 6500.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36'),
(26, '國泰航空', 'CX451', 1, 1, 6, 8, '08:00:00', '09:45:00', 105, 6200.00, '經濟艙', 9, 'active', '2026-09-17 09:53:36', '2026-09-17 09:53:36');

-- --------------------------------------------------------

--
-- 資料表結構 `itineraries`
--

CREATE TABLE `itineraries` (
  `itinerary_id` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `created_by` bigint(20) UNSIGNED NOT NULL,
  `itinerary_date` date NOT NULL,
  `item_type` enum('attraction','restaurant','accommodation','transport','shopping','meeting','free_time','other') NOT NULL,
  `title` varchar(150) NOT NULL,
  `start_time` time DEFAULT NULL,
  `end_time` time DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `transport_method` varchar(100) DEFAULT NULL,
  `transport_minutes` int(10) UNSIGNED DEFAULT 0,
  `estimated_cost` decimal(12,2) NOT NULL DEFAULT 0.00,
  `notes` text DEFAULT NULL,
  `attraction_id` bigint(20) UNSIGNED DEFAULT NULL,
  `restaurant_id` bigint(20) UNSIGNED DEFAULT NULL,
  `accommodation_id` bigint(20) UNSIGNED DEFAULT NULL,
  `sort_order` int(10) UNSIGNED NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ;

--
-- 傾印資料表的資料 `itineraries`
--

INSERT INTO `itineraries` (`itinerary_id`, `trip_id`, `created_by`, `itinerary_date`, `item_type`, `title`, `start_time`, `end_time`, `address`, `transport_method`, `transport_minutes`, `estimated_cost`, `notes`, `attraction_id`, `restaurant_id`, `accommodation_id`, `sort_order`, `created_at`, `updated_at`) VALUES
(1, 1, 1, '2026-08-10', 'attraction', '參觀台北101', '10:00:00', '12:00:00', '台北市信義區信義路五段7號', NULL, 0, 600.00, NULL, NULL, NULL, NULL, 1, '2026-09-08 18:17:45', '2026-09-08 18:17:45');

-- --------------------------------------------------------

--
-- 資料表結構 `notifications`
--

CREATE TABLE `notifications` (
  `notification_id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED DEFAULT NULL,
  `notification_type` enum('invitation','trip_edit','comment','vote','permission','departure','system') NOT NULL,
  `title` varchar(150) NOT NULL,
  `message` text NOT NULL,
  `target_url` varchar(500) DEFAULT NULL,
  `is_read` tinyint(1) NOT NULL DEFAULT 0,
  `read_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `notifications`
--

INSERT INTO `notifications` (`notification_id`, `user_id`, `trip_id`, `notification_type`, `title`, `message`, `target_url`, `is_read`, `read_at`, `created_at`) VALUES
(2, 1, 1, 'system', '你的公開行程被舉報', '你的公開行程「台北三天兩夜」收到舉報。原因：不當或違規內容；補充說明：123', '/member/trips/1', 0, NULL, '2026-09-15 09:26:05');

-- --------------------------------------------------------

--
-- 資料表結構 `proposals`
--

CREATE TABLE `proposals` (
  `proposal_id` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `proposer_id` bigint(20) UNSIGNED NOT NULL,
  `proposal_type` enum('attraction','restaurant','accommodation','activity','transport','date','other') NOT NULL,
  `title` varchar(150) NOT NULL,
  `location` varchar(255) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `estimated_cost` decimal(12,2) NOT NULL DEFAULT 0.00,
  `proposed_date` date DEFAULT NULL,
  `website_url` varchar(500) DEFAULT NULL,
  `image_path` varchar(255) DEFAULT NULL,
  `status` enum('discussing','voting','approved','rejected','added') NOT NULL DEFAULT 'discussing',
  `content_review_status` enum('not_required','pending','approved','returned') NOT NULL DEFAULT 'not_required',
  `reviewed_by` bigint(20) UNSIGNED DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `review_note` varchar(500) DEFAULT NULL,
  `deadline_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ;

--
-- 傾印資料表的資料 `proposals`
--

INSERT INTO `proposals` (`proposal_id`, `trip_id`, `proposer_id`, `proposal_type`, `title`, `location`, `description`, `estimated_cost`, `proposed_date`, `website_url`, `image_path`, `status`, `content_review_status`, `reviewed_by`, `reviewed_at`, `review_note`, `deadline_at`, `created_at`, `updated_at`) VALUES
(1, 1, 1, 'attraction', '貓空纜車', '台北市文山區', '會員提議加入貓空纜車景點，可俯瞰台北市景', 300.00, '2026-08-11', NULL, NULL, 'discussing', 'approved', 2, '2026-09-10 10:11:13', NULL, NULL, '2026-09-08 18:17:45', '2026-09-10 10:11:13'),
(2, 3, 5, 'attraction', '要去嘛', NULL, NULL, 0.00, NULL, NULL, NULL, 'discussing', 'not_required', NULL, NULL, NULL, NULL, '2026-09-10 10:34:24', '2026-09-10 10:34:24');

-- --------------------------------------------------------

--
-- 資料表結構 `reports`
--

CREATE TABLE `reports` (
  `report_id` bigint(20) UNSIGNED NOT NULL,
  `reporter_id` bigint(20) UNSIGNED NOT NULL,
  `target_type` enum('trip','comment','proposal','user','other') NOT NULL,
  `target_id` bigint(20) UNSIGNED NOT NULL,
  `reason` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `status` enum('pending','processing','resolved','rejected') NOT NULL DEFAULT 'pending',
  `handled_by` bigint(20) UNSIGNED DEFAULT NULL,
  `handling_result` text DEFAULT NULL,
  `handled_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `reports`
--

INSERT INTO `reports` (`report_id`, `reporter_id`, `target_type`, `target_id`, `reason`, `description`, `status`, `handled_by`, `handling_result`, `handled_at`, `created_at`) VALUES
(1, 5, 'trip', 1, '不當或違規內容', '123', 'pending', NULL, NULL, NULL, '2026-09-15 09:26:05'),
(2, 5, 'trip', 1, '問題回報：其它', '看不到行程ㄚㄚㄚㄚ', 'pending', NULL, NULL, NULL, '2026-09-23 20:46:11');

-- --------------------------------------------------------

--
-- 資料表結構 `restaurants`
--

CREATE TABLE `restaurants` (
  `restaurant_id` bigint(20) UNSIGNED NOT NULL,
  `category_id` bigint(20) UNSIGNED DEFAULT NULL,
  `name` varchar(150) NOT NULL,
  `country_id` bigint(20) UNSIGNED NOT NULL,
  `city_id` bigint(20) UNSIGNED NOT NULL,
  `address` varchar(255) DEFAULT NULL,
  `cuisine_type` varchar(100) DEFAULT NULL,
  `price_level` enum('low','medium','high','luxury') DEFAULT 'medium',
  `opening_hours` varchar(255) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `website_url` varchar(500) DEFAULT NULL,
  `image_path` varchar(255) DEFAULT NULL,
  `status` enum('active','hidden','pending') NOT NULL DEFAULT 'active',
  `deleted_at` datetime DEFAULT NULL,
  `ai_verified_at` datetime DEFAULT NULL,
  `ai_verified_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `restaurants`
--

INSERT INTO `restaurants` (`restaurant_id`, `category_id`, `name`, `country_id`, `city_id`, `address`, `cuisine_type`, `price_level`, `opening_hours`, `description`, `website_url`, `image_path`, `status`, `deleted_at`, `ai_verified_at`, `ai_verified_by`, `created_by`, `created_at`, `updated_at`) VALUES
(1, 12, '鼎泰豐 信義店', 1, 1, '106台灣臺北市大安區福住里信義路二段194號', '外賣餐廳', 'medium', '星期一: 11:00 – 20:30；星期二: 11:00 – 20:30；星期三: 11:00 – 20:30；星期四: 11:00 – 20:30；星期五: 11:00 – 20:30；星期六: 10:30 – 20:30；星期日: 10:30 – 20:30', '外賣餐廳，位於台灣臺北市，是當地值得一遊的景點。', 'https://www.dintaifung.com.tw/', 'images/鼎泰豐.jpg', 'active', NULL, NULL, NULL, 2, '2026-09-08 18:24:11', '2026-09-23 21:04:56'),
(2, 13, '阿宗麵線', 1, 1, '108台灣臺北市萬華區西門里峨眉街8-1號', '麵店', 'low', '星期一: 07:30 – 22:30；星期二: 07:30 – 22:30；星期三: 07:30 – 22:30；星期四: 07:30 – 22:30；星期五: 07:30 – 23:00；星期六: 07:30 – 23:00；星期日: 07:30 – 22:30', '如果到台灣臺北市旅遊，不妨把麵店阿宗麵線排進行程裡。', 'https://aychungflourricenoodle.shop/', 'images/阿宗.jpg', 'active', NULL, NULL, NULL, 2, '2026-09-08 18:24:12', '2026-09-23 21:04:34'),
(3, 13, '度小月擔仔麵 台北忠孝店', 1, 1, '106台灣臺北市大安區建倫里忠孝東路四段216巷8弄12號', '麵店', 'medium', '星期一: 11:00 – 15:00, 16:30 – 21:00；星期二: 11:00 – 15:00, 16:30 – 21:00；星期三: 11:00 – 15:00, 16:30 – 21:00；星期四: 11:00 – 15:00, 16:30 – 21:00；星期五: 11:00 – 15:00, 16:30 – 21:00；星期六: 11:00 – 15:00, 16:30 – 21:00；星期日: 11:00 – 15:00, 16:30 – 21:00', '來台灣臺北市旅遊，別錯過度小月擔仔麵 台北忠孝店，這裡是熱門的麵店。', 'http://www.noodle1895.com/', 'images/度小月.jpg', 'active', NULL, NULL, NULL, 2, '2026-09-08 18:24:12', '2026-09-23 21:04:10'),
(4, 14, '春水堂 南港店', 1, 1, '115台灣臺北市南港區三重里經貿二路188號2樓（B棟', '台式餐廳', 'medium', '星期一: 11:00 – 21:30；星期二: 11:00 – 21:30；星期三: 11:00 – 21:30；星期四: 11:00 – 21:30；星期五: 11:00 – 21:30；星期六: 11:00 – 21:30；星期日: 11:00 – 21:30', '如果到台灣臺北市旅遊，不妨把台式餐廳春水堂 南港店排進行程裡。', 'http://chunshuitang.com.tw/', 'images/春水堂.png', 'active', NULL, '2026-09-23 20:57:45', NULL, 2, '2026-09-08 18:24:13', '2026-09-23 21:03:42'),
(5, 14, '欣葉台菜創始店', 1, 1, '10491台灣臺北市中山區晴光里雙城街34之1號', '台式餐廳', 'medium', '星期一: 11:00 – 21:30；星期二: 11:00 – 21:30；星期三: 11:00 – 21:30；星期四: 11:00 – 21:30；星期五: 11:00 – 21:30；星期六: 11:00 – 21:30；星期日: 11:00 – 21:30', '欣葉台菜創始店座落於台灣臺北市，以台式餐廳聞名，值得安排時間造訪。', 'https://www.shinyeh.com.tw/content/zh/brand/Index.aspx?BrandId=1', 'images/新頁.jpg', 'active', NULL, NULL, NULL, 2, '2026-09-08 18:24:14', '2026-09-23 21:03:16');

-- --------------------------------------------------------

--
-- 資料表結構 `trains`
--

CREATE TABLE `trains` (
  `train_id` bigint(20) UNSIGNED NOT NULL,
  `train_type` enum('thsr','tra') NOT NULL COMMENT 'thsr=台灣高鐵, tra=台鐵',
  `train_number` varchar(20) NOT NULL,
  `car_class` varchar(50) NOT NULL COMMENT '高鐵:標準車廂/商務車廂；台鐵:自強號/普悠瑪/太魯閣號等',
  `origin_station` varchar(50) NOT NULL,
  `destination_station` varchar(50) NOT NULL,
  `departure_time` time NOT NULL,
  `arrival_time` time NOT NULL,
  `duration_minutes` int(11) NOT NULL,
  `price` decimal(10,2) NOT NULL DEFAULT 0.00,
  `seats_available` int(11) NOT NULL DEFAULT 20,
  `status` enum('active','hidden') NOT NULL DEFAULT 'active',
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `trains`
--

INSERT INTO `trains` (`train_id`, `train_type`, `train_number`, `car_class`, `origin_station`, `destination_station`, `departure_time`, `arrival_time`, `duration_minutes`, `price`, `seats_available`, `status`, `created_at`, `updated_at`) VALUES
(1, 'thsr', '121', '標準車廂', '台北', '板橋', '07:00:00', '07:08:00', 8, 45.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(2, 'thsr', '124', '標準車廂', '板橋', '台北', '19:20:00', '19:28:00', 8, 45.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(3, 'thsr', '133', '標準車廂', '台北', '桃園', '08:00:00', '08:20:00', 20, 160.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(4, 'thsr', '138', '標準車廂', '桃園', '台北', '18:10:00', '18:30:00', 20, 160.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(5, 'thsr', '141', '標準車廂', '台北', '新竹', '07:30:00', '08:00:00', 30, 290.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(6, 'thsr', '148', '標準車廂', '新竹', '台北', '18:40:00', '19:10:00', 30, 290.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(7, 'thsr', '105', '標準車廂', '台北', '台中', '06:30:00', '07:17:00', 47, 700.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(8, 'thsr', '157', '標準車廂', '台北', '台中', '09:30:00', '10:17:00', 47, 700.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(9, 'thsr', '181', '標準車廂', '台北', '台中', '17:30:00', '18:17:00', 47, 700.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(10, 'thsr', '108', '標準車廂', '台中', '台北', '08:00:00', '08:47:00', 47, 700.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(11, 'thsr', '172', '標準車廂', '台中', '台北', '16:30:00', '17:17:00', 47, 700.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(12, 'thsr', '190', '標準車廂', '台中', '台北', '20:30:00', '21:17:00', 47, 700.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(13, 'thsr', '411', '標準車廂', '台北', '嘉義', '08:30:00', '09:47:00', 77, 1080.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(14, 'thsr', '425', '標準車廂', '台北', '嘉義', '16:00:00', '17:17:00', 77, 1080.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(15, 'thsr', '420', '標準車廂', '嘉義', '台北', '09:20:00', '10:37:00', 77, 1080.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(16, 'thsr', '436', '標準車廂', '嘉義', '台北', '18:20:00', '19:37:00', 77, 1080.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(17, 'thsr', '605', '標準車廂', '台北', '台南', '07:00:00', '08:30:00', 90, 1350.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(18, 'thsr', '625', '標準車廂', '台北', '台南', '15:00:00', '16:30:00', 90, 1350.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(19, 'thsr', '610', '標準車廂', '台南', '台北', '08:00:00', '09:30:00', 90, 1350.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(20, 'thsr', '648', '標準車廂', '台南', '台北', '19:00:00', '20:30:00', 90, 1350.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(21, 'thsr', '203', '標準車廂', '台北', '左營', '06:30:00', '08:06:00', 96, 1490.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(22, 'thsr', '221', '標準車廂', '台北', '左營', '09:00:00', '10:36:00', 96, 1490.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(23, 'thsr', '251', '標準車廂', '台北', '左營', '17:00:00', '18:36:00', 96, 1490.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(24, 'thsr', '208', '標準車廂', '左營', '台北', '07:30:00', '09:06:00', 96, 1490.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(25, 'thsr', '270', '標準車廂', '左營', '台北', '18:00:00', '19:36:00', 96, 1490.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(26, 'thsr', '292', '標準車廂', '左營', '台北', '20:30:00', '22:06:00', 96, 1490.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(27, 'thsr', '303', '標準車廂', '台中', '左營', '08:20:00', '09:12:00', 52, 930.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(28, 'thsr', '318', '標準車廂', '左營', '台中', '17:40:00', '18:32:00', 52, 930.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(29, 'thsr', '145', '標準車廂', '新竹', '台中', '10:10:00', '10:40:00', 30, 490.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(30, 'thsr', '160', '標準車廂', '台中', '新竹', '16:20:00', '16:50:00', 30, 490.00, 200, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(31, 'tra', '152', '自強號', '台北', '台中', '07:10:00', '08:57:00', 107, 375.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(32, 'tra', '168', '自強號', '台北', '台中', '14:20:00', '16:07:00', 107, 375.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(33, 'tra', '155', '自強號', '台中', '台北', '09:30:00', '11:17:00', 107, 375.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(34, 'tra', '173', '自強號', '台中', '台北', '18:00:00', '19:47:00', 107, 375.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(35, 'tra', '1132', '自強號', '台北', '台南', '07:30:00', '10:50:00', 200, 738.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(36, 'tra', '1138', '自強號', '台北', '台南', '13:30:00', '16:50:00', 200, 738.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(37, 'tra', '1135', '自強號', '台南', '台北', '09:00:00', '12:20:00', 200, 738.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(38, 'tra', '1149', '自強號', '台南', '台北', '17:00:00', '20:20:00', 200, 738.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(39, 'tra', '104', '自強號', '台北', '高雄', '06:20:00', '10:35:00', 255, 843.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(40, 'tra', '110', '自強號', '台北', '高雄', '12:20:00', '16:35:00', 255, 843.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(41, 'tra', '105', '自強號', '高雄', '台北', '07:10:00', '11:25:00', 255, 843.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(42, 'tra', '121', '自強號', '高雄', '台北', '15:10:00', '19:25:00', 255, 843.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(43, 'tra', '401', '普悠瑪', '台北', '花蓮', '08:30:00', '10:35:00', 125, 440.00, 40, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(44, 'tra', '407', '太魯閣', '台北', '花蓮', '15:30:00', '17:35:00', 125, 440.00, 40, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(45, 'tra', '408', '普悠瑪', '花蓮', '台北', '09:00:00', '11:05:00', 125, 440.00, 40, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(46, 'tra', '414', '太魯閣', '花蓮', '台北', '18:00:00', '20:05:00', 125, 440.00, 40, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(47, 'tra', '421', '普悠瑪', '台北', '台東', '07:20:00', '11:00:00', 220, 783.00, 40, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(48, 'tra', '425', '普悠瑪', '台北', '台東', '13:20:00', '17:00:00', 220, 783.00, 40, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(49, 'tra', '422', '普悠瑪', '台東', '台北', '08:10:00', '11:50:00', 220, 783.00, 40, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(50, 'tra', '436', '普悠瑪', '台東', '台北', '16:10:00', '19:50:00', 220, 783.00, 40, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(51, 'tra', '218', '自強號', '台中', '高雄', '09:20:00', '11:50:00', 150, 470.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09'),
(52, 'tra', '234', '自強號', '高雄', '台中', '17:10:00', '19:40:00', 150, 470.00, 60, 'active', '2026-09-17 09:53:09', '2026-09-17 09:53:09');

-- --------------------------------------------------------

--
-- 資料表結構 `trips`
--

CREATE TABLE `trips` (
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `owner_id` bigint(20) UNSIGNED NOT NULL,
  `category_id` bigint(20) UNSIGNED DEFAULT NULL,
  `trip_name` varchar(150) NOT NULL,
  `cover_image_path` varchar(255) DEFAULT NULL,
  `country_id` bigint(20) UNSIGNED NOT NULL,
  `city_id` bigint(20) UNSIGNED NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `people_count` int(10) UNSIGNED NOT NULL DEFAULT 1,
  `total_budget` decimal(14,2) NOT NULL DEFAULT 0.00,
  `currency` char(3) NOT NULL DEFAULT 'TWD',
  `introduction` text DEFAULT NULL,
  `visibility` enum('private','public','link_only') NOT NULL DEFAULT 'private',
  `status` enum('planning','upcoming','completed','cancelled') NOT NULL DEFAULT 'planning',
  `share_token` varchar(100) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ;

--
-- 傾印資料表的資料 `trips`
--

INSERT INTO `trips` (`trip_id`, `owner_id`, `category_id`, `trip_name`, `cover_image_path`, `country_id`, `city_id`, `start_date`, `end_date`, `people_count`, `total_budget`, `currency`, `introduction`, `visibility`, `status`, `share_token`, `created_at`, `updated_at`) VALUES
(1, 1, 1, '台北三天兩夜', NULL, 1, 1, '2026-08-10', '2026-08-12', 3, 15000.00, 'TWD', '測試用多人協作旅遊行程', 'public', 'planning', 'demo-taipei-2026', '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(3, 5, NULL, '出發去日本', NULL, 2, 3, '2026-09-22', '2026-09-30', 50, 5000000.00, 'TWD', 'None', 'private', 'planning', 'tWpvx7sAN1zdeKCOLlUhpw', '2026-09-10 10:18:41', '2026-09-10 10:25:22'),
(6, 5, NULL, '出發去日本', NULL, 1, 1, '2026-09-23', '2026-09-26', 1, 500.00, 'TWD', NULL, 'private', 'planning', 'qbU34q-ANPQr1XvADL6ihQ', '2026-09-23 21:28:24', '2026-09-23 21:28:24');

-- --------------------------------------------------------

--
-- 資料表結構 `trip_invitations`
--

CREATE TABLE `trip_invitations` (
  `invitation_id` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `inviter_id` bigint(20) UNSIGNED NOT NULL,
  `invitee_id` bigint(20) UNSIGNED DEFAULT NULL,
  `invitee_email` varchar(150) DEFAULT NULL,
  `invite_code` varchar(50) NOT NULL,
  `invite_token` varchar(120) DEFAULT NULL,
  `assigned_role` enum('editor','viewer') NOT NULL DEFAULT 'viewer',
  `status` enum('pending','accepted','rejected','expired','cancelled') NOT NULL DEFAULT 'pending',
  `expires_at` datetime DEFAULT NULL,
  `responded_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- 資料表結構 `trip_members`
--

CREATE TABLE `trip_members` (
  `trip_member_id` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `member_role` enum('owner','editor','viewer') NOT NULL DEFAULT 'viewer',
  `join_status` enum('invited','accepted','rejected','left','removed') NOT NULL DEFAULT 'invited',
  `joined_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `trip_members`
--

INSERT INTO `trip_members` (`trip_member_id`, `trip_id`, `user_id`, `member_role`, `join_status`, `joined_at`, `created_at`) VALUES
(1, 1, 1, 'owner', 'accepted', '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(4, 3, 5, 'owner', 'accepted', '2026-09-10 10:18:41', '2026-09-10 10:18:41'),
(8, 6, 5, 'owner', 'accepted', '2026-09-23 21:28:24', '2026-09-23 21:28:24');

-- --------------------------------------------------------

--
-- 資料表結構 `users`
--

CREATE TABLE `users` (
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `nickname` varchar(100) DEFAULT NULL,
  `email` varchar(150) NOT NULL,
  `phone` varchar(30) DEFAULT NULL,
  `avatar_path` varchar(255) DEFAULT NULL,
  `role` enum('member','content_admin','system_admin') NOT NULL DEFAULT 'member',
  `status` enum('active','disabled','deleted') NOT NULL DEFAULT 'active',
  `last_login_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `users`
--

INSERT INTO `users` (`user_id`, `username`, `password_hash`, `full_name`, `nickname`, `email`, `phone`, `avatar_path`, `role`, `status`, `last_login_at`, `created_at`, `updated_at`) VALUES
(1, 'member01', 'pbkdf2:sha256:600000$67d6646475fb2904$439c40d8eb4f1f1e9de61f14cc0abafae1f4b88c3766c55cdf8827b959c106e9', '一般會員測試', '旅遊小幫手', 'member01@example.com', NULL, NULL, 'member', 'active', NULL, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(2, 'contentadmin', 'pbkdf2:sha256:600000$67d6646475fb2904$439c40d8eb4f1f1e9de61f14cc0abafae1f4b88c3766c55cdf8827b959c106e9', '旅遊內容管理員', '內容管理員', 'contentadmin@example.com', NULL, NULL, 'content_admin', 'active', NULL, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(3, 'admin', 'pbkdf2:sha256:600000$67d6646475fb2904$439c40d8eb4f1f1e9de61f14cc0abafae1f4b88c3766c55cdf8827b959c106e9', '系統管理員', '系統管理員', 'admin@example.com', NULL, NULL, 'system_admin', 'active', NULL, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(5, 'anting', 'scrypt:32768:8:1$PSuF74oLkR4h6bVt$1302dfc259432ea55882af431bcb85f104511590841955077c8b5d209f6760281522fc8663ecaafd85751290b68a73789f5dd858b517534fd2913b5674b13bfb', 'anting', 'anting', 'anitawu0731@gmail.com', NULL, NULL, 'member', 'active', NULL, '2026-09-10 10:17:03', '2026-09-10 10:17:03');

-- --------------------------------------------------------

--
-- 資料表結構 `votes`
--

CREATE TABLE `votes` (
  `vote_id` bigint(20) UNSIGNED NOT NULL,
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `proposal_id` bigint(20) UNSIGNED DEFAULT NULL,
  `created_by` bigint(20) UNSIGNED NOT NULL,
  `title` varchar(150) NOT NULL,
  `vote_type` enum('approval','multiple_choice','single_choice') NOT NULL DEFAULT 'approval',
  `status` enum('open','closed','cancelled') NOT NULL DEFAULT 'open',
  `allow_change` tinyint(1) NOT NULL DEFAULT 1,
  `deadline_at` datetime NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `votes`
--

INSERT INTO `votes` (`vote_id`, `trip_id`, `proposal_id`, `created_by`, `title`, `vote_type`, `status`, `allow_change`, `deadline_at`, `created_at`) VALUES
(6, 3, NULL, 5, '要不要去日本', 'approval', 'closed', 1, '2026-09-10 10:46:00', '2026-09-10 10:46:27');

-- --------------------------------------------------------

--
-- 資料表結構 `vote_options`
--

CREATE TABLE `vote_options` (
  `option_id` bigint(20) UNSIGNED NOT NULL,
  `vote_id` bigint(20) UNSIGNED NOT NULL,
  `option_text` varchar(255) NOT NULL,
  `sort_order` int(10) UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- 資料表結構 `vote_records`
--

CREATE TABLE `vote_records` (
  `vote_record_id` bigint(20) UNSIGNED NOT NULL,
  `vote_id` bigint(20) UNSIGNED NOT NULL,
  `option_id` bigint(20) UNSIGNED DEFAULT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `approval_choice` enum('agree','disagree','neutral') DEFAULT NULL,
  `voted_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- 替換檢視表以便查看 `vw_popular_attractions`
-- (請參考以下實際畫面)
--
CREATE TABLE `vw_popular_attractions` (
`attraction_id` bigint(20) unsigned
,`name` varchar(150)
,`country` varchar(100)
,`city` varchar(100)
,`favorite_count` bigint(21)
,`itinerary_count` bigint(21)
);

-- --------------------------------------------------------

--
-- 替換檢視表以便查看 `vw_trip_expense_summary`
-- (請參考以下實際畫面)
--
CREATE TABLE `vw_trip_expense_summary` (
`trip_id` bigint(20) unsigned
,`trip_name` varchar(150)
,`total_budget` decimal(14,2)
,`currency` char(3)
,`actual_expense` decimal(36,2)
,`remaining_budget` decimal(37,2)
);

-- --------------------------------------------------------

--
-- 檢視表結構 `vw_popular_attractions`
--
DROP TABLE IF EXISTS `vw_popular_attractions`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vw_popular_attractions`  AS SELECT `a`.`attraction_id` AS `attraction_id`, `a`.`name` AS `name`, `c`.`name` AS `country`, `ci`.`name` AS `city`, count(distinct `f`.`favorite_id`) AS `favorite_count`, count(distinct `i`.`itinerary_id`) AS `itinerary_count` FROM ((((`attractions` `a` join `countries` `c` on(`c`.`country_id` = `a`.`country_id`)) join `cities` `ci` on(`ci`.`city_id` = `a`.`city_id`)) left join `favorites` `f` on(`f`.`attraction_id` = `a`.`attraction_id`)) left join `itineraries` `i` on(`i`.`attraction_id` = `a`.`attraction_id`)) WHERE `a`.`deleted_at` is null GROUP BY `a`.`attraction_id`, `a`.`name`, `c`.`name`, `ci`.`name` ;

-- --------------------------------------------------------

--
-- 檢視表結構 `vw_trip_expense_summary`
--
DROP TABLE IF EXISTS `vw_trip_expense_summary`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vw_trip_expense_summary`  AS SELECT `t`.`trip_id` AS `trip_id`, `t`.`trip_name` AS `trip_name`, `t`.`total_budget` AS `total_budget`, `t`.`currency` AS `currency`, coalesce(sum(case when `e`.`expense_type` = 'actual' then `e`.`amount` else 0 end),0) AS `actual_expense`, `t`.`total_budget`- coalesce(sum(case when `e`.`expense_type` = 'actual' then `e`.`amount` else 0 end),0) AS `remaining_budget` FROM (`trips` `t` left join `expenses` `e` on(`e`.`trip_id` = `t`.`trip_id`)) GROUP BY `t`.`trip_id`, `t`.`trip_name`, `t`.`total_budget`, `t`.`currency` ;

--
-- 已傾印資料表的索引
--

--
-- 資料表索引 `accommodations`
--
ALTER TABLE `accommodations`
  ADD PRIMARY KEY (`accommodation_id`),
  ADD KEY `category_id` (`category_id`),
  ADD KEY `country_id` (`country_id`),
  ADD KEY `city_id` (`city_id`),
  ADD KEY `ai_verified_by` (`ai_verified_by`),
  ADD KEY `created_by` (`created_by`);

--
-- 資料表索引 `admin_logs`
--
ALTER TABLE `admin_logs`
  ADD PRIMARY KEY (`admin_log_id`),
  ADD KEY `admin_id` (`admin_id`);

--
-- 資料表索引 `announcements`
--
ALTER TABLE `announcements`
  ADD PRIMARY KEY (`announcement_id`),
  ADD KEY `created_by` (`created_by`);

--
-- 資料表索引 `attachments`
--
ALTER TABLE `attachments`
  ADD PRIMARY KEY (`attachment_id`),
  ADD KEY `uploaded_by` (`uploaded_by`),
  ADD KEY `trip_id` (`trip_id`),
  ADD KEY `itinerary_id` (`itinerary_id`),
  ADD KEY `proposal_id` (`proposal_id`);

--
-- 資料表索引 `attractions`
--
ALTER TABLE `attractions`
  ADD PRIMARY KEY (`attraction_id`),
  ADD KEY `category_id` (`category_id`),
  ADD KEY `country_id` (`country_id`),
  ADD KEY `city_id` (`city_id`),
  ADD KEY `ai_verified_by` (`ai_verified_by`),
  ADD KEY `created_by` (`created_by`);

--
-- 資料表索引 `categories`
--
ALTER TABLE `categories`
  ADD PRIMARY KEY (`category_id`),
  ADD UNIQUE KEY `category_type` (`category_type`,`category_name`),
  ADD KEY `created_by` (`created_by`);

--
-- 資料表索引 `cities`
--
ALTER TABLE `cities`
  ADD PRIMARY KEY (`city_id`),
  ADD UNIQUE KEY `country_id` (`country_id`,`name`);

--
-- 資料表索引 `comments`
--
ALTER TABLE `comments`
  ADD PRIMARY KEY (`comment_id`),
  ADD KEY `trip_id` (`trip_id`),
  ADD KEY `itinerary_id` (`itinerary_id`),
  ADD KEY `proposal_id` (`proposal_id`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `parent_comment_id` (`parent_comment_id`);

--
-- 資料表索引 `countries`
--
ALTER TABLE `countries`
  ADD PRIMARY KEY (`country_id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- 資料表索引 `edit_logs`
--
ALTER TABLE `edit_logs`
  ADD PRIMARY KEY (`edit_log_id`),
  ADD KEY `trip_id` (`trip_id`),
  ADD KEY `user_id` (`user_id`);

--
-- 資料表索引 `expenses`
--
ALTER TABLE `expenses`
  ADD PRIMARY KEY (`expense_id`),
  ADD KEY `trip_id` (`trip_id`),
  ADD KEY `category_id` (`category_id`),
  ADD KEY `created_by` (`created_by`),
  ADD KEY `payer_id` (`payer_id`);

--
-- 資料表索引 `expense_splits`
--
ALTER TABLE `expense_splits`
  ADD PRIMARY KEY (`split_id`),
  ADD UNIQUE KEY `expense_id` (`expense_id`,`user_id`),
  ADD KEY `user_id` (`user_id`);

--
-- 資料表索引 `favorites`
--
ALTER TABLE `favorites`
  ADD PRIMARY KEY (`favorite_id`),
  ADD UNIQUE KEY `user_id` (`user_id`,`trip_id`),
  ADD UNIQUE KEY `user_id_2` (`user_id`,`attraction_id`),
  ADD KEY `trip_id` (`trip_id`),
  ADD KEY `attraction_id` (`attraction_id`);

--
-- 資料表索引 `flights`
--
ALTER TABLE `flights`
  ADD PRIMARY KEY (`flight_id`),
  ADD KEY `fk_flights_origin_country` (`origin_country_id`),
  ADD KEY `fk_flights_origin_city` (`origin_city_id`),
  ADD KEY `fk_flights_destination_country` (`destination_country_id`),
  ADD KEY `fk_flights_destination_city` (`destination_city_id`);

--
-- 資料表索引 `itineraries`
--
ALTER TABLE `itineraries`
  ADD PRIMARY KEY (`itinerary_id`),
  ADD KEY `trip_id` (`trip_id`),
  ADD KEY `created_by` (`created_by`),
  ADD KEY `attraction_id` (`attraction_id`),
  ADD KEY `restaurant_id` (`restaurant_id`),
  ADD KEY `accommodation_id` (`accommodation_id`);

--
-- 資料表索引 `notifications`
--
ALTER TABLE `notifications`
  ADD PRIMARY KEY (`notification_id`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `trip_id` (`trip_id`);

--
-- 資料表索引 `proposals`
--
ALTER TABLE `proposals`
  ADD PRIMARY KEY (`proposal_id`),
  ADD KEY `trip_id` (`trip_id`),
  ADD KEY `proposer_id` (`proposer_id`),
  ADD KEY `reviewed_by` (`reviewed_by`);

--
-- 資料表索引 `reports`
--
ALTER TABLE `reports`
  ADD PRIMARY KEY (`report_id`),
  ADD KEY `reporter_id` (`reporter_id`),
  ADD KEY `handled_by` (`handled_by`);

--
-- 資料表索引 `restaurants`
--
ALTER TABLE `restaurants`
  ADD PRIMARY KEY (`restaurant_id`),
  ADD KEY `category_id` (`category_id`),
  ADD KEY `country_id` (`country_id`),
  ADD KEY `city_id` (`city_id`),
  ADD KEY `ai_verified_by` (`ai_verified_by`),
  ADD KEY `created_by` (`created_by`);

--
-- 資料表索引 `trains`
--
ALTER TABLE `trains`
  ADD PRIMARY KEY (`train_id`),
  ADD KEY `idx_trains_route` (`origin_station`,`destination_station`);

--
-- 資料表索引 `trips`
--
ALTER TABLE `trips`
  ADD PRIMARY KEY (`trip_id`),
  ADD UNIQUE KEY `share_token` (`share_token`),
  ADD KEY `owner_id` (`owner_id`),
  ADD KEY `category_id` (`category_id`),
  ADD KEY `country_id` (`country_id`),
  ADD KEY `city_id` (`city_id`);

--
-- 資料表索引 `trip_invitations`
--
ALTER TABLE `trip_invitations`
  ADD PRIMARY KEY (`invitation_id`),
  ADD UNIQUE KEY `invite_code` (`invite_code`),
  ADD UNIQUE KEY `invite_token` (`invite_token`),
  ADD KEY `trip_id` (`trip_id`),
  ADD KEY `inviter_id` (`inviter_id`),
  ADD KEY `invitee_id` (`invitee_id`);

--
-- 資料表索引 `trip_members`
--
ALTER TABLE `trip_members`
  ADD PRIMARY KEY (`trip_member_id`),
  ADD UNIQUE KEY `trip_id` (`trip_id`,`user_id`),
  ADD KEY `user_id` (`user_id`);

--
-- 資料表索引 `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`user_id`),
  ADD UNIQUE KEY `username` (`username`),
  ADD UNIQUE KEY `email` (`email`);

--
-- 資料表索引 `votes`
--
ALTER TABLE `votes`
  ADD PRIMARY KEY (`vote_id`),
  ADD KEY `trip_id` (`trip_id`),
  ADD KEY `proposal_id` (`proposal_id`),
  ADD KEY `created_by` (`created_by`);

--
-- 資料表索引 `vote_options`
--
ALTER TABLE `vote_options`
  ADD PRIMARY KEY (`option_id`),
  ADD UNIQUE KEY `vote_id` (`vote_id`,`option_text`);

--
-- 資料表索引 `vote_records`
--
ALTER TABLE `vote_records`
  ADD PRIMARY KEY (`vote_record_id`),
  ADD UNIQUE KEY `vote_id` (`vote_id`,`user_id`),
  ADD KEY `option_id` (`option_id`),
  ADD KEY `user_id` (`user_id`);

--
-- 在傾印的資料表使用自動遞增(AUTO_INCREMENT)
--

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `accommodations`
--
ALTER TABLE `accommodations`
  MODIFY `accommodation_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `admin_logs`
--
ALTER TABLE `admin_logs`
  MODIFY `admin_log_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=62;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `announcements`
--
ALTER TABLE `announcements`
  MODIFY `announcement_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `attachments`
--
ALTER TABLE `attachments`
  MODIFY `attachment_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `attractions`
--
ALTER TABLE `attractions`
  MODIFY `attraction_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=14;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `categories`
--
ALTER TABLE `categories`
  MODIFY `category_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=16;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `cities`
--
ALTER TABLE `cities`
  MODIFY `city_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=396;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `comments`
--
ALTER TABLE `comments`
  MODIFY `comment_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `countries`
--
ALTER TABLE `countries`
  MODIFY `country_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `edit_logs`
--
ALTER TABLE `edit_logs`
  MODIFY `edit_log_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `expenses`
--
ALTER TABLE `expenses`
  MODIFY `expense_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `expense_splits`
--
ALTER TABLE `expense_splits`
  MODIFY `split_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `favorites`
--
ALTER TABLE `favorites`
  MODIFY `favorite_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `flights`
--
ALTER TABLE `flights`
  MODIFY `flight_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=27;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `itineraries`
--
ALTER TABLE `itineraries`
  MODIFY `itinerary_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `notifications`
--
ALTER TABLE `notifications`
  MODIFY `notification_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `proposals`
--
ALTER TABLE `proposals`
  MODIFY `proposal_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `reports`
--
ALTER TABLE `reports`
  MODIFY `report_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `restaurants`
--
ALTER TABLE `restaurants`
  MODIFY `restaurant_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `trains`
--
ALTER TABLE `trains`
  MODIFY `train_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=53;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `trips`
--
ALTER TABLE `trips`
  MODIFY `trip_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `trip_invitations`
--
ALTER TABLE `trip_invitations`
  MODIFY `invitation_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `trip_members`
--
ALTER TABLE `trip_members`
  MODIFY `trip_member_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `users`
--
ALTER TABLE `users`
  MODIFY `user_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `votes`
--
ALTER TABLE `votes`
  MODIFY `vote_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `vote_options`
--
ALTER TABLE `vote_options`
  MODIFY `option_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `vote_records`
--
ALTER TABLE `vote_records`
  MODIFY `vote_record_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- 已傾印資料表的限制式
--

--
-- 資料表的限制式 `accommodations`
--
ALTER TABLE `accommodations`
  ADD CONSTRAINT `accommodations_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `accommodations_ibfk_2` FOREIGN KEY (`country_id`) REFERENCES `countries` (`country_id`),
  ADD CONSTRAINT `accommodations_ibfk_3` FOREIGN KEY (`city_id`) REFERENCES `cities` (`city_id`),
  ADD CONSTRAINT `accommodations_ibfk_4` FOREIGN KEY (`ai_verified_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `accommodations_ibfk_5` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- 資料表的限制式 `admin_logs`
--
ALTER TABLE `admin_logs`
  ADD CONSTRAINT `admin_logs_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `users` (`user_id`);

--
-- 資料表的限制式 `announcements`
--
ALTER TABLE `announcements`
  ADD CONSTRAINT `announcements_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`);

--
-- 資料表的限制式 `attachments`
--
ALTER TABLE `attachments`
  ADD CONSTRAINT `attachments_ibfk_1` FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `attachments_ibfk_2` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `attachments_ibfk_3` FOREIGN KEY (`itinerary_id`) REFERENCES `itineraries` (`itinerary_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `attachments_ibfk_4` FOREIGN KEY (`proposal_id`) REFERENCES `proposals` (`proposal_id`) ON DELETE CASCADE;

--
-- 資料表的限制式 `attractions`
--
ALTER TABLE `attractions`
  ADD CONSTRAINT `attractions_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `attractions_ibfk_2` FOREIGN KEY (`country_id`) REFERENCES `countries` (`country_id`),
  ADD CONSTRAINT `attractions_ibfk_3` FOREIGN KEY (`city_id`) REFERENCES `cities` (`city_id`),
  ADD CONSTRAINT `attractions_ibfk_4` FOREIGN KEY (`ai_verified_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `attractions_ibfk_5` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- 資料表的限制式 `categories`
--
ALTER TABLE `categories`
  ADD CONSTRAINT `categories_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- 資料表的限制式 `cities`
--
ALTER TABLE `cities`
  ADD CONSTRAINT `cities_ibfk_1` FOREIGN KEY (`country_id`) REFERENCES `countries` (`country_id`);

--
-- 資料表的限制式 `comments`
--
ALTER TABLE `comments`
  ADD CONSTRAINT `comments_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `comments_ibfk_2` FOREIGN KEY (`itinerary_id`) REFERENCES `itineraries` (`itinerary_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `comments_ibfk_3` FOREIGN KEY (`proposal_id`) REFERENCES `proposals` (`proposal_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `comments_ibfk_4` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `comments_ibfk_5` FOREIGN KEY (`parent_comment_id`) REFERENCES `comments` (`comment_id`) ON DELETE CASCADE;

--
-- 資料表的限制式 `edit_logs`
--
ALTER TABLE `edit_logs`
  ADD CONSTRAINT `edit_logs_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `edit_logs_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`);

--
-- 資料表的限制式 `expenses`
--
ALTER TABLE `expenses`
  ADD CONSTRAINT `expenses_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `expenses_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `expenses_ibfk_3` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`),
  ADD CONSTRAINT `expenses_ibfk_4` FOREIGN KEY (`payer_id`) REFERENCES `users` (`user_id`);

--
-- 資料表的限制式 `expense_splits`
--
ALTER TABLE `expense_splits`
  ADD CONSTRAINT `expense_splits_ibfk_1` FOREIGN KEY (`expense_id`) REFERENCES `expenses` (`expense_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `expense_splits_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE;

--
-- 資料表的限制式 `favorites`
--
ALTER TABLE `favorites`
  ADD CONSTRAINT `favorites_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `favorites_ibfk_2` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `favorites_ibfk_3` FOREIGN KEY (`attraction_id`) REFERENCES `attractions` (`attraction_id`) ON DELETE CASCADE;

--
-- 資料表的限制式 `flights`
--
ALTER TABLE `flights`
  ADD CONSTRAINT `fk_flights_destination_city` FOREIGN KEY (`destination_city_id`) REFERENCES `cities` (`city_id`),
  ADD CONSTRAINT `fk_flights_destination_country` FOREIGN KEY (`destination_country_id`) REFERENCES `countries` (`country_id`),
  ADD CONSTRAINT `fk_flights_origin_city` FOREIGN KEY (`origin_city_id`) REFERENCES `cities` (`city_id`),
  ADD CONSTRAINT `fk_flights_origin_country` FOREIGN KEY (`origin_country_id`) REFERENCES `countries` (`country_id`);

--
-- 資料表的限制式 `itineraries`
--
ALTER TABLE `itineraries`
  ADD CONSTRAINT `itineraries_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `itineraries_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`),
  ADD CONSTRAINT `itineraries_ibfk_3` FOREIGN KEY (`attraction_id`) REFERENCES `attractions` (`attraction_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `itineraries_ibfk_4` FOREIGN KEY (`restaurant_id`) REFERENCES `restaurants` (`restaurant_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `itineraries_ibfk_5` FOREIGN KEY (`accommodation_id`) REFERENCES `accommodations` (`accommodation_id`) ON DELETE SET NULL;

--
-- 資料表的限制式 `notifications`
--
ALTER TABLE `notifications`
  ADD CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `notifications_ibfk_2` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE;

--
-- 資料表的限制式 `proposals`
--
ALTER TABLE `proposals`
  ADD CONSTRAINT `proposals_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `proposals_ibfk_2` FOREIGN KEY (`proposer_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `proposals_ibfk_3` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- 資料表的限制式 `reports`
--
ALTER TABLE `reports`
  ADD CONSTRAINT `reports_ibfk_1` FOREIGN KEY (`reporter_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `reports_ibfk_2` FOREIGN KEY (`handled_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- 資料表的限制式 `restaurants`
--
ALTER TABLE `restaurants`
  ADD CONSTRAINT `restaurants_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `restaurants_ibfk_2` FOREIGN KEY (`country_id`) REFERENCES `countries` (`country_id`),
  ADD CONSTRAINT `restaurants_ibfk_3` FOREIGN KEY (`city_id`) REFERENCES `cities` (`city_id`),
  ADD CONSTRAINT `restaurants_ibfk_4` FOREIGN KEY (`ai_verified_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `restaurants_ibfk_5` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- 資料表的限制式 `trips`
--
ALTER TABLE `trips`
  ADD CONSTRAINT `trips_ibfk_1` FOREIGN KEY (`owner_id`) REFERENCES `users` (`user_id`),
  ADD CONSTRAINT `trips_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `trips_ibfk_3` FOREIGN KEY (`country_id`) REFERENCES `countries` (`country_id`),
  ADD CONSTRAINT `trips_ibfk_4` FOREIGN KEY (`city_id`) REFERENCES `cities` (`city_id`);

--
-- 資料表的限制式 `trip_invitations`
--
ALTER TABLE `trip_invitations`
  ADD CONSTRAINT `trip_invitations_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `trip_invitations_ibfk_2` FOREIGN KEY (`inviter_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `trip_invitations_ibfk_3` FOREIGN KEY (`invitee_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- 資料表的限制式 `trip_members`
--
ALTER TABLE `trip_members`
  ADD CONSTRAINT `trip_members_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `trip_members_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE;

--
-- 資料表的限制式 `votes`
--
ALTER TABLE `votes`
  ADD CONSTRAINT `votes_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `votes_ibfk_2` FOREIGN KEY (`proposal_id`) REFERENCES `proposals` (`proposal_id`) ON DELETE SET NULL,
  ADD CONSTRAINT `votes_ibfk_3` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`);

--
-- 資料表的限制式 `vote_options`
--
ALTER TABLE `vote_options`
  ADD CONSTRAINT `vote_options_ibfk_1` FOREIGN KEY (`vote_id`) REFERENCES `votes` (`vote_id`) ON DELETE CASCADE;

--
-- 資料表的限制式 `vote_records`
--
ALTER TABLE `vote_records`
  ADD CONSTRAINT `vote_records_ibfk_1` FOREIGN KEY (`vote_id`) REFERENCES `votes` (`vote_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `vote_records_ibfk_2` FOREIGN KEY (`option_id`) REFERENCES `vote_options` (`option_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `vote_records_ibfk_3` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
