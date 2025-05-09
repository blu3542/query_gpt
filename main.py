import sys
import sqlalchemy
from sqlalchemy import create_engine, text, inspect
import pymysql
import pandas as pd
import google.generativeai as genai
from tabulate import tabulate
from pymongo import MongoClient
from dotenv import load_dotenv, dotenv_values
import re
import os
import json
import warnings
warnings.filterwarnings("ignore")
load_dotenv()

# Import helper functions
from sql import main_menu, get_database_schema, classify_user_command, generate_query, execute_query, generate_schema_exploration, generate_modify_command, execute_modify_command, explain_error
from mongo import get_mongodb_schema, mongo_classify_user_command, generate_mongodb_query, build_prompt, strip_fences, build_command, execute_mongodb_query, schema_exploration, detect_collection, explore_data

# Define constants
USERNAME = 'root'
PASSWORD = 'Dsci-551'

# INSERT API KEYS
GEMINI_KEY = ''

# Configure Gemini model
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(model_name='gemini-2.0-flash')

# Define SQL databases
databases = ['beers', 'world', 'sakila']

# Configure MongoDB client
client = MongoClient("mongodb+srv://btlu03:AnDrEw%24247@dsci551.hfgftoj.mongodb.net/")


if __name__ == '__main__':
    # Display welcome message
    print('\nWelcome to ChatDB! Type "exit" at this screen to quit. To return to this menu, type "back" at any point.')

    # Display main menu
    selected_DBMS = main_menu()
    
    while selected_DBMS.lower() not in ['exit', 'back']:
        # Check for invalid command
        if selected_DBMS not in ['1', '2']:
            print('\nInvalid command. Please enter 1, 2, or "exit".')
            selected_DBMS = main_menu()

        # Branch for SQL
        if selected_DBMS == '1':
            print('\nConnected to MySQL.')
            print('When prompted, submit a natural language request to explore the schema of available databases, obtain sample data, generate and execute queries, or modify a database. Type "back" to return to the main menu.')

            # Get user input
            user_request = input('\nEnter your request: ')

            while user_request.lower() != 'back':
                # Pre-process user input
                request_class = classify_user_command(user_request)

                # Data exploration
                if request_class.lower() == 'explore':
                    # Generate output
                    output = generate_schema_exploration(user_request)

                    # Check for errors
                    if output.startswith('\nFailed to generate:'):
                        print(output)

                        # Get next input
                        user_request = input('\nEnter your request: ')
                        continue
                    
                    elif output.lower().startswith('select'):
                        try:
                            # Process query
                            lines = output.splitlines()
                            query, database, header = lines[0], lines[1], lines[2]

                            # Execute query
                            query_output = execute_query(query, database)

                            print(f'\n{header}')
                            print(query_output)

                            # Get next input
                            user_request = input('\nEnter your request: ')
                            continue

                        except Exception as e:
                            print('\nError obtaining sample data. Please try a different request.')

                            # Get next input
                            user_request = input('\nEnter your request: ')
                            continue

                    else:
                        print(output)

                        # Get next input
                        user_request = input('\nEnter your request: ')
                        continue


                # Query
                elif request_class.lower() == 'query':
                    # Generate query
                    query = generate_query(user_request)

                    # Check for errors
                    if query.startswith('Failed to generate:'):
                        print(query)

                        # Get next input
                        user_request = input('\nEnter your request: ')
                        continue

                    else:
                        try:
                            # Process query
                            lines = query.splitlines()
                            query, database = lines[0], lines[1]
                            
                            print(f'\nQuery: {lines[0]}')

                            # Execute query
                            output = execute_query(query, database)
                            print(output)

                            # Get next input
                            user_request = input('\nEnter your request: ')
                            continue

                        except Exception as e:
                            print('Error executing query. Please try a different request.')

                            # Get next input
                            user_request = input('\nEnter your request: ')
                            continue


                # Data modifcation
                elif request_class.lower() == 'modify':
                    # Generate modification command
                    modify_command = generate_modify_command(user_request)

                    # Check for errors
                    if modify_command.startswith('Failed to generate:'):
                        print(modify_command)

                        # Get next input
                        user_request = input('\nEnter your request: ')
                        continue

                    else:
                        try:
                            # Process query
                            lines = modify_command.splitlines()
                            command, database, query = lines[0], lines[1], lines[2]

                            # Execute command
                            confirmation = execute_modify_command(command, database)

                            # Execute query
                            output = execute_query(query, database)

                            # Display results
                            print(confirmation)
                            print('Displaying modifications:')
                            print(output)

                            # Get next input
                            user_request = input('\nEnter your request: ')
                            continue

                        except Exception as e:
                            print('Error executing modification command. Please try a different request.')
                            print(explain_error(e))

                            # Get next input
                            user_request = input('\nEnter your request: ')
                            continue

                # Other
                elif request_class.startswith('None'):
                    lines = request_class.splitlines()

                    # Display error message to user
                    print(f'{lines[1]}')

                    # Get next input
                    user_request = input('\nEnter your request: ')
                    continue

                else:
                    print('Error processing request. Please try again.')

                    # Get next input
                    user_request = input('\nEnter your request: ')
                    continue

        # Branch for MongoDB
        elif selected_DBMS == '2':
            print('Connected to MongoDB.')

            # Get database selection
            database_name = input("Which database do you want to query? (school): ").strip()
            schema_desc = get_mongodb_schema(database_name)

            while True:
                user_input_raw = input("\nType your natural language query (or 'exit' to quit): ").strip()
                if user_input_raw.lower() in ("exit", "quit"):
                    print("Goodbye!")
                    break

                command_type = mongo_classify_user_command(user_input_raw, database_name).lower()

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
                        explore_data(collection, database_name)
                    else:
                        print(
                            "Could not detect which collection to explore. "
                            "Please mention 'students', 'majors', or 'enrollments'."
                        )

                else:
                    schema_exploration(database_name, command_type, user_input_raw)


        # Display main menu
        selected_DBMS = main_menu()
    
    print('Bye!')   
