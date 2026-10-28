# Dataset tari untuk NaraMotion

Diperiksa 27 Okt 2026. "Lisensi" = yang tertulis di sumber; label lisensi pengunggah ulang di Kaggle tidak dianggap sah bila isinya diambil dari tempat lain.

## Bisa dipakai (lisensi jelas)

| Dataset | Isi | Lisensi | Kegunaan di NaraMotion |
| --- | --- | --- | --- |
| [Woman Basic Balinese Dance Movement](https://data.mendeley.com/datasets/s2gv9d6gpb) (Mendeley) | 1.740 video, 13 gerak dasar, 9 penari, 3 sudut | CC BY 4.0 | Sedang diproses: pose RTMW → pengenal gerak, gerak acuan Kelas Tari |
| [Male Basic Balinese Dance Movement](https://data.mendeley.com/datasets/tr9py7hzj4/1) (Mendeley) | 828 video, 11 gerak dasar putra, 4 penari | CC BY 4.0 | Tambahan gerak putra (pipeline sama) |
| [Turkish Folk Dance IMU](https://www.kaggle.com/datasets/berkaykarakis/turkish-folk-dance-imu-dataset) (Kaggle) | 5 node ESP32-C6 + MPU6050 (akselerometer + giroskop), 3 tari | CC BY 4.0 | Paling mirip perangkat kita: uji pipeline IMU, pengenal tari dari sensor |
| [AIST++](https://google.github.io/aistplusplus_dataset/) | 5,2 jam gerak 3D (SMPL), 10 genre, multi-kamera | Anotasi CC BY 4.0; video ikut ketentuan AIST Dance DB | Data pose 3D berkualitas; dasar "IMU sintetis" |

## Hanya untuk riset / perlu cek ulang

| Dataset | Catatan |
| --- | --- |
| [FineDance](https://github.com/THUSIGSICLAB/FineDance) | 14,6 jam mocap SMPL-H, 22 genre termasuk tradisional; lisensi di repo belum dicek isinya |
| Motorica Dance, PopDanceSet | Mocap tari; lisensi belum dikonfirmasi |
| AMASS, DIP-IMU, TotalCapture (dari ingatan, belum dicek) | Standar riset IMU-ke-pose; umumnya non-komersial |

## Hindari / jangan dipakai di produk

| Dataset | Alasan |
| --- | --- |
| github.com/widya-utami/dataset-taribali | Foto tanpa lisensi |
| Kaggle adiparamartha/dataset-tari-bali, sansudirman22552342/tari-pendet-bali | Label "Apache 2.0" dari pengunggah, tetapi foto tampak dikumpulkan dari web |
| Kaggle hasbishuhada/indonesian-traditional-dance | Foto, lisensi "Unknown" |
| Kaggle ziya07/multimodal-dance-motion-analysis-dataset | Unggahan ulang video AIST berlabel CC0 — pakai sumber aslinya |
| Dataset Gambyong/Remo/Topeng ([EMITTER](https://emitter.pens.ac.id/index.php/emitter/article/view/832)) | Tidak dirilis; sumbernya video YouTube |

## Temuan penelusuran lanjutan (27 Okt 2026)

| Sumber | Isi | Lisensi / status | Nilai untuk NaraMotion |
| --- | --- | --- | --- |
| [villaorlado/dance](https://github.com/villaorlado/dance) — Escobar Varela & Hernández-Barraza, [DSH 2019](https://academic.oup.com/dsh/advance-article/doi/10.1093/llc/fqy083/5299608) | **Mocap VICON tari Jawa**: 39 marker Plug-in Gait (±470 frame/klip), force plate, EMG, 6 akselerometer; tipe karakter gagah, halus/luruh, lanyap, jatayu, raksasa, wanara | Tanpa lisensi → **minta izin penulis** | Satu-satunya data gerak 3D tari Jawa yang ditemukan; cocok untuk Arsip & skor karakter (alus vs gagah) |
| [nandafirdaus/cool-tour-dance](https://github.com/nandafirdaus/cool-tour-dance) | Kerangka Kinect v1 (20 sendi, CSV) **Tari Lenggang Nyai** (Betawi), ±650 file; game Imagine Cup 2013 | Tanpa lisensi → minta izin | Contoh gerak Betawi untuk Kelas; kualitas Kinect rendah |
| [RamaPutraa/balinese_dance-detection](https://github.com/RamaPutraa/balinese_dance-detection) | 51 video + keypoint MediaPipe (.npy): Baris, Gopala, Pendet, Puspanjali, Sekar Jagat | Tanpa lisensi; sumber video tidak jelas | Hanya rujukan kelas tari Bali utuh |
| [rudyhendrawn/traditional-dance-video-classification](https://github.com/rudyhendrawn/traditional-dance-video-classification) | Kode VGG-LSTM/I3D penyusun dataset Bali Mendeley | MIT, **tanpa data** | Kode pembanding |
| [JAITI: ST-GCN 13 gerak Bali](https://ejournal.techcart-press.com/index.php/jaiti/article/view/253) | MediaPipe 33 titik + ST-GCN pada dataset Mendeley putri | Data tidak dibagikan | **Patokan akurasi: 99,4% uji** |
| Likok Pulo (Aceh), Kinect + HMM ([IEEE](https://ieeexplore.ieee.org/document/7048243)) | Gestur tari Aceh | Data tidak dirilis | Hubungi penulis |
| Topeng Cirebon, mocap ITB (Harry Nuriman) ([berita ITB](https://itb.ac.id/news/digitalizing-the-motion-of-traditional-dance-harry-nuriman-uses-motion-capture-technology/56583)) | Mocap Topeng Cirebon | Tidak publik | Calon kolaborasi |
| Mocap Saman, Cokek, Yapong, Merak, Incling (BVH) ([ResearchGate](https://www.researchgate.net/publication/315364126_Indonesian_traditional_dance_motion_capture_documentation)) | 5 tari, format BVH | Tidak publik | Calon kolaborasi |
| [ISI: IMU Arduino untuk mocap tari](https://journal.isi.ac.id/index.php/jags/article/view/1423) | Kajian IMU murah untuk dokumentasi tari | Makalah | Rujukan pembanding perangkat |
| Tari Melayu ([camelinca](https://github.com/camelinca/klasifikasi-gerak-dasar-tari-melayu)), Yospan, Sigeh Penguten, Likurai, CNN-LSTM ([BEEI](https://beei.org/index.php/EEI/article/view/11093)) | Klasifikasi gerak | Data privat / tidak dirilis | — |
| [Let's Dance (Georgia Tech)](https://www.cc.gatech.edu/cpl/projects/dance) | 1.000 video, 10 genre Barat | Riset; cek ketentuan | Pra-latih umum |

## Celah

Belum ada dataset terbuka untuk **tari Jawa** (Gambyong, Serimpi, Bedhaya) maupun data IMU tari Nusantara. Rekaman NaraMotion sendiri (10 node + video) akan menjadi dataset pertama jenis ini.
