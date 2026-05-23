from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.sync import sync_assets_from_seed
from src.db.connection import db_session, ensure_database_dir, get_database_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从 config/assets.seed.yaml 初始化同步 ETF 标的池到 etf_universe"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使数据库中标的已停用，也使用种子文件覆盖同步",
    )
    args = parser.parse_args()

    db_path = ensure_database_dir(get_database_path())
    with db_session(db_path) as conn:
        stats = sync_assets_from_seed(conn, force=args.force)

    logger.info(
        "已从 assets.seed.yaml 同步 {} 个标的，跳过 {} 个已停用标的",
        stats["imported"],
        stats["skipped"],
    )


if __name__ == "__main__":
    main()
