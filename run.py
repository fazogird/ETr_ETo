"""ETo va ETr: viloyat uchun oylik hisob.

FOYDALANISH
    1) Pastdagi 4 ta qatorni o'zgartiring.
    2) Anaconda Prompt'da:
           conda activate gis_pro
           cd /d D:\\Cloud_comp\\additional_task_claude_github\\additional_tasks
           python run.py

    Yoki fayl ichini o'zgartirmasdan:
           python run.py --viloyat Fargona --start 2026-03-01 --end 2026-09-30 --output D:\\ET_natijalar

VILOYAT NOMLARI
    Andijon, Buxoro, Fargona, Jizzax, Xorazm, Namangan, Navoiy, Qashqadaryo, Qoraqalpogiston,
    Samarqand, Sirdaryo, Surxondaryo, Toshkent viloyati, Toshkent shahri, hammasi

NATIJA (OUTPUT papkasida)
    Fargona_ETo_2026_03.tif ...      oylik ETo rasteri, mm/oy (EPSG:4326)
    Fargona_ETr_2026_03.tif ...      oylik ETr rasteri, mm/oy
    Fargona_ETo_ETr_oylik.csv        viloyat bo'yicha oylik o'rtacha va JAMI (Excel'da ochiladi)
"""

# ============================ SOZLAMALAR ============================
VILOYAT = "Fargona"
START = "2026-03-01"
END = "2026-09-30"
OUTPUT = r"D:\Cloud_comp\ET_natijalar"
# ====================================================================

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))  # paket o'rnatilmagan bo'lsa ham ishlaydi

from et_reference.cli import run_command  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ETo va ETr: viloyat uchun oylik hisob")
    parser.add_argument("--viloyat", default=VILOYAT)
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    return run_command(
        config=ROOT / "config" / "settings.yaml",
        start=args.start,
        end=args.end,
        viloyat=args.viloyat,
        output=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
