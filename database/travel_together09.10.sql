-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- 主機： 127.0.0.1
-- 產生時間： 2026-09-10 04:49:51
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
  `ai_verified_at` datetime DEFAULT NULL,
  `ai_verified_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `accommodations`
--

INSERT INTO `accommodations` (`accommodation_id`, `category_id`, `name`, `country_id`, `city_id`, `address`, `accommodation_type`, `price_per_night`, `check_in_time`, `check_out_time`, `description`, `website_url`, `image_path`, `status`, `ai_verified_at`, `ai_verified_by`, `created_by`, `created_at`, `updated_at`) VALUES
(1, 15, 'Grand Hyatt Taipei', 1, 1, '110061台灣臺北市信義區西村里松壽路2號', '度假酒店', 0.00, NULL, NULL, '鄰近台北 101 大樓的新潮飯店，附設室外泳池、健身中心、8 間餐廳和酒吧。', 'https://www.hyatt.com/grand-hyatt/en-US/taigh-grand-hyatt-taipei?src=corp_lclb_google_seo_taigh&utm_source=google&utm_medium=organic&utm_campaign=lmr', NULL, 'active', NULL, NULL, 2, '2026-09-08 18:24:14', '2026-09-08 18:24:14'),
(2, 5, '台北W飯店', 1, 1, '110台灣臺北市信義區興雅里忠孝東路五段10號', '飯店', 0.00, NULL, NULL, '內有奇趣客房的時尚高樓飯店，附設餐廳、水療中心和位於 10 樓的戶外泳池。', 'https://www.marriott.com/en-us/hotels/tpewh-w-taipei/overview/?scid=f2ae0541-1279-4f24-b197-a979c79310b0', NULL, 'active', NULL, NULL, 2, '2026-09-08 18:24:15', '2026-09-08 18:24:15'),
(3, 5, 'Sheraton Grand Taipei Hotel', 1, 1, '100台灣臺北市中正區幸福里忠孝東路一段12號', '飯店', 0.00, NULL, NULL, '高級飯店提供溫馨客房和豪華套房，設有 SPA、屋頂泳池和 9 種餐飲選擇。', 'https://www.marriott.com/en-us/hotels/tpest-sheraton-grand-taipei-hotel/overview/?scid=f2ae0541-1279-4f24-b197-a979c79310b0', NULL, 'active', NULL, NULL, 2, '2026-09-08 18:24:16', '2026-09-08 18:24:16'),
(4, 5, '美麗信花園酒店', 1, 1, '104台灣臺北市中山區市民大道三段83號', '飯店', 0.00, NULL, NULL, '高級的住宿環境有現代風格的客房，附設餐廳和健身中心，並提供免費早餐。', 'http://www.miramargarden.com.tw/zh-tw/%E5%8F%B0%E5%8C%97%E7%BE%8E%E9%BA%97%E4%BF%A1', NULL, 'active', NULL, NULL, 2, '2026-09-08 18:24:16', '2026-09-08 18:24:16');

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
(7, 2, 'approve_proposal', 'proposal', 1, '核准提案', '127.0.0.1', '2026-09-10 10:11:13');

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
  `ai_verified_at` datetime DEFAULT NULL,
  `ai_verified_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `attractions`
--

INSERT INTO `attractions` (`attraction_id`, `category_id`, `name`, `country_id`, `city_id`, `address`, `latitude`, `longitude`, `opening_hours`, `ticket_price`, `suggested_duration_minutes`, `description`, `website_url`, `image_path`, `is_popular`, `status`, `ai_verified_at`, `ai_verified_by`, `created_by`, `created_at`, `updated_at`) VALUES
(1, 3, '台北101', 1, 1, '台北市信義區信義路五段7號', NULL, NULL, NULL, 600.00, 120, '台北代表性地標與觀景台', NULL, NULL, 1, 'active', NULL, NULL, 2, '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(2, 9, '國立故宮博物院', 1, 1, '111台灣臺北市士林區至善路二段221號', 25.1023554, 121.5484925, '星期一: 休息；星期二: 09:00 – 19:00；星期三: 09:00 – 19:00；星期四: 09:00 – 19:00；星期五: 09:00 – 19:00；星期六: 09:00 – 19:00；星期日: 09:00 – 19:00', 0.00, NULL, '人潮絡繹不絕的博物館，擁有世界上最龐大的中國藝術品和文物收藏。', 'https://www.npm.gov.tw/', NULL, 0, 'active', NULL, NULL, 2, '2026-09-08 18:24:07', '2026-09-08 18:24:07'),
(3, 10, '士林夜市', 1, 1, '111台灣臺北市士林區義信里基河路101號', 25.0884972, 121.5243504, '星期一: 16:00 – 00:00；星期二: 16:00 – 00:00；星期三: 16:00 – 00:00；星期四: 16:00 – 00:00；星期五: 16:00 – 00:00；星期六: 16:00 – 00:00；星期日: 16:00 – 00:00', 0.00, NULL, '這座攤販雲集的傳統夜市售有街頭小吃、服飾和珠寶。', 'https://www.travel.taipei/zh-tw/attraction/details/1536', NULL, 0, 'active', NULL, NULL, 2, '2026-09-08 18:24:07', '2026-09-08 18:24:07'),
(4, NULL, '西門町', 1, 1, '108台灣臺北市萬華區西門町', 25.0446664, 121.5063096, NULL, 0.00, NULL, '人聲鼎沸的街區，林立著全市最高檔的商店、酒吧和餐廳。', 'https://maps.google.com/?cid=14696636719173915895&g_mp=Cidnb29nbGUubWFwcy5wbGFjZXMudjEuUGxhY2VzLlNlYXJjaFRleHQQAhgEIAA', NULL, 0, 'pending', NULL, NULL, 2, '2026-09-08 18:24:09', '2026-09-08 18:24:09'),
(5, 11, '國立中正紀念堂', 1, 1, '100台灣臺北市中正區', 25.0355020, 121.5201832, '星期一: 09:00 – 18:00；星期二: 09:00 – 18:00；星期三: 09:00 – 18:00；星期四: 09:00 – 18:00；星期五: 09:00 – 18:00；星期六: 09:00 – 18:00；星期日: 09:00 – 18:00', 0.00, NULL, '著名的紀念堂，周圍是一個大型公園，園內有魚塘和花園。', 'https://www.cksmh.gov.tw/', NULL, 0, 'active', NULL, NULL, 2, '2026-09-08 18:24:10', '2026-09-08 18:24:10'),
(10, NULL, '大稻埕碼頭貨櫃市集', 1, 1, '103台灣臺北市大同區永樂里民生西路底，五號水門', 25.0565135, 121.5075150, '星期一: 16:00 – 22:00；星期二: 16:00 – 22:00；星期三: 16:00 – 22:00；星期四: 16:00 – 22:00；星期五: 16:00 – 22:00；星期六: 12:00 – 22:00；星期日: 12:00 – 22:00', 0.00, NULL, '坐落碼頭的熱門夜生活景點，有水岸咖啡廳、小販，周末則有樂團演出和木偶秀。', 'https://www.mediasphere.com.tw/venues/1', NULL, 0, 'pending', NULL, NULL, 2, '2026-09-08 18:25:17', '2026-09-08 18:25:17'),
(11, NULL, '華山1914文化創意產業園區', 1, 1, '100台灣臺北市中正區梅花里八德路一段1號', 25.0440698, 121.5293583, '星期一: 11:00 – 21:00；星期二: 11:00 – 21:00；星期三: 11:00 – 21:00；星期四: 11:00 – 21:00；星期五: 11:00 – 21:00；星期六: 11:00 – 21:00；星期日: 11:00 – 21:00', 0.00, NULL, '這間藏身舊酒廠的文化樞紐有不少商家進駐，還有當地藝術、電影、工藝展覽與活動。', 'http://www.huashan1914.com/', NULL, 0, 'pending', NULL, NULL, 2, '2026-09-08 18:25:17', '2026-09-08 18:25:17');

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
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `cities`
--

INSERT INTO `cities` (`city_id`, `country_id`, `name`, `created_at`, `updated_at`) VALUES
(1, 1, '台北市', '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(2, 1, '高雄市', '2026-09-08 18:17:45', '2026-09-08 18:17:45'),
(3, 2, '東京都', '2026-09-08 18:17:45', '2026-09-08 18:17:45');

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
(2, '日本', '2026-09-08 18:17:45', '2026-09-08 18:17:45');

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
(1, 1, 1, '2026-08-10', 'attraction', '參觀台北101', '10:00:00', '12:00:00', '台北市信義區信義路五段7號', NULL, 0, 600.00, NULL, 1, NULL, NULL, 1, '2026-09-08 18:17:45', '2026-09-08 18:17:45');

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
  `ai_verified_at` datetime DEFAULT NULL,
  `ai_verified_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_by` bigint(20) UNSIGNED DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- 傾印資料表的資料 `restaurants`
--

INSERT INTO `restaurants` (`restaurant_id`, `category_id`, `name`, `country_id`, `city_id`, `address`, `cuisine_type`, `price_level`, `opening_hours`, `description`, `website_url`, `image_path`, `status`, `ai_verified_at`, `ai_verified_by`, `created_by`, `created_at`, `updated_at`) VALUES
(1, 12, '鼎泰豐 信義店', 1, 1, '106台灣臺北市大安區福住里信義路二段194號', '外賣餐廳', 'medium', '星期一: 11:00 – 20:30；星期二: 11:00 – 20:30；星期三: 11:00 – 20:30；星期四: 11:00 – 20:30；星期五: 11:00 – 20:30；星期六: 10:30 – 20:30；星期日: 10:30 – 20:30', '外賣餐廳，位於台灣臺北市，是當地值得一遊的景點。', 'https://www.dintaifung.com.tw/', NULL, 'active', NULL, NULL, 2, '2026-09-08 18:24:11', '2026-09-08 18:24:11'),
(2, 13, '阿宗麵線', 1, 1, '108台灣臺北市萬華區西門里峨眉街8-1號', '麵店', 'low', '星期一: 07:30 – 22:30；星期二: 07:30 – 22:30；星期三: 07:30 – 22:30；星期四: 07:30 – 22:30；星期五: 07:30 – 23:00；星期六: 07:30 – 23:00；星期日: 07:30 – 22:30', '如果到台灣臺北市旅遊，不妨把麵店阿宗麵線排進行程裡。', 'https://aychungflourricenoodle.shop/', NULL, 'active', NULL, NULL, 2, '2026-09-08 18:24:12', '2026-09-08 18:24:12'),
(3, 13, '度小月擔仔麵 台北忠孝店', 1, 1, '106台灣臺北市大安區建倫里忠孝東路四段216巷8弄12號', '麵店', 'medium', '星期一: 11:00 – 15:00, 16:30 – 21:00；星期二: 11:00 – 15:00, 16:30 – 21:00；星期三: 11:00 – 15:00, 16:30 – 21:00；星期四: 11:00 – 15:00, 16:30 – 21:00；星期五: 11:00 – 15:00, 16:30 – 21:00；星期六: 11:00 – 15:00, 16:30 – 21:00；星期日: 11:00 – 15:00, 16:30 – 21:00', '來台灣臺北市旅遊，別錯過度小月擔仔麵 台北忠孝店，這裡是熱門的麵店。', 'http://www.noodle1895.com/', NULL, 'active', NULL, NULL, 2, '2026-09-08 18:24:12', '2026-09-08 18:24:12'),
(4, 14, '春水堂 南港店', 1, 1, '115台灣臺北市南港區三重里經貿二路188號2樓（B棟', '台式餐廳', 'medium', '星期一: 11:00 – 21:30；星期二: 11:00 – 21:30；星期三: 11:00 – 21:30；星期四: 11:00 – 21:30；星期五: 11:00 – 21:30；星期六: 11:00 – 21:30；星期日: 11:00 – 21:30', '如果到台灣臺北市旅遊，不妨把台式餐廳春水堂 南港店排進行程裡。', 'http://chunshuitang.com.tw/', NULL, 'active', NULL, NULL, 2, '2026-09-08 18:24:13', '2026-09-08 18:24:13'),
(5, 14, '欣葉台菜創始店', 1, 1, '10491台灣臺北市中山區晴光里雙城街34之1號', '台式餐廳', 'medium', '星期一: 11:00 – 21:30；星期二: 11:00 – 21:30；星期三: 11:00 – 21:30；星期四: 11:00 – 21:30；星期五: 11:00 – 21:30；星期六: 11:00 – 21:30；星期日: 11:00 – 21:30', '欣葉台菜創始店座落於台灣臺北市，以台式餐廳聞名，值得安排時間造訪。', 'https://www.shinyeh.com.tw/content/zh/brand/Index.aspx?BrandId=1', NULL, 'active', NULL, NULL, 2, '2026-09-08 18:24:14', '2026-09-08 18:24:14');

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
(3, 5, NULL, '出發去日本', NULL, 2, 3, '2026-09-22', '2026-09-30', 50, 5000000.00, 'TWD', 'None', 'private', 'planning', 'tWpvx7sAN1zdeKCOLlUhpw', '2026-09-10 10:18:41', '2026-09-10 10:25:22');

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
(4, 3, 5, 'owner', 'accepted', '2026-09-10 10:18:41', '2026-09-10 10:18:41');

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

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vw_popular_attractions`  AS SELECT `a`.`attraction_id` AS `attraction_id`, `a`.`name` AS `name`, `c`.`name` AS `country`, `ci`.`name` AS `city`, count(distinct `f`.`favorite_id`) AS `favorite_count`, count(distinct `i`.`itinerary_id`) AS `itinerary_count` FROM ((((`attractions` `a` join `countries` `c` on(`c`.`country_id` = `a`.`country_id`)) join `cities` `ci` on(`ci`.`city_id` = `a`.`city_id`)) left join `favorites` `f` on(`f`.`attraction_id` = `a`.`attraction_id`)) left join `itineraries` `i` on(`i`.`attraction_id` = `a`.`attraction_id`)) GROUP BY `a`.`attraction_id`, `a`.`name`, `c`.`name`, `ci`.`name` ;

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
  MODIFY `admin_log_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `announcements`
--
ALTER TABLE `announcements`
  MODIFY `announcement_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `attachments`
--
ALTER TABLE `attachments`
  MODIFY `attachment_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `attractions`
--
ALTER TABLE `attractions`
  MODIFY `attraction_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `categories`
--
ALTER TABLE `categories`
  MODIFY `category_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=16;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `cities`
--
ALTER TABLE `cities`
  MODIFY `city_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `comments`
--
ALTER TABLE `comments`
  MODIFY `comment_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `countries`
--
ALTER TABLE `countries`
  MODIFY `country_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

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
  MODIFY `favorite_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `itineraries`
--
ALTER TABLE `itineraries`
  MODIFY `itinerary_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `notifications`
--
ALTER TABLE `notifications`
  MODIFY `notification_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `proposals`
--
ALTER TABLE `proposals`
  MODIFY `proposal_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `reports`
--
ALTER TABLE `reports`
  MODIFY `report_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `restaurants`
--
ALTER TABLE `restaurants`
  MODIFY `restaurant_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

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
  MODIFY `trip_member_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- 使用資料表自動遞增(AUTO_INCREMENT) `users`
--
ALTER TABLE `users`
  MODIFY `user_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

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
