import argparse
import json
import logging
import os
import sys
from pathlib import Path

from intersect_sdk import (
    IntersectService,
    IntersectServiceConfig,
    default_intersect_lifecycle_loop,
)

from chess_data_service.service import ChessDataEgressCapability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CHESS Data Egress INTERSECT Service")
    parser.add_argument(
        "--config",
        type=Path,
        default=os.environ.get(
            "CHESS_DATA_SERVICE_CONFIG_FILE",
            Path(__file__).parents[1] / "local-conf.json",
        ),
    )
    args = parser.parse_args()

    try:
        with Path(args.config).open("rb") as f:
            from_config_file = json.load(f)
    except (json.decoder.JSONDecodeError, OSError) as e:
        logger.critical("Unable to load config file: %s", str(e))
        sys.exit(1)

    config = IntersectServiceConfig(
        hierarchy=from_config_file["intersect-hierarchy"],
        **from_config_file["intersect"],
    )

    capability = ChessDataEgressCapability()
    service = IntersectService([capability], config)

    default_intersect_lifecycle_loop(service)
