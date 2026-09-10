# Desired Workflow

1. User opens web-ui
2. User positions camera towards the display (live feed as reference)
3. User confirms camera position -> automatic calibration (ROI)
4. User can confirm the ROI, or edit it if needed (chaning the border)
5. after ROI is set/confirmed ocr is set (user can set decimal points, numbers, height width, etc....)
6. when ocr window is set number detection can start
7. detection/detecded numbers can be seen in the log (maybe display the current detected number also in the live feed for easier visibility)

## Other features (unsorted)

- detection of GSVMulti
- selection of GSVMulit/Serial-Bus
- select desired format that fed to GSVMulti
- small camera feed of the cropped/ROI region (so its clearer for the user whats fed into the ocr. picture could be on the top right side of the camera feed)
- rotation of the camera feed (eg. if the camera is placed upsidedown)

## Idea

In the end, this project should offer a clean and simple ux, where the user just starts the tool and then opens the webui sees the live feed an can place the camera accordingly, so that the display is in the fov of the cameras. then he confirms if the display borders and the numbers/ocr are detected correctly, after confirming the process starts and the values are cleanly fed into the  GSVMulti/CSV.

## NEXT FEATURE (priority high)

Work on roi and ocr box selection/editing and confirmation ux is still confusing and buggy (needs clear, self explaining ui)
-> when when double klicking on a roi box the yellow borders dissapear and only small green bordes of the selected (doubleclicked) box remain, while other possible detections are now insible but when cklicking on their position they get selected and have a small green box.
--> think how this ui/ux workflow can be optimized. (are there testing pipelines that can check if ux/ui interactions are ideal? a pipeline complex pipeline would help catch this at the source and make development more efficent)
-> ocr automatic box placement is already working but is often slightly offset, needing user editing, otherwise the detection has no accuracy (think how this can be improved)
-> ocr detection also currently has no selection process like roi, where multiple screens can be detected and one can be selected and confirmed.
