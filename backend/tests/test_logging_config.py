import logging
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.logging import NOISY_LOGGERS, configure_logging


class LoggingConfigTest(unittest.TestCase):
    def tearDown(self):
        logging.getLogger().handlers.clear()

    def test_configure_logging_clamps_noisy_libraries(self):
        configure_logging("INFO", json_logs=False)

        self.assertEqual(logging.getLogger().level, logging.INFO)
        for logger_name, expected_level in NOISY_LOGGERS.items():
            self.assertEqual(logging.getLogger(logger_name).level, expected_level)


if __name__ == "__main__":
    unittest.main()
