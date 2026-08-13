# Grid Resilience Studio v1.2.0

نسخهٔ `v1.2.0` دامنهٔ غربال‌گری مهندسی Grid Resilience Studio را با تحلیل گذرا، N-2، گزارش‌های قابل‌ممیزی و سخت‌سازی زنجیرهٔ انتشار گسترش می‌دهد.

| حوزه | تغییر اصلی |
|---|---|
| پایداری گذرا | شبیه‌سازی multi-machine swing equation، رویداد fault/clearing، منحنی rotor angle/speed و CCT screening bound |
| قابلیت اطمینان | تحلیل جفت‌خروجی N-2، cascade overload screening، رتبه‌بندی ریسک و پیشنهادهای غیرالزام‌آور بازبینی |
| رابط Windows | نمودارهای گذرای متحرک، topology drag-and-drop، حالت روشن/تیره و پنل‌های topology/transient جداشدنی |
| گزارش | خروجی HTML و PDF شامل منشأ مدل، زمان تولید و هشدار صریح محدودیت مهندسی |
| CI/CD | matrix آزمون Python 3.10–3.13، artifact وضعیت امضا، checksum، changelog، provenance attestation و مستندات Authenticode/Azure Artifact Signing |

> این نسخه ابزار غربال‌گری مهندسی است. خروجی transient stability کاهش‌یافته است و جایگزین مطالعات تأییدشدهٔ RMS/EMT، حفاظت، بهره‌برداری بلادرنگ یا تصمیم کنترل میدان نیست.

## موارد منتشرشده

Release شامل `GridResilienceStudio.exe`، checksum SHA-256، فایل متنی و JSON وضعیت امضا، changelog و GitHub provenance attestation است. اگر گواهی سازمانی و protected secrets پیکربندی نشده باشند، وضعیت امضا عمداً `UNSIGNED` اعلام می‌شود؛ این موضوع ادعای امضای دیجیتال ایجاد نمی‌کند.
