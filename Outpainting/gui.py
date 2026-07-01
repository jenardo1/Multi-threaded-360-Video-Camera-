from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QWidget, QApplication, QLabel, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt5.QtWidgets import QSlider
from PyQt5.QtGui import QPixmap, QFont, QColor, QPalette, QImage, QTransform, QKeyEvent
from obswebsocket import obsws, requests

import sys
import cv2
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread, QTimer, QEvent
import numpy as np
import threading
import math
import pyautogui

import time
import datetime
import mediapipe as mp
import pandas
from PIL import Image 
import ctypes
from cvzone.HandTrackingModule import HandDetector

import os
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import shutil
import win32com.client
import vlc

conv = False
manual = False
ignore = False
flip = False
ignore = False
manual_90 = False
manual_180 = False
manual_270 = False
manual_360 = False
no_face = False
autoframe = False
dedicated = False
outpaint = False
zone_select = False
show_splice = False
show_fps = True
show_sliwin = False
show_bbox = True
x_off_1 = 0
x_off_2 = 0
frame_ratio = 0
thickness = 1
point_1 =0
proceed = False

x_min_thread = [None] * 5
x_max_thread = [None] * 5
detections = [None]*5

mp_face_detection = mp.solutions.face_detection
detector = HandDetector(detectionCon=0.8, maxHands=1)

pano_width = 1645
pano_height = 226

roi_top_left1 = (0, 0)
roi_bottom_right1 = (math.ceil(pano_width//5), pano_height)

roi_top_left2 = (math.ceil(pano_width//5), 0)
roi_bottom_right2 = (math.ceil(pano_width*0.4), pano_height)

roi_top_left3 = (math.ceil(pano_width*0.4), 0)
roi_bottom_right3 = (math.ceil(pano_width*(0.6)), pano_height)

roi_top_left4 = (math.ceil(pano_width*(0.6)), 0)
roi_bottom_right4 = (math.ceil(pano_width*(0.8)), pano_height)

roi_top_left5 = (math.ceil(pano_width*(0.8)), 0)
roi_bottom_right5 = (pano_width, pano_height)

rois = [
        (roi_top_left1, roi_bottom_right1),
        (roi_top_left2, roi_bottom_right2),
        (roi_top_left3, roi_bottom_right3),
        (roi_top_left4, roi_bottom_right4),
        (roi_top_left5, roi_bottom_right5)
    ]

threads = [None] * 5
roi_with_faces = []


def VideoModes():
    global margin_min, margin_max, results
    global roi_top_left_1, roi_top_left_2, roi_top_left_3, roi_top_left_4, roi_bottom_right_1, roi_bottom_right_2, roi_bottom_right_3, roi_bottom_right_4
    global display_width_ded, display_height_ded
    d_width = 428
    d_height = 321
    
    while True: 
        # Ensure x_min_a, x_max_a, and off_max are defined before using them
            try:
                if any(x is not None for x in x_min_thread) and any(x is not None for x in x_max_thread):
                    #minimum and maximum values + margin handling for autoframing
                    x_min_none = [value for value in x_min_thread if value is not None]
                    x_min_a = min(x_min_none)
                    x_max_none =  [value for value in x_max_thread if value is not None]
                    off_max_rightmost = max(x_max_none)
                    #print("dragons are great because they have magical powers AH! FANGIRLS OOH OHOHHOOOH HOOO")
                    #print(detections)
                    
                    
                    margin_min = max(0, min(x_min_a - i for i in range(101, 0, -1)))
                    margin_max = min(frame_width, max(off_max_rightmost + i for i in range(101, 0, -1)))
                    #print(margin_min)
            except:
                pass

            
            #if autoframe or dedicated:
            for i, detected in enumerate(detections):
                if detected is not None:
                    if rois[i] not in roi_with_faces:
                        roi_with_faces.append(rois[i])
                    else:
                        pass
                else:
                    if rois[i] in roi_with_faces:
                        roi_with_faces.remove(rois[i])
                    else:
                        pass
                print(roi_with_faces)

            if len(roi_with_faces) == 1:
                display_width_ded = math.ceil((pano_width//5))
                display_height_ded = pano_height
                roi_top_left_1, roi_bottom_right_1 = roi_with_faces[0]
            
            elif len(roi_with_faces) ==2:
                display_width_ded = math.ceil((pano_width//5)*2)
                display_height_ded = pano_height
                roi_top_left_1, roi_bottom_right_1 = roi_with_faces[0]
                roi_top_left_2, roi_bottom_right_2 = roi_with_faces[1]

            elif len(roi_with_faces) ==3:
                display_width_ded = math.ceil((pano_width//5)*3)
                display_height_ded = pano_height*3
                roi_top_left_1, roi_bottom_right_1 = roi_with_faces[0]
                roi_top_left_2, roi_bottom_right_2 = roi_with_faces[1]
                roi_top_left_3, roi_bottom_right_3 = roi_with_faces[2]
            
            elif len(roi_with_faces) ==4:
                display_width_ded = math.ceil((pano_width//5)*3)
                display_height_ded = pano_height*3
                roi_top_left_1, roi_bottom_right_1 = roi_with_faces[0]
                roi_top_left_2, roi_bottom_right_2 = roi_with_faces[1]
                roi_top_left_3, roi_bottom_right_3 = roi_with_faces[2]
                roi_top_left_4, roi_bottom_right_4 = roi_with_faces[3]
            
            else:
                display_width_ded = pano_width
                display_height_ded = pano_height
                pass


            print("HOOORAAAAAY I AM DEDICSTAHD")
            time.sleep(4)
                
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    change_pixmap_signal_hands = pyqtSignal(np.ndarray)

    def __init__(self, source=0):
        super().__init__()
        self._run_flag = True
        self.source = source
        self.cap = cv2.VideoCapture(self.source)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 6580)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 902)
    def run(self):
        global thickness, ignore, results, frame, conv, manual, flip, x1, x2, x_min_a, x_max_a, x_off_1, x_off_2, frame_ratio, frame_width, dedicated, autoframe, detections,  dedicated, margin_max, margin_min, autoframe, cap, frame, x_min, x_max, off_min, off_max, off_mid_max, off_mid_min, x_mid_min, x_mid_max, x_mid, frame_height, frame_width, results, no_face
        global show_sliwin, show_fps, show_splice,frame_hands,roi_top_left_1, roi_top_left_2, roi_top_left_3, roi_top_left_4, roi_bottom_right_1, roi_bottom_right_2, roi_bottom_right_3, roi_bottom_right_4
    
        # Initialize CentroidTracker and HandDetector
        detector = HandDetector(detectionCon=0.8, maxHands=1)


        # Function to process each ROI
        def process_roi(roi_top_left, roi_bottom_right, index):
            if show_splice:
                cv2.rectangle(frame, roi_top_left, roi_bottom_right, (0, 255, 0), 2)
            try:
                roi_frame = frame[roi_top_left[1]:roi_bottom_right[1], roi_top_left[0]:roi_bottom_right[0]]
                face_detect(roi_frame, frame, roi_top_left, index)
            except:
                pass
        
        def process_roi_hands(roi_top_left,roi_bottom_right, main_function):
            #cv2.rectangle(frame,roi_top_left, roi_bottom_right, (0,255,0),2)
            roi_frame = frame[roi_top_left[1]:roi_bottom_right[1], roi_top_left[0]:roi_bottom_right[0]]
            if main_function is False:
                draw = False
            else:
                draw = True
            hands, roi_frame = detector.findHands(roi_frame, draw=draw)
            y_splice_crop = roi_top_left[1]
            yheight_splice_crop = roi_bottom_right[1] - y_splice_crop
            x_splice_crop = roi_top_left[0]
            xwidth_splice_crop = roi_top_left[0] - x_splice_crop
            roi_frame[y_splice_crop:yheight_splice_crop, x_splice_crop:xwidth_splice_crop]

            return [hands, roi_frame]
        # Function to detect faces in an ROI
        def face_detect(roi_frame, frame, roi_top_left, index):
            global results, x_min,off_max,x_max

            with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detector:
                rgb_frame = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2RGB)
                results = face_detector.process(rgb_frame)

                rects = []
                if results.detections:
                    min_face = results.detections[0]
                    detections[index] = len(results.detections)
                    for face in results.detections:
                        bbox = face.location_data.relative_bounding_box
                        x_min = int(bbox.xmin * roi_frame.shape[1]) + roi_top_left[0]
                        y_min = int(bbox.ymin * roi_frame.shape[0]) + roi_top_left[1]
                        x_max = x_min + int(bbox.width * roi_frame.shape[1])
                        y_max = y_min + int(bbox.height * roi_frame.shape[0])

                        face_react = [x_min, y_min, x_max, y_max]

                        min_face_bbox = min_face.location_data.relative_bounding_box
                        min_face_bbox_1 = int(min_face_bbox.xmin * roi_frame.shape[1]) + roi_top_left[0]
                        min_face_bbox_3 = min_face_bbox_1 + int(bbox.width * roi_frame.shape[1])

                        if x_min < min_face_bbox_1:
                            x_min_thread[index] = x_min
                        else:
                            x_min_thread[index] = min_face_bbox_1
                        
                        if x_max > min_face_bbox_3:
                            x_max_thread[index] = x_max
                        else:
                            x_max_thread[index] = min_face_bbox_3
                        rects.append(face_react)
                        
                        if show_bbox:
                            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (255, 255, 255), 2)

                else:
                    x_min_thread[index] = None
                    x_max_thread[index] = None
                    detections[index] = None
                pass

        # Main video capture loop
        
        if not self.cap.isOpened():
            print("Error: Unable to open video capture device.")
            return

        frame_counter = 0
        start_time = time.time()
        prev_time = time.time()
        index_hands = 0
        hand_activated = True
        #def process_roi_hands_wrapper(roi, frame_in):
        #    global hands1, img
        #    cv2.rectangle(frame,roi[0], roi[1], (0,255,0),2)

        VolumeControlCounter = 0
        ZoomandRotateControlCounter = 0
        SlidesControlCounter = 0
        MediaControlCounter = 0
        
        ZoomCounter = 0
        VolumeCounter = 0
        forwardcounter = 0
        backwardcounter = 0

        framecounter_zoom = 0
        framecounter_volume = 0
        framecounter_slides = 0
        framecounter_media = 0
        framecounter_activator = 0
        framecounter_deactivator = 0

        main_function = True
        zoom_frame = False

        length_5_17 = 0
        length_0_12 = 0
        initial_y_8 = 0
        initial_y_16 = 0
        
        initial_p_0 = []
        initial_p_9 = []
        initial_mdpt = []
        initial_angle = 0
        x_midpt_range = [0,0]
        y_midpt_range = [0,0]

        # initial zoom variables
        zoom_image_path = "imagesample.png"

        slope_0_9 = 1000000
        stab_cx = 0
        stab_cy = 0
        middle_raised = False
        pinky_raised = False
        ZoomandRotateControl = False

        # initial volume variables
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        volper = int(volume.GetMasterVolumeLevelScalar()*100)
        VolumeControl = False

        # initial slides variables (export slides to images)
        presentation_path = r"sampleslides.pptx"
        Application = win32com.client.Dispatch("Powerpoint.Application")

        try:
            Presentation = Application.Presentations.Open(presentation_path, WithWindow = False)
            slides_folder = os.path.join(os.path.dirname(presentation_path), "Slides")
            if not os.path.exists(slides_folder):
                os.makedirs(slides_folder)
            else:
                shutil.rmtree("Slides")
                os.makedirs(slides_folder)
            for i, slide in enumerate(Presentation.Slides):
                image_path = os.path.join(slides_folder, f"{i + 1}.png")
                slide.Export(image_path, "JPG")
            Presentation.Close()
        except Exception as e:
            print(f"An error occured: {e}")
        finally:
            Application.Quit()

        folderpath = "Slides"
        pathimages = sorted(os.listdir(folderpath), key=len)
        imagenumber = 0
        movedetector = False
        framecounter = 0
        remote_hand = False
        SlidesControl = False

        # initial media variables
        video_path = r"videosample.mp4"
        video_paused = False
        video_playing = False
        rate_unscaled = 0
        general_counter = 0
        pause_counter = 0
        framecounter_rate = 0
        RateChangeCounter = 0
        framecounter_skip = 0
        rate = 1
        frame_change = False
        media = vlc.MediaPlayer(video_path)
        video = cv2.VideoCapture(video_path)
        
        MediaControl = False 
        while self._run_flag:
            frame_counter += 1
            ret, frame = self.cap.read()
            
            if not ret:
                break
            #frame = cv2.resize(frame, (6580, 904), interpolation=cv2.INTER_CUBIC)
            frame = cv2.resize(frame, (pano_width, pano_height), interpolation=cv2.INTER_AREA)
            frame_height, frame_width, _ = frame.shape
            
            hands1, img = process_roi_hands(rois[index_hands][0], rois[index_hands][1], main_function)
            cam_height = img.shape[0]
            cam_width = img.shape[1]
            if hands1:
                frame_hands = frame[rois[index_hands][0][1]:rois[index_hands][1][1], rois[index_hands][0][0]:rois[index_hands][1][0]]
                hand1 = hands1[0]
                lmList1 = hand1["lmList"]
                hand1_type = hand1["type"]
                fingers1 = detector.fingersUp(hand1)

                # initialize variables
                p_5 = lmList1[5][0:2]
                p_17 = lmList1[17][0:2]

                p_9 = lmList1[9][0:2]
                p_0 = lmList1[0][0:2]

                p_4 = lmList1[4][0:2]
                p_8 = lmList1[8][0:2]
                p_12 = lmList1[12][0:2]
                p_16 = lmList1[16][0:2]
                p_20 = lmList1[20][0:2]

                length_8_12 = math.hypot(p_8[0] - p_12[0], p_8[1] - p_12[1])
                length_16_4 = math.hypot(p_16[0] - p_4[0], p_16[1] - p_4[1])
                length_0_8 = math.hypot(p_0[0] - p_8[0], p_0[1] - p_8[1])
                length_0_12 = math.hypot(p_0[0] - p_12[0], p_0[1] - p_12[1])
                length_0_20 = math.hypot(p_0[0] - p_20[0], p_0[1] - p_20[1])

                # activate hand gesture regonizer
                if fingers1 == [1,1,1,1,1]:
                    if hand_activated is False:
                        framecounter_activator += 1
                else:
                    framecounter_activator = 0
                if framecounter_activator >= 50:
                    framecounter_activator = 0
                    hand_activated = True
                if main_function is False:
                    framecounter_activator = 0
                # slope of line 0_9
                if abs(p_9[0]-p_0[0]) < 0.05:
                    slope_0_9 = 1000000
                else:
                    slope_0_9 = abs((p_9[1]-p_0[1])/(p_9[0]-p_0[0]))

                # Functionalities
                if (hand1_type == "Right" and (p_5[0] > p_17[0])) or (hand1_type == "Left" and (p_5[0] < p_17[0])) and hand_activated:

                    # deactivate hand gesture recognizer
                    if fingers1 == [1,1,1,1,1]:
                        framecounter_activator += 1
                    else:
                        framecounter_activator = 0
                    if framecounter_activator >= 50:
                        framecounter_activator = 0
                        hand_activated = False
                    if hand_activated is False and main_function is True:
                        cv2.putText(frame_hands, f'Hand Gesture Deactivated', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                    else:
                        if ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                            cv2.line(img, (p_9[0], p_9[1]), (p_0[0], p_0[1]), (0, 255, 0), 5)
                     # ZoomandRotate activator
                    if (fingers1 == [0,1,0,0,0] or fingers1 == [0,0,0,0,0]) and VolumeControlCounter == 0 and SlidesControlCounter == 0 and MediaControlCounter == 0 and ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                        if fingers1 == [0,1,0,0,0] and ZoomandRotateControlCounter == 0:
                            framecounter_zoom = 0
                            ZoomandRotateControlCounter = 1
                        if fingers1 == [0,0,0,0,0] and (ZoomandRotateControlCounter == 1 or ZoomandRotateControlCounter == 2):
                            framecounter_zoom += 1
                            if framecounter_zoom >= 10:
                                ZoomandRotateControlCounter = 0
                            else:
                                ZoomandRotateControlCounter = 2
                        if fingers1 == [0,1,0,0,0] and ZoomandRotateControlCounter == 2:
                            main_function = False
                            ZoomandRotateControl = True
                            ZoomandRotateControlCounter = 0
                    else:
                        if ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                            framecounter_zoom += 1
                            if framecounter_zoom >= 10:
                                framecounter_zoom = 0
                                ZoomandRotateControlCounter = 0
                    
                    # VolumeControl activator
                    if (fingers1 == [0,1,1,0,0] or fingers1 == [0,0,0,0,0]) and ZoomandRotateControlCounter == 0 and SlidesControlCounter == 0 and MediaControlCounter == 0 and ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                        if fingers1 == [0,1,1,0,0] and VolumeControlCounter == 0:
                            framecounter_volume = 0
                            VolumeControlCounter = 1
                        if fingers1 == [0,0,0,0,0] and (VolumeControlCounter == 1 or VolumeControlCounter == 2):
                            framecounter_volume += 1
                            if framecounter_volume >= 10:
                                VolumeControlCounter = 0
                            else:
                                VolumeControlCounter = 2
                        if fingers1 == [0,1,1,0,0] and VolumeControlCounter == 2:
                            main_function = False
                            VolumeControl = True
                            VolumeControlCounter = 0
                    else:
                        if ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                            framecounter_volume += 1
                            if framecounter_volume >= 10:
                                framecounter_volume = 0
                                VolumeControlCounter = 0

                    # SlidesControl activator
                    if (fingers1 == [0,1,1,1,0] or fingers1 == [0,0,0,0,0]) and ZoomandRotateControlCounter == 0 and VolumeControlCounter == 0 and MediaControlCounter == 0 and ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                        if fingers1 == [0,1,1,1,0] and SlidesControlCounter == 0:
                            framecounter_slides = 0
                            SlidesControlCounter = 1
                        if fingers1 == [0,0,0,0,0] and (SlidesControlCounter == 1 or SlidesControlCounter == 2):
                            framecounter_slides += 1
                            if framecounter_slides >= 10:
                                SlidesControlCounter = 0
                            else:
                                SlidesControlCounter = 2
                        if fingers1 == [0,1,1,1,0] and SlidesControlCounter == 2:
                            main_function = False
                            SlidesControl = True
                            SlidesControlCounter = 0
                    else:
                        if ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                            framecounter_slides += 1
                            if framecounter_slides >= 10:
                                framecounter_slides = 0
                                SlidesControlCounter = 0

                    # MediaControl activator
                    if (fingers1 == [0,1,1,1,1] or fingers1 == [0,0,0,0,0]) and ZoomandRotateControlCounter == 0 and VolumeControlCounter == 0 and SlidesControlCounter == 0 and ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                        if fingers1 == [0,1,1,1,1] and MediaControlCounter == 0:
                            framecounter_media = 0
                            MediaControlCounter = 1
                        if fingers1 == [0,0,0,0,0] and (MediaControlCounter == 1 or MediaControlCounter == 2):
                            framecounter_media += 1
                            if framecounter_media >= 10:
                                MediaControlCounter = 0
                            else:
                                MediaControlCounter = 2
                        if fingers1 == [0,1,1,1,1] and MediaControlCounter == 2:
                            main_function = False
                            MediaControl = True
                            MediaControlCounter = 0
                    else:
                        if ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                            framecounter_media += 1
                            if framecounter_media >= 10:
                                framecounter_media = 0
                                MediaControlCounter = 0
                else:
                    ZoomandRotateControlCounter = 0
                    VolumeControlCounter = 0
                    SlidesControlCounter = 0
                    MediaControlCounter = 0
                 # display instructions
                if ZoomandRotateControlCounter >= 1 and ZoomandRotateControlCounter <= 2 and ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                    cv2.putText(frame_hands, f'Activate Zoom Control?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                if VolumeControlCounter >= 1 and VolumeControlCounter <= 2 and ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                    cv2.putText(frame_hands, f'Activate Volume Control?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                if SlidesControlCounter >= 1 and SlidesControlCounter <= 2 and ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                    cv2.putText(frame_hands, f'Activate Slides Control?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                if MediaControlCounter >= 1 and MediaControlCounter <= 2 and ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False and MediaControl is False:
                    cv2.putText(frame_hands, f'Activate Media Control?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                
                # Zoom function            
                if ZoomandRotateControl is True and VolumeControl is False and SlidesControl is False and MediaControl is False:          
                    # initial zoom variables
                    zoom_img = cv2.imread("imagesample.jpg")       
                    cv2.line(img, (p_16[0], p_16[1]), (p_4[0], p_4[1]), (0, 255, 0), 5)

                    # initial values
                    if length_5_17 == 0:
                        length_5_17 = math.hypot(p_5[0] - p_17[0], p_5[1] - p_17[1])

                    if initial_p_0 == []:
                        initial_p_0 = p_0
                    if initial_p_9 == []:
                        initial_p_9 = p_9
                    initial_mdpt = [(initial_p_0[0] + initial_p_9[0]) // 2, (initial_p_0[1] + initial_p_9[1]) // 2]
                    mdpt = [(p_0[0] + p_9[0]) // 2, (p_0[1] + p_9[1]) // 2]

                    # lock zoom
                    lz_ratio = length_0_20/length_5_17
                    if lz_ratio > 2:
                        pinky_raised = True
                    else:
                        pinky_raised = False

                    # zoom percentage
                    if not pinky_raised:
                        normalizer = length_16_4/length_5_17
                        zoomper = np.interp(normalizer, [0.5, 3], [100, 600])
                        if zoomper % 50 != 0:
                            zoomper = zoomper - (zoomper%50)
                        zoomper = zoomper/100

                    # resize
                    height = zoom_img.shape[0]
                    width = zoom_img.shape[1]
                    new_height = int(height/2)
                    new_width = int(width/2)
                    zoom_img = cv2.resize(zoom_img, (new_width, new_height))
                    hypothenuse = int(math.hypot(new_width, new_height))

                    border_height = int((hypothenuse-new_height)/2)
                    border_width = int((hypothenuse-new_width)/2)

                    zoom_img = cv2.copyMakeBorder(zoom_img, border_height, border_height, border_width, border_width, cv2.BORDER_CONSTANT, 0)

                    # center point
                    x_midpt_range = [int(initial_mdpt[0]-(2*length_5_17)), int(initial_mdpt[0]+(2*length_5_17))]
                    y_midpt_range = [int(initial_mdpt[1]-(2*length_5_17)), int(initial_mdpt[1]+(2*length_5_17))]

                    x_diff = x_midpt_range[1] - x_midpt_range[0]
                    y_diff = y_midpt_range[1] - y_midpt_range[0]

                    if x_midpt_range[0] < 20:     
                        x_midpt_range = [20, 20 + x_diff]
                    if x_midpt_range[1] > cam_width - 20:
                        x_midpt_range = [cam_width - 20 - x_diff, cam_width - 20]          
                    if x_midpt_range[0] <= 20 and x_midpt_range[1] >= cam_width - 20:
                        x_midpt_range = [20, cam_width - 20]
                    if y_midpt_range[0] < 20:     
                        y_midpt_range = [20, 20 + y_diff]
                    if y_midpt_range[1] > cam_height - 20:
                        y_midpt_range = [cam_height - 20 - y_diff, cam_height - 20]
                    if y_midpt_range[0] <= 20 and y_midpt_range[1] >= cam_height - 20:
                        y_midpt_range = [20, cam_height - 20]

                    cx = int(np.interp(mdpt[0], [x_midpt_range[0], x_midpt_range[1]], [hypothenuse, 0]))
                    cy = int(np.interp(mdpt[1], [y_midpt_range[0], y_midpt_range[1]], [0, hypothenuse]))
                    
                    # lock center point
                    lcp_ratio = length_0_12/length_5_17
                    if lcp_ratio > 1.5:
                        middle_raised = True
                    else:
                        middle_raised = False
                    if middle_raised is False:
                        if cx % 20 != 0:
                            stab_cx = cx - (cx%20)
                        if cy % 20 != 0:
                            stab_cy = cy - (cy%20)
                        if cx == hypothenuse:
                            stab_cx = hypothenuse
                        if cy == hypothenuse:
                            stab_cy = hypothenuse
                    # angle
                    if abs(p_9[0]-p_0[0]) < 0.05:
                        slope_0_9 = 1000000
                    else:
                        slope_0_9 = ((p_9[1]-p_0[1])/(p_9[0]-p_0[0]))

                    angle = math.atan(slope_0_9)
                    angle = math.degrees(angle)

                    if (p_0[0] < p_9[0]):
                        angle = angle + 180

                    if initial_angle == 0:
                        initial_angle = angle
                    angle = int(angle - initial_angle)

                    if angle % 30 != 0:
                        angle = angle - (angle%30)            

                    # display
                    cv2.rectangle(img, (x_midpt_range[0], y_midpt_range[0]), (x_midpt_range[1], y_midpt_range[1]), (0, 255, 0), 3)
                    cv2.circle(zoom_img, (stab_cx, stab_cy), 5, (255, 0, 0), cv2.FILLED)
                    cv2.circle(img, (mdpt[0], mdpt[1]), 10, (255, 0, 0), cv2.FILLED)

                    # zoom and rotate
                    if middle_raised is True and pinky_raised is False:
                        cv2.putText(img, f'{int(zoomper*100)}%', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                        rotate_matrix = cv2.getRotationMatrix2D((stab_cx, stab_cy), 0, scale=zoomper)
                        zoom_img = cv2.warpAffine(zoom_img, rotate_matrix, (hypothenuse, hypothenuse))    
                    if middle_raised is True and pinky_raised is True:
                        rotate_matrix = cv2.getRotationMatrix2D((stab_cx, stab_cy), 0, scale=zoomper)
                        zoom_img = cv2.warpAffine(zoom_img, rotate_matrix, (hypothenuse, hypothenuse))
                        rotate_matrix = cv2.getRotationMatrix2D((hypothenuse//2, hypothenuse//2), angle, scale=1)
                        zoom_img = cv2.warpAffine(zoom_img, rotate_matrix, (hypothenuse, hypothenuse))
                    cv2.imshow("Zoom Image", zoom_img)
                    # deactivator
                    cv2.circle(img, (p_8[0], p_8[1]), 10, (0, 255, 0), cv2.FILLED)
                    deact_ratio = length_0_8/length_5_17
                    if deact_ratio < 1.5 and ZoomandRotateControlCounter == 0:
                        ZoomandRotateControlCounter = 1
                    if deact_ratio > 2 and ZoomandRotateControlCounter == 1:
                        ZoomandRotateControlCounter = 0
                        ZoomandRotateControl = False
                        main_function = True
                        length_5_17 = 0
                        initial_p_0 = []
                        initial_p_9 = []
                        cv2.destroyWindow("Zoom Image")

                # Volume function
                if VolumeControl is True and ZoomandRotateControl is False and SlidesControl is False and MediaControl is False:
                    if abs(p_9[0]-p_0[0]) < 0.05:
                        slope_0_9 = 1000000
                    else:
                        slope_0_9 = abs((p_9[1]-p_0[1])/(p_9[0]-p_0[0]))

                    # initial values for normalizing
                    if length_5_17 == 0:
                        length_5_17 = math.hypot(p_17[0] - p_5[0], p_17[1] - p_5[1])
                    if length_0_12 == 0:    
                        length_0_12 = p_0[1] - p_12[1]
                    if initial_y_8 == 0:
                        initial_y_8 = p_8[1]
                    
                    # limits
                    botbarvalue = int(initial_y_8 + ((1.25)*length_5_17))
                    topbarvalue = int(initial_y_8 - ((1.25)*length_5_17))
                    camheight = rois[index_hands][1][1]

                    if topbarvalue < 20:
                        topbarvalue = 20
                        botbarvalue = 20 + int(2.5*length_5_17)
                    
                    if botbarvalue > camheight - length_0_12 - 20:
                        botbarvalue = int(camheight - length_0_12 - 20)
                        topbarvalue = botbarvalue - int(2.5*length_5_17)

                    if topbarvalue < 20 and botbarvalue > camheight - length_0_12 - 20:
                        topbarvalue = 20
                        botbarvalue = int(camheight - length_0_12 - 20)

                    length_8_12_normalizer = length_8_12/length_5_17
                    if (slope_0_9 > 1.732) and ((hand1_type == "Right" and (p_5[0] > p_17[0])) or (hand1_type == "Left" and (p_5[0] < p_17[0]))):
                        #cv2.line(img, (p_9[0], p_9[1]), (p_0[0], p_0[1]), (0, 255, 0), 5)
                        
                        if ((length_8_12_normalizer < 0.5) and (fingers1 == [0, 1, 1, 0, 0] or fingers1 == [1, 1, 1, 0, 0])) or (fingers1 == [0, 1, 0, 0, 0] or fingers1 == [1, 1, 0, 0, 0]):
                            cv2.rectangle(img, (20, 40), (50, 160), (255, 0, 0), 3)
                            cv2.circle(img, (p_8[0], p_8[1]), 10, (0, 255, 0), cv2.FILLED)

                            # if 2 fingers are up (adjust volume by 10)
                            if fingers1 == [0, 1, 1, 0, 0] or fingers1 == [1, 1, 1, 0, 0]:
                                volper = np.interp(p_8[1], [topbarvalue, botbarvalue], [100, 0])
                                volper = 10*round(volper/10)
                                volbar = int(np.interp(p_8[1], [topbarvalue, botbarvalue], [40, 160]))
                                volbar = (round((volbar-40)/12)*12)+40
                                cv2.putText(img, f'{int(volper)}%', (15, 180), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)

                                if fingers1 == [1, 1, 1, 0, 0]:
                                    volume.SetMasterVolumeLevelScalar(volper/100, None)
                                    cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)

                            # if 1 fingers are up (adjust volume by 1)
                            if fingers1 == [0, 1, 0, 0, 0] or fingers1 == [1, 1, 0, 0, 0]:
                                if volper >= 100:
                                    volper = 90
                                volper_10 = np.interp(p_8[1], [topbarvalue, botbarvalue], [volper+9, volper])
                                volbar = int(160-(volper_10*1.2))
                                cv2.putText(img, f'{int(volper_10)}%', (15, 180), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                
                                if fingers1 == [1, 1, 0, 0, 0]:
                                    volume.SetMasterVolumeLevelScalar(volper_10/100, None)
                                    cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)

                                if p_8[1] > botbarvalue:
                                    cv2.rectangle(img, (20, int(160-((volper)*1.2))), (50, 160), (255, 0, 0), cv2.FILLED)

                            # drawing volume bar  
                            if p_8[1] <= botbarvalue:
                                cv2.rectangle(img, (20, volbar), (50, 160), (255, 0, 0), cv2.FILLED)

                    # deactivator
                    if (fingers1 == [0,1,1,0,0] or fingers1 == [0,0,0,0,0]) and length_8_12_normalizer < 0.5:
                        if fingers1 == [0,1,1,0,0] and VolumeControlCounter == 0:
                            VolumeControlCounter = 1
                        if fingers1 == [0,0,0,0,0] and VolumeControlCounter == 1:
                            VolumeControlCounter = 2
                        if fingers1 == [0,1,1,0,0] and VolumeControlCounter == 2:
                            main_function = True
                            VolumeControl = False
                            length_5_17 = 0
                            length_0_12 = 0
                            initial_y_8 = 0
                            VolumeControlCounter = 0

                # Slides function
                if SlidesControl is True and ZoomandRotateControl is False and VolumeControl is False and MediaControl is False:
                    # initial slides variable
                    currentimg = cv2.imread(os.path.join(folderpath, pathimages[imagenumber]))
                    slide_height = currentimg.shape[0]
                    slide_width = currentimg.shape[1]
                    currentimg_ratio = slide_height/slide_width

                    if length_5_17 == 0:
                        length_5_17 = math.hypot(p_5[0] - p_17[0], p_5[1] - p_17[1])

                    if abs(p_9[0]-p_0[0]) < 0.05:
                        slope_0_9 = 1000000
                    else:
                        slope_0_9 = abs((p_9[1]-p_0[1])/(p_9[0]-p_0[0]))
                    
                    if ((hand1_type == "Right" and (p_5[0] > p_17[0])) or (hand1_type == "Left" and (p_5[0] < p_17[0]))):
                        # change slide
                        if (fingers1 == [1,0,0,0,0] and hand1_type == "Right") or (fingers1 == [0,0,0,0,1] and hand1_type == "Left"):
                            if hand1_type == "Right":
                                cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)
                            else:
                                cv2.circle(img, (p_20[0], p_20[1]), 10, (0, 255, 0), cv2.FILLED)
                            if imagenumber > 0 and movedetector is False:
                                imagenumber = imagenumber - 1
                                movedetector = True
                                backwardcounter = backwardcounter + 1      
                        else:
                            backwardcounter = 0
                        if (fingers1 == [0,0,0,0,1] and hand1_type == "Right") or (fingers1 == [1,0,0,0,0] and hand1_type == "Left"):
                            if hand1_type == "Right":
                                cv2.circle(img, (p_20[0], p_20[1]), 10, (0, 255, 0), cv2.FILLED)
                            else:
                                cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)
                            if imagenumber < len(pathimages)-1 and movedetector is False:
                                imagenumber = imagenumber + 1
                                movedetector = True
                                forwardcounter = forwardcounter + 1
                        else:
                            forwardcounter = 0

                        # zoom slide
                        if (fingers1 == [0,1,0,0,0] or fingers1 == [0,0,0,0,0]) and VolumeCounter == 0 and SlidesControlCounter == 0:
                            if fingers1 == [0,1,0,0,0] and ZoomCounter == 0:
                                framecounter_zoom = 0
                                ZoomCounter = 1
                            if fingers1 == [0,0,0,0,0] and (ZoomCounter == 1 or ZoomCounter == 2):
                                framecounter_zoom += 1
                                if framecounter_zoom >= 10:
                                    ZoomCounter = 0
                                else:
                                    ZoomCounter = 2
                            if fingers1 == [0,1,0,0,0] and ZoomCounter == 2:
                                ZoomCounter = 3           
                            if ZoomCounter == 1 or ZoomCounter == 2:
                                cv2.putText(img, f'Zoom slide image?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                        else:
                            framecounter_zoom += 1
                            if framecounter_zoom >= 10:
                                framecounter_zoom = 0
                                ZoomCounter = 0
                        length_0_8 = math.hypot(p_0[0] - p_8[0], p_0[1] - p_8[1])
                        deact_ratio = length_0_8/length_5_17
                        if ZoomCounter == 3:
                            if zoom_frame is False:
                                slide_img = currentimg
                                zoom_frame = True
                            zoom_img = slide_img
                            framecounter_zoom = 0
                            if initial_p_0 == []:
                                initial_p_0 = p_0
                            if initial_p_9 == []:
                                initial_p_9 = p_9
                            length_16_4 = math.hypot(p_16[0] - p_4[0], p_16[1] - p_4[1])
                            length_0_12 = math.hypot(p_0[0] - p_12[0], p_0[1] - p_12[1])
                            length_0_20 = math.hypot(p_0[0] - p_20[0], p_0[1] - p_20[1])
                            cv2.line(img, (p_16[0], p_16[1]), (p_4[0], p_4[1]), (0, 255, 0), 5)
                            initial_mdpt = [(initial_p_0[0] + initial_p_9[0]) // 2, (initial_p_0[1] + initial_p_9[1]) // 2]
                            mdpt = [(p_0[0] + p_9[0]) // 2, (p_0[1] + p_9[1]) // 2]
                            # lock zoom
                            lz_ratio = length_0_20/length_5_17
                            if lz_ratio > 2:
                                pinky_raised = True
                            else:
                                pinky_raised = False
                            # zoom percentage
                            if pinky_raised is False:
                                normalizer = length_16_4/length_5_17
                                zoomper = np.interp(normalizer, [0.5, 3], [100, 600])
                                if zoomper % 50 != 0:
                                    zoomper = zoomper - (zoomper%50)
                                zoomper = zoomper/100
                            # resize
                            height = zoom_img.shape[0]
                            width = zoom_img.shape[1]
                            new_height = int(height/2)
                            new_width = int(width/2)
                            zoom_img = cv2.resize(zoom_img, (new_width, new_height))
                            hypothenuse = int(math.hypot(new_width, new_height))
                            border_height = int((hypothenuse-new_height)/2)
                            border_width = int((hypothenuse-new_width)/2)
                            zoom_img = cv2.copyMakeBorder(zoom_img, border_height, border_height, border_width, border_width, cv2.BORDER_CONSTANT, 0)
                            # center point
                            x_midpt_range = [int(initial_mdpt[0]-(2*length_5_17)), int(initial_mdpt[0]+(2*length_5_17))]
                            y_midpt_range = [int(initial_mdpt[1]-(2*length_5_17)), int(initial_mdpt[1]+(2*length_5_17))]
                            x_diff = x_midpt_range[1] - x_midpt_range[0]
                            y_diff = y_midpt_range[1] - y_midpt_range[0]
                            if x_midpt_range[0] < 20:     
                                x_midpt_range = [20, 20 + x_diff]
                            if x_midpt_range[1] > cam_width - 20:
                                x_midpt_range = [cam_width - 20 - x_diff, cam_width - 20]          
                            if x_midpt_range[0] <= 20 and x_midpt_range[1] >= cam_width - 20:
                                x_midpt_range = [20, cam_width - 20]
                            if y_midpt_range[0] < 20:     
                                y_midpt_range = [20, 20 + y_diff]
                            if y_midpt_range[1] > cam_height - 20:
                                y_midpt_range = [cam_height - 20 - y_diff, cam_height - 20]
                            if y_midpt_range[0] <= 20 and y_midpt_range[1] >= cam_height - 20:
                                y_midpt_range = [20, cam_height - 20]
                            cx = int(np.interp(mdpt[0], [x_midpt_range[0], x_midpt_range[1]], [hypothenuse, 0]))
                            cy = int(np.interp(mdpt[1], [y_midpt_range[0], y_midpt_range[1]], [0, hypothenuse]))     
                            # lock center point
                            lcp_ratio = length_0_12/length_5_17
                            if lcp_ratio > 1.5:
                                middle_raised = True
                            else:
                                middle_raised = False
                            if middle_raised is False:
                                if cx % 20 != 0:
                                    stab_cx = cx - (cx%20)
                                if cy % 20 != 0:
                                    stab_cy = cy - (cy%20)
                                if cx == hypothenuse:
                                    stab_cx = hypothenuse
                                if cy == hypothenuse:
                                    stab_cy = hypothenuse
                            # angle
                            if abs(p_9[0]-p_0[0]) < 0.05:
                                slope_0_9 = 1000000
                            else:
                                slope_0_9 = ((p_9[1]-p_0[1])/(p_9[0]-p_0[0]))
                            angle = math.atan(slope_0_9)
                            angle = math.degrees(angle)
                            if (p_0[0] < p_9[0]):
                                angle = angle + 180
                            if initial_angle == 0:
                                initial_angle = angle
                            angle = int(angle - initial_angle)
                            if angle % 30 != 0:
                                angle = angle - (angle%30)            
                            # display
                            cv2.rectangle(img, (x_midpt_range[0], y_midpt_range[0]), (x_midpt_range[1], y_midpt_range[1]), (0, 255, 0), 3)
                            cv2.circle(zoom_img, (stab_cx, stab_cy), 5, (255, 0, 0), cv2.FILLED)
                            cv2.circle(img, (mdpt[0], mdpt[1]), 10, (255, 0, 0), cv2.FILLED)
                            #zoom and rotate
                            if middle_raised is True and pinky_raised is False:
                                cv2.putText(img, f'{int(zoomper*100)}%', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                                rotate_matrix = cv2.getRotationMatrix2D((stab_cx, stab_cy), 0, scale=zoomper)
                                zoom_img = cv2.warpAffine(zoom_img, rotate_matrix, (hypothenuse, hypothenuse))    
                            if middle_raised is True and pinky_raised is True:
                                rotate_matrix = cv2.getRotationMatrix2D((stab_cx, stab_cy), 0, scale=zoomper)
                                zoom_img = cv2.warpAffine(zoom_img, rotate_matrix, (hypothenuse, hypothenuse))
                                rotate_matrix = cv2.getRotationMatrix2D((hypothenuse//2, hypothenuse//2), angle, scale=1)
                                zoom_img = cv2.warpAffine(zoom_img, rotate_matrix, (hypothenuse, hypothenuse))
                            cv2.imshow("Slide Image", zoom_img)
                        if deact_ratio < 1.5 and ZoomCounter == 3:
                            ZoomCounter = 4
                        if deact_ratio > 2 and ZoomCounter == 4:
                            zoom_frame = False
                            cv2.destroyWindow("Slide Image")
                            initial_p_0 = []
                            initial_p_9 = []
                            ZoomCounter = 0

                        # change volume
                        if (fingers1 == [0,1,1,0,0] or fingers1 == [0,0,0,0,0] or fingers1 == [1,1,1,0,0]) and SlidesControlCounter == 0 and ZoomCounter == 0:
                            if fingers1 == [0,1,1,0,0] and VolumeCounter == 0:
                                framecounter_volume = 0
                                VolumeCounter = 1
                            if fingers1 == [0,0,0,0,0] and (VolumeCounter == 1 or VolumeCounter == 2):
                                framecounter_volume += 1
                                if framecounter_volume >= 10:
                                    VolumeCounter = 0
                                else:
                                    VolumeCounter = 2
                            if fingers1 == [0,1,1,0,0] and VolumeCounter == 2:
                                VolumeCounter = 3
                            if (VolumeCounter == 1 or VolumeCounter == 2):
                                cv2.putText(img, f'Adjust volume?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                        else:
                            framecounter_volume += 1
                            if framecounter_volume >= 10:
                                framecounter_volume = 0
                                VolumeCounter = 0
                        if VolumeCounter == 3:
                            framecounter_volume = 0
                            cv2.rectangle(img, (20, 40), (50, 160), (255, 0, 0), 3)
                            cv2.circle(img, (p_8[0], p_8[1]), 10, (0, 255, 0), cv2.FILLED)
                            if fingers1 == [0, 1, 1, 0, 0] or fingers1 == [1, 1, 1, 0, 0]:
                                if initial_y_8 == 0:
                                    initial_y_8 = p_8[1]
                                if length_0_12 == 0:    
                                    length_0_12 = p_0[1] - p_12[1]
                                botbarvalue_volume = int(initial_y_8 + ((1.25)*length_5_17))
                                topbarvalue_volume = int(initial_y_8 - ((1.25)*length_5_17))
                                if topbarvalue_volume < 20:
                                    topbarvalue_volume = 20
                                    botbarvalue_volume = 20 + int(2.5*length_5_17)
                                if botbarvalue_volume > cam_height - length_0_12 - 20:
                                    botbarvalue_volume = int(cam_height - length_0_12 - 20)
                                    topbarvalue_volume = botbarvalue_volume - int(2.5*length_5_17)
                                if topbarvalue_volume < 20 and botbarvalue_volume > cam_height - length_0_12 - 20:
                                    topbarvalue_volume = 20
                                    botbarvalue_volume = int(cam_height - length_0_12 - 20)
                                volper = np.interp(p_8[1], [topbarvalue_volume, botbarvalue_volume], [100, 0])
                                volper = 10*round(volper/10)
                                volbar = int(np.interp(p_8[1], [topbarvalue_volume, botbarvalue_volume], [40, 160]))
                                volbar = (round((volbar-40)/12)*12)+40
                                cv2.putText(img, f'{int(volper)}%', (15, 180), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                                if fingers1 == [1, 1, 1, 0, 0]:
                                    volume.SetMasterVolumeLevelScalar(volper/100, None)
                                    cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)

                            if fingers1 == [0, 1, 0, 0, 0] or fingers1 == [1, 1, 0, 0, 0]:
                                if volper >= 100:
                                    volper = 90
                                volper_10 = np.interp(p_8[1], [topbarvalue_volume, botbarvalue_volume], [volper+9, volper])
                                volbar = int(160-(volper_10*1.2))
                                cv2.putText(img, f'{int(volper_10)}%', (15, 180), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                                if fingers1 == [1, 1, 0, 0, 0]:
                                    volume.SetMasterVolumeLevelScalar(volper_10/100, None)
                                    cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)
                                if p_8[1] > botbarvalue_volume:
                                    cv2.rectangle(img, (20, int(160-((volper)*1.2))), (50, 160), (255, 0, 0), cv2.FILLED)
                            if p_8[1] <= botbarvalue_volume:
                                cv2.rectangle(img, (20, volbar), (50, 160), (255, 0, 0), cv2.FILLED)
                        if fingers1 == [0,0,0,0,0] and VolumeCounter == 3:
                            VolumeCounter = 4
                        if fingers1 == [0,1,1,0,0] and VolumeCounter == 4:
                            VolumeCounter = 0

                        # change speed control
                        if movedetector:
                            framecounter = framecounter + 1
                            if forwardcounter < 2 or backwardcounter < 2:
                                if framecounter >= 10:
                                    framecounter = 0
                                    movedetector = False
                            if forwardcounter == 2 or backwardcounter == 2:
                                if framecounter >= 5:
                                    framecounter = 0
                                    movedetector = False
                            if forwardcounter == 3 or backwardcounter == 3 or forwardcounter == 4 or backwardcounter == 4:
                                if framecounter >= 2:
                                    framecounter = 0
                                    movedetector = False
                            if forwardcounter > 4 or backwardcounter > 4:
                                if framecounter >= 1:
                                    framecounter = 0
                                    movedetector = False

                        # remote point
                        if fingers1 == [1,1,1,1,1] and ZoomCounter == 0:
                            remote_hand = True
                        else:
                            remote_hand = False
                        if remote_hand is True and zoom_frame is False:
                            if initial_p_0 == []:
                                initial_p_0 = p_0
                            if initial_p_9 == []:
                                initial_p_9 = p_9
                            if length_5_17 == 0:
                                length_5_17 = math.hypot(p_5[0] - p_17[0], p_5[1] - p_17[1])

                            initial_mdpt = [(initial_p_0[0] + initial_p_9[0]) // 2, (initial_p_0[1] + initial_p_9[1]) // 2]
                            mdpt = [(p_0[0] + p_9[0]) // 2, (p_0[1] + p_9[1]) // 2]

                            x_midpt_range = [int(initial_mdpt[0]-(2*length_5_17)), int(initial_mdpt[0]+(2*length_5_17))]
                            x_diff = x_midpt_range[1] - x_midpt_range[0]
                            y_diff = int(currentimg_ratio*x_diff)  
                            y_midpt_range = [int(initial_mdpt[1]-(y_diff/2)), int(initial_mdpt[1]+(y_diff/2))]

                            if x_midpt_range[0] < 20:     
                                x_midpt_range = [20, 20 + x_diff]
                            if x_midpt_range[1] > cam_width - 20:
                                x_midpt_range = [cam_width - 20 - x_diff, cam_width - 20]     
                            if x_midpt_range[0] <= 20 and x_midpt_range[1] >= cam_width - 20:
                                x_midpt_range = [20, cam_width - 20]
                            if y_midpt_range[0] < 20:     
                                y_midpt_range = [20, 20 + y_diff]
                            if y_midpt_range[1] > cam_height - 20:
                                y_midpt_range = [cam_height - 20 - y_diff, cam_height - 20]
                            if y_midpt_range[0] <= 20 and y_midpt_range[1] >= cam_height - 20:
                                y_midpt_range = [20, cam_height - 20]

                            cx = int(np.interp(mdpt[0], [x_midpt_range[0], x_midpt_range[1]], [slide_width, 0]))
                            cy = int(np.interp(mdpt[1], [y_midpt_range[0], y_midpt_range[1]], [0, slide_height]))

                            if cx == slide_width:
                                cx = slide_width
                            if cy == slide_height:
                                cy = slide_height

                        # display
                        if ZoomCounter == 0 and fingers1 == [1,1,1,1,1]:
                            cv2.rectangle(img, (x_midpt_range[0], y_midpt_range[0]), (x_midpt_range[1], y_midpt_range[1]), (0, 0, 255), 3)
                            cv2.circle(currentimg, (cx, cy), 20, (0, 0, 255), cv2.FILLED)
                            cv2.circle(img, (mdpt[0], mdpt[1]), 10, (0, 0, 255), cv2.FILLED)
                        cv2.putText(currentimg, f'{int(imagenumber+1)}', (40, 40), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 3)                
                        cv2.imshow("Slide", currentimg)
                        # deactivator
                        if (fingers1 == [0,1,1,1,0] or fingers1 == [0,0,0,0,0]) and VolumeCounter == 0 and ZoomCounter == 0:
                            if (fingers1 == [0,1,1,1,0] or fingers1 == [1,1,1,1,0]) and SlidesControlCounter == 0:
                                framecounter_deactivator = 0
                                SlidesControlCounter = 1
                            if (fingers1 == [0,0,0,0,0]) and (SlidesControlCounter == 1 or SlidesControlCounter == 2):
                                framecounter_deactivator += 1
                                if framecounter_deactivator >= 10:
                                    SlidesControlCounter = 0
                                else:
                                    SlidesControlCounter = 2
                            if (fingers1 == [0,1,1,1,0]) and SlidesControlCounter == 2:
                                cv2.destroyWindow("Slide")
                                imagenumber = 0
                                length_5_17 = 0                
                                SlidesControlCounter = 0
                                SlidesControl = False
                                main_function = True
                            if SlidesControlCounter >= 1:
                                cv2.putText(img, f'End Slide Presentation?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                        else:
                            framecounter_deactivator += 1
                            if framecounter_deactivator >= 10:
                                framecounter_deactivator = 0
                                SlidesControlCounter = 0
                # Media function
                if MediaControl is True and ZoomandRotateControl is False and VolumeControl is False and SlidesControl is False:
                    if video_playing is False:
                        media.play()
                        video_playing = True
                    # display video progress bar and pause
                    video_duration_percentage = media.get_position()
                    timebar = int(np.interp([video_duration_percentage], [0, 1], [60, cam_width-60]))
                    cv2.rectangle(img, (60, cam_height-50), (cam_width-60, cam_height-20), (255, 0, 0), 3)
                    cv2.rectangle(img, (60, cam_height-50), (timebar, cam_height-20), (255, 0, 0), cv2.FILLED)
                    if video_paused:
                        cv2.rectangle(img, (cam_width-36, 32), (cam_width-24, 52), (255, 0, 0), cv2.FILLED)
                        cv2.rectangle(img, (cam_width-52, 32), (cam_width-40, 52), (255, 0, 0), cv2.FILLED)
                    if length_5_17 == 0:
                        length_5_17 = math.hypot(p_5[0] - p_17[0], p_5[1] - p_17[1])
                    if abs(p_9[0]-p_0[0]) < 0.05:
                        slope_0_9 = 1000000
                    else:
                        slope_0_9 = (p_9[1]-p_0[1])/(p_9[0]-p_0[0])

                    if ((hand1_type == "Right" and (p_5[0] > p_17[0])) or (hand1_type == "Left" and (p_5[0] < p_17[0]))):
                        # prevent overlapping gestures:
                        if general_counter > 0:
                            general_counter -= 1 
                        if fingers1 == [0,0,0,0,0]:
                            general_counter = 10

                        # pause/resume video
                        if fingers1 == [1,1,1,1,1] and pause_counter == 0 and ZoomCounter == 0:
                            media.pause()
                            general_counter = 10
                            if video_paused is False:
                                video_paused = True              
                            else:
                                video_paused = False
                            pause_counter = 10
                        if pause_counter > 0:
                            pause_counter -= 1

                        # rewind/advance video  
                        video_duration = media.get_length()
                        currrent_video_time = media.get_time()  
                        if (fingers1 == [1,0,0,0,0] and hand1_type == "Right") or (fingers1 == [0,0,0,0,1] and hand1_type == "Left") and pause_counter == 0 and general_counter == 0 and ZoomCounter == 0:
                            if hand1_type == "Right":
                                cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)
                            else:
                                cv2.circle(img, (p_20[0], p_20[1]), 10, (0, 255, 0), cv2.FILLED)
                            if frame_change is False:
                                frame_change = True
                                if currrent_video_time < 5000:
                                    currrent_video_time = 0
                                else:
                                    currrent_video_time -= 5000
                                media.set_time(currrent_video_time)
                                backwardcounter += 1
                        else:
                            backwardcounter = 0
                        if (fingers1 == [0,0,0,0,1] and hand1_type == "Right") or (fingers1 == [1,0,0,0,0] and hand1_type == "Left") and pause_counter == 0 and general_counter == 0 and ZoomCounter == 0:
                            if hand1_type == "Right":
                                cv2.circle(img, (p_20[0], p_20[1]), 10, (0, 255, 0), cv2.FILLED)
                            else:
                                cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)
                            if frame_change is False:
                                frame_change = True
                                if currrent_video_time > video_duration-5000:
                                    currrent_video_time = video_duration-1
                                else:
                                    currrent_video_time += 5000
                                media.set_time(currrent_video_time)
                                forwardcounter += 1
                        else:
                            forwardcounter = 0

                        # speed of rewind/advance
                        if frame_change:
                            framecounter_skip = framecounter_skip + 1
                            if forwardcounter < 2 or backwardcounter < 2:
                                if framecounter_skip >= 10:
                                    framecounter_skip = 0
                                    frame_change = False
                            if forwardcounter == 2 or backwardcounter == 2:
                                if framecounter_skip >= 5:
                                    framecounter_skip = 0
                                    frame_change = False
                            if forwardcounter == 3 or backwardcounter == 3 or forwardcounter == 4 or backwardcounter == 4:
                                if framecounter_skip >= 2:
                                    framecounter_skip = 0
                                    frame_change = False
                            if forwardcounter > 4 or backwardcounter > 4:
                                if framecounter_skip >= 1:
                                    framecounter_skip = 0
                                    frame_change = False

                        # zoom frame
                        if (fingers1 == [0,1,0,0,0] or fingers1 == [0,0,0,0,0]) and MediaControlCounter == 0 and RateChangeCounter == 0 and VolumeCounter == 0 and video_paused:
                            if fingers1 == [0,1,0,0,0] and ZoomCounter == 0:
                                framecounter_zoom = 0
                                ZoomCounter = 1
                            if fingers1 == [0,0,0,0,0] and (ZoomCounter == 1 or ZoomCounter == 2):
                                framecounter_zoom += 1
                                if framecounter_zoom >= 10:
                                    ZoomCounter = 0
                                else:
                                    ZoomCounter = 2
                            if fingers1 == [0,1,0,0,0] and ZoomCounter == 2:
                                ZoomCounter = 3           
                            if ZoomCounter == 1 or ZoomCounter == 2:
                                cv2.putText(img, f'Zoom video frame?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                        else:
                            framecounter_zoom += 1
                            if framecounter_zoom >= 10:
                                framecounter_zoom = 0
                                ZoomCounter = 0
                        deact_ratio = length_0_8/length_5_17
                        frame_time = media.get_time()
                        if ZoomCounter == 3:
                            if zoom_frame is False:
                                video.set(cv2.CAP_PROP_POS_MSEC,frame_time)
                                ret, video_frame = video.read()
                                zoom_frame = True
                            framecounter_zoom = 0
                            zoom_img = video_frame
                            if initial_p_0 == []:
                                initial_p_0 = p_0
                            if initial_p_9 == []:
                                initial_p_9 = p_9
                            length_16_4 = math.hypot(p_16[0] - p_4[0], p_16[1] - p_4[1])
                            length_0_12 = math.hypot(p_0[0] - p_12[0], p_0[1] - p_12[1])
                            length_0_20 = math.hypot(p_0[0] - p_20[0], p_0[1] - p_20[1])
                            cv2.line(img, (p_16[0], p_16[1]), (p_4[0], p_4[1]), (0, 255, 0), 5)
                            initial_mdpt = [(initial_p_0[0] + initial_p_9[0]) // 2, (initial_p_0[1] + initial_p_9[1]) // 2]
                            mdpt = [(p_0[0] + p_9[0]) // 2, (p_0[1] + p_9[1]) // 2]
                            # lock zoom
                            lz_ratio = length_0_20/length_5_17
                            if lz_ratio > 2:
                                pinky_raised = True
                            else:
                                pinky_raised = False
                            # zoom percentage
                            if pinky_raised is False:
                                normalizer = length_16_4/length_5_17
                                zoomper = np.interp(normalizer, [0.5, 3], [100, 600])
                                if zoomper % 50 != 0:
                                    zoomper = zoomper - (zoomper%50)
                                zoomper = zoomper/100
                            # resize
                            height = zoom_img.shape[0]
                            width = zoom_img.shape[1]
                            new_height = int(height/2)
                            new_width = int(width/2)
                            zoom_img = cv2.resize(zoom_img, (new_width, new_height))
                            hypothenuse = int(math.hypot(new_width, new_height))
                            border_height = int((hypothenuse-new_height)/2)
                            border_width = int((hypothenuse-new_width)/2)
                            zoom_img = cv2.copyMakeBorder(zoom_img, border_height, border_height, border_width, border_width, cv2.BORDER_CONSTANT, 0)
                            # center point
                            x_midpt_range = [int(initial_mdpt[0]-(2*length_5_17)), int(initial_mdpt[0]+(2*length_5_17))]
                            y_midpt_range = [int(initial_mdpt[1]-(2*length_5_17)), int(initial_mdpt[1]+(2*length_5_17))]
                            x_diff = x_midpt_range[1] - x_midpt_range[0]
                            y_diff = y_midpt_range[1] - y_midpt_range[0]
                            if x_midpt_range[0] < 20:     
                                x_midpt_range = [20, 20 + x_diff]
                            if x_midpt_range[1] > cam_width - 20:
                                x_midpt_range = [cam_width - 20 - x_diff, cam_width - 20]          
                            if x_midpt_range[0] <= 20 and x_midpt_range[1] >= cam_width - 20:
                                x_midpt_range = [20, cam_width - 20]
                            if y_midpt_range[0] < 20:     
                                y_midpt_range = [20, 20 + y_diff]
                            if y_midpt_range[1] > cam_height - 20:
                                y_midpt_range = [cam_height - 20 - y_diff, cam_height - 20]
                            if y_midpt_range[0] <= 20 and y_midpt_range[1] >= cam_height - 20:
                                y_midpt_range = [20, cam_height - 20]
                            cx = int(np.interp(mdpt[0], [x_midpt_range[0], x_midpt_range[1]], [hypothenuse, 0]))
                            cy = int(np.interp(mdpt[1], [y_midpt_range[0], y_midpt_range[1]], [0, hypothenuse]))     
                            # lock center point
                            lcp_ratio = length_0_12/length_5_17
                            if lcp_ratio > 1.5:
                                middle_raised = True
                            else:
                                middle_raised = False
                            if middle_raised is False:
                                if cx % 20 != 0:
                                    stab_cx = cx - (cx%20)
                                if cy % 20 != 0:
                                    stab_cy = cy - (cy%20)
                                if cx == hypothenuse:
                                    stab_cx = hypothenuse
                                if cy == hypothenuse:
                                    stab_cy = hypothenuse
                            # angle
                            angle = math.atan(slope_0_9)
                            angle = math.degrees(angle)
                            if (p_0[0] < p_9[0]):
                                angle = angle + 180
                            if initial_angle == 0:
                                initial_angle = angle
                            angle = int(angle - initial_angle)
                            if angle % 30 != 0:
                                angle = angle - (angle%30)            
                            # display
                            cv2.rectangle(img, (x_midpt_range[0], y_midpt_range[0]), (x_midpt_range[1], y_midpt_range[1]), (0, 255, 0), 3)
                            cv2.circle(zoom_img, (stab_cx, stab_cy), 5, (255, 0, 0), cv2.FILLED)
                            cv2.circle(img, (mdpt[0], mdpt[1]), 10, (255, 0, 0), cv2.FILLED)
                            #zoom and rotate
                            if middle_raised is True and pinky_raised is False:
                                cv2.putText(img, f'{int(zoomper*100)}%', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                                rotate_matrix = cv2.getRotationMatrix2D((stab_cx, stab_cy), 0, scale=zoomper)
                                zoom_img = cv2.warpAffine(zoom_img, rotate_matrix, (hypothenuse, hypothenuse))    
                            if middle_raised is True and pinky_raised is True:
                                rotate_matrix = cv2.getRotationMatrix2D((stab_cx, stab_cy), 0, scale=zoomper)
                                zoom_img = cv2.warpAffine(zoom_img, rotate_matrix, (hypothenuse, hypothenuse))
                                rotate_matrix = cv2.getRotationMatrix2D((hypothenuse//2, hypothenuse//2), angle, scale=1)
                                zoom_img = cv2.warpAffine(zoom_img, rotate_matrix, (hypothenuse, hypothenuse))
                            cv2.imshow("Video Frame", zoom_img)
                        if deact_ratio < 1.5 and ZoomCounter == 3:
                            ZoomCounter = 4
                        if deact_ratio > 2 and ZoomCounter == 4:
                            zoom_frame = False
                            cv2.destroyWindow("Video Frame")
                            ZoomCounter = 0
                            initial_mdpt = []
                            initial_p_0 = []
                            initial_p_9 = []
                            length_5_17 = 0

                        # change volume
                        if (fingers1 == [0,1,1,0,0] or fingers1 == [0,0,0,0,0] or fingers1 == [1,1,1,0,0]) and MediaControlCounter == 0 and RateChangeCounter == 0 and ZoomCounter == 0:
                            if fingers1 == [0,1,1,0,0] and VolumeCounter == 0:
                                framecounter_volume = 0
                                VolumeCounter = 1
                            if fingers1 == [0,0,0,0,0] and (VolumeCounter == 1 or VolumeCounter == 2):
                                framecounter_volume += 1
                                if framecounter_volume >= 10:
                                    VolumeCounter = 0
                                else:
                                    VolumeCounter = 2
                            if fingers1 == [0,1,1,0,0] and VolumeCounter == 2:
                                VolumeCounter = 3
                            if (VolumeCounter == 1 or VolumeCounter == 2):
                                cv2.putText(img, f'Adjust volume?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                        else:
                            framecounter_volume += 1
                            if framecounter_volume >= 20:
                                framecounter_volume = 0
                                VolumeCounter = 0
                        if VolumeCounter == 3:
                            framecounter_volume = 0
                            cv2.rectangle(img, (20, 40), (50, 160), (255, 0, 0), 3)
                            cv2.circle(img, (p_8[0], p_8[1]), 10, (0, 255, 0), cv2.FILLED)
                            if fingers1 == [0, 1, 1, 0, 0] or fingers1 == [1, 1, 1, 0, 0]:
                                if initial_y_8 == 0:
                                    initial_y_8 = p_8[1]
                                if length_0_12 == 0:    
                                    length_0_12 = p_0[1] - p_12[1]
                                botbarvalue_volume = int(initial_y_8 + ((1.25)*length_5_17))
                                topbarvalue_volume = int(initial_y_8 - ((1.25)*length_5_17))
                                if topbarvalue_volume < 20:
                                    topbarvalue_volume = 20
                                    botbarvalue_volume = 20 + int(2.5*length_5_17)
                                if botbarvalue_volume > cam_height - length_0_12 - 20:
                                    botbarvalue_volume = int(cam_height - length_0_12 - 20)
                                    topbarvalue_volume = botbarvalue_volume - int(2.5*length_5_17)
                                if topbarvalue_volume < 20 and botbarvalue_volume > cam_height - length_0_12 - 20:
                                    topbarvalue_volume = 20
                                    botbarvalue_volume = int(cam_height - length_0_12 - 20)
                                volper = np.interp(p_8[1], [topbarvalue_volume, botbarvalue_volume], [100, 0])
                                volper = 10*round(volper/10)
                                volbar = int(np.interp(p_8[1], [topbarvalue_volume, botbarvalue_volume], [40, 160]))
                                volbar = (round((volbar-40)/12)*12)+40
                                cv2.putText(img, f'{int(volper)}%', (15, 180), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                                if fingers1 == [1, 1, 1, 0, 0]:
                                    volume.SetMasterVolumeLevelScalar(volper/100, None)
                                    cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)

                            if fingers1 == [0, 1, 0, 0, 0] or fingers1 == [1, 1, 0, 0, 0]:
                                if volper >= 100:
                                    volper = 90
                                volper_10 = np.interp(p_8[1], [topbarvalue_volume, botbarvalue_volume], [volper+9, volper])
                                volbar = int(160-(volper_10*1.2))
                                cv2.putText(img, f'{int(volper_10)}%', (15, 180), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                                if fingers1 == [1, 1, 0, 0, 0]:
                                    volume.SetMasterVolumeLevelScalar(volper_10/100, None)
                                    cv2.circle(img, (p_4[0], p_4[1]), 10, (0, 255, 0), cv2.FILLED)
                                if p_8[1] > botbarvalue_volume:
                                    cv2.rectangle(img, (20, int(160-((volper)*1.2))), (50, 160), (255, 0, 0), cv2.FILLED)
                            if p_8[1] <= botbarvalue_volume:
                                cv2.rectangle(img, (20, volbar), (50, 160), (255, 0, 0), cv2.FILLED)
                        if fingers1 == [0,0,0,0,0] and VolumeCounter == 3:
                            VolumeCounter = 4
                        if fingers1 == [0,1,1,0,0] and VolumeCounter == 4:
                            initial_y_8 = 0
                            length_5_17 = 0
                            VolumeCounter = 0

                        # change frame rate
                        if (fingers1 == [0,1,1,1,0] or fingers1 == [0,0,0,0,0] or fingers1 == [1,1,1,1,0]) and MediaControlCounter == 0 and VolumeCounter == 0 and ZoomCounter == 0:
                            if fingers1 == [0,1,1,1,0] and RateChangeCounter == 0:
                                framecounter_rate = 0
                                RateChangeCounter = 1
                            if fingers1 == [0,0,0,0,0] and (RateChangeCounter == 1 or RateChangeCounter == 2):
                                framecounter_rate += 1
                                if framecounter_rate >= 10:
                                    RateChangeCounter = 0
                                else:
                                    RateChangeCounter = 2
                            if (fingers1 == [1,1,1,1,0] or fingers1 == [0,1,1,1,0]) and RateChangeCounter == 2 or RateChangeCounter == 3:
                                RateChangeCounter = 3
                                framecounter_rate = 0
                                if fingers1 == [0,1,1,1,0]:
                                    if length_0_12 == 0:    
                                        length_0_12 = p_0[1] - p_12[1]
                                    if initial_y_16 == 0:
                                        initial_y_16 = p_16[1]
                                    botbarvalue_rate = int(initial_y_16 + ((1.5)*length_5_17))
                                    topbarvalue_rate = int(initial_y_16 - ((1.5)*length_5_17))
                                    if topbarvalue_rate < 20:
                                        topbarvalue_rate = 20
                                        botbarvalue_rate = 20 + int(3*length_5_17)
                                    if botbarvalue_rate > cam_height - length_0_12 - 20:
                                        botbarvalue_rate = int(cam_height - length_0_12 - 20) 
                                        topbarvalue_rate = botbarvalue_rate - int(2.5*length_5_17)
                                    if topbarvalue_rate < 20 and botbarvalue_rate > cam_height - length_0_12 - 20:
                                        topbarvalue_rate = 20
                                        botbarvalue_rate = int(cam_height - length_0_12 - 20)
                                    rate_unscaled = np.interp(p_16[1], [topbarvalue_rate, botbarvalue_rate], [6, 0])
                                    if rate_unscaled < 1:
                                        rate = 0.25
                                    elif rate_unscaled >= 1 and rate_unscaled < 2:
                                        rate = 0.5
                                    elif rate_unscaled >= 2 and rate_unscaled < 3:
                                        rate = 1
                                    elif rate_unscaled >= 3 and rate_unscaled < 4:
                                        rate = 2
                                    else:
                                        rate = 4
                                if fingers1 == [1,1,1,1,0]:
                                    media.set_rate(rate)
                                cv2.putText(img, f'Adjusting video speed', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                                cv2.putText(img, f'x{float(rate)}', (10, 60), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                            if fingers1 == [0,0,0,0,0] and RateChangeCounter == 3:
                                RateChangeCounter = 4
                            if fingers1 == [0,1,1,1,0] and RateChangeCounter == 4:
                                RateChangeCounter = 0
                                length_5_17 = 0
                                initial_y_16 = 0
                            if RateChangeCounter == 1 or RateChangeCounter == 2:
                                cv2.putText(frame_hands, f'Adjust video speed?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                        else:
                            framecounter_rate += 1
                            if framecounter_rate >= 10:
                                framecounter_rate = 0
                                RateChangeCounter = 0

                        # deactivator
                        if (fingers1 == [0,1,1,1,1] or fingers1 == [0,0,0,0,0]) and RateChangeCounter == 0 and VolumeCounter == 0 and ZoomCounter == 0:
                            if fingers1 == [0,1,1,1,1] and MediaControlCounter == 0:
                                framecounter_deactivator = 0
                                MediaControlCounter = 1
                            if fingers1 == [0,0,0,0,0] and (MediaControlCounter == 1 or MediaControlCounter == 2):
                                framecounter_deactivator += 1
                                if framecounter_deactivator >= 10:
                                    MediaControlCounter = 0
                                else:
                                    MediaControlCounter = 2
                            if fingers1 == [0,1,1,1,1] and MediaControlCounter == 2:
                                media.stop()
                                length_5_17 = 0
                                MediaControl = False
                                MediaControlCounter = 0
                                main_function = True
                                video_playing = False
                            if MediaControlCounter >= 1:
                                cv2.putText(frame_hands, f'Turn off media player?', (10, 30), cv2.FONT_HERSHEY_COMPLEX, 0.6, (255, 0, 0), 2)
                        else:
                            framecounter_deactivator += 1
                            if framecounter_deactivator >= 10:
                                framecounter_deactivator = 0
                                MediaControlCounter = 0



            else:
                framecounter_activator = 0
                ZoomandRotateControlCounter = 0
                VolumeControlCounter = 0
                SlidesControlCounter = 0
                MediaControlCounter = 0
                height, width, channels = 100, 100, 3
                if show_sliwin:
                    frame_hands = frame[rois[index_hands][0][1]:rois[index_hands][1][1], rois[index_hands][0][0]:rois[index_hands][1][0]]
                else:
                    frame_hands = cv2.imread("HANDCAM.jpg")

                index_hands += 1
                if index_hands == 5:
                    index_hands = 0

            for i, roi in enumerate(rois):  # Use enumerate to get both index and value
                #print(i)
                roi_top_left, roi_bottom_right = roi
                #print(roi)
                threads[i] = threading.Thread(target=process_roi, args=(roi_top_left, roi_bottom_right, i))
                threads[i].start()
                
                #print("xmax {}".format(x_max_thread))
            for thread in threads:
                thread.join()
            
            # Display FPS
            curr_time = time.time()
            fps = int (1 / (curr_time - prev_time))
            prev_time = curr_time
            if show_fps:
                cv2.putText(frame, f"FPS: {fps:.2f}", (30, 30), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 255, 0), 1)
    
            if ignore:
                start_point = (point_1, 0)
                end_point = (point_1, frame_height)
                frame = cv2.line(frame, start_point, end_point, (105, 105, 105) , thickness)
                if proceed:
                    frame1_i = frame[0:frame_height, 0:abs(point_1-int(round(thickness/2)))-2]
                    frame2_i = frame[0:frame_height, abs(point_1+int(round(thickness/2)))+2:frame_width]
                    frame = cv2.hconcat([frame1_i,frame2_i]) 
            
            if autoframe:
                if not no_face:
                    try:
                        frame =  frame[0:frame_height, margin_min:margin_max]
                    except:
                        pass
                else:
                    frame = frame[0:frame_height,0:frame_width] 
            #DEDICATED FOCUS
            if dedicated:
                if len(roi_with_faces) == 0:
                    conv = True

                elif len(roi_with_faces) == 1:
                    conv = False
                    frame = frame[roi_top_left_1[1]:roi_bottom_right_1[1], roi_top_left_1[0]:roi_bottom_right_1[0]]
                    frame = cv2.copyMakeBorder(frame, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                
                elif len(roi_with_faces) == 2:
                    conv = False
                    frame_1 = frame[roi_top_left_1[1]:roi_bottom_right_1[1], roi_top_left_1[0]:roi_bottom_right_1[0]]
                    frame_2 = frame[roi_top_left_2[1]:roi_bottom_right_2[1], roi_top_left_2[0]:roi_bottom_right_2[0]]

                    if roi_bottom_right_1[0] == roi_top_left_2[0]:
                        frame_1 = cv2.copyMakeBorder(frame_1, 1, 1, 1, 0, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                        frame_2 = cv2.copyMakeBorder(frame_2, 1, 1, 0, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                    else:
                        frame_1 = cv2.copyMakeBorder(frame_1, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                        frame_2 = cv2.copyMakeBorder(frame_2, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                    frame = cv2.hconcat([frame_1,frame_2]) 
                    
                elif len(roi_with_faces) == 3:
                    conv = False
                    frame_1 = frame[roi_top_left_1[1]:roi_bottom_right_1[1], roi_top_left_1[0]:roi_bottom_right_1[0]]
                    frame_2 = frame[roi_top_left_2[1]:roi_bottom_right_2[1], roi_top_left_2[0]:roi_bottom_right_2[0]]
                    
                    frame_3 = frame[roi_top_left_3[1]:roi_bottom_right_3[1], roi_top_left_3[0]:roi_bottom_right_3[0]]
                    
                    if roi_bottom_right_1[0] == roi_top_left_2[0]:
                        frame_1 = cv2.copyMakeBorder(frame_1, 1, 1, 1, 0, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                        frame_2 = cv2.copyMakeBorder(frame_2, 1, 1, 0, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                    else:
                        frame_1 = cv2.copyMakeBorder(frame_1, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                        frame_2 = cv2.copyMakeBorder(frame_2, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])

                    frame_top = cv2.hconcat([frame_1,frame_2]) 
                    pad = frame_top.shape[1] - frame_2.shape[1]
                    frame_bottom = cv2.copyMakeBorder(frame_3, 1, 1, pad//2, pad//2, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                    frame_bottom = cv2.resize(frame_bottom,(frame_top.shape[1],frame_bottom.shape[0]))
                    frame = cv2.vconcat([frame_top,frame_bottom])
                    
                elif len(roi_with_faces) == 4:
                    conv = False
                    roi_top_left_1, roi_bottom_right_1 = roi_with_faces[0]
                    roi_top_left_2, roi_bottom_right_2 = roi_with_faces[1]
                    roi_top_left_3, roi_bottom_right_3 = roi_with_faces[2]
                    roi_top_left_4, roi_bottom_right_4 = roi_with_faces[3]

                    frame_1 = frame[roi_top_left_1[1]:roi_bottom_right_1[1], roi_top_left_1[0]:roi_bottom_right_1[0]]
                    frame_2 = frame[roi_top_left_2[1]:roi_bottom_right_2[1], roi_top_left_2[0]:roi_bottom_right_2[0]]
                    frame_3 = frame[roi_top_left_3[1]:roi_bottom_right_3[1], roi_top_left_3[0]:roi_bottom_right_3[0]]
                    frame_4 = frame[roi_top_left_4[1]:roi_bottom_right_4[1], roi_top_left_4[0]:roi_bottom_right_4[0]]

                    if roi_bottom_right_1[0] == roi_top_left_2[0]:
                        frame_1 = cv2.copyMakeBorder(frame_1, 1, 1, 1, 0, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                        frame_2 = cv2.copyMakeBorder(frame_2, 1, 1, 0, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                    else:
                        frame_1 = cv2.copyMakeBorder(frame_1, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                        frame_2 = cv2.copyMakeBorder(frame_2, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])

                    if roi_bottom_right_3[0] == roi_top_left_4[0]:
                        frame_3 = cv2.copyMakeBorder(frame_3, 1, 1, 1, 0, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                        frame_4 = cv2.copyMakeBorder(frame_4, 1, 1, 0, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                    else:    
                        frame_3 = cv2.copyMakeBorder(frame_3, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                        frame_4 = cv2.copyMakeBorder(frame_4, 1, 1, 1, 1, cv2.BORDER_CONSTANT, None, value = [0,0,0])
                    
                    frame_top = cv2.hconcat([frame_1,frame_2]) 
                    frame_bottom = cv2.hconcat([frame_3,frame_4]) 
                        
                    aspect_ratio = frame_top.shape[1] / frame_bottom.shape[1]
                    height = int(frame_bottom.shape[0] * aspect_ratio)
                    frame_bottom = cv2.resize(frame_bottom,(frame_top.shape[1], height))
                    frame = cv2.vconcat([frame_top,frame_bottom]) 
                
                elif len(roi_with_faces) >= 5:
                    conv = True  
                        
                else:  
                    frame = frame[0:frame_height,0:frame_width] 
            else:
                frame = frame[0:frame_height,0:frame_width] 

            if flip:
                frame = cv2.flip(frame,1)

            if conv:
                top_x1 = 0
                top_x2 = frame.shape[1]//2

                bottom_x1 = frame.shape[1]//2
                bottom_x2 = frame.shape[1]

                frame_top = frame[0:frame.shape[0], top_x1:top_x2]
                frame_bottom = frame[0:frame.shape[0], bottom_x1:bottom_x2]
                frame_bottom = cv2.resize(frame_bottom, (frame_top.shape[1], frame_bottom.shape[0]))
                frame = np.vstack((frame_top, frame_bottom))
            
            if not manual:
                x_off_1 = 0
                x_off_2 = 0

            if manual:
                if manual_90:
                    frame_ratio = frame.shape[1]//4
                    x1 = 0+ x_off_1
                    x2 = frame_ratio + x_off_2

                elif manual_180:
                    frame_ratio = frame.shape[1]//2
                    x1 = 0 + x_off_1
                    x2 = frame_ratio + x_off_2 

                elif manual_270:
                    frame_ratio = frame.shape[1]*3//4 
                    x1 = 0 + x_off_1
                    x2 = frame_ratio + x_off_2

                else:
                    frame_ratio = frame.shape[1]
                    x1 = 0
                    x2 = frame_ratio
                
                frame = frame[0:frame.shape[1], x1:x2]
            

            # Emit signal with processed frame
            self.change_pixmap_signal.emit(frame)
            if frame_hands is not None:
                self.change_pixmap_signal_hands.emit(frame_hands)

            # Check for exit key
            if cv2.waitKey(1) == ord('x'):
                break

            

    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.wait()

class App(QWidget):
    change_pixmap_signal_hand = pyqtSignal(np.ndarray)

    def __init__(self):
        global arrow_btns,ignore_settings,ignore_settings2, manual_btn_set, ignore_coords
        super().__init__()
        self.setWindowIcon(QtGui.QIcon('hampter.jpg'))
        self.setWindowTitle("DSP Group 7")

        #self.ws = obsws('localhost', 4455, 'vjR1TdTQs4GsJAmz')
        #self.ws.connect()
        if not conv or not dedicated or not autoframe:
            self.disply_width = math.ceil(pano_width*1.17)
            self.display_height = math.ceil(pano_height*1.17)
        
        self.hand_width = math.ceil((pano_height//5)*1.5)
        self.hand_height = math.ceil(pano_height*1.5)
        # create the label that holds the image
        self.image_label = QLabel(self)
        self.image_label.resize(self.disply_width, self.display_height)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label_2 = QLabel(self)
        self.image_label_2.resize(self.hand_width, self.hand_height)

        self.image_label_2.setAlignment(Qt.AlignCenter)
        
        # create a text label
        self.settingsLabel = QLabel('Basic Settings')
        self.textLabel = QLabel('Video Modes')
        self.manuallabel = QLabel('Manual Modes')
        self.dynamiclabel = QLabel('Dynamic Modes')
        self.extendlabel = QLabel('Extend Background')

        font = QFont()
        font.setPointSize(12)
        font.setBold(True) 

        subfont = QFont()
        subfont.setPointSize(8)

        subpalette = QPalette()
        subpalette.setColor(QPalette.WindowText, QColor('darkGray'))

        palette = QPalette()
        palette.setColor(QPalette.WindowText, QColor('#5A5A5A'))

        self.textLabel.setPalette(palette)
        self.textLabel.setFont(font) 

        self.settingsLabel.setPalette(palette)
        self.settingsLabel.setFont(font)


        self.extendlabel.setPalette(palette)
        self.extendlabel.setFont(font) 


        self.manuallabel.setPalette(subpalette)
        self.dynamiclabel.setPalette(subpalette)

        self.manuallabel.setFont(subfont)
        self.dynamiclabel.setFont(subfont)

        self.manuallabel.setAlignment(Qt.AlignCenter)
        self.dynamiclabel.setAlignment(Qt.AlignCenter)

        

        self.flip_btn = QPushButton("Flip the Video", clicked=self.flip)
        self.conv_btn = QPushButton("Conversation", clicked=self.conversation)
        self.manual_btn = QPushButton("Manual", clicked=self.manual)
        self.ignore_btn = QPushButton("Ignore Zone", clicked=self.ignore)
        self.ded_btn = QPushButton("Dedicated Focus", clicked=self.dedf)
        self.auto_btn = QPushButton("Auto Framing", clicked=self.autof)
        self.extend_btn = QPushButton("Enable", clicked=self.outpainting)
        self.show_btn = QPushButton("Show Detection Splices", clicked=self.showsplice)
        self.fps_btn = QPushButton("Show FPS", clicked=self.showfps)
        self.sliding_btn = QPushButton("Show Sliding Window", clicked=self.showslidingwindow)
        self.bbox_btn = QPushButton("Show Face Boxes", clicked=self.showbbox)

        
        self.flip_btn.setFixedSize(QtCore.QSize(300, 25))
        self.conv_btn.setFixedSize(QtCore.QSize(300, 25))
        self.manual_btn.setFixedSize(QtCore.QSize(300, 25))
        self.ignore_btn.setFixedSize(QtCore.QSize(300, 25))
        self.auto_btn.setFixedSize(QtCore.QSize(300, 25))
        self.ded_btn.setFixedSize(QtCore.QSize(300, 25))
        self.auto_btn.setFixedSize(QtCore.QSize(300, 25))
        self.ded_btn.setFixedSize(QtCore.QSize(300, 25))
        self.extend_btn.setFixedSize(QtCore.QSize(300, 25))
        self.show_btn.setFixedSize(QtCore.QSize(300, 25))
        self.fps_btn.setFixedSize(QtCore.QSize(300, 25))
        self.sliding_btn.setFixedSize(QtCore.QSize(300, 25))
        self.bbox_btn.setFixedSize(QtCore.QSize(300, 25))

        ignore = QVBoxLayout()
        Vbox = QVBoxLayout()
        button_box = QVBoxLayout()
        button_box2 = QVBoxLayout()
        button_box3 = QVBoxLayout() #DITO MO LAGAY YUNG IMAGE
        setting_box = QHBoxLayout()
        manual_btn_set = QHBoxLayout()
        arrow_btns = QHBoxLayout()
        ignore_settings = QVBoxLayout()
        ignore_settings2 = QHBoxLayout()

        
        
        ignore.addWidget(self.image_label)
        button_box3.addWidget(self.image_label_2)
        ignore.addLayout(arrow_btns)
        ignore.addLayout(ignore_settings)
        ignore.addLayout(ignore_settings2)
        ignore_settings.setAlignment(Qt.AlignTop | Qt.AlignCenter)
        ignore.setAlignment(Qt.AlignCenter)
        Vbox.addLayout(ignore)
        button_box2.addWidget(self.settingsLabel)
        button_box2.addWidget(self.flip_btn)
        button_box2.addWidget(self.show_btn)
        button_box2.addWidget(self.fps_btn)
        button_box2.addWidget(self.sliding_btn)
        button_box2.addWidget(self.bbox_btn)
        button_box.addWidget(self.textLabel)
        button_box.addWidget(self.manuallabel)
        button_box.addWidget(self.conv_btn)
        button_box.addWidget(self.manual_btn)
        
        #if (ifhands==0): (no hands)
        self.playing_video_1 = False
        
        #end of ave addition
        # set the vbox layout as the widgets layout
        self.setLayout(Vbox)
        button_box.addLayout(manual_btn_set)

        button_box.addWidget(self.ignore_btn)
        button_box.addWidget(self.dynamiclabel)
        button_box.addWidget(self.ded_btn)
        button_box.addWidget(self.auto_btn)
        button_box2.addWidget(self.extendlabel)
        button_box2.addWidget(self.extend_btn)
        
        button_box.setAlignment(Qt.AlignTop | Qt.AlignCenter)
        button_box2.setAlignment(Qt.AlignTop | Qt.AlignCenter)
        button_box3.setAlignment(Qt.AlignTop | Qt.AlignCenter)
        setting_box.addLayout(button_box)
        setting_box.addLayout(button_box2)
        setting_box.addLayout(button_box3)
        
        Vbox.addLayout(setting_box)
        

        vid = "gui video.mp4"
        
        # create the video capture thread
        self.thread = VideoThread(vid)
        # connect its signal to the update_image slot
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.change_pixmap_signal_hands.connect(self.update_image_2)
        # start the thread
        self.thread.start()

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()


    @pyqtSlot()
    def showbbox(self):
        global show_bbox
        show_bbox = not show_bbox

    def showslidingwindow(self):
        global show_sliwin
        show_sliwin = not show_sliwin

    def showsplice(self):
        global show_splice
        show_splice = not show_splice
    
    def showfps(self):
        global show_fps
        show_fps = not show_fps

    def outpainting(self):
        global conv, manual, dedicated, autoframe, outpaint,ignore
        ignore = False
        dedicated = False
        manual = False
        autoframe = False
        conv = False
        outpaint = not outpaint
        print("outpaintin {}".format(outpaint))
        
        if outpaint:
            scenes = self.ws.call(requests.GetSceneList())
            # for s in scenes.getScenes():
            #     name = s['sceneName']
            #     print("\n name:"+name+"\n")
            self.ws.call(requests.SetCurrentProgramScene(sceneName='outpainted'))
    
            
            print(scenes)

            #self.ws.call(requests.SetCurrentScene("outpainted"))
        
        
        else:
            scenes = self.ws.call(requests.GetSceneList())
            print(scenes)
            self.ws.call(requests.SetCurrentProgramScene(sceneName='panorama'))
            #newScene = scenes[1]
            #self.ws.call(requests.SetCurrentScene("newScene["name"]"))



    def ignore(self):
        global ignore_settings, ignore, dedicated, manual, autoframe, conv, point_1, thickness
        dedicated = False
        manual = False
        autoframe = False
        conv = False
        ignore = not ignore
        
        if ignore:
            self.proc_btn = QPushButton("Ignore!", clicked=self.proceed)
            self.proc_btn.setFixedSize(QtCore.QSize(200, 20))
            
            self.sp = QSlider(Qt.Horizontal)
            self.sp.setMaximum(pano_width)
            self.sp.setMaximumWidth(pano_width)
            self.sp.valueChanged.connect(self.ignore_change)
            
            self.sp_thick = QSlider(Qt.Horizontal)
            self.sp_thick.setMaximum(pano_width)
            self.sp_thick.setMinimum(1)
            self.sp_thick.setMaximumWidth(pano_width//2)
            self.sp_thick.valueChanged.connect(self.ignore_change)
            
            ignore_settings.addWidget(self.sp)
            ignore_settings2.addWidget(self.sp_thick)
            ignore_settings2.addWidget(self.proc_btn)

            ignore_settings.addLayout(ignore_settings)
            
            

        if not ignore:
            self.sp.hide()
            self.sp_thick.hide()
            self.proc_btn.hide()

    def start_video_1(self):
        self.timer.start(30)  # Update frame every 30 milliseconds
        self.video_capture = self.video_capture_1

    def ignore_change(self):
        global point_1, thickness
        point_1 = int(round(self.sp.value()))
        thickness = int(round(self.sp_thick.value()))

    def proceed(self):
        global proceed
        proceed = not proceed
        
    def flip(self):
        global flip
        flip = not flip

    def conversation(self):
        global conv, manual, dedicated, autoframe
        
        conv = not conv
        dedicated = False
        manual = False
        autoframe = False
        if conv:
            self.disply_width = math.ceil((pano_width //2)*1.17)
            self.display_height = math.ceil((pano_height*2)*1.17)
        else:
            self.disply_width = math.ceil(pano_width*1.17)
            self.display_height = math.ceil(pano_height*1.17)
        manual = False
        print("Conversation is", conv)
    
    def dedf(self):
        global results, dedicated, conv, manual, autoframe,frame
        global display_width_ded, display_height_ded
        manual = False
        conv = False
        autoframe = False
        dedicated = not dedicated
        if dedicated:
            self.disply_width = frame.shape[1]*2
            self.display_height = frame.shape[0]*2
        else:
            self.disply_width = math.ceil(pano_width*1.17)
            self.display_height = math.ceil(pano_height*1.17)
        
        
    def autof(self):
        global dedicated, conv, manual, autoframe
        dedicated = False
        manual = False
        conv = False
        autoframe = not autoframe
        if autoframe:
            self.disply_width = frame.shape[1]
            self.display_height = frame.shape[0]
        else:
            self.disply_width = math.ceil(pano_width*1.17)
            self.display_height = math.ceil(pano_height*1.17)
    

    def manual(self):
        global manual, manual_btn_set, conv, dedicated,autoframe
        manual = not manual
        conv = False
        dedicated = False
        autoframe = False

        if manual:
            self.right_btn = QPushButton(">>", clicked=self.right_man)
            self.left_btn = QPushButton("<<", clicked=self.left_man)

            self.manual_btn_set_90 = QPushButton("90", clicked=self.man_90)
            self.manual_btn_set_180 = QPushButton("180", clicked=self.man_180)
            self.manual_btn_set_270 = QPushButton("270", clicked=self.man_270)
            self.manual_btn_set_360 = QPushButton("360", clicked=self.man_360)

            self.manual_btn_set_90.setFixedSize(QtCore.QSize(50, 20))
            self.manual_btn_set_180.setFixedSize(QtCore.QSize(50, 20))
            self.manual_btn_set_270.setFixedSize(QtCore.QSize(50, 20))
            self.manual_btn_set_360.setFixedSize(QtCore.QSize(50, 20))
            
            arrow_btns.addWidget(self.left_btn)
            arrow_btns.addWidget(self.right_btn)
            
            manual_btn_set.addWidget(self.manual_btn_set_90)
            manual_btn_set.addWidget(self.manual_btn_set_180)
            manual_btn_set.addWidget(self.manual_btn_set_270)
            manual_btn_set.addWidget(self.manual_btn_set_360)

        if not manual:
            self.manual_btn_set_90.hide()
            self.manual_btn_set_180.hide()
            self.manual_btn_set_270.hide()
            self.manual_btn_set_360.hide()
            self.right_btn.hide()
            self.left_btn.hide()
        print("Manual is", manual)
    
    def right_man(self):
        global x_off_1, x_off_2, frame_ratio, frame_width,x2
        if manual:
            if (x2) <= frame_width:
                x_off_1 += 5
                x_off_2 += 5
            else:
                return


    def left_man(self):
        global x_off_1, x_off_2, frame_ratio,x1
        if manual:
            if x1 > 0:
                x_off_1 -= 5
                x_off_2 -= 5
            elif (0+x_off_1) <0:
                return
   

    def man_90(self):
        global manual_90, manual_180, manual_270, manual_360
        manual_90 = not manual_90
        manual_180 = False
        manual_270 = False
        manual_360 = False

        print("Manual 90 is", manual_90)
    
    def man_180(self):
        global manual_90, manual_180, manual_270, manual_360
        manual_180 = not manual_180
        manual_90 = False
        manual_270 = False
        manual_360 = False
        print("Manual 180 is", manual_180)
    
    def man_270(self):
        global manual_90, manual_180, manual_270, manual_360
        manual_270 = not manual_270
        manual_90 = False
        manual_180 = False
        manual_360 = False
        print("Manual 270 is", manual_270)
    
    def man_360(self):
        global manual_90, manual_180, manual_270, manual_360
        manual_360 = not manual_360
        manual_90 = False
        manual_180 = False
        manual_270 = False
        print("Manual 360 is", manual_360)

    @pyqtSlot(np.ndarray)
    def update_image(self, frame):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(frame)
        self.image_label.setPixmap(qt_img)

    def update_image_2(self, frame_hands):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(frame_hands)
        #qt_img_flipped = qt_img.transformed(QTransform().scale(-1, 1))
        
        self.image_label_2.setPixmap(qt_img)
    
    def convert_cv_qt(self, frame):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.disply_width, self.display_height, Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)
    
if __name__=="__main__":
    
    app = QApplication(sys.argv)
    p2 = threading.Thread(target=VideoModes)
    p2.start()   
    print("started")
    a = App()

    
    a.show()
    sys.exit(app.exec_())