import requests
import json
import time
import base64


def generate_better_flux_images(prompt: str, aspect_ratio: str = "3:4"):
    """
    Generate images using freeaiimage.net Flux Schnell API.

    Args:
        prompt: Text description of the image to generate
        aspect_ratio: Image aspect ratio (e.g., "3:4", "16:9", "1:1")
    """
    # API endpoint
    url = "https://freeaiimage.net/api/services/create-flux-schnell"

    # Request payload
    payload = {"aspectRatio": aspect_ratio, "prompt": prompt}

    # Headers (may need to be adjusted based on actual API requirements)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    print(f"Sending request for: {prompt}")

    try:
        # Send initial POST request
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")

        # Check if we need to poll for results
        if "task_id" in result or "id" in result or "taskId" in result:
            task_id = result.get("task_id") or result.get("id") or result.get("taskId")
            print(f"Task created with ID: {task_id}")

            # Poll for completion
            images = poll_for_images(task_id, headers)
        elif "data" in result and result.get("data"):
            # Check if data contains images
            images = (
                result["data"] if isinstance(result["data"], list) else [result["data"]]
            )
        else:
            print("Unexpected response format. Full response:")
            print(json.dumps(result, indent=2))
            return None

        # Download and save images
        if images:
            print(f"got images: {images}\n")
            return save_images_to_mem(images)
        else:
            print("No images found in response")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        if hasattr(e.response, "text"):
            print(f"Response: {e.response.text}")
        return None


def poll_for_images(
    task_id: str, headers: dict, max_attempts: int = 30, interval: int = 2
):
    """
    Poll the API to check if image generation is complete.

    Args:
        task_id: The task ID returned from initial request
        headers: HTTP headers to use
        max_attempts: Maximum number of polling attempts
        interval: Seconds to wait between polls

    Returns:
        List of image URLs or data
    """
    polling_url = f"https://freeaiimage.net/api/services/flux-schnell/{task_id}"

    for attempt in range(max_attempts):
        print(f"Polling attempt {attempt + 1}/{max_attempts}...")
        time.sleep(interval)

        try:
            response = requests.get(polling_url, headers=headers, timeout=10)
            response.raise_for_status()

            result = response.json()

            # Response is an array, get first element
            if isinstance(result, list) and len(result) > 0:
                result = result[0]

            status = result.get("status", "").lower()
            print(f"Status: {status}")

            if status == "completed" or status == "success":
                # Return the data list (image URLs)
                if "data" in result and isinstance(result["data"], list):
                    return result["data"]
                else:
                    print(
                        f"Completed but no images found. Response: {json.dumps(result, indent=2)}"
                    )
                    return []
            elif status == "failed" or status == "error":
                print(f"Task failed: {result.get('message', 'Unknown error')}")
                return []
            elif status == "pending" or status == "processing":
                continue  # Keep polling

        except Exception as e:
            print(f"Polling error: {e}")

    print("Polling timed out")
    return []


def save_images_to_mem(images):
    """
    Download and save images to disk.

    Args:
        images: List of image URLs or base64 data
        output_dir: Directory to save images
        prompt: Original prompt (used for filename)
    """
    images_data = []

    for i, image in enumerate(images):
        try:
            if isinstance(image, str):
                if image.startswith("http"):
                    # Download from URL
                    print(f"Downloading image {i + 1}...")
                    response = requests.get(image, timeout=30)
                    response.raise_for_status()
                    image_data = response.content
                elif image.startswith("data:image"):
                    image_data = base64.b64decode(image.split(",")[1])
                else:
                    print(f"Unknown image format: {image[:100]}")
                    continue
            else:
                print(f"Unexpected image type: {type(image)}")
                continue

            images_data.append(image_data)

        except Exception as e:
            print(f"Error saving image {i + 1}: {e}")
            return None

    return images_data


if __name__ == "__main__":
    # Example usage
    images_data = generate_better_flux_images(
        prompt="a man on a bench",
        aspect_ratio="16:9",
    )
