import streamlit as st
import streamlit.components.v1 as components 
import pandas as pd
from groq import Groq
import os
import datetime
import csv
import time
import base64

# ==============================================================================
# 1. CẤU HÌNH & CONSTANTS
# ==============================================================================
try:
    FIXED_GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    # Thay API Key của bạn vào đây nếu chạy local
    FIXED_GROQ_API_KEY = "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" 

FIXED_CSV_PATH = "res.csv"
LOG_FILE_PATH = "game_logs.csv"  
BACKGROUND_IMAGE_NAME = "background.jpg" 

# DANH SÁCH ĐIỆP VIÊN CẤP CAO (ADMIN)
ADMIN_IDS = ["250231", "250218", "admin"] 

# --- THÔNG SỐ NHIỆM VỤ ---
MAX_QUESTIONS = 5   # Số lượt truy vấn
MAX_LIVES = 3       # Số lần vi phạm an ninh (đoán sai)
GAME_DURATION = 300 # Thời gian kết nối an toàn (5 phút)

FEMALE_NAMES = ["Khánh An", "Bảo Hân", "Lam Ngọc", "Phương Quỳnh", "Phương Nguyên", "Minh Thư"]

st.set_page_config(page_title="N.P.L.M Classified", page_icon="🕵️", layout="centered")

# --- TRẠNG THÁI SERVER ---
class SharedGameState:
    def __init__(self):
        self.status = "WAITING"     
        self.end_timestamp = 0.0    

@st.cache_resource
def get_shared_state():
    return SharedGameState()

shared_state = get_shared_state()

# ==============================================================================
# 2. UTILS & LOGIC (ĐÃ FIX LỖI DATA)
# ==============================================================================

# --- HÀM MỚI: TỰ ĐỘNG KHỞI TẠO FILE LOG NẾU SAI FORMAT ---
def init_log_system():
    header = ["TIMESTAMP", "AGENT", "ACTION"]
    reset_needed = False
    
    if os.path.exists(LOG_FILE_PATH):
        try:
            df = pd.read_csv(LOG_FILE_PATH)
            # Nếu file cũ dùng tiếng Việt (Thời gian) -> Xóa tạo lại
            if "TIMESTAMP" not in df.columns:
                reset_needed = True
        except:
            reset_needed = True
    else:
        reset_needed = True

    if reset_needed:
        with open(LOG_FILE_PATH, mode='w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(header)

# Gọi hàm này ngay khi chạy app
init_log_system()

def log_activity(user_name, action):
    time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Đảm bảo file tồn tại trước khi ghi
    if not os.path.exists(LOG_FILE_PATH): init_log_system()
    
    with open(LOG_FILE_PATH, mode='a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([time_now, user_name, action])

def check_if_lost(user_name):
    if not os.path.exists(LOG_FILE_PATH): return False
    try:
        df = pd.read_csv(LOG_FILE_PATH)
        # Fix lỗi KeyError: Kiểm tra xem cột ACTION có tồn tại không
        if 'ACTION' in df.columns and 'AGENT' in df.columns:
            losers = df[df['ACTION'] == 'TERMINATED']['AGENT'].unique()
            return user_name in losers
        return False
    except Exception: 
        return False

def get_gender(name):
    for female in FEMALE_NAMES:
        if female.lower() in name.lower(): return "Nữ"
    return "Nam"

def load_data(filepath):
    try:
        if not os.path.exists(filepath): return []    
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        profiles = []
        for index, row in df.iterrows():
            target_name = str(row['TARGET (Ten)']).strip()
            giver_name = str(row['Ten Nguoi Tang']).strip()
            if not target_name or target_name.lower() == 'nan': continue
            profiles.append({
                "search_key": target_name.lower(),
                "user_name": target_name,
                "user_id": str(row['TARGET (MSHS)']).strip(),
                "santa_name": giver_name,
                "santa_id": str(row['Nguoi Tang (MSHS)']).strip()
            })
        return profiles
    except Exception as e:
        st.error(f"DATA CORRUPTION DETECTED: {e}")
        return []

# ==============================================================================
# 3. GIAO DIỆN TERMINAL / SPY STYLE
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;700&display=swap');

    .stApp {
        background-color: #050505;
        background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
        background-size: 20px 20px;
    }

    .main .block-container { 
        background-color: rgba(10, 15, 10, 0.95) !important; 
        padding: 30px !important; 
        border: 1px solid #33FF33; 
        box-shadow: 0 0 20px rgba(0, 255, 0, 0.2);
        max-width: 800px; 
        font-family: 'Fira Code', monospace;
    }
    
    h1, h2, h3, p, div, span, label, .stMarkdown { 
        font-family: 'Fira Code', monospace !important; 
        color: #33FF33 !important; 
    }
    
    .stTextInput input { 
        background-color: #001100 !important; 
        color: #33FF33 !important; 
        border: 1px solid #33FF33 !important;
        text-align: center;
    }
    
    div.stButton > button {
        background-color: #002200 !important;
        color: #33FF33 !important;
        border: 1px solid #33FF33 !important;
        font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #33FF33 !important;
        color: #000000 !important;
    }

    /* CHAT BUBBLES */
    div[data-testid="user-message"] { 
        background-color: #002200 !important; 
        border-left: 3px solid #33FF33;
        color: #33FF33 !important;
        padding: 10px;
    }
    div[data-testid="assistant-message"] { 
        background-color: #000000 !important; 
        border: 1px dashed #33FF33;
        color: #33FF33 !important;
        padding: 10px;
    }
    
    /* ICON FIX */
    .material-icons { font-size: 16px !important; vertical-align: middle; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. KHỞI TẠO STATE
# ==============================================================================
if "messages" not in st.session_state: st.session_state.messages = []
if "user_info" not in st.session_state: st.session_state.user_info = None
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "question_count" not in st.session_state: st.session_state.question_count = 0 
if "wrong_guesses" not in st.session_state: st.session_state.wrong_guesses = 0  
if "game_status" not in st.session_state: st.session_state.game_status = "PLAYING"

# ==============================================================================
# 5. MÀN HÌNH ĐĂNG NHẬP
# ==============================================================================
if st.session_state.user_info is None and not st.session_state.is_admin:
    st.title("🔒 CLASSIFIED ACCESS")
    st.markdown("<div style='text-align: center; margin-bottom: 20px;'>PROJECT: SECRET SANTA PROTOCOL</div>", unsafe_allow_html=True)
    
    if shared_state.status == "WAITING":
        st.info(">>> SYSTEM STATUS: STANDBY (WAITING FOR ADMIN)")
    elif shared_state.status == "ENDED":
        st.error(">>> SYSTEM STATUS: OFFLINE (CONNECTION TERMINATED)")
    else:
        st.success(">>> SYSTEM STATUS: ONLINE (SECURE CHANNEL OPEN)")

    profiles = load_data(FIXED_CSV_PATH)

    with st.form("auth_form"):
        st.markdown("<label>ENTER AGENT ID OR CODENAME:</label>", unsafe_allow_html=True)
        user_input = st.text_input("", placeholder="250231 or Name...") 
        
        submitted = st.form_submit_button("AUTHENTICATE", type="primary")

        if submitted and user_input:
            query = user_input.strip()
            matches = [p for p in profiles if query.lower() in p['search_key'] or query in p['user_id']]
            
            if len(matches) == 1:
                selected_user = matches[0]
                is_admin_user = selected_user['user_id'] in ADMIN_IDS
                
                allow_entry = True
                if not is_admin_user and shared_state.status != "RUNNING": allow_entry = False

                if allow_entry:
                    has_lost = check_if_lost(selected_user['user_name'])
                    if not is_admin_user and has_lost:
                        st.error(">>> ACCESS DENIED: AGENT TERMINATED PREVIOUSLY.")
                    else:
                        st.session_state.user_info = selected_user
                        st.session_state.question_count = 0
                        st.session_state.wrong_guesses = 0
                        st.session_state.game_status = "PLAYING"
                        st.session_state.messages = []
                        
                        if not has_lost: log_activity(selected_user['user_name'], "LOGIN_SUCCESS")
                        
                        welcome_msg = f"✅ **XÁC THỰC THÀNH CÔNG.**\n\nXin chào điệp viên: **{selected_user['user_name']}**.\nDữ liệu mục tiêu đã được tải.\n\n⚠️ **QUY TẮC NHIỆM VỤ:**\n1. Bạn có **{MAX_QUESTIONS} truy vấn** (câu hỏi).\n2. Phạm vi sai số cho phép: **{MAX_LIVES} lần**.\n3. Thời gian kết nối an toàn: Theo dõi đồng hồ đếm ngược.\n\nNhập truy vấn để bắt đầu thu thập manh mối."
                        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})
                        st.rerun()
                else:
                    if shared_state.status == "WAITING": st.warning(">>> ERROR: SERVER UNREACHABLE.")
                    else: st.error(">>> ERROR: CONNECTION TIME OUT.")
            elif len(matches) > 1: st.warning(">>> AMBIGUOUS IDENTITY. USE ID NUMBER.")
            else: st.error(">>> UNKNOWN IDENTITY.")
    st.stop()

# ==============================================================================
# 6. ADMIN CONTROL CENTER (ĐÃ FIX KEYERROR)
# ==============================================================================
if st.session_state.is_admin:
    st.title("🛡️ COMMAND CENTER")
    st.markdown(f"<div style='text-align: center'>CURRENT STATUS: <b>{shared_state.status}</b></div>", unsafe_allow_html=True)
    st.divider()
    
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("INITIATE (5 MIN)"):
            shared_state.status = "RUNNING"
            shared_state.end_timestamp = time.time() + GAME_DURATION
            st.rerun()
    with c2:
        if st.button("TERMINATE"):
            shared_state.status = "ENDED"
            shared_state.end_timestamp = time.time() - 1
            st.rerun()
    with c3:
        if st.button("SYSTEM RESET"):
            shared_state.status = "WAITING"
            shared_state.end_timestamp = 0
            st.rerun()

    if shared_state.end_timestamp > 0:
        remain = max(0, int(shared_state.end_timestamp - time.time()))
        m, s = divmod(remain, 60)
        st.markdown(f"<h1 style='color: #FF0000 !important; text-align: center;'>T-MINUS: {m:02d}:{s:02d}</h1>", unsafe_allow_html=True)

    st.divider()
    if st.button("⬅️ RETURN TO FIELD"):
        st.session_state.is_admin = False
        st.rerun()

    # --- FIX HIỂN THỊ LOG ---
    if os.path.exists(LOG_FILE_PATH):
        with st.expander(">> ACCESS SYSTEM LOGS"):
            try:
                df_log = pd.read_csv(LOG_FILE_PATH)
                if "TIMESTAMP" in df_log.columns:
                    st.dataframe(df_log.sort_values(by="TIMESTAMP", ascending=False), use_container_width=True)
                else:
                    st.warning("Old log format detected. Please Purge Logs.")
                    st.dataframe(df_log, use_container_width=True)
            except Exception as e:
                st.error(f"Log Read Error: {e}")

        if st.button("PURGE LOGS"): 
            os.remove(LOG_FILE_PATH)
            init_log_system() # Tạo lại file mới ngay lập tức
            st.rerun()
    st.stop()

# ==============================================================================
# 7. MAIN MISSION INTERFACE
# ==============================================================================
user = st.session_state.user_info
is_vip = user['user_id'] in ADMIN_IDS

# Check Timeout
if shared_state.status == "RUNNING":
    if time.time() > shared_state.end_timestamp:
        if not is_vip:
            st.error(">>> TIME LIMIT EXCEEDED. MISSION ABORTED.")
            st.stop()
        else: st.toast("Admin: Time expired.")

if not is_vip and shared_state.status != "RUNNING":
    st.error(">>> CONNECTION LOST FROM HQ.")
    if st.button("LOGOUT"):
        st.session_state.user_info = None
        st.rerun()
    st.stop()

target_gender = get_gender(user['santa_name'])

st.title("🕵️ MISSION DASHBOARD")

# --- SPY HUD ---
q_left = max(0, MAX_QUESTIONS - st.session_state.question_count)
l_left = MAX_LIVES - st.session_state.wrong_guesses
end_ts_js = shared_state.end_timestamp

dashboard_html = f"""
<div style="
    display: flex; 
    justify-content: space-between; 
    align-items: center; 
    background-color: #000; 
    border: 1px solid #33FF33; 
    padding: 10px; 
    margin-bottom: 20px;
    font-family: 'Fira Code', monospace;
">
    <div style="text-align: center; width: 30%;">
        <div style="color: #00AA00; font-size: 10px;">QUERIES</div>
        <div style="color: #33FF33; font-size: 24px; font-weight: bold;">{q_left}<span style="font-size:12px">/{MAX_QUESTIONS}</span></div>
    </div>
    
    <div style="text-align: center; width: 38%; border-left: 1px dashed #005500; border-right: 1px dashed #005500;">
        <div style="color: #00AA00; font-size: 10px;">T-MINUS</div>
        <div id="countdown_timer" style="color: #33FF33; font-size: 24px; font-weight: bold;">SYNC...</div>
    </div>

    <div style="text-align: center; width: 30%;">
        <div style="color: #00AA00; font-size: 10px;">LIVES</div>
        <div style="color: #FF0000; font-size: 24px; font-weight: bold;">{l_left}<span style="font-size:12px">/{MAX_LIVES}</span></div>
    </div>
</div>

<script>
    var endTs = {end_ts_js};
    function updateTimer() {{
        var now = Date.now() / 1000;
        var diff = endTs - now;
        var el = document.getElementById("countdown_timer");
        
        if (diff <= 0) {{
            el.innerHTML = "00:00";
            el.style.color = "red";
            return;
        }}
        
        var m = Math.floor(diff / 60);
        var s = Math.floor(diff % 60);
        var display = (m<10?"0"+m:m) + ":" + (s<10?"0"+s:s);
        el.innerHTML = display;
    }}
    setInterval(updateTimer, 1000);
    updateTimer();
</script>
"""
components.html(dashboard_html, height=85)

# SIDEBAR
with st.sidebar:
    st.markdown(f"<div style='border: 1px solid #33FF33; padding: 10px; text-align: center;'>AGENT: {user['user_name']}</div>", unsafe_allow_html=True)
    if user['user_id'] in ADMIN_IDS:
        st.write("")
        if st.button("⚙️ ADMIN PANEL"):
            st.session_state.is_admin = True
            st.rerun()
    st.divider()
    if st.button("🛑 ABORT MISSION"):
         st.session_state.user_info = None
         st.rerun()

# CHAT HISTORY
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# CHECK END
if st.session_state.game_status == "LOST":
    st.error("❌ MISSION FAILED: AGENT TERMINATED.")
    st.markdown(f"**TARGET IDENTITY REVEALED:** {user['santa_name']}")
    st.stop()

if st.session_state.game_status == "WON":
    st.balloons()
    st.success("🎉 MISSION ACCOMPLISHED! TARGET IDENTIFIED.")
    st.markdown(f"**SECRET SANTA CONFIRMED:** {user['santa_name']}")
    st.stop()

# INPUT AREA
if prompt := st.chat_input("Enter query command..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    try:
        client = Groq(api_key=FIXED_GROQ_API_KEY)
        
        system_instruction = f"""
        BỐI CẢNH (BACKGROUND):
        Bạn là NPLM (North Pole Logistics Mainframe) - Hệ thống Máy chủ Bắc Cực.
        Bạn nắm giữ dữ liệu tuyệt mật về việc ai tặng quà cho ai. Tính cách: Máy móc, lạnh lùng, bảo mật cao, dùng từ ngữ chuyên ngành điệp viên/kỹ thuật.

        DỮ LIỆU ĐANG XỬ LÝ:
        - Điệp viên truy vấn (User): {user['user_name']}
        - Mục tiêu bí ẩn (Santa): {user['santa_name']} (Giới tính: {target_gender}, MSHS: {user['santa_id']}).
        
        TRẠNG THÁI HIỆN TẠI:
        - Số truy vấn đã dùng: {st.session_state.question_count}/{MAX_QUESTIONS}.
        - Số lần vi phạm (đoán sai): {st.session_state.wrong_guesses}/{MAX_LIVES}.

        GIAO THỨC TRẢ LỜI:
        1. [[WIN]]: User đoán ĐÚNG CẢ HỌ VÀ TÊN.
        2. [[WRONG]]: User đoán tên SAI.
        3. [[OK]]: User hỏi gợi ý. Nếu đã hỏi đủ {MAX_QUESTIONS} câu -> Từ chối, bắt đoán tên.
        4. [[CHAT]]: Chat xã giao.

        BẢO MẬT: KHÔNG tiết lộ tên trực tiếp. KHÔNG trả lời về ngoại hình (trả lời: "Dữ liệu thị giác không khả dụng").
        """

        messages_payload = [{"role": "system", "content": system_instruction}]
        for m in st.session_state.messages[-6:]: messages_payload.append({"role": m["role"], "content": m["content"]})

        with st.chat_message("assistant"):
            container = st.empty()
            full_res = ""
            stream = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages_payload, stream=True)
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_res += chunk.choices[0].delta.content
                    clean = full_res.replace("[[WIN]]","").replace("[[WRONG]]","").replace("[[OK]]","").replace("[[CHAT]]","")
                    container.markdown(clean + " █") 
            
            final_content = full_res
            action = None
            
            if "[[WIN]]" in full_res:
                st.session_state.game_status = "WON"
                log_activity(user['user_name'], "MISSION_COMPLETE")
                final_content = full_res.replace("[[WIN]]", "")
                action = "WIN"
            elif "[[WRONG]]" in full_res:
                st.session_state.wrong_guesses += 1
                log_activity(user['user_name'], "GUESS_FAILED")
                final_content = full_res.replace("[[WRONG]]", "")
                if st.session_state.wrong_guesses >= MAX_LIVES:
                    st.session_state.game_status = "LOST"
                    log_activity(user['user_name'], "TERMINATED")
                    action = "LOST"
                else: action = "WRONG"
            elif "[[OK]]" in full_res:
                if st.session_state.question_count < MAX_QUESTIONS:
                    st.session_state.question_count += 1
                    final_content = full_res.replace("[[OK]]", "")
                    action = "OK"
                else: final_content = ">>> ALERT: QUERY LIMIT REACHED. IDENTIFY TARGET NOW."
            else: final_content = full_res.replace("[[CHAT]]", "")

            container.markdown(final_content)
            st.session_state.messages.append({"role": "assistant", "content": final_content})
            
            if action: 
                time.sleep(1.5)
                st.rerun()

    except Exception as e: st.error(f"SYSTEM ERROR: {e}")
