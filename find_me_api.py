# To run program:  python3 skedul_api.py
# https://pi4chbdo50.execute-api.us-west-1.amazonaws.com/dev/api/v2
# README:  if conn error make sure password is set properly in RDS PASSWORD section

# README:  Debug Mode may need to be set to False when deploying live (although it seems to be working through Zappa)

# README:  if there are errors, make sure you have all requirements are loaded
# pip3 install flask
# pip3 install flask_restful
# pip3 install flask_cors
# pip3 install Werkzeug
# pip3 install pymysql
# pip3 install python-dateutil

import os
import uuid
import boto3
import json
import urllib.parse
import math
import heapq
import httplib2

from botocore.response import StreamingBody
from io import BytesIO
from datetime import time, date, datetime, timedelta
import calendar
import collections
from pytz import timezone
import random
import string
import stripe

import smtplib
from email.message import EmailMessage

from flask import Flask, request, render_template
from flask_restful import Resource, Api
from flask_cors import CORS
from flask_mail import Mail, Message

from collections import OrderedDict, Counter
from dotenv import load_dotenv

# used for serializer email and error handling
# from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
# from flask_cors import CORS

from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from werkzeug.security import generate_password_hash, check_password_hash

import googleapiclient.discovery as discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from pyzipcode import ZipCodeDatabase

import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

from gensim.models import KeyedVectors
#  NEED TO SOLVE THIS
# from NotificationHub import Notification
# from NotificationHub import NotificationHub

import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from twilio.rest import Client

from dateutil.relativedelta import *
from dateutil import tz
from decimal import Decimal
# from datetime import datetime, date, timedelta
from hashlib import sha512
from math import ceil
import string
import random
import hashlib

from email.mime.text import MIMEText
# BING API KEY
# Import Bing API key into bing_api_key.py

#  NEED TO SOLVE THIS
# from env_keys import BING_API_KEY, RDS_PW

import decimal
import sys
import json
import pytz
import pymysql
import requests

import tempfile

RDS_HOST = "io-mysqldb8.cxjnrciilyjq.us-west-1.rds.amazonaws.com"
RDS_PORT = 3306
RDS_USER = "admin"
RDS_DB = "find_me"

# SCOPES = "https://www.googleapis.com/auth/calendar"
# CLIENT_SECRET_FILE = "credentials.json"
# APPLICATION_NAME = "skedul"
# app = Flask(__name__)
app = Flask(__name__, template_folder="assets")

CORS(app)

# API
api = Api(app)

# Get RDS password from command line argument


def RdsPw():
    if len(sys.argv) == 2:
        return str(sys.argv[1])
    return ""


# RDS PASSWORD
# When deploying to Zappa, set RDS_PW equal to the password as a string
# When pushing to GitHub, set RDS_PW equal to RdsPw()
RDS_PW = "prashant"
BUCKET_NAME = "io-find-me"
s3 = boto3.client('s3')
# RDS_PW = RdsPw()

# --------------- Mail Variables ------------------
# Mail username and password loaded in .env file
app.config['MAIL_USERNAME'] = os.getenv('SUPPORT_EMAIL')
app.config['MAIL_PASSWORD'] = os.getenv('SUPPORT_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

EMAIL_ADDRESS = os.getenv('SUPPORT_EMAIL')
EMAIL_PASSWORD = os.getenv('SUPPORT_PASSWORD')

# Setting for mydomain.com
app.config["MAIL_SERVER"] = "smtp.mydomain.com"
app.config["MAIL_PORT"] = 465
# Twilio settings
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')

app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True

# Connect to MySQL database (API v2)
app.config["DEBUG"] = True

mail = Mail(app)


def connect():
    global RDS_PW
    global RDS_HOST
    global RDS_PORT
    global RDS_USER
    global RDS_DB

    print("Trying to connect to RDS (API v2)...")
    try:
        conn = pymysql.connect(
            host=RDS_HOST,
            user=RDS_USER,
            port=RDS_PORT,
            passwd=RDS_PW,
            db=RDS_DB,
            cursorclass=pymysql.cursors.DictCursor,
        )
        print("Successfully connected to RDS. (API v2)")
        return conn
    except:
        print("Could not connect to RDS. (API v2)")
        raise Exception("RDS Connection failed. (API v2)")


# Disconnect from MySQL database (API v2)
def disconnect(conn):
    try:
        conn.close()
        print("Successfully disconnected from MySQL database. (API v2)")
    except:
        print("Could not properly disconnect from MySQL database. (API v2)")
        raise Exception("Failure disconnecting from MySQL database. (API v2)")


# Serialize JSON
def serializeResponse(response):
    try:
        # print("In Serialize JSON")
        for row in response:
            for key in row:
                if type(row[key]) is Decimal:
                    row[key] = float(row[key])
                elif type(row[key]) is date or type(row[key]) is datetime:
                    row[key] = row[key].strftime("%Y-%m-%d")
        # print("In Serialize JSON response", response)
        return response
    except:
        raise Exception("Bad query JSON")


ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

# Execute an SQL command (API v2)
# Set cmd parameter to 'get' or 'post'
# Set conn parameter to connection object
# OPTIONAL: Set skipSerialization to True to skip default JSON response serialization


def execute(sql, cmd, conn, skipSerialization=False):

    # print("In SQL Execute Function")
    # print(cmd)
    # print(sql)
    response = {}
    try:
        with conn.cursor() as cur:
            # print("Before Execute")
            cur.execute(sql)
            # print("After Execute")
            if cmd == "get":
                result = cur.fetchall()
                response["message"] = "Successfully executed SQL query."
                # Return status code of 280 for successful GET request
                response["code"] = 280
                if not skipSerialization:
                    result = serializeResponse(result)
                response["result"] = result
            elif cmd == "post":
                conn.commit()
                response["message"] = "Successfully committed SQL command."
                # Return status code of 281 for successful POST request
                response["code"] = 281
            else:
                response[
                    "message"
                ] = "Request failed. Unknown or ambiguous instruction given for MySQL command."
                # Return status code of 480 for unknown HTTP method
                response["code"] = 480
    except:
        response["message"] = "Request failed, could not execute MySQL command."
        # Return status code of 490 for unsuccessful HTTP request
        response["code"] = 490
    finally:
        response["sql"] = sql
        return response


# Close RDS connection
def closeRdsConn(cur, conn):
    try:
        cur.close()
        conn.close()
        print("Successfully closed RDS connection.")
    except:
        print("Could not close RDS connection.")


# Runs a select query with the SQL query string and pymysql cursor as arguments
# Returns a list of Python tuples
def runSelectQuery(query, cur):
    try:
        cur.execute(query)
        queriedData = cur.fetchall()
        return queriedData
    except:
        raise Exception("Could not run select query and/or return data")


def sendEmail(recipient, subject, body):
    print('in sendemail')
    with app.app_context():
        print(recipient, subject, body)
        msg = Message(
            sender=app.config["MAIL_USERNAME"],
            recipients=[recipient],
            subject=subject,
            body=body
        )
        mail.send(msg)
        print('after mail send')


app.sendEmail = sendEmail

# Function to upload image to s3


def Send_Twilio_SMS2(message, phone_number):
    items = {}
    numbers = phone_number
    message = message
    numbers = list(set(numbers.split(',')))
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    for destination in numbers:
        message = client.messages.create(
            body=message,
            from_='+19254815757',
            to="+1" + destination
        )

    items['code'] = 200
    items['Message'] = 'SMS sent successfully to all recipients'
    return items


def convert24(str1):

    # Checking if last two elements of time
    # is AM and first two elements are 12
    if str1[-3:] == " AM" and str1[:2] == "12":
        return "00" + str1[2:-3]+":00"

    # remove the AM
    elif str1[-3:] == " AM":
        return str1[:-3]+":00"

    # Checking if last two elements of time
    # is PM and first two elements are 12
    elif str1[-3:] == " PM" and str1[:2] == "12":
        return str1[:-3]+":00"

    else:

        # add 12 to hours and remove PM
        return str(int(str1[:2]) + 12) + str1[2:5]+":00"


def allowed_file(filename):
    # print("In allowed_file: ", filename)
    # Checks if the file is allowed to upload
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def uploadImage(file, key, content):
    print("file, key, content", file, key, content)
    bucket = 'io-find-me'
    contentType = 'image/jpeg'
    if type(file) == StreamingBody:
        print('if streaming body')
        contentType = content
        filename = 'https://s3-us-west-1.amazonaws.com/' \
                   + str(bucket) + '/' + str(key)
        return filename

    elif file and allowed_file(file.filename):
        print('if file')

        # image link
        filename = 'https://s3-us-west-1.amazonaws.com/' \
                   + str(bucket) + '/' + str(key)

        print("Back in Helper: ", filename)
        print("Back in Helper values: ", bucket, " @ ", file, " @ ", key)
        # uploading image to s3 bucket
        upload_file = s3.put_object(
            Bucket=bucket,
            Body=file,
            Key=key,
            ACL='public-read',
            ContentType=contentType
        )

        print("File upload response : ", upload_file)
        # print("File uploaded to s3: ", filename)
        return filename
    return None


def updateImagesUser(imageFiles, id):
    content = []
    print('in updateImagesUser')
    for filename in imageFiles:

        if type(imageFiles[filename]) == str:
            print('in str')
            bucket = 'io-find-me'
            key = imageFiles[filename].split('/io-find-me/')[1]
            print(bucket, key)
            data = s3.get_object(
                Bucket=bucket,
                Key=key
            )
            imageFiles[filename] = data['Body']
            content.append(data['ContentType'])
            print(content)
        else:
            content.append('')

    s3Resource = boto3.resource('s3')
    bucket = s3Resource.Bucket('io-find-me')
    # bucket.objects.filter(
    #     Prefix=f'user/{id}/').delete()
    images = []
    for i in range(len(imageFiles.keys())):

        filename = f'img_{i-1}'
        if i == 0:
            filename = 'img_cover'
        key = f'user/{id}/{filename}'
        print("content[i] ====> ", content[i])
        image = uploadImage(
            imageFiles[filename], key, content[i])

        images.append(image)
    return images


def updateImagesEvent(imageFiles, id):
    content = []
    print('in updateImagesEvent', imageFiles, id)
    for filename in imageFiles:
        print("filename ======>", filename, type(imageFiles[filename]) , imageFiles[filename])
        if type(imageFiles[filename]) == str and imageFiles[filename] != "":
            print('in str')
            bucket = 'io-find-me'
            key = imageFiles[filename].split('/io-find-me/')[1]
            print("bucket, key", bucket, key)
            try:
                data = s3.get_object(
                    Bucket=bucket,
                    Key=key
                )
            except Exception as e:
                print("s3 failed", e)
            finally:
                print("TRY except complete")
            print("here after s3.get_object", data)
            imageFiles[filename] = data['Body']

            content.append(data['ContentType'])
            print("content", content )
        else:
            content.append('')
    print("after s3", imageFiles)
    s3Resource = boto3.resource('s3')
    bucket = s3Resource.Bucket('io-find-me')
    # bucket.objects.filter(
    #     Prefix=f'user/{id}/').delete()
    images = []
    for i in range(len(imageFiles.keys())):

        filename = f'img_{i-1}'
        if i == 0:
            filename = 'img_cover'
        key = f'event/{id}/{filename}'
        print("content[i]", content[i])
        image = uploadImage(
            imageFiles[filename], key, content[i])

        images.append(image)
    return images

#  changed updateImageEvent, if the above other function works, following commented function can be deleted
# def updateImagesEvent(imageFiles, id):
#     content = []
#     print('in updateImagesEvent', imageFiles, id)
#     s3 = boto3.client('s3')  # Initialize S3 client
#     try:
#         for filename in imageFiles:
#             print("here filename", filename)
#             # if isinstance(imageFiles[filename], str):
#             if type(imageFiles[filename]) == str:
#                 print('in str')
#                 bucket = 'io-find-me'
#                 key = imageFiles[filename].split('/io-find-me/')[1]
#                 print("bucket, key", bucket, key)
#                 try:
#                     # Retrieve object from S3
#                     data = s3.get_object(
#                         Bucket=bucket,
#                         Key=key
#                     )
#                     print("data from s3", data)
#                     imageFiles[filename] = data['Body']
#                     content.append(data['ContentType'])
#                     print("content", content)
#                 except Exception as e:
#                     print("s3.get_object failed:", e)
#                     content.append('')
#                 finally:
#                     print("TRY except complete")
#             else:
#                 print("here in else")
#                 content.append('')
#     except Exception as e:
#         print("Exception occurred in processing image files:", e)
#     print("after s3", imageFiles)
    
#     s3Resource = boto3.resource('s3')
#     bucket = s3Resource.Bucket('io-find-me')
#     images = []
#     print("imageFiles", imageFiles, content)
#     try:
#         for i, filename in enumerate(imageFiles.keys()):
#             print(i, filename)
#             if i == 0:
#                 filename = 'img_cover'
#             key = f'event/{id}/{filename}'
#             print("content[i] ==========", content[i])
#             image = uploadImage(
#                 imageFiles[filename], key, content[i])
#             images.append(image)
#         # for i in range(len(imageFiles.keys())):
#         #     print("in for", image)
#         #     filename = f'img_{i-1}'
#         #     if i == 0:
#         #         filename = 'img_cover'
#         #     key = f'event/{id}/{filename}'
#         #     print("content[i]", content[i])
#         #     image = uploadImage(
#         #         imageFiles[filename], key, content[i])

#         #     images.append(image)
#         # return images
#     except Exception as e:
#         print("Exception occurred in uploading images:", e)
#     print("images", images)
#     return images

def convertLocalToUTC(dateTime, user_timezone):
    print("user_timezone",  pytz.timezone(user_timezone))
    local = pytz.timezone(user_timezone)
    print("local" , local)
    naive = datetime.strptime(dateTime, "%m/%d/%Y %I:%M %p")
    local_dt = local.localize(naive, is_dst=None)
    print("local_dty" , local_dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    # print(utc_dt)
    utc_dateTime = {}
    utc_dateTime["date"] = utc_dt.strftime("%m/%d/%Y")
    utc_dateTime["time"] = utc_dt.strftime("%I:%M %p")
    print("utc_dateTime", utc_dateTime)
    return utc_dateTime


def convertUtcToLocal(dateTime, user_timezone):
    from_zone = tz.gettz('UTC')
    to_zone = tz.gettz(user_timezone)
    utc = datetime.strptime(dateTime, '%m/%d/%Y %I:%M %p')
    utc = utc.replace(tzinfo=from_zone)
    local_dt = utc.astimezone(to_zone)
    local_dateTime = {}
    local_dateTime["date"] = local_dt.strftime("%m/%d/%Y")
    local_dateTime["time"] = local_dt.strftime("%I:%M %p")
    # print(" local_dateTime ",local_dateTime)
    return local_dateTime


def eventListIterator(items, user_timezone):
    events = items["result"]
    for event in events:
        if event["event_start_date"] and event["event_start_time"]:
            start_datetime = event["event_start_date"] + \
                " " + event["event_start_time"]
            # print(start_datetime)
            local_start_datetime = convertUtcToLocal(
                start_datetime, user_timezone)
            event["event_start_date"] = local_start_datetime["date"]
            event["event_start_time"] = local_start_datetime["time"]
        if event["event_end_date"] and event["event_end_time"]:
            end_datetime = event["event_end_date"] + \
                " " + event["event_end_time"]
            # print(end_datetime)
            local_end_datetime = convertUtcToLocal(end_datetime, user_timezone)
            event["event_end_date"] = local_end_datetime["date"]
            event["event_end_time"] = local_end_datetime["time"]
    return items

class TestCredentials(Resource):
    def get(self):
        print("Inside Test Credentials")
        response = {}

        try:
            email_access = os.getenv('SUPPORT_EMAIL')
            response["email_access"] = email_access
        except:
            print("error in s3 access key")

        try:
            s3_access_key = os.getenv('MW_KEY')
            response["s3_access_key"] = s3_access_key
        except:
            print("error in s3 access key")

        try:
            s3_secret_key = os.getenv('MW_SECRET')
            response["s3_secret_key"] = s3_secret_key
        except:
            print("error in s3 secret key")

        try:
            s3_bucket = os.getenv('BUCKET_NAME')
            response["s3_bucket"] = s3_bucket
        except:
            print("error in s3 bucket")

        try:
            s3_path = os.getenv('S3_PATH_KEY')
            response["s3_path"] = s3_path
        except:
            print("error in s3 path")

        return response, 200
    
def cosine_similarity(v1, v2):
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    return dot_product / (norm_v1 * norm_v2) if norm_v1 != 0 and norm_v2 != 0 else 0

def get_word_vector(token, embeddings):
    for line in embeddings.split("\n"):
        if not line:
            continue
        parts = line.split(" ")
        word = parts[0]
        if word == token:
            # Assuming the word vector starts from index 1
            return np.array(parts[1:], dtype=np.float32)
    # Return zeros if the token is not found
    return np.zeros(50)

def cosine_alg_trial(users):
    s3_access_key = os.getenv('MW_KEY')
    s3_secret_key = os.getenv('MW_SECRET')
    s3_bucket_name = os.getenv('BUCKET_NAME')
    s3_file_key = os.getenv('S3_PATH_KEY')
    print("before s3 connect inside cosine algo trial", users)

    s3_client = boto3.client('s3', aws_access_key_id=s3_access_key, aws_secret_access_key=s3_secret_key)
    print("after s3 connect")
    #  new changes
    event_id = users["event_id"]
    userObject = get_user_data_from_db(event_id)
    print("the user object =============>", userObject)
    # Process user responses iteratively
    user_vectors = {}
    print("beginning every user loop")
    # for user_name, user_data in users.items():
    for user_data in userObject:
        answer_vectors = []
        user_id = user_data.get("eu_user_id")

        # for qa_pair in user_data['qas']:
        qas_list = json.loads(user_data['eu_qas'])
        for qa_pair in qas_list:
            answer = qa_pair['answer']
            tokens = answer.lower().split()
            word_vectors = []
            # Load GloVe file in chunks
            print("Connecting to S3")
            response = s3_client.get_object(Bucket=s3_bucket_name, Key=s3_file_key)
            print("the response of the S3", response)

            print("Reading GloVe file in chunks")
            for chunk in response['Body'].iter_chunks(chunk_size=8192):
                try:
                    chunk_text = chunk.decode('utf-8')
                    word_vectors_chunk = [get_word_vector(token, chunk_text) for token in tokens]
                    word_vectors.extend(word_vectors_chunk)
                    if any(np.any(vec) for vec in word_vectors_chunk):
                        break
                except UnicodeDecodeError:
                    pass
            print("done reading glove file for this user")
        #     answer_vector = np.mean(word_vectors, axis=0) if word_vectors else np.zeros(50)
        #     answer_vectors.append(answer_vector)
        # user_vectors[user_name] = answer_vectors
            max_len = max(len(vec) for vec in word_vectors)
            word_vectors = [vec if len(vec) == max_len else np.zeros(max_len) for vec in word_vectors]
                
                # Check if word_vectors is empty or has different lengths
            if not word_vectors or len(word_vectors[0]) != 50:
                answer_vector = np.zeros(50)  # If no word vectors or different lengths, create a zero vector
            else:
                answer_vector = np.mean(word_vectors, axis=0)
            answer_vectors.append(answer_vector)
            user_vectors[user_id] = (answer_vectors, qas_list)            # answer_vector = np.mean(word_vectors, axis=0) if word_vectors else np.zeros(50)


# Compute similarity scores
    print("Computing similarity scores here")
    # print("priting user_vectors ======= >", user_vectors)
    similarity_scores = {}
    for user1, (answers1, _) in user_vectors.items():  # Unpack answer_vectors and ignore qas_list
        for user2, (answers2, _) in user_vectors.items():  # Unpack answer_vectors and ignore qas_list
            if user1 != user2:
                similarities = [cosine_similarity(ans1, ans2) for ans1, ans2 in zip(answers1, answers2)]
                avg_similarity = np.mean(similarities) if similarities else 0
                similarity_scores[(user1, user2)] = avg_similarity

    # Find top matches
    top_matches = {}
    # print("user_vectors==========>", user_vectors)
    for user1 in user_vectors.keys():
        top_matches[user1] = []
        for user2 in user_vectors.keys():
            if user1 != user2:
                score = similarity_scores.get((user1, user2), 0)
                if len(top_matches[user1]) < 3 or score > min([s['score'] for s in top_matches[user1]]):
                    top_matches[user1].append({'from': user1, 'to': user2, 'score': score})
                    top_matches[user1].sort(key=lambda x: x['score'], reverse=True)
                    if len(top_matches[user1]) > 3:
                        top_matches[user1].pop()
    
    # Store user id as key
    id_matches = {}
    # print(top_matches)
    # for name, matches in top_matches.items():
    #     id_matches[users[name][0]['user_uid']] = matches
    # print("END OF COSINE ENDPOINT")
    # return id_matches
    print("top_matches =========================>", top_matches)
    # for name, matches in top_matches.items():
    #     print("here in for loop =========> name , matches", name , matches)
    #     if name in users:
    #         id_matches[users[name][0]['user_uid']] = matches
    for user_id in users['user_ids']:
        if user_id in top_matches:
            print("Processing matches for user:", user_id)
            id_matches[user_id] = top_matches[user_id]
        else:
            print("No matches found for user:", user_id)
    print("END OF COSINE ENDPOINT")
    return id_matches
# new showCosineFunction 4/12/2024

def ShowCosineResults(users):
    s3_access_key = os.getenv('MW_KEY')
    s3_secret_key = os.getenv('MW_SECRET')
    s3_bucket_name = os.getenv('BUCKET_NAME')
    s3_file_key = os.getenv('S3_PATH_KEY')
    s3_client = boto3.client('s3', aws_access_key_id=s3_access_key, aws_secret_access_key=s3_secret_key)

    print("==================================> users", users)
    event_id = users["event_id"]
    user_ids = users["user_ids"]
   # Process user responses iteratively
    user_vectors = {}
    # important
    # event_id = key of users object
    # for user_name, user_data in users.items():
    userObject = get_user_data_from_db(event_id)
    print("got the user object", userObject)
    for user_data in userObject:
        # user_data = userObject["user_data"]
        # user_name = user_data["user_name"]
        # user_id = userObject["eu_user_id"]
        user_id = user_data.get("eu_user_id")
        answer_vectors = []
        qas_list = json.loads(user_data['eu_qas'])
        for qa_pair in qas_list:

            answer = qa_pair['answer']
            # answer = qa_pair("answer")
            tokens = answer.lower().split()
            word_vectors = []
            
            # Load GloVe file in chunks
            print("Connecting to S3")
            response = s3_client.get_object(Bucket=s3_bucket_name, Key=s3_file_key)
            print("The response of the S3", response)

            print("Reading GloVe file in chunks")
            for chunk in response['Body'].iter_chunks(chunk_size=8192):
                try:
                    chunk_text = chunk.decode('utf-8')
                    word_vectors_chunk = [get_word_vector(token, chunk_text) for token in tokens]
                    word_vectors.extend(word_vectors_chunk)
                    if any(np.any(vec) for vec in word_vectors_chunk):
                        break
                except UnicodeDecodeError:
                    pass
            print("Done reading glove file for this user")
            max_len = max(len(vec) for vec in word_vectors)
            word_vectors = [vec if len(vec) == max_len else np.zeros(max_len) for vec in word_vectors]
                
                # Check if word_vectors is empty or has different lengths
            if not word_vectors or len(word_vectors[0]) != 50:
                answer_vector = np.zeros(50)  # If no word vectors or different lengths, create a zero vector
            else:
                answer_vector = np.mean(word_vectors, axis=0)
            answer_vectors.append(answer_vector)
            user_vectors[user_id] = (answer_vectors, qas_list)            # answer_vector = np.mean(word_vectors, axis=0) if word_vectors else np.zeros(50)
            # answer_vectors.append(answer_vector)
        # user_vectors[user_name] = (answer_vectors, user_data['qas'])
        # user_vectors[user_id] = (answer_vectors, user_data['eu_qas'])


    # Compute similarity scores
    print("Computing similarity scores here" , user_vectors)
    similarity_scores = {}
    for user1, (answers1, _) in user_vectors.items():
        for user2, (answers2, _) in user_vectors.items():
            if user1 != user2:
                similarities = [cosine_similarity(ans1, ans2) for ans1, ans2 in zip(answers1, answers2)]
                avg_similarity = np.mean(similarities) if similarities else 0
                similarity_scores[(user1, user2)] = avg_similarity

    # Create all matches array
    all_matches_array = []
    for user1, (_, answers1) in user_vectors.items():
        for user2, (_, answers2) in user_vectors.items():
            if user1 != user2:
                score = similarity_scores.get((user1, user2), 0)
                all_matches_array.append([user1, user2, score, answers1, answers2])

    # return [["user1","user2","similarity score",[response of user 1],[response of user2]]]
    return all_matches_array

def get_user_data_from_db(event_id):
    userObject = {}
    print("event-id====================" ,event_id)
    try:
        conn = connect()
        query = """ SELECT * FROM event_user 
                    WHERE eu_event_id = \'""" + event_id + """\' """
        items = execute(query, 'get', conn)

        print(items)
        userObject = items["result"]
        return userObject
    finally:
        print("in finally")
        

# -- Stored Procedures start here -------------------------------------------------------------------------------

# RUN STORED PROCEDURES


# -- FindMe Queries start here -------------------------------------------------------------------------------

class SendEmailAttendee(Resource):

    def post(self):
        print("In Send EMail get")
        try:
            conn = connect()
            response = {}
            response['message'] = []
            data = request.get_json(force=True)
            print(data)
            recipient = data['recipient']
            subject = data['subject']
            message = data['message']
            organizer = data['event_organizer_uid']
            eventTitle = data["event_title"]
            eventDescription = data["event_description"]
            eventLocation = data["event_location"]
            user_timezone = data['user_timezone']
            eventStartDate = data["event_start_date"]
            eventStartTime = data["event_start_time"]
            eventStartDateTime = eventStartDate + " " + eventStartTime

            eventStartDateTimeUTC = convertUtcToLocal(
                eventStartDateTime, user_timezone)

            eventStartDate = datetime.strptime(
                eventStartDateTimeUTC["date"], "%m/%d/%Y").strftime('%A, %B %d, %Y')

            eventStartTime = eventStartDateTimeUTC["time"]
            eventEndDate = data["event_end_date"]
            eventEndTime = data["event_end_time"]
            eventEndDateTime = eventEndDate + " " + eventEndTime
            eventEndDateTimeUTC = convertUtcToLocal(
                eventEndDateTime, user_timezone)
            eventEndDate = datetime.strptime(
                eventEndDateTimeUTC["date"], "%m/%d/%Y").strftime('%A, %B %d, %Y')
            eventEndTime = eventEndDateTimeUTC["time"]

            eventRegistrationCode = data["event_registration_code"]
            eventPhoto = json.loads(data["event_photo"]) if len(json.loads(
                data["event_photo"])) == 0 else json.loads(data["event_photo"])[0]

            eventCheckinCode = (data["event_checkin_code"])
            # print(organizer)
            query = """ SELECT * FROM users 
                        WHERE user_uid = \'""" + organizer + """\'"""
            items = execute(query, 'get', conn)

            # print(msg)
            with smtplib.SMTP_SSL('smtp.mydomain.com', 465) as smtp:

                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                for e in range(len(recipient)):

                    try:
                        # print('in try', recipient[e])
                        conn = connect()

                        msg = EmailMessage()
                        msg['Subject'] = str(eventTitle) + ': ' + str(subject)
                        msg['From'] = app.config["MAIL_USERNAME"]
                        msg['To'] = [recipient[e]]
                        # print(msg)
                        html = """\
                        <!DOCTYPE html>
                        <html>
                            <body style="background-color:#eee;padding:10px 20px;align:center">
                                <div style="padding:20px 0px">
                                    <div>
                                        <img src= """ + str(eventPhoto) + """ style="display:block;margin-left:auto;margin-right:auto;width:50%;">
                                        <div style="text-align:center;display:block;margin-left:auto;margin-right:auto;width:30%;">
                                        <h3>Message from the Organizer: """ + str(message) + """ </h3>
                                        </div>
                                        <div style="text-align:center;display:block;margin-left:auto;margin-right:auto;width:30%;">
                                            <h1>""" + str(eventTitle) + """</h1>
                                            <h3>""" + str(eventDescription) + """</h3>
                                            <h4>Event Date: """ + str(eventStartDate) + """ from """ + str(eventStartTime) + """ to """ + str(eventEndTime) + """</h4>
                                            <p>Event Location:  """ + str(eventLocation) + """</p>
                                            <p>Event Registration Code:  """ + str(eventRegistrationCode) + """</p>
                                            
                                
                                        </div>
                                    </div>
                                </div>
                            </body>
                        </html>
                        """.format(items)
                        msg.set_content(html, subtype='html')
                        # print(msg)
                        smtp.send_message(msg)
                        response['message'].append(
                            'Email to ' + recipient[e] + ' sent successfully')
                    except:
                        # print('in except', recipient[e])
                        response['message'].append(
                            'Email to ' + recipient[e] + ' failed')
                        continue

            return response

        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)

class BroadCastEmail(Resource):
    def post(self):
        print("In Send EMail get")
        try:
            conn = connect()
            response = {}
            response['message'] = []
            data = request.get_json(force=True)
            print(data)
            recipient = data['emailId']

            eventRegistrationCode = data["registrationCode"]
            eventTitle = "You're invited to my bizbuz Event!"
            subject = ""
            message = " You are invited to attend our Bizbuz event. Please follow the link to register using the registration Code."
            with smtplib.SMTP_SSL('smtp.mydomain.com', 465) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                for e in range(len(recipient)):
                    print("printing eeee", recipient[e])
                    try:

                        msg = EmailMessage()
                        print("msg", msg)
                        msg['Subject'] = str(eventTitle) + ': ' + str(subject)
                        msg['From'] = app.config["MAIL_USERNAME"]
                        msg['To'] = [recipient[e]]
                        print("msg after emailMsg function ", msg)

                        html = """\
                        <!DOCTYPE html>
                        <html>
                            <body style="background-color:#eee;padding:10px 20px;align:center">
                                <div style="padding:20px 0px">
                                    <div>
                                        <div style="text-align:center;display:block;margin-left:auto;margin-right:auto;width:30%;">
                                        <h3>Message from the Organizer: """ + str(message) + """ </h3>
                                        </div>
                                        <div style="text-align:center;display:block;margin-left:auto;margin-right:auto;width:30%;">
                                            <h1>""" + str(eventTitle) + """</h1>

                                            <p>Event Registration Link:  <a href="bizbuz.design/""" + str(eventRegistrationCode) + """ "> Register </a></p>
                                            
                                
                                        </div>
                                    </div>
                                </div>
                            </body>
                        </html>
                        """
                        msg.set_content(html, subtype='html')
                        print(msg)
                        smtp.send_message(msg)
                        response['message'].append(
                            'Email to ' + recipient[e] + ' sent successfully')
                    except:
                        # print('in except', recipient[e])
                        response['message'].append(
                            'Email to ' + recipient[e] + ' failed')
                        continue

            return response

        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)
        
class SendEventDetails(Resource):

    def post(self):
        print("In Send EMail get")
        try:
            conn = connect()
            response = {}
            response['message'] = []
            data = request.get_json(force=True)
            print(data)
            organizer = data['event_organizer_uid']
            eventType = data["event_type"]
            eventVisibility = data["event_visibility"]
            eventTitle = data["event_title"]
            eventDescription = data["event_description"]
            eventCapacity = data["event_capacity"]
            eventLocation = data["event_location"]
            eventStartTime = data["event_start_time"]

            user_timezone = data['user_timezone']
            eventStartDate = data["event_start_date"]
            eventStartDateTime = eventStartDate + " " + eventStartTime
            eventStartDateTimeUTC = convertUtcToLocal(
                eventStartDateTime, user_timezone)

            eventStartDate = datetime.strptime(
                eventStartDateTimeUTC["date"], "%m/%d/%Y").strftime('%A, %B %d, %Y')

            eventStartTime = eventStartDateTimeUTC["time"]
            eventEndDate = data["event_end_date"]
            eventEndTime = data["event_end_time"]
            eventEndDateTime = eventEndDate + " " + eventEndTime
            eventEndDateTimeUTC = convertUtcToLocal(
                eventEndDateTime, user_timezone)
            eventEndDate = datetime.strptime(
                eventEndDateTimeUTC["date"], "%m/%d/%Y").strftime('%A, %B %d, %Y')
            eventEndTime = eventEndDateTimeUTC["time"]
            eventRegCode = data["event_registration_code"]
            preEventQuestionnaire = json.loads(data["pre_event_questionnaire"])
            eventPhoto = json.loads(data["event_photo"]) if len(json.loads(
                data["event_photo"])) == 0 else json.loads(data["event_photo"])[0]
            eventCheckinCode = (data["event_checkin_code"])
            print('here')
            query = """ SELECT * FROM users 
                        WHERE user_uid = \'""" + organizer + """\'"""

            items = execute(query, 'get', conn)
            print(items)
            recipient = items['result'][0]['email']

            msg = EmailMessage()
            msg['Subject'] = str(eventTitle) + ': New Event Created'
            msg['From'] = app.config["MAIL_USERNAME"]
            msg['To'] = [recipient]

            items = ["<li>{}</li>".format(s['question'])
                     for s in preEventQuestionnaire]
            items = "".join(items)
            print(items)
            html = """\
            <!DOCTYPE html>
            <html>
                <body style="background-color:#eee;padding:10px 20px;align:center">
                    <div style="padding:20px 0px">
                        <div>
                            <img src= """ + str(eventPhoto) + """ style="display:block;margin-left:auto;margin-right:auto;width:50%;height:50%;">
                            <div style="text-align:center;display:block;margin-left:auto;margin-right:auto;width:30%;">
                                <h1>""" + str(eventTitle) + """</h1>
                                <h3>""" + str(eventDescription) + """</h3>
                                <h4>Event Date: """ + str(eventStartDate) + """ from """ + str(eventStartTime) + """ to """ + str(eventEndTime) + """</h4>
                                <p>Event Location:  """ + str(eventLocation) + """</p>
                                <p>Event Type:  """ + str(eventType) + """</p>
                                <p>Event Visibility:  """ + str(eventVisibility) + """</p>
                                <p>Event Capacity:  """ + str(eventCapacity) + """</p>
                                <p>Event Registration Code:  """ + str(eventRegCode) + """</p>
                                <p>Pre-event Questionnare: {0}</p>
                             </div>
                        </div>
                    </div>
                </body>
            </html>
            """.format(items)
            msg.set_content(html, subtype='html')
            # print(msg)
            with smtplib.SMTP_SSL('smtp.mydomain.com', 465) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)

            return response

        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)


class SendTextAttendee(Resource):

    def post(self):
        print("In Send Text get")
        try:
            conn = connect()
            response = {}
            response['message'] = []
            data = request.get_json(force=True)
            recipient = data['recipient']
            subject = data['subject']
            message = data['message']
            eventTitle = data["event_title"]
            user_timezone = data['user_timezone']
            eventStartDate = data["event_start_date"]
            eventStartTime = data["event_start_time"]
            eventStartDateTime = eventStartDate + " " + eventStartTime
            eventStartDateTimeUTC = convertUtcToLocal(
                eventStartDateTime, user_timezone)

            eventStartDate = datetime.strptime(
                eventStartDateTimeUTC["date"], "%m/%d/%Y").strftime('%A, %B %d, %Y')

            eventStartTime = eventStartDateTimeUTC["time"]
            eventEndDate = data["event_end_date"]
            eventEndTime = data["event_end_time"]
            eventEndDateTime = eventEndDate + " " + eventEndTime
            eventEndDateTimeUTC = convertUtcToLocal(
                eventEndDateTime, user_timezone)
            eventEndDate = datetime.strptime(
                eventEndDateTimeUTC["date"], "%m/%d/%Y").strftime('%A, %B %d, %Y')
            eventEndTime = eventEndDateTimeUTC["time"]

            eventRegistrationCode = data["event_registration_code"]
            eventCheckinCode = (data["event_checkin_code"])

            for e in range(len(recipient)):
                text_msg = (subject + "\n" +
                            message + "\n" + 'Event: ' + eventTitle + "\n" + 'On ' + eventStartDate + ' from ' + eventStartTime + ' to ' + eventEndTime + "\n" + 'Registration Code: ' + eventRegistrationCode)
                # print(text_msg)
                try:
                    Send_Twilio_SMS2(
                        text_msg, recipient[e])
                    response['message'].append(
                        'Text message to ' +
                        recipient[e] + ' sent successfully')

                except:
                    response['message'].append('Text message to ' +
                                               recipient[e] + ' failed')

                    continue

                # print(response)

            return response

        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)


class AddEvent(Resource):
    def post(self):
        print("In AddEvent")
        response = {}
        items = {}

        try:
            conn = connect()
            # event = request.get_json(force=True)
            event = request.form
            print("**", event)
            event_organizer_uid = event["event_organizer_uid"]
            eventType = event["event_type"]
            eventVisibility = event["event_visibility"]
            eventTitle = event["event_title"]
            eventDescription = event["event_description"]
            eventCapacity = event["event_capacity"]
            eventLocation = event["event_location"]
            eventZip = event["event_zip"]
            eventLocationName = event["event_location_name"]
            eventStartTime = event["event_start_time"]
            eventEndTime = event["event_end_time"]
            eventStartDate = event["event_start_date"]
            eventEndDate = event["event_end_date"]
            # eventPhoto = event["eventPhoto"]
            preEventQuestionnaire = event["pre_event_questionnaire"]
            # print(preEventQuestionnaire)
            user_timezone = event["user_timezone"]
            # print(user_timezone)

            eventStartDateTime = eventStartDate + " " + eventStartTime
            # print(" eventStartDateTime ",eventStartDateTime)
            eventStartDateTimeUTC = convertLocalToUTC(
                eventStartDateTime, user_timezone)
            eventStartDate = eventStartDateTimeUTC["date"]
            eventStartTime = eventStartDateTimeUTC["time"]
            # print("eventStartDate ",eventStartDate, " eventStartTime ",eventStartTime)

            eventEndDateTime = eventEndDate + " " + eventEndTime
            # print(" eventEndDateTime ",eventEndDateTime)
            eventEndDateTimeUTC = convertLocalToUTC(
                eventEndDateTime, user_timezone)
            eventEndDate = eventEndDateTimeUTC["date"]
            eventEndTime = eventEndDateTimeUTC["time"]
            # print("eventEndDate ",eventEndDate, " eventEndTime ",eventEndTime)

            event_id_response = execute("CAll get_event_id;", "get", conn)
            new_event_id = event_id_response["result"][0]["new_id"]

            reg_code_res = execute(
                "CAll get_six_digit_code('registration');", "get", conn)
            event_reg_code = reg_code_res["result"][0]["new_code"]

            ci_code_res = execute(
                "CAll get_six_digit_code('checkin');", "get", conn)
            event_ci_code = ci_code_res["result"][0]["new_code"]

            images = []
            i = -1
            while True:
                print('in while')
                filename = f'img_{i}'
                if i == -1:
                    filename = 'img_cover'
                file = request.files.get(filename)
                print('in file', file)
                if file:
                    key = f'event/{new_event_id}/{filename}'
                    image = uploadImage(file, key, '')
                    print('in file', image)
                    images.append(image)
                else:
                    break
                i += 1
            print('after while', images)

            query = (
                """INSERT INTO find_me.events
                SET event_uid = \'""" + new_event_id + """\',
                    event_title = \'""" + str(eventTitle).replace("'", "''") + """\',
                    event_description = \'""" + str(eventDescription).replace("'", "''") + """\',
                    event_organizer_uid = \'""" + event_organizer_uid + """\',
                    event_type = \'""" + eventType + """\',
                    event_location = \'""" + eventLocation + """\',
                    event_location_name = \'""" + str(eventLocationName).replace("'", "''") + """\',
                    event_zip = \'""" + eventZip + """\',
                    event_start_date = \'""" + eventStartDate + """\',
                    event_end_date = \'""" + eventEndDate + """\',
                    event_start_time = \'""" + eventStartTime + """\',      
                    event_end_time = \'""" + eventEndTime + """\',      
                    event_visibility = \'""" + eventVisibility + """\',                       
                    event_capacity = \'""" + eventCapacity + """\',      
                    event_registration_code = \'""" + str(event_reg_code) + """\',      
                    event_checkin_code = \'""" + str(event_ci_code) + """\',      
                    event_photo  = \'""" + json.dumps(images) + """\',      
                    pre_event_questionnaire  = \'""" + str(preEventQuestionnaire).replace("'", "''") + """\';"""
            )

            print(query)
            items = execute(query, "post", conn)
            print(items)
            query2 = ("""SELECT * FROM events e
                    WHERE event_uid = \'""" + new_event_id + """\';
                        """)
            items2 = execute(query2, "get", conn)
            response["message"] = "successful"
            response["result"] = items2['result']
            return response, 200
        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)


class UpdateEvent(Resource):
    def put(self):
        print("In UpdateEvent", request.form)
        response = {}
        items = {}

        try:
            conn = connect()
            # event = request.get_json(force=True)
            event = request.form
            # print("**", event)
            event_uid = event["event_uid"]
            event_organizer_uid = event["event_organizer_uid"]
            eventType = event["event_type"]
            eventVisibility = event["event_visibility"]
            eventTitle = event["event_title"]
            eventDescription = event["event_description"]
            eventCapacity = event["event_capacity"]
            eventLocation = event["event_location"]
            eventLocationName = event["event_location_name"]
            eventZip = event["event_zip"]
            eventStartTime = event["event_start_time"]
            eventEndTime = event["event_end_time"]
            eventStartDate = event["event_start_date"]
            eventEndDate = event["event_end_date"]
            eventRegCode = event["event_registration_code"]
            preEventQuestionnaire = event["pre_event_questionnaire"]
            user_timezone = event["user_timezone"]

            eventStartDateTime = eventStartDate + " " + eventStartTime
            # print(" eventStartDateTime ",eventStartDateTime)
            print("herere ? 1382", eventStartDateTime, user_timezone)

            eventStartDateTimeUTC = convertLocalToUTC(
                eventStartDateTime, user_timezone)
            
            eventStartDate = eventStartDateTimeUTC["date"]
            eventStartTime = eventStartDateTimeUTC["time"]
            # print("eventStartDate ",eventStartDate, " eventStartTime ",eventStartTime)

            eventEndDateTime = eventEndDate + " " + eventEndTime
            # print(" eventEndDateTime ",eventEndDateTime)
            eventEndDateTimeUTC = convertLocalToUTC(
                eventEndDateTime, user_timezone)
            eventEndDate = eventEndDateTimeUTC["date"]
            eventEndTime = eventEndDateTimeUTC["time"]
            print("eventEndDate ",eventEndDate, " eventEndTime ",eventEndTime)
            # print("at end")
            print("images, typeof event[img_cover]", type(event) )
            #  checking if image has a file

            file = request.files.get('img_cover')

            updateImg = False
            if 'img_cover' in request.files:
                
                updateImg = True
                print("here received an image")
            
            if "img_cover" in request.form:
                print("here received a null")
                updateImg = True

            if not updateImg:
                print("nothing was received")
            # noUpdate = False
            # if 'img_cover' in request.files:
            #     img_cover_file = request.files['img_cover']
            #     if img_cover_file is not None:
            #         # File is uploaded, handle accordingly
            #         print("Image file uploaded img_cover_file", img_cover_file)
            #     else:
            #         # No file uploaded, handle accordingly
            #         print("No image field not sent")
            # # else:
            # elif "img_cover" in request.form:
            #     # img_cover field is either null or not sent

            #     print("default case")
            #     print("piritning event[img_cover]", event["img_cover"], type(event["img_cover"]), type(event))
            #     if event.get("img_cover") is None:
            #         print("no field img_cover is received, => no need to update the image")
            #     elif event["img_cover"] == "null":
            #         print("img_cover received as null => default image")
            #         noUpdate = True
            #     # print("img_cover field not sent")


            images = []
            i = -1
            imageFiles = {}

            if updateImg:
                while True:
                    # print('if true')
                    filename = f'img_{i}'
                    if i == -1:
                        filename = 'img_cover'
                    file = request.files.get(filename)
                    print("filename", filename, file)
                    s3Link = event.get(filename)
                    print(file, type(file))
                    print(s3Link, type(s3Link))
                    if file is not None and file != "null":
                    # if file:
                        imageFiles[filename] = file
                    elif s3Link is not None and s3Link != "null":
                    # elif s3Link:    
                        print("in s3Link ", s3Link)
                        imageFiles[filename] = s3Link                
                    else:
                        break
                    i = 1+1
                # print("image variable before update" ,)
                images = updateImagesEvent(imageFiles, event_uid)
                print('after while', images)
            # update image either to empty array or the provided image
            if updateImg:
                query = (
                    """UPDATE  events SET
                        event_title = \'""" + str(eventTitle).replace("'", "''").replace("\\n", " ") + """\',
                        event_description = \'""" + str(eventDescription).replace("'", "''").replace("\\n", " ") + """\',
                        event_organizer_uid = \'""" + event_organizer_uid + """\',
                        event_type = \'""" + eventType + """\',
                        event_location = \'""" + eventLocation + """\',
                        event_location_name = \'""" + str(eventLocationName).replace("'", "''") + """\',
                        event_zip = \'""" + eventZip + """\',
                        event_start_date = \'""" + eventStartDate + """\',
                        event_end_date = \'""" + eventEndDate + """\',
                        event_start_time = \'""" + eventStartTime + """\',      
                        event_end_time = \'""" + eventEndTime + """\',      
                        event_visibility = \'""" + eventVisibility + """\',                       
                        event_capacity = \'""" + eventCapacity + """\',         
                        event_photo  = \'""" + json.dumps(images) + """\',      
                        pre_event_questionnaire  = \'""" + str(preEventQuestionnaire).replace("'", "''").replace("\\n", " ") + """\',
                        event_registration_code = \'""" + eventRegCode + """\'
                        WHERE  event_uid = \'""" + event_uid + """\';"""
                )
            else:
                #  update without the image field.
                query = (
                    """UPDATE  events SET
                        event_title = \'""" + str(eventTitle).replace("'", "''").replace("\\n", " ") + """\',
                        event_description = \'""" + str(eventDescription).replace("'", "''").replace("\\n", " ") + """\',
                        event_organizer_uid = \'""" + event_organizer_uid + """\',
                        event_type = \'""" + eventType + """\',
                        event_location = \'""" + eventLocation + """\',
                        event_location_name = \'""" + str(eventLocationName).replace("'", "''") + """\',
                        event_zip = \'""" + eventZip + """\',
                        event_start_date = \'""" + eventStartDate + """\',
                        event_end_date = \'""" + eventEndDate + """\',
                        event_start_time = \'""" + eventStartTime + """\',      
                        event_end_time = \'""" + eventEndTime + """\',      
                        event_visibility = \'""" + eventVisibility + """\',                       
                        event_capacity = \'""" + eventCapacity + """\',         
                        pre_event_questionnaire  = \'""" + str(preEventQuestionnaire).replace("'", "''").replace("\\n", " ") + """\',
                        event_registration_code = \'""" + eventRegCode + """\'
                        WHERE  event_uid = \'""" + event_uid + """\';"""
                )

            print(query)
            items = execute(query, "post", conn)
            print(items)
            query2 = ("""SELECT * FROM events e
                    WHERE event_uid = \'""" + event_uid + """\';
                        """)
            items2 = execute(query2, "get", conn)
            response["message"] = "successful"
            response["result"] = items2['result']
            return response, 200
        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)


class EventUser(Resource):
    def get(self):
        print('in event user get')
        conn = connect()
        event = request.get_json(force=True)
        event_user_id = event['event_user_id']
        query = ("""SELECT * FROM event_user 
                    WHERE
                    event_user_uid = \'""" + event_user_id + """\';
                    """)
        items = execute(query, "get", conn)
        return items

    def post(self):
        print('in event user post')
        response = {}
        items = {}
        try:
            conn = connect()
            event = request.get_json(force=True)
            eu_user_id = event['eu_user_id']
            eu_event_id = event['eu_event_id']
            eu_qas = event['eu_qas']

            query0 = ("""WITH event_registrants AS (
                            SELECT COUNT(*) AS registrants, eu_event_id 
                            FROM find_me.event_user WHERE eu_event_id = \'""" + eu_event_id + """\'
                        )
                        SELECT IF(event_capacity = 'No Limit' OR
                        registrants < CAST(event_capacity AS UNSIGNED), '1', '0') AS event_limit
                        FROM find_me.events INNER JOIN event_registrants
                        ON eu_event_id = event_uid OR eu_event_id IS NULL
                        WHERE event_uid = \'""" + eu_event_id + """\';
                        """)
            items0 = execute(query0, "get", conn)["result"]
            if items0[0]["event_limit"] == "0":
                response["message"] = "Registration limit reached."
                return response

            query1 = ["CALL find_me.get_event_user_id;"]
            NewIDresponse = execute(query1[0], "get", conn)
            newEventUserID = NewIDresponse["result"][0]["new_id"]
            # print('before query', newEventUserID)

            query2 = ("""INSERT INTO find_me.event_user 
                            SET
                        event_user_uid = \'""" + newEventUserID + """\',
                        eu_user_id = \'""" + eu_user_id + """\',
                        eu_event_id = \'""" + eu_event_id + """\',
                        eu_qas = \'""" + (str(eu_qas).replace("'", "''").replace("\\n", " ")) + """\';
                        """)
            # print(query2)
            items = execute(query2, "post", conn)
            # print(items)
            query3 = ("""SELECT * FROM events e
                    WHERE event_uid = \'""" + eu_event_id + """\';
                        """)
            # print(query2)
            items2 = execute(query3, "get", conn)
            response["message"] = "successful"
            response["result"] = items2['result']
            return response
        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)

    def put(self):
        print('in event user put')
        response = {}
        items = {}
        try:
            conn = connect()
            event = request.get_json(force=True)
            event_user_uid = event['event_user_uid']
            eu_qas = event['eu_qas']

            query = ("""UPDATE  event_user 
                        SET
                        eu_qas = \'""" + (str(eu_qas).replace("'", "''").replace("\\n", " ")) + """\'
                        WHERE event_user_uid = \'""" + event_user_uid + """\';
                        """)
            print(query)
            items = execute(query, "post", conn)
            print(items)
            query2 = ("""SELECT * FROM event_user eu
                    LEFT JOIN events e
                    ON e.event_uid = eu.eu_event_id
                    WHERE event_user_uid = \'""" + event_user_uid + """\';
                        """)
            items2 = execute(query2, "get", conn)
            response["message"] = "Updated Successfully"
            response["result"] = items2['result']
            return response
        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)

    def delete(self):
        response = {}
        try:
            conn = connect()
            args = request.args
            event_uid = args["eventId"]
            user_uid = args['userId']

            query = ("""
                     DELETE FROM find_me.event_user 
                     WHERE eu_event_id = \'""" + event_uid + """\' 
                     AND eu_user_id = \'""" + user_uid + """\';
                     """)
            execute(query, "post", conn)
            response["message"] = "Deleted Successfully"
            return response
        except Exception as e:
            raise BadRequest("Request failed, please try again later.") from e
        finally:
            disconnect(conn)


class GetEventUser(Resource):
    def get(self):
        print('in event user get')
        conn = connect()
        response = {}
        response["message"] = "Successfully executed SQL query."
        response["code"]: 280
        response['result'] = []
        user_timezone = request.args.get('timeZone')
        eu_user_id = request.args.get('eu_user_id')

        # query = ("""SELECT * FROM event_user eu
        #             LEFT JOIN events e
        #             ON e.event_uid = eu.eu_event_id
        #             WHERE eu.eu_user_id = \'""" + eu_user_id + """\'
        #             ORDER BY e.event_start_date,e.event_start_time ASC;
        #             """)

        query = ("""SELECT * FROM find_me.event_user eu
                    LEFT JOIN find_me.events e
                    ON e.event_uid = eu.eu_event_id
                    LEFT JOIN (
                        SELECT eu_event_id, count(eu_qas) AS registrants, sum(eu_attend) AS attendees FROM find_me.event_user eu
                        GROUP BY eu_event_id )
                        AS a
                        ON eu.eu_event_id = a.eu_event_id
                    WHERE eu.eu_user_id = \'""" + eu_user_id + """\'
                    ORDER BY e.event_start_date,e.event_start_time ASC;
                 """)


        # print(query)
        items = execute(query, "get", conn)
        # pri   nt(items)
        items = eventListIterator(items, user_timezone)
        if len(items['result']) > 0:
            for item in items['result']:
                # converting end time to datetime 24hr format
                endTime = convert24(item['event_end_time'])
                endDatetime = datetime.strptime(item['event_end_date'] +
                                                ' ' + endTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventEndDatetime = datetime.strptime(
                    (endDatetime), "%Y-%m-%d %H:%M:%S")

                # converting current time to local datetime 24hr format
                currentDatetimeLocal = convertUtcToLocal(
                    datetime.now().strftime("%m/%d/%Y %I:%M %p"), user_timezone)
                currentDate = currentDatetimeLocal['date']
                currentTime = convert24(currentDatetimeLocal['time'])
                currentDatetime = datetime.strptime(currentDate +
                                                    ' ' + currentTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventCurrentDatetime = datetime.strptime(
                    (currentDatetime), "%Y-%m-%d %H:%M:%S")
                # comparing endtime and current time
                if eventEndDatetime > eventCurrentDatetime:
                    response['result'].append(item)

        return response


class CheckAlreadyRegistered(Resource):
    def get(self, event_id, user_id):
        response = {}
        print('in event user get')
        conn = connect()
        query = ("""SELECT * 
                    FROM event_user eu
                    LEFT JOIN events e
                    ON e.event_uid = eu.eu_event_id
                    WHERE
                    eu.eu_event_id = \'""" + event_id + """\' AND 
                    eu.eu_user_id = \'""" + user_id + """\';
                    """)
        items = execute(query, "get", conn)
        print(items['result'])
        if len(items['result']) == 0:
            response['message'] = 'Not Registered'
            response['result'] = items['result']
        else:
            response['message'] = 'Already Registered'
            response['result'] = items['result']
        return response


class UserProfile(Resource):
    def get(self):
        response = {}
        print('in event user get')
        conn = connect()
        event = request.get_json(force=True)
        profile_user_id = event['profile_user_id']
        query = ("""SELECT * FROM profile_user pu
                    LEFT JOIN users u
                    ON u.user_uid = pu.profile_user_id
                    WHERE
                    pu.profile_user_id = \'""" + profile_user_id + """\';
                    """)
        items = execute(query, "get", conn)
        print(items['result'])
        if len(items['result']) == 0:
            response['message'] = 'User Profile Doest Not Exist'
            response['result'] = items['result']
        else:
            response['message'] = 'User Profile Exists'
            response['result'] = items['result']
        return response

    def post(self):
        print('in event user post')
        response = {}
        items = {}
        try:
            conn = connect()
            event = request.form
            profile_user_id = event['profile_user_id']
            title = event['title']
            company = event['company']
            catch_phrase = event['catch_phrase']
            role = event['role']
            firstName = event['first_name']
            lastName = event['last_name']
            phoneNumber = event['phone_number']
            query1 = ["CALL find_me.get_profile_id;"]
            NewIDresponse = execute(query1[0], "get", conn)
            newProfileUserID = NewIDresponse["result"][0]["new_id"]
            print('before query', newProfileUserID)
            print(event)
            images = []
            i = -1
            while True:
                print('in while')
                filename = f'img_{i}'
                if i == -1:
                    filename = 'img_cover'
                file = request.files.get(filename)
                print('in file', file)
                if file:
                    key = f'user/{profile_user_id}/{filename}'
                    image = uploadImage(file, key, '')
                    print('in file', image)
                    images.append(image)
                else:
                    break
                i += 1
            print('after while', images)

            query2 = ("""INSERT INTO find_me.profile_user 
                            SET
                        profile_uid = \'""" + newProfileUserID + """\',
                        profile_user_id = \'""" + profile_user_id + """\',
                        title = \'""" + title + """\',
                        company = \'""" + company + """\',
                        catch_phrase = \'""" + str(catch_phrase).replace("'", "''").replace("\\n", " ") + """\',
                        images = \' """ + json.dumps(images) + """ \';
                        """)
            print(query2)
            items = execute(query2, "post", conn)
            print(items)
            query3 = ("""UPDATE find_me.users
                        SET  
                        first_name = \'""" + firstName + """\',
                        last_name = \'""" + lastName + """\',
                        phone_number = \'""" + phoneNumber + """\',
                        role = \'""" + role + """\'
                        WHERE user_uid = \'""" + profile_user_id + """\'
                        """)
            items2 = execute(query3, "post", conn)
            print(items2)
            response["message"] = "successful"
            response["result"] = newProfileUserID
            return response
        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)

    def put(self):
        print('in event user put')
        response = {}
        items = {}
        try:
            conn = connect()
            event = request.form
            profile_uid = event['profile_uid']
            profile_user_id = event['profile_user_id']
            title = event['title']
            company = event['company']
            catch_phrase = event['catch_phrase']
            role = event['role']
            firstName = event['first_name']
            lastName = event['last_name']
            phoneNumber = event['phone_number']

            images = []
            i = -1
            imageFiles = {}
            while True:
                # print('if true')
                filename = f'img_{i}'
                if i == -1:
                    filename = 'img_cover'
                file = request.files.get(filename)
                s3Link = event.get(filename)
                print(file)
                print(s3Link)
                if file:
                    imageFiles[filename] = file
                elif s3Link:
                    imageFiles[filename] = s3Link
                else:
                    break
                i = 1+1
            images = updateImagesUser(imageFiles, profile_user_id)
            print('after while', images)

            query2 = ("""UPDATE find_me.profile_user 
                            SET
                        profile_user_id = \'""" + profile_user_id + """\',
                        title = \'""" + title + """\',
                        company = \'""" + company + """\',
                        catch_phrase = \'""" + str(catch_phrase).replace("'", "''").replace("\\n", " ") + """\',
                        images = \' """ + json.dumps(images) + """ \'
                        WHERE profile_uid = \'""" + profile_uid + """\';
                        """)
            print(query2)
            items = execute(query2, "post", conn)
            print(items)
            query3 = ("""UPDATE find_me.users
                        SET  
                        first_name = \'""" + firstName + """\',
                        last_name = \'""" + lastName + """\',
                        phone_number = \'""" + phoneNumber + """\',
                        role = \'""" + role + """\'
                        WHERE user_uid = \'""" + profile_user_id + """\'
                        """)
            items2 = execute(query3, "post", conn)
            print(items2)

            response["message"] = "successful"
            response["result"] = profile_uid
            return response
        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)


class CheckUserProfile(Resource):
    def get(self, user_id):
        response = {}
        print('in event user get')
        conn = connect()
        query = ("""SELECT * 
                    FROM users u
                    LEFT JOIN  profile_user pu
                    ON u.user_uid = pu.profile_user_id
                    WHERE
                    u.user_uid = \'""" + user_id + """\';
                    """)
        items = execute(query, "get", conn)
        print(items['result'])
        if (items['result'][0]['profile_uid']) == None:
            response['message'] = 'User Profile Doest Not Exist'
            response['result'] = items['result']
        else:
            response['message'] = 'User Profile Exists'
            response['result'] = items['result']
        return response


class VerifyRegCode(Resource):
    def get(self, regCode):
        print("In VerifyRegCode")
        response = {}
        items = {}

        try:
            conn = connect()

            query = (
                """SELECT *
                        FROM find_me.events
                        WHERE event_registration_code = \'"""
                + regCode
                + """\';"""
            )
            print(query)
            items = execute(query, "get", conn)
            print(items)

            response["message"] = "successful"
            response["result"] = items

            return response, 200
        except:
            raise BadRequest("Request failed, please try again later.")
        finally:
            disconnect(conn)

class AlgorithmGraph(Resource):
    # def get(self):
    def post(self):
        print("INSIDE ALGORITHM ENDPOINT")
        # encoded_string=request.args.get('EventUsers')    
        # decoded_string = urllib.parse.unquote(encoded_string)
        # decoded_json_dict=json.loads(decoded_string)
        data = request.get_json()
        result=cosine_alg_trial(data)
        print("END OF ALGORITHM ENDPOINT")
        # print("argument: ",decoded_json_dict)
        return str(result),200
    
#  ORIGINAL
# class ShowCosine(Resource):
#     def get(self):
#         print("In ShowCosine")
#         encoded_string=request.args.get('EventUsers')    
#         decoded_string = urllib.parse.unquote(encoded_string)
#         decoded_json_dict=json.loads(decoded_string)
#         result=ShowCosineResults(decoded_json_dict)
#         print("END OF SHOW ENDPOINT")
#         # print("argument: ",decoded_json_dict)
#         return str(result),200

#  Post
class ShowCosine(Resource):
    def post(self):
        print("In ShowCosine")
        # encoded_string=request.args.get('EventUsers')    
        # decoded_string = urllib.parse.unquote(encoded_string)
        # decoded_json_dict=json.loads(decoded_string)
        data = request.get_json()
        result=ShowCosineResults(data)
        print("END OF SHOW ENDPOINT", result)
        # print("argument: ",decoded_json_dict)
        return str(result),200

#  Passing list of Attendees as Arguments
# class ShowCosine(Resource):
#     def get(self, attendees):
#         print("In ShowCosine ")
#         print(attendees)
#         encoded_string=request.args.get('EventUsers')    
#         decoded_string = urllib.parse.unquote(encoded_string)
#         decoded_json_dict=json.loads(decoded_string)
#         result=ShowCosineResults(decoded_json_dict)
#         print("END OF SHOW ENDPOINT")
#         # print("argument: ",decoded_json_dict)
#         return str(result),200

# Passing list of attendees as Form Data
# class ShowCosine(Resource):
#     def get(self):
#         print("In ShowCosine ")
#         data = request.form
#         print(data)
#         encoded_string=request.args.get('EventUsers')    
#         decoded_string = urllib.parse.unquote(encoded_string)
#         decoded_json_dict=json.loads(decoded_string)
#         result=ShowCosineResults(decoded_json_dict)
#         print("END OF SHOW ENDPOINT")
#         # print("argument: ",decoded_json_dict)
#         return str(result),200
    


class NetworkingGraph(Resource):
    def get(self):
        response = {}
        helper_map = {
            "Founder": ["Founder", "VC", "Looking for Next Opportunity"],
            "VC": ["Founder", "VC", "Looking for Next Opportunity"],
            "Looking for Next Opportunity": ["Founder", "Looking for Next Opportunity"],
        }
        try:
            args = request.args
            event_id = args["eventId"]
            registrant = args.get("registrant",False)
            query=""
            if(registrant):
                query = (
                """
                SELECT user_uid, first_name, last_name, role, images
                FROM find_me.users u INNER JOIN find_me.event_user eu 
                    ON u.user_uid = eu.eu_user_id
                    INNER JOIN find_me.profile_user pu 
                    ON u.user_uid = pu.profile_user_id
                WHERE eu.eu_event_id = \'"""
                + event_id
                + """\';
                """
            )
            else:
                query = (
                    """
                    SELECT user_uid, first_name, last_name, role, images
                    FROM find_me.users u INNER JOIN find_me.event_user eu 
                        ON u.user_uid = eu.eu_user_id
                        INNER JOIN find_me.profile_user pu 
                        ON u.user_uid = pu.profile_user_id
                    WHERE eu.eu_attend = 1 
                    AND eu.eu_event_id = \'"""
                    + event_id
                    + """\';
                    """
                )
            conn = connect()
            query_result = execute(query, "get", conn)["result"]

            # Finding connections for each user
            user_groups = {}
            for idx in range(len(query_result)):
                users = query_result.copy()
                center_user = users.pop(idx)
                user_group = {}
                user_group["inward_links"] = 0
                user_group["link_count"] = 0
                user_group["origin"] = center_user
                user_group["link_uids"] = []
                if center_user["user_uid"] in user_groups.keys():
                    user_group = user_groups[center_user["user_uid"]]
                user_group["outward_links"] = 0
                helped_roles = helper_map[center_user["role"]]
                for user in users:
                    if user["role"] in helped_roles and user_group["outward_links"]<6 and user_group["link_count"] < 6 :
                        is_inward = False
                        if user["user_uid"] in list(user_groups.keys()):
                            other_user_group = user_groups[user["user_uid"]]
                            if other_user_group["link_count"] >= 6 and center_user["user_uid"] not in other_user_group["link_uids"] or other_user_group["origin"]["user_uid"] == center_user["user_uid"] or other_user_group["inward_links"]>=6:
                                continue
                        if user["user_uid"] in list(user_group.keys()):
                            user_group[user["user_uid"]]["is_outward"] = True
                        else:
                            user_group[user["user_uid"]] = {
                                **user,
                                "is_outward" : True,
                            }
                            receiver_roles = helper_map[user["role"]]
                            if center_user["role"] in receiver_roles and not user_group[user["user_uid"]].get("is_inward"):
                                is_inward = True
                                user_group[user["user_uid"]]["is_inward"] = True
                                # user_group["inward_links"] = user_group["inward_links"] + 1
                            user_group["link_count"] = user_group["link_count"] + 1
                            user_group["link_uids"].append(user["user_uid"])
                        user_group["outward_links"] = user_group["outward_links"] + 1
                        if user["user_uid"] in list(user_groups.keys()):
                            other_user_group = user_groups[user["user_uid"]]
                            if center_user["user_uid"] in other_user_group.keys():
                                other_user_group[center_user["user_uid"]]["is_inward"] = True
                            else:
                                other_user_group[center_user["user_uid"]] = {
                                    **center_user,
                                    "is_inward" : True,
                                }
                                if is_inward:
                                    other_user_group[center_user["user_uid"]]["is_outward"] = True
                                    # other_user_group["outward_links"] = other_user_group["outward_links"] + 1
                                other_user_group["link_count"] = other_user_group["link_count"] + 1
                                other_user_group["link_uids"].append(center_user["user_uid"])
                            other_user_group["inward_links"] = other_user_group["inward_links"] + 1
                        else:
                            other_user_group = {
                                center_user["user_uid"]:{
                                    **center_user,
                                    "is_inward" : True,
                                },
                                "inward_links": 1,
                                "outward_links": 0,
                                "link_count": 1,
                                "origin": user,
                                "link_uids": [center_user["user_uid"]]
                            }
                            if is_inward:
                                other_user_group[center_user["user_uid"]]["is_outward"] = True
                                other_user_group["outward_links"] = other_user_group["outward_links"] + 1
                            user_groups[user["user_uid"]] = other_user_group
                user_groups[center_user["user_uid"]] = user_group

            #Minimize the deviation of user group link count
            #Sort the user groups based on the number of linked users
            key_func = lambda ug:ug[1]["link_count"]
            ugs_to_sort = {k:v for k,v in user_groups.items() if k not in ["initial_std_dev"]}
            sorted_user_groups_list = sorted(ugs_to_sort.items(), key=key_func)
            sorted_user_groups_list_rev = sorted(ugs_to_sort.items(), key=key_func, reverse=True)
            sorted_user_groups = {ug[0]: ug for ug in sorted_user_groups_list}
            sorted_user_groups_rev = {ug[0]: ug for ug in sorted_user_groups_list_rev}
            links_count_list = []
            for curr_user_group in sorted_user_groups.values():
                links_count_list.append(curr_user_group[1]["link_count"])
            prev_std_dev = np.std(links_count_list)
            user_groups["initial_std_dev"] = prev_std_dev
            if True:
                for idx_low, user_group_low_id in enumerate(sorted_user_groups):
                    for idx_high, user_group_high_id in enumerate(sorted_user_groups_rev):
                        if idx_high == len(sorted_user_groups)-idx_low-1:
                            break
                        user_group_low = user_groups[user_group_low_id]
                        user_group_high = user_groups[user_group_high_id]
                        user_to_link_to = user_group_low["origin"]
                        users_linked_to_high = [user_group_high[user_uid] for user_uid in user_group_high["link_uids"]]
                        is_moved_outward = False
                        is_moved_inward = False
                        heap_list = []
                        heapq.heapify(heap_list)
                        for user_linked_to_high in users_linked_to_high:
                            if user_linked_to_high["user_uid"] in user_group_low["link_uids"]:
                                continue
                            if user_to_link_to["user_uid"] != user_linked_to_high["user_uid"] and user_linked_to_high["user_uid"] not in user_group_low["link_uids"]:
                                helped_roles = helper_map[user_to_link_to["role"]]
                                if user_linked_to_high["role"] in helped_roles and len(user_group_low["link_uids"]) < 6:
                                    is_moved_outward = True
                                helped_roles = helper_map[user_linked_to_high["role"]]
                                if user_to_link_to["role"] in helped_roles and len(user_group_low["link_uids"]) < 6:
                                    is_moved_inward = True
                            if is_moved_outward or is_moved_inward:
                                new_links_counts_list = []
                                for idx, count in enumerate(links_count_list):
                                    if idx_low == idx:
                                        new_links_counts_list.append(count+1)
                                    elif len(sorted_user_groups)-idx_high-1 == idx:
                                        new_links_counts_list.append(count-1)
                                    else:
                                        new_links_counts_list.append(count)
                                next_std_dev = np.std(new_links_counts_list)
                                if next_std_dev < prev_std_dev:
                                    low_priority = 3
                                    if is_moved_outward and is_moved_inward:
                                        low_priority = 1
                                    elif is_moved_inward:
                                        low_priority = 2
                                    high_priority = 1
                                    if user_linked_to_high.get("is_outward") and user_linked_to_high.get("is_inward"):
                                        high_priority = 3
                                    elif user_linked_to_high.get("is_inward"):
                                        high_priority = 2
                                    heapq.heappush(heap_list, (
                                        high_priority,
                                        low_priority, 
                                        next_std_dev, 
                                        new_links_counts_list, 
                                        user_linked_to_high["user_uid"] 
                                    ))
                                    # prev_std_dev = next_std_dev
                                    # user_group_low[user_linked_to_high["user_uid"]] = {
                                    #     **user_linked_to_high,
                                    #     "is_outward" : is_moved_outward,
                                    #     "is_inward" : is_moved_inward,
                                    # }
                                    # user_group_low["link_uids"].append(user_linked_to_high["user_uid"])
                                    # user_group_low["link_count"] = user_group_low["link_count"] + 1
                                    # del user_group_high[user_linked_to_high["user_uid"]]
                                    # user_group_high["link_uids"].remove(user_linked_to_high["user_uid"])
                                    # user_group_high["link_count"] = user_group_high["link_count"] - 1
                                    # user_groups[user_group_low_id] = user_group_low
                                    # user_groups[user_group_high_id] = user_group_high
                                    # links_count_list = new_links_counts_list
                        
                        if len(heap_list) > 0:
                            user_to_remove_tuple = heapq.heappop(heap_list)
                            high_priority = user_to_remove_tuple[0]
                            low_priority = user_to_remove_tuple[1]
                            next_std_dev = user_to_remove_tuple[2]
                            prev_std_dev = next_std_dev
                            new_links_counts_list = user_to_remove_tuple[3]
                            user_linked_to_high = user_group_high[user_to_remove_tuple[4]]
                            user_group_low[user_linked_to_high["user_uid"]] = {
                                **user_linked_to_high,
                                "is_outward" : low_priority == 2 or low_priority == 3,
                                "is_inward" : low_priority == 1 or low_priority == 3,
                            }
                            if low_priority == 1 or low_priority == 3:
                                user_group_low["inward_links"] = user_group_low["inward_links"] + 1
                            if low_priority == 2 or low_priority == 3:
                                user_group_low["outward_links"] = user_group_low["outward_links"] + 1
                            if high_priority == 2 or high_priority == 1:
                                user_group_high["inward_links"] = user_group_high["inward_links"] - 1
                            if high_priority == 3 or high_priority == 1:
                                user_group_high["outward_links"] = user_group_high["outward_links"] - 1
                            user_group_low["link_uids"].append(user_linked_to_high["user_uid"])
                            user_group_low["link_count"] = user_group_low["link_count"] + 1
                            del user_group_high[user_linked_to_high["user_uid"]]
                            user_group_high["link_uids"].remove(user_linked_to_high["user_uid"])
                            user_group_high["link_count"] = user_group_high["link_count"] - 1
                            user_groups[user_group_low_id] = user_group_low
                            user_groups[user_group_high_id] = user_group_high
                            links_count_list = new_links_counts_list
            summary = {}
            for key, value in user_groups.items():
                if key != "initial_std_dev":
                    summary[key] = {
                        "inward_links": value["inward_links"],
                        "outward_links": value["outward_links"],
                        "total_links": value["link_count"],
                    }
            response["summary"] = summary
            user_groups["final_std_dev"] = prev_std_dev
            user_groups["link_counts"] = links_count_list
            response["message"] = "successful"
            response["user_groups"] = user_groups
            response["users"] = query_result
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class OverallGraph(Resource):
    def get(self):
        response = {}
        helper_map = {
            "Founder": ["Founder", "Looking for Next Opportunity"],
            "VC": ["VC"],
            "Looking for Next Opportunity": ["Looking for Next Opportunity"],
        }
        needer_map = {
            "Founder": ["VC"],
            "VC": ["Founder"],
            "Looking for Next Opportunity": ["Founder", "VC"],
        }
        try:
            args = request.args
            event_id = args["eventId"]
            query = (
                """
                SELECT user_uid, first_name, last_name, role, images
                FROM find_me.users u INNER JOIN find_me.event_user eu 
                    ON u.user_uid = eu.eu_user_id
                    INNER JOIN find_me.profile_user pu 
                    ON u.user_uid = pu.profile_user_id
                WHERE eu.eu_attend = 1 
                AND eu.eu_event_id = \'"""
                + event_id
                + """\';
                """
            )
            conn = connect()
            query_result = execute(query, "get", conn)["result"]
            # Finding connections for each user
            links = []
            for idx in range(len(query_result)):
                users = query_result.copy()
                user = users.pop(idx)
                # Finding who the current user can help
                needer_roles = set()
                for role in user["role"].split(", "):
                    needer_roles.update(needer_map[role])
                needers = []
                for idx, needer_user in enumerate(users):
                    if any(role in needer_roles for role in needer_user["role"].split(", ")):
                        needers.append({
                            "from": user["user_uid"],
                            "to": needer_user["user_uid"],
                        })
                    if any(role in helper_map[role] for role in needer_user["role"].split(", ")):
                        needers.append({
                            "from": needer_user["user_uid"],
                            "to": user["user_uid"],
                        })
                # Finding who can help the current user
                helper_roles = set()
                for role in user["role"].split(", "):
                    helper_roles.update(helper_map[role])
                helpers = []
                for idx, helper_user in enumerate(users):
                    if any(role in helper_roles for role in helper_user["role"].split(", ")):
                        helpers.append({
                            "from": helper_user["user_uid"],
                            "to": user["user_uid"],
                        })
                    if any(role in needer_map[role] for role in helper_user["role"].split(", ")):
                        helpers.append({
                            "from": user["user_uid"],
                            "to": helper_user["user_uid"],
                        })
                links = links + helpers + needers
            response["message"] = "successful"
            response["users"] = query_result
            response["links"] = links
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class EventAttendees(Resource):
    def get(self):
        print("In EventAttendees")
        response = {}
        try:
            args = request.args
            event_id = args["eventId"]
            attend_flag = args.get("attendFlag")
            attend_clause = ""
            if attend_flag is not None:
                attend_clause = (""" eu.eu_attend = \'"""
                                 + attend_flag
                                 + """\' AND""")
            query = (
                """
                SELECT user_uid, first_name, last_name, role, email, 
                    phone_number, images , eu_qas
                FROM find_me.users u INNER JOIN find_me.event_user eu 
                    ON u.user_uid = eu.eu_user_id
                    INNER JOIN find_me.profile_user pu 
                    ON u.user_uid = pu.profile_user_id
                WHERE""" +
                attend_clause
                + """ eu.eu_event_id = \'"""
                + event_id
                + """\';
                """
            )
            conn = connect()
            attendees = execute(query, "get", conn)["result"]

            response["message"] = "successful"
            response["attendees"] = attendees
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class GetEvents(Resource):
    def get(self):
        print("IN GET EVENTS")
        conn = connect()
        response = {}
        response["message"] = "Successfully executed SQL query."
        response["code"]: 280
        response['result'] = []
        user_timezone = request.args.get('timeZone')
        filters = ['event_start_date', 'event_organizer_uid', "event_uid", 
                   'event_location', 'event_zip', 'event_type']
        where = {}
        for filter in filters:
            filterValue = request.args.get(filter)

            if filterValue is not None:
                if filter == 'event_start_date':
                    filterValue = filterValue + " 12:00 AM"
                    utcDateTime = convertLocalToUTC(filterValue, user_timezone)
                    where[filter] = utcDateTime["date"] + \
                        " " + utcDateTime["time"]
                else:
                    where[filter] = filterValue

        if where == {}:
            print('in no filter')
            query = ("""SELECT * FROM find_me.events
                        ORDER BY event_start_date,event_start_time  ASC;
                        """)
            items = execute(query, "get", conn)
            items = eventListIterator(items, user_timezone)
            if len(items['result']) > 0:
                for item in items['result']:

                    query2 = ("""SELECT * FROM  event_user 
                                WHERE eu_event_id = \'""" + item['event_uid'] + """\'""")
                    items2 = execute(query2, "get", conn)
                    item['registrants'] = len(items2['result'])
                    # converting end time to datetime 24hr format
                    endTime = convert24(item['event_end_time'])
                    endDatetime = datetime.strptime(item['event_end_date'] +
                                                    ' ' + endTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                    eventEndDatetime = datetime.strptime(
                        (endDatetime), "%Y-%m-%d %H:%M:%S")

                    # converting current time to local datetime 24hr format
                    currentDatetimeLocal = convertUtcToLocal(
                        datetime.now().strftime("%m/%d/%Y %I:%M %p"), user_timezone)
                    currentDate = currentDatetimeLocal['date']
                    currentTime = convert24(currentDatetimeLocal['time'])
                    currentDatetime = datetime.strptime(currentDate +
                                                        ' ' + currentTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                    eventCurrentDatetime = datetime.strptime(
                        (currentDatetime), "%Y-%m-%d %H:%M:%S")
                    # comparing endtime and current time
                    if eventEndDatetime > eventCurrentDatetime:
                        response['result'].append(item)
        elif list(where.keys())[0] == 'event_start_date':
            query = (
                """
                WITH event_start AS (
                    SELECT event_uid,
                        STR_TO_DATE(
                            concat(event_start_date, ' ', event_start_time),
                            '%m/%d/%Y %h:%i %p'
                        ) AS start_datetime
                    FROM find_me.events e
                )
                SELECT e.*
                FROM find_me.events e
                    INNER JOIN event_start es ON e.event_uid = es.event_uid
                WHERE start_datetime BETWEEN STR_TO_DATE(\'"""
                + list(where.values())[0]
                + """\', '%m/%d/%Y %h:%i %p') AND STR_TO_DATE(\'"""
                + list(where.values())[0]
                + """\', '%m/%d/%Y %h:%i %p') + INTERVAL 1 DAY 
                ORDER BY start_datetime;
                """
            )
            items = execute(query, "get", conn)
            items = eventListIterator(items, user_timezone)
            if len(items['result']) > 0:
                for item in items['result']:
                    query2 = ("""SELECT * FROM  event_user 
                                WHERE eu_event_id = \'""" + item['event_uid'] + """\'""")
                    items2 = execute(query2, "get", conn)
                    item['registrants'] = len(items2['result'])
                    # converting end time to datetime 24hr format
                    endTime = convert24(item['event_end_time'])
                    endDatetime = datetime.strptime(item['event_end_date'] +
                                                    ' ' + endTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                    eventEndDatetime = datetime.strptime(
                        (endDatetime), "%Y-%m-%d %H:%M:%S")

                    # converting current time to local datetime 24hr format
                    currentDatetimeLocal = convertUtcToLocal(
                        datetime.now().strftime("%m/%d/%Y %I:%M %p"), user_timezone)
                    currentDate = currentDatetimeLocal['date']
                    currentTime = convert24(currentDatetimeLocal['time'])
                    currentDatetime = datetime.strptime(currentDate +
                                                        ' ' + currentTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                    eventCurrentDatetime = datetime.strptime(
                        (currentDatetime), "%Y-%m-%d %H:%M:%S")
                    # comparing endtime and current time
                    if eventEndDatetime > eventCurrentDatetime:
                        response['result'].append(item)
        else:

            query = ("""SELECT * 
                        FROM events 
                        WHERE """ + list(where.keys())[0] + """ = \'""" + list(where.values())[0] + """\'
                        ORDER BY event_start_date,event_start_time  ASC;
                        """)
            items = execute(query, "get", conn)
            items = eventListIterator(items, user_timezone)
            # print(items['result'])
            if len(items['result']) > 0:
                for item in items['result']:
                    query2 = ("""SELECT * FROM  event_user 
                                WHERE eu_event_id = \'""" + item['event_uid'] + """\'""")
                    items2 = execute(query2, "get", conn)
                    item['registrants'] = len(items2['result'])
                    # converting end time to datetime 24hr format
                    endTime = convert24(item['event_end_time'])
                    endDatetime = datetime.strptime(item['event_end_date'] +
                                                    ' ' + endTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                    eventEndDatetime = datetime.strptime(
                        (endDatetime), "%Y-%m-%d %H:%M:%S")

                    # converting current time to local datetime 24hr format
                    currentDatetimeLocal = convertUtcToLocal(
                        datetime.now().strftime("%m/%d/%Y %I:%M %p"), user_timezone)
                    currentDate = currentDatetimeLocal['date']
                    currentTime = convert24(currentDatetimeLocal['time'])
                    currentDatetime = datetime.strptime(currentDate +
                                                        ' ' + currentTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                    eventCurrentDatetime = datetime.strptime(
                        (currentDatetime), "%Y-%m-%d %H:%M:%S")
                    # comparing endtime and current time
                    if eventEndDatetime > eventCurrentDatetime:
                        response['result'].append(item)
        # print(item)

        # response = eventListIterator(response, user_timezone)

        # strip leading 0s from event time
        # print(response['result'])
        for item in response['result']:
            item['event_start_time'] = item['event_start_time'].lstrip("0")
            item['event_end_time'] = item['event_end_time'].lstrip("0")
        return response


class GetOrganizers(Resource):

    def get(self):
        conn = connect()
        response = {}
        response["message"] = "Successfully executed SQL query."
        response["code"]: 280
        response['result'] = []

        user_timezone = request.args.get('timeZone')
        query = ("""SELECT u.*, pu.*, e.*
                    FROM events e 
                    LEFT JOIN users u 
                    ON u.user_uid = e.event_organizer_uid
                    LEFT JOIN profile_user pu
                    ON u.user_uid = pu.profile_user_id;
                    """)
        items = execute(query, "get", conn)
        items = eventListIterator(items, user_timezone)
        print(items['result'])
        if len(items['result']) > 0:
            for item in items['result']:
                # converting end time to datetime 24hr format
                endTime = convert24(item['event_end_time'])
                endDatetime = datetime.strptime(item['event_end_date'] +
                                                ' ' + endTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventEndDatetime = datetime.strptime(
                    (endDatetime), "%Y-%m-%d %H:%M:%S")

                # converting current time to local datetime 24hr format
                currentDatetimeLocal = convertUtcToLocal(
                    datetime.now().strftime("%m/%d/%Y %I:%M %p"), user_timezone)
                currentDate = currentDatetimeLocal['date']
                currentTime = convert24(currentDatetimeLocal['time'])
                currentDatetime = datetime.strptime(currentDate +
                                                    ' ' + currentTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventCurrentDatetime = datetime.strptime(
                    (currentDatetime), "%Y-%m-%d %H:%M:%S")
                # comparing endtime and current time
                if eventEndDatetime > eventCurrentDatetime:
                    response['result'].append(item)
        # print(items)
        seen = collections.OrderedDict()
        users = response['result']
        for obj in users:
            print(obj)
            print(seen)
            # eliminate this check if you want the last item
            if obj['user_uid'] not in seen:
                seen[obj['user_uid']] = obj

        response['result'] = list(seen.values())

        print(list(seen.values()))

        return response


class IsOrganizer(Resource):
    def get(self):
        response = {}
        try:
            args = request.args
            user_uid = args["userId"]
            event_uid = args["eventId"]
            query = (
                """
                SELECT 1 FROM find_me.events
                WHERE event_organizer_uid = \'"""
                + user_uid
                + """\'
                    AND event_uid = \'"""
                + event_uid
                + """\';
                """
            )
            conn = connect()
            query_result = execute(query, "get", conn)["result"]
            is_organizer = False
            if len(query_result) > 0:
                is_organizer = True
            response["message"] = "successful"
            response["isOrganizer"] = is_organizer
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class VerifyCheckinCode(Resource):
    def post(self):
        response = {}
        try:
            payload = request.get_json()
            user_id = payload["userId"]
            event_uid = payload["eventId"]
            reg_Code = payload["regCode"]
            query = (
                """
                SELECT IF(
                        EXISTS(
                            SELECT 1
                            FROM find_me.event_user eu
                            WHERE eu.eu_user_id = \'"""
                + user_id
                + """\'     AND eu.eu_event_id = e.event_uid
                        ),
                        TRUE,
                        FALSE
                    ) AS has_registered
                FROM find_me.events e
                WHERE e.event_checkin_code = \'"""
                + reg_Code
                + """\' AND e.event_uid = \'"""
                + event_uid
                + """\';
                """
            )
            conn = connect()
            query_result = execute(query, "get", conn)["result"]
            if len(query_result) < 1:
                raise BadRequest
            response["message"] = "successful"
            response["hasRegistered"] = query_result[0]["has_registered"]
        except BadRequest as e:
            raise BadRequest("Please enter a valid code.") from e
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class CurrentEvents(Resource):
    def get(self):
        response = {}
        try:
            query = (
                """
                WITH event_start AS (
                    SELECT event_uid,
                        STR_TO_DATE(
                            concat(event_start_date, ' ', event_start_time),
                            '%m/%d/%Y %h:%i %p'
                        ) AS start_datetime
                    FROM find_me.events e
                )
                SELECT e.*
                FROM find_me.events e
                    INNER JOIN event_start es ON e.event_uid = es.event_uid
                WHERE start_datetime >= ( NOW() - INTERVAL 1 HOUR )
                ORDER BY start_datetime;
                """
            )
            conn = connect()
            # events = execute(query, "get", conn)["result"]
            events = execute(query, "get", conn)

            # converting event time from UTC to local timezone
            user_timezone = request.args.get('timeZone')
            events = eventListIterator(events, user_timezone)

            response["message"] = "successful"
            response["events"] = events["result"]
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class EventStatus(Resource):
    def get(self):
        response = {}
        try:
            args = request.args
            event_uid = args["eventId"]
            user_id = args["userId"]
            query = (
                """
                SELECT IF(
                        EXISTS(
                            SELECT 1
                            FROM find_me.event_user eu
                            WHERE eu.eu_user_id = \'"""
                + user_id
                + """\'     AND eu.eu_event_id = e.event_uid
                        ),
                        TRUE,
                        FALSE
                    ) AS has_registered,
                    event_status
                FROM find_me.events e
                WHERE e.event_uid = \'"""
                + event_uid
                + """\';
                """
            )
            conn = connect()
            query_result = execute(query, "get", conn, True)["result"]
            response["message"] = "successful"
            response["eventStarted"] = query_result[0]["event_status"]
            response["hasRegistered"] = query_result[0]["has_registered"]
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200

    def put(self):
        response = {}
        try:
            args = request.args
            event_uid = args["eventId"]
            event_status = args["eventStatus"]
            query = (
                """
                UPDATE find_me.events 
                SET event_status = \'"""
                + event_status
                + """\' 
                WHERE event_uid = \'"""
                + event_uid
                + """\';
                """
            )
            conn = connect()
            execute(query, "post", conn)
            response["message"] = "successful"
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class EventsByZipCodes(Resource):
    def post(self):
        print('in EventsByZipCodes')
        response = {}
        response["message"] = "Successfully executed SQL query."
        response["code"]: 280
        response['result'] = []
        conn = connect()
        location = request.get_json()
        miles = location['miles']
        zip_code = location['zip_code']
        zcdb = ZipCodeDatabase()
        in_radius = [z.zip for z in zcdb.get_zipcodes_around_radius(
            zip_code, int(miles))]  # ('ZIP', radius in miles)

        print(in_radius)
        print(type(in_radius))

        query = 'SELECT * from events where event_zip in {}'.format(
            tuple(in_radius))
        items = execute(query, "get", conn)
        print(items)

        # converting event time from UTC to local timezone
        user_timezone = request.args.get('timeZone')
        items = eventListIterator(items, user_timezone)
        if len(items['result']) > 0:
            for item in items['result']:
                # converting end time to datetime 24hr format
                endTime = convert24(item['event_end_time'])
                endDatetime = datetime.strptime(item['event_end_date'] +
                                                ' ' + endTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventEndDatetime = datetime.strptime(
                    (endDatetime), "%Y-%m-%d %H:%M:%S")

                # converting current time to local datetime 24hr format
                currentDatetimeLocal = convertUtcToLocal(
                    datetime.now().strftime("%m/%d/%Y %I:%M %p"), user_timezone)
                currentDate = currentDatetimeLocal['date']
                currentTime = convert24(currentDatetimeLocal['time'])
                currentDatetime = datetime.strptime(currentDate +
                                                    ' ' + currentTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventCurrentDatetime = datetime.strptime(
                    (currentDatetime), "%Y-%m-%d %H:%M:%S")
                # comparing endtime and current time
                if eventEndDatetime > eventCurrentDatetime:
                    response['result'].append(item)
        return response


class EventsByCity(Resource):
    def post(self):
        print('in EventsByZipCodes')
        response = {}
        response["message"] = "Successfully executed SQL query."
        response["code"]: 280
        response['result'] = []
        conn = connect()
        location = request.get_json()
        city = location['city']

        query = """SELECT * from events where event_location LIKE '%""" + city + """%' """
        items = execute(query, "get", conn)
        print(items)

        # converting event time from UTC to local timezone
        user_timezone = request.args.get('timeZone')
        items = eventListIterator(items, user_timezone)
        if len(items['result']) > 0:
            for item in items['result']:
                # converting end time to datetime 24hr format
                endTime = convert24(item['event_end_time'])
                endDatetime = datetime.strptime(item['event_end_date'] +
                                                ' ' + endTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventEndDatetime = datetime.strptime(
                    (endDatetime), "%Y-%m-%d %H:%M:%S")

                # converting current time to local datetime 24hr format
                currentDatetimeLocal = convertUtcToLocal(
                    datetime.now().strftime("%m/%d/%Y %I:%M %p"), user_timezone)
                currentDate = currentDatetimeLocal['date']
                currentTime = convert24(currentDatetimeLocal['time'])
                currentDatetime = datetime.strptime(currentDate +
                                                    ' ' + currentTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventCurrentDatetime = datetime.strptime(
                    (currentDatetime), "%Y-%m-%d %H:%M:%S")
                # comparing endtime and current time
                if eventEndDatetime > eventCurrentDatetime:
                    response['result'].append(item)
        return response


class EventsByAddress(Resource):
    def post(self):
        print('in EventsByAddress')
        response = {}
        response["message"] = "Successfully executed SQL query."
        response["code"]: 280
        response['result'] = []
        conn = connect()
        location = request.get_json()
        miles = location['miles']
        address = location['address']

        query = """SELECT * from events; """
        items = execute(query, "get", conn)

        # converting event time from UTC to local timezone
        user_timezone = request.args.get('timeZone')
        items = eventListIterator(items, user_timezone)
        if len(items['result']) > 0:
            for item in items['result']:
                # converting end time to datetime 24hr format
                endTime = convert24(item['event_end_time'])
                endDatetime = datetime.strptime(item['event_end_date'] +
                                                ' ' + endTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventEndDatetime = datetime.strptime(
                    (endDatetime), "%Y-%m-%d %H:%M:%S")

                # converting current time to local datetime 24hr format
                currentDatetimeLocal = convertUtcToLocal(
                    datetime.now().strftime("%m/%d/%Y %I:%M %p"), user_timezone)
                currentDate = currentDatetimeLocal['date']
                currentTime = convert24(currentDatetimeLocal['time'])
                currentDatetime = datetime.strptime(currentDate +
                                                    ' ' + currentTime, "%m/%d/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                eventCurrentDatetime = datetime.strptime(
                    (currentDatetime), "%Y-%m-%d %H:%M:%S")
                # comparing endtime and current time
                if eventEndDatetime > eventCurrentDatetime:
                    response['result'].append(item)
                    addresses = [[item['event_location'], address]]
                    print(addresses)
                    df = pd.DataFrame(addresses, columns=[
                                      'Address1', 'Address2'])
                    print(df)
                    geolocator = Nominatim(
                        user_agent=app.config['MAIL_USERNAME'])

                    df["Cor1"] = df["Address1"].apply(geolocator.geocode)
                    df['Cor2'] = df["Address2"].apply(geolocator.geocode)
                    df["lat1"] = df['Cor1'].apply(
                        lambda x: x.latitude if x != None else None)
                    df["lon1"] = df['Cor1'].apply(
                        lambda x: x.longitude if x != None else None)
                    df["lat2"] = df['Cor2'].apply(
                        lambda x: x.latitude if x != None else None)
                    df["lon2"] = df['Cor2'].apply(
                        lambda x: x.longitude if x != None else None)
                    print(df)
                    for index, row in df.iterrows():
                        address1 = (row["lat1"], row["lon1"])
                        address2 = (row["lat2"], row["lon2"])
                        try:
                            dist = (geodesic(address1, address2).miles)
                            print(dist, type(dist))
                            if dist <= int(miles):
                                response['result'].append(item)
                        except:
                            continue

        return response


class EventRegistrant(Resource):
    def get(self):
        response = {}
        try:
            args = request.args
            event_id = args["eventId"]
            registrant_id = args["registrantId"]
            query = (
                """
                SELECT user_uid, first_name, last_name, role, email, title,
                    phone_number, images, catch_phrase, eu_qas, company
                FROM find_me.users u INNER JOIN find_me.event_user eu 
                    ON u.user_uid = eu.eu_user_id
                    INNER JOIN find_me.profile_user pu 
                    ON u.user_uid = pu.profile_user_id
                WHERE eu.eu_event_id = \'"""
                + event_id
                + """\' 
                AND u.user_uid = \'"""
                + registrant_id
                + """\';
                """
            )
            conn = connect()
            registrant = execute(query, "get", conn)["result"][0]

            response["message"] = "successful"
            response["registrant"] = registrant
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class ProfileByUserUID(Resource):
    def get(self):
        response = {}
        try:
            args = request.args
            user_id = args["userId"]
            query = (
                """
                SELECT *
                FROM find_me.users u INNER JOIN find_me.profile_user pu 
                    ON u.user_uid = pu.profile_user_id
                WHERE u.user_uid = \'"""
                + user_id
                + """\';
                """
            )
            conn = connect()
            profile = execute(query, "get", conn)["result"][0]

            response["message"] = "successful"
            response["profile"] = profile
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class EventAttend(Resource):
    def put(self):
        response = {}
        try:
            args = request.args
            user_uid = args["userId"]
            event_uid = args["eventId"]
            attend_flag = args["attendFlag"]
            query = (
                """
                UPDATE find_me.event_user 
                SET eu_attend = \'"""
                + attend_flag
                + """\'
                WHERE eu_event_id = \'"""
                + event_uid
                + """\' AND eu_user_id = \'"""
                + user_uid
                + """\';
                """
            )
            conn = connect()
            execute(query, "post", conn)
            response["message"] = "successful"
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


# -- DEFINE APIS -------------------------------------------------------------------------------
# Define API routes
# event creation and editing endpoints
api.add_resource(AddEvent, "/api/v2/AddEvent")
api.add_resource(UpdateEvent, "/api/v2/UpdateEvent")
api.add_resource(GetEvents, "/api/v2/GetEvents")
api.add_resource(EventsByZipCodes, '/api/v2/EventsByZipCodes')
api.add_resource(EventsByCity, '/api/v2/EventsByCity')
api.add_resource(EventsByAddress, '/api/v2/EventsByAddress')
# event pre-registration endpoints
api.add_resource(VerifyRegCode, "/api/v2/verifyRegCode/<string:regCode>")

# arrive at event endpoints
api.add_resource(AlgorithmGraph, "/api/v2/algorithmgraph")
# api.add_resource(ShowCosine, "/api/v2/showcosineresults/<string:attendees>")
api.add_resource(ShowCosine, "/api/v2/showcosineresults")
api.add_resource(NetworkingGraph, "/api/v2/networkingGraph")
api.add_resource(OverallGraph, "/api/v2/overallGraph")
api.add_resource(EventAttendees, "/api/v2/eventAttendees")
api.add_resource(IsOrganizer, "/api/v2/isOrganizer")
api.add_resource(VerifyCheckinCode, "/api/v2/verifyCheckinCode")
api.add_resource(CurrentEvents, "/api/v2/currentEvents")
api.add_resource(EventStatus, "/api/v2/eventStatus")
api.add_resource(EventRegistrant, "/api/v2/eventRegistrant")
api.add_resource(ProfileByUserUID, "/api/v2/profileByUserUID")
api.add_resource(EventAttend, "/api/v2/eventAttend")

# add event and user relationship + questions

api.add_resource(EventUser, "/api/v2/EventUser")
api.add_resource(GetEventUser, "/api/v2/GetEventUser")
api.add_resource(CheckAlreadyRegistered,
                 "/api/v2/CheckAlreadyRegistered/<string:event_id>,<string:user_id>")
api.add_resource(GetOrganizers, "/api/v2/GetOrganizers")

# add user profile
api.add_resource(UserProfile, "/api/v2/UserProfile")
api.add_resource(CheckUserProfile, "/api/v2/CheckUserProfile/<string:user_id>")


api.add_resource(SendEmailAttendee, "/api/v2/SendEmailAttendee")
api.add_resource(SendTextAttendee, "/api/v2/SendTextAttendee")
api.add_resource(SendEventDetails, "/api/v2/SendEventDetails")

api.add_resource(TestCredentials, "/api/v2/TestCredentials")
api.add_resource(BroadCastEmail , "/api/v2/broadCastEmail")
# Run on below IP address and port
# Make sure port number is unused (i.e. don't use numbers 0-1023)
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=4000)
