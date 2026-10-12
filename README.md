# hergunyeni-videolar

@hergunyeni_teknoloji Instagram hesabına saatte bir otomatik paylaşım yapan zamanlanmış görevin çalışma alanı.

- `tools/render_reel.py` — yazı + animasyonlu 1080x1920 Reel ve 1080x1350 karusel üretici
  - Reel: `python3 tools/render_reel.py spec.json cikti.mp4`
  - Karusel: `python3 tools/render_reel.py --carousel spec.json cikti_oneki`
- `tools/muzik.py` — her videoya özel telifsiz fon müziği üretir (render_reel.py otomatik çağırır; spec'te `"music"`: enerjik | chill | gizem | auto | none)
- `tools/medya_yukle.sh` — dosyaları `medya` dalına koyup (geçmişsiz, force-push) Metricool'a verilecek jsDelivr linklerini basar
- `log/posts.jsonl` — her paylaşımın kaydı (tarih, tür, kategori, konu, kaynak, Metricool id)
- `log/analiz.md` — günlük performans analizi notları
- `log/specs/` — her paylaşımın sahne metni (spec.json)

`medya` dalı her çalışmada baştan yazılır; videolar Metricool'a kopyalandıktan sonra burada tutulmaz.
