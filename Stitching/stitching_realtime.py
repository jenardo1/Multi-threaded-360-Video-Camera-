import pickle
import numpy as np
import cv2 as cv

with open('camera_params.pkl', 'rb') as f: #precomputed cam params 
    camera_data = pickle.load(f)

cameras = []
for data in camera_data:
    cam = cv.detail.CameraParams()
    cam.focal = data["focal"]
    cam.aspect = data["aspect"]
    cam.ppx = data["ppx"]
    cam.ppy = data["ppy"]
    cam.R = np.array(data["R"], dtype=np.float32)
    cam.t = np.array(data["t"], dtype=np.float32)
    cameras.append(cam)


NUM_CAMERAS = len(cameras)
cams = [cv.VideoCapture(i) for i in range(NUM_CAMERAS)]
print(NUM_CAMERAS)

for cam in cams: # ideal aspect ratio for stitching
    cam.set(cv.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv.CAP_PROP_FRAME_HEIGHT, 720)

warped_image_scale = cameras[0].focal
warper = cv.PyRotationWarper("cylindrical", warped_image_scale)
blender = cv.detail_MultiBandBlender()
blender.setNumBands(2) # smoother transition if more bands = lower fps

#blender = cv.detail_FeatherBlender()
#blender.setSharpness(0.02)

first_frame = True
masks_warped = []
corners = []
sizes = []
compensator = None
seam_finder = None

display_fps = 0
frame_counter = 0
widthscale = 0.85 # 1 0.78
fps_update_interval = 20

while True:

    t_start = cv.getTickCount()

    frames = []
    for cam in cams:
        ret, frame = cam.read()
        if not ret:
            print("Failed to capture from camera.")
            break

    # Resize the frame (to match the seams on the precomputed matrix) 0.33 if work megapix = 0.1
        resized_frame = cv.resize(frame, None, fx=widthscale*0.33, fy=0.33, interpolation=cv.INTER_LINEAR)
        frames.append(resized_frame)

    if len(frames) != NUM_CAMERAS:
        continue  # Skip this loop if any camera failed

    images_warped = []
    corners = []
    sizes = []

    for idx, frame in enumerate(frames):
        K = cameras[idx].K().astype(np.float32)
        corner, image_wp = warper.warp(frame, K, cameras[idx].R, cv.INTER_LINEAR, cv.BORDER_REFLECT)
        corners.append(corner)
        sizes.append((image_wp.shape[1], image_wp.shape[0]))
        images_warped.append(image_wp)

    if first_frame:
        masks_warped = [255 * np.ones((img.shape[0], img.shape[1]), np.uint8) for img in images_warped]
        compensator = cv.detail.ExposureCompensator_createDefault(cv.detail.ExposureCompensator_GAIN)
        compensator.feed(corners=corners, images=images_warped, masks=masks_warped)
        images_warped_f = [img.astype(np.float32) for img in images_warped]
        #seam_finder = cv.detail_DpSeamFinder('COLOR')  # faster than GraphCut
        seam_finder = cv.detail.GraphCutSeamFinder('COST_COLOR')
        masks_warped = seam_finder.find(images_warped_f, corners, masks_warped)
        first_frame = False
        result_roi = cv.detail.resultRoi(corners=corners, sizes=sizes)
    blender.prepare(result_roi)
    
    for idx in range(NUM_CAMERAS):
        mask = masks_warped[idx]
        compensator.apply(idx, corners[idx], images_warped[idx], mask)
        image_warped_s = images_warped[idx].astype(np.int16)
        blender.feed(cv.UMat(image_warped_s), mask, corners[idx])

    result, result_mask = blender.blend(None, None)
    stitched = cv.normalize(result, None, 0, 255, cv.NORM_MINMAX, dtype=cv.CV_8U)


    t_end = cv.getTickCount()
    time_diff = (t_end - t_start) / cv.getTickFrequency()
    current_fps = 1.0 / time_diff

    frame_counter += 1
    if frame_counter >= fps_update_interval:
        display_fps = round(current_fps)
        frame_counter = 0

    #cv.putText(stitched, f"FPS: {display_fps+1}", (10, 60), cv.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    zoom_scale = 1
    dst = cv.normalize(stitched, None, 0, 255, cv.NORM_MINMAX, dtype=cv.CV_8U)
    dst = cv.resize(dst, None, fx=zoom_scale, fy=zoom_scale, interpolation=cv.INTER_LINEAR)

    cv.namedWindow("Panorama", cv.WINDOW_NORMAL)
    cv.imshow("Panorama", dst)
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
for cam in cams:
    cam.release()
cv.destroyAllWindows()
