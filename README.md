# hergunyeni-videolar

@hergunyeni_teknoloji Instagram hesabına otomatik paylaşılan Reels videoları ve görselleri.

- `videos/` — yayınlanan videolar ve görseller (Metricool buradaki herkese açık linkten alıyor)
- `tools/render_reel.py` — yazı + animasyonlu 1080x1920 Reel üretici (`python3 tools/render_reel.py spec.json cikti.mp4`)
- `log/posts.jsonl` — her paylaşımın kaydı: tarih, tür, konu, kaynak
- `log/*.spec.json` — her videonun sahne metni
