# بۆتی ڕیاکشن لەسەر Vercel

دوو فایل هەن: `api/index.py` و `vercel.json`. هەردووکیان دەبێت لە GitHub دابنرێن.

## ١. GitHub

1. بچۆ github.com و ئەکاونتێک دروست بکە.
2. **New repository** دابگرە، ناوێکی بۆ دابنێ (بۆ نمونە `reaction-bot`)، پاشان **Create repository**.
3. لەناو repository: **Add file** ← **Create new file**.
4. لە خانەی ناوی فایل بنووسە: `api/index.py` (ئەو `/` خۆی پۆشەی `api` دروست دەکات).
5. ناوەڕۆکی فایلی `api/index.py` کۆپی بکە و لێرە دایبنێ. **Commit changes** دابگرە.
6. هەمان شت بۆ فایلی دووەم: ناوی `vercel.json`، ناوەڕۆکەکەی دابنێ، Commit.

## ٢. Vercel

1. بچۆ vercel.com ← **Add New** ← **Project**.
2. repository ەکەت هەڵبژێرە ← **Import** ← **Deploy**.
3. دوای تەواوبوون، ناونیشانی پڕۆژەکەت دەبینیت، وەک `https://reaction-bot.vercel.app`.

## ٣. Redis (بۆ ئەوەی ئەپەکە بتوانێت ڕێکخستنەکان بگۆڕێت)

1. لە پڕۆژەکەت: **Storage** ← **Create Database** ← **Upstash Redis** (یان Redis) ← پلانی بێخەرج ← **Connect to project**.
2. Vercel خۆی `KV_REST_API_URL` و `KV_REST_API_TOKEN` دادەنێت.

## ٤. وشە نهێنییەکان

**Settings** ← **Environment Variables**:

| ناو | نرخ |
|---|---|
| `BOT_TOKEN` | تۆکێنی نوێی بۆت (لە @BotFather بە `/revoke` وەریبگرە) |
| `ADMIN_KEY` | وشەیەکی نهێنی درێژ، لانیکەم 8 پیت |

پاشان **Deployments** ← سێ خاڵەکە ← **Redeploy**.

## ٥. چالاککردنی بۆتەکە (تەنها جارێک)

لە براوزەر بیکەرەوە (ناونیشانی خۆت و `ADMIN_KEY`ـی خۆت دابنێ):

`https://reaction-bot.vercel.app/api/setup?key=ADMIN_KEY`

ئەگەر `"ok": true` بینی، بۆتەکە ئامادەیە.

## ٦. ئەپەکە

دۆخی **سێرڤەر** هەڵبژێرە ← ناونیشانی Vercel و `ADMIN_KEY` بنووسە ← **پەیوەستبوون**.

## ئاگاداری

- **دۆخی "ئەم مۆبایلە" بەکار مەهێنە** کاتێک Vercel کار دەکات؛ ئەو دۆخە Webhook ەکە دەسڕێتەوە. ئەگەر ئەمەت کرد، دووبارە ناونیشانی `setup` بکەرەوە.
- داشبۆردی کۆن و `reaction.py` و `server.py` یش بوەستێنە.
- ئەگەر `setup` دەڵێت 401 یان بۆتەکە ڕیاکشن ناکات، لە Vercel: **Settings** ← **Deployment Protection** ← Vercel Authentication بکوژێنەوە، و ناونیشانی سەرەکیی پڕۆژەکە بەکار بهێنە نەک ناونیشانی Preview.
- یەکەم نامە دوای ماوەیەکی بێ بەکارهێنان ڕەنگە چەند چرکەیەک درەنگتر ڕیاکشن بکرێت.
- دواکەوتن لە ئەپەکە لە 5 چرکە زیاتر ناکات.
