import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
import datetime
import time
import io
import os
import glob
import re
import base64

st.set_page_config(page_title="대규모 만화 판본별 비교 번역 뷰어", layout="wide")

st.title("📚 대규모 만화 권(Volume)별 판본 비교 번역 시스템 (통합 일괄 저장 지원)")
st.markdown("💡 **Tip**: 자동 번역 후 하단이나 사이드바에서 **[전체 권 비교 통합 HTML 보고서 다운로드]**를 누르면, 모든 페이지가 나란히 배치된 책자 형태의 문서를 한 번에 얻을 수 있습니다. (한글 깨짐 없음)")

api_key = ""
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = os.environ.get("GEMINI_API_KEY", "")

if api_key:
    genai.configure(api_key=api_key)

if "translation_history" not in st.session_state:
    st.session_state.translation_history = {}
if "current_idx" not in st.session_state:
    st.session_state.current_idx = 0
if "stored_uploaded_files" not in st.session_state:
    st.session_state.stored_uploaded_files = None
if "stored_file_names" not in st.session_state:
    st.session_state.stored_file_names = []
if "auto_translate_running" not in st.session_state:
    st.session_state.auto_translate_running = False

with st.sidebar:
    st.header("⚙️ 프로젝트 & 일괄 내보내기")
    
    if not api_key:
        st.error("⚠️ 시스템에 Gemini API Key가 설정되지 않았습니다.")
    else:
        st.success("✅ 시스템 API Key 연동 완료")

    volume_name = st.text_input("현재 작업 중인 권/챕터 이름", value="vol_01")
    
    st.markdown("---")
    st.markdown("### 📦 전체 일괄 저장 (권 단위)")
    
    # 이미지 파일을 Base64로 변환하여 HTML 내부에 포함시키는 통합 비교 보고서 생성 기능
    if st.button("🌟 전체 페이지 비교 통합 보고서 생성 (HTML)"):
        if not st.session_state.stored_uploaded_files:
            st.warning("업로드된 이미지 파일이 없습니다.")
        else:
            def strict_natural_key(filename):
                sub_nums = re.findall(r'\d+', filename)
                return [int(n) for n in sub_nums] if sub_nums else [filename]

            sorted_files_for_html = sorted(st.session_state.stored_uploaded_files, key=lambda x: strict_natural_key(x.name))
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>[{volume_name}] 만화 판본 비교 번역 보고서</title>
                <style>
                    body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; background-color: #f4f4f9; margin: 0; padding: 20px; color: #333; }}
                    h1 {{ text-align: center; color: #2c3e50; margin-bottom: 30px; }}
                    .page-container {{ display: flex; flex-direction: row; background: white; margin-bottom: 40px; padding: 20px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); page-break-after: always; }}
                    .image-box {{ flex: 1; text-align: center; padding-right: 20px; border-right: 2px solid #eee; }}
                    .image-box img {{ max-width: 100%; height: auto; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                    .text-box {{ flex: 1; padding-left: 20px; white-space: pre-wrap; font-size: 15px; line-height: 1.6; background: #fafbfc; padding: 15px; border-radius: 5px; overflow-y: auto; }}
                    .page-title {{ font-size: 18px; font-weight: bold; margin-bottom: 15px; color: #2980b9; }}
                </style>
            </head>
            <body>
                <h1>📚 [{volume_name}] 만화 판본 비교 번역 통합 보고서</h1>
            """
            
            for file_obj in sorted_files_for_html:
                f_name = file_obj.name
                # 이미지를 열어서 base64 인코딩
                file_obj.seek(0)
                img_bytes = file_obj.read()
                encoded_img = base64.b64encode(img_bytes).decode('utf-8')
                
                # 번역 텍스트 가져오기
                trans_text = st.session_state.translation_history.get(f_name, "⚠️ 아직 번역되지 않은 페이지입니다.")
                
                html_content += f"""
                <div class="page-container">
                    <div class="image-box">
                        <div class="page-title">🖼️ 원본 페이지: {f_name}</div>
                        <img src="data:image/jpeg;base64,{encoded_img}" />
                    </div>
                    <div class="text-box">
                        <div class="page-title">🇰🇷 글자 추출 및 번역 결과</div>
                        <div>{trans_text}</div>
                    </div>
                </div>
                """
            
            html_content += """
            </body>
            </html>
            """
            
            st.download_button(
                label="📥 통합 비교 보고서 다운로드 (HTML)",
                data=html_content,
                file_name=f"{volume_name}_comparison_report.html",
                mime="text/html"
            )
            st.success("✅ 전체 페이지가 나란히 배치된 통합 보고서가 생성되었습니다! 다운로드 버튼을 눌러주세요.")

    st.markdown("---")
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

    st.success(f"🎯 인식된 총 페이지 수: **{total_files}장**")

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

    def execute_translation(target_idx):
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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content([t_image, prompt])
                res_text = response.text
                st.session_state.translation_history[t_name] = res_text
                
                backup_filename = f"manga_backup_{volume_name}_{t_name}.txt"
                with open(backup_filename, "w", encoding="utf-8") as bf:
                    bf.write(res_text)
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    return False
                else:
                    time.sleep(5)
        return False

    st.sidebar.markdown("---")
    st.sidebar.subheader("🚀 자동 릴레이 번역 제어")
    
    col_auto1, col_auto2 = st.sidebar.columns(2)
    with col_auto1:
        start_auto = st.button("자동 번역 시작", use_container_width=True)
    with col_auto2:
        stop_auto = st.button("정지", use_container_width=True)

    if start_auto:
        st.session_state.auto_translate_running = True
        st.rerun()

    if stop_auto:
        st.session_state.auto_translate_running = False
        st.rerun()

    if st.session_state.auto_translate_running:
        if not api_key:
            st.sidebar.error("❌ API Key가 없습니다!")
            st.session_state.auto_translate_running = False
        else:
            untranslated_indices = [i for i, f in enumerate(file_names) if f not in st.session_state.translation_history]
            
            if not untranslated_indices:
                st.sidebar.success("🎉 모든 페이지 번역 완료!")
                st.session_state.auto_translate_running = False
            else:
                target_idx = untranslated_indices[0]
                f_name = file_names[target_idx]
                
                with st.spinner(f"🚀 자동 번역 중 [{volume_name}]: {f_name} (남은 페이지: {len(untranslated_indices)}장)"):
                    success = execute_translation(target_idx)
                    if success:
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.error(f"⚠️ [{f_name}] 번역 실패. 다시 시도합니다.")
                        time.sleep(5)
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
                success = execute_translation(current_idx)
                if success:
                    st.success("현재 페이지 번역 완료!")
                    st.rerun()
                else:
                    st.error("번역 실패")

    if batch_btn:
        if not api_key:
            st.error("❌ API Key가 없습니다!")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            for idx in range(total_files):
                status_text.text(f"전체 재번역 중: [{idx+1}/{total_files}] {file_names[idx]}")
                success = execute_translation(idx)
                if not success:
                    break
                progress_bar.progress((idx + 1) / total_files)
                time.sleep(5)
            st.success("전체 강제 재번역 완료!")
            st.rerun()

    st.markdown("---")

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
        else:
            st.warning("아직 이 페이지의 번역이 실행되지 않았습니다. 사이드바의 [자동 번역 시작] 버튼을 눌러주세요.")
