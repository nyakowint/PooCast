## PooCast

A very sloppily made fork of FlooCast, that uses bluetooth to check the battery level of whatever device you have connected.
Bluetooth is obviously required to be enabled on your PC, along with connecting your device thru whatever method you normally do (presumably your FlooGoo dongle)
A dropped connection or
read failure due to connection problems can still cause devices with announcers to yap "connected" "disconnected" etc etc

You cant firmware update from this fork or upstream either for that matter because they dont include the stuff for it. soz lol

if your name is paige you may leave the pa(i)ge now

As this was made for personal use and not for profeshional shipping, i really cba

Clankers used: GPT-6-Astra and GPT-6.1-Sol
Humans used: the ability to read
yo mama: XBOX LIIIIIIIIIIIIIIVE
my steam? framed. sike im STILL waitlisted mf

# FlooCast

A Python application that allows for the control and configuration of FlooGoo USB Bluetooth dongles.

It configures a FlooGoo FMA120 Bluetooth dongle to pair and connect with a Bluetooth headset/speaker for streaming audio or making VoIP calls. It can also configure the dongle to work as an AuraCast sender.

The dongle functions as a standard USB audio speaker and microphone, requiring no drivers on Windows, macOS, or Linux.

DFU Function Notice

The open-source code in this repository does not include the DFU (Device Firmware Update) functionality.

The DFU implementation provided by the chip vendor is distributed under a different license, which does not allow redistribution as part of this open-source project. For this reason, the DFU-related source code has been excluded from this repository.

If you require DFU support, please download the binary releases provided with this project, which include the DFU functionality.

## Installation

### Windows
On Windows, the compiled App can be downloaded directly from Microsoft Store.

### Linux/Mac

Requires python 3.7+

#### Configure Python Environment
Create a virtual environment and install the required packages.
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Running
After configuring the environment, run `main.py` within it.
```bash
venv/bin/python main.py
```

If your dongle is not found, or if you see a permission denied error, check the [Platform specific notes/issues](#Platform-specific-notes/issues) section.
You may also choose to run the command as root to ensure it has access to the serial device.
```bash
sudo venv/bin/python main.py
```

## Usage

Once configured, the dongle can automatically reconnect to the most recently used device. Please check the support link for more advanced uses. 
 
## Platform specific notes/issues

On Linux, if you run the app as a non-root user, you might get "Permission denied: '/dev/ttyACM0'" error. 
Please verify the ttyACM0 device is the "dialout" user group and add your $USER to the group.
You may take the following link as a reference,
https://askubuntu.com/questions/133235/how-do-i-allow-non-root-access-to-ttyusb0

## Acknowledgements
