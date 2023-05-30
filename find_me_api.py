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
import math
import httplib2
from botocore.response import StreamingBody
from datetime import time, date, datetime, timedelta
import calendar
import collections
from pytz import timezone
import random
import string
import stripe


from flask import Flask, request, render_template
from flask_restful import Resource, Api
from flask_cors import CORS
from flask_mail import Mail, Message

from collections import OrderedDict, Counter

# used for serializer email and error handling
# from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
# from flask_cors import CORS

from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from werkzeug.security import generate_password_hash, check_password_hash

import googleapiclient.discovery as discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

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

# Connect to MySQL database (API v2)
app.config["DEBUG"] = True


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

# Function to upload image to s3


def allowed_file(filename):
    # print("In allowed_file: ", filename)
    # Checks if the file is allowed to upload
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def uploadImage(file, key, content):
    bucket = 'io-find-me'
    contentType = 'image/jpeg'
    if type(file) == StreamingBody:
        print('if streaming body')
        contentType = content
        return

    if file and allowed_file(file.filename):
        print('if file')

        # image link
        filename = 'https://s3-us-west-1.amazonaws.com/' \
                   + str(bucket) + '/' + str(key)

        print("Back in Helper: ", filename)
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


def updateImages(imageFiles, id):
    content = []
    print('in updateImages')
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
        print(content[i])
        image = uploadImage(
            imageFiles[filename], key, content[i])

        images.append(image)
    return images


# -- Stored Procedures start here -------------------------------------------------------------------------------


# RUN STORED PROCEDURES


# -- FindMe Queries start here -------------------------------------------------------------------------------
class AddEvent(Resource):
    def post(self):
        print("In AddEvent")
        response = {}
        items = {}

        try:
            conn = connect()
            event = request.get_json(force=True)
            print("**", event)
            eventType = event["eventType"]
            eventVisibility = event["eventVisibility"]
            eventTitle = event["eventTitle"]
            eventDescription = event["eventDescription"]
            eventCapacity = event["eventCapacity"]
            eventStartTime = event["eventStartTime"]
            eventEndTime = event["eventEndTime"]
            eventStartDate = event["eventStartDate"]
            eventEndDate = event["eventEndDate"]
            # eventPhoto = event["eventPhoto"]
            questionList = event["preEventQuestionnaire"]

            preEventQuestionnaire = {i: key for i,
                                     key in enumerate(questionList)}

            event_id_response = execute("CAll get_event_id;", "get", conn)
            new_event_id = event_id_response["result"][0]["new_id"]
            print("**** ", eventType)
            print("**** ", preEventQuestionnaire)

            query = (
                """INSERT INTO events
                           SET event_uid = \'"""
                + new_event_id
                + """\',
                                event_title = \'"""
                + eventTitle
                + """\',
                                event_description = \'"""
                + eventDescription
                + """\',
                                event_type = \'"""
                + eventType
                + """\',
                                event_start_date = \'"""
                + eventStartDate
                + """\',
                                event_end_date = \'"""
                + eventEndDate
                + """\',
                               event_start_time = \'"""
                + eventStartTime
                + """\',
                                event_end_time = \'"""
                + eventEndTime
                + """\',
                                event_visibility = \'"""
                + eventVisibility
                + """\',
                                event_capacity = \'"""
                + eventCapacity
                + """\',
                               pre_event_questionnaire  = \'"""
                + json.dumps(preEventQuestionnaire)
                + """\';"""
            )

            print(query)
            items = execute(query, "post", conn)
            print(items)

            response["message"] = "successful"
            response["result"] = new_event_id
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

            query1 = ["CALL find_me.get_event_user_id;"]
            NewIDresponse = execute(query1[0], "get", conn)
            newEventUserID = NewIDresponse["result"][0]["new_id"]
            print('before query', newEventUserID)

            query2 = ("""INSERT INTO find_me.event_user 
                            SET
                        event_user_uid = \'""" + newEventUserID + """\',
                        eu_user_id = \'""" + eu_user_id + """\',
                        eu_event_id = \'""" + eu_event_id + """\',
                        eu_qas = \'""" + json.dumps(eu_qas) + """\';
                        """)
            print(query2)
            items = execute(query2, "post", conn)
            print(items)
            response["message"] = "successful"
            response["result"] = newEventUserID
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
                        eu_qas = \'""" + json.dumps(eu_qas) + """\'
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


class GetEventUser(Resource):
    def get(self, eu_user_id):
        print('in event user get')
        conn = connect()
        query = ("""SELECT * FROM event_user eu
                    LEFT JOIN events e
                    ON e.event_uid = eu.eu_event_id
                    WHERE eu.eu_user_id = \'""" + eu_user_id + """\';
                    """)
        items = execute(query, "get", conn)
        return items


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
                        catch_phrase = \'""" + catch_phrase + """\',
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
                return

            images = updateImages(imageFiles, profile_user_id)
            print('after while', images)

            query2 = ("""UPDATE find_me.profile_user 
                            SET
                        profile_user_id = \'""" + profile_user_id + """\',
                        title = \'""" + title + """\',
                        company = \'""" + company + """\',
                        catch_phrase = \'""" + catch_phrase + """\',
                        images = \' """ + json.dumps(images) + """ \'
                        WHERE profile_uid = \'""" + profile_uid + """\';
                        """)

            items = execute(query2, "post", conn)
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


class NetworkingGraph(Resource):
    def get(self):
        response = {}
        helper_map = {
            "Founder": ["Founder", "Looking for a new challenge"],
            "VC": ["VC"],
            "Looking for a new challenge": ["Looking for a new challenge"],
        }
        needer_map = {
            "Founder": ["VC"],
            "VC": ["Founder"],
            "Looking for a new challenge": ["Founder", "VC"],
        }
        try:
            args = request.args
            event_id = args["eventId"]
            user_id = args["userId"]
            query = (
                """
                SELECT user_uid, first_name, last_name, role
                FROM find_me.users u INNER JOIN find_me.event_user eu 
                    ON u.user_uid = eu.eu_user_id
                WHERE eu.eu_event_id = \'"""
                + event_id
                + """\';
                """
            )
            conn = connect()
            query_result = execute(query, "get", conn)["result"]
            user_group = []
            # Finding current user data
            user = {}
            for idx, value in enumerate(query_result):
                if user_id == value["user_uid"]:
                    user = query_result.pop(idx)
                    user["graph_code"] = 1
                    user_group.append(user)
            # Finding who the current user can help
            needer_roles = set()
            for role in user["role"].split(", "):
                needer_roles.update(needer_map[role])
            needers = []
            for idx, needer_user in enumerate(query_result):
                if any(role in needer_roles for role in needer_user["role"].split(", ")) and len(needers) < 3:
                    needer_user = query_result.pop(idx)
                    needer_user["graph_code"] = 5
                    user_group.append(needer_user)
                    needers.append({
                        "from": user["user_uid"],
                        "to": needer_user["user_uid"],
                    })
            # Finding who can help the current user
            helper_roles = set()
            for role in user["role"].split(", "):
                helper_roles.update(helper_map[role])
            helpers = []
            for idx, helper_user in enumerate(query_result):
                if any(role in helper_roles for role in helper_user["role"].split(", ")) and len(helpers) < 3:
                    helper_user = query_result.pop(idx)
                    helper_user["graph_code"] = 15
                    user_group.append(helper_user)
                    helpers.append({
                        "from": helper_user["user_uid"],
                        "to": user["user_uid"],
                    })
            response["message"] = "successful"
            response["users"] = user_group
            response["links"] = helpers + needers
        except Exception as e:
            raise InternalServerError("An unknown error occured.") from e
        finally:
            disconnect(conn)
        return response, 200


class EventAttendees(Resource):
    def get(self):
        response = {}
        try:
            args = request.args
            event_id = args["eventId"]
            query = (
                """
                SELECT user_uid, first_name, last_name, role
                FROM find_me.users u INNER JOIN find_me.event_user eu 
                    ON u.user_uid = eu.eu_user_id
                WHERE eu.eu_event_id = \'"""
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
        conn = connect()
        filters = ['event_start_date', 'event_organizer_uid',
                   'event_location', 'event_zip', 'event_type']
        where = {}
        for filter in filters:
            filterValue = request.args.get(filter)

            if filterValue is not None:
                where[filter] = filterValue

        if where == {}:
            query = ("""SELECT * FROM events;
                        """)
            items = execute(query, "get", conn)

        else:

            query = ("""SELECT * 
                        FROM events 
                        WHERE """ + list(where.keys())[0] + """ = \'""" + list(where.values())[0] + """\';
                        """)
            items = execute(query, "get", conn)

        return items


class GetOrganizers(Resource):

    def get(self):
        conn = connect()
        response = {}
        response["message"] = "Successfully executed SQL query."
        response["code"]: 280
        response['result'] = []

        query = ("""SELECT u.* 
                    FROM events e 
                    LEFT JOIN users u 
                    ON u.user_uid = e.event_organizer_uid;
                    """)
        items = execute(query, "get", conn)
        # print(items)
        seen = collections.OrderedDict()
        users = items['result']
        for obj in users:
            print(obj)
            print(seen)
            # eliminate this check if you want the last item
            if obj['user_uid'] not in seen:
                seen[obj['user_uid']] = obj

        response['result'] = list(seen.values())

        print(list(seen.values()))
        # for user in items['result']:
        #     print(user)
        #     quer_events = ("""SELECT *
        #             FROM events e WHERE event_organizer_uid = \'""" + user['user_uid'] + """\' ;
        #             """)
        #     items_events = execute(quer_events, 'get', conn)
        #     if len(items_events['result']) > 0:
        #         response['result'] = response['result'].append(user)

        return response


# -- DEFINE APIS -------------------------------------------------------------------------------
# Define API routes
# event creation and editing endpoints
api.add_resource(AddEvent, "/api/v2/AddEvent")
api.add_resource(GetEvents, "/api/v2/GetEvents")

# event pre-registration endpoints
api.add_resource(VerifyRegCode, "/api/v2/verifyRegCode/<string:regCode>")


# networking endpoints
api.add_resource(NetworkingGraph, "/api/v2/networkingGraph")
api.add_resource(EventAttendees, "/api/v2/eventAttendees")

# add event and user relationship + questions

api.add_resource(EventUser, "/api/v2/EventUser")
api.add_resource(GetEventUser, "/api/v2/GetEventUser/<string:eu_user_id>")
api.add_resource(CheckAlreadyRegistered,
                 "/api/v2/CheckAlreadyRegistered/<string:event_id>,<string:user_id>")
api.add_resource(GetOrganizers, "/api/v2/GetOrganizers")

# add user profile
api.add_resource(UserProfile, "/api/v2/UserProfile")
api.add_resource(CheckUserProfile, "/api/v2/CheckUserProfile/<string:user_id>")


# Run on below IP address and port
# Make sure port number is unused (i.e. don't use numbers 0-1023)
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=4000)
