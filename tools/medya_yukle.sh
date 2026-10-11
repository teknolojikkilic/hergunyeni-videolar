#!/usr/bin/env bash
# Kullanım: tools/medya_yukle.sh dosya1 [dosya2 ...]
#
# Verilen dosyaları 'medya' dalına TEK commit olarak koyar ve force-push eder.
# Geçmiş tutulmaz: her çalışmada dal baştan yazılır, böylece repo videolarla şişmez.
# (Metricool planlama anında dosyayı kendi sunucusuna kopyalıyor; eski dosyalara gerek kalmıyor.)
# Çıktı: her dosya için Metricool'a verilecek herkese açık jsDelivr linki, verilen sırayla.
set -euo pipefail
REPO_DIR=$(git rev-parse --show-toplevel)
REMOTE=$(git -C "$REPO_DIR" remote get-url origin)
TMP=$(mktemp -d)
for f in "$@"; do cp "$f" "$TMP/"; done
cd "$TMP"
git init -q -b medya
git remote add origin "$REMOTE"
git add -A
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -q -m "medya: $(date -u +%FT%TZ)"
git push -q -f origin medya
SHA=$(git rev-parse HEAD)
for f in "$@"; do
  echo "https://cdn.jsdelivr.net/gh/teknolojikkilic/hergunyeni-videolar@${SHA}/$(basename "$f")"
done
