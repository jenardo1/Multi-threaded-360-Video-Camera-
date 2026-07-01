#########################################################################################
# Importing stuff

import cv2
import mediapipe as mp
from cvzone.HandTrackingModule import HandDetector
import numpy as np

from PIL import Image, ImageFilter, ImageDraw, ImageChops
from diffusers import StableDiffusionInpaintPipeline
import torch

import pyautogui
import os

import threading
import queue
import time
#########################################################################################
# Preliminary Stuff

# Pytorch exhausts the VRAM of GTX 1050 so forced to run on cpu
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Separate body from initial background
mp_selfie_segmentation = mp.solutions.selfie_segmentation
selfie_segmentation = mp_selfie_segmentation.SelfieSegmentation(model_selection = 1)

# Stable Diffusion to extend the chosen background image
pipe = StableDiffusionInpaintPipeline.from_pretrained("stabilityai/stable-diffusion-2-inpainting", variant = "fp16")

pipe.load_lora_weights("pytorch_lora_weights.safetensors")
pipe.fuse_lora(lora_scale = 1)

pipe = pipe.to("cpu")  # CPU/GPU (GTX 1050 with 3GB VRAM runs out of memory when running)
pipe.enable_attention_slicing() 

#########################################################################################
# Threading and queueing system for 

outpaint_queue = queue.Queue()
latest_outpainted = None
outpaint_lock = threading.Lock()

def outpaint_worker(output_size):
    global latest_outpainted
    while True:
        try:
            real_background = outpaint_queue.get(timeout = 1)
        except queue.Empty:
            continue

        try:
            outpainted_pil = outpaint_image(real_background, output_size, pipe)
            resized_pil = outpainted_pil.resize(output_size, resample=Image.Resampling.LANCZOS)
            background_outpainted = cv2.cvtColor(np.array(resized_pil), cv2.COLOR_RGB2BGR)

            with outpaint_lock:
                latest_outpainted = background_outpainted
        except Exception as e:
            print(f"[Thread] Error during outpainting: {e}")

#########################################################################################
# Outpaint background 

def outpaint_image(image, output_size, pipe):
    if isinstance(image, np.ndarray):
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
    elif isinstance(image, Image.Image):
        pil_image = image.convert("RGB")
    else:
        raise ValueError("Input not an image!")

    output_width, output_height = output_size
    frame3_width = 426
    frame3_height = output_height
    frame3_x = 852  # Frame 3 starts at pixel 852

    # Resize Frame 3 to fit expected height and width
    resized_frame3 = pil_image.resize((frame3_width, frame3_height), Image.Resampling.LANCZOS)

    # Set up the canvas
    canvas = Image.new("RGB", (output_width, output_height), (0, 0, 0))
    canvas.paste(resized_frame3, (frame3_x, 0))

    # Create a mask
    mask = Image.new("L", (output_width, output_height), 0)

    # Left region to inpaint: from 0 to 852
    mask.paste(255, (0, 0, frame3_x, output_height))

    # Right region to inpaint: from 1278 to 1704
    right_x = frame3_x + frame3_width
    mask.paste(255, (right_x, 0, output_width, output_height))

    # Optional: set seed for deterministic results
    # Good: 4151, 4214, 467
    # Bad: 4712
    generator = torch.manual_seed(467)

    try:
        result = pipe(
            prompt = "Pitch black background",
            negative_prompt = "blurry, overexposure, uneven lighting, color bleeding, text, distorted details, asymmetrical, multiple angles, multiple views, deformed objects",
            image = canvas,
            mask_image = mask,
            num_inference_steps = 15,
            generator=generator
        )
        outpainted_image = result.images[0]
    except Exception as e:
        print(f"Pipeline error: {e}")
        raise

    return outpainted_image

#########################################################################################
# Video Modes Gestures

def open_presentation(ppt_app, presentation_path, Presentation):
    if ppt_app and Presentation is None:
        ppt_app.Visible = True  # Show PowerPoint
        Presentation = ppt_app.Presentations.Open(presentation_path)

def enter_presenter_view():
    pyautogui.hotkey('shift', 'f5')  # Start Presenter Mode

def close_presentation(ppt_app, Presentation):
    if ppt_app and Presentation:
        Presentation.Close()
        Presentation = None

def next_slide():
    pyautogui.press("right")

def prev_slide():
    pyautogui.press("left")

#########################################################################################

def main():
    # Track FPS
    prev_time = time.time()

    # Image background testing (Not needed)
    background_path = "Background.JPG"
    background = cv2.imread(background_path)
    
    #####################################################################################

    # Windows-specific PowerPoint control
    try:
        import win32com.client
        import pywintypes
        ppt_app = win32com.client.Dispatch("PowerPoint.Application")
    except ImportError:
        ppt_app = None
        print("win32com is required for PowerPoint control on Windows. Install with 'pip install pywin32'.")

    # PowerPoint file path
    presentation_path = os.path.abspath("sampleslides.pptx")
    Presentation = None

    # Start camera for real time
    # cap = cv2.VideoCapture(0) # Comment if doing demo

    # Load videos for demo
    caps = [
    cv2.VideoCapture("frame 1 down.mp4"),
    cv2.VideoCapture("frame 4 down.mp4"),
    cv2.VideoCapture("frame 3.mp4"), # Host
    cv2.VideoCapture("frame 2 down.mp4") 
    ]

    #####################################################################################
    detector = HandDetector(detectionCon = 0.8, maxHands = 2)

    # Initialize MediaPipe Face Mesh
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh()
    face_tracking_active = False
    #####################################################################################

    cv2.namedWindow("Panoramic Output", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Panoramic Output", 1704, 240)

    # Comment if doing demo
    # if not cap.isOpened():
    #     print("Error: Could not open webcam.")
    #     return
    
    print("Press 'q' to quit.")
    
    # Temporarily adjust the output size to match StableDiffusion requirements (divisible by 8)
    output_size = (1704, 240) # Desired Resolution
    temp_width = (output_size[0] // 8) * 8
    temp_height = (output_size[1] // 8) * 8

    # Start thread
    outpaint_thread = threading.Thread(target = outpaint_worker, args  = ((temp_width, temp_height),), daemon = True)
    outpaint_thread.start()

    while True:
        # Real time (Comment if doing demo)
        # ret, frame = cap.read()
        # if not ret:
        #     break

        # Preload (Uncomment if doing demo)
        frames = []
        all_ret = True

        for cap in caps:
            ret, frame = cap.read()

            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Rewind to beginning
                ret, frame = cap.read()              # Try reading again
            
            if not ret:
                all_ret = False
                break  # Still failed after reset — stop processing this round
            else:
                frame = cv2.resize(frame, (426, 240))
                frames.append(frame)

        if not all_ret:
            continue  # Skip this iteration instead of breaking the whole loop
        
        # Timing
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time

        #####################################################################################
        # Comment if doing demo

        # # Keep frame size at (426, 240) so that four participants results in (4*426, 240) or (426, 240)        
        # frame = cv2.resize(frame, (426, 240)) 

        # # Build the panoramic frame (simulate 4 participants)
        # frame1 = cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV), cv2.COLOR_HSV2BGR)
        # frame2 = cv2.flip(frame, 1)
        # frame3 = frame.copy() # Host
        # frame4 = cv2.GaussianBlur(frame, (15, 15), 0)

        # frames = [frame1, frame2, frame3, frame4]

        masks = []
        alpha_masks = []

        for idx, f in enumerate(frames):
            if idx == 2:
                # Skip mask generation for frame 3 (host)
                masks.append(None)
                alpha_masks.append(None)
                continue

            f_rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            result = selfie_segmentation.process(f_rgb)

            # 1. Soft alpha mask (no thresholding)
            alpha = result.segmentation_mask  # Shape: (H, W), values in [0, 1]

            # 2. Smooth the alpha mask to reduce jagged edges
            alpha = cv2.GaussianBlur(alpha, (5, 5), 0)

            # 3. Hard binary mask
            hard_mask = (alpha > 0.5).astype(np.uint8) * 255

            masks.append(hard_mask)
            alpha_masks.append(alpha)

        # Handle background outpainting for frame3 (host)
        if outpaint_queue.empty():
            background = cv2.inpaint(frames[2], masks[2] if masks[2] is not None else np.zeros((240, 426), dtype=np.uint8), 3, cv2.INPAINT_TELEA)
            outpaint_queue.put(background)

        # Compose the panoramic output using latest outpainted background
        with outpaint_lock:
            background_ready = latest_outpainted is not None
            if background_ready:
                panoramic_bg = latest_outpainted.copy()
            else:
                panoramic_bg = np.hstack(frames)  # Fallback background

        composed = panoramic_bg.copy()
        for i in range(4):
            x_offset = i * 426
            if i == 0:
                # Frame 1: use masked background replacement
                if background_ready:
                    fg = cv2.bitwise_and(frames[0], frames[0], mask=masks[0])
                    roi = composed[0:240, x_offset:x_offset + 426]
                    bg = cv2.bitwise_and(roi, roi, mask=cv2.bitwise_not(masks[0]))
                    combined = cv2.add(bg, fg)
                    composed[0:240, x_offset:x_offset + 426] = combined
                else:
                    composed[0:240, x_offset:x_offset + 426] = frames[0]

            elif i == 2:
                # Frame 3: Paste as-is (host)
                composed[0:240, x_offset:x_offset + 426] = frames[i]

            else:
                # Other frames: blend using masks
                fg = cv2.bitwise_and(frames[i], frames[i], mask=masks[i])
                roi = composed[0:240, x_offset:x_offset + 426]
                bg = cv2.bitwise_and(roi, roi, mask=cv2.bitwise_not(masks[i]))
                combined = cv2.add(bg, fg)
                composed[0:240, x_offset:x_offset + 426] = combined

        #####################################################################################
        #Hand Tracking and Gestures
        hands, img = detector.findHands(composed)
        cv2.putText(img, f"FPS: {fps:.2f}", (10, 30), 
            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        if hands:
            for hand in hands:
                fingers = detector.fingersUp(hand)
                
                if fingers == [0, 0, 1, 1, 0]:
                    open_presentation(ppt_app, presentation_path, Presentation)
                    cv2.putText(img, 'Presentation Opened', (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                
                if fingers == [0, 0, 0, 1, 1]:
                    enter_presenter_view()
                    cv2.putText(img, 'Presenter View', (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
                
                if fingers == [1, 1, 1, 0, 0]:
                    close_presentation(ppt_app, Presentation)
                    cv2.putText(img, 'Presentation Closed', (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                
                if fingers == [1, 0, 0, 0, 1]:
                    prev_slide()
                    cv2.putText(img, 'Slide Left', (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                elif fingers == [0, 0, 0, 0, 1]:
                    next_slide()
                    cv2.putText(img, 'Slide Right', (10, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                if fingers == [0, 1, 0, 0, 1]:
                    face_tracking_active = True
                    cv2.putText(img, 'Face Tracking Activated', (10, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                
                if fingers == [0, 1, 1, 0, 1]:
                    face_tracking_active = False
                    cv2.putText(img, 'Face Tracking Stopped', (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
        
        if face_tracking_active:
            rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            result = face_mesh.process(rgb_image)
            
            if result.multi_face_landmarks:
                for facial_landmarks in result.multi_face_landmarks:
                    min_x, min_y, max_x, max_y = img.shape[1], img.shape[0], 0, 0
                    
                    for i in range(468):
                        pt1 = facial_landmarks.landmark[i]
                        x, y = int(pt1.x * img.shape[1]), int(pt1.y * img.shape[0])
                        min_x, min_y = min(min_x, x), min(min_y, y)
                        max_x, max_y = max(max_x, x), max(max_y, y)
                        cv2.circle(img, (x, y), 2, (0, 255, 0), -1)
                    
                    center_x, center_y = (min_x + max_x) // 2, (min_y + max_y) // 2
                    zoom_factor = 1.5
                    new_width = int(img.shape[1] / zoom_factor)
                    new_height = int(new_width / (img.shape[1] / img.shape[0]))
                    roi_x1, roi_y1 = max(center_x - new_width // 2, 0), max(center_y - new_height // 2, 0)
                    roi_x2, roi_y2 = min(center_x + new_width // 2, img.shape[1]), min(center_y + new_height // 2, img.shape[0])
                    zoomed_image = img[roi_y1:roi_y2, roi_x1:roi_x2]
                    zoomed_image_resized = cv2.resize(zoomed_image, (img.shape[1], img.shape[0]), interpolation = cv2.INTER_LINEAR)
                    #cv2.imshow("Zoomed Face", zoomed_image_resized)

        cv2.imshow("Panoramic Output", img)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Real time (Comment if doing demo)
    # cap.release()
    # Preload
    for cap in caps:
         cap.release()

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()