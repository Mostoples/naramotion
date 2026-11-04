"""Unduh SEMUA file keluaran kernel Kaggle (CLI resmi hanya mengambil halaman pertama, ±500 file).
Pemakaian: python tools/kaggle_output_all.py <owner/kernel> <folder> [regex]
"""
import os, re, sys, requests
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest

kernel, out = sys.argv[1], sys.argv[2]; pat = re.compile(sys.argv[3]) if len(sys.argv) > 3 else None
owner, slug = kernel.split("/")
api = KaggleApi(); api.authenticate()
n = skip = page = 0; token = None
with api.build_kaggle_client() as k:
    while True:
        req = ApiListKernelSessionOutputRequest(); req.user_name = owner; req.kernel_slug = slug
        if token: req.page_token = token
        res = k.kernels.kernels_api_client.list_kernel_session_output(req); page += 1
        for it in res.files or []:
            if pat and not pat.search(it.file_name): continue
            dst = os.path.join(out, it.file_name)
            if os.path.exists(dst) and os.path.getsize(dst) > 0: skip += 1; continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with requests.get(it.url, stream=True, timeout=120) as r, open(dst, "wb") as f:
                for ch in r.iter_content(1 << 16): f.write(ch)
            n += 1
        token = res.next_page_token
        if not token: break
print(f"{kernel}: {page} halaman, {n} diunduh, {skip} sudah ada")
