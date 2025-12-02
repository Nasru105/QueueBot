"""
Конфигурация для pytest.
"""

import sys
from pathlib import Path

# Добавляем корневую папку проекта в sys.path
root_path = Path(__file__).parent.parent
sys.path.insert(0, str(root_path))
