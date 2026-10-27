CREATE DATABASE IF NOT EXISTS campus_lost_found
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE campus_lost_found;

CREATE TABLE IF NOT EXISTS users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(100) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('student','admin') NOT NULL DEFAULT 'student',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
  category_id INT AUTO_INCREMENT PRIMARY KEY,
  category_name VARCHAR(60) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS locations (
  location_id INT AUTO_INCREMENT PRIMARY KEY,
  location_name VARCHAR(100) NOT NULL UNIQUE,
  building VARCHAR(100) NULL
);

CREATE TABLE IF NOT EXISTS item_reports (
  report_id INT AUTO_INCREMENT PRIMARY KEY,
  reporter_id INT NOT NULL,
  category_id INT NOT NULL,
  location_id INT NOT NULL,
  report_type ENUM('lost','found') NOT NULL,
  item_name VARCHAR(120) NOT NULL,
  description TEXT NOT NULL,
  event_date DATE NOT NULL,
  contact_note VARCHAR(255) NULL,
  image_url VARCHAR(500) NULL,
  status ENUM('open','matched','claimed','returned','closed') NOT NULL DEFAULT 'open',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_report_user FOREIGN KEY (reporter_id) REFERENCES users(user_id),
  CONSTRAINT fk_report_category FOREIGN KEY (category_id) REFERENCES categories(category_id),
  CONSTRAINT fk_report_location FOREIGN KEY (location_id) REFERENCES locations(location_id),
  INDEX idx_report_search (report_type, status, category_id, event_date),
  INDEX idx_report_location (location_id, event_date)
);

CREATE TABLE IF NOT EXISTS matches (
  match_id INT AUTO_INCREMENT PRIMARY KEY,
  lost_report_id INT NOT NULL,
  found_report_id INT NOT NULL,
  match_score DECIMAL(5,2) NOT NULL DEFAULT 0,
  match_reason VARCHAR(255) NOT NULL,
  status ENUM('suggested','confirmed','dismissed') NOT NULL DEFAULT 'suggested',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_match_lost FOREIGN KEY (lost_report_id) REFERENCES item_reports(report_id),
  CONSTRAINT fk_match_found FOREIGN KEY (found_report_id) REFERENCES item_reports(report_id),
  CONSTRAINT uq_match_pair UNIQUE (lost_report_id, found_report_id),
  CONSTRAINT chk_match_score CHECK (match_score >= 0 AND match_score <= 100),
  CHECK (lost_report_id <> found_report_id)
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id INT AUTO_INCREMENT PRIMARY KEY,
  report_id INT NOT NULL,
  claimant_id INT NOT NULL,
  ownership_details TEXT NOT NULL,
  evidence_note VARCHAR(500) NULL,
  status ENUM('pending','approved','rejected','withdrawn') NOT NULL DEFAULT 'pending',
  reviewed_by INT NULL,
  review_reason VARCHAR(500) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at DATETIME NULL,
  CONSTRAINT fk_claim_report FOREIGN KEY (report_id) REFERENCES item_reports(report_id),
  CONSTRAINT fk_claim_user FOREIGN KEY (claimant_id) REFERENCES users(user_id),
  CONSTRAINT fk_claim_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(user_id),
  INDEX idx_claim_status (status, created_at)
);

CREATE TABLE IF NOT EXISTS claim_history (
  history_id INT AUTO_INCREMENT PRIMARY KEY,
  claim_id INT NOT NULL,
  changed_by INT NOT NULL,
  old_status VARCHAR(20) NULL,
  new_status VARCHAR(20) NOT NULL,
  reason VARCHAR(500) NULL,
  changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_history_claim FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
  CONSTRAINT fk_history_user FOREIGN KEY (changed_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS handovers (
  handover_id INT AUTO_INCREMENT PRIMARY KEY,
  report_id INT NOT NULL UNIQUE,
  claim_id INT NOT NULL UNIQUE,
  handed_over_by INT NOT NULL,
  received_by INT NOT NULL,
  handover_note VARCHAR(500) NULL,
  handed_over_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_handover_report FOREIGN KEY (report_id) REFERENCES item_reports(report_id),
  CONSTRAINT fk_handover_claim FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
  CONSTRAINT fk_handover_admin FOREIGN KEY (handed_over_by) REFERENCES users(user_id),
  CONSTRAINT fk_handover_receiver FOREIGN KEY (received_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS disputes (
  dispute_id INT AUTO_INCREMENT PRIMARY KEY,
  report_id INT NOT NULL,
  opened_by INT NOT NULL,
  description TEXT NOT NULL,
  status ENUM('open','investigating','resolved','dismissed') NOT NULL DEFAULT 'open',
  resolution VARCHAR(500) NULL,
  resolved_by INT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at DATETIME NULL,
  CONSTRAINT fk_dispute_report FOREIGN KEY (report_id) REFERENCES item_reports(report_id),
  CONSTRAINT fk_dispute_user FOREIGN KEY (opened_by) REFERENCES users(user_id),
  CONSTRAINT fk_dispute_admin FOREIGN KEY (resolved_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS notifications (
  notification_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(120) NOT NULL,
  message VARCHAR(500) NOT NULL,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_notification_user FOREIGN KEY (user_id) REFERENCES users(user_id),
  INDEX idx_notifications_user (user_id, is_read, created_at)
);

CREATE TABLE IF NOT EXISTS audit_logs (
  audit_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  actor_id INT NULL,
  action VARCHAR(100) NOT NULL,
  entity_type VARCHAR(50) NOT NULL,
  entity_id INT NULL,
  details JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_audit_actor FOREIGN KEY (actor_id) REFERENCES users(user_id),
  INDEX idx_audit_entity (entity_type, entity_id, created_at)
);

INSERT IGNORE INTO categories(category_name) VALUES
 ('ID Card'),('Wallet'),('Electronics'),('Books & Notes'),('Keys'),
 ('Bag'),('Bottle'),('Clothing'),('Other');

INSERT IGNORE INTO locations(location_name, building) VALUES
 ('Central Library','Library'),('Main Canteen','Student Centre'),
 ('Computer Lab 1','Academic Block'),('Sports Ground','Sports Complex'),
 ('Main Auditorium','Auditorium'),('Parking Area','Campus'),('Hostel Reception','Hostels'),
 ('Other / Not Sure','Campus');


-- Useful views for demonstrations and reporting.
CREATE OR REPLACE VIEW v_open_reports AS
SELECT r.report_id, r.report_type, r.item_name, r.description, r.event_date,
       r.status, c.category_name, l.location_name, u.full_name AS reporter_name
FROM item_reports r
JOIN categories c ON c.category_id = r.category_id
JOIN locations l ON l.location_id = r.location_id
JOIN users u ON u.user_id = r.reporter_id
WHERE r.status IN ('open','matched','claimed');

CREATE OR REPLACE VIEW v_pending_claims AS
SELECT cl.claim_id, cl.report_id, r.item_name, u.full_name AS claimant_name,
       u.email AS claimant_email, cl.ownership_details, cl.evidence_note, cl.created_at
FROM claims cl
JOIN item_reports r ON r.report_id = cl.report_id
JOIN users u ON u.user_id = cl.claimant_id
WHERE cl.status = 'pending';

CREATE OR REPLACE VIEW v_recovery_summary AS
SELECT c.category_name, COUNT(DISTINCT r.report_id) AS reports_total,
       COUNT(DISTINCT h.handover_id) AS items_recovered
FROM categories c
LEFT JOIN item_reports r ON r.category_id = c.category_id
LEFT JOIN handovers h ON h.report_id = r.report_id
GROUP BY c.category_id, c.category_name;

-- Automatically preserve claim status history in the same transaction.
DROP TRIGGER IF EXISTS trg_claim_status_history;
DELIMITER $$
CREATE TRIGGER trg_claim_status_history
AFTER UPDATE ON claims
FOR EACH ROW
BEGIN
  IF OLD.status <> NEW.status THEN
    INSERT INTO claim_history(claim_id, changed_by, old_status, new_status, reason)
    VALUES(NEW.claim_id, COALESCE(NEW.reviewed_by, NEW.claimant_id), OLD.status, NEW.status, NEW.review_reason);
  END IF;
END$$
DELIMITER ;

-- Demonstration procedure for grouped report statistics.
DROP PROCEDURE IF EXISTS sp_report_counts_by_category;
DELIMITER $$
CREATE PROCEDURE sp_report_counts_by_category()
BEGIN
  SELECT c.category_name, COUNT(r.report_id) AS report_count,
         SUM(r.report_type = 'lost') AS lost_count,
         SUM(r.report_type = 'found') AS found_count
  FROM categories c
  LEFT JOIN item_reports r ON r.category_id = c.category_id
  GROUP BY c.category_id, c.category_name
  ORDER BY report_count DESC, c.category_name;
END$$
DELIMITER ;
