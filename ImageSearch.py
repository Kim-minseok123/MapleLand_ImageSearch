import streamlit as st
from pathlib import Path
from PIL import Image
import imagehash
from rembg import remove

# --------------------------- Configuration -----------------------------------
IMAGES_DIR = Path("Images")
HASH_SIZE = 16  # pHash size ⇒ 64-bit hash

# ---------------------- Helper: perceptual hashing ---------------------------
@st.cache_data
def load_library_hashes():
    hashes = {}
    if not IMAGES_DIR.exists():
        st.error(f"Images 디렉토리 '{IMAGES_DIR}'가 존재하지 않습니다.")
        return hashes
    for path in IMAGES_DIR.iterdir():
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp", ".gif"}:
            continue
        try:
            img = Image.open(path)
            if img.format == "GIF":
                img = img.convert("RGBA")
            hashes[path.name] = imagehash.phash(img, hash_size=HASH_SIZE)
        except Exception as e:
            st.warning(f"[WARN] 해시 계산 실패: {path.name}: {e}")
    if not hashes:
        st.error("Images 디렉토리에 지원되는 이미지 파일이 없습니다.")
    return hashes

# --------------------------- Main App -----------------------------------------
def main():
    st.set_page_config(page_title="Image Matcher Web", layout="centered")
    st.title("🖼️ Image Matcher Web")
    st.write("이미지를 업로드하면 라이브러리 내에서 가장 비슷한 파일명을 찾아드립니다.")

    # 사이드바 설정
    st.sidebar.header("설정")
    auto_resize = st.sidebar.checkbox("배경 제거 후 자동 리사이즈", value=True)

    # 라이브러리 해시 로드 (캐시 적용)
    lib_hashes = load_library_hashes()
    
    # 이미지 업로드
    uploaded = st.file_uploader("비교할 스크린샷 업로드", type=["png","jpg","jpeg","bmp","gif"])
    if not uploaded:
        st.info("이미지를 업로드해주세요.")
        return

    # 처리 시작
    with st.spinner("분석 중... 잠시만 기다려주세요."):
        pil = Image.open(uploaded)
        # 배경 제거
        pil_no_bg = remove(pil).convert("RGBA")
        # 자동 리사이즈
        if auto_resize:
            alpha = pil_no_bg.split()[-1]
            bbox = alpha.getbbox()
            if bbox:
                pil_no_bg = pil_no_bg.crop(bbox).resize(pil.size, Image.LANCZOS)

        # 퍼셉추얼 해시 계산
        target_hash = imagehash.phash(pil_no_bg, hash_size=HASH_SIZE)

        # 최적 매칭 찾기
        best_name, best_dist = None, float('inf')
        for name, h in lib_hashes.items():
            dist = target_hash - h
            if dist < best_dist:
                best_name, best_dist = name, dist

    # 결과 표시
    if best_name:
        result = Path(best_name).stem
        st.success(f"✅ Best match: **{result}** (해시 거리: {best_dist})")
        # 복사를 위한 텍스트 필드
        st.text_input("파일명 복사용", value=result, key="copy_field")
    else:
        st.error("❌ 매칭되는 이미지가 없습니다.")

if __name__ == "__main__":
    main()