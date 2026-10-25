ALTER TABLE trip_members
    MODIFY COLUMN join_status ENUM('invited','requested','accepted','rejected','left','removed') NOT NULL DEFAULT 'invited';
