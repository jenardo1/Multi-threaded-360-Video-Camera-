import cv2

# for index checking

def capture_frame(camera_index):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Camera {camera_index} could not be opened.")
        return

    # Query native/default resolution
    #cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    #cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    #cap.set(cv2.CAP_PROP_FPS, 24)



    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    ret, frame = cap.read()
    if ret:
        filename = f"camera_{camera_index}_frame_{width}x{height}.jpg"
        cv2.imwrite(filename, frame)
        print(f"[Camera {camera_index}] Saved as '{filename}'.")
    else:
        print(f"[Camera {camera_index}] Failed to capture frame.")

    cap.release()
    #cv2.waitKey(2000)

def find_available_cameras(max_tested=8): # change number of camss
    available = []
    for i in range(max_tested):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
            #cv2.waitKey(2000)
    return available

def main():
    cameras = find_available_cameras()
    if not cameras:
        print("No cameras found.")
        return

    print(f"Found cameras: {cameras}")

    for index in cameras:
        capture_frame(index)

    print("All frames captured and saved.")

if __name__ == "__main__":
    main()
