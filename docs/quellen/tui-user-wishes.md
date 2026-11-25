# TUI-Wunschliste von Leonhard (Rohfassung, 2026-11-20)

Ursprünglich `tui-user-wishes.md` im Wurzelverzeichnis des Hauptcheckouts;
unverändert übernommen, Quelle für die [Konsolen-Tabs](../superpowers/specs/2026-11-20-picam-konsole-tabs-design.md).

---

Dashboard

- clean with oom for logo/icon
- status info on the left (run active/clibration active?, if run active wich mode/connection is used (as a set-in bullet point)?, camera connected?, web-dashboard/workbench running?, free disk space, used ram, used cpu, which version of project? )
- keybinding/usage info on the bottom (keys to navigate, keys to open help menu, etc...)
- when the calibration or run is active it should be visible in the main dashboard, but not to distracting (the main status info should display the essentials), by clicking on the text/indicator/.... the tui is switching to the workbench dashboard where more details about the run/calibration are shown (current step, config, letency/readings, maybe small animated graphs showing lateny, confidence, valid/transition/unreadable, etc... this should be more like a second metics dashboard than a paralell control interface, meaning everything around the calibration and runs are managed in the workbench, the tui is for general configs, setup, troubleshooting and configuration, not for general use as a workbench tui cli)
- errors/crashes should be pop-up's that clearly communicate the error and give the user options to act.
- the dashboard should have buttons to start/stop the workbench (with extra confirmation when a calibration or run is active, so the user clearly knws the possible risk and consequences), throubleshooting like reconnecting the camera, windows bridge, etc.. should also be possible

Tabs
  Service
    - status of the workbench service
    - start/stop/restart service (also warning if run/calibration is active)
    - logo
    -etc...
    - info (small button, can be opened by cklciking or keyboard, or keybinding). a pop up that briefly explains the service
  camera
    - info about the kamera specs, producer, etc..
    - info about the connected port, the resolution and framerate...
    - options to restart/reconnect the camera, as well as other infos
  bridge
    - the mode (if active or selected) should be visible (maybe tabs on the top showing "direct uart", "uart over bridge", "network", and if the output is disabled this should also somehow be visible in the tab (think of a way yourself)). THE different modes should also show infos about connected ports (if there are any), baudrate, etc... Icons would also be cool where
  certificate
    - it should be clear to the user what "certificate" means. there should be infos like adress, location of the certificate, an option to enable/disable or create a certificate
  storage
    - the remaining and used storage should be displayed, as well as details about what and wich is used (graphic showing usage spit into differetn location/groups, and an option to claer storage if there are pictures/runs saved, there also should be a wrning in the main dashbard if storage is running low and runs could be affected)
  network
    - network stats, ip's (local, external, tailscale, etc...), if existent options to manage or configure these connections should also eb there
  uart
     picture/graphic of he gpio pinout so the user can connect the uart adapter correctly (should also be in the wii and in the first setup), as well as options to change the used ports (if possible ), etc...
  account

misc:

- the password for the workbench should be configured in the setup and also should be changable in the tui
- configs should be editable/changable in the tui, but risk should be clearly dsplayed (if the changes are risky)
- if possible the ui should communicate the function (self explanatory ui/design)
- location of session files and logs should be visible in the tui (maybe also changable)
- the reinstall and install/uninstall of services/software,etc.. should also be possible in the tui (only to a degree and if mostly safe)
