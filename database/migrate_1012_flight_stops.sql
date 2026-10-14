ALTER TABLE flights ADD COLUMN IF NOT EXISTS stops TINYINT UNSIGNED NOT NULL DEFAULT 0 AFTER cabin_class;

INSERT INTO flights
  (airline_name, flight_number, origin_country_id, origin_city_id, destination_country_id, destination_city_id,
   departure_time, arrival_time, duration_minutes, price, cabin_class, stops, seats_available, status)
SELECT v.airline_name, v.flight_number, o.country_id, o.city_id, d.country_id, d.city_id,
       v.departure_time, v.arrival_time, v.duration_minutes, v.price, v.cabin_class, v.stops, v.seats_available, 'active'
FROM (
  SELECT '台北市' AS origin_city, '曼谷' AS destination_city, '國泰航空' AS airline_name, 'CX400' AS flight_number, '07:00:00' AS departure_time, '14:20:00' AS arrival_time, 440 AS duration_minutes, 9500.00 AS price, '經濟艙' AS cabin_class, 1 AS stops, 9 AS seats_available
  UNION ALL SELECT '曼谷', '台北市', '國泰航空', 'CX401', '16:00:00', '22:10:00', 370, 9500.00, '經濟艙', 1, 9
) v
JOIN cities o ON o.name = v.origin_city
JOIN cities d ON d.name = v.destination_city
WHERE NOT EXISTS (
  SELECT 1 FROM flights f WHERE f.flight_number = v.flight_number
    AND f.origin_city_id = o.city_id AND f.destination_city_id = d.city_id
);
