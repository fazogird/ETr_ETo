# et-reference: oylik ETo va ETr rasterlari (ERA5-Land, ASCE standarti)

Berilgan davr uchun **har oylik etalon bug'lanish** rasterlarini hisoblaydi:
- **ETo** — o't bo'yicha etalon ET
- **ETr** — beda bo'yicha etalon ET

Hisob usuli — ASCE-EWRI (2005) standartlashtirilgan Penman-Monteith tenglamasi, kunlik qadamda.

| | |
|---|---|
| Ob-havo ma'lumoti | ERA5-Land, soatlik, 0.1° (Copernicus CDS). GEE kerak emas |
| Hudud | O'zbekiston, geoBoundaries ADM1 |
| Mahalliy kun | Asia/Tashkent (UTC+5) |
| Natija | Har oy uchun alohida GeoTIFF: EPSG:4326, mm/oy, NoData = −9999 |

Formulalar: [`docs/formulalar.md`](docs/formulalar.md). Metodologiya: [`docs/usullar.md`](docs/usullar.md).

---

## 1. O'rnatish (Windows)

```bat
cd /d D:\Cloud_comp\additional_task_claude_github
git clone https://github.com/fazogird/additional_tasks.git
cd additional_tasks
git checkout claude/intelligent-noether-yl28x8

conda env create -f environment.yml
conda activate et-reference
```

> `conda` (conda-forge) GDAL/rasterio ni Windows da eng ishonchli o'rnatadi.

**Conda serverlariga ulanib bo'lmasa** (`CondaHTTPError: HTTP 000 CONNECTION FAILED`), pip bilan o'rnating.
Barcha kutubxonalarning (rasterio, geopandas, netCDF4) PyPI da Windows uchun tayyor paketlari bor:

```bat
cd /d D:\Cloud_comp\additional_task_claude_github\additional_tasks
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Keyingi safar faqat `.venv\Scripts\activate` buyrug'ini berish yetarli.

## 2. CDS API kaliti: qayerda va qanday saqlanadi

**Asosiy tamoyil:** kod kalitning *qayerda turganini* biladi, kalitning *o'zini* esa hech qachon ko'rmaydi va saqlamaydi.

Buni uy kaliti bilan solishtirish mumkin. Biz eshikka "kalit shu tortmada" degan yozuvni osib qo'yamiz, kalitni esa eshikka ilib qo'ymaymiz.

1. CDS saytida ERA5-Land sahifasini oching: https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land. **Download** bo'limida litsenziya shartlarini **qabul qiling**. Aks holda so'rov "required licences not accepted" xatosi bilan rad etiladi.
2. Kalit papkasida `.cdsapirc` nomli matn fayl yarating:
   ```
   D:\Cloud_comp\additional_task_claude_github\keys\cds.climate.copernicus.eu\.cdsapirc
   ```
   Fayl mazmuni (tokenni CDS profil sahifangizdan oling):
   ```
   url: https://cds.climate.copernicus.eu/api
   key: <SIZNING-TOKENINGIZ>
   ```
   Papkada bitta fayl bo'lsa, uning nomi boshqacha bo'lishi ham mumkin. Faqat token yozilgan bitta qatorli fayl ham qabul qilinadi.
3. Yo'l [`config/settings.yaml`](config/settings.yaml) da allaqachon ko'rsatilgan (`cds.credentials`). Kod papkani o'zi tekshirib, faylni topadi.
4. **Himoya choralari:**
   - `.gitignore` faylida `keys/` va `.cdsapirc` bor, ular commit qilinmaydi. Har commitdan oldin `git status` bilan tekshiring.
   - Kalit log, xato xabari yoki `repr` da chiqmaydi (testlar bilan tekshirilgan).
   - Muqobil yo'l: `CDSAPI_RC` muhit o'zgaruvchisi yoki `%USERPROFILE%\.cdsapirc`.

## 3. Tarmoq

Kompyuteringizdan quyidagi manzillarga ulanish kerak:
- `cds.climate.copernicus.eu` — ERA5-Land
- `www.geoboundaries.org` va `github.com` (`media.githubusercontent.com`) — ADM1 chegaralari

## 4. Ishga tushirish

```bat
:: 1) Tekshirish: sozlamalar, kalit (faqat "topildi" deydi), CDS so'rovlar rejasi
python -m et_reference check

:: 2) To'liq hisob: yuklash → QC → ETo/ETr → GeoTIFF
python -m et_reference run

:: Faqat keshdagi ma'lumot bilan (internetsiz qayta hisoblash)
python -m et_reference run --skip-download

:: Boshqa davr
python -m et_reference run --start 2026-05-01 --end 2026-07-31
```

Yuklangan fayllar `data\cache\` ga tushadi va qayta yuklanmaydi. Birinchi ishga tushirishda vaqtning asosiy qismi CDS navbatiga ketadi. Hisobning o'zi soniyalarda bajariladi.

> CDS so'rovni hajmi katta deb rad etsa, `settings.yaml` da `cds.split_by_variable: true` qiling.

## 5. Natijalar

```
outputs\
├── rasters\
│   ├── ETo_2026_03.tif … ETo_2026_09.tif       mm/oy, float32
│   ├── ETr_2026_03.tif … ETr_2026_09.tif       mm/oy, float32
│   └── valid_days_2026_03.tif …                asl (to'ldirilmagan) ma'lumotli kunlar soni
├── run_summary.json                             davr, tarmoq, QC hisoboti, oylik o'rtachalar
└── logs\run_YYYYMMDD-HHMMSS.log
```

Har bir rasterning metama'lumotida quyidagilar yozilgan: birlik, oy, oydagi kunlar soni, usul (Cn/Cd), manba va vaqt zonasi.

**Viloyatlar bo'yicha shp ga yozishda:**
- 0.1° piksel taxminan 93 km². Toshkent shahri kabi kichik birliklar uchun **qoplanish ulushi bo'yicha vaznli** zonal statistikadan foydalaning (`exactextract` yoki `rasterstats` + `all_touched`).
- Maydon hisoblash kerak bo'lsa, teng maydonli proyeksiyaga o'ting (masalan, EPSG:6933).

## 6. Loyiha tuzilmasi

```
src/et_reference/
├── config.py, credentials.py, timeutils.py
├── ingestion/        era5land.py (CDS so'rovlari, kesh), archive.py (NetCDF o'qish), boundaries.py
├── preprocessing/    accumulation.py (ssrd de-akkumulyatsiyasi), daily.py (UTC → UTC+5 kunlik), quality.py (QC, bo'shliqlar)
├── calculations/     atmosphere.py, radiation.py, wind.py, reference_et.py (ASCE ETsz: ETo/ETr)
├── aggregation/      temporal.py (oylik yig'indi, ≥90% kun qoidasi)
├── output/           rasters.py (EPSG:4326 GeoTIFF, hudud niqobi)
├── pipeline.py       orkestrator
└── cli.py            check | run
```

## 7. Testlar

```bat
python -m pytest
```

Testlar quyidagilarni tekshiradi:
- FAO-56 misollari: 18-misolda ETo = 3.9 mm/kun.
- RefET validatsiyasi (Fallon, NV): ETr = 10.626 mm/kun.
- RefET bilan 5000 ta tasodifiy holatda solishtirish: farq 10⁻⁹ mm dan kichik.
- To'liq zanjir (end-to-end): sintetik ERA5-Land fayllaridan GeoTIFF gacha, natija RefET bilan mustaqil tekshiriladi.
