# WarDogs Tools

واجهة Windows مبنية بـ PySide6 لإدارة اختيار الفريق وAFK وTank والشراء السريع في WARDOGS. يعتمد التطبيق على التقاط الشاشة ومناطق وإحداثيات محددة؛ قد تحتاج إلى ضبطه حسب دقة العرض وتخطيط اللعبة.

> **ملاحظة:** يتطلب التطبيق فتح اللعبة قبل تشغيل المهام. استخدام البرنامج يخضع لقواعد اللعبة وسياساتها.

## المتطلبات

- Windows 10 أو أحدث، 64-bit.
- Python 3.11 لتشغيل الشيفرة أو اختبارها.
- تثبيت Tesseract OCR على جهاز التطوير؛ المسار الافتراضي هو `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- لتشغيل وظائف يد التحكم الافتراضية، يلزم ViGEmBus. يضم المثبّت المُنشأ MSI للتعريف، ويطلب صلاحيات المسؤول عند تثبيته.
- Inno Setup 6 مطلوب لإنشاء ملف المثبّت.

## تشغيل من الشيفرة

من PowerShell داخل مجلد المشروع:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\app.py
```

يحفظ التشغيل من الشيفرة الإعدادات في `wardogs_gui_config.json` بجذر المشروع. هذا الملف محلي ومضاف إلى `.gitignore`.

## الاختصارات الافتراضية

| المفتاح | الوظيفة |
| --- | --- |
| F6 | تبديل اختيار الفريق |
| F5 | تشغيل/إيقاف Tank (يمكن تعطيل الاختصار من سويتش Tank) |
| F7–F10 | الشراء السريع (يمكن تعطيل الأزرار والاختصارات من سويتش Quick Buy) |
| End | إيقاف جميع المهام |

يمكن تعطيل أتمتة اختيار الفريق وزر Start واختصار F6 من سويتش اختيار الفريق؛ يبقى اختيار اللون متاحاً. يمكن تغيير الاختصارات من تبويب الإعدادات، كما يمكن تشغيل AFK يدوياً من الواجهة.

## الاختبار

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

تُشغّل اختبارات GitHub Actions على Windows وPython 3.11 عند كل push وpull request.

## إنشاء نسخة التوزيع

ثبت متطلبات البناء، ثم شغّل السكربت من PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build-release.ps1
```

ينشئ هذا مجلد التطبيق في `dist\WarDogsTools`. لإنشاء المثبّت، ثبّت Inno Setup 6 ثم شغّل:

```powershell
.\build-installer.ps1
```

ينشأ المثبّت في `dist\WarDogsTools-Setup.exe`. لا ترفع ملفات `dist` أو `build` إلى مستودع الشيفرة؛ أرفق المثبّت بإصدار GitHub Releases عند الحاجة. يتطلب بناء التطبيق تثبيت Tesseract على جهاز البناء. يمكن تحديد مساره عبر متغير البيئة `TESSERACT_DIR`.

للمزيد حول توزيع البرنامج والتبعيات، راجع [DISTRIBUTION.txt](DISTRIBUTION.txt) ورخصة ViGEmBus في `installer/licenses`.

## ملفات المشروع

- `app.py`: الواجهة الرئيسية المضمنة في التطبيق.
- `auto.py` و`autobay/main.py` و`tank/tankauto-relod.py`: سكربتات مستقلة؛ لا تدخل في بناء الواجهة الرئيسية.
- `tests/`: اختبارات الوحدة والتكامل.

## الترخيص

المشروع مرخّص وفق GNU General Public License v3.0؛ راجع [LICENSE](LICENSE). رخصة ViGEmBus المضمّنة تخص ذلك المكوّن فقط، ولا تستبدل ترخيص المشروع.

---

**English summary:** Windows/PySide6 control panel for WARDOGS team selection, AFK, Tank, and quick-buy features. See the sections above for setup, tests, and packaging instructions.
