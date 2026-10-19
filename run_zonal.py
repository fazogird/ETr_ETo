"""ETr/ETo rasterlari bo'yicha ekin dalalari uchun zonal statistika: shp ustunlari + Excel hisobot.

FOYDALANISH
    1) Pastdagi 3 ta yo'lni (va kerak bo'lsa ekin ustuni nomini) o'zgartiring.
    2) Anaconda Prompt'da:
           conda activate gis_pro
           cd /d D:\\Cloud_comp\\additional_task_claude_github\\additional_tasks
           python run_zonal.py

    Yoki fayl ichini o'zgartirmasdan:
           python run_zonal.py --shp D:\\dalalar\\fargona.shp --raster D:\\...\\outputs --output D:\\...\\hisobot

NATIJA (OUTPUT_PATH\\<Viloyat>\\ papkasida; viloyat nomi raster fayl nomidan olinadi)
    <Viloyat>_ET_zonal.shp      asl shp + har oy uchun ETr3_mm, ETr3_m3, ETr3_m3ha (ETo ham), mavsum
                                yig'indisi (ETr_mm ...), area_ga va ET_QC (sifat kodi)
    <Viloyat>_ET_hisobot.xlsx   ETr, ETo jamlamasi; (CROP_COLUMN bo'lsa) tur bo'yicha varaqlar; sifat nazorati
"""

# ============================ SOZLAMALAR ============================
SHP_PATH = r""
RASTER_PATH = r""     # viloyat rasterlari (Fargona_ETr_2026_03.tif ...) turgan papka
OUTPUT_PATH = r""

CROP_COLUMN = "turi"  # shp'dagi ekin turi ustuni. Boshqa ustun bo'lsa nomini yozing; kerak bo'lmasa None
AREA_CRS = "auto"     # "auto" (EPSG:6933, teng-maydonli), "utm" yoki aniq EPSG, masalan "EPSG:32642"
VILOYAT = None        # RASTER_PATH ichida bir nechta viloyat bo'lsagina kerak, masalan "Fargona"
# ====================================================================

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))  # paket o'rnatilmagan bo'lsa ham ishlaydi

from et_reference.zonal_report.pipeline import run  # noqa: E402
from et_reference.zonal_report.settings import ZonalSettings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ETr/ETo zonal statistika: shp + Excel")
    parser.add_argument("--shp", default=SHP_PATH)
    parser.add_argument("--raster", default=RASTER_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--crop-column", default=CROP_COLUMN)
    parser.add_argument("--area-crs", default=AREA_CRS)
    parser.add_argument("--viloyat", default=VILOYAT)
    args = parser.parse_args()

    missing = [name for name, value in (("SHP_PATH", args.shp), ("RASTER_PATH", args.raster),
                                        ("OUTPUT_PATH", args.output)) if not value]
    if missing:
        print(f"Quyidagi yo'l(lar) kiritilmagan: {', '.join(missing)} (run_zonal.py tepasida yoki --shp/--raster/--output)",
              file=sys.stderr)
        return 2

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    settings = ZonalSettings(
        shp_path=args.shp, raster_path=args.raster, output_path=args.output,
        crop_column=args.crop_column or None, area_crs=args.area_crs, viloyat=args.viloyat,
    )
    try:
        outputs = run(settings)
    except (ValueError, OSError) as exc:  # foydalanuvchi xatolari: yo'l, CRS, ustun, ruxsat (Excel ochiq)
        logging.getLogger("et_reference").error("%s", exc)
        return 1
    print(f"\nShp  : {outputs.shapefile}\nExcel: {outputs.excel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
