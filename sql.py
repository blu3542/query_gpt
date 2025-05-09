import pymysql
import sqlalchemy
from sqlalchemy import create_engine, text, inspect
import google.generativeai as genai
from tabulate import tabulate

# Define constants
USERNAME = 'root'
PASSWORD = 'Dsci-551'

# INSERT API KEYS
GEMINI_KEY = ''

# Configure Gemini model
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(model_name='gemini-2.0-flash')

# Define databases
databases = ['beers', 'world', 'sakila']


def main_menu():
    print('\nMenu option: ')
    print('(1) SQL')
    print('(2) MongoDB')

    userInput = input('Please select a database system: ')

    return userInput


# Define function to extract schema descriptions from a given database
def get_database_schema(database):
    # Connect to given database
    conn = sqlalchemy.create_engine(f'mysql+pymysql://{USERNAME}:{PASSWORD}@localhost/{database}')
    inspector = inspect(conn)

    schema_description = f'DATABASE: {database}'
    
    # Loop through each table
    for table_name in inspector.get_table_names():
        # Add table to schema description
        schema_description += f'\nTABLE: {table_name}\n'

        # Loop through each attribute
        for column in inspector.get_columns(table_name):
            # Add attribute to schema description
            schema_description += f'• {column['name']} ({column['type']})\n'
        
        # Add primary key constraint to schema description
        primary_key = inspector.get_pk_constraint(table_name).get('constrained_columns', [])

        if primary_key:
            schema_description += f'• PRIMARY KEY: {str(primary_key).strip('[').strip(']').replace("'", '')}\n'

        # Loop through each foreign key constraint
        for foreign_key in inspector.get_foreign_keys(table_name):
            # Extract foreign key elements
            local_column = str(foreign_key['constrained_columns']).strip('[').strip(']').replace("'", '')
            foreign_table = foreign_key['referred_table']
            foreign_column = str(foreign_key['referred_columns']).strip('[').strip(']').replace("'", '')

            # Add foreign key constraint to schema description
            schema_description += f'• FOREIGN KEY: {local_column} REFERENCES {foreign_table}({foreign_column})\n'

    return schema_description.strip()


# Define function to classify a user request
def classify_user_command(user_input):
    # Retrieve base prompt
    PROMPT_PATH = 'sql_prompts/classify_prompt.txt'

    with open(PROMPT_PATH, 'r') as file:
        prompt = file.read()
    
    # Add user request
    prompt += f'{user_input}\n'

    # Add database schema information
    prompt += '\nDATABASE SCHEMAS:\n'

    for database in databases:
        prompt += f'\n{get_database_schema(database)}\n'
    
    # Generate response
    response = model.generate_content(prompt)

    return response.text.strip()


# Define function to generate a query based on a user request
def generate_query(user_input):
    # Retrieve base prompt
    PROMPT_PATH = 'sql_prompts/query_prompt.txt'

    with open(PROMPT_PATH, 'r') as file:
        prompt = file.read()
    
    # Add user request
    prompt += f'{user_input}\n'

    # Add database schema information
    prompt += '\nDATABASE SCHEMAS:\n'

    for database in databases:
        prompt += f'\n{get_database_schema(database)}\n'
    
    # Generate response
    response = model.generate_content(prompt)

    return response.text.strip()


# Define function to execute a generated query in MySQL
def execute_query(query, database):
    # Connect to given database
    conn = sqlalchemy.create_engine(f'mysql+pymysql://{USERNAME}:{PASSWORD}@localhost/{database}')
    
    try:
        with conn.connect() as connection:
            # Execute query
            result = connection.execute(text(query))
            
            if result.rowcount > 0:
                # Retrieve rows
                rows = result.all()
                headers = result.keys()

                # Truncate return if more than 10 rows are returned
                if len(rows) > 10:
                    total_length = len(rows)
                    rows = rows[:10]
                    table = tabulate(rows, headers=headers, tablefmt='grid')

                    return table + f'\nNote: displaying 10 out of {total_length} rows.'
                
                else:
                    table = tabulate(rows, headers=headers, tablefmt='grid')
                    
                    return table

            else:
                return 'No rows returned.'

    except Exception as e:
        raise


# Define function to generate schema information, as requested by the user
def generate_schema_exploration(user_input):
    # Retrieve base prompt
    PROMPT_PATH = 'sql_prompts/explore_prompt.txt'

    with open(PROMPT_PATH, 'r') as file:
        prompt = file.read()
    
    # Add user request
    prompt += f'{user_input}\n'

    # Add database schema information
    prompt += '\nDATABASE SCHEMAS:\n'

    for database in databases:
        prompt += f'\n{get_database_schema(database)}\n'
    
    # Generate response
    response = model.generate_content(prompt)

    return response.text.strip()


def generate_modify_command(user_input):
    # Retrieve base prompt
    PROMPT_PATH = 'sql_prompts/modify_prompt.txt'

    with open(PROMPT_PATH, 'r') as file:
        prompt = file.read()
    
    # Add user request
    prompt += f'{user_input}\n'

    # Add database schema information
    prompt += '\nDATABASE SCHEMAS:\n'

    for database in databases:
        prompt += f'\n{get_database_schema(database)}\n'
    
    # Generate response
    response = model.generate_content(prompt)

    return response.text.strip()


def execute_modify_command(command, database):
    # Connect to given database
    conn = sqlalchemy.create_engine(f'mysql+pymysql://{USERNAME}:{PASSWORD}@localhost/{database}')
    
    try:
        with conn.begin() as connection:
            # Execute query
            result = connection.execute(text(command))

            return f'Modification successful. {result.rowcount} rows affected.'

    except Exception as e:
        raise


# Define function to explain any exceptions raised while executing a SQL command
def explain_error(exception):
    # Retrieve base prompt
    PROMPT_PATH = 'sql_prompts/error_prompt.txt'

    with open(PROMPT_PATH, 'r') as file:
        prompt = file.read()
    
    # Add user request
    prompt += f'{exception}\n'
    
    # Generate response
    response = model.generate_content(prompt)

    return response.text.strip()