import streamlit as st
from PIL import Image
from google import genai
import datetime
import time
import io
import os
import glob
import re
import zipfile
import base64

st.set_page_config(page_title="대규모 만화 판본별 비교 번역 뷰어", layout="wide")

# ==========================================
# 🛠️ [핵심 수정] 세션 상태 초기화를 가장 최상단으로 이동
# ==========================================
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

st.title("📚 대규모 만화 권(Volume)별 판본 비교 번역 시스템 (사용자 키 입력 모드)")
st.markdown("💡 **Tip**: 각자 본인의 Gemini API Key를 입력하여 안전하게 사용할 수 있습니다.")

# --- 🔑 사용자별 API Key 입력 시스템 ---
with st.sidebar:
    st.header("⚙️ 프로젝트 & API 설정")
    
    # 사용자가 직접 입력하는 비밀번호 형태의 입력창
    user_api_key = st.text_input(
        "🔑 Gemini API Key 입력", 
        type="password", 
        help="Google AI Studio에서 발급받은 본인의 API Key를 입력하세요."
    )
    
    # 입력된 키 사용, 없으면 빈 값
    if user_api_key:
        api_key = user_api_key
        st.success("✅ 사용자 API Key 연동 완료")
    else:
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.info("ℹ️ 시스템 기본(Secrets) API Key가 감지되었습니다.")
        except:
            api_key = ""
            st.warning("⚠️ 번역을 사용하려면 본인의 Gemini API Key를 입력해주세요.")

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
                    return False
                else:
                    time.sleep(10 * (attempt + 1))
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

    untranslated_indices = [i for i, f in enumerate(file_names) if f not in st.session_state.translation_history]
    completed_count = total_files - len(untranslated_indices)
    
    st.sidebar.markdown("### 📊 진행 현황")
    progress_val = completed_count / total_files if total_files > 0 else 0
    st.sidebar.progress(progress_val)
    st.sidebar.text(f"완료: {completed_count} / {total_files} 페이지 ({int(progress_val * 100)}%)")
    
    if st.session_state.auto_translate_running and len(untranslated_indices) > 0:
        remaining_pages = len(untranslated_indices)
        est_seconds = remaining_pages * 90
        est_min = est_seconds // 60
        est_sec = est_seconds % 60
        st.sidebar.info(f"⏳ 남은 예상 시간: 약 {est_min}분 {est_sec}초")

    if st.session_state.auto_translate_running:
        if not api_key:
            st.sidebar.error("❌ API Key가 입력되지 않았습니다! 사이드바에 본인의 API Key를 입력해주세요.")
            st.session_state.auto_translate_running = False
        else:
            try:
                client = genai.Client(api_key=api_key)
            except Exception as init_err:
                st.sidebar.error(f"❌ 클라이언트 초기화 오류: {init_err}")
                client = None

            if client:
                current_untranslated = [i for i, f in enumerate(file_names) if f not in st.session_state.translation_history]
                
                if not current_untranslated:
                    st.sidebar.success("🎉 모든 페이지 번역 완료!")
                    st.session_state.auto_translate_running = False
                    st.rerun()
                else:
                    target_idx = current_untranslated[0]
                    f_name = file_names[target_idx]
                    
                    with st.spinner(f"🚀 자동 번역 중 [{volume_name}]: {f_name} (남은 페이지: {len(current_untranslated)}장)"):
                        success = execute_translation(target_idx, client)
                        if success:
                            time.sleep(12)
                            st.rerun()
                        else:
                            st.error(f"⚠️ [{f_name}] 번역 실패. API Key 상태를 확인하거나 잠시 후 다시 시도합니다.")
                            time.sleep(15)
                            st.rerun()

    action_col1, action_col2 = st.columns([1, 1])
    with action_col1:
        single_btn = st.button("🤖 현재 선택된 페이지만 번역", use_container_width=True)
    with action_col2:
        st.empty()

    if single_btn:
        if not api_key:
            st.error("❌ API Key가 입력되지 않았습니다! 사이드바에 본인의 API Key를 입력해주세요.")
        else:
            with st.spinner(f"[{selected_name}] 페이지 분석 및 번역 중..."):
                try:
                    client = genai.Client(api_key=api_key)
                    success = execute_translation(current_idx, client)
                    if success:
                        st.success("현재 페이지 번역 완료!")
                        st.rerun()
                    else:
                        st.error("번역 실패 (API Key가 올바른지 또는 할당량이 초과되었는지 확인하세요)")
                except Exception as e:
                    st.error(f"오류: {e}")

    st.markdown("---")

    def create_html_report(img_file, res_text, page_name):
        img_file.seek(0)
        img_bytes = img_file.read()
        encoded_img = base64.b64encode(img_bytes).decode("utf-8")
        
        formatted_text = res_text.replace("\n", "<br>")
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <title>{volume_name} - {page_name} 2단 비교 보고서</title>
            <style>
                body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; margin: 20px; background-color: #f4f6f9; }}
                h1 {{ text-align: center; color: #333; }}
                .container {{ display: flex; flex-direction: row; gap: 20px; max-width: 1400px; margin: 0 auto; background: #fff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
                .pane {{ flex: 1; padding: 15px; border: 1px solid #ddd; border-radius: 6px; background: #fafafa; display: flex; flex-direction: column; }}
                .pane h3 {{ margin-top: 0; color: #0056b3; border-bottom: 2px solid #0056b3; padding-bottom: 8px; }}
                .img-wrapper {{ text-align: center; overflow-y: auto; max-height: 750px; }}
                .img-wrapper img {{ max-width: 100%; height: auto; border: 1px solid #ccc; border-radius: 4px; }}
                .text-scroll-box {{ max-height: 750px; overflow-y: auto; padding: 10px; border: 1px solid #e0e0e0; border-radius: 6px; background-color: #ffffff; }}
                .text-content {{ white-space: pre-wrap; font-size: 15px; line-height: 1.6; color: #222; }}
            </style>
        </head>
        <body>
            <h1>[{volume_name}] 만화 판본 2단 비교 보고서 ({page_name})</h1>
            <div class="container">
                <div class="pane">
                    <h3>🖼️ 원본 만화 페이지</h3>
                    <div class="img-wrapper">
                        <img src="data:image/png;base64,{encoded_img}" alt="{page_name}">
                    </div>
                </div>
                <div class="pane">
                    <h3>🇰🇷 원본 텍스트 추출 및 번역 결과</h3>
                    <div class="text-scroll-box">
                        <div class="text-content">{formatted_text}</div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html_content

    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 2단 비교 HTML 파일 ZIP 저장")
    if st.session_state.translation_history:
        if st.sidebar.button(f"🌐 [{volume_name}] 전체 2단 비교 HTML ZIP 생성"):
            with st.spinner("HTML 2단 비교 문서 압축 중..."):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for idx, file_obj in enumerate(uploaded_files):
                        f_name = file_names[idx]
                        if f_name in st.session_state.translation_history:
                            res_text = st.session_state.translation_history[f_name]
                            html_str = create_html_report(file_obj, res_text, f_name)
                            zip_file.writestr(f"{volume_name}_compare_{f_name}.html", html_str.encode("utf-8"))
                
                zip_buffer.seek(0)
                st.sidebar.download_button(
                    label="📥 HTML ZIP 다운로드",
                    data=zip_buffer,
                    file_name=f"{volume_name}_html_reports_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip"
                )
    else:
        st.sidebar.info("번역된 내역이 있어야 다운로드가 가능합니다.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"🖼️ 원본 ({selected_name}) - [{current_idx + 1} / {total_files}]")
        st.image(image, use_container_width=True)

    with col2:
        st.subheader("🇰🇷 원본 글자 추출 및 맥락 연동 번역 결과 (2단 뷰)")
        
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
            if st.button("🌐 이 페이지의 2단 비교 HTML 보고서 다운로드"):
                selected_file.seek(0)
                html_data = create_html_report(selected_file, result_text, selected_name)
                st.download_button(
                    label="💾 HTML 보고서 파일 저장",
                    data=html_data,
                    file_name=f"{volume_name}_compare_{selected_name}.html",
                    mime="application/html"
                )
        else:
            st.warning("아직 이 페이지의 번역이 실행되지 않았습니다. 사이드바의 [자동 번역 시작] 버튼을 눌러주세요.")
