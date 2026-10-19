-- 提案狀態加入「已取消」，對應五(八)景點提案功能規格中的 6 種狀態。
ALTER TABLE proposals
  MODIFY `status` ENUM('discussing','voting','approved','rejected','added','cancelled') NOT NULL DEFAULT 'discussing';
