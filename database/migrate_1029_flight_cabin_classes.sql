-- 目前所有機票資料都只有經濟艙，「艙等」篩選功能篩不出其他結果。
-- 幫傳統航空公司（非廉航）的既有航班各補一個商務艙版本（同航班號、同時刻，價格依艙等調整、座位較少），
-- 再幫幾條熱門長程航線（台北↔東京/新加坡/香港/曼谷，用該航線上定位較高的航空公司）補頭等艙版本。
-- 廉價航空（台灣虎航、樂桃航空、酷航、德威航空、真航空、香港快運航空、泰國微笑航空）維持只有經濟艙，符合實際廉航不賣商務/頭等艙的情況。

-- 商務艙：全日空、中華航空、星宇航空、日本航空、長榮航空、大韓航空、泰國航空、中華航空、新加坡航空、長榮航空、國泰航空 既有航班
INSERT INTO `flights`
  (`airline_name`,`flight_number`,`origin_country_id`,`origin_city_id`,`destination_country_id`,`destination_city_id`,
   `departure_time`,`arrival_time`,`duration_minutes`,`price`,`cabin_class`,`stops`,`seats_available`,`status`)
SELECT `airline_name`,`flight_number`,`origin_country_id`,`origin_city_id`,`destination_country_id`,`destination_city_id`,
       `departure_time`,`arrival_time`,`duration_minutes`, ROUND(`price` * 2.3, -2), '商務艙', `stops`, 5, `status`
FROM `flights`
WHERE `cabin_class` = '經濟艙'
  AND `airline_name` IN ('中華航空','星宇航空','日本航空','長榮航空','大韓航空','泰國航空','新加坡航空','國泰航空','全日空航空');

-- 頭等艙：幾條熱門長程航線上，實際有提供頭等艙服務的航空公司（中華航空、新加坡航空、國泰航空）
INSERT INTO `flights`
  (`airline_name`,`flight_number`,`origin_country_id`,`origin_city_id`,`destination_country_id`,`destination_city_id`,
   `departure_time`,`arrival_time`,`duration_minutes`,`price`,`cabin_class`,`stops`,`seats_available`,`status`)
SELECT `airline_name`,`flight_number`,`origin_country_id`,`origin_city_id`,`destination_country_id`,`destination_city_id`,
       `departure_time`,`arrival_time`,`duration_minutes`, ROUND(`price` * 4.2, -2), '頭等艙', `stops`, 2, `status`
FROM `flights`
WHERE `cabin_class` = '經濟艙'
  AND (
    (`airline_name` = '中華航空' AND `flight_number` IN ('CI100','CI101','CI835','CI836'))
    OR (`airline_name` = '新加坡航空' AND `flight_number` IN ('SQ879','SQ880'))
    OR (`airline_name` = '國泰航空' AND `flight_number` IN ('CX451','CX452'))
  );
