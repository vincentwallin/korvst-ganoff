import streamlit as st
import sqlite3
import hashlib
import base64
from PIL import Image
import io

# --- DATABAS-FUNKTIONER ---
def init_db():
    conn = sqlite3.connect("app_data.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT UNIQUE, 
            password TEXT, 
            bio TEXT
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            image_data TEXT, 
            caption TEXT, 
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            post_id INTEGER, 
            username TEXT, 
            text TEXT, 
            FOREIGN KEY(post_id) REFERENCES posts(id)
        )""")
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# Kryptering av lösenord
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# Konvertera uppladdad bild till Base64-sträng för databasen
def image_to_base64(uploaded_file):
    image = Image.open(uploaded_file)
    # Konvertera till RGB om det är t.ex. en PNG med transparens
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    
    # Komprimera bilden något så att databasen inte blir för tung
    image.thumbnail((800, 800))
    
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode()

# --- SESSION STATE ---
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "Flöde"
if "view_profile" not in st.session_state:
    st.session_state.view_profile = None

# --- SIDOKOLUMN (Navigation & Inloggning) ---
with st.sidebar:
    st.title("📱 BildAppen v2")
    
    if st.session_state.user:
        st.write(f"Inloggad som: **{st.session_state.user['username']}**")
        if st.button("Min Profil"):
            st.session_state.view_profile = st.session_state.user['username']
            st.session_state.page = "Profil"
        if st.button("Logga ut"):
            st.session_state.user = None
            st.rerun()
    else:
        st.subheader("Logga in eller Registrera")
        tab1, tab2 = st.tabs(["Logga in", "Skapa konto"])
        
        with tab1:
            login_user = st.text_input("Användarnamn", key="login_u")
            login_pass = st.text_input("Lösenord", type="password", key="login_p")
            if st.button("Logga in"):
                hashed = hash_password(login_pass)
                c.execute("SELECT * FROM users WHERE username=? AND password=?", (login_user, hashed))
                res = c.fetchone()
                if res:
                    st.session_state.user = {"id": res[0], "username": res[1]}
                    st.success("Inloggad!")
                    st.rerun()
                else:
                    st.error("Fel användarnamn eller lösenord")
                    
        with tab2:
            reg_user = st.text_input("Välj användarnamn", key="reg_u")
            reg_pass = st.text_input("Välj lösenord", type="password", key="reg_p")
            if st.button("Registrera"):
                if reg_user and reg_pass:
                    hashed = hash_password(reg_pass)
                    try:
                        c.execute("INSERT INTO users (username, password, bio) VALUES (?, ?, ?)", (reg_user, hashed, "Hej! Jag är ny här."))
                        conn.commit()
                        st.success("Konto skapat! Logga in till vänster.")
                    except sqlite3.IntegrityError:
                        st.error("Användarnamnet är upptaget.")
                else:
                    st.error("Fyll i alla fält.")

    st.divider()
    if st.button("🏠 Gå till Hemflödet"):
        st.session_state.page = "Flöde"
        st.session_state.view_profile = None
        st.rerun()

# --- HUVUDSIDA: HEMFLÖDE ---
if st.session_state.page == "Flöde":
    st.header("Huvudflöde")
    
    # Skapa inlägg med RIKTIG BILD
    if st.session_state.user:
        with st.expander("➕ Skapa nytt inlägg"):
            uploaded_file = st.file_uploader("Välj en bild från datorn eller mobilen", type=["jpg", "jpeg", "png"])
            caption = st.text_input("Bildtext")
            
            if st.button("Publicera"):
                if uploaded_file and caption:
                    with st.spinner("Laddar upp bild..."):
                        img_base64 = image_to_base64(uploaded_file)
                        c.execute("INSERT INTO posts (user_id, image_data, caption) VALUES (?, ?, ?)", 
                                  (st.session_state.user['id'], img_base64, caption))
                        conn.commit()
                    st.success("Inlägg publicerat!")
                    st.rerun()
                else:
                    st.error("Du måste välja en bild och skriva en bildtext.")
    else:
        st.info("💡 Logga in i sidomenyn för att lägga upp egna bilder och kommentera!")

    # Visa alla inlägg
    c.execute("""
        SELECT posts.id, posts.image_data, posts.caption, users.username 
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        ORDER BY posts.id DESC""")
    posts = c.fetchall()
    
    for post_id, img_base64, caption, author in posts:
        st.container(border=True)
        if st.button(f"👤 {author}", key=f"author_{post_id}"):
            st.session_state.view_profile = author
            st.session_state.page = "Profil"
            st.rerun()
            
        # Gör om Base64-strängen till en visa-bar bild i Streamlit
        raw_img = base64.b64decode(img_base64)
        st.image(raw_img, use_container_width=True)
        st.write(f"**{author}**: {caption}")
        
        # Kommentarer
        st.caption("💬 Kommentarer:")
        c.execute("SELECT username, text FROM comments WHERE post_id=?", (post_id,))
        comments = c.fetchall()
        for c_user, c_text in comments:
            st.write(f"**{c_user}**: {c_text}")
            
        # Skriv kommentar
        if st.session_state.user:
            with st.form(key=f"comment_form_{post_id}", clear_on_submit=True):
                new_comment = st.text_input("Skriv en kommentar...", label_visibility="collapsed")
                if st.form_submit_button("Skicka"):
                    if new_comment:
                        c.execute("INSERT INTO comments (post_id, username, text) VALUES (?, ?, ?)", 
                                  (post_id, st.session_state.user['username'], new_comment))
                        conn.commit()
                        st.rerun()

# --- HUVUDSIDA: PROFIL ---
elif st.session_state.page == "Profil" and st.session_state.view_profile:
    username = st.session_state.view_profile
    st.header(f"Profil: {username}")
    
    c.execute("SELECT id, bio FROM users WHERE username=?", (username,))
    profile_data = c.fetchone()
    
    if profile_data:
        profile_id, bio = profile_data
        st.write(f"*\"{bio}\"*")
        
        c.execute("SELECT image_data, caption FROM posts WHERE user_id=? ORDER BY id DESC", (profile_id,))
        user_posts = c.fetchall()
        
        st.subheader(f"Inlägg ({len(user_posts)})")
        if user_posts:
            cols = st.columns(2)
            for idx, (img_base64, caption) in enumerate(user_posts):
                with cols[idx % 2]:
                    raw_img = base64.b64decode(img_base64)
                    st.image(raw_img, use_container_width=True)
                    st.caption(caption)
        else:
            st.write("Denna användare har inte lagt upp några bilder än.")
