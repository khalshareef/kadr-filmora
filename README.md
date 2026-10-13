# Kadr for Filmora · كادر لفيلمورا

**[العربية](#بالعربي) · [English](#english)**

---

## بالعربي

«كادر» باقة مجانية لـ Claude Code بتخلّي Claude يعمل **مشاريع فيلمورا 16 حقيقية (.wfp) قابلة للتعديل بالكامل** —
مقاطع، صور، نصوص فيلمورا أصلية، إفكتات، فلاتر، أوفرلايات، ترانزشنات، قص على الإيقاع، كابشن، موشن غرافيك،
موسيقى ومؤثرات صوتية — بكتابة ملف المشروع مباشرة.

ما في تحكّم بالشاشة ولا ضغط أزرار: Claude بيكتب الملف، بيفحصه، بيضيفه لشاشة المشاريع بفيلمورا، وإنت بتفتحه
وبتكمّل عليه متل أي مشروع عملته بإيدك. كل شي بيصير على جهازك — ما في رفع لأي ملف.

### شو بتقدر تطلب؟
- «اعملي ريل 30 ثانية من الكليبات بهالمجلد على هالأغنية، قص على الإيقاع، ستايل فيلوسيتي»
- «هاد تعليقي الصوتي — حطلي كابشن عربي كلمة بكلمة، وخليني اختار الخط من الخطوط اللي عندي»
- «اعملي موشن غرافيك عمودي يشرح هالفكرة بثلاث مشاهد، مع أصوات خفيفة من مكتبتي»
- «شو الإفكتات اللي عندي بتناسب ستايل ريترو؟»
- «المشروع ما فتح» ← بيقرأ سجلات فيلمورا وبيعرف السبب

### المهارات (9)
| المهارة | شو بتعمل |
|---|---|
| `filmora-core` | من وصف المشروع لملف فيلمورا جاهز: بناء، فحص، وإضافة لشاشة المشاريع |
| `filmora-text` | نصوص فيلمورا أصلية قابلة للتعديل، كابشن من ملفات الترجمة أو توقيت الكلمات، حجم النص حسب دوره وحسب الخط |
| `filmora-fx-library` | يختار من الإفكتات والترانزشنات المنزّلة عندك حسب الستايل والطاقة والاستخدام (379 مصنّفة) |
| `filmora-beat-edit` | تحليل الأغنية (سرعة، ضربات، ذروة، استراحة) وقص الكليبات عليها |
| `filmora-edit-styles` | ستايلات جاهزة: فيلوسيتي، غليتش، تريلر سينمائي، رياضة، فلوغ هادي، ريترو، نصوص متحركة… |
| `filmora-design-system` | ألوان، خطوط عربي وإنجليزي، مناطق آمنة، وعناصر رسومية شفافة |
| `filmora-motion` | موشن غرافيك حقيقي: رسم خطوط، أشكال بتتركّب، رسوم بيانية، حركة كاميرا وضبابية حركة — كل مشهد كليب |
| `filmora-sfx` | يفهرس مكتبة أصواتك ويختار أصوات خفيفة ناعمة ويحطها بالضبط على الحركة (بدون أجراس) |
| `filmora-troubleshoot` | يقرأ سجلات فيلمورا ويحدد سبب المشكلة وحلّها |

### المتطلبات
- ويندوز + Wondershare Filmora 16 (مجرّب على 16.0.12).
- Python 3.10 أو أحدث، و ffmpeg/ffprobe موجودين على الـPATH.
- `pip install -r requirements.txt` وبعدها `python -m playwright install chromium`.
- اختياري لترجمة الكلام العربي بدقة: `pip install faster-whisper` (موديل large-v3).

### التثبيت
جوّا Claude Code:
```
/plugin marketplace add khalshareef/kadr-filmora
/plugin install kadr-filmora@kadr
```
(أو حط المسار المحلي لهالمجلد بدل `khalshareef/kadr-filmora`.)

أول مرة قول لـ Claude: «جهّز كادر» — بيعمل فهرس للإفكتات المنزّلة بفيلمورا عندك. إذا عندك مكتبة مؤثرات صوتية،
قلّه وين هي وبيفهرسها كمان.
(بالأوامر: `python scripts/catalog_filmora.py` للإفكتات، و`python scripts/sfx_catalog.py scan "D:/Sound Effects"` للأصوات.)

### وين بينحفظ المشروع؟
بالمجلد اللي فاتح فيه محادثة Claude Code (أي درايف). بدك مجلد ثابت؟ قول لـ Claude، أو:
`python scripts/filmora_paths.py set project_dir "D:/Filmora Projects"`.
الأفضل يكون فيلمورا مسكّر وقت يبني Claude المشروع، حتى يبيّن بشاشة المشاريع؛ وإلا افتحه من File ▸ Open Project.

### كمان بيكتب بالملف
- السرعة: ثابتة، منحنيات فيلمورا الجاهزة (Montage، Hero moment، Bullet time…)، منحنى خاص، عكس، وتنعيم الحركة.
- الماسكات: دائرة، مستطيل، خط، خطين، نجمة، قلب، نص، صورة — وكمان متحركة.
- أنيميشن النصوص الجاهزة بفيلمورا (دخول، خروج، متكرر) — حوالي 150 بيجوا مع البرنامج. كتير منها عليه علامة
  الاشتراك المدفوع بفيلمورا.
- تحريك قيم أي إفكت أو فلتر مع الوقت، وتحريك مستوى الصوت.
- موشن غرافيك على طبقات: الخلفية لحال وكل عنصر شفاف لحال، بحواف نظيفة.

- طرق الدمج الـ18، وأكتر من ماسك على نفس المقطع (جمع، طرح، تقاطع).
- قص الشخص من الخلفية (يحسبه فيلمورا على جهازك بدون نقاط).
- أشكال مرسومة (مستطيل، دائرة، سهم، نجمة، مضلّع، خط) وخطوط بترسم حالها.
- تقسيم الشاشة على الخط الزمني نفسه (2، 3، 4 أجزاء، قطري) — كل جزء مقطع باين.
- تتبّع الحركة: نص أو صورة أو شكل بيلحق شي متحرك بالفيديو.
- مسار ترجمة أصلي بفيلمورا، وكابشن ديناميكي (الكلمة اللي عم تنقال بلون تاني) من تفريغنا للصوت — بدون نقاط.

### الحدود الحالية
- الميزات اللي بتصرف نقاط الذكاء الاصطناعي المدفوعة بفيلمورا (تحويل الكلام لنص، الكابشن الذكي، توليد صوت وصور)
  بتضل بإيدك. الكابشن بيجي من تفريغ الصوت عندنا بدالها.

### تواصل
للتعاون التجاري، الشراكات، أو أي استفسار: **kadr.studio3@gmail.com**
للمشاكل والاقتراحات: افتح طلب جديد بصفحة المستودع (Issues).

### تنبيه
مشروع مستقل وغير رسمي، ما إلو علاقة بـ Wondershare ولا مدعوم منها. صيغة الملف مفهومة من مشاريع المستخدم نفسه —
احتفظ بنسخة من مشاريعك المهمة. «Filmora» علامة تجارية لأصحابها. الرخصة: MIT.

---

## English

Kadr is a free Claude Code plugin that lets Claude create **native, fully editable Wondershare Filmora 16 projects
(.wfp)** — video and image clips, real Filmora titles, effects, filters, overlays, transitions, beat-synced cuts,
captions, motion graphics, music and SFX — by writing the project file directly.

No screen automation: Claude writes the file, checks it, adds it to Filmora's project list, and you open it and keep
editing like any project you made by hand. Everything runs on your PC; nothing is uploaded.

### Try asking
- "Make a 30 s reel from the clips in this folder on this song, cut on the beat, Velocity style"
- "Here's my voice-over — add word-by-word Arabic captions and let me pick the font from the ones I have"
- "Make a vertical motion-graphics piece explaining this idea in three scenes, with soft sounds from my library"
- "Which of my effects fit a retro look?"
- "The project won't open" → reads Filmora's logs and finds the cause

### Skills
| skill | what it does |
|---|---|
| `filmora-core` | JSON spec → .wfp → integrity check → Filmora project list; saving rules; script map |
| `filmora-text` | editable titles, captions from SRT/word timings, role-based sizing per font, contrast check, safe areas |
| `filmora-fx-library` | pick installed effects/transitions by style, energy and use (379 hand-tagged) |
| `filmora-beat-edit` | tempo/beat/kick/drop analysis, cut grid, beat-synced draft spec |
| `filmora-edit-styles` | recipes: Velocity, Glitch Party, Cinematic Trailer, Hype, Smooth Vlog, Retro VHS, Kinetic Type… |
| `filmora-design-system` | palettes, Arabic/Latin font pairing, safe areas, transparent PNG elements |
| `filmora-motion` | real motion graphics: time-driven HTML/SVG pages → one clip per scene (camera flights, line drawing, springs, motion blur), premium workflow, 10 named styles + more |
| `filmora-sfx` | catalog of your own SFX library; soft Foley picks with peak-aligned single hits; no bells |
| `filmora-troubleshoot` | Filmora log diagnosis, symptom → fix table, template re-extraction |

### Requirements
- Windows, Wondershare Filmora 16 (tested on 16.0.12).
- Python 3.10+, ffmpeg/ffprobe on PATH.
- `pip install -r requirements.txt`, then `python -m playwright install chromium`.
- Optional: `pip install faster-whisper` to transcribe a voice-over for captions (use the large-v3 model for Arabic).

### Install
Inside Claude Code:
```
/plugin marketplace add khalshareef/kadr-filmora
/plugin install kadr-filmora@kadr
```
(or use the local path of this folder instead of `khalshareef/kadr-filmora`).

First run: ask Claude to "set up Kadr" — it builds the catalog of effects installed in your Filmora. If you have a
sound-effects library, tell Claude where it is and it will catalog that too
(commands: `python scripts/catalog_filmora.py`, `python scripts/sfx_catalog.py scan "D:/Sound Effects"`).

Projects are saved in the folder the Claude Code conversation was opened in (any drive), unless you set
`python scripts/filmora_paths.py set project_dir "<folder>"`. Close Filmora while projects are built so they appear on
its home screen (otherwise use File ▸ Open Project).

### Also written into the file
- Speed: constant, Filmora's ramp presets (Montage, Hero moment, Bullet time…), custom curves, reverse, frame blending.
- Masks: ellipse, rectangle, line, double line, star, heart, text and image masks — animated too.
- Filmora's own text animation presets (in, out, loop; ~150 bundled). Many carry Filmora's premium mark (paid plan).
- Keyframed values of any effect or filter, and volume automation.
- Layered motion graphics: background and every element as separate transparent clips with clean edges.

- All 18 blend modes, several masks per clip (add, subtract, intersect).
- AI Portrait Cutout (computed by Filmora on your PC, no credits).
- Native shapes (rectangle, ellipse, arrow, star, polygon, line) and self-drawing lines.
- Split screens built on the main timeline (2, 3, 4 parts, diagonal) — every part a visible clip.
- Motion tracking: a text, image or shape follows a moving object in the video.
- Native Filmora subtitle track and Dynamic Captions (spoken word highlighted) from our own word timings — no credits.

### Not supported yet
- Filmora features that spend its paid AI credits (speech-to-text, AI captions, AI voice/image tools) stay manual;
  captions come from our own transcription instead.

### Contact
Business, partnerships or licensing: **kadr.studio3@gmail.com**
Bugs and ideas: open an issue on this repository.

### Disclaimer
Independent, unofficial project — not affiliated with or endorsed by Wondershare. The file format was understood from
the user's own projects; keep backups of important projects. "Filmora" is a trademark of its owner.

License: MIT.
