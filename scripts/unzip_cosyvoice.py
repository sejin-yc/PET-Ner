#!/usr/bin/env python3
"""
CosyVoice_inference_only.zip 압축 해제 (Jetson/Linux용)
ZIP이 있는 디렉터리에서 실행하면 같은 위치에 CosyVoice/ 폴더가 생성됩니다.

사용법:
  cd /home/SSAFY
  python3 unzip_cosyvoice.py

또는 ZIP 경로 지정:
  python3 unzip_cosyvoice.py /home/SSAFY/CosyVoice_inference_only.zip
"""
import zipfile
import sys
from pathlib import Path

ZIP_NAME = "CosyVoice_inference_only.zip"


def main():
    if len(sys.argv) >= 2:
        zip_path = Path(sys.argv[1])
    else:
        # 1) 현재 작업 디렉터리, 2) 스크립트가 있는 디렉터리
        zip_path = Path.cwd() / ZIP_NAME
        if not zip_path.exists():
            zip_path = Path(__file__).resolve().parent / ZIP_NAME
    if not zip_path.exists():
        print(f"ZIP not found: {zip_path}")
        print("Usage: python3 unzip_cosyvoice.py [path/to/CosyVoice_inference_only.zip]")
        sys.exit(1)

    dest_dir = zip_path.parent
    print(f"Extracting {zip_path} -> {dest_dir}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    print("Done. CosyVoice/ folder created.")


if __name__ == "__main__":
    main()
