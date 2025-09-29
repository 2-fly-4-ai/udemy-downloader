import base64
import logging
import os
import sys
import time

CLIENT_SECRET = "f2lgDUDxjFiOlVHUpwQNFUfCQPyMO0tJQMaud53PF01UKueW8enYjeEYoyVeP0bb2XVEDkJ5GLJaVTfM5QgMVz6yyXyydZdA5QhzgvG9UmCPUYaCrIVf7VpmiilfbLJc"
CLIENT_ID = "TH96Ov3Ebo3OtgoSH5mOYzYolcowM3ycedWQDDce"
BASIC_AUTH = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")).decode("utf-8")

HEADERS = {
    "User-Agent": "okhttp/4.12.0 UdemyAndroid 9.51.2(594) (phone)",
    "Accept-Encoding": "gzip",
    "x-mobile-visit-enabled": "true",
    "x-udemy-client-secret": CLIENT_SECRET,
    "authorization": "Basic {}".format(BASIC_AUTH),
    "x-udemy-client-id": CLIENT_ID,
    "accept-language": "en_US",
    "x-version-name": "9.51.2",
    "x-client-name": "Udemy-Android",
}


class URLS:
    # fmt: off
    CURRICULUM_ITEMS = "https://{portal_name}.udemy.com/api-2.0/courses/{course_id}/subscriber-curriculum-items/"
    COURSE = "https://{portal_name}.udemy.com/api-2.0/courses/{course_id}/"
    COURSE_SEARCH = "https://{portal_name}.udemy.com/api-2.0/users/me/subscribed-courses?fields[course]=id,url,title,published_title&page=1&page_size=500&search={course_name}"
    SUBSCRIPTION_COURSES = "https://{portal_name}.udemy.com/api-2.0/users/me/subscription-course-enrollments?fields%5Buser%5D=title%2Cimage_100x100&fields%5Bcourse%5D=title%2Cheadline%2Curl%2Ccompletion_ratio%2Cnum_published_lectures%2Cimage_480x270%2Cimage_240x135%2Cfavorite_time%2Carchive_time%2Cis_taking_disabled%2Cfeatures%2Cvisible_instructors%2Clast_accessed_time%2Csort_order%2Cis_user_subscribed%2Cis_in_user_subscription%2Cis_wishlisted%2Cpublished_title%2Cavailable_features%2Cnum_published_practice_tests%2Cnum_coding_exercises%2Cnum_published_quizzes%2Cnum_of_published_curriculum_objects%2Cprimary_category%2Clocale%2Ccourse_has_labels%2Cis_gen_ai_policy_opted_in%2Cavailable_features&ordering=-last_accessed%2C-enrolled&page=1&page_size=50&locale=en_US"
    MY_COURSES = "https://{portal_name}.udemy.com/api-2.0/users/me/subscribed-courses?fields[course]=id,url,title,published_title&ordering=-last_accessed,-access_time&page=1&page_size=10000"
    COLLECTION = "https://{portal_name}.udemy.com/api-2.0/users/me/subscribed-courses-collections/?collection_has_courses=True&course_limit=20&fields[course]=last_accessed_time,title,published_title&fields[user_has_subscribed_courses_collection]=@all&page=1&page_size=1000"
    QUIZ = "https://{portal_name}.udemy.com/api-2.0/quizzes/{quiz_id}/assessments/?version=1&page_size=250&fields[assessment]=id,assessment_type,prompt,correct_response,section,question_plain,related_lectures"
    VISIT = "https://{portal_name}.udemy.com/api-2.0/visits/current/?fields%5Bvisit%5D=@default,visitor,country&locale=en_US"
    # URL form encoded, email
    CODE_GENERATION = "https://www.udemy.com/api-2.0/auth/code-generation/login/4.0/"
    # URL form encoded, email, otp, upow (20250728HIDX)
    # returns json, with access_token property
    PASSWORDLESS_LOGIN = "https://www.udemy.com/api-2.0/auth/udemy-passwordless/login/4.0/"


CURRICULUM_ITEMS_PARAMS = {
    "fields[lecture]": "title,object_index,created,asset,supplementary_assets,description,download_url",
    "fields[quiz]": "title,object_index,type",
    "fields[practice]": "title,object_index",
    "fields[chapter]": "title,object_index",
    "fields[asset]": "title,filename,asset_type,status,is_external,media_license_token,course_is_drmed,media_sources,captions,slides,slide_urls,download_urls,external_url,stream_urls,@min,status,delayed_asset_message,processing_errors,body",
    "caching_intent": True,
    "page_size": "200",
}

COURSE_URL_PARAMS = {
    "fields[course]": "title",
    "use_remote_version": True,
    "caching_intent": True,
}

# Resolve application root independently of current working directory.
# When frozen (PyInstaller onefile), the exe lives under {app}\bin\, so APP_ROOT is parent.
# In dev, resolve to the repository root (directory containing this file).
if getattr(sys, "frozen", False):
    APP_ROOT = os.path.dirname(os.path.dirname(sys.executable))
else:
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))

HOME_DIR = APP_ROOT
SAVED_DIR = os.path.join(APP_ROOT, "saved")
KEY_FILE_PATH = os.path.join(APP_ROOT, "keyfile.json")
COOKIE_FILE_PATH = os.path.join(APP_ROOT, "cookies.txt")
# Allow host to override log paths so it can tail a known file
_ENV_LOG_DIR = os.environ.get("UDEMY_LOG_DIR")
_ENV_LOG_FILE = os.environ.get("UDEMY_LOG_FILE")
LOG_DIR_PATH = _ENV_LOG_DIR if _ENV_LOG_DIR else os.path.join(APP_ROOT, "logs")
LOG_FILE_PATH = _ENV_LOG_FILE if _ENV_LOG_FILE else os.path.join(
    LOG_DIR_PATH, f"{time.strftime('%Y-%m-%d-%I-%M-%S')}.log"
)
LOG_FORMAT = "[%(asctime)s] [%(name)s] [%(funcName)s:%(lineno)d] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%I:%M:%S"
LOG_LEVEL = logging.INFO
