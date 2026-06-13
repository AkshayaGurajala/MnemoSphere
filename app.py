from flask import Flask, render_template, request, redirect, jsonify, Response, session
import sqlite3
import requests
from bs4 import BeautifulSoup
import os
import json
from dotenv import load_dotenv
from groq import Groq
import csv
from flask import Response
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash


load_dotenv()
app = Flask(__name__)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # MEMORIES TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            topic TEXT NOT NULL,
            notes TEXT,
            difficulty TEXT,
            summary TEXT,
            keywords TEXT,
            category TEXT,
            knowledge_score INTEGER,
            memory_type TEXT,
            next_topics TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
def extract_webpage_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup([
            "script", "style", "nav", "footer", "header",
            "aside", "noscript", "form"
        ]):
            tag.decompose()

        main_content = soup.find("main")
        article = soup.find("article")

        if main_content:
            text = main_content.get_text(separator=" ")
        elif article:
            text = article.get_text(separator=" ")
        else:
            text = soup.get_text(separator=" ")

        clean_text = " ".join(text.split())
        return clean_text[:10000]

    except Exception as e:
        print("Extraction Error:", e)
        return ""


def generate_ai_analysis(text, title="", topic="", notes="", user_difficulty="Medium"):
    fallback = {
        "summary": f"""
        <h3>Overview</h3>
        <p>{title} is saved under the topic '{topic}'.</p>

        <h3>Key Concepts</h3>
        <ul>
            <li>{topic}</li>
        </ul>

        <h3>Important Points</h3>
        <p>{notes}</p>

        <h3>Practical Use</h3>
        <p>This resource can be used for learning and future reference.</p>

        <h3>User Learning Insight</h3>
        <p>The user explored this resource to improve knowledge in {topic}.</p>
        """,
        "keywords": topic if topic else "Not available",
        "category": topic if topic else "General Knowledge",
        "difficulty": user_difficulty if user_difficulty else "Medium",
        "knowledge_score": 50,
        "memory_type": "General Knowledge",
        "next_topics": "Further Study, Advanced Concepts, Practical Applications"
    }

    if not text:
        return fallback

    prompt = f"""
You are MnemoSphere AI, an intelligent learning memory assistant.

Convert the webpage into a structured learning memory.

Return ONLY valid JSON in this exact format:

{{
    "summary": "<h3>Overview</h3><p>Clear overview.</p><h3>Key Concepts</h3><ul><li>Concept 1</li><li>Concept 2</li><li>Concept 3</li><li>Concept 4</li></ul><h3>Important Points</h3><p>Main important ideas.</p><h3>Practical Use</h3><p>How this is useful in real life, projects, or learning.</p><h3>User Learning Insight</h3><p>Connect with the user's notes.</p>",
    "keywords": "10-15 comma separated keywords",
    "category": "best main learning category",
    "difficulty": "Easy or Medium or Hard",
    "knowledge_score": 1,
    "memory_type": "Tutorial",
    "next_topics": "Topic 1, Topic 2, Topic 3, Topic 4, Topic 5"
}}

STRICT RULES:
- Summary MUST contain these exact sections:
  Overview, Key Concepts, Important Points, Practical Use, User Learning Insight.
- Use HTML tags inside summary: <h3>, <p>, <ul>, <li>.
- Minimum 180 words.
- knowledge_score must be an integer from 1 to 100.
- memory_type must be exactly one of:
  Tutorial, Documentation, Research, Career, Reference, General Knowledge, Entertainment.
- next_topics must always contain 3-5 useful recommended next topics.
- Never return "Not available" for next_topics.
- Return JSON only. No markdown. No extra text.

Scoring guide:
- 90-100: official documentation, research, high-value technical tutorials
- 70-89: strong educational learning resource
- 50-69: moderate educational value
- 1-49: low learning value or entertainment

Title:
{title}

User Topic:
{topic}

User Notes:
{notes}

Webpage Content:
{text[:7000]}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )

        result = response.choices[0].message.content.strip()
        result = result.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(result)

        return {
            "summary": parsed.get("summary", fallback["summary"]),
            "keywords": parsed.get("keywords", fallback["keywords"]),
            "category": parsed.get("category", fallback["category"]),
            "difficulty": parsed.get("difficulty", fallback["difficulty"]),
            "knowledge_score": parsed.get("knowledge_score", fallback["knowledge_score"]),
            "memory_type": parsed.get("memory_type", fallback["memory_type"]),
            "next_topics": parsed.get("next_topics", fallback["next_topics"])
        }

    except Exception as e:
        print("Groq Error:", e)
        return fallback

def answer_from_memories(question, memories):
    if not memories:
        return "No related memories found. Save more resources first."

    memory_context = ""

    for memory in memories:
        memory_context += f"""
Title: {memory[2]}
Topic: {memory[4]}
Notes: {memory[5]}
Summary: {memory[7]}
Keywords: {memory[8]}
Category: {memory[9]}
Knowledge Score: {memory[10]}
Memory Type: {memory[11]}
Recommended Next Topics: {memory[12]}
---
"""

    prompt = f"""
You are MnemoSphere, a personal AI memory assistant.

Answer the user's question ONLY using the saved memories below.
If the memories do not contain enough information, say that clearly.

User Question:
{question}

Saved Memories:
{memory_context}

Give a clear, helpful answer in simple language.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("Ask MnemoSphere Error:", e)
        return "AI answer failed. Please try again."
def semantic_memory_search(question, all_memories, top_k=5):

    if not all_memories:
        return []

    question_words = question.lower().split()

    scored = []

    for memory in all_memories:

        memory_text = f"""
        {memory[1]}
        {memory[3]}
        {memory[4]}
        {memory[6]}
        {memory[7]}
        {memory[8]}
        """.lower()

        score = 0

        for word in question_words:
            if word in memory_text:
                score += 1

        if score > 0:
            scored.append((score, memory))

    scored.sort(reverse=True, key=lambda x: x[0])

    return [memory for score, memory in scored[:top_k]]
    

def get_related_memories(current_memory, all_memories, top_k=3):

    current_text = f"""
    {current_memory[3]}
    {current_memory[7]}
    {current_memory[8]}
    """.lower()

    current_words = set(current_text.replace(",", " ").split())

    related = []

    for memory in all_memories:

        if memory[0] == current_memory[0]:
            continue

        memory_text = f"""
        {memory[3]}
        {memory[7]}
        {memory[8]}
        """.lower()

        memory_words = set(memory_text.replace(",", " ").split())

        score = len(current_words.intersection(memory_words))

        if score > 0:
            related.append((score, memory))

    related.sort(reverse=True, key=lambda x: x[0])

    return [memory for score, memory in related[:top_k]]
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/add", methods=["GET", "POST"])
def add_memory():
    if request.method == "POST":
        title = request.form.get("title", "")
        url = request.form.get("url", "")
        topic = request.form.get("topic", "")
        notes = request.form.get("notes", "")
        difficulty = request.form.get("difficulty", "Medium")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM memories WHERE url = ?", (url,))
        existing_memory = cursor.fetchone()

        if existing_memory:
            conn.close()
            return redirect("/memories")

        page_text = extract_webpage_text(url)

        ai_result = generate_ai_analysis(
            page_text,
            title,
            topic,
            notes,
            difficulty
        )

        summary = ai_result["summary"]
        keywords = ai_result["keywords"]
        category = ai_result["category"]
        knowledge_score = ai_result["knowledge_score"]
        memory_type = ai_result["memory_type"]
        next_topics = ai_result["next_topics"]

        cursor.execute("""
            INSERT INTO memories
            (
                title,
                url,
                topic,
                notes,
                difficulty,
                summary,
                keywords,
                category,
                knowledge_score,
                memory_type,
                next_topics
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            url,
            topic,
            notes,
            difficulty,
            summary,
            keywords,
            category,
            knowledge_score,
            memory_type,
            next_topics
        ))

        conn.commit()
        conn.close()

        return redirect("/memories")

    return render_template("add_memory.html")

@app.route("/memories")
def memories():
    search = request.args.get("search", "")
    difficulty_filter = request.args.get("difficulty", "")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    query = "SELECT * FROM memories WHERE 1=1"
    params = []

    if search:
        query += """
            AND (
                title LIKE ? OR topic LIKE ? OR notes LIKE ?
                OR summary LIKE ? OR keywords LIKE ? OR category LIKE ?
            )
        """
        params.extend([f"%{search}%"] * 6)

    if difficulty_filter:
        query += " AND difficulty = ?"
        params.append(difficulty_filter)

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    data = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM memories")
    total_memories = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM memories WHERE difficulty='Easy'")
    easy_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM memories WHERE difficulty='Medium'")
    medium_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM memories WHERE difficulty='Hard'")
    hard_count = cursor.fetchone()[0]

    conn.close()

    stats = {
        "total": total_memories,
        "easy": easy_count,
        "medium": medium_count,
        "hard": hard_count
    }

    return render_template(
        "memories.html",
        memories=data,
        search=search,
        stats=stats,
        difficulty_filter=difficulty_filter
    )


@app.route("/api/add-memory", methods=["POST"])
def api_add_memory():
    data = request.get_json()

    title = data.get("title", "")
    url = data.get("url", "")
    topic = data.get("topic", "")
    notes = data.get("notes", "")
    difficulty = data.get("difficulty", "Medium")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM memories WHERE url = ?", (url,))
    existing_memory = cursor.fetchone()

    if existing_memory:
        conn.close()
        return jsonify({
            "message": "This memory already exists in MnemoSphere!"
        })

    page_text = extract_webpage_text(url)

    ai_result = generate_ai_analysis(
        page_text,
        title,
        topic,
        notes,
        difficulty
    )

    summary = ai_result["summary"]
    keywords = ai_result["keywords"]
    category = ai_result["category"]
    knowledge_score = ai_result.get("knowledge_score", 50)
    memory_type = ai_result.get("memory_type", "General Knowledge")
    next_topics = ai_result.get("next_topics", "Not available")

    cursor.execute("""
        INSERT INTO memories 
        (
            title,
            url,
            topic,
            notes,
            difficulty,
            summary,
            keywords,
            category,
            knowledge_score,
            memory_type,
            next_topics
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        url,
        topic,
        notes,
        difficulty,
        summary,
        keywords,
        category,
        knowledge_score,
        memory_type,
        next_topics
    ))

    conn.commit()
    conn.close()

    return jsonify({"message": "Memory saved successfully!"})

@app.route("/ask", methods=["GET", "POST"])
def ask():
    answer = ""
    question = ""
    related_memories = []

    if request.method == "POST":
        question = request.form.get("question", "").lower()

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM memories ORDER BY created_at DESC")
        all_memories = cursor.fetchall()

        conn.close()
        related_memories = semantic_memory_search(question,all_memories)
        answer = answer_from_memories(question, related_memories)

    return render_template(
        "ask.html",
        question=question,
        answer=answer,
        related_memories=related_memories
    )

@app.route("/edit/<int:memory_id>", methods=["GET", "POST"])
def edit_memory(memory_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form.get("title", "")
        url = request.form.get("url", "")
        topic = request.form.get("topic", "")
        notes = request.form.get("notes", "")
        difficulty = request.form.get("difficulty", "Medium")
        summary = request.form.get("summary", "")
        keywords = request.form.get("keywords", "")
        category = request.form.get("category", "")

        cursor.execute("""
            UPDATE memories
            SET title = ?, url = ?, topic = ?, notes = ?, difficulty = ?,
                summary = ?, keywords = ?, category = ?
            WHERE id = ?
        """, (
            title, url, topic, notes, difficulty,
            summary, keywords, category, memory_id
        ))

        conn.commit()
        conn.close()

        return redirect("/memories")

    cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
    memory = cursor.fetchone()

    conn.close()

    return render_template("edit_memory.html", memory=memory)
@app.route("/delete/<int:memory_id>")
def delete_memory(memory_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    conn.commit()
    conn.close()

    return redirect("/memories")
@app.route("/regenerate/<int:memory_id>")
def regenerate_memory(memory_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
    memory = cursor.fetchone()

    if not memory:
        conn.close()
        return redirect("/memories")

    title = memory[1]
    url = memory[2]
    topic = memory[3]
    notes = memory[4]
    difficulty = memory[5]

    page_text = extract_webpage_text(url)

    ai_result = generate_ai_analysis(
        page_text,
        title,
        topic,
        notes,
        difficulty
    )

    summary = ai_result["summary"]
    keywords = ai_result["keywords"]
    category = ai_result["category"]

    cursor.execute("""
        UPDATE memories
        SET summary = ?, keywords = ?, category = ?
        WHERE id = ?
    """, (summary, keywords, category, memory_id))

    conn.commit()
    conn.close()

    return redirect("/memories")
@app.route("/export/csv")
def export_csv():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM memories ORDER BY created_at DESC")
    memories = cursor.fetchall()

    conn.close()

    def generate():
        header = [
            "ID", "Title", "URL", "Topic", "Notes", "Difficulty",
            "Summary", "Keywords", "Category", "Saved Date"
        ]

        yield ",".join(header) + "\n"

        for memory in memories:
            row = [str(item).replace(",", " ") if item else "" for item in memory]
            yield ",".join(row) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=mnemosphere_memories.csv"
        }
    )
@app.route("/export/pdf")
def export_pdf():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM memories ORDER BY created_at DESC")
    memories = cursor.fetchall()

    conn.close()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    width, height = letter
    y = height - 50

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "MnemoSphere Memory Report")

    y -= 35
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Total Memories: {len(memories)}")

    y -= 30

    for memory in memories:
        if y < 120:
            pdf.showPage()
            y = height - 50

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, f"Title: {memory[1]}")
        y -= 18

        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, y, f"Topic: {memory[3]} | Difficulty: {memory[5]}")
        y -= 16

        pdf.drawString(50, y, f"Category: {memory[8]}")
        y -= 16

        pdf.drawString(50, y, f"Keywords: {memory[7][:90]}")
        y -= 16

        pdf.drawString(50, y, f"Saved on: {memory[9]}")
        y -= 16

        pdf.drawString(50, y, f"URL: {memory[2][:90]}")
        y -= 20

        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y, "Summary:")
        y -= 14

        pdf.setFont("Helvetica", 10)
        summary = memory[6] or ""

        for line in [summary[i:i+90] for i in range(0, len(summary), 90)]:
            if y < 80:
                pdf.showPage()
                y = height - 50
            pdf.drawString(60, y, line)
            y -= 14

        y -= 20

    pdf.save()
    buffer.seek(0)

    return Response(
        buffer,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=mnemosphere_report.pdf"
        }
    )
@app.route("/memory/<int:memory_id>")
def memory_detail(memory_id):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
    memory = cursor.fetchone()

    if not memory:
        conn.close()
        return redirect("/memories")

    cursor.execute("SELECT * FROM memories")
    all_memories = cursor.fetchall()

    conn.close()

    related_memories = get_related_memories(
        memory,
        all_memories
    )

    return render_template(
        "memory_detail.html",
        memory=memory,
        related_memories=related_memories
    )
@app.route("/tag/<tag_name>")
def filter_by_tag(tag_name):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    search_tag = f"%{tag_name}%"

    cursor.execute("""
        SELECT * FROM memories
        WHERE keywords LIKE ?
        OR topic LIKE ?
        OR category LIKE ?
        ORDER BY created_at DESC
    """, (
        search_tag,
        search_tag,
        search_tag
    ))

    memories = cursor.fetchall()

    conn.close()

    return render_template(
        "tag_memories.html",
        memories=memories,
        tag_name=tag_name
    )
@app.route("/signup", methods=["GET", "POST"])
def signup():

    error = ""

    if request.method == "POST":

        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if len(password) < 8:
            error = "Password must be at least 8 characters."

        elif password != confirm_password:
            error = "Passwords do not match."

        else:

            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:
                error = "Email already registered."

            else:

                hashed_password = generate_password_hash(password)

                cursor.execute("""
                    INSERT INTO users (username, email, password)
                    VALUES (?, ?, ?)
                """, (
                    username,
                    email,
                    hashed_password
                ))

                conn.commit()
                conn.close()

                return redirect("/login")

            conn.close()

    return render_template(
        "signup.html",
        error=error
    )
@app.route("/login", methods=["GET", "POST"])
def login():

    error = ""

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        )

        user = cursor.fetchone()

        conn.close()

        if not user:
            error = "Email does not exist."

        elif not check_password_hash(user[3], password):
            error = "Incorrect password."

        else:
            session["user_id"] = user[0]
            session["username"] = user[1]

            return redirect("/")

    return render_template(
        "login.html",
        error=error
    )
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")
@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM memories")
    total_memories = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(knowledge_score) FROM memories")
    avg_score = cursor.fetchone()[0]
    avg_score = round(avg_score, 2) if avg_score else 0

    cursor.execute("""
        SELECT category, COUNT(*) 
        FROM memories 
        GROUP BY category 
        ORDER BY COUNT(*) DESC
    """)
    categories = cursor.fetchall()

    cursor.execute("""
        SELECT memory_type, COUNT(*) 
        FROM memories 
        GROUP BY memory_type 
        ORDER BY COUNT(*) DESC
    """)
    memory_types = cursor.fetchall()

    cursor.execute("""
        SELECT topic, COUNT(*) 
        FROM memories 
        GROUP BY topic 
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """)
    top_topic_result = cursor.fetchone()
    top_topic = top_topic_result[0] if top_topic_result else "No topic yet"

    cursor.execute("""
        SELECT title, knowledge_score, memory_type
        FROM memories
        ORDER BY knowledge_score DESC
        LIMIT 5
    """)
    top_memories = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*)
        FROM memories
        WHERE date(created_at) >= date('now', '-7 days')
    """)
    memories_this_week = cursor.fetchone()[0]

    cursor.execute("""
        SELECT AVG(knowledge_score)
        FROM memories
        WHERE date(created_at) >= date('now', '-7 days')
    """)
    weekly_avg_score = cursor.fetchone()[0]
    weekly_avg_score = round(weekly_avg_score, 2) if weekly_avg_score else 0

    cursor.execute("""
        SELECT COUNT(*)
        FROM memories
        WHERE knowledge_score >= 80
    """)
    high_value_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT date(created_at)
        FROM memories
        GROUP BY date(created_at)
        ORDER BY date(created_at) DESC
    """)
    learning_days = [row[0] for row in cursor.fetchall()]

    conn.close()

    from datetime import datetime, timedelta

    learning_streak = 0
    today = datetime.now().date()

    for i in range(30):
        check_day = today - timedelta(days=i)

        if str(check_day) in learning_days:
            learning_streak += 1
        else:
            break

    return render_template(
        "dashboard.html",
        total_memories=total_memories,
        avg_score=avg_score,
        categories=categories,
        memory_types=memory_types,
        top_topic=top_topic,
        top_memories=top_memories,
        memories_this_week=memories_this_week,
        weekly_avg_score=weekly_avg_score,
        high_value_count=high_value_count,
        learning_streak=learning_streak
    )
@app.route("/regenerate-missing")
def regenerate_missing():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM memories
        WHERE knowledge_score IS NULL
        OR memory_type IS NULL
        OR next_topics IS NULL
        OR category LIKE 'http%'
    """)

    memories = cursor.fetchall()

    for memory in memories:
        memory_id = memory[0]
        title = memory[2]
        url = memory[3]
        topic = memory[4]
        notes = memory[5]
        difficulty = memory[6]

        page_text = extract_webpage_text(url)

        ai_result = generate_ai_analysis(
            page_text,
            title,
            topic,
            notes,
            difficulty
        )

        cursor.execute("""
            UPDATE memories
            SET summary = ?, keywords = ?, category = ?,
                knowledge_score = ?, memory_type = ?, next_topics = ?
            WHERE id = ?
        """, (
            ai_result["summary"],
            ai_result["keywords"],
            ai_result["category"],
            ai_result["knowledge_score"],
            ai_result["memory_type"],
            ai_result["next_topics"],
            memory_id
        ))
    
    conn.commit()
    conn.close()

    return redirect("/dashboard")
@app.route("/knowledge-graph")
def knowledge_graph():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT title, topic, category, keywords
        FROM memories
        ORDER BY created_at DESC
        LIMIT 30
    """)

    memories = cursor.fetchall()
    conn.close()

    nodes = []
    edges = []
    added_nodes = set()

    def add_node(node_id, label, node_type):
        if node_id not in added_nodes:
            nodes.append({
                "id": node_id,
                "label": label,
                "type": node_type
            })
            added_nodes.add(node_id)

    for memory in memories:
        title = memory[0]
        topic = memory[1]
        category = memory[2]
        keywords = memory[3] or ""

        memory_id = "memory_" + title[:40]
        topic_id = "topic_" + topic
        category_id = "category_" + category

        add_node(memory_id, title, "memory")
        add_node(topic_id, topic, "topic")
        add_node(category_id, category, "category")

        edges.append({
            "from": memory_id,
            "to": topic_id
        })

        edges.append({
            "from": topic_id,
            "to": category_id
        })

        for keyword in keywords.split(",")[:5]:
            keyword = keyword.strip().replace("#", "")

            if keyword:
                keyword_id = "keyword_" + keyword

                add_node(keyword_id, keyword, "keyword")

                edges.append({
                    "from": memory_id,
                    "to": keyword_id
                })

    return render_template(
        "knowledge_graph.html",
        nodes=nodes,
        edges=edges
    )
@app.route("/api/analyze-page", methods=["POST"])
def analyze_page():
    data = request.get_json()

    title = data.get("title", "")
    url = data.get("url", "")
    content = data.get("content", "")

    prompt = f"""
You are MnemoSphere AI.

Analyze this webpage and decide if it should be saved as a learning memory.

Return ONLY valid JSON:

{{
    "should_save": true,
    "topic": "best topic",
    "difficulty": "Easy or Medium or Hard",
    "reason": "short reason why this page should or should not be saved"
}}

Rules:
- Save educational, technical, academic, career, research, documentation, tutorial, biography, science, history, and useful knowledge pages.
- Do not save login pages, shopping pages, entertainment gossip, ads, banking, private pages, payment pages, or low-value pages.
- Be strict but not too narrow.
- If the page has clear learning value, should_save must be true.

Title:
{title}

URL:
{url}

Content:
{content[:4000]}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        result = response.choices[0].message.content.strip()
        result = result.replace("```json", "").replace("```", "").strip()

        return jsonify(json.loads(result))

    except Exception as e:
        print("Analyze Page Error:", e)

        return jsonify({
            "should_save": False,
            "topic": "General Knowledge",
            "difficulty": "Medium",
            "reason": "AI analysis failed."
        })
with app.app_context():
    init_db()
if __name__ == "__main__":
    init_db()
    app.run(debug=True)