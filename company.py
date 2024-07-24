from flask import Flask, jsonify, request, make_response, current_app, send_file

from bson import json_util
from flask_pymongo import PyMongo, DESCENDING
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from bson import ObjectId
from flask_cors import CORS
import logging
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



# Configure logging
logging.basicConfig(level=logging.DEBUG)







# Set MongoDB connection string
mongo_connection_string = os.environ.get('MONGO_CONNECTION_STRING')
app.config['MONGO_URI'] = mongo_connection_string




secret_key = os.environ.get('SECRET_KEY')
current_time = datetime.now()



    # Variables for customization
TEXT_SPEED = 24  # frames per second
TEXT_COLOR = (255, 255, 255)
# Updated FONT_PATH with an absolute path
#FONT_PATH = "arial.ttf" 
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
