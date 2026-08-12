# Grid Resilience Studio

**Grid Resilience Studio v1.1.0** یک نرم‌افزار دسکتاپ آفلاین برای غربال‌گری مهندسی تاب‌آوری شبکه‌های قدرت است. این نسخه، تحلیل اقتضایی N-1 مبتنی بر DC را با **پخش بار AC متعادل Newton–Raphson**، dispatch اقتصادی مقید با بررسی قابلیت‌پذیری AC، واردسازی IEEE CDF و subset شفاف CIM/CGMES، و کنترل دسترسی نقش‌محور محلی ترکیب می‌کند.

> این نرم‌افزار برای تحلیل مهندسی و آموزش طراحی شده است، نه فرمان بلادرنگ یا تصمیم بهره‌برداری. پیش از هر تصمیم عملیاتی، ورودی‌ها و نتایج باید مستقلانه توسط مهندس صلاحیت‌دار بازبینی و با ابزارها و مطالعات مصوب تأیید شوند.

| حوزه | قابلیت v1.1.0 | وضعیت |
|---|---|---|
| تحلیل تاب‌آوری | پخش بار DC، غربال‌گری N-1 خطوط/ژنراتورها، تشخیص جزیره‌شدگی، بار بدون‌خدمت و رتبه‌بندی ریسک | پیاده‌سازی‌شده |
| تحلیل AC | باس‌های PQ/PV/slack، ولتاژ مختلط، توان راکتیو، تلفات، جریان دو سر شاخه، حدود ولتاژ و Q-limit switching | پیاده‌سازی‌شده |
| بهینه‌سازی | dispatch اقتصادی با هزینهٔ درجه‌دو، حدود `Pmin/Pmax` و post-check پخش بار AC | پیاده‌سازی‌شده؛ **AC-OPF کامل نیست** |
| دادهٔ صنعتی | IEEE CDF fixed-column و scanner/subset importer برای RDF/XML و ZIPهای CIM/CGMES | پیاده‌سازی‌شده؛ **انطباق CGMES ادعا نمی‌شود** |
| حاکمیت و امنیت | RBAC محلی، PBKDF2-HMAC-SHA256، audit trail زنجیره‌هش، کنترل دسترسی در رابط | پیاده‌سازی‌شده |
| عرضهٔ ویندوز | ساخت EXE، checksum، وضعیت امضای قابل‌انتشار و مسیر اختیاری Authenticode با secrets محافظت‌شده | پیاده‌سازی‌شده |

## شروع سریع

اجرای مستقیم کد منبع به Python 3.10 یا جدیدتر نیاز دارد و وابستگی زمان‌اجرای خارجی ندارد.

```bash
python -m unittest discover -s tests -v
python grid_resilience_desktop.py
```

در نخستین اجرا، برنامه یک حساب **Administrator** محلی می‌سازد. گذرواژه در فایل قابل‌حمل پروژه ذخیره نمی‌شود؛ رکورد هویت محلی با PBKDF2-HMAC-SHA256 و salt تصادفی نگهداری می‌شود. نقش‌های `viewer`، `analyst`، `operator` و `administrator` از یک نگاشت مرکزی permission استفاده می‌کنند.

## تحلیل AC و بهینه‌سازی

حل‌گر AC، یک شبکهٔ متعادل در حالت ماندگار را با Newton–Raphson حل می‌کند. خروجی، همگرایی، mismatch، ولتاژ و زاویهٔ هر باس، تزریق P/Q، جریان و توان دو سر شاخه، تلفات و نقض حدود را نشان می‌دهد. در باس‌های PV، اگر تولید توان راکتیو از حد تعیین‌شده عبور کند، باس با ثبت پیام ممیزی از PV به PQ تبدیل می‌شود.

> dispatch اقتصادی v1.1.0 یک کمینه‌سازی محدب هزینهٔ درجه‌دو تحت حدود توان فعال است و سپس نتیجه را با پخش بار AC بررسی می‌کند. این فرایند **جایگزین AC-OPF غیرخطی یا SCOPF نیست**؛ به‌ویژه optimum محلی/سراسری، قیدهای غیرخطی همهٔ شاخه‌ها و dual variables تأییدشده را تضمین نمی‌کند. AC-OPF حرفه‌ای، هزینه، متغیرهای `Vm`/`Va`/`Pg`/`Qg`، توازن توان و قیود خطی/غیرخطی را در یک مسئلهٔ واحد حل می‌کند. [1] [2]

| روش | کاربرد مجاز | محدودیت کلیدی |
|---|---|---|
| DC N-1 | غربال‌گری سریع بارگذاری و اتصال‌پذیری | ولتاژ، Q، تلفات و پایداری را مدل نمی‌کند |
| AC power flow | کنترل حالت ماندگار شبکهٔ متعادل | حفاظت، اتصال کوتاه، نامتعادلی و دینامیک را مدل نمی‌کند |
| Economic dispatch + AC check | مقایسهٔ setpointهای اقتصادی و قابلیت‌پذیری اولیه | AC-OPF/SCOPF تأییدشده نیست |

## واردسازی صنعتی

Importer فایل IEEE CDF بخش‌های Bus و Branch را با محدوده‌های ستونی استاندارد می‌خواند؛ نوع باس PQ/PV/swing، بار MW/MVAR، تولید، R/X/B، rating و tap به مدل داخلی نگاشت می‌شوند. قالب CDF دادهٔ کامل موردنیاز OPF، از جمله منحنی هزینه و همهٔ حدود عملیاتی را الزاماً ندارد؛ بنابراین برای هر مقدار استنباطی، گزارش هشدار provenance ایجاد می‌شود و چنین داده‌ای باید پیش از optimization اصلاح و تأیید شود. [3] [4]

CIM/CGMES در تبادل شبکه‌های قدرت از فایل‌های RDF/CIM XML و profileهای جداگانه برای تجهیز، توپولوژی و وضعیت بهره‌برداری استفاده می‌کند. [5] پیاده‌سازی v1.1.0 ابتدا فایل XML/RDF یا ZIP را با محدودیت اندازهٔ ایمن می‌خواند، سپس subset شامل `TopologicalNode`/`ConnectivityNode`، `Terminal`، `EnergyConsumer`، `SynchronousMachine`/`ExternalNetworkInjection` و `ACLineSegment` را گزارش و در صورت کفایت داده، نگاشت می‌کند. تجهیز پشتیبانی‌نشده یا profile ناقص به‌وضوح در `ImportReport` می‌آید. یک importer صنعتی کامل معمولاً همهٔ profileها را در triplestore می‌خواند و با تبدیل‌های دقیق‌تر به مدل شبکه می‌رسد. [6]

> این برنامه هیچ ادعای **CGMES conformance** ندارد. چنین ادعایی تنها پس از پوشش profileهای لازم، مجموعه‌های آزمون رسمی و ارزیابی مستقل قابل طرح است.

## امنیت و امضای کد

تمام عملیات حساس رابط با permission کنترل می‌شوند. نقش Analyst می‌تواند واردسازی و تحلیل انجام دهد؛ نقش Operator علاوه بر آن مجاز به dispatch اقتصادی است؛ و Administrator فقط نقش مدیریت حساب و سیاست را دارد. audit محلی به‌صورت JSONL hash-chained ذخیره و قابل اعتبارسنجی است؛ شکست زنجیره یا تغییر رکورد آشکار می‌شود. این کنترل‌ها جایگزین SSO، HSM، رمزنگاری دیسک، EDR یا کنترل سیستم‌عامل نیستند.

مسیر ساخت ویندوز ابتدا فایل `GridResilienceStudio-signing-status.txt` با وضعیت `UNSIGNED` می‌سازد. اگر secrets محافظت‌شدهٔ `WINDOWS_CERT_BASE64` و `WINDOWS_CERT_PASSWORD` و variable سازمانی `AUTHENTICODE_TIMESTAMP_URL` موجود باشند، workflow گواهی را به‌صورت موقت از محیط runner بازسازی می‌کند، با `signtool` امضا و verify می‌کند و سپس فایل گواهی را حذف می‌کند. SignTool برای امضا، اعتبارسنجی و timestamp فایل‌های امضاشدهٔ ویندوز استفاده می‌شود. [7]

> هیچ گواهی، گذرواژه، کلید خصوصی یا endpoint حساس را در مخزن، کد منبع یا release asset قرار ندهید. تا پیش از نصب گواهی code-signing و تنظیم protected secrets، Releaseها عمداً با وضعیت شفاف **unsigned** منتشر می‌شوند.

## ساخت EXE در ویندوز

```powershell
python -m pip install --upgrade pip -r requirements-build.txt
pyinstaller --noconfirm --clean --onefile --windowed --name GridResilienceStudio --collect-all tkinter grid_resilience_desktop.py
```

خروجی در `dist/GridResilienceStudio.exe` قرار می‌گیرد. GitHub Actions آزمون‌ها را روی Python 3.10 تا 3.13 اجرا می‌کند، EXE را روی runner ویندوز می‌سازد، checksum SHA-256 و وضعیت امضا را تولید می‌کند و فقط برای تگ‌های `v*` آن‌ها را به Release ضمیمه می‌کند.

## نقشهٔ راه تجاری

| اولویت | قابلیت | دلیل |
|---|---|---|
| P1 | AC-OPF غیرخطی با solver تأییدشده و benchmarkهای استاندارد | تبدیل post-check فعلی به بهینه‌سازی یکپارچه و قابل‌اعتبارسنجی |
| P1 | SCOPF، N-2، common-mode و اقدام اصلاحی | تحلیل امنیت پس از رخداد در سطح بازار و بهره‌برداری |
| P1 | profileهای کامل CGMES و conformance test suite | تبادل‌پذیری واقعی بین فروشندگان و TSOها |
| P1 | امضای Authenticode با HSM/Trusted Signing و SBOM | زنجیرهٔ تأمین تجاری و اعتماد کاربر ویندوز |
| P2 | SSO/OIDC، سیاست رمزنگاری پروژه، retention و immutable audit storage | استقرار سازمانی چندکاربره |
| P2 | transformer/tap، سه‌فاز نامتعادل، اتصال کوتاه و حفاظت | پوشش مطالعات شبکهٔ توزیع و انتقال |
| P3 | digital twin، اتصال EMS/DMS/SCADA با gateway ایزوله | هم‌گرایی با عملیات بدون ایجاد ریسک دسترسی مستقیم |

## مجوز

این پروژه تحت مجوز [MIT](LICENSE) منتشر می‌شود. برای عرضهٔ تجاری با اجزای اختصاصی، مدل مجوزدهی دوگانه و تفکیک روشن ماژول‌های متن‌باز از بسته‌های سازمانی توصیه می‌شود.

## منابع

[1]: https://matpower.org/documentation/ref-manual/legacy/functions/opf.html "MATPOWER — OPF"
[2]: https://jump.dev/JuMP.jl/stable/tutorials/applications/optimal_power_flow/ "JuMP — AC Optimal Power Flow"
[3]: https://labs.ece.uw.edu/pstca/formats/cdf.txt "IEEE Common Data Format"
[4]: https://matpower.org/docs/ref/matpower4.0/cdf2matp.html "MATPOWER — CDF conversion caveats"
[5]: https://www.entsoe.eu/digital/common-information-model/cim-for-grid-models-exchange/ "ENTSO-E — CIM for Grid Models Exchange"
[6]: https://powsybl.readthedocs.io/projects/powsybl-core/en/stable/grid_exchange_formats/cgmes/import.html "PowSyBl — CGMES Import"
[7]: https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool "Microsoft — SignTool"
