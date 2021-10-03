import requests
from xml.etree import ElementTree
import geopandas as gpd
import os
import folium
from folium import plugins
from geopy.geocoders import Nominatim
import time
from flask import Flask, request, abort
from geopy.geocoders import Nominatim
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReplyButton,QuickReply, MessageAction, ImageSendMessage
)

import json
import pandas as pd
import os
import copy
import random
import time
LINE_CHANNEL_SECRET = "[TOKEN1]"   # チャンネルシークレット
LINE_CHANNEL_ACCESS_TOKEN = "[TOKEN2]"



# 地図表示用

PATH_SHP = "./data_hazard/A26-10_03-g_SedimentDisasterHazardArea_Surface.shp"
gdf = gpd.read_file(os.path.join( PATH_SHP))  # Shapefile読込
gdf.crs = "epsg:4612"
# ベースマップの作製
map_center = [39.58329, 141.253457] #久喜市に設定
map_fu = folium.Map(location=map_center, tiles='openstreetmap', zoom_start=13)
print(map_fu.location, type(map_fu.location), map_fu.zoom_start)
for _, r in gdf.iterrows():
    #without simplifying the representation of each borough, the map might not be displayed
    #sim_geo = gpd.GeoSeries(r['geometry'])
    #print(r['A26_001'] , type(r['A26_001'] ))
    if int(r['A26_001']) in [7, 8 ,9, 10]:
        sim_geo = gpd.GeoSeries(r['geometry']).simplify(tolerance=0.001)
        geo_j = sim_geo.to_json()
        geo_j = folium.GeoJson(data=geo_j,
                            style_function=lambda x: {'fillColor': 'red'})
        #folium.Popup(r['A26_001']).add_to(geo_j)
        geo_j.add_to(map_fu)


def get_hazard_map(lat, lon, map_):
    #config = imgkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')
    map_.location = [lat, lon] 
    map_.zoom_start = 13
    #folium.Marker([lat, lon], popup="you").add_to(map_)
    #with tempfile.TemporaryDirectory() as dname:
    dname = "static"
    os.makedirs(dname, exist_ok=True)
    s = abs(hash(str(lat)+str(lon)))
    path_html = os.path.join(dname, f'{s}.html')
    map_.save(path_html)
    return path_html

base_html = get_hazard_map(39.58329, 141.253457 ,map_fu)

base_html


geolocator = Nominatim(user_agent="test-dayo")
place_text = '[岩手県立福岡高等学校]'.replace('[', '').replace(']', '')
print(place_text)
di_location = geolocator.geocode(place_text).raw
print(di_location)

geolocator = Nominatim(user_agent="test-dayo")

app = Flask(__name__, static_folder='static')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)    # config.pyで設定したチャネルアクセストークン
handler = WebhookHandler(LINE_CHANNEL_SECRET)    # config.pyで設定したチャネルシークレット

def get_info_from_msg(t):
    """
    テクストの種類は次の通り.
    初期定型文(その他)、住所登録したい(rrr)、住所内容("address")、　報告したい(ppp)
    場所の報告(*****)、異音報告(aaa, bbb, ccc)、亀裂報告(ddd, eee, fff)
    それぞれを
    "first", "want_register", "address", "want_report", "report_address", "report_sound", "report_crack", "end_report"
    として、いずれかを返す.
    :param body_dict:
    :return:
    """
    
    if t == "register":
        return "want_register"
    elif t == "report":
        return "want_report"
    elif t in WANT_REPORT_label:
        return "report_sound"
    elif t in REPORT_SOUND_label:
        return "report_crack"
    elif t in REPORT_CRACK_label:
        return "end_report"
    elif ("[" in t) and ("]" in t):
        return "input_address"
    else:
        return "first"

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    print(body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    if event.reply_token == "00000000000000000000000000000000":
        return

    kind_info = get_info_from_msg(event.message.text)
    user_id = event.source.user_id
    test_id = random.randint(0, 10000000)
    
    print(event.message.text)
    print(kind_info)
    if kind_info == "first":
        # 住所を知っているかで分岐. 今回は知っているテイで.
        if user_id in df_user.index:
            msg = "May I help you?"
            items = [QuickReplyButton(action=MessageAction(label=eva, text=f'{eva}')) for eva in FIRST_OP_known]
            messages = TextSendMessage(text=msg,
                               quick_reply=QuickReply(items=items))
            line_bot_api.reply_message(event.reply_token, messages=messages)
        else:
            msg = "Please register your address. You must use below format.\n\n" + "[ your address ]"
            line_bot_api.reply_message(event.reply_token, messages=TextSendMessage(text=msg))
        return

    elif kind_info == "input_address":
        # add info to df_user
        try:
            place_text = event.message.text.replace('[', '').replace(']', '').replace(" ", '')
            dic_loc  = dict(geolocator.geocode(place_text).raw)
            df_user.loc[user_id] = [event.message.text, dic_loc['lat'], dic_loc['lon']]
            # 住所から緯度経度を求めてdf_userへ保存.
            
            msg = "Thank you!"
        except:
            msg = "Error. " + "Please register your address. You must use below format.\n\n" + "[ your address ]"
        line_bot_api.reply_message(event.reply_token, messages=TextSendMessage(text=msg))
        return

    elif kind_info == "want_register":
        msg = "Input your address"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    elif kind_info == "want_report":
        msg = "What sounds do you hear around you?\n"
        for i in range(3):
          msg += "s{} = {}\n".format(i+1, WANT_REPORT[i])

        items = [QuickReplyButton(action=MessageAction(label=WANT_REPORT_label[i],
                                                       text=WANT_REPORT_label[i])) for i in range(3)]
        messages = TextSendMessage(text=msg, quick_reply=QuickReply(items=items))
        line_bot_api.reply_message(event.reply_token, messages=messages)
        return

    elif kind_info == "report_sound":
        # add info to DataFrame
        df_events.loc[test_id, "text"] = event.message.text
        df_events.loc[test_id, "from"] = user_id
        df_events.loc[test_id, "time"] = time.time()
        

        msg = "What is the condition of springs and groundwater in your neighborhood?\n"
        for i in range(4):
          msg += "w{} = {}\n".format(i+1, REPORT_SOUND[i])

        items = [QuickReplyButton(action=MessageAction(label=REPORT_SOUND_label[i],
                                                       text=REPORT_SOUND_label[i])) for i in range(4)]
        messages = TextSendMessage(text=msg, quick_reply=QuickReply(items=items))
        line_bot_api.reply_message(event.reply_token, messages=messages)
        return

    elif kind_info == "report_crack":
        # add info to DataFrame
        df_events.loc[test_id, "text"] = event.message.text
        df_events.loc[test_id, "from"] = user_id
        df_events.loc[test_id, "time"] = time.time()

        msg = "Are there any other changes or observations?\n"
        for i in range(3):
          msg += "w{} = {}\n".format(i+1, REPORT_CRACK[i])

        items = [QuickReplyButton(action=MessageAction(label=REPORT_CRACK_label[i],
                                                       text=REPORT_CRACK_label[i])) for i in range(3)]
        messages = TextSendMessage(text=msg, quick_reply=QuickReply(items=items))
        line_bot_api.reply_message(event.reply_token, messages=messages)
        return

    elif kind_info == "end_report":
        # add info to DataFrame
        df_events.loc[test_id, "text"] = event.message.text
        df_events.loc[test_id, "from"] = user_id
        df_events.loc[test_id, "time"] = time.time()

        msg = "Thank you for infomation! Be careful!"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        print(df_events.head())

        time.sleep(2)
        # 情報が出そろったので、ハザードマップの生成とほかの人へのプッシュ通知.
        # event_lat = df_user.loc[user_id]["lat"]
        # event_lon = df_user.loc[user_id]["lon"]
        # list_push_member_id, path_image = search_danger_user(event_lat, event_lon, df_user)
        for uid in set(df_user.index):
            lon = df_user.loc[uid]['lon']
            lat = df_user.loc[uid]['lat']
            if lon and lat:
                try:
                    html_path = get_hazard_map(lat,lon , map_fu)
                    msg = f'We got info about slide at your address!!\n'
                    msg += f'{URL}/{html_path}'
                    msg = TextSendMessage(text=msg)
                    print("debug", uid, msg)
                    print('same ', uid==user_id)
                    line_bot_api.push_message(str(uid),msg)
                except:
                    print("fail: ", uid)

            #msg = ImageSendMessage(original_content_url="https://placehold.jp/150x150.png",
            #                    preview_image_url="https://placehold.jp/150x150.png")

    return

    @app.route('static/<path:path>')
    def send_map_html(path):
        return send_from_directory ('js', path)




if __name__ == "__main__":
    FIRST_OP = ["register", "report"]
    FIRST_OP_known = ["report"]
    FIRST_OP_unknown = ["register"]
    WANT_REPORT = ["The ground is rumbling", "The buildings are creaking.", "No unusual sounds."]
    WANT_REPORT_label = ["s1", "s2", "s3"]
    REPORT_SOUND = ["Spring water or groundwater is cloudy.",
                    "The speed of flowing spring water or groundwater is increasing rapidly.",
                    "Springs and/or groundwater are no longer flowing.",
                    "No unusual changes"]
    REPORT_SOUND_label = ["w1", "w2", "w3", "w4"]
    REPORT_CRACK = ["There are cracks and bumps in the road.",
                    "Fallen rocks and/or small landslides have occurred.", 
                    "No unusual changes."]
    REPORT_CRACK_label = ["c1", "c2", "c3"]

    df_user = pd.DataFrame(columns=["address", "lat", "lon"])
    test1_id = "AAAAAAAAAAAAAAAAAAAAA222"
    test1_address = "岩手県久慈市栄町"

    test2_id = "AAAAAAAAAAAAAAAAAAA111"
    test2_address = "岩手県二戸市福岡上平10"
    # address_latlon = get_latlon(test1_address)
    df_user.loc[test1_id] = [test1_address, 40.114260, 141.451245]
    df_user.loc[test2_id] = [test2_address, 40.274179, 141.303416]

    df_events = pd.DataFrame(columns=["text", 'from', 'time'])

    app.run(host="localhost", port=6006)



