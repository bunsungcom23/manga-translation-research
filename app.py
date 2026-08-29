import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from google import genai
import datetime
import time
import io
import os
import glob
import re
import zipfile

st.set_page_config(page_title="대규모 만화 판본별 비교 번역 뷰어", layout="wide")

st.title("📚 대규모 만화 권(Volume)별 판본 비교 번역 시스템")
st.markdown("💡 **Tip**: 연구자 및 일반 독자들이 안정적으로 번역을 비교할 수 있도록 **타임아웃 방지 대기 시간 연장 및 한글 폰트 드로잉 최적화**가 적용되었습니다.")

# Streamlit Cloud의 Secrets에서 API 키를 안전하게 자동 로드
api_key = ""
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = os.environ.get("GEMINI_API_KEY", "")

def get_korean_font(size=14):
    font_paths = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    # 시스템에 폰트가 없을 경우 기본 폰트 반환 경고
    return ImageFont.load_default()

# 세션 상태 초기화
if "translation_history" not in st.session_state:
    st.session_state.translation_history = {}
if "current_idx" not in st.session_state:
    st.session_state.current_idx = 0
if "stored_uploaded_files" not in st.session_state:
    st.session_state.stored_uploaded_files = None
if "stored_file_names" not in st.session_state:
    st.session_state.stored_file_names = []

with st.sidebar:
    st.header("⚙️ 프로젝트 & 백업 관리")
    
    if not api_key:
        st.error("⚠️ 시스템에 Gemini API Key가 설정되지 않았습니다. Streamlit Secrets를 확인해주세요.")
    else:
        st.success("✅ 시스템 API Key 연동 완료")

    volume_name = st.text_input("현재 작업 중인 권/챕터 이름", value="vol_01", help="예: vol_01, book_2 등 폴더/파일명 구분자")
    
    st.markdown("---")
    st.markdown("### 🔄 데이터 복구 및 백업")
    backup_prefix = f"manga_backup_{volume_name}_"
    
    if st.button("📁 서버 저장소에서 해당 권 백업 불러오기"):
        backup_files = glob.glob(f"{backup_prefix}*.txt")
        recovered_count = 0
        for b_file in backup_files:
            b_name = b_file.replace(backup_prefix, "").replace(".txt", "")
            with open(b_file, "r", encoding="utf-8") as bf:
                st.session_state.translation_history[b_name] = bf.read()
                recovered_count += 1
        if recovered_count > 0:
            st.success(f"[{volume_name}] 총 {recovered_count}개 복구 완료!")
            st.rerun()
        else:
            st.warning(f"[{volume_name}] 백업 파일이 없습니다.")

    st.markdown("---")
    st.markdown(f"### 📥 [{volume_name}] 전체 데이터 내보내기")
    if st.session_state.translation_history:
        all_texts_combined = ""
        def strict_natural_key(filename):
            sub_nums = re.findall(r'\d+', filename)
            return [int(n) for n in sub_nums] if sub_nums else [filename]

        sorted_history = sorted(st.session_state.translation_history.items(), key=lambda x: strict_natural_key(x[0]))
        for name, text in sorted_history:
            all_texts_combined += f"=== [페이지: {name}] ===\n{text}\n\n"
        
        st.download_button(
            label=f"📦 {volume_name} 전체 번역 모음 (TXT)",
            data=all_texts_combined,
            file_name=f"{volume_name}_all_translations_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
    else:
        st.info("번역 내역이 쌓이면 활성화됩니다.")

uploaded_files = st.file_uploader(
    "번역할 만화 페이지 이미지들을 대량으로 업로드하세요",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)

if uploaded_files:
    def strict_natural_sort_key(file):
        filename = file.name
        numbers = re.findall(r'\d+', filename)
        if numbers:
            return [int(n) for n in numbers]
        return [filename]

    sorted_files = sorted(uploaded_files, key=strict_natural_sort_key)
    st.session_state.stored_uploaded_files = sorted_files
    st.session_state.stored_file_names = [f.name for f in sorted_files]

if st.session_state.stored_uploaded_files:
    uploaded_files = st.session_state.stored_uploaded_files
    file_names = st.session_state.stored_file_names
    total_files = len(uploaded_files)

    st.success(f"🎯 인식된 총 페이지 수: **{total_files}장** (파일명 순서 정렬 완료)")

    if st.session_state.current_idx >= total_files:
        st.session_state.current_idx = 0

    def go_prev():
        if st.session_state.current_idx > 0:
            st.session_state.current_idx -= 1

    def go_next():
        if st.session_state.current_idx < total_files - 1:
            st.session_state.current_idx += 1

    col_nav1, col_nav2, col_nav3 = st.columns([1, 4, 1])
    
    with col_nav1:
        st.button("◀ 이전 페이지", on_click=go_prev, use_container_width=True)

    with col_nav2:
        def on_selectbox_change():
            selected_val = st.session_state.box_selector
            st.session_state.current_idx = file_names.index(selected_val)

        selected_name = st.selectbox(
            "📖 분석/번역할 페이지 선택:", 
            file_names, 
            index=st.session_state.current_idx,
            key="box_selector",
            on_change=on_selectbox_change
        )

    with col_nav3:
        st.button("다음 페이지 ▶", on_click=go_next, use_container_width=True)

    current_idx = st.session_state.current_idx
    selected_file = uploaded_files[current_idx]
    image = Image.open(selected_file)

    st.markdown("---")

    def execute_translation(target_idx, client_obj):
        t_name = file_names[target_idx]
        t_image = Image.open(uploaded_files[target_idx])
        
        context_prompt = ""
        if target_idx > 0:
            prev_name = file_names[target_idx - 1]
            if prev_name in st.session_state.translation_history:
                context_prompt = (
                    f"[참고용 이전 페이지({prev_name})의 번역 내용 요약]\n"
                    f"{st.session_state.translation_history[prev_name]}\n"
                    "---\n"
                    "위 이전 페이지의 스토리 흐름과 인물 대사 톤을 이어받아, "
                    "다음 페이지인 현재 페이지를 자연스럽게 이어서 번역해 주세요."
                )

        prompt = f"""
        You are a professional manga translator and researcher.
        Analyze this manga page image carefully.
        {context_prompt}
        1. Detect all speech bubbles and text blocks in reading order. Give the original text reference if possible.
        2. Translate them into fluent, context-aware Korean suitable for academic manga comparison.
        3. Maintain consistent character tone and story continuity from previous pages if provided.
        4. Format the output clearly, matching each bubble number or text block with its extracted original text and Korean translation.
        """

        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = client_obj.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=[t_image, prompt]
                )
                res_text = response.text
                st.session_state.translation_history[t_name] = res_text
                
                backup_filename = f"manga_backup_{volume_name}_{t_name}.txt"
                with open(backup_filename, "w", encoding="utf-8") as bf:
                    bf.write(res_text)
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    st.error(f"⚠️ [{t_name}] 번역 실패 상세 에러: {e}")
                    return False
                else:
                    time.sleep(8 * (attempt + 1))

    st.sidebar.markdown("---")
    st.sidebar.subheader("🛡️ 대규모 연쇄 번역 (이어하기 지원)")
    
    if st.sidebar.button("🚀 대규모 연쇄 번역 시작"):
        if not api_key:
            st.sidebar.error("❌ API Key가 설정되지 않았습니다!")
        else:
            try:
                client = genai.Client(api_key=api_key)
            except Exception as init_err:
                st.sidebar.error(f"❌ 클라이언트 초기화 오류: {init_err}")
                client = None

            if client:
                untranslated_indices = [i for i, f in enumerate(file_names) if f not in st.session_state.translation_history]
                
                if not untranslated_indices:
                    st.sidebar.success("🎉 모든 페이지가 이미 번역되어 있습니다!")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    completed = 0
                    total_to_do = len(untranslated_indices)
                    
                    for idx in untranslated_indices:
                        f_name = file_names[idx]
                        status_text.text(f"🚀 번역 중 [{volume_name}]: [{idx + 1} / {total_files}] {f_name}")
                        
                        success = execute_translation(idx, client)
                        if not success:
                            st.error(f"중단됨: {f_name} 처리 중 문제가 발생했습니다. 백업된 페이지까지는 안전하게 저장되어 있습니다.")
                            break
                        
                        completed += 1
                        progress_bar.progress(completed / total_to_do)
                        
                        # API 과부하 및 속도 제한(Rate Limit)을 안전하게 피하기 위해 지연 시간을 25초로 대폭 늘림
                        time.sleep(25)
                    
                    status_text.text("✨ 이번 연쇄 번역 작업 구간이 완료되었습니다!")
                    st.success("🎉 번역 데이터가 백업 파일로 안전하게 저장되었습니다!")
                    st.rerun()

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        single_btn = st.button("🤖 현재 선택된 페이지만 번역", use_container_width=True)
    with action_col2:
        batch_btn = st.button("⚡ 전체 강제 재번역(주의)", use_container_width=True)

    if single_btn:
        if not api_key:
            st.error("❌ API Key가 없습니다!")
        else:
            with st.spinner(f"[{selected_name}] 페이지 분석 및 번역 중..."):
                try:
                    client = genai.Client(api_key=api_key)
                    success = execute_translation(current_idx, client)
                    if success:
                        st.success("현재 페이지 번역 완료!")
                        st.rerun()
                except Exception as e:
                    st.error(f"오류: {e}")

    if batch_btn:
        if not api_key:
            st.error("❌ API Key가 없습니다!")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            try:
                client = genai.Client(api_key=api_key)
                for idx in range(total_files):
                    status_text.text(f"전체 재번역 중: [{idx+1}/{total_files}] {file_names[idx]}")
                    success = execute_translation(idx, client)
                    if not success:
                        break
                    progress_bar.progress((idx + 1) / total_files)
                    time.sleep(25)
                st.success("전체 강제 재번역 완료!")
                st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")

    st.markdown("---")

    def create_merged_image(img_file, res_text, page_name):
        base_img = Image.open(img_file).convert("RGB")
        target_height = base_img.height
        
        panel_width = 650
        panel = Image.new("RGB", (panel_width, target_height), (255, 255, 255))
        draw = ImageDraw.Draw(panel)
        
        font_title = get_korean_font(16)
        font_body = get_korean_font(13)
        
        margin = 20
        y_text = margin
        draw.text((margin, y_text), f"[{volume_name} - {page_name}] Translation", fill=(0, 0, 0), font=font_title)
        y_text += 35
        
        lines = res_text.split('\n')
        for line in lines:
            if y_text > target_height - 40:
                draw.text((margin, y_text), "... (내용 생략됨)", fill=(100, 100, 100), font=font_body)
                break
            
            max_chars = 40
            wrapped_line = [line[i:i+max_chars] for i in range(0, len(line), max_chars)] if len(line) > max_chars else [line]
            for w_line in wrapped_line:
                if y_text > target_height - 30:
                    break
                draw.text((margin, y_text), w_line, fill=(30, 30, 30), font=font_body, encoding="utf-8")
                y_text += 22
            y_text += 4

        total_width = base_img.width + panel.width
        combined_image = Image.new("RGB", (total_width, target_height))
        combined_image.paste(base_img, (0, 0))
        combined_image.paste(panel, (base_img.width, 0))
        return combined_image

    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 병합 이미지 ZIP 저장")
    if st.session_state.translation_history:
        if st.sidebar.button(f"🖼️ [{volume_name}] 모든 병합 이미지 ZIP 생성"):
            with st.spinner("대규모 이미지 생성 및 압축 중..."):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for idx, file_obj in enumerate(uploaded_files):
                        f_name = file_names[idx]
                        if f_name in st.session_state.translation_history:
                            res_text = st.session_state.translation_history[f_name]
                            merged_img = create_merged_image(file_obj, res_text, f_name)
                            
                            img_byte_arr = io.BytesIO()
                            merged_img.save(img_byte_arr, format="PNG")
                            img_byte_arr.seek(0)
                            
                            zip_file.writestr(f"{volume_name}_merged_{f_name}.png", img_byte_arr.getvalue())
                
                zip_buffer.seek(0)
                st.sidebar.download_button(
                    label="📥 ZIP 파일 다운로드",
                    data=zip_buffer,
                    file_name=f"{volume_name}_merged_images_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip"
                )
    else:
        st.sidebar.info("번역된 내역이 있어야 다운로드가 가능합니다.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"🖼️ 원본 ({selected_name}) - [{current_idx + 1} / {total_files}]")
        st.image(image, use_container_width=True)

    with col2:
        st.subheader("🇰🇷 원본 글자 추출 및 맥락 연동 번역 결과")
        
        st.markdown(
            """
            <style>
            .scrollable-box {
                max-height: 650px;
                overflow-y: auto;
                padding: 15px;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fafafa;
                color: #000000;
            }
            </style>
            """, 
            unsafe_allow_html=True
        )

        if selected_name in st.session_state.translation_history:
            result_text = st.session_state.translation_history[selected_name]
            st.markdown(f'<div class="scrollable-box">{result_text}</div>', unsafe_allow_html=True)
            st.markdown("")
            
            st.download_button(
                label="📄 이 페이지 결과만 TXT로 저장",
                data=result_text,
                file_name=f"{volume_name}_translation_{selected_name}.txt",
                mime="text/plain"
            )
            
            st.markdown("---")
            if st.button("🖼️ 원본+번역 결과를 이미지(PNG)로 병합 저장"):
                with st.spinner("이미지 생성 중..."):
                    combined_image = create_merged_image(selected_file, result_text, selected_name)
                    buf = io.BytesIO()
                    combined_image.save(buf, format="PNG")
                    byte_im = buf.getvalue()
                    
                    st.download_button(
                        label="💾 병합된 이미지 최종 다운로드",
                        data=byte_im,
                        file_name=f"{volume_name}_merged_{selected_name}.png",
                        mime="image/png"
                    )
        else:
            st.warning("아직 이 페이지의 번역이 실행되지 않았습니다. 사이드바의 연쇄 번역 버튼을 눌러주세요.")
