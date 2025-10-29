from inference_sdk import InferenceHTTPClient

CLIENT = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key="NtndLpbU01xixJJoy4c2"
)

result = CLIENT.infer("/Users/priyanshraj/Documents/Development/Aletheia2.0/photo-1709159057304-2f4d5c9fb37e.webp", model_id="book-counter-rhspr/1")
print(result)

# Display parsed predictions if available
if "predictions" in result:
    print("\nDetected objects:")
    for pred in result["predictions"]:
        class_name = pred.get("class", "unknown")
        confidence = pred.get("confidence", 0)
        print(f"- {class_name}: {confidence:.2f}")
else:
    print("\nNo predictions found in result.")

from PIL import Image, ImageDraw

# Load the original image
image_path = "/Users/priyanshraj/Documents/Development/Aletheia2.0/myimagee.png"
image = Image.open(image_path)
draw = ImageDraw.Draw(image)

# Draw bounding boxes from predictions
if "predictions" in result:
    for pred in result["predictions"]:
        x, y, width, height = pred["x"], pred["y"], pred["width"], pred["height"]
        class_name = pred.get("class", "unknown")
        confidence = pred.get("confidence", 0)

        # Calculate corners of bounding box
        x0 = x - width / 2
        y0 = y - height / 2
        x1 = x + width / 2
        y1 = y + height / 2

        # Draw rectangle and label
        draw.rectangle([x0, y0, x1, y1], outline="red", width=3)
        draw.text((x0, y0 - 10), f"{class_name} ({confidence:.2f})", fill="red")

    # Show image with boxes
    image.show()
else:
    print("\nNo predictions found in result.")