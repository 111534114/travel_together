-- 五(十一) 行程變更提案：讓共同編輯者可以提出「修改/刪除/新增行程項目」的提案，
-- 附上修改前後比較，交給成員討論投票，最後由建立者確認是否套用。
-- 直接重用既有的 proposals / votes / comments 機制，只是多加一種 proposal_type 和幾個欄位。

ALTER TABLE proposals
  MODIFY `proposal_type` ENUM('attraction','restaurant','accommodation','activity','transport','date','itinerary_change','other') NOT NULL;

ALTER TABLE proposals
  ADD COLUMN `target_itinerary_id` BIGINT UNSIGNED DEFAULT NULL AFTER `proposal_type`,
  ADD COLUMN `change_type` ENUM('update','delete','create') DEFAULT NULL AFTER `target_itinerary_id`,
  ADD COLUMN `before_data` JSON DEFAULT NULL AFTER `change_type`,
  ADD COLUMN `after_data` JSON DEFAULT NULL AFTER `before_data`;

ALTER TABLE proposals
  ADD CONSTRAINT `proposals_ibfk_itinerary` FOREIGN KEY (`target_itinerary_id`) REFERENCES `itineraries` (`itinerary_id`) ON DELETE SET NULL;
