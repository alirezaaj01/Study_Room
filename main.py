"""
main.py
Entry point for the StudyRoom application.
Handles initialization, database setup, and UI execution.
"""

import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Import Data and UI components
from data.database import DatabaseManager
from ui.main_window import MainWindow

# تنظیمات لاگینگ برای عیب‌یابی
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """بررسی نسخه پایتون برای اطمینان از سازگاری."""
    if sys.version_info < (3, 11):
        logger.error("StudyRoom requires Python 3.11 or higher.")
        sys.exit(1)

def get_db_path() -> Path:
    """تعیین مسیر ذخیره‌سازی دیتابیس در پوشه User Home."""
    db_dir = Path.home() / ".studyroom"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "studyroom.db"

def load_stylesheet(app: QApplication):
    """بارگذاری فایل استایل‌شیت سراسری."""
    qss_path = Path("ui/theme.qss")
    if qss_path.exists():
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    else:
        logger.warning("theme.qss not found. Using default styles.")

def main():
    # ۱. بررسی پیش‌نیازها [cite: 242]
    check_environment()

    # ۲. تنظیمات High DPI برای نمایش صحیح در مانیتورهای مختلف [cite: 245]
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # ظاهر یکپارچه در سیستم‌عامل‌های مختلف [cite: 244]

    # ۳. راه‌اندازی دیتابیس و جداول [cite: 243, 246]
    db_path = get_db_path()
    try:
        DatabaseManager.init(db_path)
        logger.info(f"Database initialized at: {db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    # ۴. ایجاد پنجره اصلی و بارگذاری تم [cite: 248, 249]
    window = MainWindow()
    load_stylesheet(app)

    # ۵. نمایش برنامه و شروع حلقه رویدادها [cite: 251]
    window.show()
    
    logger.info("StudyRoom is running...")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()