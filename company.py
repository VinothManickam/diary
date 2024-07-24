from flask import Flask, jsonify, request, make_response, current_app, send_file
import requests
import json
from bson import json_util
from flask_pymongo import PyMongo, DESCENDING
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from bson import ObjectId
from flask_cors import CORS
from json import JSONEncoder
from werkzeug.utils import secure_filename
import markdown
from bs4 import BeautifulSoup
from collections import Counter
from flask_caching import Cache
import uuid
import logging
import base64
import pymongo
from bson import ObjectId
from PIL import ImageFont, ImageDraw, Image
from gtts import gTTS
from moviepy.editor import ImageSequenceClip, AudioFileClip
from pydub import AudioSegment
import colorsys
import numpy as np
import time


load_dotenv()
app = Flask(__name__)

cors = CORS(app, resources={
     r"/api/*": {"origins": "*"},
     r"/api/fetch-content": {"origins": "*"}
})

# Configure the Flask-Caching extension
app.config['CACHE_TYPE'] = "simple"
cache = Cache(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)



class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()  # Convert datetime objects to string
        return super(CustomJSONEncoder, self).default(obj)

app.json_encoder = CustomJSONEncoder





# Set MongoDB connection string
mongo_connection_string = os.environ.get('MONGO_CONNECTION_STRING')
app.config['MONGO_URI'] = mongo_connection_string
UPLOAD_FOLDER = 'uploads'  # temporary storage folder
ALLOWED_EXTENSIONS = {'md'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


mongo = PyMongo(app)

diaryblog_space_collection = mongo.db.diaryblog_space
diaryblog_post_collection = mongo.db.diaryblog_post
followers_collection = mongo.db.followers_data
template_collection = mongo.db.blogpost_template
digital_marketing_collection = mongo.db.digital_marketing
digital_marketing_templates_collection = mongo.db.email_templates_digital_marketing
user_collection = mongo.db.users


secret_key = os.environ.get('SECRET_KEY')
current_time = datetime.now()

def parse_to_datetime(timestamp_str):
    try:
        return datetime.fromisoformat(timestamp_str)
    except Exception:
        return datetime.min

def is_token_expired(token, secret_key):
    try:
        jwt.decode(token, secret_key, algorithms=['HS256'])
        return False
    except jwt.ExpiredSignatureError:
        return True
    except jwt.InvalidTokenError:
        return True

def decode_jwt_token(token):
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return decoded_payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_response_data(token):
    decoded_data = decode_jwt_token(token)
    user = decoded_data['user']
    if user:
        username = decoded_data.get('name')
        license = decoded_data.get('license')
        diaryblogAccess = decoded_data.get('diaryblogAccess')
        typeitAccess = decoded_data.get('typeitAccess')

        response_data = {
            'Username': username,
            'License': license,
            'DiaryblogAccess': diaryblogAccess,
            'TypeitAccess': typeitAccess
        }
        return response_data
    else:
        return None
    

def jsonify_objectid(data):
    """Converts any ObjectId fields to string."""
    if isinstance(data, ObjectId):
        return str(data)
    if isinstance(data, (list, tuple)):
        return [jsonify_objectid(item) for item in data]
    if isinstance(data, dict):
        return {key: jsonify_objectid(value) for key, value in data.items()}
    return data

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def send_email_notification_newpost(recipients, post_title, post_description_text, post_imageUrl,blogId,postId, username, blogSpaceName, userId, email_subject):
    try:
        url = 'https://api.brevo.com/v3/smtp/email'
        brevo_api_key = os.environ.get('BREVO_API_KEY')
        print("brevo_api_key",brevo_api_key)
        if brevo_api_key is None:
            raise ValueError("BREVO_API_KEY environment variable is not set.")
        
        headers = {
            'accept': 'application/json',
            'api-key': brevo_api_key,
            'content-type': 'application/json'
        }
        payload = {
            "sender": {
                "email": "universe@admin.com",
                "name": "Universe"
            },
            "subject": email_subject,
            "templateId": 1,
            "params": {
                "title": post_title,
                "description": post_description_text,
                "imageUrl": post_imageUrl,
                "blogId": blogId,
                "postId": postId,
                "username": username,
                "blogSpaceName": blogSpaceName,
                "userId": userId,
                "customHtml": """<div style="display: flex; align-items: center; color: #3b3f44; margin-bottom: 0.5rem; margin-top: 0.5rem;">
                                    <img src="data:image/jpeg;base64, {imageBase64}" alt="avatar" style="object-fit: cover; width: 2.5rem; height: 2.5rem; margin-left: 0.5rem; margin-right: 0.5rem; border-radius: 9999px;">
                                    <span style="display: flex; flex-direction: column;">
                                      <a href="https://diaryblog.connectingpeopletech.com/profile?user_id={userId}" style="font-size: 1rem; text-decoration: none; color: inherit; cursor: pointer; text-align: left;">{username}</a>
                                      <div style="display: flex; flex-direction: row; color: #3b3f44; font-size: 0.875rem; text-align: center; align-items: center; justify-content: space-between;">
                                        <img src="{blogSpaceImageUrl}" alt="Blog Space" style="object-fit: fill; width: 1rem; height: 1rem; border-radius: 9999px; margin-right: 0.5rem;">
                                        <a href="https://diaryblog.connectingpeopletech.com/{blogId}/viewposts" style="text-decoration: none; color: #3b3f44; cursor: pointer; margin-right: 0.5rem;">{blogSpaceName}</a>
                                        <a href="https://diaryblog.connectingpeopletech.com/{blogId}/subscribe" style="color: #007bff; font-weight: bold; text-decoration: underline; cursor: pointer; margin-right: 0.5rem;">Follow</a>
                                      </div>
                                    </span>
                                  </div>""",
            },
            "messageVersions": []
        }

        print("recipients:",recipients)

        for recipient in recipients:
            message_version = {
                "bcc": [
                    {
                        "email": recipient
                    }
                ],
                "params": {
                    "post_title": post_title,
                    "post_content": post_description_text,
                    "post_imageUrl": post_imageUrl,
                    "blogId": blogId,
                    "postId": postId
                },
                "subject": email_subject,
            }
            payload['messageVersions'].append(message_version)

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        print("Response of send_email_notification_newpost:", response)
        return response
    
    except requests.HTTPError as e:
        print("HTTP Error while sending email notification:", e)
        print("Response text:", e.response.text)
        return None

    except requests.RequestException as e:
        print("Error sending email notification:", e)
        return None

    except Exception as e:
        print("An unexpected error occurred:", e)
        return None


@app.route('/api/diaryblog_space', methods=['GET'])
def get_all_blogspaces():
    blogspaces = list(diaryblog_space_collection.find())
    
    # Use MongoDB's provided json_util.dumps to serialize the data
    blogspaces_json = json.loads(json_util.dumps(blogspaces))
    
    return jsonify(blogspaces_json)

@app.route('/api/diaryblog_space/<string:user_id>', methods=['GET'])
def get_blogspaces_by_user(user_id):
    user_obj_id = ObjectId(user_id)
    blogspaces = list(diaryblog_space_collection.find({"user_id": user_obj_id}))
    return jsonify(blogspaces)

@app.route('/api/blogSpace/<blogSpaceId>', methods=['GET'])
def get_blog_space_by_id(blogSpaceId):
    try:
        # Convert the blogSpaceId to an ObjectId for querying MongoDB
        # blog_space_object_id = ObjectId(blogSpaceId)
        
        # Fetch the blog space document related to the provided ID
        blog_space_data = diaryblog_space_collection.find_one({"_id": ObjectId(blogSpaceId)})

        # If the document exists, return it
        print(blog_space_data)
        if blog_space_data:
            return jsonify({
                '_id': str(blog_space_data['_id']),
            'name': blog_space_data['name'],
            'category': blog_space_data['category'],
            'description': blog_space_data.get('description', ''),  # Optional description
            'image_url': blog_space_data.get('image_url', ''), 
            'blogPosts': [str(post_id) for post_id in blog_space_data['blogPosts']],  # Convert ObjectId's to strings here
            'owner': blog_space_data['owner'],
            'createDate': blog_space_data['createDate'],
            'updateDate': blog_space_data['updateDate'],
            'views':blog_space_data['views'],
            'total_likes':blog_space_data.get('total_likes', ''), 
            'followers':blog_space_data.get('followers',''),
            'total_comments_count':blog_space_data.get('total_comments_count','')
            }), 200

        else:
            # Return a 404 status code if the blog space with the given ID is not found
            return jsonify({"message": "Blog space not found"}), 404
    except Exception as e:
        # Handle any exceptions, such as invalid ObjectId format
        return jsonify({"message": str(e)}), 400



@app.route('/api/blogSpace/<blogSpaceId>', methods=['PUT'])
def update_blog_space(blogSpaceId):
    try:
        existing_blog_space_data = diaryblog_space_collection.find_one({"_id": ObjectId(blogSpaceId)})

        if existing_blog_space_data:
            # Update the fields based on the data sent in the request
            data = request.get_json()
 # Trim the name to remove any trailing spaces
            if 'name' in data:
                data['name'] = data['name'].strip()
            
            existing_blog_space_data['name'] = data.get('name', existing_blog_space_data['name'])
            existing_blog_space_data['category'] = data.get('category', existing_blog_space_data['category'])
            existing_blog_space_data['description'] = data.get('description', '')  # Use empty string as default
            existing_blog_space_data['image_url'] = data.get('image_url', existing_blog_space_data.get('image_url', ''))
            # Update other fields as needed

            # Update the document in the database
            diaryblog_space_collection.update_one({"_id": ObjectId(blogSpaceId)}, {"$set": existing_blog_space_data})

            return jsonify({"message": "Blog space updated successfully"}), 200
        else:
            return jsonify({"message": "Blog space not found"}), 404

    except Exception as e:
        # Handle any exceptions, such as invalid ObjectId format or other errors
        return jsonify({"message": str(e)}), 400




@app.route('/api/diaryblog_space/user/<user_id>', methods=['GET'])
def get_diary_blog_space_by_user(user_id):
    diary_blog_spaces = list(diaryblog_space_collection.find({"owner": user_id}))

    if diary_blog_spaces:
        return jsonify([{
            '_id': str(space['_id']),
            'name': space['name'],
            'category': space['category'],
           "description": space.get('description', ''),  # Optional description with default value
            'image_url': space.get('image_url', ''), 
            'blogPosts': [str(post_id) for post_id in space['blogPosts']],  # Convert ObjectId's to strings here
            'owner': space['owner'],
            'createDate': space['createDate'],
            'updateDate': space['updateDate'],
            'views': space['views'],
            'total_likes': space.get('total_likes', ''), 
            'followers': space.get('followers', ''),
            'total_comments_count': space.get('total_comments_count', ''),  # Added comma here
            'blogSpace': str(space['_id'])  # Include blogSpace ID
        } for space in diary_blog_spaces])
    else:
        return jsonify({"error": "blog spaces not found for the given user"}), 404

@app.route('/api/diaryblog_space', methods=['POST'])
def create_blog_space():
    # Get the token from the 'Authorization' header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = auth_header.split(' ')[1]

    # Check if the token has expired
    if is_token_expired(token, secret_key):
        return jsonify({"error": "Token has expired"}), 401

    # Decode the token directly here
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "Invalid or expired token"}), 401

    # user_id = decoded_payload['id']
    user = decoded_payload['user']
    user_id = user['id']
    diaryblogAccess = True


    if diaryblogAccess:  # Assuming diaryblogAccess allows creating spaces. Adjust if needed.
        data = request.get_json()

         # Trim the name to remove any trailing spaces
        data['name'] = data['name'].strip()

        # Check if the blog space with the given name already exists
        existing_space = diaryblog_space_collection.find_one({"name": data['name']})
        if existing_space:
            return jsonify({"error": "Blog space with this name already exists"}), 400

        # Create the new blog space
        new_space = {
            "name": data['name'],  # Replace 'name' with 'title'
            "category": data.get('category'),
            "description": data.get('description', ''),  # Optional description
            "image_url":data['image_url'],
            "blogPosts": [],  # Empty list as it's a new space
            "owner": user_id,  # Here we use the decoded user ID
            "createDate": datetime.utcnow(),
            "updateDate": datetime.utcnow(),
            "views":0,
            "total_likes":0,
            "followers":0,
            "total_comments_count":0
        }

        # Insert the new space into diaryblog_space_collection
        space_id = diaryblog_space_collection.insert_one(new_space).inserted_id

        return jsonify({"message": "Blog space created successfully", "id": str(space_id), "blog details": jsonify_objectid(new_space)}), 201

    else:
        return jsonify({"error": "Not sufficient privilege to create a blog space"}), 401

@app.route('/api/posts/<string:blog_space_name>', methods=['POST'])
def create_blog_post(blog_space_name):
    # ... [Token validation remains unchanged] ...
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = auth_header.split(' ')[1]

    # Check if the token has expired
    if is_token_expired(token, secret_key):
        return jsonify({"error": "Token has expired"}), 401

    # Decode the token and get user-specific data using get_response_data function
    user_data = get_response_data(token)

    print(user_data)
    if not user_data:
        return jsonify({"error": "Invalid token"}), 401
    
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "Invalid or expired token"}), 401

    # user_id = decoded_payload['id']
    user = decoded_payload['user']
    user_id = user['id']

    # license = user_data.get('License')
    # diaryblogAccess = user_data.get('DiaryblogAccess')
    diaryblogAccess = True

    # if not license:
    #     return jsonify({"error": "Not sufficient privilege"}), 401


    if diaryblogAccess:
        blog_space_data = diaryblog_space_collection.find_one({"name": blog_space_name})
        if not blog_space_data:
            return jsonify({"error": "Blog space not found"}), 404

        data = request.get_json()
        # status = data.get('status')

        # Create the new blog post
        new_post = {
            "blogSpace": blog_space_data['_id'],
            "title": data['title'],
            "imageUrl": data['imageUrl'],
            "description": data['description'],
            "author": user_id,
            "status": data.get('status', 'draft'), 
            "category": data.get('category', 'Default Category'),
            "createDate": datetime.utcnow(),
            "updateDate": datetime.utcnow(),
            "views": 0

        }

        # Insert the new post into diaryblog_post_collection and get its ID
        post_id = diaryblog_post_collection.insert_one(new_post).inserted_id

        # if status=="preview":
        #     diaryblog_post_collection.update_one(
        #         {"_id": ObjectId(post_id)},
        #         {"$push": {"pkey": data.get('pkey')},}
        #     )

        # Add the new post's ID to the blogPosts array and update the updateDate for the blog space
        diaryblog_space_collection.update_one(
            {"name": blog_space_name},
            {
                "$push": {"blogPosts": post_id},
                "$set": {"updateDate": datetime.utcnow()}
            }
        )

        response_post = {
            "_id": str(post_id),
            "blogSpace": str(new_post["blogSpace"]),
            "title": new_post["title"],
            "description": new_post["description"],
            "imageUrl": new_post["imageUrl"],
            "author": new_post["author"],
            "status": new_post["status"],
            "category": new_post["category"],
            "createDate": new_post["createDate"],
            "updateDate": new_post["updateDate"],
            "views": new_post["views"],
            
        }
        return jsonify(response_post), 201
    
    else:
        return jsonify({"error": "Not sufficient privilege for this blog space"}), 401
    
    


@app.route('/api/posts/<string:blog_space_name>/<string:post_id>', methods=['PUT'])
def update_blog_post(blog_space_name, post_id):

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401
    token = auth_header.split(' ')[1]
    if is_token_expired(token, secret_key):
        return jsonify({"error": "Token has expired"}), 401

    
    user_data = get_response_data(token)
    if not user_data:
        return jsonify({"error": "Invalid token"}), 401
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "Invalid or expired token"}), 401
    

    user = decoded_payload['user']
    user_id = user['id']

    diaryblogAccess = True

    if diaryblogAccess:
        blog_space_data = diaryblog_space_collection.find_one({"name": blog_space_name})
        if not blog_space_data:
            return jsonify({"error": "Blog space not found"}), 404

        data = request.get_json()
        status = data.get('status')

        if status=="preview":
            diaryblog_post_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$set": {"pkey": str(data.get('pkey'))},}
            )

        # Update the existing blog post
        updated_post = {
            "title": data.get('title'),
            "imageUrl": data.get('imageUrl'),
            "description": data.get('description'),
            "author": user_id,
            "status": data.get('status'), 
            "category": data.get('category'),
            "updateDate": datetime.utcnow(),
        }

        # Update the post in diaryblog_post_collection
        diaryblog_post_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": updated_post}
        )

        updated_post_data = diaryblog_post_collection.find_one({"_id": ObjectId(post_id)})

        if not updated_post_data:
            return jsonify({"error": "Post not found"}), 404

        response_post = {
            "_id": str(updated_post_data['_id']),
            "blogSpace": str(blog_space_data['_id']),
            "title": updated_post_data["title"],
            "description": updated_post_data["description"],
            "imageUrl": updated_post_data["imageUrl"],
            "author": updated_post_data["author"],
            "status": updated_post_data["status"],
            "category": updated_post_data["category"],
            "createDate": updated_post_data["createDate"],
            "updateDate": updated_post_data["updateDate"],
            "views": updated_post_data["views"],
            "pkey": updated_post_data.get('pkey'),
        }
        return jsonify(response_post), 200
    
    else:
        return jsonify({"error": "Not sufficient privilege for this blog space"}), 401





@app.route('/api/posts/<string:blog_space_name>', methods=['GET'])
def get_blog_posts(blog_space_name):
    # Fetch the blog space data
    blog_space_data = diaryblog_space_collection.find_one({"name": blog_space_name})
    
    # Check if the blog space exists
    if not blog_space_data:
        return jsonify({"error": "Blog space not found"}), 404

    # Fetch the posts related to the specified blog_space_name
    # Assuming 'blogPosts' is an array of ObjectIds linking to actual posts
    posts_data = diaryblog_post_collection.find({"_id": {"$in": blog_space_data['blogPosts']}, "status": "published"})
    
    # Convert the Cursor object to a list and then to JSON format
    # Also convert ObjectId to str for JSON serialization
    posts_list = [{
        "_id": str(post["_id"]),
        "blogSpace": str(post["blogSpace"]),
        "title": post["title"],
        "imageUrl": post["imageUrl"],
        "description": post["description"],
        "author": post["author"],
        "status": post["status"],
        "category": post["category"],
        "createDate": post["createDate"],
        "updateDate": post["updateDate"],
        "views": post["views"]
    } for post in posts_data]

    return jsonify(posts_list), 200

@app.route('/api/latest_5_posts', methods=['GET'])
def get_latest_5_posts():
    print("Executing get_latest_5_posts function")  # Log message to console

    # Fetch from cache if available
    cached_result = cache.get('latest_5_posts')
    if cached_result:
        return jsonify(cached_result), 200

    blogposts = list(diaryblog_post_collection.find({'status': 'published'}).sort('_id', -1).limit(5))

    # Convert the Cursor object to a list of dictionaries
    blog_posts_data_list = list(blogposts)

    # Check if the blog posts exist
    if not blog_posts_data_list:
        return jsonify({"error": "Blog posts not found"}), 404

    # Convert ObjectId to str for JSON serialization
    serialized_data = [
        {
            "_id": str(post["_id"]),
            "blogSpace": str(post["blogSpace"]),
            "title": post["title"],
            "imageUrl": post["imageUrl"],
            "description": post["description"],
            "author": post["author"],
            "status": post["status"],
            "category": post["category"],
            "createDate": post["createDate"],
            "updateDate": post["updateDate"],
            "views": post["views"]
        }
        for post in blog_posts_data_list
    ]
    print("Returning response from get_latest_5_posts")  # Log message to console

    # Cache the result for future requests
    cache.set('latest_5_posts', serialized_data, timeout=60)

    return jsonify(serialized_data), 200




@app.route('/api/next_5_posts', methods=['GET'])
def get_more_blogposts():
     last_post_id = request.args.get('last_post_id')
     if last_post_id:
         last_post_id = ObjectId(last_post_id)
         next_10_posts = list(diaryblog_post_collection.find({'_id': {'$lt': last_post_id},'status': 'published'}).sort('_id', -1).limit(5))
         serialized_data = [
         {
             "_id": str(post["_id"]),
             "blogSpace": str(post["blogSpace"]),
             "title": post["title"],
             "imageUrl": post["imageUrl"],
             "description": post["description"],
             "author": post["author"],
             "status": post["status"],
             "category": post["category"],
             "createDate": post["createDate"],
             "updateDate": post["updateDate"],
             "views": post["views"]
         }
         for post in next_10_posts
     ]
         return jsonify(serialized_data)
     else:
         return jsonify({"error": "Blog posts not found"}), 404


@app.route('/api/posts/<string:blog_post_id>/views', methods=['PUT'])
def increment_post_views(blog_post_id):
    # Your logic to find the specified post and increment its views
    # Using the ObjectId from BSON for MongoDB's unique _id field
    from bson import ObjectId
    
    post = diaryblog_post_collection.find_one({"_id": ObjectId(blog_post_id)})


    blogSpace_id = post.get('blogSpace')

    if not post:
        return jsonify({"error": "Post not found"}), 404

    # Increment the views
    diaryblog_post_collection.update_one(
        {"_id": ObjectId(blog_post_id)},
        {"$inc": {"views": 1}}
    )


    diaryblog_space_collection.update_one(
        {"_id": ObjectId(blogSpace_id)},
        {"$inc": {"views": 1}}
    )

    # Return the new views count
    updated_post = diaryblog_post_collection.find_one({"_id": ObjectId(blog_post_id)})
    return jsonify({"views": updated_post["views"]}), 200


@app.route('/api/<string:blog_space_id>/views', methods=['PUT'])
def increment_blogSpace_views(blog_space_id):

    blogSpace = diaryblog_space_collection.find_one({"_id": ObjectId(blog_space_id)})

    if not blogSpace:
        return jsonify({"error":"blogSpace not found"}),404
    
    diaryblog_space_collection.update_one(
        {"_id": ObjectId(blog_space_id)},
        {"$inc": {"views": 1}})
    
    updated_blogSpace = diaryblog_space_collection.find_one({"_id":ObjectId(blog_space_id)})
    return jsonify({"views":updated_blogSpace["views"]}),200



@app.route('/api/posts/<string:blog_space_name>/<string:post_id>', methods=['DELETE'])
def delete_blog_post(blog_space_name, post_id):
    try:
        # First, check if the blog space is valid. (Optional)
        blog_space_data = diaryblog_space_collection.find_one({"name": blog_space_name})
        if not blog_space_data:
            return jsonify({"error": "Blog space not found"}), 404

        # Check if the given post_id is a valid ObjectId
        if not ObjectId.is_valid(post_id):
            return jsonify({"error": "Invalid post ID"}), 400
        
        # Delete the post from the collection
        delete_result = diaryblog_post_collection.delete_one({"_id": ObjectId(post_id)})

        # If no post was deleted, then the post was not found
        if delete_result.deleted_count == 0:
            return jsonify({"error": "Post not found"}), 404
        
        diaryblog_space_collection.update_one(
            {"name": blog_space_name},
            {
                "$pull": {"blogPosts": ObjectId(post_id)}
            }
        )

        # If the post was deleted successfully, return success message
        return jsonify({"message": "Post deleted successfully"}), 200
    except Exception as e:
        # Log the exception for debugging
        print(str(e))
        return jsonify({"error": "An error occurred while processing the request"}), 500
    

@app.route('/api/blogspace/<blog_space_id>/posts', methods=['GET'])
def get_posts_of_blogspace(blog_space_id):
    # Convert the provided string ID to ObjectId for querying MongoDB
    blog_space_object_id = ObjectId(blog_space_id)
    
    posts_data = list(diaryblog_post_collection.find({"blogSpace": blog_space_object_id, "status": "published"}).sort("_id",-1).limit(5))

    # Convert the Cursor object to a list and then to JSON format
    # Also convert ObjectId to str for JSON serialization
    posts_list = [{
        "_id": str(post["_id"]),
        "blogSpace": str(post["blogSpace"]),
        "title": post["title"],
        "imageUrl":post["imageUrl"],
        "description": post["description"],
        "author": post["author"],
        "status": post["status"],
        "category": post["category"],
        "createDate": post["createDate"],
        "updateDate": post["updateDate"],
        "views": post["views"]
    } for post in posts_data]

    return jsonify(posts_list), 200


@app.route('/api/blogspace/<blog_space_id>/5_more_posts', methods=['GET'])
def get_5_more_posts_of_blogspace(blog_space_id):
    
    blog_space_object_id = ObjectId(blog_space_id)

    last_post_id = request.args.get('last_post_id')  # Changed to 'last_post_id'
    if last_post_id:
        last_post_id = ObjectId(last_post_id)
        next_5_posts = list(diaryblog_post_collection.find({'_id': {'$lt': last_post_id},"blogSpace": blog_space_object_id,'status': 'published'}).sort('_id', -1).limit(5))
        serialized_data = [
        {
            "_id": str(post["_id"]),
            "blogSpace": str(post["blogSpace"]),
            "title": post["title"],
            "imageUrl": post["imageUrl"],
            "description": post["description"],
            "author": post["author"],
            "status": post["status"],
            "category": post["category"],
            "createDate": post["createDate"],
            "updateDate": post["updateDate"],
            "views": post["views"]
        }
        for post in next_5_posts
    ]
        return jsonify(serialized_data)
    else:
        return jsonify({"error": "Blog posts not found"}), 404



@app.route('/api/companies/<blogspace_id>/posts/<postId>', methods=['GET'])
def get_post_by_blogspace_and_postId(blogspace_id, postId):
    # Convert the provided string IDs to ObjectId for querying MongoDB
    blog_space_object_id = ObjectId(blogspace_id)
    post_object_id = ObjectId(postId)

    # Fetch post related to the provided blogSpace ID and postId
    post_data = diaryblog_post_collection.find_one({"blogSpace": blog_space_object_id, "_id": post_object_id})

    # Check if the post exists
    if not post_data:
        return jsonify({"error": "Post not found"}), 404

    # Convert the document to JSON format
    # Also convert ObjectId to str for JSON serialization
    # post_json = {
    #     "_id": str(post_data["_id"]),
    #     "blogSpace": str(post_data["blogSpace"]),
    #     "title": post_data["title"],
    #     "imageUrl": post_data["imageUrl"],
    #     "description": post_data["description"],
    #     "author": post_data["author"],
    #     "likes":post_data["likes"]
    #     # ... other fields of the post can be added similarly
    # }

    return jsonify(post_data), 200


@app.route('/api/blogSpace/<blogSpaceId>/follow', methods=['POST'])
def handle_follow(blogSpaceId):
    # Extract the email from the request body
    data = request.json
    email = data.get('email')

    # Convert the blogSpaceId to an ObjectId for querying MongoDB
    blog_space_object_id = ObjectId(blogSpaceId)

    # Fetch the followers document related to the provided blogSpace ID
    follower_data = followers_collection.find_one({"blogSpace": blog_space_object_id})

    if follower_data and email in follower_data["userEmails"]:
        return jsonify({"message": "Email already subscribed!"}), 400

    # If the document exists, append the email to userEmails (if not already present)
    if follower_data:
        if email not in follower_data["userEmails"]:
            follower_data["userEmails"].append(email)
            # Update the document in the database
            followers_collection.update_one(
                {"blogSpace": blog_space_object_id},
                {"$set": {"userEmails": follower_data["userEmails"], "updateDate": datetime.utcnow()}}
            )
            diaryblog_space_collection.update_one(
                {"_id": ObjectId(blog_space_object_id)},
                {"$inc": {"followers": 1}}
            )
    else:
        # If the document doesn't exist, create a new one
        new_follower_data = {
            "blogSpace": blog_space_object_id,
            "userEmails": [email],
            # "owner": ObjectId("user_id"),
            "createDate": datetime.utcnow(),
            "updateDate": datetime.utcnow()
            # ... you can also set 'owner' here if you have that info ...
        }
        followers_collection.insert_one(new_follower_data)
        diaryblog_space_collection.update_one(
                {"_id": ObjectId(blog_space_object_id)},
                {"$inc": {"followers": 1}}
            )

    return jsonify({"message": "Subscribed successfully!"}), 200


def generate_cache_key():
    # Get the request path (route)
    path = request.path
    # Get the value of the blogSpaceId parameter from the URL
    blogSpaceId = request.view_args.get('blogSpaceId')
    # Construct the cache key using the route and parameter value
    cache_key = f"{path}/{blogSpaceId}"
    return cache_key


@app.route('/api/blogSpace/<blogSpaceId>/followers', methods=['GET'])
@cache.cached(timeout=300, key_prefix=generate_cache_key)  # Cache the response for 300 seconds (5 minutes)
def get_followers(blogSpaceId):
    try:
        # Convert the blogSpaceId to an ObjectId for querying MongoDB
        blog_space_object_id = ObjectId(blogSpaceId)

        # Fetch the followers document related to the provided blogSpace ID
        follower_data = followers_collection.find_one({"blogSpace": blog_space_object_id})

        if follower_data:
            # Log cache hit
            current_app.logger.info("Cache hit: Data retrieved from cache")
            # Convert ObjectId fields to string for JSON serialization
            follower_data['_id'] = str(follower_data['_id'])
            follower_data['blogSpace'] = str(follower_data['blogSpace'])
            return jsonify(follower_data), 200
        else:
            # Log cache miss
            current_app.logger.info("Cache miss: Data retrieved from database")
            return jsonify({"message": "No followers data found for this blog space.", "userEmails": [], "count": 0}), 200
    except Exception as e:
        # Log any exceptions
        current_app.logger.error(f"Error in get_followers: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
FOLLOWER_API_URL = "https://diaryblogapi2.onrender.com/api/blogSpace/{}/followers"

def call_follower_api(blogSpaceId):
    try:
        # Convert the blogSpaceId to an ObjectId for querying MongoDB
        blog_space_object_id = ObjectId(blogSpaceId)

        # Fetch the followers document related to the provided blogSpace ID
        follower_data = followers_collection.find_one({"blogSpace": blog_space_object_id})

        if follower_data:
            # Log cache hit
            current_app.logger.info("Cache hit: Data retrieved from cache")
            # Convert ObjectId fields to string for JSON serialization
            follower_data['_id'] = str(follower_data['_id'])
            follower_data['blogSpace'] = str(follower_data['blogSpace'])
            return jsonify(follower_data)
        else:
            # Log cache miss
            current_app.logger.info("Cache miss: Data retrieved from database")
            return jsonify({"message": "No followers data found for this blog space.", "userEmails": [], "count": 0})
    except Exception as e:
        # Log any exceptions
        current_app.logger.error(f"Error in get_followers: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
    
    



@app.route('/api/blogpost/last30daysviews', methods=['GET'])
def get_views_count():
    # 1. Obtain the JWT token from the request headers
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = token.split(' ')[1]

    # 2. Decode the token to extract the user ID
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        # user_id = decoded_payload['id']
        user = decoded_payload['user']
        user_id = user['id']
        # user = decoded_payload['user']
        # user_id = user['id']
        print(user_id)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({'message': 'Invalid or expired token'}), 401

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "+00:00"
    end_date_str = end_date.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "+00:00"
    print("Start Date:", start_date)
    print("End Date:", end_date)

    # Fetch the posts
    posts = diaryblog_post_collection.find({'author': user_id})
    posts_list = list(posts)
    # print("Number of posts retrieved:", len(posts_list))
    # for post in posts_list:
    #     print(post)

    # Summing up the views for these posts using posts_list
    total_views = sum(post.get('views', 0) for post in posts_list)

    return jsonify({'total_views_last_30_days': total_views})
        

@app.route('/api/latest_posts', methods=['GET'])
def get_latest_posts():
    # 1. Obtain the JWT token from the request headers
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = token.split(' ')[1]

    # 2. Decode the token to extract the user ID
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        user = decoded_payload['user']
        user_id = user['id']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({'message': 'Invalid or expired token'}), 401

    # 3. Fetch the latest four posts for the given user ID
    post_data = diaryblog_post_collection.find({"author": user_id, "status": "published"}).sort("createDate", -1).limit(4)

    # Convert the Cursor object to a list of dictionaries
    posts_list = list(post_data)

    # Check if any posts are fetched
    if not posts_list:
        return jsonify({"message": "No posts found for the given user ID"}), 404

    # Create a response containing the latest four posts
    response = []
    for post in posts_list:
        post_response = {
            "_id": str(post["_id"]),
            "blogSpace": str(post["blogSpace"]),
            "title": post["title"],
            "imageUrl": post["imageUrl"],
            "description": post["description"],
            "author": post["author"],
            "status": post["status"],
            "category": post["category"],
            "createDate": post["createDate"],
            "updateDate": post["updateDate"],
            "views": post["views"]
        }
        response.append(post_response)

    return jsonify(response), 200




@app.route('/api/drafts', methods=['GET'])
def get_draft_posts():
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = token.strip().split(' ')[1]

    # 2. Decode the token to extract the user ID
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        # user_id = decoded_payload['id']
        user = decoded_payload['user']
        user_id = user['id']
        print(user_id)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({'message': 'Invalid or expired token'}), 401
    # Fetch the posts related to the specified user_id with a "draft" status
    posts_data = diaryblog_post_collection.find({"author": user_id, "status": "draft"})
    
    # If you want to handle the situation where no draft posts are found, you can check if posts_data is empty here.
    
    # Convert the Cursor object to a list and then to JSON format
    # Also convert ObjectId to str for JSON serialization
    posts_list = [{
        "_id": str(post["_id"]),
        "blogSpace": str(post["blogSpace"]),
        "title": post["title"],
        "imageUrl": post["imageUrl"],
        "description": post["description"],
        "author": str(post["author"]),
        "status": post["status"],
        "category": post["category"],
        "createDate": post["createDate"],
        "updateDate": post["updateDate"],
        "views": post["views"]
    } for post in posts_data]

    return jsonify(posts_list), 200

@app.route('/api/drafts/<string:draft_id>', methods=['DELETE'])
def delete_draft(draft_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = auth_header.split(' ')[1]
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        # user_id = decoded_payload['id']
        user = decoded_payload['user']
        user_id = user['id']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({'message': 'Invalid or expired token'}), 401

    # Check if the post exists and belongs to the authenticated user
    post_data = diaryblog_post_collection.find_one({"_id": ObjectId(draft_id), "author": user_id})

    if not post_data:
        return jsonify({"error": "Draft not found or unauthorized action"}), 404

    # Delete the post
    diaryblog_post_collection.delete_one({"_id": ObjectId(draft_id)})

    return jsonify({"message": "Draft successfully deleted"}), 200


@app.route('/api/follow_spaces', methods=['POST'])
def get_follow_spaces_by_companies():
    company_ids_and_names = request.json['companyIdsandNames']
    
    # Extract only the company IDs for the database query.
    company_ids = [company['id'] for company in company_ids_and_names]

    follow_spaces_results = list(followers_collection.find({"blogSpace": {"$in": [ObjectId(id) for id in company_ids]}}))

    # Create a dictionary for faster lookup of company names based on ID.
    company_name_lookup = {company['id']: company['name'] for company in company_ids_and_names}

    # Pair each follow space result with its corresponding company name.
    response_data = []
    for space in follow_spaces_results:
        paired_data = {
            '_id': str(space['_id']),
            'blogSpace': str(space['blogSpace']),
            'companyName': company_name_lookup.get(str(space['blogSpace']), 'Unknown'),
            'userEmails': space['userEmails'],
            'createDate': space['createDate'],
            'updateDate': space['updateDate']
        }
        response_data.append(paired_data)

    if response_data:
        return jsonify(response_data)
    else:
        return jsonify({"error": "blog spaces not found for the given company IDs"}), 404
    



@app.route('/api/md_templates', methods=['GET'])
def get_md_templates():
    # Access the md_templates collection
    templates_collection = mongo.db.blogpost_template
    # Fetch all templates
    templates = list(templates_collection.find({}))

    # Convert the templates to a more friendly format for the frontend
    templates_list = [{
        "id": str(template["_id"]),
        "name": template["name"],
        "content": template["content"]
    } for template in templates]

    return jsonify(templates_list)


@app.route('/api/fetch-content', methods=['GET'])
def fetch_content():
    target_url = request.args.get('url')
    try:
        response = requests.get(target_url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        return jsonify(error=str(e)), 500
    
# @app.route('/api/sentimentforpost', methods=['POST'])
# def sentiment_for_post():
   # try:
    #    data = request.json
    #    blogId = data.get('blogId')
    #    postId = data.get('postId')
    #    icon = data.get('icon')
    #    user_who_selected_this_icon = data.get('user_who_selected_this_icon')

        # Convert postId to ObjectId
   #     postId = ObjectId(postId)

   #     blogpost = diaryblog_post_collection.find_one({"_id": postId})
   #     blogSpace_id = blogpost.get('blogSpace')

  #      if blogpost:
            # Check if the user has already liked the post
   #         if user_who_selected_this_icon not in blogpost.get('likes', []):
                # Add the user to the list of likes
   #             diaryblog_post_collection.update_one(
   #                 {'_id': postId},
   #                 {
  #                      '$push': {'likes': user_who_selected_this_icon}
 #                   }
#                )

  #              diaryblog_space_collection.update_one(
  #                  {'_id': ObjectId(blogSpace_id)},
  #                  {
  #                      '$inc': {'total_likes': 1}
 #                   }
  #              )

  #              return jsonify({"message": "Sentiment recorded successfully."}), 200
  #          else:
 #               return jsonify({"message": "User has already selected this sentiment."}), 400

 #       return jsonify({"message": "Post not found."}), 404

#    except Exception as e:
#        return jsonify({"error": str(e)}), 500
    

@app.route('/api/sentimentforpost', methods=['POST'])
def sentiment_for_post():
    try:
        data = request.json
        blogId = data.get('blogId')
        postId = data.get('postId')
        icon = data.get('icon')

        # Convert postId to ObjectId
        postId = ObjectId(postId)

        blogpost = diaryblog_post_collection.find_one({"_id": postId})
        blogSpace_id = blogpost.get('blogSpace')

        if blogpost:
            # Increment the like count directly
            diaryblog_post_collection.update_one(
                {'_id': postId},
                {
                    '$inc': {'likes_count': 1}
                }
            )

            diaryblog_space_collection.update_one(
                {'_id': ObjectId(blogSpace_id)},
                {
                    '$inc': {'total_likes': 1}
                }
            )

            return jsonify({"message": "Sentiment recorded successfully."}), 200
        else:
            return jsonify({"message": "Post not found."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/drafts/<blogSpaceId>', methods=['GET'])
def get_draft_posts_by_blog_space(blogSpaceId):
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = token.strip().split(' ')[1]

    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        user = decoded_payload['user']
        user_id = user['id']
        print(user_id)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({'message': 'Invalid or expired token'}), 401

    posts_data = diaryblog_post_collection.find({"blogSpace": ObjectId(blogSpaceId), "status": "draft"})

    posts_list = [{
        "_id": str(post["_id"]),
        "blogSpace": str(post["blogSpace"]),
        "title": post["title"],
        "imageUrl": post["imageUrl"],
        "description": post["description"],
        "author": str(post["author"]),
        "status": post["status"],
        "category": post["category"],
        "createDate": post["createDate"],
        "updateDate": post["updateDate"],
        "views": post["views"]
    } for post in posts_data]

    return jsonify(posts_list), 200

@app.route('/api/preview/<blogSpaceId>', methods=['GET'])
def get_preview_posts_by_blog_space(blogSpaceId):

    try:
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({"error": "Invalid token"}), 401

        token = token.strip().split(' ')[1]

        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        user = decoded_payload['user']
        user_id = user['id']
        
        
        posts_data = diaryblog_post_collection.find({
            "blogSpace": ObjectId(blogSpaceId),
            "status": "preview"
        })

        blog_posts_preview = [{
            '_id': str(post['_id']),
            'blogSpace': str(post['blogSpace']),
            'title': post['title'],
            'imageUrl': post.get('imageUrl', ''),
            'description': post.get('description', ''),
            'author': str(post['author']),
            'status': post.get('status', ''),
            'category': post['category'],
            'createDate': post['createDate'],
            'updateDate': post['updateDate'],
            'views': post['views'],
            'pkey':post.get('pkey')
        } for post in posts_data]

        return jsonify(blog_posts_preview), 200

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({'message': 'Invalid or expired token'}), 401
    

@app.route('/api/email_preview', methods=['POST'])
def email_preview():
    data = request.json
    blogId = data.get("blogId")
    # Generate a unique cache key
    cache_key = str(uuid.uuid4())
    

    # Call follower api and store the followers in cache with the generated cache key
    #followers = call_follower_api(blogId)
    blog_space_object_id = ObjectId(blogId)

    # Fetch the followers document related to the provided blogSpace ID
    follower_data = followers_collection.find_one({"blogSpace": blog_space_object_id})

    if follower_data:
        # Log cache hit
        current_app.logger.info("Cache hit: Data retrieved from cache")
        # Convert ObjectId fields to string for JSON serialization
        follower_data['_id'] = str(follower_data['_id'])
        follower_data['blogSpace'] = str(follower_data['blogSpace'])
        print("follower_data:",follower_data)
        cache.set(cache_key, follower_data)

    else:
        return jsonify({"error": "Cached followers data not found."}), 500
    

    return jsonify({'cache_key': cache_key})



@app.route('/api/send_email_new_post', methods=['POST'])
def send_email_for_new_post():
    try:
        data = request.json
        print("Received JSON data:", data)
        post_title = data.get("post_title")
        post_description_markdown = data.get("post_description", {}).get("props", {}).get("children", "")
        post_imageUrl = data.get("post_imageUrl")
        blogId = data.get("blogId")
        postId = data.get("postId")
        # imageBase64 = data.get("imageBase64")
        username = data.get("username")
        # blogSpaceImageUrl = data.get("blogSpaceImageUrl")
        blogSpaceName = data.get("blogSpaceName")
        userId = data.get("userId")
        email_subject = post_title
        cache_key = data.get('cacheKey', {}).get('cache_key')


        post_description_html = markdown.markdown(post_description_markdown)
        post_description_text = BeautifulSoup(post_description_html, "html.parser").get_text()

        # Check if all required fields are present
        if not all([post_title, post_description_markdown, post_imageUrl, blogId, postId]):
            raise ValueError("Missing required fields in the request")
        
        # Check if cache key exists
        if cache_key:
        # Retrieve followers from cache using the provided cache key
            print("fetching followers using cachekey")
            followers = cache.get(cache_key)
            print("followers:",followers)

            
            
        else:
        # Call follower api if no cache key is provided
            # followers = call_follower_api(blogId)
            
            print("cache data missed")
            
            blog_space_object_id = ObjectId(blogId)

            # Fetch the followers document related to the provided blogSpace ID
            follower_data = followers_collection.find_one({"blogSpace": blog_space_object_id})
        
            if follower_data:
                # Log cache hit
                current_app.logger.info("Cache hit: Data retrieved from cache")
                # Convert ObjectId fields to string for JSON serialization
                follower_data['_id'] = str(follower_data['_id'])
                follower_data['blogSpace'] = str(follower_data['blogSpace'])
                followers = jsonify(follower_data)
            else:
                return jsonify({"error": "Cached followers data not found."}), 500
        
        recipients = followers.get("userEmails",[])
        print("recepients:",recipients)
        

        if recipients:
            # Send email notification to followers
            send_email_notification_newpost(recipients, post_title, post_description_text, post_imageUrl, blogId, postId, username, blogSpaceName, userId, email_subject)

            return jsonify({"message": "Email notification sent successfully"}), 200
        else:
            return jsonify({"error": "Cached followers data not found. Please try again later."}), 500

    except Exception as e:
        # Log the error message
        print("Error in send_email_for_new_post:", str(e))
        return jsonify({"error": str(e)}), 500



def fetch_engagement_metrics(user_id):
    try:
        # Fetch data from the database
            #diary_blog_spaces = list(diaryblog_space_collection.find({"owner": user_id}))

        #user_obj_id = ObjectId(user_id)
        blogspaces = list(diaryblog_space_collection.find({"owner": user_id}))
        posts_data = list(diaryblog_post_collection.find({"author": user_id, "status": "published"}))

        total_blog_spaces = len(blogspaces)
        total_blog_posts = len(posts_data)
        total_views = sum(post['views'] for post in posts_data)  
        total_followers = sum(space.get('followers', 0) for space in blogspaces)
        total_comments = sum(post.get('comments', 0) for post in posts_data) 
        total_shares = sum(post.get('shares', 0) for post in posts_data)  
        total_likes = sum(space.get('total_likes', 0) for space in blogspaces)  

        engagement_metrics = {
            "total_blog_spaces": total_blog_spaces,
            "total_blog_posts": total_blog_posts,
            "total_views": total_views,
            "total_followers": total_followers,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "total_likes": total_likes,
        }

        return engagement_metrics

    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Invalid or expired token'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401
    except Exception as e:
        print(f"Error in calculating engagement: {e}")
        return jsonify({"error": "Failed to calculate engagement metrics"}), 500


@app.route('/api/engagement', methods=['GET'])

def get_engagement():
    try:
        # Obtain the JWT token from the request headers
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({"error": "Invalid token"}), 401

        token = token.split(' ')[1]
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        user_id = decoded_payload['user']['id']

        engagement = fetch_engagement_metrics(user_id)  # Pass user_id argument here
        return jsonify(engagement)

    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Invalid or expired token'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401
    except Exception as e:
        print(f"Error in getting engagement metrics: {e}")
        return jsonify({"error": "Failed to get engagement metrics"}), 500

@app.route('/api/posts/analytics', methods=['GET'])
def get_post_analytics():
    # Obtain the JWT token from the request headers
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = token.split(' ')[1]

    # Decode the token to extract the user ID
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        user = decoded_payload['user']
        user_id = user['id']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({'message': 'Invalid or expired token'}), 401

    # Fetch most and least posts by the user
    most_posts = diaryblog_post_collection.find({"author": user_id, "status": "published"}).sort([("views", -1)]).limit(3)
    least_posts = diaryblog_post_collection.find({"author": user_id, "status": "published"}).sort([("views", 1)]).limit(3)


    most_loved_posts_cursor = diaryblog_post_collection.find({"author": user_id, "status": "published"}).sort([("likes_count", -1)]).limit(3)
    least_loved_posts_cursor = diaryblog_post_collection.find({"author": user_id, "status": "published"}).sort([("likes_count", 1)]).limit(3)

    
    most_viewed_posts = []
    least_viewed_posts = []
    most_loved_posts = []
    least_loved_posts = []


    # Extract necessary data from most and least posts
    for post in most_posts:
        most_viewed_posts.append({
             "_id": str(post.get("_id")),
            "blogSpace": str(post.get("blogSpace")),
            "title": post.get("title"),
            "imageUrl": post.get("imageUrl"),
            "category": post.get("category"),
            "createDate": post.get("createDate"),
            "views": post.get("views"),
            "comments": post.get("comments"),
            "like": post.get("likes_count")
        })

    for post in least_posts:
        least_viewed_posts.append({
             "_id": str(post.get("_id")),
            "blogSpace": str(post.get("blogSpace")),
            "title": post.get("title"),
            "imageUrl": post.get("imageUrl"),
             "createDate": post.get("createDate"),
             "category": post.get("category"),
            "views": post.get("views"),
            "comments": post.get("comments"),
            "like": post.get("likes_count")
        })

   
    most_commented_posts = []
    most_shared_posts = []
    #most_loved_posts = []
    least_commented_posts = []
    least_shared_posts = []
    #least_loved_posts = []

    for post in most_posts:
        most_commented_posts.append({
             "_id": str(post.get("_id")),
            "blogSpace": str(post.get("blogSpace")),
            "title": post.get("title"),
             "imageUrl": post.get("imageUrl"),
             "createDate": post.get("createDate"),
             "category": post.get("category"),
            "views": post.get("views"),
            "comments": post.get("comments"),
            "like": post.get("likes_count")
        })

    for post in most_posts:
        most_shared_posts.append({
             "_id": str(post.get("_id")),
            "blogSpace": str(post.get("blogSpace")),
            "title": post.get("title"),
             "imageUrl": post.get("imageUrl"),
             "createDate": post.get("createDate"),
             "category": post.get("category"),
            "views": post.get("views"),
            "comments": post.get("comments"),
            "like": post.get("likes_count")
        })

      #for post in most_posts:
    for post in most_loved_posts_cursor:

        most_loved_posts.append({
            "title": post.get("title"),
            "imageUrl": post.get("imageUrl"),
             "createDate": post.get("createDate"),
             "category": post.get("category"),
            "views": post.get("views"),
            "comments": post.get("comments"),
            "like": post.get("likes_count")
        })

    for post in least_commented_posts:
        least_commented_posts.append({
             "_id": str(post.get("_id")),
            "blogSpace": str(post.get("blogSpace")),
            "title": post.get("title"),
             "imageUrl": post.get("imageUrl"),
             "createDate": post.get("createDate"),
             "category": post.get("category"),
            "views": post.get("views"),
            "comments": post.get("comments"),
            "like": post.get("likes_count")
        })

    for post in least_posts:
        least_shared_posts.append({
             "_id": str(post.get("_id")),
            "blogSpace": str(post.get("blogSpace")),
            "title": post.get("title"),
             "imageUrl": post.get("imageUrl"),
             "createDate": post.get("createDate"),
             "category": post.get("category"),
            "views": post.get("views"),
            "comments": post.get("comments"),
            "like": post.get("likes_count")
        })

      #for post in least_posts:
    for post in least_loved_posts_cursor:

        least_loved_posts.append({
             "_id": str(post.get("_id")),
            "blogSpace": str(post.get("blogSpace")),
            "title": post.get("title"),
             "imageUrl": post.get("imageUrl"),
             "createDate": post.get("createDate"),
             "category": post.get("category"),
            "views": post.get("views"),
            "comments": post.get("comments"),
            "like": post.get("likes_count")
        })

    return jsonify({
        "most_viewed_posts": most_viewed_posts,
        "least_viewed_posts": least_viewed_posts,
        "most_commented_posts": most_commented_posts,
        "most_shared_posts": most_shared_posts,
        "most_loved_posts": most_loved_posts,
        "least_commented_posts": least_commented_posts,
        "least_shared_posts": least_shared_posts,
        "least_loved_posts": least_loved_posts
    })



# @app.route('/api/followers/<blogSpaceId>/followers', methods=['GET'])
# def get_followers_api(blogSpaceId):
    # Convert the blogSpaceId to an ObjectId for querying MongoDB
  #  blog_space_object_id = ObjectId(blogSpaceId)

    # Fetch the followers document related to the provided blogSpace ID
   # follower_data = followers_collection.find_one({"blogSpace": blog_space_object_id})

   # if not follower_data:
    #    return jsonify({"message": "No followers found for this blog space"}), 404

    # Prepare the followers information to be returned
   # followers_info = []
   # for idx, email in enumerate(follower_data["userEmails"], start=1):
       # follower_info = {
          #  "id": idx,
          #  "email": email,
          #  "subscription": "",  # Assuming all subscriptions are free in this example
         #   "type": "",  # You can populate this based on your data model
        #    "amount": "",  # You can populate this if you have payment information
       #     "subscribedDate": "",  # You can populate this based on your data model
      #      "paidDate": ""  # You can populate this if you have payment information
     #   }
    #    followers_info.append(follower_info)

   # return jsonify(followers_info), 200


#@app.route('/api/followers', methods=['POST'])
#def add_followers():
    #try:
        #data = request.json  # Assuming the frontend sends JSON data with follower information
       # if not data:
           # return jsonify({"error": "No data provided"}), 400

        # Convert the blogSpaceId to an ObjectId for querying MongoDB
        #blog_space_object_id = ObjectId(data['blogSpaceId'])
        
        # Fetch the followers document related to the provided blogSpace ID
        # follower_data = followers_collection.find_one({"blogSpace": blog_space_object_id})

        #if not follower_data:
         #   return jsonify({"message": "No followers found for this blog space"}), 404

        # Extract only the email addresses from the followers' data
        #new_followers_emails = [follower['email'] for follower in data['followers']]
        
        # Update the followers collection with new followers' email addresses
        #followers_collection.update_one(
        #    {"blogSpace": blog_space_object_id},
       #     {"$push": {"userEmails": {"$each": new_followers_emails}}},
      #  )

     #   return jsonify({"message": "Followers added successfully"}), 200
    #except Exception as e:
       # return jsonify({"error": str(e)}), 500

@app.route('/api/followers/<blogSpaceId>/followers', methods=['GET'])
def get_followers_api(blogSpaceId):
    try:
        # Convert the blogSpaceId to an ObjectId for querying MongoDB
        blog_space_object_id = ObjectId(blogSpaceId)

        # Fetch the followers document related to the provided blogSpace ID
        follower_data = followers_collection.find_one({"blogSpace": blog_space_object_id})

        if not follower_data or "userEmails" not in follower_data:
            return jsonify({"message": "No followers found for this blog space"}), 404

        # Prepare the followers information to be returned
        followers_info = []
        for idx, email in enumerate(follower_data["userEmails"], start=1):
            follower_info = {
                "id": idx,
                "email": email,
                "subscription": "",  # Assuming all subscriptions are free in this example
                "type": "",  # You can populate this based on your data model
                "amount": "",  # You can populate this if you have payment information
                "subscribedDate": "",  # You can populate this based on your data model
                "paidDate": ""  # You can populate this if you have payment information
            }
            followers_info.append(follower_info)

        return jsonify(followers_info), 200

    except Exception as e:
        logging.error(f"Error in get_followers_api: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/followers', methods=['POST'])
def add_followers():
    try:
        data = request.json  # Assuming the frontend sends JSON data with follower information
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Convert the blogSpaceId to an ObjectId for querying MongoDB
        blog_space_object_id = ObjectId(data['blogSpaceId'])

        # Fetch the followers document related to the provided blogSpace ID
        follower_data = followers_collection.find_one({"blogSpace": blog_space_object_id})

        if not follower_data:
            return jsonify({"message": "No followers found for this blog space"}), 404

        # Extract only the email addresses from the followers' data
        new_followers_emails = [follower['email'] for follower in data['followers']]

        # Update the followers collection with new followers' email addresses
        result = followers_collection.update_one(
            {"blogSpace": blog_space_object_id},
            {"$push": {"userEmails": {"$each": new_followers_emails}}}
        )

        # Check if any documents were modified
        if result.modified_count > 0:
            # Increment the followers count
            diaryblog_space_collection.update_one(
                {"_id": blog_space_object_id},
                {"$inc": {"followers": len(new_followers_emails)}}
            )

        return jsonify({"message": "Followers added successfully"}), 200
    except Exception as e:
        logging.error(f"Error in add_followers: {str(e)}")
        return jsonify({"error": str(e)}), 500



@app.route('/api/digital_marketing_space/<space_id>', methods=['DELETE'])
def delete_digital_marketing_space(space_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = auth_header.split(' ')[1]

    # Check if the token has expired
    if is_token_expired(token, secret_key):
        return jsonify({"error": "Token has expired"}), 401

    # Decode the token directly here
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "Invalid or expired token"}), 401

    user = decoded_payload['user']
    user_id = user['id']

    result = digital_marketing_collection.delete_one(
        {"_id": ObjectId(space_id), "user_id": ObjectId(user_id)}
    )

    if result.deleted_count == 0:
        return jsonify({"error": "Digital marketing space not found or you don't have permission to delete"}), 404
    else:
        return jsonify({"message": "Digital marketing space deleted successfully"}), 200







        
@app.route('/api/digital_marketing_space',methods=['POST'])
def create_and_edit_digital_marketing_space():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = auth_header.split(' ')[1]

    # Check if the token has expired
    if is_token_expired(token, secret_key):
        return jsonify({"error": "Token has expired"}), 401

    # Decode the token directly here
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "Invalid or expired token"}), 401

    # user_id = decoded_payload['id']
    user = decoded_payload['user']
    user_id = user['id']

    data = request.json
    

    existing_space = digital_marketing_collection.find_one({"title": data['title']})
    if existing_space:
        return jsonify({"error": "marketing space with this name already exists"}), 400
    
    new_space = {
        "title" : data.get("title"),
        "campaign_about" : data.get("campaign_about"),
        "imageUrl" : data.get("imageUrl"),
        "category" : data.get("category"),
        "marketingPosts": [],  # Empty list as it's a new space
        "user_id": ObjectId(user_id),  # Here we use the decoded user ID
        "createDate": datetime.utcnow(),
        "updateDate": datetime.utcnow(),
        "views":0,
        "total_likes":0,
        "followers":0,
        "total_comments_count":0
        }

    space_id = digital_marketing_collection.insert_one(new_space).inserted_id

    return jsonify({"message": "Marketing space created successfully", "id": str(space_id), "blog details": jsonify_objectid(new_space)}), 201


    

@app.route('/api/digital_marketing_space/<space_id>', methods=['PUT'])
def update_digital_marketing_space(space_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = auth_header.split(' ')[1]

    # Check if the token has expired
    if is_token_expired(token, secret_key):
        return jsonify({"error": "Token has expired"}), 401

    # Decode the token directly here
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "Invalid or expired token"}), 401

    # user_id = decoded_payload['id']
    user = decoded_payload['user']
    user_id = user['id']

    data = request.json

    updated_space = {
        "$set": {
            "title": data.get("title"),
            "campaign_about": data.get("campaign_about"),
            "imageUrl": data.get("imageUrl"),
            "category": data.get("category"),
            "updateDate": datetime.utcnow()
        }
    }

    result = digital_marketing_collection.update_one(
        {"_id": ObjectId(space_id), "user_id": ObjectId(user_id)},
        updated_space
    )

    if result.matched_count == 0:
        return jsonify({"error": "Digital marketing space not found or you don't have permission to update"}), 404
    elif result.modified_count == 0:
        return jsonify({"message": "No changes were made to the digital marketing space"}), 200
    else:
        return jsonify({"message": "Digital marketing space updated successfully"}), 200



@app.route('/api/digital_marketing_space/<userId>', methods=['GET'])
def get_digital_marketing_space_by_user(userId):
        marketing_spaces = list(digital_marketing_collection.find({ "user_id": ObjectId(userId)}))
        if marketing_spaces:
            return jsonify([{
                '_id': str(marketing_space['_id']),
                'title': marketing_space['title'],
                'category': marketing_space['category'],
                'campaign_about': marketing_space['campaign_about'],
                'image_url': marketing_space.get('imageUrl', ''), 
                'marketingPosts': marketing_space['marketingPosts'],  
                'user_id': str(marketing_space['user_id']),
                'createDate': marketing_space['createDate'],
                'updateDate': marketing_space['updateDate'],
                'views': marketing_space['views'],
                'total_likes': marketing_space.get('total_likes', ''), 
                'followers': marketing_space.get('followers', ''),
                'total_comments_count': marketing_space.get('total_comments_count', '')
            }for marketing_space in marketing_spaces])
        else:
            return jsonify({"error": "Marketing space not found for the given user"}), 404
        
def send_email_notification_digital_marketing(recipients, exportedHtmlData, email_subject):
    try:
        url = 'https://api.brevo.com/v3/smtp/email'
        brevo_api_key = os.environ.get('BREVO_API_KEY')
        if brevo_api_key is None:
            raise ValueError("BREVO_API_KEY environment variable is not set.")
        
        headers = {
            'accept': 'application/json',
            'api-key': brevo_api_key,
            'content-type': 'application/json'
        }
        
        payload = {
            "sender": {
                "email": "universe@admin.com",
                "name": "Universe"
            },
            "subject": email_subject,
            "htmlContent": exportedHtmlData,
            "params": {
                "exportedHtmlData": exportedHtmlData
            },
            "messageVersions": [
                {
                    "bcc": [{"email": recipient} for recipient in recipients],
                    "htmlContent": exportedHtmlData,
                    "subject": email_subject
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print("Response of send_email_notification_newpost:", response.json())
        return response.json()
    
    except requests.HTTPError as e:
        print("HTTP Error while sending email notification:", e)
        print("Response text:", e.response.text)
        return None

    except requests.RequestException as e:
        print("Error sending email notification:", e)
        return None

    except Exception as e:
        print("An unexpected error occurred:", e)
        return None


@app.route('/api/send_email_for_digital_marketing', methods=['POST'])
def send_email_for_digital_marketing():
    try:
        data = request.json
        print("Received JSON data:", data)
        
        # userId = data.get("userId")
        # cache_key = data.get('cacheKey', {}).get('cache_key')
        exportedHtmlData = data.get("exportedHtmlData")
        print(type(exportedHtmlData))
        recipients = data.get("recipients")
        email_subject = data.get("email_subject")
        print("email subject:",email_subject)
        

        # Check if all required fields are present
        if not (exportedHtmlData):
            raise ValueError("Missing required field in the request")
        

        if recipients:
            # Send email notification to followers
            send_email_notification_digital_marketing(recipients, exportedHtmlData, email_subject)

            return jsonify({"message": "Email notification sent successfully"}), 200
        else:
            return jsonify({"error": "Cached followers data not found. Please try again later."}), 500

    except Exception as e:
        # Log the error message
        print("Error in send_email_for_new_post:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/api/create_digital_marketing_template", methods=['POST'])
def create_digital_marketing_template():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = auth_header.split(' ')[1]

    # Check if the token has expired
    if is_token_expired(token, secret_key):
        return jsonify({"error": "Token has expired"}), 401

    # Decode the token directly here
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "Invalid or expired token"}), 401

    user = decoded_payload['user']
    user_id = user['id']

    data = request.json
    exportedHtmlData = data.get('exportedHtmlData')
    marketSpaceId = data.get('marketSpaceId')
    design = data.get("design")

    existing_space = digital_marketing_templates_collection.find_one({"campaignSpace_id": ObjectId(marketSpaceId)})

    if existing_space:
        # If the space exists, update it
        updated_space = {
            "$set": {
                "exportedHtmlData": exportedHtmlData,
                "design":design,
                "updateDate": datetime.utcnow(),
            }
        }
        result = digital_marketing_templates_collection.update_one(
            {"_id": ObjectId(existing_space["_id"]), "user_id": ObjectId(user_id)},
            updated_space
        )
        if result.modified_count > 0:
            return jsonify({"message": "Digital marketing template updated successfully"}), 200
        else:
            return jsonify({"error": "Failed to update digital marketing template"}), 500
    else:
        # If the space does not exist, create it
        new_space = {
            "user_id": ObjectId(user_id),
            "campaignSpace_id": ObjectId(marketSpaceId),
            "exportedHtmlData": exportedHtmlData,
            "design": design,
            "createDate": datetime.utcnow(),
            "updateDate": datetime.utcnow(),
        }
        result = digital_marketing_templates_collection.insert_one(new_space)
        if result.inserted_id:
            return jsonify({"message": "Digital marketing template created successfully"}), 201
        else:
            return jsonify({"error": "Failed to create digital marketing template"}), 500


@app.route("/api/get_digital_marketing_template", methods=['GET'])
def get_digital_marketing_template():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Invalid token"}), 401

    token = auth_header.split(' ')[1]

    # Check if the token has expired
    if is_token_expired(token, secret_key):
        return jsonify({"error": "Token has expired"}), 401

    # Decode the token directly here
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "Invalid or expired token"}), 401

    user = decoded_payload['user']
    user_id = user['id']

    campaignSpace_id = request.args.get('campaignSpace_id')

    if not campaignSpace_id:
        return jsonify({"error": "Missing campaignSpace_id parameter"}), 400

    digital_marketing_template = digital_marketing_templates_collection.find_one({
        "user_id": ObjectId(user_id),
        "campaignSpace_id": ObjectId(campaignSpace_id)
    })

    if digital_marketing_template:
        
        return jsonify({
                '_id': str(digital_marketing_template['_id']),
                'exportedHtmlData': digital_marketing_template['exportedHtmlData'],
                'design':digital_marketing_template['design'],
                'createDate': digital_marketing_template['createDate'],
                'updateDate': digital_marketing_template['updateDate']
            }), 200
    else:
        return jsonify({"error": "Digital marketing template not found"}), 404


# @app.route('/api/followSpaces_by_userId', methods=['GET'])
# def get_followSpaces_by_userId():
#     data = request.json
#     userId = data.get("userId")
#     # Specify projection to include only _id field
#     blogSpaces_cursor = diaryblog_space_collection.find({"owner": userId}, {"_id": 1})
    
#     # Extract the IDs from the cursor
#     blog_space_ids = [ObjectId(blog_space["_id"]) for blog_space in blogSpaces_cursor]
#     print(blog_space_ids)
    
#     # Use the IDs to fetch corresponding follow spaces from the followers collection
#     followSpaces_cursor = followers_collection.find({"blogSpace": {"$in": blog_space_ids}})
    
#     # Use json_util to serialize the cursor directly
#     followSpaces_json = json_util.dumps(followSpaces_cursor)
    
#     # Return the JSON response
#     return followSpaces_json
    
# APP_ID = '1153449319297719'
# APP_SECRET = '3675368b2e54b43755afd46ca17ac158'

@app.route('/api/exchange_token', methods=['POST'])
def exchange_token():
    data = request.json
    short_lived_token = data.get('accessToken')
    client_id = data.get('clientId')
    client_secret = data.get('clientSecret')
    
    url1 = f"https://graph.facebook.com/v6.0/oauth/access_token"
    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': client_id,
        'client_secret': client_secret,
        'fb_exchange_token': short_lived_token
    }
    
    response = requests.get(url1, params=params)
    response_data = response.json()

    # Check if access token is in the response
    if 'access_token' in response_data:
        long_lived_token = response_data['access_token']
        
        url2 = f"https://graph.facebook.com/v6.0/me"
        params2 = {
            'access_token': long_lived_token
        }
        
        response2 = requests.get(url2, params=params2)
        user_data = response2.json()

        if 'id' in user_data:
            user_id = user_data['id']
            url3 = f"https://graph.facebook.com/{user_id}/accounts"
            params3 = {
            'access_token': long_lived_token
            }
    
            response3 = requests.get(url3, params=params3)

            user_data2 = response3.json()

        
        return jsonify(user_data2)
    
    # Handle error if access token is not found in the response
    return jsonify({'error': 'Failed to exchange token', 'details': response_data})

@app.route('/api/user_facebook_details', methods=['POST'])
def update_userProfile_with_facebookDetails():
    data = request.json
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')
    page_id = data.get('page_id')
    page_name = data.get('page_name')
    permanent_token = data.get('permanent_token')
    user_id = data.get('user_id')

    existing_collection = user_collection.find_one({"_id": ObjectId(user_id)})

    if existing_collection:
        # Update the facebook_details field
        facebook_integration_details = {
            "client_id": client_id,
            "client_secret": client_secret,
            "page_id": page_id,
            "page_name": page_name,
            "permanent_token": permanent_token
        }

        # Update the user document
        user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"facebook_integration_details": facebook_integration_details}}
        )

        return jsonify({"message": "User profile updated with Facebook details"}), 200
    else:
        return jsonify({"message": "User not found"}), 404

@app.route('/api/user_facebook_details', methods=['GET'])
def get_user_facebook_details():
    # Get user_id from query parameter
    user_id = request.args.get('user_id')

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        # Query MongoDB for user details
        user_details = user_collection.find_one({'_id': ObjectId(user_id)})

        if not user_details:
            return jsonify({"error": "User not found"}), 404

        # Extract Facebook integration details
        facebook_details = user_details.get('facebook_integration_details', {})

        # # Convert ObjectId to string for JSON serialization
        # facebook_details['_id'] = str(user_details['_id'])

        return jsonify(facebook_details)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/facebook_post', methods=['POST'])
def facebook_post():
    data = request.json
    permanent_token = data.get('permanent_token')
    page_id = data.get('page_id')
    message = data.get('message')

    url = f"https://graph.facebook.com/{page_id}/feed"
    params = {
        'message': message,
        'access_token': permanent_token
    }
    
    response = requests.post(url, params=params)
    return jsonify(response.json())
        


@app.route('/api/user_linkedin_details', methods=['POST'])
def update_userProfile_with_linkedInDetails():
    data = request.json
    linkedIn_access_token = data.get('linkedInAccessToken')
    user_id = data.get('user_id')

    url1 = f"https://api.linkedin.com/v2/userinfo"
    headers = {
    'Authorization': f'Bearer {linkedIn_access_token}'
    }

    response = requests.get(url1, headers=headers)
    response_data = response.json()
    print("linkedIN_data",response_data)

    existing_collection = user_collection.find_one({"_id": ObjectId(user_id)})

    if existing_collection:
        # Update the facebook_details field
        LinkedIn_integration_details = {
            "linkedIn_access_token": linkedIn_access_token,
            "profile_name": response_data.get('name'),
            "URN_sub": response_data.get('sub')
        }

        # Update the user document
        user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"LinkedIn_integration_details": LinkedIn_integration_details}}
        )

        return jsonify({"message": "User profile updated with LinkedIn details"}), 200
    else:
        return jsonify({"message": "User not found"}), 404
    
@app.route('/api/user_linkedin_details', methods=['GET'])
def get_user_linkedIn_details():
    # Get user_id from query parameter
    user_id = request.args.get('user_id')

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        # Query MongoDB for user details
        user_details = user_collection.find_one({'_id': ObjectId(user_id)})

        if not user_details:
            return jsonify({"error": "User not found"}), 404

        # Extract Facebook integration details
        linkedIn_details = user_details.get('LinkedIn_integration_details', {})

        # # Convert ObjectId to string for JSON serialization
        # facebook_details['_id'] = str(user_details['_id'])

        return jsonify(linkedIn_details)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/linkedin_post', methods=['POST'])
def linkedIn_post():
    data = request.json
    linkedIn_access_token = data.get('linkedIn_access_token')
    urn = data.get('URN_sub')
    message = data.get('message')

    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        'Authorization': f'Bearer {linkedIn_access_token}',
        'Content-Type': 'application/json'
    }
    body = {
        "author": f"urn:li:person:{urn}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": message
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    response = requests.post(url, headers=headers, json=body)
    return jsonify(response.json())





    # Variables for customization
TEXT_SPEED = 24  # frames per second
TEXT_COLOR = (255, 255, 255)
# Updated FONT_PATH with an absolute path
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" 
FONT_SIZE = 180
BACKGROUND_SPEED = 0.8  # Background color change speed (lower value means slower)
TIMING_ADJUSTMENT = -0.3  # Adjusts the duration of each word in the video
START_BG_COLOR = "#000000"  # Start color in HEX
END_BG_COLOR = "#6638f0"  # End color in HEX

def get_ffmpeg_path():
    return r"C:\Users\hp\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin\ffmpeg.exe"

# Function to convert HEX color to RGB
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

# interpolate color
def interpolate_color(start_color, end_color, progress):
    start_color = hex_to_rgb(start_color)
    end_color = hex_to_rgb(end_color)

    start_h, start_s, start_v = colorsys.rgb_to_hsv(
        start_color[0] / 255, start_color[1] / 255, start_color[2] / 255
    )
    end_h, end_s, end_v = colorsys.rgb_to_hsv(
        end_color[0] / 255, end_color[1] / 255, end_color[2] / 255
    )

    interpolated_h = start_h + (end_h - start_h) * progress
    interpolated_s = start_s + (end_s - start_s) * progress
    interpolated_v = start_v + (end_v - start_v) * progress

    r, g, b = colorsys.hsv_to_rgb(interpolated_h, interpolated_s, interpolated_v)

    return int(r * 255), int(g * 255), int(b * 255)






def text_to_video(text, outputfile, video_size):
    words = text.split()
    images = []
    durations = []
    start_time = time.time()
    try:
        fnt = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except OSError as e:
        logging.error(f"Error opening font resource: {e}")
        return jsonify({"error": "Font resource not found"}), 500

    # Generate speech for the whole text and save as a temporary file
    tts = gTTS(text=text, lang="en")
    tts.save("temp.mp3")
    #time.sleep(10)
    logging.info("TTS conversion completed")

    # Measure the speech duration using pydub
    full_audio = AudioSegment.from_file("temp.mp3", ffmpeg=get_ffmpeg_path())
    full_audio_duration = len(full_audio) / 1000  # duration in seconds
    avg_word_duration = full_audio_duration / len(words)  # average duration per word
    logging.info(f"Full audio duration: {full_audio_duration}s, average word duration: {avg_word_duration}s")

    durations.append(avg_word_duration + TIMING_ADJUSTMENT)  # Adjust frame duration based on average word duration and timing adjustment

    total_time = time.time() - start_time
    logging.info(f"Video generation completed in {total_time}s")
    for i, word in enumerate(words):
        # Calculate text size and position only once per word
        text_bbox = fnt.getbbox(word)  # Get bounding box of the text
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]  # Calculate width and height from bounding box
        position = ((video_size[0] - text_width) / 2, (video_size[1] - text_height) / 2)

        # Calculate background color based on word index and total number of words
        background_progress = i / len(words)
        background_color = interpolate_color(START_BG_COLOR, END_BG_COLOR, background_progress)

        img = Image.new("RGB", video_size, color=background_color)  # Set background color
        d = ImageDraw.Draw(img)
        d.text(position, word, font=fnt, fill=TEXT_COLOR)

        images.append(np.array(img))
        durations.append(avg_word_duration)  # Set frame duration based on average word duration

    audioclip = AudioFileClip("temp.mp3")
    clip = ImageSequenceClip(images, durations=durations)
    clip = clip.set_audio(audioclip)

    clip.fps = TEXT_SPEED
    clip.write_videofile(outputfile, codec="libx264")

    # Remove the temporary file
    os.remove("temp.mp3")
  

def fetch_post_from_mongodb(blog_space_id, post_id):
    client = pymongo.MongoClient(mongo_connection_string)
    DATABASE_NAME = 'indian_hacker_news'
    COLLECTION_NAME = 'diaryblog_post'

    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    blog_space_object_id = ObjectId(blog_space_id.strip())
    post_object_id = ObjectId(post_id.strip())

    post_data = collection.find_one({"blogSpace": blog_space_object_id, "_id": post_object_id})

    if post_data:
        title = post_data.get("title", "")
        description = post_data.get("description", "")
        return f"{title}\n\n{description}"
    else:
        return None

@app.route('/api/generate-video', methods=['GET'])
def generate_video():
     blog_space_id = request.args.get('blog_space_id').strip()
     post_id = request.args.get('post_id').strip()
     outputfile = request.args.get('outputfile', 'output.mp4')
     format_short = request.args.get('format_short', 'false').lower() == 'true'

     VIDEO_SIZE = (1080, 1920) if format_short else (1920, 1080)  # width, height

     text = fetch_post_from_mongodb(blog_space_id, post_id)

     if text:
         logging.info(f"Generating video for blog_space_id: {blog_space_id}, post_id: {post_id}")
         text_to_video(text, outputfile, VIDEO_SIZE)
         return send_file(outputfile, as_attachment=True)

     else:
         logging.error(f"Post not found for blog_space_id: {blog_space_id}, post_id: {post_id}")
         return jsonify({"error": "Post not found"}), 404




if __name__ == '__main__':
    app.run(debug=True, port=5001)
