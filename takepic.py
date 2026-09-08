import time

from picamera2 import Picamera2, Preview

# Create camera object
picam2 = Picamera2()

# Configure camera settings
camera_config = picam2.create_still_configuration()
picam2.configure(camera_config)

# Start preview and camera system
picam2.start_preview(Preview.QTGL)
picam2.start()

# Wait 2 seconds to let the camera adjust
time.sleep(2)

# Take a picture and save it
picam2.capture_file("test_photo.jpg")

# Stop camera
picam2.stop()
