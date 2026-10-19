# Usullar: ETo va ETr hisoblash metodologiyasi

> Bu hujjat ikki savolga javob beradi:
> 1. Yuklangan kutubxonalar (`pyet`, `RefET`) **qanday usullar** bilan hisoblaydi?
> 2. Biz O'zbekiston viloyatlari uchun 2026-yil mart–sentabr oylik ETo/ETr rasterlarini **qaysi usul bilan va qanday** hisoblaymiz?
>
> Barcha formulalarning to'liq yozuvi [`formulalar.md`](formulalar.md) da.

---

## 0. Qisqacha (TL;DR)

- **Usul:** ASCE standartlashtirilgan Penman-Monteith tenglamasi, **kunlik** qadam, `method="asce"` (ASCE-EWRI 2005).
  - **ETo** (o't): Cn = 900, Cd = 0.34
  - **ETr** (beda): Cn = 1600, Cd = 0.38
- **Ma'lumot:** ERA5-Land (ECMWF reanalizi), 0.1° (~9–11 km), soatlik ma'lumot → mahalliy vaqt (UTC+5) bo'yicha kunlik.
- **Hisob tartibi:** har bir piksel uchun kunlik ETo/ETr hisoblanadi. Keyin oylik yig'indi olinadi (mm/oy).
- **Natija:** oylik GeoTIFF rasterlar, EPSG:4326, NoData = −9999. Viloyatlar bo'yicha zonal statistika (shp) lokalda qilinadi.
- **Ishonchlilik:** formulalar FAO-56 va RefET validatsiya qiymatlari bilan unit-testdan o'tkaziladi. `refet` va `pyet` "hakam" (oracle) sifatida ishlatiladi.

---

## 1. Manbalar

| Manba | Versiya | Nima beradi |
|---|---|---|
| `pyet-master.zip` | v1.4.0 (`master`) | 20 ga yaqin PET usuli; pandas (1D) va xarray (3D) bilan ishlaydi |
| `pyet-v1.3.1.zip` | v1.3.1 | Formulalar `master` bilan **bir xil**. Farq faqat importlar tartibida va README dagi maqola havolasida |
| `RefET-main.zip` | `main` | ASCE standartining rasmiy NumPy talqini: kunlik va soatlik ETo/ETr. Ref-ET v4.2 dasturi bilan validatsiya qilingan |

> `E:\My_projects\ET\ETr` papkasidagi qo'shimcha hujjatlar (masalan, PDF lar) yuklanmagan. Shu sababli bu hujjat faqat yuqoridagi uchta arxivga va ular keltirgan standartlarga asoslanadi.

---

## 2. ETo va ETr: farqi nimada? (Feynman usulida)

Atmosferani **chanqoq** deb tasavvur qiling. Uning qanchalik chanqaganini o'lchash uchun shartli "standart stakan" kerak.
Bu stakan har doim suvga to'la, doim yashil va bir xil balandlikdagi o'simlik bilan qoplangan maydon:

| | ETo | ETr |
|---|---|---|
| Etalon sirt | Qirqilgan o't, h = 0.12 m | Beda (alfalfa), h = 0.50 m |
| Sirt qarshiligi (kunlik) | ~70 s m⁻¹ | ~45 s m⁻¹ |
| Standart | FAO-56 va ASCE "short" | ASCE "tall" |
| Tenglamadagi Cn / Cd | 900 / 0.34 | 1600 / 0.38 |

Beda baland va "g'adir-budur". U shamolni ko'proq "ushlaydi", ya'ni aerodinamik bog'lanishi kuchli.
Natijada **quruq va shamolli iqlimda** ETr ETo dan sezilarli katta chiqadi. Tekshiruvimizda arid Fallon (Nevada, AQSh) stansiyasining 2015-07-01 kuni uchun **ETr/ETo = 10.626/7.998 = 1.33** bo'ldi.

Formula bitta: Cn ikkinchi (aerodinamik) hadni kuchaytiradi, Cd esa maxrajni. Ikkalasi birgalikda beda uchun "qurg'oqchilikka sezgirlikni" oshiradi.

---

## 3. RefET kutubxonasi qanday hisoblaydi

### 3.1 Kunlik algoritm (`refet.Daily`)

Kirish ma'lumotlari:
- tmin, tmax [°C]
- rs [MJ m⁻² d⁻¹]
- uz [m s⁻¹] va zw [m]
- elev [m], lat [°], doy
- ea [kPa] **yoki** tdew [°C]

Hisob ketma-ketligi:
1. Birliklar konvertatsiya qilinadi (`input_units` orqali: °F, K, Langley, W m⁻², mph, ft).
2. Agar ea berilmagan bo'lsa, ea = e°(Tdew).
3. T = (Tmax + Tmin)/2 olinadi.
4. P **balandlikdan** hisoblanadi (standart shakl), keyin γ = 0.000665·P.
5. Δ(T); es = [e°(Tmax) + e°(Tmin)]/2; VPD = max(es − ea, 0).
6. Ra (kenglik, DOY) va Rso (`asce` → soddalashtirilgan; `refet` → to'liq, D ilovasi).
7. fcd = 1.35·clip(Rs/Rso, 0.3, 1) − 0.35 → Rnl → Rn = 0.77·Rs − Rnl; G = 0.
8. u₂ = uz·4.87/ln(67.8·zw − 5.42).
9. ETsz hisoblanadi: `.eto()` (900/0.34) yoki `.etr()` (1600/0.38).

### 3.2 `method="asce"` va `method="refet"` farqi

| Qadam | `asce` (standart tenglamalar) | `refet` (Ref-ET dasturiga moslik) |
|---|---|---|
| Bosim daraja ko'rsatkichi | 5.26 | 9.8/(0.0065·286.9) ≈ 5.255 |
| Δ koeffitsiyenti | 2503 | 4098·0.6108 |
| Quyosh og'ishi δ | 0.409·sin(2πJ/365 − 1.39) | 23.45°·sin(2π(284 + J)/365) |
| G_sc | 4.92 MJ m⁻² h⁻¹ | 1367·0.0036 = 4.9212 |
| Rso | soddalashtirilgan: (0.75 + 2·10⁻⁵·z)·Ra | to'liq (D ilovasi: K_B, K_D, W) |

Fallon misolida farq:

| Usul | Rso | fcd | ETo | ETr |
|---|---|---|---|---|
| `asce` | 32.243 | 0.8316 | 7.998 | 10.626 |
| `refet` | 31.566 | 0.8570 | 7.942 | 10.571 |

Farq ~0.5–0.7% va asosan Rso modelidan kelib chiqadi.

### 3.3 Soatlik algoritm (`refet.Hourly`)

Kunlikdan farqlari:
- Cn/Cd va G kunduz/tunga qarab o'zgaradi (`formulalar.md`, 1-bo'lim).
- Ra quyosh vaqti va soat burchagi orqali hisoblanadi.
- es = e°(T_soatlik).
- Quyosh past turganda (β < 0.3 rad) fcd = 1 qilib qotiriladi (soddalashtirish).

### 3.4 RefET cheklovlari (o'z README sidan)

- Turli shakldagi massivlar (2D/3D) uchun broadcasting **sinovdan o'tmagan**.
- Fayl o'qish/yozish, QA/QC va bo'shliqlarni to'ldirish foydalanuvchining zimmasida.

---

## 4. pyet kutubxonasi qanday hisoblaydi

### 4.1 Usullar tasnifi va kerakli kirishlar

T — harorat, RH — namlik, R — radiatsiya, u₂ — shamol, φ — kenglik, z — balandlik.

| Guruh | Usul | Funksiya | T | RH | R | u₂ | φ | z |
|---|---|---|---|---|---|---|---|---|
| Kombinatsion | Penman | `penman` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| | Penman-Monteith (umumiy, LAI/CO₂) | `pm` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| | **ASCE-PM (ETo / ETr)** | `pm_asce` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| | **FAO-56 PM (ETo)** | `pm_fao56` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| | Priestley-Taylor | `priestley_taylor` | ✔ | ✔ | ✔ | – | ✔ | ✔ |
| | Kimberly-Penman | `kimberly_penman` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| | Thom-Oliver | `thom_oliver` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Harorat | Blaney-Criddle | `blaney_criddle` | ✔ | (m=2) | – | (m=2) | ✔ | – |
| | Hamon | `hamon` | ✔ | – | – | – | ✔ | – |
| | Romanenko | `romanenko` | ✔ | ✔ | – | – | – | – |
| | Linacre | `linacre` | ✔ | – | – | – | ✔ | ✔ |
| | Haude | `haude` | ✔ | ✔ | – | – | – | – |
| Radiatsiya | Turc | `turc` | ✔ | ✔ | ✔ | – | – | – |
| | Jensen-Haise | `jensen_haise` | ✔ | – | ✔ | – | (m=1) | – |
| | McGuinness-Bordne | `mcguinness_bordne` | ✔ | – | – | – | ✔ | – |
| | Hargreaves | `hargreaves` | ✔ | – | – | – | ✔ | – |
| | FAO-24 radiatsion | `fao_24` | ✔ | ✔ | ✔ | ✔ | – | ✔ |
| | Abtew | `abtew` | ✔ | – | ✔ | – | – | – |
| | Makkink (+ KNMI) | `makkink`, `makkink_knmi` | ✔ | – | ✔ | – | – | ✔ |
| | Oudin | `oudin` | ✔ | – | – | – | ✔ | – |

`calculate_all()` funksiyasi barcha usullarni bitta jadvalda hisoblaydi. Bu taqqoslash uchun qulay.

### 4.2 pyet konvensiyalari (xatoga yo'l qo'ymaslik uchun)

- **Kenglik radianda** beriladi (`pyet.deg_to_rad()`). RefET esa gradus qabul qiladi.
- **RH foizda.** Agar max(RH) ≤ 1 bo'lsa, xato chiqaradi.
- **Rs MJ m⁻² d⁻¹ da.** Agar max(Rs) ≥ 100 bo'lsa, xato chiqaradi.
- `wind` allaqachon **u₂** (2 m) deb hisoblanadi. 10 m dan konversiyani foydalanuvchi qiladi.
- `clip_zero=True` bo'lsa, manfiy PET 0 ga tenglanadi.
- `tmean` qanday berilsa, shunday ishlatiladi. Standartga mos bo'lishi uchun (Tmax+Tmin)/2 berish kerak.
- Radiatsiya uchun uch yo'l bor: Rn berilgan, Rs berilgan yoki quyoshli soatlar (n) berilgan.

---

## 5. RefET va pyet taqqoslash

| Mezon | RefET | pyet |
|---|---|---|
| Asosiy maqsad | ASCE standarti (ETo + ETr), aniq va validatsiyalangan | Ko'p usulli PET "ensiklopediyasi" |
| ETr (beda) | ✔ `Daily.etr()` | ✔ `pm_asce(etype="rs")` |
| Soatlik qadam | ✔ | – (faqat kunlik) |
| Rso to'liq modeli (D ilovasi) | ✔ | – (faqat soddalashtirilgan) |
| 3D grid (xarray) | Rasmiy emas (broadcasting sinovdan o'tmagan) | ✔ |
| Validatsiya | Ref-ET v4.2, AgriMet Fallon 2015 (yil bo'yi) | FAO-56, McMahon (2013), ASCE jadvallari, CoAgMET, KNMI |
| Bog'liqliklar | Faqat NumPy | NumPy, pandas, xarray |

**Mustaqil tekshiruv** (yuklangan kod bilan, Fallon 2015-07-01):

| | ETo | ETr |
|---|---|---|
| `refet.Daily(method="asce")` | 7.998 | 10.626 |
| `pyet.pm_asce` | 7.997 | 10.625 |

Farq ≤ 0.001 mm. Sababi kichik konstantalarda (σ: 4.901·10⁻⁹ va 4.903·10⁻⁹).

---

## 6. Kodda aniqlangan nomuvofiqliklar (amalda tekshirilgan)

| # | Joy | Muammo | Ta'sir | Bizga ta'siri |
|---|---|---|---|---|
| 1 | `pyet/combination.py: kimberly_penman` | Shamol funksiyasi w kodda `wind * (0.4 + 0.14·e^{…} + (0.605 + 0.345·exp((J−243)/80)**2))` ko'rinishida yozilgan. Ikkinchi qavs u₂ ga ko'paytirilyapti va eksponentada **minus belgisi yo'q**. Hujjatda esa `u₂(0.4 + 0.14·e^{…}) + (0.605 + 0.345·e^{−((J−243)/80)²})` | J = 365 da u₂ ga ko'paytiriladigan qism **8.29** chiqadi. To'g'ri qiymat ~0.4 + 0.6 bo'lishi kerak. Kuzda va qishda PET keskin oshib ketadi | Ishlatmaymiz |
| 2 | `pyet/radiation.py: jensen_haise(method=1)` | `extraterrestrial_r(index, lat, tmean)` 3 ta argument bilan chaqiriladi, funksiya esa 2 ta qabul qiladi | `TypeError` — usul umuman ishlamaydi | Ishlatmaymiz |
| 3 | `pyet: pm_asce`, `pm_fao56` | Δ va Cn/(T+273) uchun foydalanuvchi bergan `tmean` ishlatiladi | 24 soatlik o'rtacha berilsa, standartdan biroz og'adi | O'z kodimizda T = (Tmax+Tmin)/2 qotiriladi |
| 4 | `pyet: hamon(method=1)`, `fao_24` | Docstring va kod mos emas: Hamon da "/16" va "/100"; FAO-24 da "3.15" va "0.315" | Faqat hujjatda; kod mantiqan to'g'ri ko'rinadi | Yo'q |
| 5 | `refet/calcs.py: rso_daily` | Izohda "sinβ ≥ 0.01" deyilgan, kodda esa `max(sinβ, 0.1)` | Faqat yuqori kengliklarda va qishda | Yo'q (biz soddalashtirilgan Rso dan foydalanamiz) |
| 6 | σ (Stefan-Boltzmann) | RefET: 4.901·10⁻⁹ (ASCE); pyet: 4.903·10⁻⁹ (FAO-56) | ~0.04% Rnl da | Yo'q (biz ASCE qiymatini olamiz) |

---

## 7. Bizning tanlov va uning asosi

| Qaror | Tanlov | Nega |
|---|---|---|
| Tenglama | ASCE standartlashtirilgan PM | Ham ETo, ham ETr ni bitta fizik tenglama beradi. Xalqaro standart (FAO-56 bilan to'liq mos) |
| Variant | `method="asce"`, Rso soddalashtirilgan | Standart tenglamalarning o'zi. `refet` variantidan farqi < 1% |
| Vaqt qadami | **Kunlik** (G = 0) | Standart va barqaror; ERA5-Land dan ishonchli kunlik agregatlar olinadi. Soatlik variant (RefET `Hourly`) kelajakda qo'shimcha sifatida |
| Amalga oshirish | O'zimizning vektorlashtirilgan `calculations` moduli (NumPy/xarray, `[vaqt, lat, lon]`). Formulalari RefET `asce` bilan **bir xil** | RefET 3D broadcasting ni rasman qo'llamaydi. pyet ning 3D talqinida kenglik/`tmean` kabi tuzoqlar bor. O'z modulimiz toza, tez va to'liq nazoratda |
| Hakam (test oracle) | `refet` va `pyet` | Bizning natijalar ular bilan ≤ 10⁻⁶ mm aniqlikda mos kelishi shart |
| Zaxira usul | Hargreaves (faqat harorat bor bo'lsa) | Asosiy hisobda ishlatilmaydi. Faqat diagnostika va taqqoslash uchun |

---

## 8. Loyiha metodologiyasi: O'zbekiston, 2026-yil mart–sentabr

### 8.1 Hudud va davr

- **Davr:** 2026-03-01 … 2026-09-30, ya'ni 7 to'liq oy, 214 kun. Chala oy muammosi yo'q.
- **Hudud:** O'zbekiston. Chegaralar: **geoBoundaries ADM1** (14 birlik: 12 viloyat, Qoraqalpog'iston Respublikasi, Toshkent shahri). CRS: EPSG:4326.
- **Grid:** ERA5-Land doimiy lat/lon to'ri, 0.1°. O'zbekiston chegarasi ichida taxminan 15 ming piksel.

### 8.2 Ob-havo ma'lumotlari: ERA5-Land (Copernicus CDS)

| ERA5-Land o'zgaruvchisi (CDS nomi) | Turi | Birlik | Bizga nima uchun |
|---|---|---|---|
| `2m_temperature` | lahzalik | K | Tmax, Tmin |
| `2m_dewpoint_temperature` | lahzalik | K | Tdew → ea (ASCE ustuvorligi bo'yicha 2-o'rinda) |
| `10m_u_component_of_wind`, `10m_v_component_of_wind` | lahzalik | m s⁻¹ | u₁₀ = √(u² + v²) → u₂ |
| `surface_solar_radiation_downwards` | **yig'ilgan, 00 UTC dan** | J m⁻² | Rs |
| `surface_pressure` | lahzalik | Pa | z (bosim balandligi) → P, Rso |

> **Balandlik qanday olinadi.** Davr bo'yicha o'rtacha sirt bosimi `sp` dan standart formulaning teskarisi bilan **bosim balandligi** hisoblanadi:
>
> z = (293/0.0065)·[1 − (P/101.3)^(1/5.26)]
>
> Keyin standart shakl bo'yicha P(z) va Rso(z) hisoblanadi.
>
> Bu usulning uchta afzalligi bor:
> 1. z ERA5-Land ning **o'z model relyefiga** mos keladi, harorat maydonlari ham aynan shu relyefda hisoblangan. Tashqi DEM olinsa, piksel ichidagi relyef nomuvofiqligi xato qo'shadi.
> 2. γ haqiqiy o'rtacha bosimdan olinadi.
> 3. Statik geopotensial faylini alohida yuklash shart emas.
>
> Rso ga ta'siri juda kichik: 100 m farq Rso ni ~0.3% o'zgartiradi.

Yuklab olish oralig'i **2026-02-28 … 2026-09-30 (UTC)** qilib olinadi. Sababi: mahalliy 1-mart kuni UTC bo'yicha 28-fevral soat 19:00 da boshlanadi.
Ma'lumot mavjudligi (sentabr oxiri) ishga tushirishda avtomatik tekshiriladi.

### 8.3 Preprocessing: soatlikdan kunlikka

1. **Uzunlik koordinatasi** −180…180 ga keltiriladi. Koordinatalar **piksel markazlari** ekani hisobga olinadi.
2. **Radiatsiyani de-akkumulyatsiya qilish.** ERA5-Land da yig'ish har kuni 00 UTC dan boshlanadi:
   - soatlik(t) = acc(t) − acc(t − 1h), bunda t ≠ 01 UTC;
   - soatlik(01 UTC) = acc(01 UTC).
   - 00 UTC dagi qiymat butun oldingi sutkaning yig'indisi hisoblanadi.
   - Manfiy "shovqin" qiymatlar 0 ga tenglanadi.
3. **Mahalliy kun:** Asia/Tashkent (UTC+5, yozgi vaqt yo'q).
   - Lahzalik kattaliklar uchun mahalliy kun D ga UTC 19:00 (D−1) … 18:00 (D) oralig'i to'g'ri keladi.
   - Yig'ilgan oqimlar soat oxiri bo'yicha belgilanadi, shuning uchun ular uchun oraliq bir soatga suriladi: UTC 20:00 (D−1) … 19:00 (D).
4. **Kunlik agregatlar:**
   - Tmax = max(T_soatlik), Tmin = min(T_soatlik)
   - Tdew = o'rtacha(Tdew_soatlik)
   - Rs = Σ soatlik / 10⁶ [MJ m⁻² d⁻¹]
   - u₁₀ = o'rtacha(√(u² + v²))
   - sp = o'rtacha(sp_soatlik) / 1000 [kPa]
   - ⚠️ Shamol tezligi **avval soatlik** hisoblanadi, keyin o'rtacha olinadi. Teskari tartibda (o'rtacha u va o'rtacha v dan tezlik) shamol sistematik ravishda **kamayib** chiqadi.
5. **Birliklar:** K → °C (−273.15). u₂ = 0.748·u₁₀.

### 8.4 Sifat nazorati (QC), NoData va bo'shliqlar

| Qoida | Amal |
|---|---|
| Fizik chegaralar: T ∈ [−60, 60] °C; Rs ≥ 0; Rs ≤ Ra | Chegaradan tashqaridagi qiymatlar NaN qilinadi va hisoblanadi (log) |
| Tdew > Tmax | Tdew = Tmax (RH ≤ 100%) va belgilanadi (flag) |
| VPD < 0 | 0 ga tenglanadi (RefET kabi) |
| u₂ < 0.5 m s⁻¹ | 0.5 ga tenglanadi (FAO-56 tavsiyasi) |
| ETo, ETr < 0 | 0 ga tenglanadi (mart–sentabrda kam uchraydi) |
| **Fazoviy NaN** (ERA5-Land quruqlik niqobidan tashqari: Orol qoldiqlari, Aydar-Arnasoy, yirik suv omborlari) | NoData = −9999 bo'lib qoladi. **Fazoviy to'ldirilmaydi**, chunki suv yuzasi uchun quruqlik ETo si fizik ma'noga ega emas |
| **Vaqtdagi bo'shliq** ≤ 3 kun ketma-ket | Kirish o'zgaruvchilari vaqt bo'yicha chiziqli interpolyatsiya qilinadi (ETo emas, meteo ma'lumot) |
| Oyda yaroqli kunlar ≥ 90% | Oylik yig'indi = o'rtacha kunlik × oy kunlari soni; `valid_days` rasteri orqali belgilanadi |
| Oyda yaroqli kunlar < 90% | Shu oy uchun piksel NoData bo'ladi |

### 8.5 Calculations

Har bir piksel va har bir kun uchun (`formulalar.md`, 1–5-bo'limlar):

```
z = bosim_balandligi(o'rtacha sp)
T = (Tmax+Tmin)/2 → P(z) → γ → Δ(T) → es, ea = e°(Tdew) → VPD
J, φ → δ, dr, ωs → Ra → Rso = (0.75 + 2e-5·z)·Ra → fcd → Rnl → Rn = 0.77·Rs − Rnl
u2 = 0.748·u10
ETo = ETsz(Cn=900,  Cd=0.34),  ETr = ETsz(Cn=1600, Cd=0.38)
```

> **Nega avval piksel, keyin o'rtacha?** Penman-Monteith nochiziqli. O'rtacha haroratdan hisoblangan ETo o'rtacha ETo ga teng emas. Shuning uchun hisob har doim eng mayda birlikda (piksel × kun) bajariladi, agregatsiya esa eng oxirida.

Hajm: taxminan 15 ming piksel × 214 kun ≈ 3 mln qiymat. NumPy bilan bu soniyalarda hisoblanadi. Asosiy vaqt CDS dan yuklab olishga ketadi, keyin hammasi lokal keshdan o'qiladi.

### 8.6 Natija: oylik rasterlar va viloyat jadvali

| Parametr | Qiymat |
|---|---|
| Format | GeoTIFF: float32, DEFLATE siqish |
| CRS | **EPSG:4326** (WGS 84) |
| Piksel | 0.1° × 0.1°. Transform: chap yuqori burchak = (lon_min − 0.05, lat_max + 0.05), shimol tepada |
| NoData | −9999 |
| Qiymat | **mm/oy** (kunlik ETo/ETr yig'indisi) |
| Fayllar | `<Viloyat>_ETo_2026_03.tif` …, `<Viloyat>_ETr_2026_03.tif` …, `<Viloyat>_ETo_ETr_oylik.csv` |
| Hudud | Tanlangan viloyat chegarasi atrofida 1 piksel zaxira bilan kesiladi. Niqob `all_touched=True`, ya'ni chegaradagi piksellar ham saqlanadi |

**Viloyat o'rtachasi (CSV).** Bu yerda shp/zonal statistika kerak emas, o'rtacha avtomatik hisoblanadi:
- 0.1° piksel 41° kenglikda ≈ 11.1 × 8.4 km ≈ 93 km². **Toshkent shahri** atigi bir necha pikseldan iborat.
- Shu sababli "piksel markazi" usuli ishlatilmaydi. Har bir piksel 10 × 10 mayda katakka bo'linadi va uning **poligon ichidagi ulushi** hisoblanadi (aniqligi ~1%).
- Vazn = ulush × cos(kenglik): EPSG:4326 da piksel maydoni kenglikka qarab kichrayadi.
- Formula: o'rtacha = Σ(vazn · qiymat) / Σ(vazn). NoData piksellar hisobga olinmaydi.
- `asl_malumot_foiz` ustuni oy kunlarining necha foizi to'ldirilmagan, asl ma'lumotga asoslanganini ko'rsatadi (maydon bo'yicha vaznli).

### 8.7 Validatsiya rejasi

1. **Unit-testlar:** `formulalar.md` ning 9-bo'limidagi jadval.
   - FAO-56 18-misol: ETo = 3.9 ± 0.05
   - Fallon (`asce`): ETo = 7.998, ETr = 10.626, ± 0.001
2. **Hakam bilan solishtirish:** tasodifiy 10 ming piksel-kun uchun bizning modul `refet.Daily(method="asce")` bilan solishtiriladi. Maksimal farq < 10⁻⁶ mm bo'lishi kerak.
3. **Fizik mantiq:**
   - ETr/ETo nisbati yozda taxminan 1.15–1.4 oralig'ida bo'lishi kerak.
   - Fazoviy manzara mantiqiy bo'lishi kerak: cho'l > tog'oldi > tog'.
4. **Diagnostika rasteri (ixtiyoriy):** oylik o'rtacha (Tmin − Tdew) chiqariladi. Katta qiymatlar "quruq" muhitni ko'rsatadi (8.8-bo'limga qarang).
5. **Stansiyalar (ixtiyoriy):** O'zgidromet yoki NOAA GSOD stansiyalari ma'lumoti bo'lsa, Tmax, Tmin, Tdew va shamol bo'yicha bias va RMSE hisoblanadi.

### 8.8 Cheklovlar va xatarlar

- **Aridlik effekti.** ERA5-Land sug'orishni modellashtirmaydi. Shu sababli voha va sug'oriladigan maydonlarda reanaliz haroratni yuqoriroq, namlikni pastroq ko'rsatishi mumkin. Natijada etalon ET (ETo/ETr) oshirib baholanadi.
  - ASCE-EWRI (2005) ilovalari ma'lumotlar etalon (yaxshi sug'orilgan) muhitni aks ettirishini tekshirishni tavsiya qiladi, xususan Tmin − Tdew farqi orqali.
  - Tuzatish standart sifatida **qo'llanmaydi**. Avval validatsiya natijalariga qarab qaror qilinadi.
- **Fazoviy aniqlik** 0.1°: kichik ma'muriy birliklar va tog'li hududlar uchun noaniqlik yuqori.
- **Tmax/Tmin soatlik qiymatlardan** olinadi. Haqiqiy ekstremumlar biroz kesilishi mumkin; bu reanaliz uchun standart amaliyot.

---

## 9. Adabiyotlar

1. Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop evapotranspiration — Guidelines for computing crop water requirements.* FAO Irrigation and Drainage Paper 56. FAO, Rome.
2. ASCE-EWRI (2005). *The ASCE Standardized Reference Evapotranspiration Equation.* ASCE, Reston, VA. https://doi.org/10.1061/9780784408056
3. Vremec, M., Collenteur, R.A., Birk, S. (2024). PyEt v1.3.1: a Python package for the estimation of potential evapotranspiration. *Geosci. Model Dev.*, 17, 7083–7103. https://doi.org/10.5194/gmd-17-7083-2024
4. WSWUP RefET — ASCE Standardized Reference ET (Python). https://github.com/WSWUP/refet (Ref-ET v4.2, University of Idaho, bilan validatsiya qilingan)
5. Muñoz-Sabater, J. va boshq. (2021). ERA5-Land: a state-of-the-art global reanalysis dataset for land applications. *Earth Syst. Sci. Data*, 13, 4349–4383. https://doi.org/10.5194/essd-13-4349-2021
6. Runfola, D. va boshq. (2020). geoBoundaries: A global database of political administrative boundaries. *PLOS ONE*, 15(4), e0231866. https://doi.org/10.1371/journal.pone.0231866
7. McMahon, T.A. va boshq. (2013). Estimating actual, potential, reference crop and pan evaporation using standard meteorological data: a pragmatic synthesis. *Hydrol. Earth Syst. Sci.*, 17, 1331–1363. https://doi.org/10.5194/hess-17-1331-2013
8. Oudin, L. va boshq. (2005). Which potential evapotranspiration input for a lumped rainfall–runoff model? *J. Hydrol.*, 303, 290–306.
9. Valiantzas, J.D. (2006). Simplified versions for the Penman evaporation equation using routine weather data. *J. Hydrol.*, 331, 690–702.
