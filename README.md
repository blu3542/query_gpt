# ChatDB: Natural Language Interface for SQL & MongoDB

ChatDB is an interactive command-line interface that allows users to interact with **MySQL** and **MongoDB Atlas** databases using **natural language**. It uses **Google's Gemini API** to classify user intent and generate database commands or queries.

---

## 📦 Installation

### 1. Clone the repository
```bash
git clone https://github.com/blu3542/query_gpt.git
cd chatdb
```

### 2. Install dependencies
Use the provided `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

## 🔐 Environment Variables

Create a `.env` file in your root directory:

**NOTE:** This is software best practice. In our final project code, we did not use a `.env` file to simplify the recreation process.  
Instead, API keys can be directly updated in the following lines:
- `main.py` → Line 26  
- `mongo.py` → Lines 11 & 12  
- `sql.py` → Line 12  

If using `.env`, follow this format:
```env
GEMINI_API_KEY=your_gemini_api_key
MONGO_URI=mongodb+srv://your_username:your_password@yourcluster.mongodb.net/
```

---

## 📁 Project Structure

```
.
├── main.py                      # Entry point for ChatDB
├── sql/                         # SQL helper logic (query gen, schema analysis)
│   └── ...
├── mongo/                       # Mongo helper logic (query gen, classification)
│   └── ...
├── requirements.txt             # Python dependencies
├── .env                         # API keys (not committed)
├── mongo_classify_prompt.txt    # Gemini prompt for Mongo command classification
├── mongo_query_prompt.txt       # Gemini prompt for MongoDB query generation
└── README.md
```

---

## ▶️ Running ChatDB

Start the CLI interface:

python main.py


You'll see:
```
Welcome to ChatDB! Type "exit" at this screen to quit...
```

**Supported DBMS options:**
- `1` – MySQL  
- `2` – MongoDB

---

## 💬 Example Natural Language Inputs

### 🗂️ Schema Exploration
- What tables exist in the world database?
- Show me fields in the students collection

### 📊 Data Queries
- Show me all students with GPA over 3.5
- List all countries in Asia

### ✏️ Data Modifications
- Add a new student named John
- Delete the record of Alice from enrollments

---
