-- One-time migration from the original schema to the content-admin schema.
-- Back up the travel_together database before running this file.
USE `travel_together`;

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
 UNIQUE(country_id, name),
 CONSTRAINT fk_cities_country FOREIGN KEY(country_id) REFERENCES countries(country_id)
) ENGINE=InnoDB;

INSERT IGNORE INTO countries(name)
SELECT country FROM attractions
UNION SELECT country FROM restaurants
UNION SELECT country FROM accommodations;

INSERT IGNORE INTO cities(country_id, name)
SELECT co.country_id, places.city
FROM (
 SELECT country, city FROM attractions
 UNION SELECT country, city FROM restaurants
 UNION SELECT country, city FROM accommodations
) places
JOIN countries co ON co.name = places.country;

ALTER TABLE attractions
 ADD COLUMN country_id BIGINT UNSIGNED NULL AFTER name,
 ADD COLUMN city_id BIGINT UNSIGNED NULL AFTER country_id,
 ADD COLUMN ai_verified_at DATETIME NULL AFTER status,
 ADD COLUMN ai_verified_by BIGINT UNSIGNED NULL AFTER ai_verified_at;

ALTER TABLE restaurants
 ADD COLUMN country_id BIGINT UNSIGNED NULL AFTER name,
 ADD COLUMN city_id BIGINT UNSIGNED NULL AFTER country_id,
 ADD COLUMN ai_verified_at DATETIME NULL AFTER status,
 ADD COLUMN ai_verified_by BIGINT UNSIGNED NULL AFTER ai_verified_at;

ALTER TABLE accommodations
 ADD COLUMN country_id BIGINT UNSIGNED NULL AFTER name,
 ADD COLUMN city_id BIGINT UNSIGNED NULL AFTER country_id,
 ADD COLUMN check_in_time TIME NULL AFTER price_per_night,
 ADD COLUMN check_out_time TIME NULL AFTER check_in_time,
 ADD COLUMN ai_verified_at DATETIME NULL AFTER status,
 ADD COLUMN ai_verified_by BIGINT UNSIGNED NULL AFTER ai_verified_at;

UPDATE attractions a
JOIN countries co ON co.name = a.country
JOIN cities ci ON ci.country_id = co.country_id AND ci.name = a.city
SET a.country_id = co.country_id, a.city_id = ci.city_id;

UPDATE restaurants r
JOIN countries co ON co.name = r.country
JOIN cities ci ON ci.country_id = co.country_id AND ci.name = r.city
SET r.country_id = co.country_id, r.city_id = ci.city_id;

UPDATE accommodations ac
JOIN countries co ON co.name = ac.country
JOIN cities ci ON ci.country_id = co.country_id AND ci.name = ac.city
SET ac.country_id = co.country_id, ac.city_id = ci.city_id;

ALTER TABLE attractions
 MODIFY country_id BIGINT UNSIGNED NOT NULL,
 MODIFY city_id BIGINT UNSIGNED NOT NULL,
 ADD CONSTRAINT fk_attractions_country FOREIGN KEY(country_id) REFERENCES countries(country_id),
 ADD CONSTRAINT fk_attractions_city FOREIGN KEY(city_id) REFERENCES cities(city_id),
 ADD CONSTRAINT fk_attractions_ai_user FOREIGN KEY(ai_verified_by) REFERENCES users(user_id) ON DELETE SET NULL,
 DROP COLUMN country,
 DROP COLUMN city;

ALTER TABLE restaurants
 MODIFY country_id BIGINT UNSIGNED NOT NULL,
 MODIFY city_id BIGINT UNSIGNED NOT NULL,
 ADD CONSTRAINT fk_restaurants_country FOREIGN KEY(country_id) REFERENCES countries(country_id),
 ADD CONSTRAINT fk_restaurants_city FOREIGN KEY(city_id) REFERENCES cities(city_id),
 ADD CONSTRAINT fk_restaurants_ai_user FOREIGN KEY(ai_verified_by) REFERENCES users(user_id) ON DELETE SET NULL,
 DROP COLUMN country,
 DROP COLUMN city;

ALTER TABLE accommodations
 MODIFY country_id BIGINT UNSIGNED NOT NULL,
 MODIFY city_id BIGINT UNSIGNED NOT NULL,
 ADD CONSTRAINT fk_accommodations_country FOREIGN KEY(country_id) REFERENCES countries(country_id),
 ADD CONSTRAINT fk_accommodations_city FOREIGN KEY(city_id) REFERENCES cities(city_id),
 ADD CONSTRAINT fk_accommodations_ai_user FOREIGN KEY(ai_verified_by) REFERENCES users(user_id) ON DELETE SET NULL,
 DROP COLUMN country,
 DROP COLUMN city;

DROP VIEW IF EXISTS vw_popular_attractions;
CREATE VIEW vw_popular_attractions AS
SELECT a.attraction_id, a.name, co.name AS country, ci.name AS city,
 COUNT(DISTINCT f.favorite_id) favorite_count,
 COUNT(DISTINCT i.itinerary_id) itinerary_count
FROM attractions a
JOIN countries co ON co.country_id = a.country_id
JOIN cities ci ON ci.city_id = a.city_id
LEFT JOIN favorites f ON f.attraction_id = a.attraction_id
LEFT JOIN itineraries i ON i.attraction_id = a.attraction_id
GROUP BY a.attraction_id, a.name, co.name, ci.name;

SELECT 'Content-admin schema migration completed' AS message;
