# Formulalar: ETo va ETr hisoblash

> **Manba kodlar:** `pyet` v1.3.1 va `master` (v1.4.0). Ikkala versiyada formulalar bir xil, farq faqat importlar tartibida.
> `RefET` (WSWUP, `main` tarmog'i) — ASCE standartining NumPy dagi rasmiy talqini.
> **Asosiy adabiyot:** FAO-56 (Allen va boshq., 1998) va ASCE-EWRI (2005).
>
> Har bir formula yonida uni amalga oshiruvchi funksiya ko'rsatilgan. Shu sababli hujjatni kod bilan solishtirib tekshirish mumkin.

---

## 0. Belgilar va birliklar

| Belgi | Ma'nosi | Birlik |
|---|---|---|
| ETo | Qisqa (o't, 0.12 m) etalon bug'lanish | mm d⁻¹ |
| ETr | Baland (beda, 0.5 m) etalon bug'lanish | mm d⁻¹ |
| ETsz | ASCE standartlashtirilgan etalon ET (ETo yoki ETr) | mm d⁻¹ (mm h⁻¹) |
| Rn | Sof radiatsiya | MJ m⁻² d⁻¹ |
| Rs | Kiruvchi qisqa to'lqinli (quyosh) radiatsiya | MJ m⁻² d⁻¹ |
| Ra | Atmosferadan tashqi radiatsiya | MJ m⁻² d⁻¹ |
| Rso | Ochiq osmon radiatsiyasi | MJ m⁻² d⁻¹ |
| G | Tuproq issiqlik oqimi | MJ m⁻² d⁻¹ |
| T | O'rtacha havo harorati, 1.5–2.5 m | °C |
| Tmax, Tmin | Kunlik maksimal / minimal harorat | °C |
| Tdew | Shudring nuqtasi harorati | °C |
| u₂ | 2 m balandlikdagi shamol tezligi | m s⁻¹ |
| uz, zw | zw balandlikdagi shamol tezligi, o'lchash balandligi | m s⁻¹, m |
| e°(T) | T haroratdagi to'yingan bug' bosimi | kPa |
| es | To'yingan bug' bosimi (kunlik) | kPa |
| ea | Haqiqiy bug' bosimi | kPa |
| Δ | To'yingan bug' bosimi egri chizig'ining qiyaligi | kPa °C⁻¹ |
| γ | Psixrometrik doimiy | kPa °C⁻¹ |
| P | Atmosfera bosimi | kPa |
| λ | Bug'lanishning yashirin issiqligi | MJ kg⁻¹ |
| z | Joyning dengiz sathidan balandligi | m |
| φ | Kenglik | rad |
| J | Yil kuni (DOY), 1–365/366 | – |
| Cn, Cd | Sirt turiga bog'liq surat va maxraj konstantalari | K mm s³ Mg⁻¹ d⁻¹, s m⁻¹ |

---

## 1. Asosiy tenglama: ASCE standartlashtirilgan Penman-Monteith

Bitta tenglama ikkala etalon sirtni ham beradi. Farq faqat ikki konstantada: Cn va Cd.

$$
ET_{sz} = \frac{0.408\,\Delta\,(R_n - G) + \gamma\,\dfrac{C_n}{T + 273}\,u_2\,(e_s - e_a)}{\Delta + \gamma\,(1 + C_d\,u_2)}
$$

| Vaqt qadami | Sirt | Cn | Cd | G |
|---|---|---|---|---|
| Kunlik | **ETo** (o't) | **900** | **0.34** | 0 |
| Kunlik | **ETr** (beda) | **1600** | **0.38** | 0 |
| Soatlik, kunduz (Rn > 0) | ETo | 37 | 0.24 | 0.1·Rn |
| Soatlik, tun (Rn < 0) | ETo | 37 | 0.96 | 0.5·Rn |
| Soatlik, kunduz (Rn > 0) | ETr | 66 | 0.25 | 0.04·Rn |
| Soatlik, tun (Rn < 0) | ETr | 66 | 1.7 | 0.2·Rn |

**Kodda:**
- `refet/calcs.py: etsz()`; `refet/daily.py: Daily.eto()`, `Daily.etr()`; `refet/hourly.py: Hourly.eto()`, `Hourly.etr()`
- `pyet/combination.py: pm_asce(etype="os" | "rs")`. Bu yerda `"os"` o't (Cn=900, Cd=0.34), `"rs"` esa beda (Cn=1600, Cd=0.38).
- `pyet/combination.py: pm_fao56()` — FAO-56 tenglamasi. U kunlik ETo ga aynan teng (Cn=900, Cd=0.34):

$$
ET_o = \frac{0.408\,\Delta\,(R_n - G) + \gamma\,\dfrac{900}{T + 273}\,u_2\,(e_s - e_a)}{\Delta + \gamma\,(1 + 0.34\,u_2)}
$$

> ⚠️ **Muhim:** kunlik qadamda standart T = (Tmax + Tmin)/2 ni talab qiladi.
> RefET buni o'zi hisoblaydi (`self.tmean = 0.5 * (tmax + tmin)`).
> pyet esa foydalanuvchi bergan `tmean` ni ishlatadi, shuning uchun unga aynan (Tmax+Tmin)/2 ni berish kerak. 24 soatlik o'rtacha berilsa, Δ va Cn/(T+273) biroz o'zgaradi.

---

## 2. Atmosfera parametrlari

### 2.1 Atmosfera bosimi (FAO-56 7-tenglama; ASCE 3-tenglama)

$$
P = 101.3\left(\frac{293 - 0.0065\,z}{293}\right)^{5.26}
$$

- `refet/calcs.py: air_pressure(method="asce")`, `pyet/meteo_utils.py: calc_press()`
- `method="refet"` varianti: daraja ko'rsatkichi 9.8/(0.0065·286.9) ≈ 5.255.
- RefET standart shaklga mos kelishi uchun P ni **doim balandlikdan** hisoblaydi. pyet esa, agar berilgan bo'lsa, o'lchangan P ni ishlatadi.

### 2.2 Psixrometrik doimiy (FAO-56 8-tenglama)

$$
\gamma = 0.000665\,P
$$

- `refet/daily.py` (`psy = 0.000665 * pair`), `pyet/meteo_utils.py: calc_psy(pressure)`
- pyet muqobili (agar `tmean` berilsa): γ = c_p·P / (0.622·λ), bunda c_p = 1.013·10⁻³ MJ kg⁻¹ °C⁻¹.

### 2.3 Yashirin issiqlik (FAO-56 3-1 ilova tenglamasi)

$$
\lambda = 2.501 - 0.002361\,T
$$

- `pyet/meteo_utils.py: calc_lambda()`. Penman, PM, Priestley-Taylor va radiatsion usullarda ishlatiladi. ASCE tenglamasida esa 0.408 = 1/λ (λ = 2.45) qilib "qotirilgan".

### 2.4 Havo zichligi (FAO-56 3-5 ilova tenglamasi)

$$
\rho_a = 3.486\,\frac{P}{T_{kv}}, \qquad T_{kv} = \frac{273.16 + T}{1 - 0.378\,e_a / P}
$$

- `pyet/meteo_utils.py: calc_rho()`. Faqat umumiy `pm()` funksiyasida ishlatiladi.

---

## 3. Namlik va bug' bosimi

### 3.1 To'yingan bug' bosimi (FAO-56 11-tenglama)

$$
e^{\circ}(T) = 0.6108\,\exp\!\left(\frac{17.27\,T}{T + 237.3}\right)
$$

- `refet/calcs.py: sat_vapor_pressure()`, `pyet/meteo_utils.py: calc_e0()`

### 3.2 Kunlik to'yingan bug' bosimi (FAO-56 12-tenglama)

$$
e_s = \frac{e^{\circ}(T_{max}) + e^{\circ}(T_{min})}{2}
$$

- `refet/daily.py`, `pyet/meteo_utils.py: calc_es()`
- ⚠️ Bu ifoda e°((Tmax+Tmin)/2) ga teng **emas**. Funksiya nochiziqli bo'lgani uchun o'rtachaning e° si e° larning o'rtachasidan kichik chiqadi.

### 3.3 Egri chiziq qiyaligi (FAO-56 13-tenglama)

$$
\Delta = \frac{4098\,e^{\circ}(T)}{(T + 237.3)^2} = \frac{2503\,\exp\!\left(\frac{17.27\,T}{T + 237.3}\right)}{(T + 237.3)^2}
$$

- `refet/calcs.py: es_slope(method="asce")` 2503 koeffitsiyentini ishlatadi. `method="refet"` varianti esa 4098·0.6108 ni. Farq faqat yaxlitlashda.
- `pyet/meteo_utils.py: calc_vpc()`

### 3.4 Haqiqiy bug' bosimi ea (ustuvorlik tartibida, ASCE 3-jadval)

| # | Kirish ma'lumoti | Formula | Kod |
|---|---|---|---|
| 1 | O'lchangan ea | to'g'ridan-to'g'ri | `Daily(ea=...)`, `calc_ea(ea=...)` |
| 2 | **Tdew** (shudring nuqtasi) | ea = e°(Tdew) | `Daily(tdew=...)` |
| 3 | RHmax va RHmin | quyida (17) | `calc_ea(rhmax, rhmin)` |
| 4 | RHmean | quyida (19) | `calc_ea(rh)` |
| – | Solishtirma namlik q | quyida | `refet/calcs.py: actual_vapor_pressure()` |

$$
e_a = \frac{e^{\circ}(T_{min})\,\frac{RH_{max}}{100} + e^{\circ}(T_{max})\,\frac{RH_{min}}{100}}{2} \qquad \text{(FAO-56, 17)}
$$

$$
e_a = \frac{RH_{mean}}{100}\cdot\frac{e^{\circ}(T_{max}) + e^{\circ}(T_{min})}{2} \qquad \text{(FAO-56, 19)}
$$

$$
e_a = \frac{q\,P}{0.622 + 0.378\,q}, \qquad q = \frac{0.622\,e_a}{P - 0.378\,e_a}
$$

### 3.5 Bug' bosimi defitsiti (VPD)

$$
VPD = \max(e_s - e_a,\ 0)
$$

- RefET kunlik qadamda manfiy qiymatlarni 0 ga tenglaydi (`calcs.vpd`). Soatlik qadamda bunday cheklash yo'q.
- pyet esa VPD ni cheklamaydi.

---

## 4. Radiatsiya

### 4.1 Quyosh–Yer nisbiy masofasi (FAO-56 23-tenglama)

$$
d_r = 1 + 0.033\cos\!\left(\frac{2\pi}{365}J\right)
$$

- `refet/calcs.py: dr()`, `pyet/meteo_utils.py: relative_distance()`

### 4.2 Quyosh og'ishi (FAO-56 24-tenglama)

$$
\delta = 0.409\,\sin\!\left(\frac{2\pi}{365}J - 1.39\right)
$$

- `refet/calcs.py: declination(method="asce")`, `pyet/meteo_utils.py: solar_declination()`
- `method="refet"` varianti (Duffie & Beckman): δ = 23.45·(π/180)·sin(2π(284 + J)/365)

### 4.3 Quyosh botish soat burchagi (FAO-56 25-tenglama)

$$
\omega_s = \arccos\!\big[\mathrm{clip}(-\tan\varphi\,\tan\delta,\ -1,\ 1)\big]
$$

- `refet/calcs.py: sunset_hour_angle()`, `pyet/meteo_utils.py: sunset_angle()`. `clip` qutb kengliklarida NaN chiqishining oldini oladi.

### 4.4 Kunlik tashqi radiatsiya (FAO-56 21-tenglama)

$$
R_a = \frac{24\cdot 60}{\pi}\,G_{sc}\,d_r\,\big[\omega_s\sin\varphi\sin\delta + \cos\varphi\cos\delta\sin\omega_s\big]
$$

| Kod | Ifoda | G_sc |
|---|---|---|
| FAO-56 / pyet `extraterrestrial_r()` | 118.08/π · … | 0.0820 MJ m⁻² min⁻¹ |
| RefET `ra_daily(method="asce")` | (24/π)·4.92 · … | 4.92 MJ m⁻² h⁻¹ |
| RefET `ra_daily(method="refet")` | (24/π)·(1367·0.0036) · … | 4.9212 MJ m⁻² h⁻¹ |

### 4.5 Kun uzunligi (FAO-56 34-tenglama)

$$
N = \frac{24}{\pi}\,\omega_s
$$

- `pyet/meteo_utils.py: daylight_hours()`

### 4.6 Quyosh radiatsiyasi quyoshli soatlardan (Angstrom, FAO-56 35-tenglama)

Rs o'lchanmagan bo'lsa ishlatiladi:

$$
R_s = \left(a_s + b_s\,\frac{n}{N}\right)R_a, \qquad a_s = 0.25,\ b_s = 0.50
$$

- `pyet/rad_utils.py: calc_rad_sol_in()`

### 4.7 Ochiq osmon radiatsiyasi Rso

**Soddalashtirilgan variant** (FAO-56 37-tenglama; ASCE 19-tenglama). `method="asce"` da standart sifatida shu ishlatiladi:

$$
R_{so} = (0.75 + 2\cdot10^{-5}\,z)\,R_a \qquad \text{yoki} \qquad R_{so} = K_{ab}\,R_a,\ \ K_{ab} = a_s + b_s
$$

- `refet/calcs.py: rso_simple()`, `pyet/rad_utils.py: calc_rso()`

**To'liq variant** (ASCE D ilovasi). `method="refet"` yoki `rso_type="full"` da ishlatiladi:

$$
\sin\beta_{24} = \sin\!\left[0.85 + 0.3\,\varphi\,\sin\!\left(\frac{2\pi}{365}J - 1.39\right) - 0.42\,\varphi^2\right], \quad \sin\beta_{24} \ge 0.1
$$

$$
W = 0.14\,e_a\,P + 2.1 \quad \text{(yog'in hosil qila oladigan suv, mm)}
$$

$$
K_B = 0.98\,\exp\!\left[\frac{-0.00146\,P}{K_t\,\sin\beta_{24}} - 0.075\left(\frac{W}{\sin\beta_{24}}\right)^{0.4}\right], \quad K_t = 1
$$

$$
K_D = \min(0.35 - 0.36\,K_B,\ \ 0.18 + 0.82\,K_B), \qquad R_{so} = (K_B + K_D)\,R_a
$$

- `refet/calcs.py: rso_daily()`

### 4.8 Sof qisqa to'lqinli radiatsiya (FAO-56 38-tenglama)

$$
R_{ns} = (1 - \alpha)\,R_s = 0.77\,R_s, \qquad \alpha = 0.23
$$

### 4.9 Bulutlilik funksiyasi va sof uzun to'lqinli radiatsiya (FAO-56 39-tenglama; ASCE 17–18-tenglamalar)

$$
f_{cd} = 1.35\,\mathrm{clip}\!\left(\frac{R_s}{R_{so}},\ 0.3,\ 1.0\right) - 0.35
$$

$$
R_{nl} = \sigma\,\frac{T_{max,K}^4 + T_{min,K}^4}{2}\,\big(0.34 - 0.14\sqrt{e_a}\big)\,f_{cd}, \qquad T_K = T + 273.16
$$

| Kod | σ (kunlik) | Qo'shimcha |
|---|---|---|
| RefET `rnl_daily()`, `fcd_daily()` | 4.901·10⁻⁹ MJ K⁻⁴ m⁻² d⁻¹ (ASCE) | Rso = 0 bo'lsa, fcd = 1 |
| pyet `calc_rad_long()` | 4.903·10⁻⁹ (FAO-56) | fcd yana [0.05, 1] ga cheklanadi. Standart koeffitsiyentlarda bu ortiqcha: fcd ≥ 0.055 |

σ dagi farq Rnl ga taxminan 0.04% ta'sir qiladi, amalda sezilmaydi.

### 4.10 Sof radiatsiya va tuproq issiqlik oqimi

$$
R_n = R_{ns} - R_{nl}, \qquad G_{kunlik} \approx 0
$$

- `refet/calcs.py: rn_daily()`, `pyet/rad_utils.py: calc_rad_net()`

---

## 5. Shamol: balandlikni 2 m ga keltirish (FAO-56 47-tenglama; ASCE 33-tenglama)

$$
u_2 = u_z\,\frac{4.87}{\ln(67.8\,z_w - 5.42)}
$$

| zw | Ko'paytuvchi |
|---|---|
| 2 m | 1.000 |
| 3 m | 0.921 |
| **10 m** (ERA5-Land) | **0.748** |

- `refet/calcs.py: wind_height_adjust()`. pyet bu konversiyani qilmaydi: `wind` allaqachon u₂ deb hisoblanadi.

---

## 6. Soatlik qadam (RefET `Hourly`)

Kunlik formulalardan farqlari:

$$
b = \frac{2\pi(J - 81)}{364}, \qquad S_c = 0.1645\sin 2b - 0.1255\cos b - 0.025\sin b
$$

$$
\omega = \frac{2\pi}{24}\left(t_{mid,UTC} + \frac{\lambda_{lon}\cdot 24}{2\pi} + S_c - 12\right), \quad \omega \in [-\pi, \pi]
$$

$$
\omega_1 = \mathrm{clip}\!\left(\omega - \frac{\pi}{24}, -\omega_s, \omega_s\right), \qquad \omega_2 = \mathrm{clip}\!\left(\omega + \frac{\pi}{24}, -\omega_s, \omega_s\right)
$$

$$
R_{a,h} = \frac{12}{\pi}\,G_{sc}\,d_r\,\big[(\omega_2 - \omega_1)\sin\varphi\sin\delta + \cos\varphi\cos\delta\,(\sin\omega_2 - \sin\omega_1)\big]
$$

$$
R_{nl,h} = 2.042\cdot10^{-10}\,f_{cd}\,(0.34 - 0.14\sqrt{e_a})\,T_K^4, \qquad e_s = e^{\circ}(T_{soatlik})
$$

- Quyosh balandligi β < 0.3 rad bo'lganda RefET fcd = 1 qilib qo'yadi. Bu soddalashtirish: ASCE quyosh botishidan oldingi fcd ni ishlatishni tavsiya qiladi.
- Cn, Cd va G qiymatlari 1-bo'limdagi jadvalda.

---

## 7. pyet dagi boshqa PET usullari (qisqa ma'lumotnoma)

Barchasi mm d⁻¹ beradi. λ, Δ, γ yuqoridagi formulalar bo'yicha hisoblanadi. Standart koeffitsiyentlar qavs ichida.

### 7.1 Kombinatsion (energiya + aerodinamika)

**Penman** (`penman`, Valiantzas 2006 shakli; aw = 1, bw = 0.537):

$$
PET = \frac{\dfrac{\Delta(R_n - G)}{\lambda} + \gamma\,(a_w + b_w u_2)(e_s - e_a)}{\Delta + \gamma}
$$

**Penman-Monteith, umumiy shakl** (`pm`; K_min = 86400 s d⁻¹, c_p = 1.013·10⁻³):

$$
PET = \frac{\Delta(R_n - G) + \rho_a c_p K_{min}\,\dfrac{(e_s - e_a)\,a_{sh}}{r_a}}{\lambda\left[\Delta + \gamma\,\dfrac{a_{sh}}{a_s}\left(1 + \dfrac{r_s}{r_a}\right)\right]}
$$

$$
r_a = \frac{208}{u_2}\ \ (\text{ra\_method}=0), \qquad r_a = \frac{\ln\frac{z_w - d}{z_{om}}\,\ln\frac{z_h - d}{z_{oh}}}{0.41^2\,u_2}\ \ (\text{ra\_method}=1)
$$

$$
d = 0.667h,\ \ z_{om} = 0.123h,\ \ z_{oh} = 0.0123h, \qquad r_s = \frac{f_{CO_2}\,r_l}{LAI_{eff}},\ \ f_{CO_2} = 1 + S_{rs}(CO_2 - 300)
$$

LAI berilmasa, r_s = r_l / (0.5·h·24). O't uchun (h = 0.12 m, r_l = 100) bu ≈ 70 s m⁻¹ beradi, ya'ni FAO-56 qiymati.

LAI_eff variantlari:
- 0.5·LAI
- LAI/(0.3·LAI + 1.2)
- Zhang va boshq. (2008) bo'yicha ikki xil cheklangan variant

**Priestley-Taylor** (`priestley_taylor`, α = 1.26):

$$
PET = \frac{\alpha\,\Delta\,(R_n - G)}{\lambda(\Delta + \gamma)}
$$

**Kimberly-Penman** (`kimberly_penman`; hujjatlashtirilgan shakl):

$$
PET = \frac{\Delta(R_n - G) + \gamma(e_s - e_a)\,w}{\lambda(\Delta + \gamma)}
$$

$$
w = u_2\left(0.4 + 0.14\,e^{-\left(\frac{J - 173}{58}\right)^2}\right) + \left(0.605 + 0.345\,e^{-\left(\frac{J - 243}{80}\right)^2}\right)
$$

> ⚠️ Koddagi w hujjatdagidan farq qiladi. Tafsilotlar `usullar.md` ning 6-bo'limida.

**Thom-Oliver** (`thom_oliver`, aw = 2.6, bw = 0.536):

$$
PET = \frac{\Delta(R_n - G) + 2.5\,\gamma\,(e_s - e_a)\,w}{\lambda\left[\Delta + \gamma\left(1 + \frac{r_s}{r_a}\right)\right]}, \qquad w = a_w(1 + b_w u_2)
$$

### 7.2 Haroratga asoslangan usullar

| Usul (funksiya) | Formula | Koeffitsiyentlar |
|---|---|---|
| Blaney-Criddle, m=0 (`blaney_criddle`) | a + b·p·(0.457T + 8.128) | a = −1.55, b = 0.96 |
| Blaney-Criddle, m=1 | k·p·(0.46T + 8.13) | k = 0.65 |
| Blaney-Criddle, m=2 (FAO-24) | k₁ + b_var·p·(0.46T + 8.13) | k₁ = 0.0043·RHmin − n/N − 1.41 |
| Hamon, m=0 (`hamon`) | k·(DL/12)²·exp(T/16) | k = 1 |
| Hamon, m=1 | c·(DL/12)²·4.95·exp(0.062T)/100 | c = 13.97 |
| Hamon, m=2 | cc·(DL/12)·exp(17.26939T/(T+273.3))/(T+273.3) | cc = 218.527 |
| Hamon, m=3 | k·14·(n/12)²·(216.7·es·10/(T+273.3))/100 | – |
| Romanenko (`romanenko`) | k·(1 + T/25)²·(1 − ea/es) | k = 4.5 |
| Linacre (`linacre`) | [500·Tm/(100 − φ°) + 15(T − Td)] / (80 − T) | Tm = T + 0.006z |
| Haude (`haude`) | k·f_oy·(e°(T) − ea)·10 | k = 1 |

Qo'shimcha izohlar:
- **Blaney-Criddle:** p — kun uzunligining yillik yig'indiga nisbati (%). m=2 uchun b_var = e₀ + e₁RHmin + e₂n/N + e₃u₂ + e₄RHmin·n/N + e₅RHmin·u₂, bunda e₀..e₅ = 0.81917, −0.0040922, 1.0705, 0.065649, −0.0059684, −0.0005967.
- **Linacre:** Td berilmasa, Td = 0.52·Tmin + 0.6·Tmax − 0.009·Tmax² − 2.
- **Haude:** T sifatida soat 14:00 dagi harorat yoki Tmax olinadi. Oylik koeffitsiyentlar (yanvar–dekabr): 0.27, 0.27, 0.28, 0.39, 0.39, 0.37, 0.35, 0.33, 0.31, 0.29, 0.27, 0.27.

### 7.3 Radiatsiyaga asoslangan usullar

| Usul (funksiya) | Formula | Koeffitsiyentlar |
|---|---|---|
| Turc (`turc`) | k·c·T/(T + 15)·(23.88·Rs + 50) | k = 0.013; c = 1 (RH ≥ 50), aks holda c = 1 + (50 − RH)/70 |
| Jensen-Haise, m=0 (`jensen_haise`) | Cr·(T − Tx)·Rs/λ | Cr = 0.025, Tx = −3 |
| Jensen-Haise, m=1 | Ra·(T + 5)/(68λ) | ⚠️ kodda ishlamaydi, 6-bo'limga qarang |
| McGuinness-Bordne (`mcguinness_bordne`) | k·Ra·(T + 5)/λ | k = 0.0147 |
| Hargreaves, m=0 (`hargreaves`) | 0.0023·(k/0.0135)·(T + 17.8)·√(Tmax − Tmin)·Ra/λ | k = 0.0135 |
| Hargreaves, m=1 | k·c_hs·√(Tmax − Tmin)·Ra/λ·(T + 17.8) | c_hs = 0.00185·ΔT² − 0.0433·ΔT + 0.4023 |
| FAO-24 radiatsion (`fao_24`) | −0.3 + Δ/(Δ + γ)·Rs·(1 − α)·w/λ | w = 1.066 − 0.13·RH/100 + 0.045u₂ − 0.02·(RH/100)·u₂ − 0.315·(RH/100)² − 0.0011u₂ |
| Abtew (`abtew`) | k·Rs/λ | k = 0.53 |
| Makkink (`makkink`) | k·Δ/(Δ + γ)·Rs/λ | k = 0.65 |
| Makkink-KNMI (`makkink_knmi`) | KNMI ning empirik varianti | faqat Niderlandiya uchun (~dengiz sathi) |
| Oudin (`oudin`) | Ra·(T + k₂)/(λ·k₁), agar T + k₂ ≥ 0; aks holda 0 | k₁ = 100, k₂ = 5 |

---

## 8. Birlik konvertatsiyalari

| Kattalik | Dan | Ga | Amal | Manba |
|---|---|---|---|---|
| Harorat | K | °C | − 273.15 | `refet/units.py` |
| Harorat | °F | °C | (F − 32)·5/9 | `refet/units.py` |
| Rs (kunlik o'rtacha oqim) | W m⁻² | MJ m⁻² d⁻¹ | × 0.0864 | `refet/units.py` |
| Rs (soatlik) | W m⁻² | MJ m⁻² h⁻¹ | × 0.0036 | `refet/units.py` |
| Rs (yig'ilgan energiya, ERA5) | J m⁻² | MJ m⁻² | × 10⁻⁶ | ERA5-Land konvensiyasi |
| Rs | Langley | MJ m⁻² | × 0.041868 | `refet/units.py` |
| Bosim / ea | Pa | kPa | ÷ 1000 | `refet/units.py` |
| Shamol | mph | m s⁻¹ | × 0.44704 | `refet/units.py` |
| Balandlik | ft | m | × 0.3048 | `refet/units.py` |
| Balandlik (ERA5 geopotensial) | m² s⁻² | m | ÷ 9.80665 | ERA5 konvensiyasi |
| Kenglik | ° | rad | × π/180 | pyet radian talab qiladi; RefET gradus qabul qiladi |
| Shamol (ERA5, komponentlar) | u₁₀, v₁₀ | u₁₀ tezlik | √(u² + v²) — **soatlik** qadamda | 2-bo'lim, `usullar.md` |

---

## 9. Nazorat qiymatlari (unit-testlar uchun)

| Test | Kirish | Kutilgan | Tekshiruv natijasi (yuklangan kod bilan) |
|---|---|---|---|
| FAO-56 2-misol | z = 1800 m | P = 81.8 kPa | pyet testi ✔ |
| FAO-56 5-misol | Tmax = 25, Tmin = 18, RHmax = 82, RHmin = 54 | ea = 1.70 kPa (17-tenglama); 1.78 (RHmean) | pyet testi ✔ |
| FAO-56 8-misol | J = 246, φ = −0.35 rad | Ra = 32.2 MJ m⁻² d⁻¹ | pyet testi ✔ |
| FAO-56 9-misol | J = 246, φ = −0.35 rad | N = 11.7 soat | pyet testi ✔ |
| FAO-56 10-misol | Rs = 14.5, Rso = 18.8, Tmax = 25.1, Tmin = 19, ea = 2.1 | Rnl = 3.5 MJ m⁻² d⁻¹ | pyet testi ✔ |
| **FAO-56 18-misol** (Bryussel, 6-iyul) | Tmax = 21.5, Tmin = 12.3, RHmax = 84, RHmin = 63, Rs = 22.07, u₂ = 2.078, z = 100, φ = 50.80° | **ETo ≈ 3.9 mm d⁻¹** | pyet `pm_fao56`: **3.880** ✔ |
| **RefET, Fallon NV** (2015-07-01, arid) | Tmin = 66.65 °F, Tmax = 102.80 °F, ea = 1.2207 kPa, Rs = 674.07 Ly, uz = 4.80 mph, zw = 3 m, z = 1208.5 m, φ = 39.4575°, J = 182 | asce: **ETo = 7.998, ETr = 10.626**; refet: ETo = 7.942, ETr = 10.571 | refet ✔, pyet `pm_asce`: 7.997 / 10.625 ✔ |

> Fallon misolida ETr/ETo = **1.33**. Quruq iqlimda beda o't etalonidan taxminan uchdan bir ko'p suv bug'latadi. O'zbekiston sharoiti ham shunga yaqin.
