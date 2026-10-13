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
- `pip install -r requirements.txt` وبعدها `playwright install chromium`.
- اختياري: `pip install faster-whisper` لتفريغ التعليق الصوتي لكابشن.

### التثبيت
جوّا Claude Code:
```
/plugin marketplace add khalshareef/kadr-filmora
/plugin install kadr-filmora@kadr
```
(أو حط المسار المحلي لهالمجلد بدل `khalshareef/kadr-filmora`.)

أول مرة قول لـ Claude: «جهّز كادر» — بيعمل فهرس للإفكتات المنزّلة بفيلمورا عندك. إذا عندك مكتبة مؤثرات صوتية،
قلّه وين هي وبيفهرسها كمان.

### وين بينحفظ المشروع؟
بالمجلد اللي فاتح فيه محادثة Claude Code (أي درايف). بدك مجلد ثابت؟ قول لـ Claude، أو:
`python scripts/filmora_paths.py set project_dir "D:/Filmora Projects"`.

### الحدود الحالية
- ما بينكتبوا بالملف لسا: Speed Ramp، قوالب Split Screen، أنيميشن النصوص الجاهزة بفيلمورا، الماسكات، ميزات الذكاء
  الاصطناعي، وتحريك قيم الإفكتات. Claude بيقلك شو تكبس بعد ما تفتح المشروع.
- طبقات الموشن الشفافة (كل عنصر لحال) تجريبية — بيبين حواف بيضا خفيفة بفيلمورا. الافتراضي: كليب واحد لكل مشهد.

### شكر وإلهام
أفكار الموشن مستوحاة (أفكار بس، بدون نسخ كود) من: prompt-motion.com،
[HyperFrames](https://github.com/heygen-com/hyperframes)، [cinetic](https://github.com/Leonxlnx/cinetic)،
[product-film-skill](https://github.com/Rieranthony/product-film-skill)، [brag](https://github.com/latent-spaces/brag).

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
| `filmora-motion` | real motion graphics: time-driven HTML/SVG pages → one clip per scene (camera flights, line drawing, springs, motion blur), premium workflow, 18 styles |
| `filmora-sfx` | catalog of your own SFX library; soft Foley picks with peak-aligned single hits; no bells |
| `filmora-troubleshoot` | Filmora log diagnosis, symptom → fix table, template re-extraction |

### Requirements
- Windows, Wondershare Filmora 16 (tested on 16.0.12).
- Python 3.10+, ffmpeg/ffprobe on PATH.
- `pip install -r requirements.txt`, then `playwright install chromium`.
- Optional: `pip install faster-whisper` to transcribe a voice-over for captions.

### Install
Inside Claude Code:
```
/plugin marketplace add khalshareef/kadr-filmora
/plugin install kadr-filmora@kadr
```
(or use the local path of this folder instead of `khalshareef/kadr-filmora`).

First run: ask Claude to "set up Kadr" — it builds the catalog of effects installed in your Filmora. If you have a
sound-effects library, tell Claude where it is and it will catalog that too.

Projects are saved in the folder the Claude Code conversation was opened in (any drive), unless you set
`python scripts/filmora_paths.py set project_dir "<folder>"`.

### Not supported yet
- Speed ramps, split-screen templates, Filmora's built-in text animation presets, masks, AI features, keyframed effect
  parameters. Claude tells you the clicks to add them after opening.
- Transparent per-element motion layers are experimental (a faint white edge shows in Filmora); the default is one
  clip per scene.

### Credits
Motion ideas inspired by (ideas only, no copied code): prompt-motion.com,
[HyperFrames](https://github.com/heygen-com/hyperframes), [cinetic](https://github.com/Leonxlnx/cinetic),
[product-film-skill](https://github.com/Rieranthony/product-film-skill), [brag](https://github.com/latent-spaces/brag).

### Disclaimer
Independent, unofficial project — not affiliated with or endorsed by Wondershare. The file format was understood from
the user's own projects; keep backups of important projects. "Filmora" is a trademark of its owner.

License: MIT.
