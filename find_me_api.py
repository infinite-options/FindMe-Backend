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

from datetime import time, date, datetime, timedelta
import calendar

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

from werkzeug.exceptions import BadRequest, NotFound
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
# RDS_PW = RdsPw()

# Connect to MySQL database (API v2)


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
            # eventPhoto = event["eventPhoto"]
            questionList = event["preEventQuestionnaire"]
            preEventQuestionnaire = {i: key for i, key in enumerate(questionList)}

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

# -- DEFINE APIS -------------------------------------------------------------------------------

# Define API routes
# event creation and editing endpoints
api.add_resource(AddEvent, "/api/v2/addEvent")

# event pre-registration endpoints
api.add_resource(VerifyRegCode, "/api/v2/verifyRegCode/<string:regCode>")

# Run on below IP address and port
# Make sure port number is unused (i.e. don't use numbers 0-1023)
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=4000)
