import cv2
import mediapipe as mp
import numpy as np
from PIL import Image
from diffusers import LCMSuperResolutionPipeline
import torch

# Initialize selfie segmentation
mp_selfie_segmentation = mp.solutions.selfie_segmentation
selfie_segmentation = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

# Load Stable Diffusion Inpainting model
pipe = LCMSuperResolutionPipeline.from_pretrained("latent-consistency-model")
pipe = pipe.to("cpu")  # CPU usage
pipe.unet = torch.compile(pipe.unet)

# Function to replace background
def replace_background(frame, background):
    output_size = (frame.shape[1], frame.shape[0])
    
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = selfie_segmentation.process(frame_rgb)
    
    # Mask
    mask = result.segmentation_mask
    threshold = 0.5
    binary_mask = (mask > threshold).astype(np.uint8)
    
    # Automatically resize background to match frame size
    if background.shape[:2] != output_size:
        background_resized = cv2.resize(background, output_size)
    else:
        background_resized = background

    # Resize the binary mask to match frame dimensions
    binary_mask_resized = cv2.resize(binary_mask, output_size, interpolation=cv2.INTER_NEAREST)
    binary_mask_resized = binary_mask_resized[:, :, None]

    # Blend the resized frame with the resized background
    combined = frame * binary_mask_resized + background_resized * (1 - binary_mask_resized)
    return combined.astype(np.uint8)

# Function to extend the background image
def outpaint_image(image, output_size):

    # Check if the format is correct
    if isinstance(image, np.ndarray):
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
    elif isinstance(image, Image.Image):
        pil_image = image.convert("RGB")
    else:
        raise ValueError("Input is not an image!")

    # Resize while maintaining aspect ratio
    background_width, background_height = pil_image.size
    scale = min(output_size[0] / background_width, output_size[1] / background_height)
    new_size = (int(background_width * scale), int(background_height * scale))
    pil_resized_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)

    # Create a centered black canvas
    canvas = Image.new("RGB", output_size, (0, 0, 0))
    x_offset = (output_size[0] - new_size[0]) // 2
    y_offset = (output_size[1] - new_size[1]) // 2
    canvas.paste(pil_resized_image, (x_offset, y_offset)) # Add the unmodified image to canvas

    # Create mask for outpainting
    mask = Image.new("L", output_size, 0)

    mask.paste(255, (0, 0, x_offset , output_size[1]))  # Left
    mask.paste(255, (x_offset + new_size[0], 0, output_size[0], output_size[1]))  # Right

    # Perform outpainting
    try:
        outpainted_image = pipe(prompt = "Extend this landscape realistically", 
                                image = canvas, 
                                mask_image = mask, 
                                num_inference_steps = 20).images[0]
    except Exception as e:
        print(f"Pipeline error: {e}")
        raise

    return outpainted_image

def main():
    background_path = "Background.jpg"
    background = cv2.imread(background_path)

    if background is None:
        print("Error: Could not load the background image.")
        return

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

    cv2.namedWindow("Panoramic Output", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Panoramic Output", 1280, 540)

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("Press 'q' to quit.")

    # Generate the outpainted background
    temp_width = (1280 // 8) * 8
    temp_height = (1280 // 8) * 8
    output_size = (temp_width, temp_height)  # Adjusted for Stable Diffusion compatibility
    outpainted_pil = outpaint_image(background, output_size)
    background_outpainted = cv2.cvtColor(np.array(outpainted_pil), cv2.COLOR_RGB2BGR)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        output_frame = replace_background(frame, background)
        cv2.imshow("Panoramic Output", output_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()