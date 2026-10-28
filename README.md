# NaraMotion

Platform motion capture dan pelatihan berbasis AI untuk tari tradisional Indonesia — non-komersial, untuk pelestarian budaya.
*Low-cost motion capture and AI coaching for Indonesian traditional dance (non-commercial, cultural preservation).*

**Live:** https://naramotion.web.app · **Ekosistem (rich picture):** https://naramotion.web.app/ekosistem.html

## Isi repositori
| Folder | Isi |
|---|---|
| `index.html`, `css/`, `js/`, `assets/` | Web statis (Studio, Kelas Tari, Arsip) di Firebase Hosting |
| `ml/kaggle/` | Kernel Kaggle: ekstraksi pose RTMW, pelatihan TCN, IMU sintetis AIST++, IMU Turki, SAM 3D Body, Motion2MixamoRig |
| `ml/DATASETS.md` | Daftar dataset, lisensi, dan atribusi |
| `tools/` | Skrip build: video profil, figur & paper, rich picture, ekspor web |
| `blender/` | Adegan sinematik (Blender CLI) |
| `paper/` | Paper I2ASPO (PDF, DOCX, Markdown, figur) |
| `media/deck/` | Deck 12 slide (PDF, PPTX) |

Data mentah, hasil Kaggle, dan video tidak disimpan di repo ini.

## Menjalankan web secara lokal
```bash
python -m http.server 8080   # lalu buka http://localhost:8080
firebase deploy --only hosting --project naramotion
```

## Data & lisensi pihak ketiga
- Video Dataset of Woman/Male Basic Balinese Dance Movement — Hendrawan dkk., Mendeley Data, CC BY 4.0
- AIST++ (anotasi CC BY 4.0) · Turkish Folk Dance IMU Dataset (CC BY 4.0)
- SAM 3D Body (Meta, SAM License) · Motion2MixamoRig (Apache 2.0) dengan SMPL-X & MANO (lisensi riset non-komersial; file model **tidak** disertakan) · karakter Y Bot (Adobe Mixamo)
- Data Javanese VICON dan Lenggang Nyai tanpa lisensi terbuka: hanya analisis internal, tidak didistribusikan.

## Tim
SMANSA: Kim Arumi Malika Putri, Afra Na’ila Arkana, Anyaila Wahyu · ABBS: Khaifat Attallah Wibowo, Nabila Azalea, Khairan Athaya Wibowo
