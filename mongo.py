#Import Libraries
import re
from pymongo import MongoClient
import google.generativeai as genai
import os
from dotenv import load_dotenv, dotenv_values
import json
load_dotenv()

# ADD API KEYS
MONGO_KEY = ''
GEMINI_KEY = ''

#MongoDB connection
client = MongoClient(MONGO_KEY)

#Gemini setup
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(model_name = "gemini-2.0-flash")

question_type = ""
user_input = ""
database_name = ""

#we will put our mongo_command in dict form for PyMongo
mongo_command = {}

#Step 1: Schema Exploration, collecting the database name, collection names, to then prompt Gemini model
def get_mongodb_schema(database_name):
    db = client[database_name]
    schema_description = f'DATABASE: {database_name}\n'

    for collection_name in db.list_collection_names():
        schema_description += f"COLLECTIOn: {collection_name}\n"

        sample_doc = db[collection_name].find_one()
        if sample_doc:
            for field, value in sample_doc.items():
                schema_description += f'{field} ({type(value).__name__}) \n '
                
        
    return schema_description.strip()

    


#Step 2: Prompt Gemini to classify the user request: Schema exploration, query, data modificaitno. THis well help us prompt Gemini more accurately
def mongo_classify_user_command(user_text, database_name):
    global question_type, user_input
    user_input = user_text

    # load prompt once at module start, not each call (optional)
    with open("mongo_classify_prompt.txt") as f:
        base = f.read().rstrip()

    prompt = (
        base
        + f"\n\nUSER: {user_input}\n"
        + "\nDATABASE SCHEMAS:\n" + get_mongodb_schema(database_name)
    )
    response = model.generate_content(prompt)
    question_type = response.text.strip().lower()

    # simple keyword overrides
    low = user_input.lower()
    if any(w in low for w in ("schema","tables","fields","collections")):
        question_type = "schema exploration"
    elif any(w in low for w in ("show","list","sample","display")) \
         and not any(w in low for w in ("where","with","filter","match")):
        question_type = "data exploration"

    print(f"CLASSIFY RESPONSE: {question_type}")
    return question_type




#Commented out previous code, as the approach was revised
"""
#Step 3: Generate the MongoDB query
def generate_mongodb_query(user_input):
    prompt = f"Our user requested a {question_type}, and his request was {user_input}. Help translate this into a MongoDB query" 

    prompt += f"\n Here is our database schema: \n {get_mongodb_schema(database_name)}"

    prompt += f"\n Final Note: Make sure you return just the query, exactly how it would look like in code"
    
    mongo_command = model.generate_content(prompt)




#Step 4: executing the mongo_command in our database
def execute_mongo_query(mongo_command):

    import json
"""


#We generate mongodb query as a strucutred JSON...which is then turned into a Python dictionary. This helps us with feeding into PyMongo easier
def generate_mongodb_query(user_input, schema_desc, database_name):
    # 1) Build prompt
    prompt = build_prompt(user_input, schema_desc)

    # 2) Call model
    raw = model.generate_content(prompt).text

    # DEBUG: raw LLM output
    #print("LLM raw output:\n", raw)

    # 3) Strip fences + whitespace
    text = strip_fences(raw).strip()

    # DEBUG: cleaned JSON text
    #print("Cleaned JSON text:\n", text)

    # 4) Check for failure
    if text.lower().startswith("failed to generate:"):
        print("Generation failed:", text)
        return None

    # 5) Parse JSON
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        print("JSON decode error:", e)
        return None

    # DEBUG: parsed Python object
    #print("Parsed JSON object:\n", parsed)

    # 6) Build final command dict
    cmd = build_command(parsed, user_input, database_name)

    # DEBUG: final PyMongo command dict
    print("Final mongo_command dict for pymongo:\n", cmd)

    return cmd




def build_prompt(user_input, schema_desc):
    """
    Load the JSON-command template and substitute in the user request and schema.
    """
    # Read the template file once (could also cache if you like)
    with open("mongo_query_prompt.txt", "r") as f:
        template = f.read()

    prompt = (
        template
        .replace("{{USER_REQUEST}}", user_input)
        .replace("{{SCHEMA}}", schema_desc)
    )
    return prompt




def strip_fences(text):
    
    #Remove markdown fences (```json ... ```) from the model's response.
    
    # Remove opening fence
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    # Remove closing fence
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    return text


def build_command(parsed, user_input, database_name, default_collection="students"):
    # 1) Aggregation pipeline
    if isinstance(parsed, list):
        coll = detect_collection(user_input) or default_collection
        return {
            "database": database_name,
            "collection": coll,
            "operation": "aggregate",
            "pipeline": parsed
        }

    # 2) Already full command
    if isinstance(parsed, dict) and all(k in parsed for k in ("database","collection","operation")):
        return parsed

    # 3) Top‑level "find" + "filter" shortcut
    if (
        isinstance(parsed, dict)
        and "find" in parsed
        and isinstance(parsed.get("filter"), dict)
    ):
        coll   = parsed["find"] or detect_collection(user_input) or default_collection
        filt   = parsed["filter"]
        proj   = parsed.get("projection", {})
        return {
            "database":   database_name,
            "collection": coll,
            "operation":  "find",
            "query":      filt,
            "projection": proj
        }

    # 4) Fallback single‑op dispatcher --- added to handle the case where the model returns a dictionary with a single key-value pair
    if isinstance(parsed, dict):
        op_name, params = next(iter(parsed.items()))
        if not isinstance(params, dict):
            params = {}

        coll = detect_collection(user_input) or default_collection
        cmd  = {"database": database_name, "collection": coll, "operation": op_name}

        if op_name == "find":
            # look for either params["filter"] or params["query"]
            cmd["query"]      = params.get("filter", params.get("query", {}))
            cmd["projection"] = params.get("projection", {})

        elif op_name == "insertOne":
            cmd["document"] = params.get("document", params)

        elif op_name == "insertMany":
            cmd["documents"] = params.get("documents", params)

        elif op_name == "updateOne":
            filt = params.get("filter", {})
            upd  = params.get("update", {})
            # wrap simple updates in $set
            if not any(k.startswith("$") for k in upd):
                upd = {"$set": upd}
            cmd["filter"] = filt
            cmd["update"] = upd

        elif op_name in ("deleteOne", "deleteMany"):
            # if they provided an explicit "filter", use it; otherwise treat all params as the filter
            if "filter" in params and isinstance(params["filter"], dict):
                cmd["filter"] = params["filter"]
            else:
                cmd["filter"] = params

        # (else: leave cmd as-is for any other ops)

        return cmd

    raise ValueError(f"Unexpected JSON type: {type(parsed)}")








def execute_mongodb_query(cmd):
    """
    Execute a PyMongo‑style command dict against the database.
    Expects cmd to be the dict returned from generate_mongodb_query(...).
    """
    #Note: Code is very long. Added significant portions to handle edge cases 
    if not cmd:
        print("No valid MongoDB command to run.")
        return

    db   = client[cmd["database"]]
    coll = db[cmd["collection"]]
    op   = cmd["operation"]

    try:
        if op == "find":
            q = cmd.get("query", {})
            p = cmd.get("projection", {})

            # remap filters on non‑fields (e.g. "major_name" → major_id)
            sample = coll.find_one() or {}
            fields = set(sample.keys())
            for k in list(q):
                if k not in fields:
                    val = q.pop(k)
                    if k in ("major", "major_name"):
                        maj = db["majors"].find_one({
                            "major_name": {
                                "$regex": f"^{re.escape(val)}$",
                                "$options": "i"
                            }
                        })
                        if maj:
                            q["major_id"] = maj["_id"]
                    else:
                        q["name"] = val

            # apply case‑insensitive regex for string filters
            for k, v in list(q.items()):
                if isinstance(v, str):
                    q[k] = {"$regex": f"^{re.escape(v)}$", "$options": "i"}

            for doc in coll.find(q, p):
                print(doc)

        elif op == "aggregate":
            for doc in coll.aggregate(cmd["pipeline"]):
                print(doc)

        elif op == "insertOne":
            res = coll.insert_one(cmd["document"])
            print(f"Inserted _id={res.inserted_id}")

        elif op == "insertMany":
            res = coll.insert_many(cmd["documents"])
            print(f"Inserted {len(res.inserted_ids)} documents")

        elif op == "updateOne":
            filt = cmd.get("filter", {})
            upd  = cmd.get("update", {})

            # remap & regex for filter keys not in fields
            sample = coll.find_one() or {}
            fields = set(sample.keys())
            for k in list(filt):
                if k not in fields:
                    val = filt.pop(k)
                    if k in ("major", "major_name"):
                        maj = db["majors"].find_one({
                            "major_name": {
                                "$regex": f"^{re.escape(val)}$",
                                "$options": "i"
                            }
                        })
                        if maj:
                            filt["major_id"] = maj["_id"]
                    else:
                        filt["name"] = val

            for k, v in list(filt.items()):
                if isinstance(v, str):
                    filt[k] = {"$regex": f"^{re.escape(v)}$", "$options": "i"}

            res = coll.update_one(filt, upd)
            print(f"Matched={res.matched_count}, Modified={res.modified_count}")

        elif op == "deleteOne":
            filt = cmd.get("filter", {})
            for k, v in list(filt.items()):
                if isinstance(v, str):
                    filt[k] = {"$regex": f"^{re.escape(v)}$", "$options": "i"}
            res = coll.delete_one(filt)
            print(f"Deleted={res.deleted_count} document(s)")

        elif op == "deleteMany":
            filt = cmd.get("filter", {})
            for k, v in list(filt.items()):
                if isinstance(v, str):
                    filt[k] = {"$regex": f"^{re.escape(v)}$", "$options": "i"}
            res = coll.delete_many(filt)
            print(f"Deleted={res.deleted_count} document(s)")

        else:
            print(f"Unsupported operation: {op}")

    except Exception as e:
        print(f"Error executing command: {e}")










def schema_exploration(database_name, question_type, user_input):
    #get the schema from mongodb database
    prompt = (
        f"Our user requested a {question_type}, and their request was: {user_input}.\n"
        f"Answer their question regarding schema exploration accordingly.\n\n"
        f"Here is the database schema:\n{get_mongodb_schema(database_name)}\n\n"
        
    )

    response = model.generate_content(prompt)
    print(response.text)







def detect_collection(user_input):
    
    #Use basic NLP keyword matching to identify which collection the user wants to explore.
    
    user_input = user_input.lower()

    collection_keywords = {
        "students": ["student", "students", "people", "names"],
        "majors": ["majors", "departments", "programs", "fields"],
        "enrollments": ["enrollments", "enrollment", "registered", "classes", "grades"]
    }

    for collection, keywords in collection_keywords.items():
        if any(keyword in user_input for keyword in keywords):
            return collection

    return None

def explore_data(collection_name, database_name, limit=5):
    """
    Retrieves sample documents from the given MongoDB collection.
    """
    try:
        db = client[database_name]

        if collection_name not in db.list_collection_names():
            print(f" Collection '{collection_name}' does not exist.")
            return

        docs = list(db[collection_name].find().limit(limit))
        if not docs:
            print(f" Collection '{collection_name}' is empty.")
            return

        print(f"Showing {len(docs)} documents from '{collection_name}':")
        for i, doc in enumerate(docs, 1):
            print(f"{i}. {doc}")

    except Exception as e:
        print(f"Error retrieving data: {e}")


'''
if __name__ == '__main__':
    print("Welcome to the MongoDB Natural Language Interface")
    print("------------------------------------------------")
    database_name = input("Which database do you want to query? (school): ").strip()
    schema_desc = get_mongodb_schema(database_name)

    while True:
        user_input_raw = input("\nType your natural language query (or 'exit' to quit): ").strip()
        if user_input_raw.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        command_type = mongo_classify_user_command(user_input_raw).lower()

        if command_type in ("query", "data modification"):
            # Generate and debug-print the command
            cmd = generate_mongodb_query(user_input_raw, schema_desc, database_name)
            if cmd:
                execute_mongodb_query(cmd)
            else:
                print("Failed to generate a valid MongoDB command.")

        elif command_type == "data exploration":
            collection = detect_collection(user_input_raw)
            if collection:
                explore_data(collection)
            else:
                print(
                    "Could not detect which collection to explore. "
                    "Please mention 'students', 'majors', or 'enrollments'."
                )

        else:
            schema_exploration()

'''