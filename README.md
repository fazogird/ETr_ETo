# ETo va ETr: viloyat bo'yicha oylik hisob (ERA5-Land, ASCE standarti)

## Tez boshlash

**1.** [`run.py`](run.py) faylini oching va tepadagi 4 qatorni o'zgartiring:

```python
VILOYAT = "Fargona"
START = "2026-03-01"
END = "2026-09-30"
OUTPUT = r"D:\Cloud_comp\ET_natijalar"
```

**2.** Anaconda Prompt'da ishga tushiring:

```bat
conda activate gis_pro
cd /d D:\Cloud_comp\additional_task_claude_github\additional_tasks
python run.py
```

Faylni o'zgartirmasdan ham ishlatish mumkin:

```bat
python run.py --viloyat Samarqand --start 2026-06-01 --end 2026-08-31 --output D:\ET_samarqand
```

**Viloyat nomlari:** Andijon, Buxoro, Fargona, Jizzax, Xorazm, Namangan, Navoiy, Qashqadaryo,
Qoraqalpogiston, Samarqand, Sirdaryo, Surxondaryo, Toshkent viloyati, Toshkent shahri, **hammasi**.
`Farg'ona` va `Fergana` kabi yozilishlar ham qabul qilinadi.

**3.** Natija `OUTPUT` papkasida paydo bo'ladi:

| Fayl | Mazmuni |
|---|---|
| `Fargona_ETo_2026_03.tif` … | Oylik ETo rasteri: mm/oy, EPSG:4326, NoData = −9999, viloyat bo'yicha kesilgan |
| `Fargona_ETr_2026_03.tif` … | Oylik ETr (beda) rasteri: mm/oy |
| `Fargona_ETo_ETr_oylik.csv` | Viloyat bo'yicha har oy uchun o'rtacha ETo/ETr (mm, mm/kun), ETr/ETo nisbati va **JAMI** qatori. Excel'da ochiladi |
| `Fargona_hisobot.json`, `logs\` | Sifat nazorati va ishga tushirish tafsilotlari |

> `hammasi` tanlansa: butun respublika rasteri va CSV da 14 ta birlikning har biri uchun alohida qatorlar chiqadi.

**Birinchi ishga tushirish** ERA5-Land ma'lumotini CDS'dan yuklab oladi. Bunda vaqtning asosiy qismi CDS navbatiga ketadi.
- Faqat tanlangan viloyat hududi (0.2° zaxira bilan) yuklanadi.
- Keshda shu oy uchun kattaroq fayl bo'lsa (masalan, `hammasi` uchun yuklangan), u qayta ishlatiladi.
- Takroriy hisob **soniyalarda** bajariladi.

> **`data\cache\era5land\*.nc` — bu natija emas, xom kesh.** Unda soatlik ERA5-Land ma'lumotlari saqlanadi va uni ochish shart emas.
> QGIS'da har bir band bitta soatni bildiradi. Band nomidagi `valid_time` — 1970-01-01 dan beri o'tgan soniyalar (UTC).
> Masalan, `1772323200` = 2026-03-01 00:00 UTC (Toshkent vaqti bilan 05:00).

---

## Bir martalik sozlash (allaqachon qilingan)

- **Python muhiti:** `gis_pro`. Unga qo'shimcha ravishda `pip install pytest refet` qilingan.
- **CDS kaliti:** `D:\Cloud_comp\additional_task_claude_github\keys\cds.climate.copernicus.eu\` papkasida turadi. Yo'l [`config/settings.yaml`](config/settings.yaml) da (`cds.credentials`) ko'rsatilgan.
  - Kalit repoga tushmaydi: `keys/` va `.cdsapirc` `.gitignore` da.
  - Kalit logga ham chiqmaydi.
- **CDS litsenziyasi:** ERA5-Land sahifasida qabul qilingan.
- **Tarmoq:** kompyuter `cds.climate.copernicus.eu` va `www.geoboundaries.org` ga ulana olishi kerak.

## Qanday hisoblanadi (qisqacha)

1. **Ob-havo ma'lumoti:** ERA5-Land, soatlik, 0.1°. Soatlik qiymatlar Toshkent vaqti (UTC+5) bo'yicha kunlik Tmax, Tmin, Tdew, Rs va shamolga aylantiriladi.
2. **Hisob:** har bir piksel va har bir kun uchun ASCE standartlashtirilgan Penman-Monteith tenglamasi qo'llanadi:
   - **ETo** (o'tli sirt): Cn = 900, Cd = 0.34
   - **ETr** (beda sirti): Cn = 1600, Cd = 0.38
3. **Oylik qiymat:** kunlik qiymatlar yig'indisi.
4. **Viloyat o'rtachasi:** maydon bo'yicha vaznli. Pikselning viloyat ichidagi ulushi va cos(kenglik) hisobga olinadi, shuning uchun Toshkent shahri kabi kichik birliklar uchun ham to'g'ri chiqadi.
5. **Sifat nazorati:** fizik chegaralar tekshiriladi, ≤ 3 kunlik bo'shliqlar to'ldiriladi, oyda kamida 90% kun bo'lishi talab qilinadi.

Batafsil: [`docs/formulalar.md`](docs/formulalar.md) (barcha formulalar) va [`docs/usullar.md`](docs/usullar.md) (metodologiya).

## Testlar

```bat
python -m pytest
```

Testlar quyidagilarni tekshiradi:
- FAO-56 misollari
- RefET validatsiyasi
- RefET bilan tasodifiy solishtirish: farq 10⁻⁹ mm dan kichik
- sintetik ERA5-Land ma'lumotidan GeoTIFF va CSV gacha to'liq zanjir

## Kengaytirilgan buyruqlar

```bat
python -m et_reference check                          :: kalit, chegaralar va CDS so'rovlar rejasi
python -m et_reference run --viloyat Fargona --skip-download   :: faqat keshdan, internetsiz
```

Agar CDS so'rovni hajmi katta deb rad etsa, `config/settings.yaml` da `cds.split_by_variable: true` qiling.

---

## Zonal statistika: ekin dalalari bo'yicha ETr/ETo (shp + Excel)

Tayyor oylik rasterlar (`Fargona_ETr_2026_03.tif` ...) va ekin dalalari shp'idan har bir dala uchun mm → m³ → m³/ga hisoblaydi.

**1.** [`run_zonal.py`](run_zonal.py) ning tepasidagi yo'llarni yozing:

```python
SHP_PATH = r"D:\dalalar\fargona_ekin.shp"
RASTER_PATH = r"D:\Cloud_comp\additional_task_claude_github\outputs"   # <Viloyat>_ETr_<yil>_<oy>.tif / ..._ETo_... lar shu yerda
OUTPUT_PATH = r"D:\Cloud_comp\additional_task_claude_github\hisobot"
CROP_COLUMN = "turi"   # ekin turi ustuni; boshqa nom yozish yoki None qilish mumkin
```

**2.** `python run_zonal.py`

Natija `OUTPUT_PATH\<Viloyat>\` ichida (viloyat nomi raster fayl nomidan olinadi):

| Fayl | Mazmuni |
|---|---|
| `<Viloyat>_ET_zonal.shp` | Asl shp (CRS i o'zgarmaydi) + har oy uchun `ETr3_mm`, `ETr3_m3`, `ETr3_m3ha` (ETo ham), mavsum yig'indisi `ETr_mm`, `ETr_m3`, `ETr_m3ha`, `area_ga`, `ET_QC` |
| `<Viloyat>_ET_hisobot.xlsx` | `ETr`, `ETo`: oylar va **JAMI** bo'yicha dalalar soni, maydon (ga), m³, mm, m³/ga. `ETr_tur`, `ETo_tur`: ekin turi bo'yicha (CROP_COLUMN bo'lsa). `Sifat`: CRS, maydon, NoData holatlari |

**Qanday ishlaydi**
- **CRS:** raster o'zgarmaydi; shp rasterning CRS iga o'tkaziladi (qayta namunalash qiymatni buzmaydi).
- **Zonal:** dala ichidagi piksellar bo'yicha, dalaning har pikselga tushgan **yuza ulushi** bilan vaznli o'rtacha mm.
- **Maydon:** shp'dagi tayyor ustun ishlatilmaydi (CRS i noma'lum). Maydon teng-maydonli **EPSG:6933** da hisoblanadi, shuning uchun viloyatga qarab zona tanlash shart emas. `AREA_CRS = "utm"` yoki aniq EPSG ham berish mumkin. Tayyor ustun bo'lsa, `Sifat` varag'ida birligi (ga yoki m²) aniqlanadi.
- **O'tkazish:** `m³ = mm/1000 × maydon(m²)`, `m³/ga = m³ / maydon(ga)` (= mm × 10).
- **Excel o'rtachasi:** mm va m³/ga = jami m³ / hisobga olingan dalalar maydoni (maydon bo'yicha vaznli).
- **NoData:** dala to'liq NoData'ga tushsa, 2 piksel ichidagi eng yaqin yaroqli piksel olinadi, aks holda qiymat `-9999`. Holat `ET_QC` da: 0 to'liq yaroqli, 1 qisman NoData, 2 to'ldirilgan, 3 qiymat yo'q.
- Shp ustun nomlari 10 belgigacha (DBF limiti); mavsum yig'indisi biror oy yetishmasa `-9999`.
