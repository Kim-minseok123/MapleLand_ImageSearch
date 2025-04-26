import streamlit as st
from pathlib import Path
from PIL import Image
import imagehash
from rembg import remove
from streamlit_paste_button import paste_image_button as paste_btn

# --------------------------- Configuration -----------------------------------
IMAGES_DIR = Path("Images")
HASH_SIZE = 16  # pHash size ⇒ 64‑bit hash
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

# ---------------------- Helper: perceptual hashing ---------------------------
@st.cache_data(show_spinner=False)
def load_library_hashes():
    """Images/ 폴더의 모든 이미지를 미리 해싱해 dict 로 반환"""
    hashes = {}
    if not IMAGES_DIR.exists():
        st.error(f"Images 디렉토리 '{IMAGES_DIR}'가 존재하지 않습니다.")
        return hashes
    for path in IMAGES_DIR.iterdir():
        if path.suffix.lower() not in SUPPORTED_EXT:
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

# --------------------------- Utility – JS helpers ----------------------------
_clipboard_js = """
<script>
function copyText(text){
    navigator.clipboard.writeText(text);
    const evt = new Event("copied", {"bubbles":true});
    document.dispatchEvent(evt);
}
</script>
"""

# --------------------------- Main App -----------------------------------------

def main():
    st.set_page_config(page_title="Image Matcher Web", layout="centered")
    st.title("🖼️ Image Matcher Web – Paste & Match (Clipboard Button)")

    st.write("📋 먼저 **Win+Shift+S** 로 화면을 캡처한 뒤, 아래 **이미지 넣기** 버튼을 클릭하세요.")

    # 사이드바 옵션
    st.sidebar.header("설정")
    auto_resize = st.sidebar.checkbox("배경 제거 후 자동 리사이즈", value=True)

    # 라이브러리 해시 로드 (캐시)
    lib_hashes = load_library_hashes()

    # 클립보드 버튼 (Streamlit component)
    paste_result = paste_btn("📋 이미지 넣기")

    if paste_result.image_data is None:
        st.info("클립보드에 이미지가 없습니다. 캡처 후 다시 클릭해주세요.")
        st.markdown(_clipboard_js, unsafe_allow_html=True)
        return

    # 처리 로직
    with st.spinner("분석 중... 잠시만 기다려주세요."):
        pil = paste_result.image_data
        pil_no_bg = remove(pil).convert("RGBA")
        if auto_resize:
            alpha = pil_no_bg.split()[-1]
            bbox = alpha.getbbox()
            if bbox:
                pil_no_bg = pil_no_bg.crop(bbox).resize(pil.size, Image.LANCZOS)

        target_hash = imagehash.phash(pil_no_bg, hash_size=HASH_SIZE)
        best_name, best_dist = None, float("inf")
        for name, h in lib_hashes.items():
            dist = target_hash - h
            if dist < best_dist:
                best_name, best_dist = name, dist

    # 결과 표시
    st.markdown(_clipboard_js, unsafe_allow_html=True)

    if best_name:
        result = Path(best_name).stem
        st.success(f"✅ Best match: **{result}** ")
    else:
        st.error("❌ 매칭되는 이미지가 없습니다.")

if __name__ == "__main__":
    main()
