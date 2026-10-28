"""NaraMotion · cek akses SAM 3D Body: GPU Kaggle + token Hugging Face (Kaggle Secret bernama HF_TOKEN)."""
import subprocess, json, urllib.request
print(subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", shell=True, capture_output=True, text=True).stdout)
try:
    from kaggle_secrets import UserSecretsClient
    tok = UserSecretsClient().get_secret("HF_TOKEN")
except Exception as e:
    tok = None; print("HF_TOKEN belum terpasang sebagai Secret:", e)
if tok:
    for repo in ("facebook/sam-3d-body-dinov3",):
        req = urllib.request.Request(f"https://huggingface.co/api/models/{repo}/tree/main", headers={"Authorization": f"Bearer {tok}"})
        try:
            files = json.load(urllib.request.urlopen(req)); print("AKSES OK", repo, [f["path"] for f in files][:10])
        except Exception as e:
            print("BELUM ADA AKSES", repo, e)
