# Internetga joylash (Render + Neon, bepul)

## 1. Baza (Neon)
1. neon.tech da ro'yxatdan o'ting, yangi Project yarating.
2. **Connection string** ni nusxalang (`postgresql://...?sslmode=require`).

## 2. GitHub
1. github.com da yangi **private** repository oching.
2. `academy-uz-site` papkasi ichidagilarni yuklang (`.env` va `academy.db` yuklanmaydi, `.gitignore` buni ta'minlaydi).

## 3. Render
1. render.com -> **New -> Blueprint** -> repositoryni tanlang (`render.yaml` avtomatik o'qiladi).
2. So'ralganda kiriting:
   - `DATABASE_URL` = Neon connection string
   - `ADMIN_PASSWORD` = o'zingiz o'ylagan **yangi** kuchli parol
3. Deploy tugagach sayt `https://academy-uz.onrender.com` (yoki Render bergan manzil) da ochiladi. Manzil boshqacha bo'lsa, `CORS_ORIGINS` ni shunga moslang.
4. Kirish: login `academyadmin`, parol - 2-qadamda kiritganingiz.

## Bilish kerak
- Bepul Render 15 daqiqa faolsiz tursa uxlaydi; birinchi kirish 30-60 soniya kutadi.
- Hisoblar, o'quvchilar, arizalar Neon'da saqlanadi va yo'qolmaydi.
- **Media fayllar (rasm/video/PDF) Render'da vaqtinchalik** - qayta deploydan keyin o'chadi. Doimiy saqlash uchun Cloudinary/S3 ulash kerak.
- Birinchi kirgach Settings'da admin loginini/parolini o'zgartirishingiz mumkin.
